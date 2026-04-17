# PROGRESS — leadlag-platform build

Running log of implementation progress against [plan.md](plan.md). Read this first when resuming across sessions.

## Roadmap (from plan.md §19)

- [x] **Phase 1** (1-2 weeks) — Python package `leadlag/` — _scaffold done, awaits real-data verification_
- [x] Phase 2 (1 week) — Strategy + Backtest engine (slippage/spread/SL/TP) — _scaffold done, synthetic verified_
- [x] Phase 3 (1 week) — FastAPI + explorer/backtest/trade/strategy UI — _scaffold done, TestClient verified. Montecarlo UI deferred._
- [x] Phase 4 (1 week) — Dashboard + Collector UI + Data Quality — _scaffold done_
- [x] Phase 5 (1 week) — Paper trading + real-time pipeline — _scaffold done, synthetic drive verified_
- [ ] Phase 6 (later) — Real trading

## Session log

### Session 1 — 2026-04-16 — scaffold Phase 1

Goal: create `leadlag/` Python package by porting the 3 research notebooks (`collect_full.txt`, `analysis_full.txt`, `visualization_full.txt`) into clean modules matching the spec in plan.md §2–19.

**Completed:**

- [x] Package skeleton: `pyproject.toml`, `leadlag/__init__.py`, all subpackage init files
- [x] `leadlag/venues/` — 17 parsers + 2 subscribe factories + `VenueConfig` dataclass + registry (all 12 venues registered)
- [x] `config/venues.yaml` — 12-venue config mirrored from plan.md §contract 3
- [x] `leadlag/analysis/` — `binning.py` (50ms VWAP + ffill), `ema.py` (EMA + deviation), `detection.py` (detect_ema_events_v3 + clustering + A/B/C classification), `metrics.py` (lag_50/80, hit, mfe/mae, grid search, bootstrap CI)
- [x] `leadlag/session.py` — `Session` class + `load_session()` + `Session.build_from_raw()` (runs full pipeline on parquet dirs and writes session-contract JSON files per plan.md §contract 2)
- [x] `leadlag/strategy.py` — `Order` + `Strategy` base class + `Event` + `Context` + `BboSnapshot`
- [x] `leadlag/strategy_loader.py` — `load_strategy(path)` with importlib + validation of `on_event(event, ctx)` signature
- [x] `leadlag/collector/` — schemas + async WS engine (ws_venue_task, keepalive, backoff) + rotating parquet writer (30-min, zstd, date-partitioned per plan.md §contract 1)

**Deferred (needs real data or out-of-session-scope):**

- [ ] End-to-end verification `s.events.filter(signal='C').count == 229` — requires the reference parquet dataset (`data/ticks/YYYY-MM-DD/ticks_*.parquet` from the 12h collection on 2026-04-11/12). User needs to point at the data or re-run collector.
- [ ] Rewrite the 3 existing notebooks as thin clients of `leadlag` — deferred (notebooks/ dir created but empty).

**Known design choices / deviations from notebooks:**

- `Session.build_from_raw()` uses the notebook's `analysis_results.pkl` data but writes the proper JSON contract (meta / events / price_windows / bbo_windows / quality) so downstream phases can read it without pickle.
- `session_id = {collection_id}_{params_hash}` (first 8 chars of SHA256 of params JSON) per plan.md §contract 2.
- Collector writes to `data/ticks/YYYY-MM-DD/ticks_*.parquet` and `data/bbo/YYYY-MM-DD/bbo_*.parquet` (date-partitioned) vs notebook's flat `data/ticks_*.parquet`. Loader accepts both layouts.
- `bbo_available` policy: parsers module exposes `BBO_UNAVAILABLE_VENUES = {'MEXC Perp', 'Gate Perp', 'Hyperliquid Perp'}`; `BboSnapshot.available=False` for those so strategies can branch.

**Verification run (2026-04-16):**

