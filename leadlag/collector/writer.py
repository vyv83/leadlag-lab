"""Rotating parquet writer.

Writes to:
    {data_dir}/{prefix}/YYYY-MM-DD/{prefix}_YYYYMMDD_HHMMSS.parquet

30-minute rotation, zstd compression. Conforms to plan.md §contract 1.
"""
from __future__ import annotations

import asyncio
import json
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

    def log(event_type: str, message: str) -> None:
        rec = {
            "ts_ms": int(time.time() * 1000),
            "time_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "venue": "writer",
            "event_type": event_type,
            "message": f"{prefix}: {message}",
        }
        try:
            with (data_dir / ".collector_log.jsonl").open("a") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception:
            pass

    def flush() -> None:
        nonlocal buffer, last_rotate
        if not buffer:
            return
        try:
            now = datetime.now(timezone.utc)
            date_dir = data_dir / prefix / now.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True, exist_ok=True)
            ts_str = now.strftime("%Y%m%d_%H%M%S")
            path = date_dir / f"{prefix}_{ts_str}.parquet"
            cols = {n: [_coerce_value(r.get(n), schema.field(n).type) for r in buffer] for n in schema.names}
            pq.write_table(pa.table(cols, schema=schema), path, compression="zstd")
            log("writer_flush", f"wrote {len(buffer)} rows to {path.name}")
            buffer = []
            last_rotate = time.time()
        except Exception as exc:
            log("writer_error", f"{type(exc).__name__}: {exc}; dropped {len(buffer)} buffered rows")
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


def _coerce_value(value, arrow_type):
    if value is None:
        return 0 if pa.types.is_integer(arrow_type) or pa.types.is_floating(arrow_type) else ""
    try:
        if pa.types.is_integer(arrow_type):
            return int(value)
        if pa.types.is_floating(arrow_type):
            return float(value)
        if pa.types.is_string(arrow_type):
            return str(value)
    except Exception:
        return 0 if pa.types.is_integer(arrow_type) or pa.types.is_floating(arrow_type) else ""
    return value
