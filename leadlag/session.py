"""Session loading, persistence and batch-analysis artifact generation.

The public contract is intentionally split:
  * ``events.json`` stays small and contains metadata/metrics only.
  * ``price_windows.json`` and ``bbo_windows.json`` hold chart windows and are
    loaded lazily by API/UI event-detail calls.
  * ``vwap.parquet``/``ema.parquet``/``dev.parquet``/``bbo.parquet`` are local
    frame artifacts that make ``load_session(...).vwap_df`` usable from
    notebooks and let the backtest API run from a saved session.
"""
from __future__ import annotations

import glob
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from leadlag.contracts import (
    utc_from_ms,
    utc_now_iso,
    validate_session_artifacts,
    validate_session_payload,
    write_json,
)


DEFAULT_DATA_DIR = Path("data")
SESSION_CONTRACT_VERSION = "session.v1"


def _params_hash(params: dict) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()[:8]


def make_session_id(collection_id: str, params: dict) -> str:
    return f"{collection_id}_{_params_hash(params)}"


class EventsTable:
    """Notebook-friendly wrapper around event rows."""

    def __init__(self, rows: Iterable[dict] | None = None):
        self.rows = list(rows or [])

    @property
    def count(self) -> int:
        return len(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, i):
        return self.rows[i]

    def filter(
        self,
        *,
        signal: str | None = None,
        min_magnitude: float | None = None,
        follower: str | None = None,
        leader_mode: str | None = None,
        direction: int | str | None = None,
        time_range: tuple[str, str] | None = None,
        min_lagging: int | None = None,
        **exact: Any,
    ) -> "EventsTable":
        out = list(self.rows)
        if signal:
            out = [e for e in out if e.get("signal") == signal]
        if min_magnitude is not None:
            out = [e for e in out if float(e.get("magnitude_sigma") or 0.0) >= float(min_magnitude)]
        if follower:
            out = [e for e in out if follower in e.get("lagging_followers", [])]
        if leader_mode:
            lm = leader_mode.lower()
            if lm in {"confirmed", "c"}:
                out = [e for e in out if e.get("signal") == "C" or e.get("leader") == "confirmed"]
            elif lm in {"okx", "okx only"}:
                out = [e for e in out if e.get("anchor_leader") == "OKX Perp" or e.get("leader") == "OKX Perp"]
            elif lm in {"bybit", "bybit only"}:
                out = [e for e in out if e.get("anchor_leader") == "Bybit Perp" or e.get("leader") == "Bybit Perp"]
        if direction not in (None, ""):
            dir_int = int(direction)
            out = [e for e in out if int(e.get("direction") or 0) == dir_int]
        if min_lagging is not None:
            out = [e for e in out if int(e.get("n_lagging", len(e.get("lagging_followers", [])))) >= int(min_lagging)]
        if time_range:
            start_hhmm, end_hhmm = time_range
            out = [e for e in out if _utc_time_in_range(int(e.get("ts_ms", 0)), start_hhmm, end_hhmm)]
        for key, value in exact.items():
            out = [e for e in out if e.get(key) == value]
        return EventsTable(out)

    def stats(self, follower: str) -> dict:
        rows = [e for e in self.rows if follower in e.get("follower_metrics", {})]
        metrics = [e["follower_metrics"][follower] for e in rows]
        if not metrics:
            return {"count": 0}
        hit_vals = [m.get("hit") for m in metrics if m.get("hit") is not None]
        lag_vals = [m.get("lag_50_ms") for m in metrics if m.get("lag_50_ms") is not None]
        mfe_vals = [m.get("mfe_bps") for m in metrics if m.get("mfe_bps") is not None]
        mae_vals = [m.get("mae_bps") for m in metrics if m.get("mae_bps") is not None]
        return {
            "count": len(rows),
            "hit_rate": float(np.mean(hit_vals)) if hit_vals else None,
            "mean_lag_50_ms": float(np.mean(lag_vals)) if lag_vals else None,
            "mean_mfe_bps": float(np.mean(mfe_vals)) if mfe_vals else None,
            "mean_mae_bps": float(np.mean(mae_vals)) if mae_vals else None,
        }

    def to_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


