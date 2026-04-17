"""Session: entry point that loads analysis results and exposes them as dataframes.

Two constructors:
    load_session(session_id)            — reads data/sessions/{id}/
    Session.build_from_raw(collection_id, params, **paths)
        — runs the full pipeline on raw parquet and writes the session contract.

See plan.md §contract 2 for the on-disk layout:
    data/sessions/{collection_id}_{params_hash}/
      meta.json            — params, params_hash, venues, n_events
      events.json          — [{bin_idx, signal, direction, magnitude_sigma,
                                lagging_followers, follower_metrics, ...}]
      price_windows.json   — VWAP ±10s per event (optional, for graphs)
      bbo_windows.json     — BBO ±10s per event (optional)
      quality.json         — ticks/s, bin coverage, BBO availability per venue
"""
from __future__ import annotations

import glob
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd


DEFAULT_DATA_DIR = Path("data")


def _params_hash(params: dict) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()[:8]


def make_session_id(collection_id: str, params: dict) -> str:
    return f"{collection_id}_{_params_hash(params)}"


@dataclass
class EventsTable:
    """Thin wrapper around events list with notebook-friendly filter API."""

    rows: list[dict]

    @property
    def count(self) -> int:
        return len(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, i):
        return self.rows[i]

    def filter(self, **kwargs) -> "EventsTable":
        out = self.rows
        for k, v in kwargs.items():
            out = [e for e in out if e.get(k) == v]
        return EventsTable(out)

    def to_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


@dataclass
class Session:
    session_id: str
    meta: dict
    events: EventsTable
    quality: dict = field(default_factory=dict)
    price_windows: list[dict] = field(default_factory=list)
    bbo_windows: list[dict] = field(default_factory=list)

    # Lazy-loaded heavy frames (populated when build_from_raw or load_with_frames used).
    vwap_df: Optional[pd.DataFrame] = None
    ema_df: Optional[pd.DataFrame] = None
    dev_df: Optional[pd.DataFrame] = None
    bbo_df: Optional[pd.DataFrame] = None

    @property
    def collection_id(self) -> str:
        return self.meta.get("collection_id", self.session_id.rsplit("_", 1)[0])

    @property
    def params(self) -> dict:
        return self.meta.get("params", {})

    # ─── persistence ───

    def save(self, data_dir: Path | str = DEFAULT_DATA_DIR) -> Path:
        out = Path(data_dir) / "sessions" / self.session_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "meta.json").write_text(json.dumps(self.meta, indent=2))
        (out / "events.json").write_text(json.dumps(self.events.rows))
        (out / "quality.json").write_text(json.dumps(self.quality, indent=2))
        if self.price_windows:
            (out / "price_windows.json").write_text(json.dumps(self.price_windows))
        if self.bbo_windows:
            (out / "bbo_windows.json").write_text(json.dumps(self.bbo_windows))
        return out

    # ─── constructors ───

    @classmethod
    def build_from_raw(
        cls,
        collection_id: str,
        ticks_path_glob: str | list[str],
        bbo_path_glob: str | list[str] | None = None,
        *,
        bin_size_ms: int = 50,
        ema_span_bins: int = 200,
        threshold_sigma: float = 2.0,
        follower_max_dev: float = 0.5,
        cluster_gap_bins: int = 60,
        detection_window_bins: int = 10,
        confirm_window_bins: int = 10,
    ) -> "Session":
        """Run the full pipeline on raw parquet and return a Session.

        Writes no files until .save() is called.
        """
        from leadlag.analysis.binning import bin_to_vwap
        from leadlag.analysis.ema import compute_ema, compute_deviation
        from leadlag.analysis.detection import detect_events, cluster_events_first, classify_signals
        from leadlag.analysis.metrics import compute_metrics
        from leadlag.venues.config import LEADERS, FEES

        params = {
            "bin_size_ms": bin_size_ms,
            "ema_span_bins": ema_span_bins,
            "threshold_sigma": threshold_sigma,
            "follower_max_dev": follower_max_dev,
            "cluster_gap_bins": cluster_gap_bins,
            "detection_window_bins": detection_window_bins,
            "confirm_window_bins": confirm_window_bins,
        }
        session_id = make_session_id(collection_id, params)

        df_ticks = _read_parquets(ticks_path_glob)
        df_ticks = df_ticks.sort_values("ts_ms").reset_index(drop=True)
        df_ticks = df_ticks.drop_duplicates(subset=["ts_ms", "venue", "price", "qty"])

        all_venues_seen = list(df_ticks["venue"].unique())
        leaders = [v for v in LEADERS if v in all_venues_seen]
        followers = sorted([v for v in all_venues_seen if v not in leaders])
        venues = leaders + followers

        vwap_df, t_start, coverage = bin_to_vwap(df_ticks, venues, bin_size_ms=bin_size_ms)
        ema_df = compute_ema(vwap_df, venues, ema_span_bins=ema_span_bins)
        dev_df, sigma = compute_deviation(vwap_df, ema_df, venues, ema_span_bins=ema_span_bins)

        clustered_by_leader = {}
        for leader in leaders:
            raw = detect_events(
                leader, followers, dev_df, t_start=t_start,
                bin_size_ms=bin_size_ms,
                threshold=threshold_sigma,
                follower_max_dev=follower_max_dev,
                ema_span_bins=ema_span_bins,
                detection_window_bins=detection_window_bins,
            )
            clustered_by_leader[leader] = cluster_events_first(raw, gap_bins=cluster_gap_bins)

        all_events = classify_signals(
            clustered_by_leader,
            bin_size_ms=bin_size_ms,
            confirm_window_bins=confirm_window_bins,
        )

        # Attach follower_metrics per event.
        for fol in followers:
            metrics = compute_metrics(all_events, vwap_df, ema_df, fol, bin_size_ms=bin_size_ms)
            by_bin = {m["bin_idx"]: m for m in metrics}
            for ev in all_events:
                if ev["bin_idx"] in by_bin:
                    ev.setdefault("follower_metrics", {})[fol] = {
                        k: v for k, v in by_bin[ev["bin_idx"]].items()
                        if k in ("lag_50_ms", "lag_80_ms", "hit", "mfe_bps", "mae_bps", "leader_move_bps")
                    }

        duration_s = (int(df_ticks["ts_ms"].max()) - int(df_ticks["ts_ms"].min())) / 1000

        df_bbo = _read_parquets(bbo_path_glob) if bbo_path_glob else pd.DataFrame()
        if not df_bbo.empty:
            df_bbo = df_bbo.sort_values("ts_ms").reset_index(drop=True)

        quality = {
            "duration_s": duration_s,
            "t_start_ms": int(df_ticks["ts_ms"].min()),
            "t_end_ms": int(df_ticks["ts_ms"].max()),
            "coverage_pct": coverage,
            "sigma_per_venue": sigma,
            "ticks_per_venue": {v: int((df_ticks["venue"] == v).sum()) for v in venues},
            "bbo_per_venue": (
                {v: int((df_bbo["venue"] == v).sum()) for v in venues} if not df_bbo.empty else {}
            ),
        }

        meta = {
            "session_id": session_id,
            "collection_id": collection_id,
            "params": params,
            "params_hash": _params_hash(params),
            "venues": venues,
            "leaders": leaders,
            "followers": followers,
            "n_events": len(all_events),
            "n_signal_a": sum(1 for e in all_events if e["signal"] == "A"),
            "n_signal_b": sum(1 for e in all_events if e["signal"] == "B"),
            "n_signal_c": sum(1 for e in all_events if e["signal"] == "C"),
        }

        s = cls(
            session_id=session_id,
            meta=meta,
            events=EventsTable(all_events),
            quality=quality,
        )
        s.vwap_df = vwap_df
        s.ema_df = ema_df
        s.dev_df = dev_df
        s.bbo_df = df_bbo if not df_bbo.empty else None
        return s


