"""FastAPI application for leadlag-platform.

Exposes the read-only endpoints needed by the HTML UIs under `leadlag/ui/`:
    analyses, strategies, backtests (+ run).

System / collector / paper endpoints belong to Phase 4/5 and are not yet wired.

Run: `python -m leadlag.api` or `uvicorn leadlag.api:app --port 8899`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from leadlag import load_analysis, load_strategy, run_backtest, list_analyses as core_list_analyses, run_monte_carlo
from leadlag.backtest import BacktestResult
from leadlag.collections import get_collection, list_collections
from leadlag.contracts import ContractError, read_json
from leadlag.session import Analysis, make_analysis_id
from leadlag.monitor import system_stats, read_history, read_pings, list_data_files, read_collector_log, system_processes
from leadlag.monitor.snapshot import read_collector_status
from leadlag.venues import REGISTRY


DATA_DIR = Path("data")
COLLECTOR_PROC: "subprocess.Popen | None" = None
PAPER_PROC: "subprocess.Popen | None" = None
UI_DIR = Path(__file__).parent.parent / "ui"
ANALYSIS_JOBS_DIRNAME = ".analysis_jobs"
BACKTEST_JOBS_DIRNAME = ".backtest_jobs"
BACKTEST_STATUS_FILENAME = ".backtest_status.json"

app = FastAPI(title="leadlag-platform", version="0.1.0")


# ─── root + static ───

@app.get("/")
def root():
    return RedirectResponse("ui/dashboard.html")


@app.get("/leadlag-lab/")
def leadlag_lab_root():
    return RedirectResponse("/leadlag-lab/ui/dashboard.html")


if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")


# ─── analyses ───


@app.get("/api/analyses")
def list_analyses():
    return [_public_analysis_row(row) for row in core_list_analyses(DATA_DIR)]


@app.get("/api/collections")
def api_collections():
    return [_public_collection(c) for c in list_collections(DATA_DIR)]


def _analysis_job_path(data_dir: Path | str, job_id: str) -> Path:
    root = Path(data_dir) / ANALYSIS_JOBS_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{job_id}.json"


def _write_analysis_job(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def _backtest_job_path(data_dir: Path | str, job_id: str) -> Path:
    root = Path(data_dir) / BACKTEST_JOBS_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{job_id}.json"


def _write_backtest_job(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def _backtest_status_path(data_dir: Path | str = DATA_DIR) -> Path:
    return Path(data_dir) / BACKTEST_STATUS_FILENAME


def _write_backtest_status(payload: dict, data_dir: Path | str = DATA_DIR) -> Path:
    path = _backtest_status_path(data_dir)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)
    return path


def _read_backtest_status(data_dir: Path | str = DATA_DIR) -> dict | None:
    path = _backtest_status_path(data_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _pid_alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
    except Exception:
        return False
    return True


def _acquire_backtest_slot(strategy_name: str, analysis_id: str, data_dir: Path | str = DATA_DIR) -> dict:
    """Allow only one backtest worker at a time on this server."""
    now_ms = int(time.time() * 1000)
    payload = {
        "running": True,
        "status": "starting",
        "strategy_name": strategy_name,
        "analysis_id": analysis_id,
        "request_pid": os.getpid(),
        "worker_pid": None,
        "started_at_ms": now_ms,
        "updated_at_ms": now_ms,
    }
    path = _backtest_status_path(data_dir)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                json.dump(payload, fh, indent=2)
            return payload
        except FileExistsError:
            existing = _read_backtest_status(data_dir) or {}
            worker_pid = existing.get("worker_pid")
            updated_at_ms = int(existing.get("updated_at_ms") or existing.get("started_at_ms") or 0)
            age_ms = now_ms - updated_at_ms
            if worker_pid and _pid_alive(worker_pid):
                raise HTTPException(409, {
                    "error": "backtest_already_running",
                    "message": "Another backtest is already running on the server.",
                    "running": existing,
                })
            if age_ms < 5 * 60 * 1000:
                raise HTTPException(409, {
                    "error": "backtest_start_in_progress",
                    "message": "A backtest start is already in progress.",
                    "running": existing,
                })
            try:
                path.unlink()
            except FileNotFoundError:
                pass
    raise HTTPException(409, {
        "error": "backtest_slot_busy",
        "message": "Could not acquire backtest execution slot.",
    })


def _update_backtest_slot(data_dir: Path | str = DATA_DIR, **updates: Any) -> dict | None:
    current = _read_backtest_status(data_dir)
    if current is None:
        return None
    current.update(updates)
    current["updated_at_ms"] = int(time.time() * 1000)
    _write_backtest_status(current, data_dir=data_dir)
    return current


def _release_backtest_slot(data_dir: Path | str = DATA_DIR) -> None:
    path = _backtest_status_path(data_dir)
    try:
        path.unlink()
    except FileNotFoundError:
        pass


@app.get("/api/backtests/status")
def backtest_status():
    current = _read_backtest_status(DATA_DIR)
    if not current:
        return {"running": False}
    worker_pid = current.get("worker_pid")
    if worker_pid and not _pid_alive(worker_pid):
        _release_backtest_slot(DATA_DIR)
        return {"running": False, "stale": True}
    return _public_payload(current)


@app.get("/api/backtest-jobs/{job_id}")
def backtest_job_status(job_id: str):
    path = _backtest_job_path(DATA_DIR, job_id)
    if not path.exists():
        raise HTTPException(404, {"error": "backtest_job_not_found", "job_id": job_id})
    return _public_payload(json.loads(path.read_text()))


def _normalize_analysis_params(body: dict | None) -> dict:
    raw = body.get("params") if isinstance((body or {}).get("params"), dict) else dict(body or {})
    return {
        "bin_size_ms": int(raw.get("bin_size_ms", 50)),
        "ema_span_bins": int(raw.get("ema_span_bins", raw.get("ema_span", 200))),
        "threshold_sigma": float(raw.get("threshold_sigma", 2.0)),
        "follower_max_dev": float(raw.get("follower_max_dev", 0.5)),
        "cluster_gap_bins": int(raw.get("cluster_gap_bins", 60)),
        "detection_window_bins": int(raw.get("detection_window_bins", 10)),
        "confirm_window_bins": int(raw.get("confirm_window_bins", 10)),
        "window_ms": int(raw.get("window_ms", 10_000)),
    }


def _public_payload(payload: dict) -> dict:
    out = dict(payload)
    if "collection_id" in out:
        out["recording_id"] = out["collection_id"]
    return out


def _public_analysis_row(row: dict) -> dict:
    out = _public_payload(row)
    if "id" in out and "analysis_id" not in out:
        out["analysis_id"] = out["id"]
    return out


def _analyze_worker(job_path: str, job_id: str, collection_id: str, tick_files: list, bbo_files: list, params: dict, data_dir: str) -> dict:
    """Runs in a subprocess so OOM-kill doesn't take down uvicorn."""
    from pathlib import Path

    status_path = Path(job_path)

    def update(stage: str, message: str, progress: float, *, status: str = "running", extra: dict | None = None) -> None:
        current = {
            "job_id": job_id,
            "collection_id": collection_id,
            "analysis_id": make_analysis_id(collection_id, params),
            "status": status,
            "stage": stage,
            "message": message,
            "progress": max(0.0, min(1.0, float(progress))),
            "params": params,
            "updated_at_ms": int(time.time() * 1000),
        }
        if extra:
            current.update(extra)
        _write_analysis_job(status_path, current)

    update("starting", "Worker process started", 0.01)
    analysis = Analysis.build_from_raw(
        collection_id, tick_files, bbo_files,
        bin_size_ms=params["bin_size_ms"],
        ema_span_bins=params["ema_span_bins"],
        threshold_sigma=params["threshold_sigma"],
        follower_max_dev=params["follower_max_dev"],
        cluster_gap_bins=params["cluster_gap_bins"],
        detection_window_bins=params["detection_window_bins"],
        confirm_window_bins=params["confirm_window_bins"],
        window_ms=params["window_ms"],
        progress_callback=update,
    )
    update("saving", "Saving analysis artifacts", 0.98)
    out = analysis.save(Path(data_dir))
    result = {
        "analysis_id": analysis.analysis_id,
        "events_count": analysis.events.count,
        "path": str(out),
    }
    update("complete", f"Analysis ready: {analysis.events.count} events", 1.0, status="completed", extra=result)
    return result