class Session:
    def __init__(
        self,
        session_id: str,
        meta: dict,
        events: EventsTable | list[dict],
        quality: dict | None = None,
        *,
        price_windows: list[dict] | None = None,
        bbo_windows: list[dict] | None = None,
        root_dir: Path | None = None,
        vwap_df: pd.DataFrame | None = None,
        ema_df: pd.DataFrame | None = None,
        dev_df: pd.DataFrame | None = None,
        bbo_df: pd.DataFrame | None = None,
        metrics_df: pd.DataFrame | None = None,
        grid_df: pd.DataFrame | None = None,
        ci: list[dict] | None = None,
    ):
        self.session_id = session_id
        self.meta = meta
        self.events = events if isinstance(events, EventsTable) else EventsTable(events)
        self.quality = quality or {}
        self.root_dir = root_dir
        self._price_windows = price_windows
        self._bbo_windows = bbo_windows
        self._vwap_df = vwap_df
        self._ema_df = ema_df
        self._dev_df = dev_df
        self._bbo_df = bbo_df
        self._metrics_df = metrics_df
        self._grid_df = grid_df
        self.ci = ci or []

    @property
    def collection_id(self) -> str:
        return self.meta.get("collection_session_id") or self.meta.get("collection_id") or self.session_id.rsplit("_", 1)[0]

    @property
    def params(self) -> dict:
        return self.meta.get("params", {})

    @property
    def price_windows(self) -> list[dict]:
        if self._price_windows is None:
            self._price_windows = self._read_json_artifact("price_windows.json", default=[])
        return self._price_windows

    @price_windows.setter
    def price_windows(self, value: list[dict]) -> None:
        self._price_windows = value

    @property
    def bbo_windows(self) -> list[dict]:
        if self._bbo_windows is None:
            self._bbo_windows = self._read_json_artifact("bbo_windows.json", default=[])
        return self._bbo_windows

    @bbo_windows.setter
    def bbo_windows(self, value: list[dict]) -> None:
        self._bbo_windows = value

    @property
    def vwap_df(self) -> pd.DataFrame | None:
        if self._vwap_df is None:
            self._vwap_df = self._read_frame_artifact("vwap.parquet")
        return self._vwap_df

    @vwap_df.setter
    def vwap_df(self, value: pd.DataFrame | None) -> None:
        self._vwap_df = value

    @property
    def ema_df(self) -> pd.DataFrame | None:
        if self._ema_df is None:
            self._ema_df = self._read_frame_artifact("ema.parquet")
        return self._ema_df

    @ema_df.setter
    def ema_df(self, value: pd.DataFrame | None) -> None:
        self._ema_df = value

    @property
    def dev_df(self) -> pd.DataFrame | None:
        if self._dev_df is None:
            self._dev_df = self._read_frame_artifact("dev.parquet")
        return self._dev_df

    @dev_df.setter
    def dev_df(self, value: pd.DataFrame | None) -> None:
        self._dev_df = value

    @property
    def bbo_df(self) -> pd.DataFrame | None:
        if self._bbo_df is None:
            self._bbo_df = self._read_frame_artifact("bbo.parquet")
        return self._bbo_df

    @bbo_df.setter
    def bbo_df(self, value: pd.DataFrame | None) -> None:
        self._bbo_df = value

    @property
    def metrics_df(self) -> pd.DataFrame | None:
        if self._metrics_df is None:
            self._metrics_df = self._read_frame_artifact("metrics.parquet")
        return self._metrics_df

    @metrics_df.setter
    def metrics_df(self, value: pd.DataFrame | None) -> None:
        self._metrics_df = value

    @property
    def grid_df(self) -> pd.DataFrame | None:
        if self._grid_df is None:
            self._grid_df = self._read_frame_artifact("grid.parquet")
        return self._grid_df

    @grid_df.setter
    def grid_df(self, value: pd.DataFrame | None) -> None:
        self._grid_df = value

    def get_price_window(self, bin_idx: int) -> dict | None:
        return next((w for w in self.price_windows if int(w.get("bin_idx", -1)) == int(bin_idx)), None)

    def get_bbo_window(self, bin_idx: int) -> dict | None:
        return next((w for w in self.bbo_windows if int(w.get("bin_idx", -1)) == int(bin_idx)), None)

    def event_detail(self, bin_idx: int) -> dict:
        event = next((r for r in self.events.rows if int(r.get("bin_idx", -1)) == int(bin_idx)), None)
        if event is None:
            raise KeyError(f"Event bin_idx={bin_idx} not found")
        bbo_window = self.get_bbo_window(bin_idx)
        bbo_available = self.meta.get("bbo_available", {})
        no_bbo_venues = [v for v, available in bbo_available.items() if not available]
        return {
            "event": event,
            "price_window": self.get_price_window(bin_idx),
            "bbo_window": bbo_window,
            "bbo_available": bbo_available,
            "no_bbo_venues": no_bbo_venues,
            "fees": self.meta.get("fees", {}),
        }

    def save(self, data_dir: Path | str = DEFAULT_DATA_DIR) -> Path:
        out = Path(data_dir) / "sessions" / self.session_id
        out.mkdir(parents=True, exist_ok=True)

        meta = _complete_meta(self.meta, self.session_id, self.events.rows, self.quality)
        price_windows = self.price_windows if self._price_windows is not None else []
        bbo_windows = self.bbo_windows if self._bbo_windows is not None else []
        validate_session_payload(meta, self.events.rows, price_windows, bbo_windows, self.quality)

        write_json(out / "meta.json", meta, indent=2)
        write_json(out / "events.json", self.events.rows)
        write_json(out / "price_windows.json", price_windows)
        write_json(out / "bbo_windows.json", bbo_windows)
        write_json(out / "quality.json", self.quality, indent=2)
        if self.ci:
            write_json(out / "ci.json", self.ci, indent=2)

        _write_frame(out / "vwap.parquet", self._vwap_df)
        _write_frame(out / "ema.parquet", self._ema_df)
        _write_frame(out / "dev.parquet", self._dev_df)
        _write_frame(out / "bbo.parquet", self._bbo_df)
        _write_frame(out / "metrics.parquet", self._metrics_df)
        _write_frame(out / "grid.parquet", self._grid_df)
        validate_session_artifacts(out)
        self.meta = meta
        self.root_dir = out
        return out

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
        window_ms: int = 10_000,
    ) -> "Session":
        """Run the full batch pipeline over raw parquet files."""
        from leadlag.analysis.binning import bin_to_vwap
        from leadlag.analysis.ema import compute_deviation, compute_ema
        from leadlag.analysis.detection import classify_signals, cluster_events_first, detect_events
        from leadlag.analysis.metrics import bootstrap_ci, compute_metrics, grid_search
        from leadlag.venues import BBO_UNAVAILABLE_VENUES, LEADERS, REGISTRY

        params = {
            "bin_size_ms": bin_size_ms,
            "ema_span_bins": ema_span_bins,
            "threshold_sigma": threshold_sigma,
            "follower_max_dev": follower_max_dev,
            "cluster_gap_bins": cluster_gap_bins,
            "detection_window_bins": detection_window_bins,
            "confirm_window_bins": confirm_window_bins,
            "window_ms": window_ms,
        }
        session_id = make_session_id(collection_id, params)
        tick_files = _files_for(ticks_path_glob)
        bbo_files = _files_for(bbo_path_glob) if bbo_path_glob else []

        df_ticks = _read_parquets(tick_files)
        if df_ticks.empty:
            raise ValueError("No tick rows available for analysis")
        df_ticks = df_ticks.sort_values("ts_ms").reset_index(drop=True)
        df_ticks = df_ticks.drop_duplicates(subset=["ts_ms", "venue", "price", "qty"])

        all_venues_seen = list(df_ticks["venue"].dropna().unique())
        leaders = [v for v in LEADERS if v in all_venues_seen]
        followers = sorted([v for v in all_venues_seen if v not in leaders])
        venues = leaders + followers

        vwap_df, t_start, coverage = bin_to_vwap(df_ticks, venues, bin_size_ms=bin_size_ms)
        ema_df = compute_ema(vwap_df, venues, ema_span_bins=ema_span_bins)
        dev_df, sigma = compute_deviation(vwap_df, ema_df, venues, ema_span_bins=ema_span_bins)

        clustered_by_leader = {}
        for leader in leaders:
            raw = detect_events(
                leader,
                followers,
                dev_df,
                t_start=t_start,
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

        metrics_rows: list[dict] = []
        for fol in followers:
            metrics = compute_metrics(all_events, vwap_df, ema_df, fol, bin_size_ms=bin_size_ms)
            metrics_rows.extend(metrics)
            by_bin = {m["bin_idx"]: m for m in metrics}
            for ev in all_events:
                if ev["bin_idx"] in by_bin:
                    ev.setdefault("follower_metrics", {})[fol] = {
                        k: v
                        for k, v in by_bin[ev["bin_idx"]].items()
                        if k in ("lag_50_ms", "lag_80_ms", "hit", "mfe_bps", "mae_bps", "leader_move_bps")
                    }

        fees_bps = {
            name: float(cfg.taker_fee_bps)
            for name, cfg in REGISTRY.items()
            if name in venues
        }
        grid_df = grid_search(all_events, vwap_df, followers, fees_bps, bin_size_ms=bin_size_ms)
        _attach_grid_results(all_events, grid_df)
        events = _normalize_events(all_events)

        df_bbo = _read_parquets(bbo_files) if bbo_files else pd.DataFrame()
        if not df_bbo.empty:
            df_bbo = df_bbo.sort_values("ts_ms").reset_index(drop=True)

        price_windows = _build_price_windows(events, vwap_df, venues, bin_size_ms, window_ms)
        bbo_windows = _build_bbo_windows(events, df_bbo, venues, t_start, bin_size_ms, window_ms, BBO_UNAVAILABLE_VENUES)
        duration_s = (int(df_ticks["ts_ms"].max()) - int(df_ticks["ts_ms"].min())) / 1000.0
        quality = _build_quality(df_ticks, df_bbo, venues, leaders, coverage, sigma, duration_s, bin_size_ms)

        metrics_df = pd.DataFrame(metrics_rows)
        ci = _build_ci(grid_df, bootstrap_ci)

        meta = {
            "session_id": session_id,
            "collection_id": collection_id,
            "collection_session_id": collection_id,
            "params": params,
            "params_hash": _params_hash(params),
            "collection_files": {
                "ticks": [str(Path(f)) for f in tick_files],
                "bbo": [str(Path(f)) for f in bbo_files],
            },
            "t_start_ms": int(df_ticks["ts_ms"].min()),
            "t_end_ms": int(df_ticks["ts_ms"].max()),
            "duration_s": duration_s,
            "bin_size_ms": bin_size_ms,
            "ema_span": ema_span_bins,
            "threshold_sigma": threshold_sigma,
            "follower_max_dev": follower_max_dev,
            "cluster_gap_bins": cluster_gap_bins,
            "confirm_window_bins": confirm_window_bins,
            "venues": venues,
            "leaders": leaders,
            "followers": followers,
            "fees": _fees_for_venues(venues),
            "bbo_available": {
                v: bool(v not in BBO_UNAVAILABLE_VENUES and v in set(df_bbo.get("venue", pd.Series(dtype=str)).unique()))
                for v in venues
            },
            "n_ticks": int(len(df_ticks)),
            "n_bbo": int(len(df_bbo)),
            "n_events": len(events),
            "n_signal_a": sum(1 for e in events if e["signal"] == "A"),
            "n_signal_b": sum(1 for e in events if e["signal"] == "B"),
            "n_signal_c": sum(1 for e in events if e["signal"] == "C"),
            "created_at_utc": utc_now_iso(),
            "source_data_layout_version": SESSION_CONTRACT_VERSION,
        }

        return cls(
            session_id=session_id,
            meta=meta,
            events=EventsTable(events),
            quality=quality,
            price_windows=price_windows,
            bbo_windows=bbo_windows,
            vwap_df=vwap_df,
            ema_df=ema_df,
            dev_df=dev_df,
            bbo_df=df_bbo if not df_bbo.empty else None,
            metrics_df=metrics_df if not metrics_df.empty else None,
            grid_df=grid_df if not grid_df.empty else None,
            ci=ci,
        )

    def _read_json_artifact(self, name: str, default: Any) -> Any:
        if self.root_dir is None:
            return default
        path = self.root_dir / name
        if not path.exists():
            return default
        return json.loads(path.read_text())

    def _read_frame_artifact(self, name: str) -> pd.DataFrame | None:
        if self.root_dir is None:
            return None
        path = self.root_dir / name
        if not path.exists():
            return None
        return pd.read_parquet(path)


def load_session(
    session_id: str,
    data_dir: Path | str = DEFAULT_DATA_DIR,
    *,
    load_windows: bool = False,
    load_frames: bool = False,
) -> Session:
    root = Path(data_dir) / "sessions" / session_id
    if not root.is_dir():
        raise FileNotFoundError(f"Session directory not found: {root}")

    meta = json.loads((root / "meta.json").read_text())
    events = json.loads((root / "events.json").read_text())
    quality = json.loads((root / "quality.json").read_text()) if (root / "quality.json").exists() else {"venues": {}}
    ci = json.loads((root / "ci.json").read_text()) if (root / "ci.json").exists() else []
    session = Session(
        session_id=session_id,
        meta=meta,
        events=EventsTable(events),
        quality=quality,
        root_dir=root,
        price_windows=json.loads((root / "price_windows.json").read_text()) if load_windows and (root / "price_windows.json").exists() else None,
        bbo_windows=json.loads((root / "bbo_windows.json").read_text()) if load_windows and (root / "bbo_windows.json").exists() else None,
        ci=ci,
    )
    if load_frames:
        _ = session.vwap_df
        _ = session.ema_df
        _ = session.dev_df
        _ = session.bbo_df
    return session


def list_sessions(data_dir: Path | str = DEFAULT_DATA_DIR) -> list[dict]:
    root = Path(data_dir) / "sessions"
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir(), reverse=True):
        meta_p = d / "meta.json"
        if not meta_p.exists():
            continue
        try:
            meta = json.loads(meta_p.read_text())
        except Exception:
            continue
        t_start = meta.get("t_start_ms")
        out.append({
            "id": meta.get("session_id", d.name),
            "collection_id": meta.get("collection_session_id") or meta.get("collection_id"),
            "collection_session_id": meta.get("collection_session_id") or meta.get("collection_id"),
            "params_hash": meta.get("params_hash"),
            "date": (utc_from_ms(t_start) or "")[:10] if t_start else None,
            "duration_h": (float(meta.get("duration_s", 0.0)) / 3600.0) if meta.get("duration_s") is not None else None,
            "n_ticks": meta.get("n_ticks", 0),
            "n_bbo": meta.get("n_bbo", 0),
            "n_events": meta.get("n_events", 0),
            "n_signal_a": meta.get("n_signal_a", 0),
            "n_signal_b": meta.get("n_signal_b", 0),
            "n_signal_c": meta.get("n_signal_c", 0),
            "n_venues": len(meta.get("venues", [])),
            "venues": meta.get("venues", []),
            "created_at_utc": meta.get("created_at_utc"),
            "has_vwap": (d / "vwap.parquet").exists(),
            "has_bbo": (d / "bbo.parquet").exists(),
        })
    return out


