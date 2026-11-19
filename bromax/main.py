from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path
import asyncio
from .config import settings
from .storage import Store
from .engine import ResearchEngine
from .backtest import walk_forward

store=Store(settings.db_path)
engine=ResearchEngine(store)
clients=set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_start:
        await engine.start()
    yield
    await engine.stop()
    store.close()

app=FastAPI(title="BROMAX TOOL",version="2.0.0",description="Read-only Deriv Digit MATCH research and next-tick shadow testing",lifespan=lifespan)
app.mount("/static",StaticFiles(directory=Path(__file__).resolve().parent.parent/"static"),name="static")

class StartRequest(BaseModel):
    symbol: str | None = Field(default=None,pattern=r"^[A-Za-z0-9_]{2,30}$")

@app.get("/",response_class=HTMLResponse)
async def home():
    return (Path(__file__).resolve().parent.parent/"static"/"index.html").read_text(encoding="utf-8")

@app.get("/api/health")
async def health():
    return {"ok":True,"version":"2.0.0","read_only":True,"trading_enabled":False}

@app.get("/api/status")
async def status():
    return engine.status()

@app.post("/api/research/start")
async def start(req: StartRequest):
    try: return await engine.start(req.symbol)
    except ValueError as e: raise HTTPException(400,str(e))

@app.post("/api/research/stop")
async def stop():
    return await engine.stop()

@app.get("/api/ticks")
async def ticks(limit:int=200):
    if not 1<=limit<=5000: raise HTTPException(400,"limit must be 1..5000")
    return {"items":store.ticks(engine.symbol,limit)}

@app.get("/api/agents/latest")
async def agents():
    return engine.latest_agents()

@app.get("/api/signals")
async def signals(limit:int=100):
    return {"items":store.signals(engine.symbol,min(max(limit,1),500))}

@app.get("/api/events")
async def events(limit:int=100):
    return {"items":store.events(min(max(limit,1),500))}

@app.post("/api/backtest/run")
async def backtest():
    rows=store.ticks(engine.symbol,settings.max_ticks)
    digits=[r["digit"] for r in rows]
    if len(digits)<100:
        raise HTTPException(400,"At least 100 stored ticks are required")
    return walk_forward(digits,train_size=min(1000,max(50,len(digits)//3)),test_size=250)

@app.websocket("/ws/live")
async def live(ws:WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json({"status":engine.status(),"agents":engine.latest_agents(),
                                "signals":store.signals(engine.symbol,20),
                                "ticks":store.ticks(engine.symbol,30)})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