- [x] `pip install -e leadlag-lab/` — success
- [x] `from leadlag import load_session, load_strategy, run_backtest` — ok
- [x] `len(REGISTRY) == 12` — ok
- [x] Dummy `Strategy` subclass file loads via `load_strategy()` — ok
- [x] Fabricated session JSON loads via `load_session()`, `s.events.filter(signal='C').count` works — ok
- [x] Synthetic Phase 2 backtest: Lighter/market/fixed slippage → `net_pnl_bps < gross_pnl_bps`; MEXC Perp (no BBO) + `half_spread` → `slippage_source == 'fixed_fallback'`; SL branch exercised; `BacktestResult.save()` writes meta/trades/equity/stats JSON.
- [ ] Real-data `count == 229` — still awaits reference parquet dataset

### Session 2 — 2026-04-16 — Phase 2 backtest engine

- [x] Aligned `Order.qty_btc` with spec (renamed from `size_btc`)
- [x] `leadlag/backtest/slippage.py` — `compute_slippage_bps(model, spread, available, fixed)` returning `(bps, source)` where source ∈ {none, fixed, bbo, fixed_fallback}
- [x] `leadlag/backtest/engine.py` — `run_backtest(strategy, session, params_override)` + `BacktestResult` with full plan.md §contract 5 trade/equity/stats fields. Handles market/limit entry, SL/TP/hold exit, taker/maker fees, position_mode reject/stack/reverse, BBO snapshot lookup with `BBO_UNAVAILABLE_VENUES` fallback, MFE/MAE tracking, 6-field equity (gross/post_fee/net/drawdown), stats with fee_impact + by_entry_type + by_exit_reason + by_venue + by_spread_bucket.
- [x] Exported `run_backtest`, `BacktestResult` from `leadlag.__init__`

### Session 3 — 2026-04-16 — Phase 3 FastAPI + UI

- [x] `leadlag/api/app.py` — FastAPI with endpoints: sessions (list/meta/events/event-detail/quality), strategies (list/detail/delete, scans `data/strategies/*.py`), backtests (list/meta/trades/equity/stats/montecarlo/trade-detail/run).
- [x] `python -m leadlag.api` launches uvicorn on :8899.
- [x] `leadlag/ui/` — static HTML: `dashboard.html`, `explorer.html` (filters + Plotly price window), `strategy.html` (list + run form), `backtest.html` (equity with layers toggle + trades table + stats), `trade.html` (kv dump). Shared `app.js`, `style.css`.
- [x] TestClient smoke test: `/api/sessions`, `/api/strategies`, `/api/sessions/{id}/events?signal=C`, `/api/backtests` all respond correctly against fabricated `data/` tree.
- Deferred: `montecarlo.html`, system/collector/paper endpoints (Phase 4/5), `/api/sessions/{id}/analyze` re-run endpoint, strategy *source editor* page.

### Session 4 — 2026-04-16 — Phase 4 monitor + collector UI + quality

- [x] `leadlag/monitor/snapshot.py` — `system_stats()` (psutil), `read_history()`, `read_pings()`, `read_collector_status()`, `list_data_files()`.
- [x] `leadlag/monitor/daemon.py` — `python -m leadlag.monitor.daemon` writes `data/.system_history.jsonl` every 5s and `data/.ping_cache.json` every 10s (atomic rename); 24h trim.
- [x] API extended: `/api/system/{stats,history,pings,files}`, `/api/collector/{status,start,stop}` (start spawns `python -m leadlag.collector --duration N --venues ...`). 25 routes total.
- [x] `leadlag/collector/__main__.py` — CLI entrypoint wrapping `run_collector`.
- [x] `dashboard.html` now shows system kv + 60-min CPU sparkline (Plotly) + exchange ping table, refreshes every 5s.
- [x] `collector.html` — duration/venues inputs + start/stop + parquet file list.
- [x] `quality.html` — per-session summary + per-venue ticks/bbo/σ table.
- [x] Smoke-tested all new endpoints via TestClient (empty data env).

## How to resume

### Session 5 — 2026-04-16 — Phase 5 realtime + paper trader

