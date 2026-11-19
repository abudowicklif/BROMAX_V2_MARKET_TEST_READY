import asyncio, json, uuid, time
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal
import websockets
from .models import Tick, normalize_quote, utc_now
from .agents import run_agents
from .config import settings

class ResearchEngine:
    def __init__(self, store):
        self.store=store
        self.symbol=settings.symbol
        self.state="STOPPED"
        self.last_error=None
        self.last_tick_received=None
        self.generation=0
        self.sequence=0
        self.buffer=deque(maxlen=settings.max_ticks)
        self.agent_results={}
        self.task=None
        self.stop_event=asyncio.Event()
        self.lock=asyncio.Lock()
        self.reconnects=0
        self.last_tick=None
        self._has_connected=False
        self._first_live=True
        self._accepting_live=False

    def status(self):
        age=None
        if self.last_tick_received:
            try:
                age=(datetime.now(timezone.utc)-datetime.fromisoformat(self.last_tick_received)).total_seconds()
            except Exception: pass
        return {"state":self.state,"symbol":self.symbol,"generation":self.generation,
                "latest_sequence":self.sequence,"tick_count_buffered":len(self.buffer),
                "last_tick_received":self.last_tick_received,"feed_age_seconds":age,
                "last_error":self.last_error,"reconnects":self.reconnects,
                "read_only":True,"trading_enabled":False}

    async def start(self, symbol=None):
        async with self.lock:
            if self.task and not self.task.done():
                return self.status()
            if symbol:
                if not symbol.replace("_","").isalnum() or len(symbol)>30:
                    raise ValueError("Invalid symbol")
                self.symbol=symbol
            self.stop_event=asyncio.Event()
            self._has_connected=False
            self._accepting_live=False
            self.generation += 1
            self.sequence=0
            self.buffer.clear()
            self.state="CONNECTING"
            self.task=asyncio.create_task(self._run())
        return self.status()

    async def stop(self):
        self.stop_event.set()
        self._accepting_live=False
        self.store.invalidate_generation(
            self.symbol, self.generation,
            "Invalidated: research stream stopped before target resolution."
        )
        if self.task:
            self.task.cancel()
            try: await self.task
            except (asyncio.CancelledError, Exception): pass
        self.state="STOPPED"
        return self.status()

    async def _run(self):
        delay=1
        while not self.stop_event.is_set():
            try:
                self.state="CONNECTING"
                async with websockets.connect(settings.deriv_ws_url, ping_interval=20, ping_timeout=20, close_timeout=5) as ws:
                    if self._has_connected:
                        old_generation = self.generation
                        self.store.invalidate_generation(
                            self.symbol, old_generation,
                            "Invalidated: feed reconnected; target tick continuity could not be proven."
                        )
                        self.generation += 1
                        self.sequence = 0
                        self.buffer.clear()
                        self.last_tick = None
                    self._has_connected = True
                    self._first_live = True
                    self.state="CONNECTED"
                    self.last_error=None
                    await ws.send(json.dumps({"ticks_history":self.symbol,"count":settings.history_count,"end":"latest","style":"ticks","req_id":1}))
                    history_loaded=False
                    async for raw in ws:
                        if self.stop_event.is_set(): break
                        msg=json.loads(raw)
                        if msg.get("error"):
                            raise RuntimeError(msg["error"].get("message","Deriv API error"))
                        if msg.get("msg_type")=="history":
                            await self._load_history(msg)
                            history_loaded=True
                            self._accepting_live=True
                            await ws.send(json.dumps({"ticks":self.symbol,"subscribe":1,"req_id":2}))
                            delay=1
                        elif msg.get("msg_type")=="tick" and msg.get("tick"):
                            await self._ingest_live(msg["tick"])
                if not self.stop_event.is_set():
                    raise ConnectionError("WebSocket closed")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error=str(exc)
                self.state="DEGRADED"
                self.store.log("ERROR","deriv_stream",str(exc))
                self.reconnects += 1
                await asyncio.sleep(delay)
                delay=min(delay*2,settings.reconnect_max_seconds)
        self.state="STOPPED"

    async def _load_history(self, msg):
        history=msg.get("history") or {}
        prices=history.get("prices") or []
        times=history.get("times") or []
        pip=msg.get("pip_size")
        if pip is None or len(prices)!=len(times):
            raise ValueError("History missing pip_size or aligned prices/times")
        # New generation on each run. Keep full history order; sequence assigned locally.
        for price, epoch in zip(prices,times):
            await self._commit_tick(price, int(epoch), int(pip), None)

    async def _ingest_live(self, tick):
        pip=tick.get("pip_size")
        if pip is None:
            raise ValueError("Live tick missing required pip_size")
        quote=tick.get("quote")
        epoch=tick.get("epoch")
        if quote is None or epoch is None:
            raise ValueError("Live tick missing quote or epoch")
        # The first live quote may overlap history's final quote. Suppress exactly one
        # identical first overlap only; subsequent identical prices are valid observations.
        if self._first_live:
            self._first_live=False
            if self.last_tick and str(quote)==self.last_tick.raw_quote and int(epoch)==self.last_tick.source_epoch:
                return
        await self._commit_tick(quote,int(epoch),int(pip),tick.get("id"))

    async def _commit_tick(self, quote, epoch, pip, provider_id):
        normalized,digit=normalize_quote(quote,pip)
        self.sequence += 1
        tick=Tick(symbol=self.symbol,sequence=self.sequence,stream_generation=self.generation,
                  source_epoch=epoch,received_at=utc_now(),raw_quote=str(quote),
                  normalized_quote=normalized,pip_size=pip,digit=digit,provider_id=str(provider_id) if provider_id else None)
        self.store.add_tick(tick)
        self.buffer.append(tick.as_dict())
        self.last_tick=tick
        self.last_tick_received=tick.received_at
        # Resolve any forecast explicitly bound to this next sequence.
        for signal in self.store.pending_signals(self.symbol):
            if signal["generation"]==self.generation and signal["target_sequence"]==tick.sequence:
                self.store.resolve_signal(signal["signal_id"],tick)
        # Analysis on each tick only when enough data; rate limit expensive calls to every 5 ticks.
        if self._accepting_live and len(self.buffer)>=100 and self.sequence % 5 == 0:
            self._analyse()

    def _analyse(self):
        rows=list(self.buffer)
        self.agent_results=run_agents(rows,settings.min_sample)
        ensemble=self.agent_results["ensemble"]
        # Every issued research forecast is journaled, including abstentions.
        sid=str(uuid.uuid4())
        approved=ensemble["status"]=="APPROVED"
        signal={"signal_id":sid,"symbol":self.symbol,"generation":self.generation,
                "snapshot_sequence":self.sequence,"target_sequence":self.sequence+1,
                "created_at":utc_now(),"predicted_digit":ensemble["candidate"] if approved else None,
                "probabilities":ensemble["probabilities"],"status":"PENDING",
                "verifier_reason":ensemble["reason"],"model_version":"bromax-v2.0"}
        self.store.create_signal(signal)
        self.store.log("INFO","signal_engine","Forecast journaled",{"signal_id":sid,"target_sequence":self.sequence+1,"status":ensemble["status"]})

    def snapshot(self):
        return list(self.buffer)

    def latest_agents(self):
        return self.agent_results
