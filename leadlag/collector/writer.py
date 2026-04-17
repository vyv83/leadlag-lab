"""Rotating parquet writer.

Writes to:
    {data_dir}/{prefix}/YYYY-MM-DD/{prefix}_YYYYMMDD_HHMMSS.parquet

30-minute rotation, zstd compression. Conforms to plan.md §contract 1.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


ROTATION_INTERVAL_SEC = 1800


async def writer_task(
    queue: asyncio.Queue,
    stop_event: asyncio.Event,
    prefix: str,
    schema: pa.Schema,
    data_dir: Path | str = "data",
) -> None:
    buffer: list[dict] = []
    last_rotate = time.time()
    data_dir = Path(data_dir)

    def flush() -> None:
        nonlocal buffer, last_rotate
        if not buffer:
            return
        now = datetime.now(timezone.utc)
        date_dir = data_dir / prefix / now.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        ts_str = now.strftime("%Y%m%d_%H%M%S")
        path = date_dir / f"{prefix}_{ts_str}.parquet"
        cols = {n: [r.get(n, 0) for r in buffer] for n in schema.names}
        pq.write_table(pa.table(cols, schema=schema), path, compression="zstd")
        buffer = []
        last_rotate = time.time()

    try:
        while not (stop_event.is_set() and queue.empty()):
            try:
                item = await asyncio.wait_for(queue.get(), timeout=1.0)
                buffer.append(item)
            except asyncio.TimeoutError:
                pass
            if time.time() - last_rotate >= ROTATION_INTERVAL_SEC:
                flush()
    finally:
        flush()