- [x] `leadlag/realtime/bin_buffer.py` — incremental 50ms VWAP with forward-fill on empty bins.
- [x] `leadlag/realtime/ema_tracker.py` — EMA + rolling return-std. **Parity check:** vs `pandas.Series.ewm(span=200, adjust=False)` max relative diff 2.9e-16 on 2000-tick random walk (well below 0.1% threshold).
- [x] `leadlag/realtime/bbo_tracker.py` — last-BBO per venue, staleness gate, `BboSnapshot` factory respecting `BBO_UNAVAILABLE_VENUES`.
- [x] `leadlag/realtime/detector.py` — `RealtimeDetector` wires BinBuffer+EmaTracker, arms/fires per-leader first-crossing events with lagging-follower list.
- [x] `leadlag/paper/trader.py` — `PaperTrader` orchestrator: `feed_tick` / `feed_bbo` → detector → strategy.on_event → slippage-adjusted entry → hold_ms / SL / TP exit → writes `config.json`, `signals.jsonl`, `trades.jsonl`, `equity.jsonl`, `positions.json` under `data/paper/{name}/`, plus atomic `data/.paper_status.json`.
- [x] API extended: `/api/paper/status`, `/api/paper/strategies`, `/api/paper/{name}/{trades,signals,equity,positions}`.
- [x] `paper.html` — status kv, equity Plotly line, positions/signals/trades tables, 5s refresh.
- [x] End-to-end synthetic drive: leader shock on `OKX Perp` → detector emits event → `PaperTrader` opens & closes positions, writes all 5 JSON/JSONL files, atomic `.paper_status.json` updated.
- Deferred: live WS wiring in `leadlag/paper/__main__.py` (currently the orchestrator is fed by caller; in production the collector's WS queues should pipe into `feed_tick`/`feed_bbo`). Fill-probability for `entry_type='limit'` in paper mode. Monte Carlo UI.

Phases 1–5 scaffolds are verified against synthetic data.

### Session 6 — 2026-04-16 — deployable under VYV nginx

- [x] UI refactored to be path-prefix aware: `app.js` derives `BASE` from `location.pathname` and every fetch goes through `fetchJSON`/`apiFetch`, so the same static files serve correctly at `http://127.0.0.1:8899/ui/` and at `https://vyv.ftp.sh/leadlag-lab/ui/`.
- [x] All HTML nav / `<link>` / `<script>` paths are now relative (no `/ui/` prefix); dynamic `linkTo("/ui/…")` strings rewritten; `fetch("/api/…")` POSTs wrapped with `apiFetch()`.
- [x] `GET /` now redirects with a **relative** target (`ui/dashboard.html`) so the Location header lands on the correct absolute path whether served at `/` or `/leadlag-lab/`.
- [x] `/root/projects/leadlag-lab/index.html` — VYV dashboard gateway, redirects to `/leadlag-lab/` through nginx (falls back to a “not running” message with the systemctl hint).
- [x] `deploy/leadlag-lab.service`, `deploy/leadlag-monitor.service` — systemd unit files for the FastAPI app (`python -m leadlag.api`) and the monitor daemon.
- [x] `deploy/nginx-leadlag-lab.conf` — `location ^~ /leadlag-lab/` snippet with `proxy_pass http://127.0.0.1:8899/` (trailing slash, `Cache-Control: no-cache`, `Upgrade`/`Connection` headers).
- [x] `README.md` — install, local run, deploy-under-nginx checklist, one-shot commands, path reference.
- [x] Smoke-tested: TestClient `/` 307 → `ui/dashboard.html`, static files 200, `/api/sessions` 200 with data from a fabricated tree.
- No services were started in this session; deployment is ready but not activated. Next step: Phase 4 (Dashboard + Collector UI + Data Quality) — `leadlag-monitor` daemon (`.system_history.jsonl`, `.ping_cache.json`), collector control from UI, `quality.html`. Or pause Phase 4 and port the 3 notebooks + run real collector to validate `count == 229`.

## Open questions for user

- Where is the reference dataset `data/ticks/*` with 863,967 bins / 519 events / 229 signal-C events? Needed for end-to-end verification.
- Confirm we should proceed to Phase 2 (backtest engine) next, or pause for review of Phase 1.
