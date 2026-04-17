"""CLI entrypoint: `python -m leadlag.collector --duration 3600 [--venues a,b]`."""
from __future__ import annotations

import argparse
import asyncio
import json

from leadlag.collector.engine import run_collector


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=int, required=True, help="seconds to collect")
    p.add_argument("--venues", type=str, default="", help="comma-separated venue names (default: all enabled)")
    p.add_argument("--data-dir", type=str, default="data")
    p.add_argument("--rotation-s", type=int, default=1800, help="parquet rotation interval in seconds")
    p.add_argument("--bin-size-ms", type=int, default=50, help="analysis/default bin size metadata in milliseconds")
    args = p.parse_args()
    venues = [v.strip() for v in args.venues.split(",") if v.strip()] or None
    stats = asyncio.run(run_collector(
        args.duration,
        venues,
        args.data_dir,
        rotation_s=args.rotation_s,
        bin_size_ms=args.bin_size_ms,
    ))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