@app.post("/api/collections/{collection_id}/analyze")
def api_collection_analyze(collection_id: str, body: dict = Body(default_factory=dict)):
    import multiprocessing

    collection = get_collection(DATA_DIR, collection_id)
    if collection is None:
        raise HTTPException(404, {"error": "collection_not_found", "collection_id": collection_id})
    if not collection.get("tick_file_paths"):
        raise HTTPException(400, {"error": "collection_has_no_ticks", "collection_id": collection_id})

    params = _normalize_analysis_params(body)
    analysis_id = make_analysis_id(collection_id, params)
    will_overwrite = (DATA_DIR / "analyses" / analysis_id).exists()
    job_id = str(uuid.uuid4())
    job_path = _analysis_job_path(DATA_DIR, job_id)
    payload = {
        "job_id": job_id,
        "collection_id": collection_id,
        "analysis_id": analysis_id,
        "status": "queued",
        "stage": "queued",
        "message": "Analysis queued",
        "progress": 0.0,
        "params": params,
        "updated_at_ms": int(time.time() * 1000),
        "will_overwrite": will_overwrite,
    }
    _write_analysis_job(job_path, payload)

    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(
        target=_run_analysis_job,
        args=(
            str(job_path),
            job_id,
            collection_id,
            collection["tick_file_paths"],
            collection.get("bbo_file_paths") or [],
            params,
            str(DATA_DIR),
        ),
        daemon=True,
    )
    proc.start()
    return {
        "ok": True,
        "queued": True,
        "job_id": job_id,
        "collection_id": collection_id,
        "analysis_id": analysis_id,
        "events_count": None,
        "will_overwrite": will_overwrite,
        "status_url": f"/api/analysis-jobs/{job_id}",
    }