def _read_parquets(path_or_glob: str | list[str]) -> pd.DataFrame:
    files = _files_for(path_or_glob)
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


def _files_for(path_or_glob: str | list[str] | None) -> list[str]:
    if path_or_glob is None:
        return []
    if isinstance(path_or_glob, list):
        files: list[str] = []
        for p in path_or_glob:
            files.extend(_expand_paths(p))
        return sorted(set(files))
    return _expand_paths(path_or_glob)


def _expand_paths(pattern: str) -> list[str]:
    p = Path(pattern)
    if p.is_dir():
        return sorted(glob.glob(str(p / "**" / "*.parquet"), recursive=True))
    matches = sorted(glob.glob(pattern, recursive=True))
    if matches:
        return matches
    return []


def _write_frame(path: Path, df: pd.DataFrame | None) -> None:
    if df is not None and not df.empty:
        df.to_parquet(path)


def _complete_meta(meta: dict, session_id: str, events: list[dict], quality: dict) -> dict:
    out = dict(meta)
    out.setdefault("session_id", session_id)
    out.setdefault("collection_session_id", out.get("collection_id", session_id.rsplit("_", 1)[0]))
    out.setdefault("collection_id", out["collection_session_id"])
    out.setdefault("params_hash", session_id.rsplit("_", 1)[-1] if "_" in session_id else "")
    out.setdefault("collection_files", {"ticks": [], "bbo": []})
    out.setdefault("t_start_ms", quality.get("t_start_ms", 0))
    out.setdefault("t_end_ms", quality.get("t_end_ms", out["t_start_ms"]))
    out.setdefault("duration_s", quality.get("duration_s", 0.0))
    params = out.get("params", {})
    out.setdefault("bin_size_ms", params.get("bin_size_ms", 50))
    out.setdefault("ema_span", params.get("ema_span_bins", params.get("ema_span", 200)))
    out.setdefault("threshold_sigma", params.get("threshold_sigma", 2.0))
    out.setdefault("venues", list((quality.get("venues") or {}).keys()))
    out.setdefault("leaders", [])
    out.setdefault("followers", [v for v in out.get("venues", []) if v not in out.get("leaders", [])])
    out.setdefault("fees", _fees_for_venues(out.get("venues", [])))
    out.setdefault("bbo_available", {v: bool((quality.get("venues", {}).get(v, {}) or {}).get("bbo_available", False)) for v in out.get("venues", [])})
    out.setdefault("n_ticks", sum(int((q or {}).get("ticks_total", 0)) for q in (quality.get("venues") or {}).values()))
    out.setdefault("n_bbo", sum(int((q or {}).get("bbo_total", 0)) for q in (quality.get("venues") or {}).values()))
    out["n_events"] = len(events)
    out["n_signal_a"] = sum(1 for e in events if e.get("signal") == "A")
    out["n_signal_b"] = sum(1 for e in events if e.get("signal") == "B")
    out["n_signal_c"] = sum(1 for e in events if e.get("signal") == "C")
    out.setdefault("created_at_utc", utc_now_iso())
    out.setdefault("source_data_layout_version", SESSION_CONTRACT_VERSION)
    return out


