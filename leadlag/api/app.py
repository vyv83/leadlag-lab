"""FastAPI application for leadlag-platform.

Exposes the read-only endpoints needed by the HTML UIs under `leadlag/ui/`:
    sessions, strategies, backtests (+ run).

System / collector / paper endpoints belong to Phase 4/5 and are not yet wired.

Run: `python -m leadlag.api` or `uvicorn leadlag.api:app --port 8899`.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from leadlag import load_session, load_strategy, run_backtest
from leadlag.monitor import system_stats, read_history, read_pings, list_data_files
from leadlag.monitor.snapshot import read_collector_status


DATA_DIR = Path("data")
COLLECTOR_PROC: "subprocess.Popen | None" = None
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
    root = DATA_DIR / "sessions"
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        meta_p = d / "meta.json"
        if not meta_p.exists():
            continue
        meta = json.loads(meta_p.read_text())
        out.append({
            "id": meta.get("session_id", d.name),
            "collection_id": meta.get("collection_id"),
            "params_hash": meta.get("params_hash"),
            "n_events": meta.get("n_events", 0),
            "n_signal_c": meta.get("n_signal_c", 0),
            "venues": meta.get("venues", []),
        })
    return out


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
    ev = next((r for r in s.events.rows if int(r.get("bin_idx", -1)) == bin_idx), None)
    if ev is None:
        raise HTTPException(404, f"Event bin_idx={bin_idx} not found")
    pw = next((w for w in s.price_windows if int(w.get("bin_idx", -1)) == bin_idx), None)
    bw = next((w for w in s.bbo_windows if int(w.get("bin_idx", -1)) == bin_idx), None)
    return {"event": ev, "price_window": pw, "bbo_window": bw}


@app.get("/api/sessions/{session_id}/quality")
def session_quality(session_id: str):
    s = _load_session(session_id)
    return {"quality": s.quality, "meta": s.meta}


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
            entry.update({
                "class_name": s.__class__.__name__,
                "description": getattr(s, "description", ""),
                "params": getattr(s, "params", {}),
            })
        except Exception as e:
            entry["valid"] = False
            entry["error"] = f"{type(e).__name__}: {e}"
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
            "win_rate": stats.get("win_rate", 0.0),
            "sharpe": stats.get("sharpe", 0.0),
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
    trades_p = DATA_DIR / "backtest" / bt_id / "trades.json"
    if not trades_p.exists():
        raise HTTPException(404, "trades.json missing")
    trades = json.loads(trades_p.read_text())
    t = next((x for x in trades if int(x.get("trade_id", -1)) == trade_id), None)
    if t is None:
        raise HTTPException(404, f"trade_id={trade_id} not found")
    return {"trade": t}


@app.post("/api/backtests/run")
def backtest_run(body: dict = Body(...)):
    name = body.get("strategy_name")
    session_id = body.get("session_id")
    params_override = body.get("params_override")
    if not name or not session_id:
        raise HTTPException(400, "strategy_name and session_id required")
    strategy_path = DATA_DIR / "strategies" / f"{name}.py"
    if not strategy_path.exists():
        raise HTTPException(400, f"Strategy file not found: {strategy_path}")
    try:
        strategy = load_strategy(str(strategy_path))
    except Exception as e:
        raise HTTPException(400, f"Strategy load failed: {type(e).__name__}: {e}")
    try:
        session = load_session(session_id, data_dir=DATA_DIR)
    except Exception as e:
        raise HTTPException(400, f"Session load failed: {type(e).__name__}: {e}")
    result = run_backtest(strategy, session, params_override=params_override, data_dir=DATA_DIR)
    out = result.save(data_dir=DATA_DIR)
    return {"backtest_id": out.name, "n_trades": len(result.trades)}


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


# ─── collector ───

@app.get("/api/collector/status")
def api_collector_status():
    st = read_collector_status(DATA_DIR)
    st["proc_alive"] = COLLECTOR_PROC is not None and COLLECTOR_PROC.poll() is None
    return st


@app.post("/api/collector/start")
def api_collector_start(body: dict = Body(...)):
    global COLLECTOR_PROC
    if COLLECTOR_PROC is not None and COLLECTOR_PROC.poll() is None:
        raise HTTPException(409, "collector already running")
    duration_s = int(body.get("duration_s", 3600))
    venues = body.get("venues") or []
    cmd = [sys.executable, "-m", "leadlag.collector", "--duration", str(duration_s)]
    if venues:
        cmd += ["--venues", ",".join(venues)]
    COLLECTOR_PROC = subprocess.Popen(cmd, cwd=str(DATA_DIR.parent.resolve()))
    return {"ok": True, "pid": COLLECTOR_PROC.pid}


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
    return {"ok": True}


# ─── paper trading ───

@app.get("/api/paper/status")
def api_paper_status():
    p = DATA_DIR / ".paper_status.json"
    if not p.exists():
        return {"running": False}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"running": False}


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


@app.get("/api/paper/{name}/signals")
def api_paper_signals(name: str, last: int = 100):
    rows = _read_jsonl(DATA_DIR / "paper" / name / "signals.jsonl", None)
    return rows[-last:]


@app.get("/api/paper/{name}/equity")
def api_paper_equity(name: str):
    return _read_jsonl(DATA_DIR / "paper" / name / "equity.jsonl", None)


@app.get("/api/paper/{name}/positions")
def api_paper_positions(name: str):
    p = DATA_DIR / "paper" / name / "positions.json"
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


# ─── helpers ───

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


def main():
    import uvicorn
    uvicorn.run("leadlag.api:app", host="127.0.0.1", port=8899, reload=False)


if __name__ == "__main__":
    main()
