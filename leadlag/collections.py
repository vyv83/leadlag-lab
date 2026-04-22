"""Raw collection discovery for ticks/BBO parquet files.

Collector rotation filenames describe flush time, not necessarily collection
start time. Discovery therefore reads parquet ``ts_ms`` ranges and groups
overlapping/nearby raw files into collections that can be analyzed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from leadlag.contracts import utc_from_ms
from leadlag.session import list_analyses


DEFAULT_MAX_GAP_S = 45 * 60
_SCAN_CACHE: dict[tuple[str, int], tuple[tuple[tuple[str, int, int], ...], list[dict]]] = {}


def list_collections(data_dir: Path | str = "data", *, max_gap_s: int = DEFAULT_MAX_GAP_S) -> list[dict]:
    data_dir = Path(data_dir)
    files = _cached_scan_raw_files(data_dir, max_gap_s)
    if not files:
        return []

    groups: list[list[dict]] = []
    for row in sorted(files, key=lambda r: (r["t_start_ms"], r["kind"], r["path"])):
        if not groups:
            groups.append([row])
            continue
        prev_end = max(int(f["t_end_ms"]) for f in groups[-1])
        if int(row["t_start_ms"]) - prev_end <= max_gap_s * 1000:
            groups[-1].append(row)
        else:
            groups.append([row])

    analyses_by_collection: dict[str, list[dict]] = {}
    for analysis in list_analyses(data_dir):
        cid = analysis.get("recording_id") or analysis.get("collection_id")
        if cid:
            analyses_by_collection.setdefault(str(cid), []).append(analysis)

    collections = [_collection_from_group(g, data_dir) for g in groups]
    for collection in collections:
        analyzed = sorted(
            analyses_by_collection.get(collection["id"], []),
            key=lambda a: str(a.get("created_at_utc") or ""),
            reverse=True,
        )
        collection["analyzed_analyses"] = [a["id"] for a in analyzed if a.get("id")]
        collection["latest_analysis_id"] = collection["analyzed_analyses"][0] if collection["analyzed_analyses"] else None

    return sorted(collections, key=lambda r: int(r.get("t_start_ms") or 0), reverse=True)


def get_collection(data_dir: Path | str, collection_id: str) -> dict | None:
    for collection in list_collections(data_dir):
        if collection.get("id") == collection_id:
            return collection
    return None


def _scan_raw_files(data_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for kind in ("ticks", "bbo"):
        root = data_dir / kind
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.parquet")):
            meta = _parquet_time_range(path, data_dir, kind)
            if meta:
                rows.append(meta)
    return rows


def _cached_scan_raw_files(data_dir: Path, max_gap_s: int) -> list[dict]:
    key = (str(data_dir.resolve()), int(max_gap_s))
    fingerprint = _raw_fingerprint(data_dir)
    cached = _SCAN_CACHE.get(key)
    if cached and cached[0] == fingerprint:
        return [dict(r) for r in cached[1]]
    rows = _scan_raw_files(data_dir)
    _SCAN_CACHE[key] = (fingerprint, [dict(r) for r in rows])
    return rows


def _raw_fingerprint(data_dir: Path) -> tuple[tuple[str, int, int], ...]:
    items: list[tuple[str, int, int]] = []
    for kind in ("ticks", "bbo"):
        root = data_dir / kind
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.parquet")):
            try:
                st = path.stat()
            except OSError:
                continue
            items.append((str(path), int(st.st_mtime_ns), int(st.st_size)))
    return tuple(items)


def _parquet_time_range(path: Path, data_dir: Path, kind: str) -> dict | None:
    try:
        df = pd.read_parquet(path, columns=["ts_ms", "venue"])
    except Exception:
        return None
    if df.empty or "ts_ms" not in df:
        return None
    ts = pd.to_numeric(df["ts_ms"], errors="coerce").dropna()
    if ts.empty:
        return None
    venues = sorted(str(v) for v in df.get("venue", pd.Series(dtype=str)).dropna().unique())
    stat = path.stat()
    return {
        "kind": kind,
        "path": str(path),
        "relative_path": str(path.relative_to(data_dir)),
        "rows": int(len(df)),
        "t_start_ms": int(ts.min()),
        "t_end_ms": int(ts.max()),
        "venues": venues,
        "size_mb": round(stat.st_size / 1e6, 3),
        "modified": int(stat.st_mtime * 1000),
    }


def _collection_from_group(files: list[dict], data_dir: Path) -> dict[str, Any]:
    t_start = min(int(f["t_start_ms"]) for f in files)
    t_end = max(int(f["t_end_ms"]) for f in files)
    cid = _collection_id_from_ms(t_start)
    tick_files = [f for f in files if f["kind"] == "ticks"]
    bbo_files = [f for f in files if f["kind"] == "bbo"]
    venues = sorted({venue for f in files for venue in f.get("venues", [])})
    return {
        "id": cid,
        "date": (utc_from_ms(t_start) or "")[:10],
        "t_start_ms": t_start,
        "t_end_ms": t_end,
        "start_utc": utc_from_ms(t_start),
        "end_utc": utc_from_ms(t_end),
        "duration_s": max(0.0, (t_end - t_start) / 1000.0),
        "n_tick_files": len(tick_files),
        "n_bbo_files": len(bbo_files),
        "n_ticks": sum(int(f["rows"]) for f in tick_files),
        "n_bbo": sum(int(f["rows"]) for f in bbo_files),
        "venues": venues,
        "n_venues": len(venues),
        "tick_files": [f["relative_path"] for f in tick_files],
        "bbo_files": [f["relative_path"] for f in bbo_files],
        "tick_file_paths": [f["path"] for f in tick_files],
        "bbo_file_paths": [f["path"] for f in bbo_files],
        "size_mb": round(sum(float(f["size_mb"]) for f in files), 3),
        "modified": max(int(f["modified"]) for f in files),
    }


def _collection_id_from_ms(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y%m%d_%H%M%S")