def _normalize_events(events: list[dict]) -> list[dict]:
    out = []
    for i, ev in enumerate(sorted(events, key=lambda e: (int(e.get("bin_idx", 0)), str(e.get("signal", ""))))):
        leader = ev.get("leader", "")
        anchor = ev.get("anchor_leader") or (leader if leader != "confirmed" else _infer_anchor_leader(ev))
        row = {
            "event_id": int(ev.get("event_id", i)),
            "bin_idx": int(ev["bin_idx"]),
            "ts_ms": int(ev.get("ts_ms", 0)),
            "time_utc": utc_from_ms(int(ev.get("ts_ms", 0))),
            "signal": ev.get("signal", ""),
            "direction": int(ev.get("direction", 0)),
            "magnitude_sigma": float(ev.get("magnitude_sigma", 0.0)),
            "leader": leader,
            "leader_dev": ev.get("leader_dev"),
            "anchor_leader": anchor,
            "confirmer_leader": ev.get("confirmer_leader"),
            "confirmer_bin": ev.get("confirmer_bin"),
            "confirmer_lag_ms": ev.get("confirmer_lag_ms"),
            "lagging_followers": list(ev.get("lagging_followers", [])),
            "n_lagging": int(ev.get("n_lagging", len(ev.get("lagging_followers", [])))),
            "follower_metrics": ev.get("follower_metrics", {}),
            "grid_results": ev.get("grid_results", {}),
            "quality_flags_at_event": ev.get("quality_flags_at_event", []),
        }
        out.append(row)
    return out


