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
from pathlib import Path
from typing import Any

import psutil


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
    return rows


def read_pings(data_dir: Path | str = "data") -> dict:
    p = Path(data_dir) / ".ping_cache.json"
    if not p.exists():
        return {"ts": None, "venues": {}}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"ts": None, "venues": {}}


def read_collector_status(data_dir: Path | str = "data") -> dict:
    p = Path(data_dir) / ".collector_status.json"
    if not p.exists():
        return {"running": False}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"running": False}


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
        })
    return out
