"""Async WebSocket collector engine.

Per-venue task with keepalive + exponential backoff + stable-threshold reset.
Ported from collect_full.txt (Ячейка 4).
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from pathlib import Path

import websockets

from leadlag.collector.schemas import TICK_SCHEMA, BBO_SCHEMA
from leadlag.collector.writer import writer_task
from leadlag.venues.config import REGISTRY, VenueConfig


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
) -> None:
    BACKOFF_BASE, BACKOFF_CAP, STABLE_THRESHOLD = 1.0, 60.0, 60.0
    stats.setdefault(cfg.name, {"ticks": 0, "bbo": 0, "reconnects": 0, "status": "connecting"})
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
            async with websockets.connect(cfg.ws_url, **ws_kwargs) as ws:
                connect_time = time.time()
                stats[cfg.name]["status"] = "ok"
                if attempt > 0:
                    stats[cfg.name]["reconnects"] += 1

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
                            stats[cfg.name]["ticks"] += len(ticks)
                        except Exception:
                            pass
                        if cfg.bbo_parser:
                            try:
                                bbo = cfg.bbo_parser(msg, ts_local)
                                if bbo:
                                    bbo["venue"] = cfg.name
                                    await bbo_q.put(bbo)
                                    stats[cfg.name]["bbo"] += 1
                            except Exception:
                                pass
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
) -> dict:
    stats: dict = {}
    active = {n: c for n, c in REGISTRY.items()
              if c.enabled and (venues_filter is None or n in venues_filter)}

    trades_q: asyncio.Queue = asyncio.Queue(maxsize=1_000_000)
    bbo_q: asyncio.Queue = asyncio.Queue(maxsize=1_000_000)
    stop_event = asyncio.Event()

    ws_tasks = [
        asyncio.create_task(_ws_venue_task(cfg, trades_q, bbo_q, stop_event, stats))
        for cfg in active.values()
    ]
    t_writer = asyncio.create_task(writer_task(trades_q, stop_event, "ticks", TICK_SCHEMA, data_dir))
    b_writer = asyncio.create_task(writer_task(bbo_q, stop_event, "bbo", BBO_SCHEMA, data_dir))

    try:
        await asyncio.sleep(collect_seconds)
    finally:
        stop_event.set()
        await asyncio.sleep(1)
        for t in ws_tasks:
            t.cancel()
        await asyncio.gather(t_writer, b_writer, return_exceptions=True)

    return stats