def _infer_anchor_leader(ev: dict) -> str | None:
    confirmer = ev.get("confirmer_leader")
    if confirmer == "OKX Perp":
        return "Bybit Perp"
    if confirmer == "Bybit Perp":
        return "OKX Perp"
    return None


def _attach_grid_results(events: list[dict], grid_df: pd.DataFrame) -> None:
    if grid_df.empty:
        for ev in events:
            ev.setdefault("grid_results", {})
        return
    by_bin = {int(ev["bin_idx"]): ev for ev in events}
    for r in grid_df.to_dict(orient="records"):
        ev = by_bin.get(int(r["bin_idx"]))
        if ev is None:
            continue
        fol = str(r["follower"])
        delay = str(int(r["delay_ms"]))
        hold = str(int(r["hold_ms"]))
        ev.setdefault("grid_results", {}).setdefault(fol, {}).setdefault(delay, {})[hold] = {
            "gross_bps": r.get("gross_pnl_bps"),
            "net_bps": r.get("net_pnl_bps"),
            "hit": r.get("hit"),
            "fee_bps": r.get("fee_bps"),
        }
    for ev in events:
        ev.setdefault("grid_results", {})


def _build_ci(grid_df: pd.DataFrame, bootstrap_ci_fn) -> list[dict]:
    if grid_df.empty:
        return []
    rows = []
    group_cols = ["follower", "signal", "delay_ms", "hold_ms"]
    for keys, g in grid_df.groupby(group_cols):
        follower, signal, delay_ms, hold_ms = keys
        net_mean, net_lo, net_hi = bootstrap_ci_fn(g["net_pnl_bps"].values, n_iter=200)
        gross_mean, _, _ = bootstrap_ci_fn(g["gross_pnl_bps"].values, n_iter=200)
        hit_mean, hit_lo, hit_hi = bootstrap_ci_fn(g["hit"].values, n_iter=200)
        std = float(g["net_pnl_bps"].std(ddof=0))
        classification = "profit" if net_lo > 0 else "marginal" if net_hi > 0 else "loss"
        rows.append({
            "follower": follower,
            "signal": signal,
            "delay_ms": int(delay_ms),
            "hold_ms": int(hold_ms),
            "n": int(len(g)),
            "net_mean": net_mean,
            "net_lo": net_lo,
            "net_hi": net_hi,
            "gross_mean": gross_mean,
            "hit_mean": hit_mean,
            "hit_lo": hit_lo,
            "hit_hi": hit_hi,
            "sharpe": float(g["net_pnl_bps"].mean() / std) if std > 0 else 0.0,
            "classification": classification,
        })
    return rows