def _run_analysis_job(job_path: str, job_id: str, collection_id: str, tick_files: list, bbo_files: list, params: dict, data_dir: str) -> None:
    try:
        _analyze_worker(job_path, job_id, collection_id, tick_files, bbo_files, params, data_dir)
    except Exception as e:
        _write_analysis_job(Path(job_path), {
            "job_id": job_id,
            "collection_id": collection_id,
            "analysis_id": make_analysis_id(collection_id, params),
            "status": "failed",
            "stage": "failed",
            "message": str(e),
            "error": {
                "type": type(e).__name__,
                "message": str(e),
            },
            "progress": 1.0,
            "params": params,
            "updated_at_ms": int(time.time() * 1000),
        })


@app.get("/api/analysis-jobs/{job_id}")
def api_analysis_job_status(job_id: str):
    job_path = _analysis_job_path(DATA_DIR, job_id)
    if not job_path.exists():
        raise HTTPException(404, {"error": "analysis_job_not_found", "job_id": job_id})
    return _public_payload(json.loads(job_path.read_text()))

@app.get("/api/analyses/{analysis_id}/meta")
def analysis_meta(analysis_id: str):
    analysis = _load_analysis(analysis_id)
    return _public_payload({**analysis.meta, "quality_summary": _quality_summary(analysis.quality)})

@app.get("/api/analyses/{analysis_id}/events")
def analysis_events(
    analysis_id: str,
    signal: Optional[str] = None,
    min_mag: Optional[float] = None,
    direction: Optional[int] = None,
    follower: Optional[str] = None,
    min_lagging: Optional[int] = None,
):
    analysis = _load_analysis(analysis_id)
    rows = analysis.events.rows
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


@app.get("/api/analyses/{analysis_id}/event/{bin_idx}")
def analysis_event_detail(analysis_id: str, bin_idx: int):
    analysis = _load_analysis(analysis_id)
    try:
        return analysis.event_detail(bin_idx)
    except KeyError:
        raise HTTPException(404, {"error": "event_not_found", "analysis_id": analysis_id, "bin_idx": bin_idx})


@app.get("/api/analyses/{analysis_id}/quality")
def analysis_quality(analysis_id: str):
    analysis = _load_analysis(analysis_id)
    return {"quality": analysis.quality, "meta": _public_payload(analysis.meta)}


def _delete_backtests_for_analysis_ids(analysis_ids: set[str]) -> int:
    if not analysis_ids:
        return 0
    bt_root = DATA_DIR / "backtest"
    if not bt_root.is_dir():
        return 0
    removed_backtests = 0
    for d in list(bt_root.iterdir()):
        if not d.is_dir():
            continue
        meta_p = d / "meta.json"
        if not meta_p.exists():
            continue
        try:
            meta = json.loads(meta_p.read_text())
        except Exception:
            continue
        if meta.get("analysis_id") in analysis_ids:
            shutil.rmtree(d, ignore_errors=True)
            removed_backtests += 1
    return removed_backtests


