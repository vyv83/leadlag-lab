"""FastAPI application for leadlag-platform.

Exposes the read-only endpoints needed by the HTML UIs under `leadlag/ui/`:
    sessions, strategies, backtests (+ run).

System / collector / paper endpoints belong to Phase 4/5 and are not yet wired.

Run: `python -m leadlag.api` or `uvicorn leadlag.api:app --port 8899`.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from leadlag import load_session, load_strategy, run_backtest, list_sessions as core_list_sessions, run_monte_carlo
from leadlag.backtest import BacktestResult
from leadlag.collections import get_collection, list_collections
from leadlag.contracts import ContractError, read_json
from leadlag.session import Session
from leadlag.monitor import system_stats, read_history, read_pings, list_data_files, read_collector_log, system_processes
from leadlag.monitor.snapshot import read_collector_status
from leadlag.venues import REGISTRY


DATA_DIR = Path("data")
COLLECTOR_PROC: "subprocess.Popen | None" = None
PAPER_PROC: "subprocess.Popen | None" = None
UI_DIR = Path(__file__).parent.parent / "ui"

app = FastAPI(title="leadlag-platform", version="0.1.0")


# ─── root + static ───

@app.get("/")
def root():
    return RedirectResponse("ui/dashboard.html")


if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")


# ─── sessions ───

@app.get("/api/sessions")
def list_sessions():
    return core_list_sessions(DATA_DIR)


@app.get("/api/collections")
def api_collections():
    return [_public_collection(c) for c in list_collections(DATA_DIR)]


@app.post("/api/collections/{collection_id}/analyze")
def api_collection_analyze(collection_id: str, body: dict = Body(default_factory=dict)):
    collection = get_collection(DATA_DIR, collection_id)
    if collection is None:
        raise HTTPException(404, {"error": "collection_not_found", "collection_id": collection_id})
    if not collection.get("tick_file_paths"):
        raise HTTPException(400, {"error": "collection_has_no_ticks", "collection_id": collection_id})

    params = body.get("params") if isinstance(body.get("params"), dict) else dict(body or {})
    try:
        session = Session.build_from_raw(
            collection_id,
            collection["tick_file_paths"],
            collection.get("bbo_file_paths") or [],
            bin_size_ms=int(params.get("bin_size_ms", 50)),
            ema_span_bins=int(params.get("ema_span_bins", params.get("ema_span", 200))),
            threshold_sigma=float(params.get("threshold_sigma", 2.0)),
            follower_max_dev=float(params.get("follower_max_dev", 0.5)),
            cluster_gap_bins=int(params.get("cluster_gap_bins", 60)),
            detection_window_bins=int(params.get("detection_window_bins", 10)),
            confirm_window_bins=int(params.get("confirm_window_bins", 10)),
            window_ms=int(params.get("window_ms", 10_000)),
        )
        out = session.save(DATA_DIR)
    except Exception as e:
        raise HTTPException(400, {"error": "analysis_failed", "type": type(e).__name__, "message": str(e)})
    return {
        "ok": True,
        "collection_id": collection_id,
        "session_id": session.session_id,
        "events_count": session.events.count,
        "n_events": session.events.count,
        "path": str(out),
    }


@app.get("/api/sessions/{session_id}/meta")
def session_meta(session_id: str):
    s = _load_session(session_id)
    return {**s.meta, "quality_summary": _quality_summary(s.quality)}


@app.get("/api/sessions/{session_id}/events")
def session_events(
    session_id: str,
    signal: Optional[str] = None,
    min_mag: Optional[float] = None,
    direction: Optional[int] = None,
    follower: Optional[str] = None,
    min_lagging: Optional[int] = None,
):
    s = _load_session(session_id)
    rows = s.events.rows
    if signal:
        rows = [r for r in rows if r.get("signal") == signal]
    if min_mag is not None:
        rows = [r for r in rows if float(r.get("magnitude_sigma", 0)) >= min_mag]
    if direction is not None:
        rows = [r for r in rows if int(r.get("direction", 0)) == direction]
    if follower:
        rows = [r for r in rows if follower in r.get("lagging_followers", [])]
    if min_lagging is not None:
        rows = [r for r in rows if len(r.get("lagging_followers", [])) >= min_lagging]
    return rows


@app.get("/api/sessions/{session_id}/event/{bin_idx}")
def session_event_detail(session_id: str, bin_idx: int):
    s = _load_session(session_id)
    try:
        return s.event_detail(bin_idx)
    except KeyError:
        raise HTTPException(404, {"error": "event_not_found", "session_id": session_id, "bin_idx": bin_idx})


@app.get("/api/sessions/{session_id}/quality")
def session_quality(session_id: str):
    s = _load_session(session_id)
    return {"quality": s.quality, "meta": s.meta}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    session_dir = DATA_DIR / "sessions" / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"session not found: {session_id}")
    shutil.rmtree(session_dir)
    return {"ok": True}


# ─── strategies ───

@app.get("/api/strategies")
def list_strategies():
    d = DATA_DIR / "strategies"
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.py")):
        entry = {"name": p.stem, "path": str(p), "valid": True, "error": None}
        try:
            s = load_strategy(str(p))
            params = getattr(s, "params", {})
            entry.update({
                "class_name": s.__class__.__name__,
                "description": getattr(s, "description", ""),
                "params": params,
                "version": getattr(s, "version", ""),
                "venues": _extract_venues(params),
                "signal_type": _extract_signal_type(params),
            })
        except Exception as e:
            entry["valid"] = False
            entry["error"] = f"{type(e).__name__}: {e}"
        # last_backtest_summary
        entry["last_backtest_summary"] = _last_backtest_summary(p.stem)
        # status flags
        entry["has_backtest"] = _strategy_has_backtest(p.stem)
        entry["has_paper"] = _strategy_has_paper(p.stem)
        entry["has_live"] = False  # live trading not implemented yet
        out.append(entry)
    return out


@app.get("/api/strategies/{name}")
def strategy_detail(name: str):
    p = DATA_DIR / "strategies" / f"{name}.py"
    if not p.exists():
        raise HTTPException(404, "strategy not found")
    try:
        s = load_strategy(str(p))
        return {
            "name": name,
            "class_name": s.__class__.__name__,
            "description": getattr(s, "description", ""),
            "params": getattr(s, "params", {}),
            "source": p.read_text(),
        }
    except Exception as e:
        return {"name": name, "valid": False, "error": f"{type(e).__name__}: {e}", "source": p.read_text()}


@app.delete("/api/strategies/{name}")
def delete_strategy(name: str):
    p = DATA_DIR / "strategies" / f"{name}.py"
    if p.exists():
        p.unlink()
    return {"ok": True}


@app.post("/api/strategies/save")
def save_strategy(body: dict = Body(...)):
    name = body.get("name")
    code = body.get("code")
    if not name or code is None:
        raise HTTPException(400, {"error": "missing_fields", "required": ["name", "code"]})
    if not name.isidentifier() and not all(c.isalnum() or c in ("_", "-") for c in name):
        raise HTTPException(400, {"error": "invalid_name", "name": name})
    strategies_dir = DATA_DIR / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)
    target = strategies_dir / f"{name}.py"
    target.write_text(code)
    return {"ok": True, "path": str(target)}


# ─── backtests ───

@app.get("/api/backtests")
def list_backtests():
    root = DATA_DIR / "backtest"
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        meta_p = d / "meta.json"
        stats_p = d / "stats.json"
        if not meta_p.exists():
            continue
        meta = json.loads(meta_p.read_text())
        stats = json.loads(stats_p.read_text()) if stats_p.exists() else {}
        out.append({
            "id": d.name,
            "strategy": meta.get("strategy_name"),
            "session_id": meta.get("session_id"),
            "created_at": meta.get("created_at"),
            "n_trades": stats.get("n_trades", 0),
            "total_net_pnl_bps": stats.get("total_net_pnl_bps", 0.0),
            "avg_trade_bps": stats.get("avg_trade_bps", 0.0),
            "win_rate": stats.get("win_rate", 0.0),
            "sharpe": stats.get("sharpe", 0.0),
            "max_drawdown_bps": stats.get("max_drawdown_bps", 0.0),
            "has_montecarlo": (d / "montecarlo.json").exists(),
        })
    return out


@app.get("/api/backtests/{bt_id}/{artifact}")
def backtest_artifact(bt_id: str, artifact: str):
    if artifact not in {"meta", "trades", "equity", "stats", "montecarlo"}:
        raise HTTPException(404, "unknown artifact")
    p = DATA_DIR / "backtest" / bt_id / f"{artifact}.json"
    if not p.exists():
        if artifact == "montecarlo":
            return {}
        raise HTTPException(404, f"{artifact}.json missing")
    return json.loads(p.read_text())


@app.get("/api/backtests/{bt_id}/trade/{trade_id}")
def backtest_trade_detail(bt_id: str, trade_id: int):
    bt_root = DATA_DIR / "backtest" / bt_id
    trades_p = bt_root / "trades.json"
    if not trades_p.exists():
        raise HTTPException(404, {"error": "artifact_missing", "artifact": "trades.json", "backtest_id": bt_id})
    trades = json.loads(trades_p.read_text())
    t = next((x for x in trades if int(x.get("trade_id", -1)) == trade_id), None)
    if t is None:
        raise HTTPException(404, {"error": "trade_not_found", "backtest_id": bt_id, "trade_id": trade_id})
    meta_p = bt_root / "meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    detail = {"trade": t, "meta": meta, "total_trades": len(trades)}
    if meta.get("session_id") and t.get("signal_bin_idx") is not None:
        try:
            session = load_session(meta["session_id"], data_dir=DATA_DIR)
            detail.update(session.event_detail(int(t["signal_bin_idx"])))
        except Exception as exc:
            detail["event_error"] = f"{type(exc).__name__}: {exc}"
    prev_ids = [int(x.get("trade_id", -1)) for x in trades if int(x.get("trade_id", -1)) < trade_id]
    next_ids = [int(x.get("trade_id", -1)) for x in trades if int(x.get("trade_id", -1)) > trade_id]
    detail["prev_trade_id"] = max(prev_ids) if prev_ids else None
    detail["next_trade_id"] = min(next_ids) if next_ids else None
    return detail


@app.post("/api/backtests/run")
def backtest_run(body: dict = Body(...)):
    name = body.get("strategy_name")
    session_id = body.get("session_id")
    params_override = body.get("params_override")
    if not name or not session_id:
        raise HTTPException(400, {"error": "missing_fields", "required": ["strategy_name", "session_id"]})
    strategy_path = DATA_DIR / "strategies" / f"{name}.py"
    if not strategy_path.exists():
        raise HTTPException(400, {"error": "strategy_not_found", "path": str(strategy_path)})
    try:
        strategy = load_strategy(str(strategy_path))
    except Exception as e:
        raise HTTPException(400, {"error": "strategy_load_failed", "type": type(e).__name__, "message": str(e)})
    try:
        session = load_session(session_id, data_dir=DATA_DIR)
    except Exception as e:
        raise HTTPException(400, {"error": "session_load_failed", "type": type(e).__name__, "message": str(e)})
    try:
        result = run_backtest(strategy, session, params_override=params_override, data_dir=DATA_DIR)
        out = result.save(data_dir=DATA_DIR)
    except ContractError as e:
        raise HTTPException(500, {"error": "contract_validation_failed", "message": str(e)})
    except Exception as e:
        raise HTTPException(400, {"error": "backtest_failed", "type": type(e).__name__, "message": str(e)})
    return {"backtest_id": out.name, "n_trades": len(result.trades), "stats": result.stats}


@app.post("/api/backtests/{bt_id}/montecarlo/run")
def backtest_montecarlo_run(bt_id: str, body: dict = Body(default_factory=dict)):
    bt_root = DATA_DIR / "backtest" / bt_id
    if not bt_root.is_dir():
        raise HTTPException(404, {"error": "backtest_not_found", "backtest_id": bt_id})
    trades = read_json(bt_root / "trades.json") if (bt_root / "trades.json").exists() else []
    meta = read_json(bt_root / "meta.json") if (bt_root / "meta.json").exists() else {}
    stats = read_json(bt_root / "stats.json") if (bt_root / "stats.json").exists() else {}
    result = BacktestResult(
        strategy_name=meta.get("strategy_name", bt_id),
        session_id=meta.get("session_id", ""),
        params=meta.get("strategy_params", meta.get("params", {})),
        trades=trades,
        equity=read_json(bt_root / "equity.json") if (bt_root / "equity.json").exists() else [],
        stats=stats,
        meta={**meta, "backtest_id": bt_id},
    )
    mc = run_monte_carlo(
        result,
        n=int(body.get("n_simulations", body.get("n", 10_000))),
        method=body.get("method", "bootstrap"),
        block_size=int(body.get("block_size", 10)),
        seed=body.get("seed", 42),
    )
    mc.save(bt_root)
    return {"ok": True, "backtest_id": bt_id, **mc.summary()}


@app.get("/api/backtests/{bt_id}/montecarlo")
def backtest_montecarlo_get(bt_id: str):
    bt_root = DATA_DIR / "backtest" / bt_id
    if not bt_root.is_dir():
        raise HTTPException(404, {"error": "backtest_not_found", "backtest_id": bt_id})
    mc_path = bt_root / "montecarlo.json"
    if not mc_path.exists():
        return {}
    return json.loads(mc_path.read_text())


# ─── system / dashboard ───

@app.get("/api/system/stats")
def api_system_stats():
    return system_stats()


@app.get("/api/system/history")
def api_system_history(minutes: int = 60):
    return read_history(DATA_DIR, minutes=minutes)


@app.get("/api/system/pings")
def api_system_pings():
    return read_pings(DATA_DIR)


@app.get("/api/system/files")
def api_system_files():
    return list_data_files(DATA_DIR)


@app.get("/api/system/processes")
def api_system_processes():
    return system_processes()


@app.get("/api/venues")
def api_venues():
    return [
        {
            "name": name,
            "role": cfg.role,
            "enabled": cfg.enabled,
            "ws_url": cfg.ws_url,
            "taker_fee_bps": cfg.taker_fee_bps,
            "maker_fee_bps": cfg.maker_fee_bps,
            "bbo_available": cfg.bbo_available,
            "keepalive_type": cfg.keepalive_type,
            "keepalive_interval": cfg.keepalive_interval,
        }
        for name, cfg in REGISTRY.items()
    ]


# ─── collector ───

@app.get("/api/collector/status")
def api_collector_status():
    st = read_collector_status(DATA_DIR)
    proc_alive = COLLECTOR_PROC is not None and COLLECTOR_PROC.poll() is None
    st["proc_alive"] = proc_alive
    st["running_effective"] = bool(proc_alive or st.get("running_effective"))
    st["running"] = st["running_effective"] and not st.get("stale", False)
    return st


@app.get("/api/collector/log")
def api_collector_log(since_ts: Optional[int] = None, venue: Optional[str] = None, type: Optional[str] = None):
    return read_collector_log(DATA_DIR, since_ts=since_ts, venue=venue, event_type=type)


@app.get("/api/collector/files")
def api_collector_files():
    return [f for f in list_data_files(DATA_DIR) if f["path"].startswith(("ticks/", "bbo/"))]


@app.post("/api/collector/start")
def api_collector_start(body: dict = Body(...)):
    global COLLECTOR_PROC
    if COLLECTOR_PROC is not None and COLLECTOR_PROC.poll() is None:
        raise HTTPException(409, "collector already running")
    current = read_collector_status(DATA_DIR)
    if current.get("running_effective") and not current.get("stale"):
        raise HTTPException(409, {"error": "collector_status_running", "session_id": current.get("session_id")})
    duration_s = int(body.get("duration_s", 3600))
    venues = body.get("venues") or []
    rotation_s = int(body.get("rotation_s", 1800))
    bin_size_ms = int(body.get("bin_size_ms", 50))
    if duration_s <= 0 or rotation_s <= 0 or bin_size_ms <= 0:
        raise HTTPException(400, {"error": "invalid_collector_params", "message": "duration_s, rotation_s and bin_size_ms must be positive"})
    cmd = [sys.executable, "-m", "leadlag.collector", "--duration", str(duration_s)]
    if venues:
        cmd += ["--venues", ",".join(venues)]
    cmd += ["--rotation-s", str(rotation_s), "--bin-size-ms", str(bin_size_ms)]
    COLLECTOR_PROC = subprocess.Popen(cmd, cwd=str(DATA_DIR.parent.resolve()))
    return {"ok": True, "pid": COLLECTOR_PROC.pid, "rotation_s": rotation_s, "bin_size_ms": bin_size_ms}


@app.post("/api/collector/stop")
def api_collector_stop():
    global COLLECTOR_PROC
    if COLLECTOR_PROC is None or COLLECTOR_PROC.poll() is not None:
        return {"ok": True, "already_stopped": True}
    try:
        COLLECTOR_PROC.send_signal(signal.SIGINT)
        COLLECTOR_PROC.wait(timeout=10)
    except Exception:
        COLLECTOR_PROC.kill()
    COLLECTOR_PROC = None
    stale = read_collector_status(DATA_DIR)
    if stale.get("stale"):
        _write_json_file(DATA_DIR / ".collector_status.json", {
            **stale,
            "running": False,
            "running_effective": False,
            "cleared_stale": True,
        })
    return {"ok": True}


@app.post("/api/collector/clear-stale")
def api_collector_clear_stale():
    st = read_collector_status(DATA_DIR)
    if not st.get("stale"):
        return {"ok": True, "stale": False}
    st["running"] = False
    st["running_effective"] = False
    st["cleared_stale"] = True
    _write_json_file(DATA_DIR / ".collector_status.json", st)
    return {"ok": True, "stale": True}


# ─── paper trading ───

@app.get("/api/paper/status")
def api_paper_status():
    p = DATA_DIR / ".paper_status.json"
    if not p.exists():
        return {"running": False, "running_effective": False, "blocked": False}
    try:
        st = json.loads(p.read_text())
        proc_alive = PAPER_PROC is not None and PAPER_PROC.poll() is None
        st["proc_alive"] = proc_alive
        st["blocked"] = bool(st.get("blocked") or st.get("mode") == "collector_ipc_pending")
        st["can_trade"] = bool(st.get("running") and not st["blocked"])
        st["running_effective"] = st["can_trade"]
        return st
    except Exception:
        return {"running": False, "running_effective": False, "blocked": False}


@app.post("/api/paper/start")
def api_paper_start(body: dict = Body(...)):
    global PAPER_PROC
    if PAPER_PROC is not None and PAPER_PROC.poll() is None:
        raise HTTPException(409, {"error": "paper_already_running"})
    name = body.get("strategy_name")
    if not name:
        raise HTTPException(400, {"error": "missing_fields", "required": ["strategy_name"]})
    path = DATA_DIR / "strategies" / f"{name}.py"
    if not path.exists():
        raise HTTPException(400, {"error": "strategy_not_found", "path": str(path)})
    duration = body.get("duration_s")
    cmd = [sys.executable, "-m", "leadlag.paper", "--strategy", str(path), "--data-dir", str(DATA_DIR)]
    if duration:
        cmd += ["--duration", str(int(duration))]
    PAPER_PROC = subprocess.Popen(cmd, cwd=str(DATA_DIR.parent.resolve()))
    return {"ok": True, "pid": PAPER_PROC.pid}


@app.post("/api/paper/stop")
def api_paper_stop():
    global PAPER_PROC
    if PAPER_PROC is not None and PAPER_PROC.poll() is None:
        try:
            PAPER_PROC.send_signal(signal.SIGINT)
            PAPER_PROC.wait(timeout=10)
        except Exception:
            PAPER_PROC.kill()
    PAPER_PROC = None
    _write_json_file(DATA_DIR / ".paper_status.json", {"running": False})
    return {"ok": True}


@app.get("/api/paper/strategies")
def api_paper_strategies():
    root = DATA_DIR / "paper"
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        cfg_p = d / "config.json"
        if not cfg_p.exists():
            continue
        out.append({"name": d.name, **json.loads(cfg_p.read_text())})
    return out


@app.get("/api/paper/{name}/trades")
def api_paper_trades(name: str, since_ts: Optional[int] = None):
    return _read_jsonl(DATA_DIR / "paper" / name / "trades.jsonl", since_ts)


@app.get("/api/paper/trades")
def api_paper_current_trades(since_ts: Optional[int] = None):
    name = _current_paper_name()
    return _read_jsonl(DATA_DIR / "paper" / name / "trades.jsonl", since_ts) if name else []


@app.get("/api/paper/{name}/signals")
def api_paper_signals(name: str, last: int = 100):
    rows = _read_jsonl(DATA_DIR / "paper" / name / "signals.jsonl", None)
    return rows[-last:]


@app.get("/api/paper/signals")
def api_paper_current_signals(last: int = 100):
    name = _current_paper_name()
    if not name:
        return []
    rows = _read_jsonl(DATA_DIR / "paper" / name / "signals.jsonl", None)
    return rows[-last:]


@app.get("/api/paper/{name}/equity")
def api_paper_equity(name: str):
    return _read_jsonl(DATA_DIR / "paper" / name / "equity.jsonl", None)


@app.get("/api/paper/equity")
def api_paper_current_equity():
    name = _current_paper_name()
    return _read_jsonl(DATA_DIR / "paper" / name / "equity.jsonl", None) if name else []


@app.get("/api/paper/{name}/positions")
def api_paper_positions(name: str):
    p = DATA_DIR / "paper" / name / "positions.json"
    return json.loads(p.read_text()) if p.exists() else []


@app.get("/api/paper/positions")
def api_paper_current_positions():
    name = _current_paper_name()
    if not name:
        return []
    p = DATA_DIR / "paper" / name / "positions.json"
    return json.loads(p.read_text()) if p.exists() else []


@app.get("/api/paper/stats")
def api_paper_stats():
    trades = api_paper_current_trades()
    if not trades:
        return {"n_trades": 0, "total_net_pnl_bps": 0.0, "win_rate": 0.0}
    total = sum(float(t.get("net_pnl_bps", 0.0)) for t in trades)
    return {
        "n_trades": len(trades),
        "total_net_pnl_bps": total,
        "win_rate": sum(1 for t in trades if float(t.get("net_pnl_bps", 0.0)) > 0) / len(trades),
        "avg_trade_bps": total / len(trades),
        "total_fees_bps": sum(float(t.get("fee_total_bps", 0.0)) for t in trades),
        "total_slippage_bps": sum(float(t.get("slippage_total_bps", 0.0)) for t in trades),
    }


@app.get("/api/paper/venues")
def api_paper_venues():
    p = DATA_DIR / ".paper_venues.json"
    return json.loads(p.read_text()) if p.exists() else []


def _read_jsonl(path: Path, since_ts: Optional[int]) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if since_ts is not None and int(r.get("ts_ms", 0)) < since_ts:
                continue
            out.append(r)
    return out


def _current_paper_name() -> Optional[str]:
    p = DATA_DIR / ".paper_status.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text()).get("strategy")
    except Exception:
        return None


def _write_json_file(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


# ─── helpers ───

def _public_collection(collection: dict) -> dict:
    hidden = {"tick_file_paths", "bbo_file_paths"}
    return {k: v for k, v in collection.items() if k not in hidden}


def _load_session(session_id: str):
    try:
        return load_session(session_id, data_dir=DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(404, f"session not found: {session_id}")


def _quality_summary(q: dict) -> dict:
    if not q:
        return {}
    return {
        "duration_s": q.get("duration_s"),
        "coverage_pct": q.get("coverage_pct"),
        "ticks_per_venue": q.get("ticks_per_venue", {}),
    }


def _extract_venues(params: dict) -> list[str]:
    """Extract venue/follower names from strategy params."""
    for key in ("followers", "venue", "venues", "follower"):
        val = params.get(key)
        if val is not None:
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                return [val]
    return []


def _extract_signal_type(params: dict) -> list[str]:
    """Extract signal types from strategy params."""
    for key in ("signal", "signals"):
        val = params.get(key)
        if val is not None:
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                return [val]
    return []


def _last_backtest_summary(strategy_name: str) -> Optional[dict]:
    """Find latest backtest for a strategy and return summary metrics."""
    bt_root = DATA_DIR / "backtest"
    if not bt_root.is_dir():
        return None
    best: Optional[dict] = None
    best_date: str = ""
    for d in bt_root.iterdir():
        if not d.is_dir():
            continue
        meta_p = d / "meta.json"
        if not meta_p.exists():
            continue
        try:
            meta = json.loads(meta_p.read_text())
        except Exception:
            continue
        if meta.get("strategy_name") != strategy_name:
            continue
        date_str = meta.get("created_at", "")
        if date_str > best_date:
            best_date = date_str
            stats_p = d / "stats.json"
            stats = json.loads(stats_p.read_text()) if stats_p.exists() else {}
            best = {
                "id": d.name,
                "date": date_str,
                "n_trades": stats.get("n_trades", 0),
                "total_net_pnl_bps": stats.get("total_net_pnl_bps", 0.0),
                "win_rate": stats.get("win_rate", 0.0),
                "sharpe": stats.get("sharpe", 0.0),
                "avg_trade_bps": stats.get("avg_trade_bps", 0.0),
            }
    return best


def _strategy_has_backtest(strategy_name: str) -> bool:
    """Check if any backtest exists for this strategy."""
    bt_root = DATA_DIR / "backtest"
    if not bt_root.is_dir():
        return False
    for d in bt_root.iterdir():
        if not d.is_dir():
            continue
        meta_p = d / "meta.json"
        if not meta_p.exists():
            continue
        try:
            meta = json.loads(meta_p.read_text())
        except Exception:
            continue
        if meta.get("strategy_name") == strategy_name:
            return True
    return False


def _strategy_has_paper(strategy_name: str) -> bool:
    """Check if any paper trading session exists for this strategy."""
    paper_root = DATA_DIR / "paper"
    if not paper_root.is_dir():
        return False
    for d in paper_root.iterdir():
        if not d.is_dir():
            continue
        cfg_p = d / "config.json"
        if not cfg_p.exists():
            continue
        try:
            cfg = json.loads(cfg_p.read_text())
        except Exception:
            continue
        if cfg.get("strategy_name") == strategy_name or d.name == strategy_name:
            return True
    return False


def main():
    import uvicorn
    uvicorn.run("leadlag.api:app", host="127.0.0.1", port=8899, reload=False)


if __name__ == "__main__":
    main()
