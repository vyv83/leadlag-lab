"""leadlag-monitor daemon.

Writes:
  data/.system_history.jsonl   — one line every 5s, 24h retention
  data/.ping_cache.json        — refreshed every 10s (atomic rename)

Run: `python -m leadlag.monitor.daemon`.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import time
from pathlib import Path

from leadlag.monitor.snapshot import system_stats
from leadlag.venues.config import REGISTRY


HISTORY_INTERVAL_S = 5.0
PING_INTERVAL_S = 10.0
RETENTION_HOURS = 24


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data)
    os.replace(tmp, path)


def _trim_history(path: Path) -> None:
    cutoff_ms = int((time.time() - RETENTION_HOURS * 3600) * 1000)
    if not path.exists():
        return
    kept: list[str] = []
    with path.open() as f:
        for line in f:
            try:
                if int(json.loads(line).get("ts", 0)) >= cutoff_ms:
                    kept.append(line)
            except Exception:
                continue
    path.write_text("".join(kept))


async def _history_loop(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    hist_path = data_dir / ".system_history.jsonl"
    last_trim = time.time()
    while True:
        s = system_stats()
        with hist_path.open("a") as f:
            f.write(json.dumps({
                "ts": s["ts"], "cpu_pct": s["cpu_percent"],
                "ram_used_gb": s["ram_used_gb"], "disk_used_gb": s["disk_used_gb"],
                "net_sent": s["net_bytes_sent"], "net_recv": s["net_bytes_recv"],
            }) + "\n")
        if time.time() - last_trim > 600:  # trim every 10min
            _trim_history(hist_path)
            last_trim = time.time()
        await asyncio.sleep(HISTORY_INTERVAL_S)


async def _ping_one(host: str, port: int = 443, timeout: float = 2.0) -> dict:
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return {"host": host, "latency_ms": round((loop.time() - t0) * 1000, 2), "status": "ok"}
    except asyncio.TimeoutError:
        return {"host": host, "latency_ms": None, "status": "timeout"}
    except Exception as e:
        return {"host": host, "latency_ms": None, "status": f"error:{type(e).__name__}"}


async def _ping_loop(data_dir: Path) -> None:
    hosts: dict[str, str] = {}
    for name, cfg in REGISTRY.items():
        try:
            url = cfg.ws_url
            host = url.split("//", 1)[1].split("/", 1)[0].split(":")[0]
            hosts[name] = host
        except Exception:
            continue
    while True:
        results = await asyncio.gather(*[_ping_one(h) for h in hosts.values()])
        payload = {
            "ts": int(time.time() * 1000),
            "venues": {venue: r for venue, r in zip(hosts.keys(), results)},
        }
        _atomic_write(data_dir / ".ping_cache.json", json.dumps(payload))
        await asyncio.sleep(PING_INTERVAL_S)


async def run(data_dir: Path | str = "data") -> None:
    data_dir = Path(data_dir)
    await asyncio.gather(_history_loop(data_dir), _ping_loop(data_dir))


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