@app.delete("/api/analyses/{analysis_id}")
def delete_analysis(analysis_id: str):
    analysis_dir = DATA_DIR / "analyses" / analysis_id
    if not analysis_dir.exists():
        raise HTTPException(404, f"analysis not found: {analysis_id}")
    removed_backtests = _delete_backtests_for_analysis_ids({analysis_id})
    shutil.rmtree(analysis_dir, ignore_errors=True)
    return {"ok": True, "removed_backtests": removed_backtests, "analysis_id": analysis_id}


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
            entry_type = params.get("entry_type", getattr(s, "entry_type", "market"))
            slippage_model = params.get("slippage_model", getattr(s, "slippage_model", "half_spread"))
            position_mode = params.get("position_mode", getattr(s, "position_mode", "reject"))
            entry.update({
                "class_name": s.__class__.__name__,
                "description": getattr(s, "description", ""),
                "params": params,
                "param_keys": _extract_strategy_param_keys(p.read_text(), params),
                "version": getattr(s, "version", ""),
                "venues": _extract_venues(params),
                "signal_type": _extract_signal_type(params),
                "entry_type": entry_type,
                "slippage_model": slippage_model,
                "position_mode": position_mode,
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
def delete_strategy(name: str, include_notebook: bool = Query(default=False)):
    p = DATA_DIR / "strategies" / f"{name}.py"
    if not p.exists():
        raise HTTPException(404, "strategy not found")
    # guard: block if paper trading is using this strategy
    paper_status_path = DATA_DIR / ".paper_status.json"
    if paper_status_path.exists():
        try:
            ps = json.loads(paper_status_path.read_text())
            if ps.get("running") and ps.get("strategy_name") == name:
                raise HTTPException(409, {"error": "strategy_in_use_by_paper", "message": "Stop paper trading before deleting this strategy"})
        except HTTPException:
            raise
        except Exception:
            pass
    # cascade: delete related backtests + MC
    bt_root = DATA_DIR / "backtest"
    removed_backtests = 0
    if bt_root.is_dir():
        for d in list(bt_root.iterdir()):
            if not d.is_dir():
                continue
            meta_p = d / "meta.json"
            if not meta_p.exists():
                continue
            try:
                meta = json.loads(meta_p.read_text())
            except Exception:
                continue
            if meta.get("strategy_name") == name:
                shutil.rmtree(d, ignore_errors=True)
                removed_backtests += 1
    # cascade: delete related paper runs
    paper_root = DATA_DIR / "paper"
    if paper_root.is_dir():
        for d in list(paper_root.iterdir()):
            if not d.is_dir():
                continue
            cfg_p = d / "config.json"
            if not cfg_p.exists():
                if d.name == name:
                    shutil.rmtree(d, ignore_errors=True)
                continue
            try:
                cfg = json.loads(cfg_p.read_text())
            except Exception:
                continue
            if cfg.get("strategy_name") == name or d.name == name:
                shutil.rmtree(d, ignore_errors=True)
    # delete .py
    p.unlink()
    # optionally delete notebook
    nb_deleted = False
    if include_notebook:
        for nb_dir in [DATA_DIR.parent / "notebooks", DATA_DIR / "notebooks"]:
            nb_p = nb_dir / f"{name}.ipynb"
            if nb_p.exists():
                nb_p.unlink()
                nb_deleted = True
                break
    return {"ok": True, "removed_backtests": removed_backtests, "notebook_deleted": nb_deleted}


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
        total_net_pnl_bps = stats.get("total_net_pnl_bps", 0.0)
        max_drawdown_bps = stats.get("max_drawdown_bps", 0.0)
        recovery_factor = stats.get("recovery_factor")
        if recovery_factor is None and isinstance(max_drawdown_bps, (int, float)) and max_drawdown_bps < 0:
            recovery_factor = float(total_net_pnl_bps / abs(max_drawdown_bps))
        out.append({
            "id": d.name,
            "strategy": meta.get("strategy_name"),
            "analysis_id": meta.get("analysis_id"),
            "created_at": meta.get("created_at"),
            "backtest_date_utc": meta.get("backtest_date_utc"),
            "strategy_version": meta.get("strategy_version"),
            "strategy_description": meta.get("strategy_description"),
            "params": meta.get("params", {}),
            "strategy_params": meta.get("strategy_params", {}),
            "params_override": meta.get("params_override", {}),
            "entry_type": meta.get("entry_type"),
            "slippage_model": meta.get("slippage_model"),
            "position_mode": meta.get("position_mode"),
            "fixed_slippage_bps": meta.get("fixed_slippage_bps"),
            "engine_version": meta.get("engine_version"),
            "computation_time_s": meta.get("computation_time_s"),
            "n_trades": stats.get("n_trades", 0),
            "total_net_pnl_bps": total_net_pnl_bps,
            "total_gross_pnl_bps": stats.get("total_gross_pnl_bps", 0.0),
            "avg_trade_bps": stats.get("avg_trade_bps", 0.0),
            "profit_factor": stats.get("profit_factor"),
            "recovery_factor": recovery_factor,
            "win_rate": stats.get("win_rate", 0.0),
            "sharpe": stats.get("sharpe", 0.0),
            "max_drawdown_bps": max_drawdown_bps,
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
    payload = json.loads(p.read_text())
    return _public_payload(payload) if artifact == "meta" else payload


def _backtest_worker(
    strategy_path: str,
    strategy_name: str,
    analysis_id: str,
    params_override: dict | None,
    data_dir: str,
    progress_callback=None,
) -> dict:
    if progress_callback:
        progress_callback("loading_strategy", "Loading strategy…", 0.10)
    try:
        strategy = load_strategy(strategy_path)
        if getattr(strategy, "name", "") in ("", "UnnamedStrategy"):
            strategy.name = strategy_name
    except Exception as e:
        return {
            "ok": False,
            "status": 400,
            "error": {"error": "strategy_load_failed", "type": type(e).__name__, "message": str(e)},
        }
    if progress_callback:
        progress_callback("loading_session", "Loading analysis artifacts…", 0.22)
    try:
        analysis = load_analysis(analysis_id, data_dir=data_dir)
    except Exception as e:
        return {
            "ok": False,
            "status": 400,
            "error": {"error": "analysis_load_failed", "type": type(e).__name__, "message": str(e)},
        }
    if progress_callback:
        progress_callback("running_backtest", "Running backtest engine…", 0.55)
    try:
        result = run_backtest(strategy, analysis, params_override=params_override, data_dir=data_dir)
        if progress_callback:
            progress_callback("saving", "Saving backtest artifacts…", 0.88)
        out = result.save(data_dir=data_dir)
    except ContractError as e:
        return {
            "ok": False,
            "status": 500,
            "error": {"error": "contract_validation_failed", "message": str(e)},
        }
    except Exception as e:
        return {
            "ok": False,
            "status": 400,
            "error": {"error": "backtest_failed", "type": type(e).__name__, "message": str(e)},
        }
    return {
        "ok": True,
        "data": {"backtest_id": out.name, "n_trades": len(result.trades), "stats": result.stats},
    }


def _run_backtest_job(job_path: str, job_id: str, strategy_path: str, strategy_name: str, analysis_id: str, params_override: dict | None, data_dir: str) -> None:
    path = Path(job_path)
    try:
        payload = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        payload = {}

    def update(status: str, message: str, extra: dict | None = None) -> None:
        current = {
            **payload,
            "job_id": job_id,
            "strategy_name": strategy_name,
            "analysis_id": analysis_id,
            "status": status,
            "message": message,
            "stage": current_stage.get("stage", payload.get("stage", "queued")),
            "progress": current_stage.get("progress", payload.get("progress", 0.0)),
            "updated_at_ms": int(time.time() * 1000),
        }
        if extra:
            current.update(extra)
        _write_backtest_job(path, current)

    current_stage = {
        "stage": payload.get("stage", "queued"),
        "progress": float(payload.get("progress", 0.0) or 0.0),
    }

    def update_stage(stage: str, message: str, progress: float) -> None:
        current_stage["stage"] = stage
        current_stage["progress"] = max(0.0, min(1.0, float(progress)))
        update("running", message)

    try:
        current_stage["stage"] = "starting"
        current_stage["progress"] = 0.04
        update("running", "Backtest worker started", {"worker_pid": os.getpid()})
        _update_backtest_slot(
            data_dir,
            status="running",
            worker_pid=os.getpid(),
            strategy_name=strategy_name,
            analysis_id=analysis_id,
            job_id=job_id,
        )
        result = _backtest_worker(
            strategy_path,
            strategy_name,
            analysis_id,
            params_override,
            data_dir,
            progress_callback=update_stage,
        )
        if result.get("ok"):
            data = result["data"]
            current_stage["stage"] = "completed"
            current_stage["progress"] = 1.0
            update("completed", f"Backtest ready: {data['backtest_id']}", data)
        else:
            current_stage["stage"] = "failed"
            current_stage["progress"] = 1.0
            update("failed", result.get("error", {}).get("message", "Backtest failed"), {
                "error": result.get("error"),
                "http_status": result.get("status", 500),
            })
    except Exception as e:
        current_stage["stage"] = "failed"
        current_stage["progress"] = 1.0
        update("failed", str(e), {
            "error": {"type": type(e).__name__, "message": str(e)},
            "http_status": 500,
        })
    finally:
        _release_backtest_slot(data_dir)


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
    detail = {"trade": t, "meta": _public_payload(meta), "total_trades": len(trades)}
    analysis_id = meta.get("analysis_id")
    if analysis_id and t.get("signal_bin_idx") is not None:
        try:
            analysis = load_analysis(analysis_id, data_dir=DATA_DIR)
            detail.update(analysis.event_detail(int(t["signal_bin_idx"])))
        except Exception as exc:
            detail["event_error"] = f"{type(exc).__name__}: {exc}"
    prev_ids = [int(x.get("trade_id", -1)) for x in trades if int(x.get("trade_id", -1)) < trade_id]
    next_ids = [int(x.get("trade_id", -1)) for x in trades if int(x.get("trade_id", -1)) > trade_id]
    detail["prev_trade_id"] = max(prev_ids) if prev_ids else None
    detail["next_trade_id"] = min(next_ids) if next_ids else None
    return detail


@app.post("/api/backtests/run")
def backtest_run(body: dict = Body(...)):
    import multiprocessing

    name = body.get("strategy_name")
    analysis_id = body.get("analysis_id")
    params_override = body.get("params_override")
    if not name or not analysis_id:
        raise HTTPException(400, {"error": "missing_fields", "required": ["strategy_name", "analysis_id"]})
    strategy_path = DATA_DIR / "strategies" / f"{name}.py"
    if not strategy_path.exists():
        raise HTTPException(400, {"error": "strategy_not_found", "path": str(strategy_path)})
    _acquire_backtest_slot(name, analysis_id, DATA_DIR)
    job_id = str(uuid.uuid4())
    job_path = _backtest_job_path(DATA_DIR, job_id)
    _write_backtest_job(job_path, {
        "job_id": job_id,
        "strategy_name": name,
        "analysis_id": analysis_id,
        "status": "queued",
        "stage": "queued",
        "progress": 0.02,
        "message": "Backtest queued",
        "params_override": params_override or {},
        "created_at_ms": int(time.time() * 1000),
        "updated_at_ms": int(time.time() * 1000),
    })
    ctx = multiprocessing.get_context("spawn")
    try:
        proc = ctx.Process(
            target=_run_backtest_job,
            args=(str(job_path), job_id, str(strategy_path), name, analysis_id, params_override, str(DATA_DIR)),
            daemon=True,
        )
        proc.start()
        _update_backtest_slot(
            DATA_DIR,
            status="queued",
            worker_pid=proc.pid,
            strategy_name=name,
            analysis_id=analysis_id,
            job_id=job_id,
        )
        return {
            "ok": True,
            "queued": True,
            "job_id": job_id,
            "analysis_id": analysis_id,
            "status_url": f"/api/backtest-jobs/{job_id}",
        }
    except Exception:
        _release_backtest_slot(DATA_DIR)
        try:
            job_path.unlink()
        except FileNotFoundError:
            pass
        raise


@app.delete("/api/backtests/{bt_id}")
def delete_backtest(bt_id: str):
    bt_root = DATA_DIR / "backtest" / bt_id
    if not bt_root.is_dir():
        raise HTTPException(404, f"backtest not found: {bt_id}")
    shutil.rmtree(bt_root)
    return {"ok": True}


@app.get("/api/notebooks")
def list_notebooks():
    out = []
    for nb_dir in [DATA_DIR.parent / "notebooks", DATA_DIR / "notebooks"]:
        if not nb_dir.is_dir():
            continue
        for p in nb_dir.glob("*.ipynb"):
            if p.stem not in [n["name"] for n in out]:
                out.append({"name": p.stem, "path": str(p)})
    return out


@app.delete("/api/backtests/{bt_id}/montecarlo")
def delete_montecarlo(bt_id: str):
    mc_path = DATA_DIR / "backtest" / bt_id / "montecarlo.json"
    if not mc_path.exists():
        raise HTTPException(404, "Monte Carlo results not found")
    mc_path.unlink()
    return {"ok": True}


@app.delete("/api/collections/{collection_id}")
def delete_collection(collection_id: str):
    """Delete a collection (raw parquet files) and all related analyses."""
    collection = get_collection(DATA_DIR, collection_id)
    if collection is None:
        raise HTTPException(404, {"error": "collection_not_found", "collection_id": collection_id})
    removed_analyses = 0
    removed_backtests = 0
    # find and delete related analyses
    analyses_dir = DATA_DIR / "analyses"
    exact_prefix = "_".join(collection_id.split("_")[:2])
    related_analysis_ids: set[str] = set()
    if analyses_dir.is_dir():
        for d in list(analyses_dir.iterdir()):
            if not d.is_dir():
                continue
            # sessions whose ID starts with the collection ID prefix
            # or that reference this collection in their metadata
            meta_p = d / "meta.json"
            if meta_p.exists():
                try:
                    meta = json.loads(meta_p.read_text())
                    if meta.get("collection_id") == collection_id or d.name.startswith(exact_prefix):
                        related_analysis_ids.add(d.name)
                        shutil.rmtree(d, ignore_errors=True)
                        removed_analyses += 1
                        continue
                except Exception:
                    pass
            # fallback: check if session starts with collection timestamp prefix
            if d.name.startswith(exact_prefix):
                related_analysis_ids.add(d.name)
                shutil.rmtree(d, ignore_errors=True)
                removed_analyses += 1
    # delete related backtests for removed analyses
    removed_backtests = _delete_backtests_for_analysis_ids(related_analysis_ids)
    # delete raw tick/bbo files for this collection
    ticks_dir = DATA_DIR / "ticks"
    bbo_dir = DATA_DIR / "bbo"
    removed_files = 0
    for raw_path in list(collection.get("tick_file_paths") or []) + list(collection.get("bbo_file_paths") or []):
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path(raw_path)
        if path.exists():
            path.unlink()
            removed_files += 1
            parent = path.parent
            while parent not in {ticks_dir.parent, ticks_dir, bbo_dir, DATA_DIR}:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
    return {
        "ok": True,
        "removed_analyses": removed_analyses,
        "removed_backtests": removed_backtests,
        "removed_files": removed_files,
    }

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
        analysis_id=meta.get("analysis_id", ""),
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
        raise HTTPException(409, {"error": "collector_status_running", "recording_id": current.get("recording_id")})
    duration_s = int(body.get("duration_s", 3600))
    venues = body.get("venues") or []
    rotation_s = int(body.get("rotation_s", 1800))
    if duration_s <= 0 or rotation_s <= 0:
        raise HTTPException(400, {"error": "invalid_collector_params", "message": "duration_s and rotation_s must be positive"})
    cmd = [sys.executable, "-m", "leadlag.collector", "--duration", str(duration_s)]
    if venues:
        cmd += ["--venues", ",".join(venues)]
    cmd += ["--rotation-s", str(rotation_s)]
    COLLECTOR_PROC = subprocess.Popen(cmd, cwd=str(DATA_DIR.parent.resolve()))
    return {"ok": True, "pid": COLLECTOR_PROC.pid, "rotation_s": rotation_s}


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
    return _public_payload({k: v for k, v in collection.items() if k not in hidden})


def _load_analysis(analysis_id: str):
    try:
        return load_analysis(analysis_id, data_dir=DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(404, f"analysis not found: {analysis_id}")


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


def _extract_strategy_param_keys(source: str, params: dict | None = None) -> list[str]:
    keys = set((params or {}).keys())
    patterns = [
        r'(?:self\.params|params|p)\s*\[\s*["\']([A-Za-z0-9_]+)["\']\s*\]',
        r'(?:self\.params|params|p)\.get\(\s*["\']([A-Za-z0-9_]+)["\']',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, source or ""):
            keys.add(str(match))
    return sorted(keys)


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
                "avg_trade_bps": stats.get("avg_trade_bps", 0.0),
                "win_rate": stats.get("win_rate", 0.0),
                "sharpe": stats.get("sharpe", 0.0),
                "max_drawdown_bps": stats.get("max_drawdown_bps", 0.0),
                "has_montecarlo": (d / "montecarlo.json").exists(),
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
