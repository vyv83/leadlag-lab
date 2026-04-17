"""System snapshot helpers (psutil-based) + IPC file readers.

The dashboard API reads live numbers via `system_stats()` and historical
sparklines via `read_history()` from `data/.system_history.jsonl`, written
by the leadlag-monitor daemon (see monitor/daemon.py). Ping cache is read
from `data/.ping_cache.json` — populated by the same daemon.

Files are atomically written (.tmp → os.rename) by the daemon; this module
only reads.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
import pandas as pd


def system_stats() -> dict[str, Any]:
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/")
    try:
        net = psutil.net_io_counters()
        net_sent, net_recv = int(net.bytes_sent), int(net.bytes_recv)
    except Exception:
        net_sent, net_recv = 0, 0
    return {
        "ts": int(time.time() * 1000),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_per_core": psutil.cpu_percent(interval=None, percpu=True),
        "ram_total_gb": round(vm.total / 1e9, 2),
        "ram_used_gb": round(vm.used / 1e9, 2),
        "ram_percent": vm.percent,
        "disk_total_gb": round(du.total / 1e9, 2),
        "disk_used_gb": round(du.used / 1e9, 2),
        "disk_data_gb": round(_dir_size(Path("data")) / 1e9, 2),
        "net_bytes_sent": net_sent,
        "net_bytes_recv": net_recv,
    }


def read_history(data_dir: Path | str = "data", minutes: int = 60) -> list[dict]:
    p = Path(data_dir) / ".system_history.jsonl"
    if not p.exists():
        return []
    cutoff_ms = int((time.time() - minutes * 60) * 1000)
    rows: list[dict] = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if int(r.get("ts", 0)) >= cutoff_ms:
                rows.append(r)
    return _with_network_rates(rows)


def read_pings(data_dir: Path | str = "data") -> dict:
    p = Path(data_dir) / ".ping_cache.json"
    if not p.exists():
        return {"ts": None, "venues": {}}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"ts": None, "venues": {}}


def read_collector_status(data_dir: Path | str = "data", stale_after_s: int = 30) -> dict:
    p = Path(data_dir) / ".collector_status.json"
    if not p.exists():
        return {"running": False, "running_effective": False, "stale": False}
    try:
        st = json.loads(p.read_text())
    except Exception:
        return {"running": False, "running_effective": False, "stale": False}
    now_ms = int(time.time() * 1000)
    updated = st.get("updated_at_ms")
    if updated is None:
        try:
            updated = int(p.stat().st_mtime * 1000)
        except OSError:
            updated = None
    age_s = ((now_ms - int(updated)) / 1000.0) if updated else None
    file_running = bool(st.get("running"))
    stale = bool(file_running and age_s is not None and age_s > stale_after_s)
    st["file_running"] = file_running
    st["stale"] = stale
    st["status_age_s"] = age_s
    st["stale_after_s"] = stale_after_s
    st["running_effective"] = bool(file_running and not stale)
    if stale:
        st["running"] = False
        st["status"] = "stale"
    else:
        st["running"] = st["running_effective"]
    return st


def list_data_files(data_dir: Path | str = "data") -> list[dict]:
    root = Path(data_dir)
    if not root.is_dir():
        return []
    out: list[dict] = []
    for p in sorted(root.rglob("*.parquet")):
        try:
            st = p.stat()
        except OSError:
            continue
        out.append({
            "path": str(p.relative_to(root)),
            "size_mb": round(st.st_size / 1e6, 3),
            "modified": int(st.st_mtime * 1000),
            **_parquet_brief(p),
        })
    return out


def read_collector_log(data_dir: Path | str = "data", since_ts: int | None = None, venue: str | None = None, event_type: str | None = None) -> list[dict]:
    p = Path(data_dir) / ".collector_log.jsonl"
    if not p.exists():
        return []
    rows = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if since_ts is not None and int(row.get("ts_ms", 0)) < since_ts:
                continue
            if venue and row.get("venue") != venue:
                continue
            if event_type and row.get("event_type") != event_type:
                continue
            rows.append(row)
    return rows[-1000:]


def system_processes() -> list[dict]:
    wanted = {
        "leadlag-api": ("uvicorn", "leadlag.api"),
        "leadlag-collector": ("leadlag.collector",),
        "leadlag-paper": ("leadlag.paper", "paper_trade"),
        "leadlag-monitor": ("leadlag.monitor",),
        "jupyter-lab": ("jupyter", "jupyter-lab"),
    }
    now = time.time()
    rows = {name: {"name": name, "status": "stopped", "pid": None, "mem_mb": 0.0, "uptime_s": 0} for name in wanted}
    for proc in psutil.process_iter(["pid", "name", "cmdline", "status", "memory_info", "create_time"]):
        try:
            info = proc.info
            cmd = " ".join(info.get("cmdline") or [info.get("name") or ""])
            for service, needles in wanted.items():
                if any(n in cmd for n in needles):
                    mem = info.get("memory_info")
                    rows[service] = {
                        "name": service,
                        "status": info.get("status") or "running",
                        "pid": info.get("pid"),
                        "mem_mb": round((mem.rss if mem else 0) / 1e6, 1),
                        "uptime_s": int(now - float(info.get("create_time") or now)),
                    }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return list(rows.values())


def _parquet_brief(path: Path) -> dict:
    try:
        df = pd.read_parquet(path, columns=["ts_ms", "venue"])
        ts = pd.to_numeric(df.get("ts_ms"), errors="coerce")
        venues = sorted(str(v) for v in df.get("venue", pd.Series(dtype=str)).dropna().unique())
        return {
            "rows": int(len(df)),
            "ts_min": int(ts.min()) if len(ts.dropna()) else None,
            "ts_max": int(ts.max()) if len(ts.dropna()) else None,
            "venues": venues,
        }
    except Exception:
        return {"rows": None, "ts_min": None, "ts_max": None, "venues": []}


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _with_network_rates(rows: list[dict]) -> list[dict]:
    prev: dict | None = None
    out: list[dict] = []
    for row in rows:
        r = dict(row)
        if "net_down_bps" not in r or "net_up_bps" not in r:
            if prev and r.get("net_recv") is not None and prev.get("net_recv") is not None:
                dt = max(0.001, (int(r.get("ts", 0)) - int(prev.get("ts", 0))) / 1000.0)
                r["net_down_bps"] = max(0.0, (float(r.get("net_recv", 0)) - float(prev.get("net_recv", 0))) / dt)
                r["net_up_bps"] = max(0.0, (float(r.get("net_sent", 0)) - float(prev.get("net_sent", 0))) / dt)
            else:
                r.setdefault("net_down_bps", 0.0)
                r.setdefault("net_up_bps", 0.0)
        prev = r
        out.append(r)
    return out
