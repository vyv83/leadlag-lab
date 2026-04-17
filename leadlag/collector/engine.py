"""Async WebSocket collector engine.

Per-venue task with keepalive + exponential backoff + stable-threshold reset.
Ported from collect_full.txt (Ячейка 4).
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets

from leadlag.collector.schemas import TICK_SCHEMA, BBO_SCHEMA
from leadlag.collector.writer import writer_task
from leadlag.venues.config import REGISTRY, VenueConfig


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def _append_log(data_dir: Path, venue: str, event_type: str, message: str) -> None:
    rec = {
        "ts_ms": int(time.time() * 1000),
        "time_utc": _utc_now(),
        "venue": venue,
        "event_type": event_type,
        "message": message,
    }
    try:
        with (data_dir / ".collector_log.jsonl").open("a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


async def _keepalive(ws, cfg: VenueConfig) -> None:
    try:
        while True:
            await asyncio.sleep(cfg.keepalive_interval)
            if cfg.keepalive_type == "text_ping":
                await ws.send("ping")
            elif cfg.keepalive_type == "json_ping":
                await ws.send(json.dumps(cfg.keepalive_msg))
    except (asyncio.CancelledError, Exception):
        pass


async def _ws_venue_task(
    cfg: VenueConfig,
    trades_q: asyncio.Queue,
    bbo_q: asyncio.Queue,
    stop_event: asyncio.Event,
    stats: dict,
    data_dir: Path,
) -> None:
    BACKOFF_BASE, BACKOFF_CAP, STABLE_THRESHOLD = 1.0, 60.0, 60.0
    stats.setdefault(cfg.name, {
        "ticks": 0, "bbo": 0, "reconnects": 0, "status": "connecting",
        "last_tick_ts": None, "last_bbo_ts": None, "last_price": None,
        "last_reconnect_utc": None, "last_error": None,
    })
    attempt = 0

    while not stop_event.is_set():
        connect_time = None
        try:
            ws_kwargs = dict(close_timeout=5, max_size=10_000_000, open_timeout=15)
            if cfg.keepalive_type == "ws_ping":
                ws_kwargs["ping_interval"] = cfg.keepalive_interval
                ws_kwargs["ping_timeout"] = 10
            else:
                ws_kwargs["ping_interval"] = None
                ws_kwargs["ping_timeout"] = None

            stats[cfg.name]["status"] = "connecting"
            _append_log(data_dir, cfg.name, "connecting", cfg.ws_url)
            async with websockets.connect(cfg.ws_url, **ws_kwargs) as ws:
                connect_time = time.time()
                stats[cfg.name]["status"] = "ok"
                if attempt > 0:
                    stats[cfg.name]["reconnects"] += 1
                    stats[cfg.name]["last_reconnect_utc"] = _utc_now()
                _append_log(data_dir, cfg.name, "connected", "websocket connected")

                if cfg.subscribe_msg == "DYNAMIC" and cfg.subscribe_factory:
                    res = cfg.subscribe_factory()
                    for s in (res if isinstance(res, list) else [res]):
                        await ws.send(json.dumps(s))
                elif cfg.subscribe_msg is not None:
                    await ws.send(json.dumps(cfg.subscribe_msg))
                if cfg.bbo_subscribe_msg:
                    await ws.send(json.dumps(cfg.bbo_subscribe_msg))

                ka = (
                    asyncio.create_task(_keepalive(ws, cfg))
                    if cfg.keepalive_type in ("text_ping", "json_ping")
                    else None
                )
                try:
                    async for raw in ws:
                        if stop_event.is_set():
                            break
                        ts_local = int(time.time_ns() // 1_000_000)
                        try:
                            msg = json.loads(raw)
                        except Exception:
                            continue
                        if not isinstance(msg, dict):
                            continue
                        if msg.get("event") in ("subscribe", "subscribed", "info", "pong"):
                            continue
                        if msg.get("type") in ("connected", "pong", "subscribed"):
                            continue
                        if msg.get("type") == "ping":
                            await ws.send(json.dumps({"type": "pong", "time": msg.get("time", "")}))
                            continue
                        try:
                            ticks = cfg.parser(msg, ts_local) or []
                            for t in ticks:
                                t["venue"] = cfg.name
                                await trades_q.put(t)
                                stats[cfg.name]["last_tick_ts"] = int(t.get("ts_ms", ts_local))
                                stats[cfg.name]["last_price"] = t.get("price")
                            stats[cfg.name]["ticks"] += len(ticks)
                        except Exception as exc:
                            stats[cfg.name]["last_error"] = f"{type(exc).__name__}: {exc}"
                            _append_log(data_dir, cfg.name, "parser_error", stats[cfg.name]["last_error"])
                        if cfg.bbo_parser:
                            try:
                                bbo = cfg.bbo_parser(msg, ts_local)
                                if bbo:
                                    bbo["venue"] = cfg.name
                                    await bbo_q.put(bbo)
                                    stats[cfg.name]["bbo"] += 1
                                    stats[cfg.name]["last_bbo_ts"] = int(bbo.get("ts_ms", ts_local))
                            except Exception as exc:
                                stats[cfg.name]["last_error"] = f"{type(exc).__name__}: {exc}"
                                _append_log(data_dir, cfg.name, "bbo_parser_error", stats[cfg.name]["last_error"])
                finally:
                    if ka:
                        ka.cancel()
                if connect_time and (time.time() - connect_time) > STABLE_THRESHOLD:
                    attempt = 0
        except asyncio.CancelledError:
            return
        except Exception as e:
            stats[cfg.name]["status"] = "reconnecting"
            stats[cfg.name]["last_error"] = f"{type(e).__name__}: {e}"
            _append_log(data_dir, cfg.name, "reconnecting", stats[cfg.name]["last_error"])
            if stop_event.is_set():
                return
            delay = min(BACKOFF_BASE * (2 ** attempt), BACKOFF_CAP)
            delay = max(0.5, delay + delay * 0.25 * (2 * random.random() - 1))
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
                return
            except asyncio.TimeoutError:
                pass
            attempt += 1


async def run_collector(
    collect_seconds: int,
    venues_filter: list[str] | None = None,
    data_dir: Path | str = "data",
    *,
    rotation_s: int = 1800,
    bin_size_ms: int = 50,
) -> dict:
    stats: dict = {}
    data_dir = Path(data_dir)
    active = {n: c for n, c in REGISTRY.items()
              if c.enabled and (venues_filter is None or n in venues_filter)}
    session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    start_ts_ms = int(time.time() * 1000)

    trades_q: asyncio.Queue = asyncio.Queue(maxsize=1_000_000)
    bbo_q: asyncio.Queue = asyncio.Queue(maxsize=1_000_000)
    stop_event = asyncio.Event()

    ws_tasks = [
        asyncio.create_task(_ws_venue_task(cfg, trades_q, bbo_q, stop_event, stats, data_dir))
        for cfg in active.values()
    ]
    t_writer = asyncio.create_task(writer_task(trades_q, stop_event, "ticks", TICK_SCHEMA, data_dir, rotation_s=rotation_s))
    b_writer = asyncio.create_task(writer_task(bbo_q, stop_event, "bbo", BBO_SCHEMA, data_dir, rotation_s=rotation_s))

    try:
        deadline = time.time() + collect_seconds
        _append_log(data_dir, "collector", "started", f"session_id={session_id}, venues={','.join(active)}")
        while time.time() < deadline:
            _write_status(
                data_dir, session_id, start_ts_ms, collect_seconds, active, stats,
                running=True, rotation_s=rotation_s, bin_size_ms=bin_size_ms,
            )
            await asyncio.sleep(2)
    finally:
        stop_event.set()
        _write_status(
            data_dir, session_id, start_ts_ms, collect_seconds, active, stats,
            running=False, rotation_s=rotation_s, bin_size_ms=bin_size_ms,
        )
        _append_log(data_dir, "collector", "stopping", f"session_id={session_id}")
        await asyncio.sleep(1)
        for t in ws_tasks:
            t.cancel()
        await asyncio.gather(t_writer, b_writer, return_exceptions=True)

    return stats


def _write_status(
    data_dir: Path,
    session_id: str,
    start_ts_ms: int,
    planned_duration_s: int,
    active: dict[str, VenueConfig],
    stats: dict,
    *,
    running: bool,
    rotation_s: int = 1800,
    bin_size_ms: int = 50,
) -> None:
    now_ms = int(time.time() * 1000)
    venues = []
    for name, cfg in active.items():
        row = stats.get(name, {})
        ticks = int(row.get("ticks", 0))
        bbo = int(row.get("bbo", 0))
        elapsed = max(1.0, (now_ms - start_ts_ms) / 1000.0)
        last_tick = row.get("last_tick_ts")
        seconds_idle = ((now_ms - int(last_tick)) / 1000.0) if last_tick else None
        raw_status = row.get("status", "disabled")
        status = raw_status
        severity = "ok"
        if raw_status == "ok" and running:
            if ticks == 0 and elapsed >= 60.0:
                status = "connected_no_data"
                severity = "warning"
            elif seconds_idle is not None and seconds_idle >= 60.0:
                status = "connected_no_data"
                severity = "warning"
        if raw_status in {"connecting", "reconnecting"}:
            severity = "warning"
        if raw_status not in {"ok", "connecting", "reconnecting"}:
            severity = "error" if raw_status not in {"disabled"} else "muted"
        venues.append({
            "name": name,
            "role": cfg.role,
            "status": status,
            "raw_status": raw_status,
            "severity": severity,
            "ticks": ticks,
            "ticks_per_s_1m": ticks / elapsed,
            "ticks_per_s_10m": ticks / elapsed,
            "bbo": bbo,
            "bbo_per_s": bbo / elapsed,
            "reconnects": int(row.get("reconnects", 0)),
            "last_reconnect_utc": row.get("last_reconnect_utc"),
            "last_tick_ts": last_tick,
            "seconds_since_last_tick": seconds_idle,
            "last_price": row.get("last_price"),
            "median_price": row.get("last_price"),
            "last_error": row.get("last_error"),
            "uptime_pct": 100.0 if row.get("status") == "ok" else 0.0,
            "bbo_available": cfg.bbo_available,
            "taker_fee_bps": cfg.taker_fee_bps,
            "maker_fee_bps": cfg.maker_fee_bps,
        })
    _atomic_json(data_dir / ".collector_status.json", {
        "running": running,
        "running_effective": running,
        "stale": False,
        "session_id": session_id,
        "start_time": start_ts_ms,
        "start_time_utc": datetime.fromtimestamp(start_ts_ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "planned_duration_s": planned_duration_s,
        "rotation_s": int(rotation_s),
        "bin_size_ms": int(bin_size_ms),
        "updated_at_ms": now_ms,
        "updated_at_utc": _utc_now(),
        "venues": venues,
    })
