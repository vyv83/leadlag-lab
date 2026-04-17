"""Paper trading daemon.

If the collector is stopped, this daemon opens WS connections only for the
strategy-required venues. If the collector is already running, it does not
create duplicate WS connections; it marks the status as ``collector_ipc_pending``
until collector IPC is wired in a later hardening pass.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import time
from pathlib import Path

from leadlag.collector.engine import _ws_venue_task
from leadlag.collector.schemas import BBO_SCHEMA, TICK_SCHEMA
from leadlag.contracts import utc_from_ms
from leadlag.monitor.snapshot import read_collector_status
from leadlag.paper.trader import PaperTrader
from leadlag.strategy_loader import load_strategy
from leadlag.venues import LEADERS, REGISTRY


async def run(strategy_path: str, data_dir: Path, duration_s: int | None = None) -> None:
    strategy = load_strategy(strategy_path)
    followers = _strategy_followers(strategy)
    leaders = [v for v in LEADERS if v in REGISTRY]
    venues = list(dict.fromkeys(leaders + followers))
    trader = PaperTrader(strategy, leaders, followers, data_dir=data_dir)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    collector = read_collector_status(data_dir)
    if collector.get("running"):
        _write_daemon_status(data_dir, strategy, venues, mode="collector_ipc_pending", running=True)
        try:
            await _sleep_until_stop(stop_event, duration_s)
        finally:
            _write_daemon_status(data_dir, strategy, venues, mode="stopped", running=False)
        return

    trades_q: asyncio.Queue = asyncio.Queue(maxsize=500_000)
    bbo_q: asyncio.Queue = asyncio.Queue(maxsize=500_000)
    stats: dict = {}
    active = {name: REGISTRY[name] for name in venues if name in REGISTRY and REGISTRY[name].enabled}
    ws_tasks = [
        asyncio.create_task(_ws_venue_task(cfg, trades_q, bbo_q, stop_event, stats, data_dir))
        for cfg in active.values()
    ]
    consumers = [
        asyncio.create_task(_tick_consumer(trader, trades_q, stop_event)),
        asyncio.create_task(_bbo_consumer(trader, bbo_q, stop_event)),
        asyncio.create_task(_status_loop(trader, data_dir, strategy, venues, stop_event)),
    ]
    try:
        await _sleep_until_stop(stop_event, duration_s)
    finally:
        stop_event.set()
        for task in ws_tasks + consumers:
            task.cancel()
        await asyncio.gather(*ws_tasks, *consumers, return_exceptions=True)
        _write_daemon_status(data_dir, strategy, venues, mode="stopped", running=False)


async def _tick_consumer(trader: PaperTrader, queue: asyncio.Queue, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            row = await asyncio.wait_for(queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        trader.feed_tick(row["venue"], int(row["ts_ms"]), float(row["price"]), float(row.get("qty", 0.0)))


async def _bbo_consumer(trader: PaperTrader, queue: asyncio.Queue, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            row = await asyncio.wait_for(queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        trader.feed_bbo(
            row["venue"], int(row["ts_ms"]), float(row["bid_price"]), float(row["ask_price"]),
            float(row.get("bid_qty", 0.0)), float(row.get("ask_qty", 0.0)),
        )


async def _status_loop(trader: PaperTrader, data_dir: Path, strategy, venues: list[str], stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        trader._write_status()
        _write_venues(data_dir, venues)
        await asyncio.sleep(2)


async def _sleep_until_stop(stop_event: asyncio.Event, duration_s: int | None) -> None:
    if duration_s is None:
        await stop_event.wait()
        return
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=duration_s)
    except asyncio.TimeoutError:
        return


def _strategy_followers(strategy) -> list[str]:
    params = getattr(strategy, "params", {}) or {}
    if params.get("follower"):
        return [params["follower"]]
    followers = params.get("followers")
    if isinstance(followers, list) and followers:
        return followers
    return [name for name, cfg in REGISTRY.items() if cfg.role == "follower"]


def _write_daemon_status(data_dir: Path, strategy, venues: list[str], *, mode: str, running: bool) -> None:
    now = int(time.time() * 1000)
    payload = {
        "running": running,
        "strategy": getattr(strategy, "name", Path(str(strategy)).stem),
        "mode": mode,
        "started_at_ms": now if running else None,
        "started_at_utc": utc_from_ms(now) if running else None,
        "uptime_s": 0,
        "equity_today": 0.0,
        "cumulative_pnl_bps": 0.0,
        "venues_monitored": venues,
    }
    path = data_dir / ".paper_status.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    os.replace(tmp, path)
    _write_venues(data_dir, venues)


def _write_venues(data_dir: Path, venues: list[str]) -> None:
    rows = []
    for name in venues:
        cfg = REGISTRY.get(name)
        if not cfg:
            continue
        rows.append({
            "venue": name,
            "role": cfg.role,
            "used_by_strategy": True,
            "status": "monitoring",
            "bbo_available": cfg.bbo_available,
            "taker_fee_bps": cfg.taker_fee_bps,
            "maker_fee_bps": cfg.maker_fee_bps,
        })
    path = data_dir / ".paper_venues.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, indent=2))
    os.replace(tmp, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--duration", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(run(args.strategy, Path(args.data_dir), duration_s=args.duration))


if __name__ == "__main__":
    main()
