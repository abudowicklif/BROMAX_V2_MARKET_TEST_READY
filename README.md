# BROMAX TOOL V2 — Market-data research & shadow testing

BROMAX is a read-only research platform for Deriv Digit MATCH final-digit analysis. It predicts only the **next eligible tick** as a research target. It does not place trades, access accounts, or guarantee a predictive edge.

## Important readiness statement

This is a complete runnable V2 research application with a public Deriv feed adapter, persistent tick/signal journal, target-sequence tracking, multi-agent descriptive analysis, conservative abstention, a walk-forward baseline evaluator, FastAPI endpoints and a browser dashboard. It is designed for **controlled shadow market testing**. A profitable edge is not established by software installation or by an attractive dashboard. The system deliberately abstains until genuine out-of-sample evidence and payout inputs justify changing the verifier policy.

The public Deriv feed and schema must be confirmed on the target machine/network. Current public API references:
- Ticks history: https://developers.deriv.com/docs/data/ticks-history/
- Tick stream: https://developers.deriv.com/docs/data/ticks/
- Public market-data workflow: https://developers.deriv.com/docs/workflows/

## Requirements

- Windows 10/11, macOS or Linux
- Python 3.11+
- Internet access to `wss://api.derivws.com`
- No Deriv account token is required or used.

## Windows quick start

1. Extract the ZIP.
2. Open PowerShell in the extracted `BROMAX_V2_MARKET_TEST_READY` folder.
3. Create a virtual environment and install dependencies:

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[test]"
```

4. Copy environment settings:

```powershell
Copy-Item .env.example .env
```

5. Start BROMAX on the alternate port **8765**:

```powershell
python run.py
```

Or double-click `run_windows.bat` to create the virtual environment, install the application and launch it.

6. Open on this computer: http://127.0.0.1:8765
7. To present on a phone connected to the same Wi-Fi, open `http://YOUR-PC-LAN-IP:8765`. Find the PC address with `ipconfig`. Allow Python/port 8765 through Windows Firewall only on a trusted private network.

The default port is deliberately **8765**, not FastAPI/Uvicorn's usual 8000. Change `BROMAX_PORT` in `.env` to choose another available port; `python run.py` reads that setting.

## Start/stop live research

- Select a supported Deriv symbol (default `1HZ100V`) in the dashboard.
- Click **Start live research**.
- The backend requests a bounded historical tick sample, then subscribes to the public tick stream.
- Click **Stop** to close the stream.
- The dashboard refreshes state, ticks, agent diagnostics and journal records.

If the selected symbol is unavailable or the network cannot reach the public endpoint, the system reports a degraded state and reconnects with capped exponential backoff.

## Exact next-tick target semantics

Every accepted tick gets a local monotonic sequence number within a stream generation. A forecast created after sequence N is registered for target sequence N+1. The target is resolved only when that sequence is committed. A tick is an event, not a fixed wall-clock duration; BROMAX cannot know in advance exactly when the next tick will arrive.

A reconnect starts a new stream generation. Pending forecasts from a previous generation are not silently attached to a tick in the new generation. The app's current engine only resolves forecasts when generation and sequence both match.

## API endpoints

- `GET /api/health`
- `GET /api/status`
- `POST /api/research/start` body `{"symbol":"1HZ100V"}`
- `POST /api/research/stop`
- `GET /api/ticks?limit=200`
- `GET /api/agents/latest`
- `GET /api/signals?limit=100`
- `GET /api/events?limit=100`
- `POST /api/backtest/run`
- `WS /ws/live`

There are intentionally no account, proposal, buy, sell, contract, balance or trading routes.

## Run tests

```powershell
pytest -q
```

## Important technical limitations to resolve during the first live-feed validation

1. Provider `pip_size` is required. A missing or inconsistent precision value blocks ingestion rather than guessing.
2. The current V2 target tracker is exact within a single stream generation. If the stream disconnects before the target arrives, a pending forecast remains pending and is not scored against a later generation. An operational review/reconciliation workflow should classify it as invalidated in the next hardening pass.
3. Historical/live overlap suppression currently skips at most one first live message if its epoch and quote exactly match the final history tick. The provider does not guarantee a unique tick ID in every response. Validate overlap behaviour with captured real payloads; do not silently expand de-duplication to epoch-only.
4. The agent models are transparent research baselines, not validated predictive models. The verifier intentionally returns ABSTAIN until a separately validated out-of-sample policy is implemented. Historical backfill does not create live forecast records; forecasts begin only after the live subscription phase.
5. The included walk-forward endpoint is a benchmark baseline (expanding-window most-frequent digit), not a full model-selection research pipeline.
6. SQLite is appropriate for a single-machine research instance. Back up `data/bromax.sqlite3` before upgrades.

## Market-test checklist

- [ ] Public feed connects for the chosen symbol.
- [ ] History returns aligned prices, times and `pip_size`.
- [ ] Live ticks carry quote, epoch and `pip_size`.
- [ ] Final digits verified against the quote's displayed precision.
- [ ] No unresolved feed gap or timestamp-ordering issue.
- [ ] Forecast target is snapshot sequence + 1.
- [ ] Pending outcomes are not included in resolved hit rate.
- [ ] Dashboard reports stale/disconnected state honestly.
- [ ] Read-only mode remains active.
- [ ] No profitable edge is claimed without adequate untouched out-of-sample evidence.

## Safety

This application is a research/shadow-testing tool only. Never add account credentials or trade execution code to this build. Do not use urgency, loss recovery or martingale logic to override the verifier's abstention.