def _build_price_windows(
    events: list[dict],
    vwap_df: pd.DataFrame,
    venues: list[str],
    bin_size_ms: int,
    window_ms: int,
) -> list[dict]:
    half_bins = max(1, int(window_ms // bin_size_ms))
    n = len(vwap_df)
    rows = []
    for ev in events:
        t0 = int(ev["bin_idx"])
        start = max(0, t0 - half_bins)
        end = min(n, t0 + half_bins + 1)
        rel = [(b - t0) * bin_size_ms for b in range(start, end)]
        venue_data = {}
        for venue in venues:
            if venue not in vwap_df.columns:
                continue
            vals = vwap_df[venue].iloc[start:end].astype(float).to_numpy()
            venue_data[venue] = [None if np.isnan(v) else float(v) for v in vals]
        rows.append({"bin_idx": t0, "rel_times_ms": rel, "venues": venue_data})
    return rows


def _build_bbo_windows(
    events: list[dict],
    df_bbo: pd.DataFrame,
    venues: list[str],
    t_start_ms: int,
    bin_size_ms: int,
    window_ms: int,
    unavailable_venues: set[str],
) -> list[dict]:
    if df_bbo.empty:
        return [{"bin_idx": int(ev["bin_idx"]), "rel_times_ms": [], "venues": {}} for ev in events]
    half_bins = max(1, int(window_ms // bin_size_ms))
    per_venue = {
        venue: g.sort_values("ts_ms").reset_index(drop=True)
        for venue, g in df_bbo.groupby("venue")
        if venue in venues and venue not in unavailable_venues
    }
    rows = []
    for ev in events:
        t0 = int(ev["bin_idx"])
        start = max(0, t0 - half_bins)
        end = t0 + half_bins + 1
        bins = list(range(start, end))
        rel = [(b - t0) * bin_size_ms for b in bins]
        target_ts = np.array([t_start_ms + b * bin_size_ms for b in bins])
        venue_data = {}
        for venue, g in per_venue.items():
            ts = g["ts_ms"].to_numpy()
            idx = np.searchsorted(ts, target_ts, side="right") - 1
            bid, ask, spread = [], [], []
            for pos in idx:
                if pos < 0:
                    bid.append(None)
                    ask.append(None)
                    spread.append(None)
                    continue
                r = g.iloc[int(pos)]
                bp = float(r["bid_price"])
                ap = float(r["ask_price"])
                mid = 0.5 * (bp + ap)
                bid.append(bp if bp > 0 else None)
                ask.append(ap if ap > 0 else None)
                spread.append((ap - bp) / mid * 1e4 if bp > 0 and ap > 0 and mid > 0 else None)
            venue_data[venue] = {"bid": bid, "ask": ask, "spread_bps": spread}
        rows.append({"bin_idx": t0, "rel_times_ms": rel, "venues": venue_data})
    return rows


def _build_quality(
    df_ticks: pd.DataFrame,
    df_bbo: pd.DataFrame,
    venues: list[str],
    leaders: list[str],
    coverage: dict[str, float],
    sigma: dict[str, float],
    duration_s: float,
    bin_size_ms: int,
) -> dict:
    from leadlag.venues import BBO_UNAVAILABLE_VENUES, REGISTRY

    leader_prices = df_ticks[df_ticks["venue"].isin(leaders)]["price"]
    leader_median = float(leader_prices.median()) if len(leader_prices) else None
    venues_quality = {}
    timeline_gaps = []
    for venue in venues:
        ticks = df_ticks[df_ticks["venue"] == venue]
        bbo = df_bbo[df_bbo["venue"] == venue] if not df_bbo.empty and "venue" in df_bbo else pd.DataFrame()
        cfg = REGISTRY.get(venue)
        ticks_total = int(len(ticks))
        bbo_total = int(len(bbo))
        median_price = float(ticks["price"].median()) if ticks_total else None
        dev = ((median_price - leader_median) / leader_median * 1e4) if median_price and leader_median else None
        bin_counts = pd.Series(dtype=int)
        if ticks_total:
            base = int(df_ticks["ts_ms"].min())
            bin_counts = ((ticks["ts_ms"] - base) // bin_size_ms).value_counts()
        ticks_per_s_max = float((bin_counts.max() / (bin_size_ms / 1000.0))) if len(bin_counts) else 0.0
        ticks_per_s_min = float((bin_counts.min() / (bin_size_ms / 1000.0))) if len(bin_counts) else 0.0
        side_buy_pct = float((ticks.get("side", pd.Series(dtype=str)) == "buy").mean()) if ticks_total and "side" in ticks else None
        side_sell_pct = float((ticks.get("side", pd.Series(dtype=str)) == "sell").mean()) if ticks_total and "side" in ticks else None
        bbo_stats = _bbo_quality_stats(bbo)
        gaps = _timeline_gaps(ticks, venue)
        timeline_gaps.extend(gaps)
        flag, reasons = _quality_flag(
            ticks_total=ticks_total,
            ticks_per_s=(ticks_total / duration_s if duration_s else 0.0),
            coverage_pct=float(coverage.get(venue, 0.0)),
            price_dev=dev,
        )
        venues_quality[venue] = {
            "role": cfg.role if cfg else ("leader" if venue in leaders else "follower"),
            "ticks_total": ticks_total,
            "ticks_per_s_avg": float(ticks_total / duration_s) if duration_s else 0.0,
            "ticks_per_s_max": ticks_per_s_max,
            "ticks_per_s_min_nonzero": ticks_per_s_min,
            "bin_coverage_pct": float(coverage.get(venue, 0.0)),
            "bbo_total": bbo_total,
            "bbo_per_s_avg": float(bbo_total / duration_s) if duration_s else 0.0,
            "bbo_coverage_pct": bbo_stats.pop("bbo_coverage_pct"),
            "bbo_available": bool(venue not in BBO_UNAVAILABLE_VENUES and bbo_total > 0),
            "median_price": median_price,
            "price_deviation_from_leader_bps": dev,
            "reconnects": 0,
            "downtime_s": float(sum(g["duration_s"] for g in gaps)),
            "uptime_pct": max(0.0, 100.0 - (sum(g["duration_s"] for g in gaps) / duration_s * 100.0)) if duration_s else 0.0,
            "zero_price_ticks": int((ticks["price"] <= 0).sum()) if ticks_total else 0,
            "zero_qty_ticks": int((ticks["qty"] <= 0).sum()) if ticks_total and "qty" in ticks else 0,
            "side_buy_pct": side_buy_pct,
            "side_sell_pct": side_sell_pct,
            "flag": flag,
            "flag_reasons": reasons,
            "sigma": sigma.get(venue),
            **bbo_stats,
        }
    return {
        "duration_s": duration_s,
        "t_start_ms": int(df_ticks["ts_ms"].min()),
        "t_end_ms": int(df_ticks["ts_ms"].max()),
        "coverage_pct": coverage,
        "sigma_per_venue": sigma,
        "venues": venues_quality,
        "timeline_gaps": timeline_gaps,
    }


def _bbo_quality_stats(bbo: pd.DataFrame) -> dict:
    empty = {
        "bbo_coverage_pct": 0.0,
        "bbo_median_spread_bps": None,
        "bbo_mean_spread_bps": None,
        "bbo_max_spread_bps": None,
        "bbo_p95_spread_bps": None,
        "bbo_p99_spread_bps": None,
        "bbo_pct_above_5bps": None,
    }
    if bbo.empty:
        return empty
    mid = (bbo["bid_price"].astype(float) + bbo["ask_price"].astype(float)) / 2.0
    spread = (bbo["ask_price"].astype(float) - bbo["bid_price"].astype(float)) / mid * 1e4
    spread = spread.replace([np.inf, -np.inf], np.nan).dropna()
    if spread.empty:
        return empty
    return {
        "bbo_coverage_pct": 100.0,
        "bbo_median_spread_bps": float(spread.median()),
        "bbo_mean_spread_bps": float(spread.mean()),
        "bbo_max_spread_bps": float(spread.max()),
        "bbo_p95_spread_bps": float(spread.quantile(0.95)),
        "bbo_p99_spread_bps": float(spread.quantile(0.99)),
        "bbo_pct_above_5bps": float((spread > 5.0).mean() * 100.0),
    }


def _quality_flag(ticks_total: int, ticks_per_s: float, coverage_pct: float, price_dev: float | None) -> tuple[str, list[str]]:
    reasons = []
    if ticks_total == 0:
        reasons.append("no_ticks")
    if coverage_pct < 1.0:
        reasons.append("bin_coverage_lt_1pct")
    if ticks_per_s < 0.1:
        reasons.append("ticks_per_s_lt_0_1")
    if price_dev is not None and abs(price_dev) > 100.0:
        reasons.append("price_deviation_gt_100bps")
    if reasons:
        return "bad", reasons
    if coverage_pct < 5.0:
        reasons.append("bin_coverage_lt_5pct")
    if ticks_per_s < 1.0:
        reasons.append("ticks_per_s_lt_1")
    return ("warning", reasons) if reasons else ("good", [])


def _timeline_gaps(ticks: pd.DataFrame, venue: str, gap_ms: int = 10_000) -> list[dict]:
    if len(ticks) < 2:
        return []
    ts = ticks["ts_ms"].sort_values().to_numpy()
    diffs = np.diff(ts)
    rows = []
    for i, d in enumerate(diffs):
        if d > gap_ms:
            rows.append({
                "venue": venue,
                "start_ms": int(ts[i]),
                "end_ms": int(ts[i + 1]),
                "duration_s": float(d / 1000.0),
            })
    return rows


def _fees_for_venues(venues: list[str]) -> dict:
    from leadlag.venues import REGISTRY

    out = {}
    for venue in venues:
        cfg = REGISTRY.get(venue)
        out[venue] = {
            "taker_bps": float(cfg.taker_fee_bps) if cfg else 0.0,
            "maker_bps": float(cfg.maker_fee_bps) if cfg else 0.0,
        }
    return out


def _utc_time_in_range(ts_ms: int, start_hhmm: str, end_hhmm: str) -> bool:
    iso = utc_from_ms(ts_ms)
    if not iso:
        return False
    hhmm = iso[11:16]
    if not start_hhmm and not end_hhmm:
        return True
    if start_hhmm and hhmm < start_hhmm:
        return False
    if end_hhmm and hhmm > end_hhmm:
        return False
    return True