def load_session(session_id: str, data_dir: Path | str = DEFAULT_DATA_DIR) -> Session:
    root = Path(data_dir) / "sessions" / session_id
    if not root.is_dir():
        raise FileNotFoundError(f"Session directory not found: {root}")

    meta = json.loads((root / "meta.json").read_text())
    events = json.loads((root / "events.json").read_text())
    quality = json.loads((root / "quality.json").read_text()) if (root / "quality.json").exists() else {}
    pw = json.loads((root / "price_windows.json").read_text()) if (root / "price_windows.json").exists() else []
    bw = json.loads((root / "bbo_windows.json").read_text()) if (root / "bbo_windows.json").exists() else []

    return Session(
        session_id=session_id,
        meta=meta,
        events=EventsTable(events),
        quality=quality,
        price_windows=pw,
        bbo_windows=bw,
    )


# ─── helpers ───

def _read_parquets(path_or_glob: str | list[str]) -> pd.DataFrame:
    if isinstance(path_or_glob, list):
        files: list[str] = []
        for p in path_or_glob:
            files.extend(_expand_paths(p))
    else:
        files = _expand_paths(path_or_glob)
    if not files:
        raise FileNotFoundError(f"No parquet files matched: {path_or_glob}")
    dfs = []
    for f in files:
        try:
            tmp = pd.read_parquet(f)
            if len(tmp):
                dfs.append(tmp)
        except Exception:
            continue
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


def _expand_paths(pattern: str) -> list[str]:
    p = Path(pattern)
    # Accept: flat (data/ticks_*.parquet), date-partitioned (data/ticks/), or explicit glob.
    if p.is_dir():
        return sorted(glob.glob(str(p / "**" / "*.parquet"), recursive=True))
    matches = sorted(glob.glob(pattern, recursive=True))
    if matches:
        return matches
    # Spec layout fallback: "data/ticks" -> search subdirectories.
    if p.exists() and p.is_dir():
        return sorted(glob.glob(str(p / "**" / "*.parquet"), recursive=True))
    return []
