"""Analysis loading, persistence and batch-analysis artifact generation.

The public contract is intentionally split:
  * ``events.json`` stays small and contains metadata/metrics only.
  * ``price_windows.json`` and ``bbo_windows.json`` hold chart windows and are
    loaded lazily by API/UI event-detail calls.
  * ``vwap.parquet``/``ema.parquet``/``dev.parquet``/``bbo.parquet`` are local
    frame artifacts that make ``load_analysis(...).vwap_df`` usable from
    notebooks and let the backtest API run from a saved analysis.
"""
from __future__ import annotations

import glob
import hashlib
import json
import random
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from leadlag.contracts import (
    utc_from_ms,
    utc_now_iso,
    validate_analysis_artifacts,
    validate_analysis_payload,
    write_json,
)


DEFAULT_DATA_DIR = Path("data")
ANALYSIS_CONTRACT_VERSION = "analysis.v1"
PARQUET_BATCH_ROWS = 250_000
PRICE_SAMPLE_SIZE = 4096
TIMELINE_GAP_MS = 10_000


def _params_hash(params: dict) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()[:8]


def make_analysis_id(collection_id: str, params: dict) -> str:
    return f"{collection_id}_{_params_hash(params)}"


class EventView(dict):
    def __init__(self, row: dict, analysis: "Analysis | None" = None):
        super().__init__(row)
        self._analysis = analysis

    def plot(self, follower: str | None = None):
        if self._analysis is None:
            raise ValueError("EventView is not attached to an Analysis")
        return self._analysis.plot_event(int(self["bin_idx"]), follower=follower)


class EventsTable:
    """Notebook-friendly wrapper around event rows."""

    def __init__(self, rows: Iterable[dict] | None = None, analysis: "Analysis | None" = None):
        self.rows = list(rows or [])
        self._analysis = analysis

    @property
    def count(self) -> int:
        return len(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, i):
        return EventView(self.rows[i], self._analysis)

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
        return EventsTable(out, analysis=self._analysis)

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

    def grid_search(
        self,
        followers: list[str] | None = None,
        delays_ms: list[int] | None = None,
        holds_ms: list[int] | None = None,
    ) -> pd.DataFrame:
        if self._analysis is None or self._analysis.vwap_df is None:
            raise ValueError("EventsTable.grid_search requires an Analysis with vwap_df")
        from leadlag.analysis.metrics import grid_search

        followers = followers or self._analysis.meta.get("followers", [])
        fees = {
            venue: float((self._analysis.meta.get("fees", {}).get(venue) or {}).get("taker_bps", 0.0))
            for venue in followers
        }
        return grid_search(
            self.rows,
            self._analysis.vwap_df,
            followers,
            fees,
            delay_grid_ms=delays_ms,
            hold_grid_ms=holds_ms,
            bin_size_ms=int(self._analysis.meta.get("bin_size_ms", 50)),
        )

    def plot_lag_distribution(self, follower: str):
        import plotly.graph_objects as go

        vals = [
            e.get("follower_metrics", {}).get(follower, {}).get("lag_50_ms")
            for e in self.rows
        ]
        vals = [v for v in vals if v is not None]
        fig = go.Figure(go.Histogram(x=vals, name="lag_50_ms"))
        return _style_fig(fig, "Lag 50 distribution", "lag ms", "count")

    def plot_magnitude_distribution(self):
        import plotly.graph_objects as go

        vals = [e.get("magnitude_sigma") for e in self.rows if e.get("magnitude_sigma") is not None]
        fig = go.Figure(go.Histogram(x=vals, name="magnitude_sigma"))
        return _style_fig(fig, "Magnitude distribution", "sigma", "count")

    def plot_heatmap(self, *, x: str, y: str, metric: str, follower: str, signal: str | None = None):
        import plotly.graph_objects as go

        rows = self.filter(signal=signal).grid_search(followers=[follower]) if signal else self.grid_search(followers=[follower])
        if rows.empty:
            return _style_fig(go.Figure(), "No grid rows", x, y)
        pivot = rows.pivot_table(index=y, columns=x, values=metric, aggfunc="mean")
        fig = go.Figure(go.Heatmap(x=list(pivot.columns), y=list(pivot.index), z=pivot.values, colorscale="RdYlGn"))
        return _style_fig(fig, f"{metric} heatmap for {follower}", x, y)

    def plot_equity(self, follower: str, hold_ms: int = 30000, delay_ms: int = 0):
        import plotly.graph_objects as go

        grid = self.grid_search(followers=[follower], delays_ms=[delay_ms], holds_ms=[hold_ms])
        if grid.empty:
            return _style_fig(go.Figure(), "No equity rows", "event", "net bps")
        grid = grid.sort_values("bin_idx")
        eq = grid["net_pnl_bps"].cumsum()
        fig = go.Figure(go.Scatter(x=list(range(1, len(eq) + 1)), y=eq, mode="lines+markers", name="net"))
        return _style_fig(fig, f"{follower} equity hold={hold_ms}ms", "event", "cumulative bps")


class Analysis:
    def __init__(
        self,
        analysis_id: str,
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
        self.analysis_id = analysis_id
        self.meta = meta
        self.events = events if isinstance(events, EventsTable) else EventsTable(events)
        self.events._analysis = self
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
        return self.meta.get("recording_id") or self.meta.get("collection_id") or self.analysis_id.rsplit("_", 1)[0]

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

    def get_ema_window(self, bin_idx: int) -> dict | None:
        price_window = self.get_price_window(bin_idx)
        ema_df = self.ema_df
        if not price_window or ema_df is None or ema_df.empty:
            return None
        rel = price_window.get("rel_times_ms") or []
        bin_size_ms = int(self.meta.get("bin_size_ms", 50) or 50)
        venues = {}
        for venue in (price_window.get("venues") or {}):
            if venue not in ema_df.columns:
                continue
            values = []
            for rel_ms in rel:
                idx = int(bin_idx) + int(round(float(rel_ms) / bin_size_ms))
                if idx < 0 or idx >= len(ema_df):
                    values.append(None)
                    continue
                val = ema_df[venue].iloc[idx]
                values.append(None if pd.isna(val) else float(val))
            venues[venue] = values
        return {"bin_idx": int(bin_idx), "rel_times_ms": rel, "venues": venues}

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
            "ema_window": self.get_ema_window(bin_idx),
            "bbo_window": bbo_window,
            "bbo_available": bbo_available,
            "no_bbo_venues": no_bbo_venues,
            "fees": self.meta.get("fees", {}),
        }

    def plot_event(self, bin_idx: int, follower: str | None = None):
        import plotly.graph_objects as go

        detail = self.event_detail(bin_idx)
        event = detail["event"]
        price_window = detail.get("price_window") or {}
        rel = price_window.get("rel_times_ms") or []
        venues = price_window.get("venues") or {}
        follower = follower or (event.get("lagging_followers") or self.meta.get("followers") or [None])[0]
        fig = go.Figure()
        leaders = self.meta.get("leaders", []) if event.get("signal") == "C" else [event.get("anchor_leader") or event.get("leader")]
        for venue in leaders:
            if venue in venues:
                fig.add_trace(go.Scatter(x=rel, y=_bps_from_t0(venues[venue], rel), mode="lines", name=venue))
        if follower in venues:
            fig.add_trace(go.Scatter(x=rel, y=_bps_from_t0(venues[follower], rel), mode="lines", name=follower))
        bbo = (detail.get("bbo_window") or {}).get("venues", {}).get(follower or "")
        if bbo and follower in venues:
            fig.add_trace(go.Scatter(x=rel, y=_bps_from_t0(bbo.get("bid", []), rel), mode="lines", name=f"{follower} bid"))
            fig.add_trace(go.Scatter(x=rel, y=_bps_from_t0(bbo.get("ask", []), rel), mode="lines", fill="tonexty", name=f"{follower} ask"))
        fig.add_vline(x=0, line_dash="dash", line_color="red")
        return _style_fig(fig, f"Event {bin_idx} {event.get('signal')}", "ms from event", "bps from t0")

    def save(self, data_dir: Path | str = DEFAULT_DATA_DIR) -> Path:
        out = Path(data_dir) / "analyses" / self.analysis_id
        out.mkdir(parents=True, exist_ok=True)

        meta = _complete_meta(self.meta, self.analysis_id, self.events.rows, self.quality)
        price_windows = self.price_windows if self._price_windows is not None else []
        bbo_windows = self.bbo_windows if self._bbo_windows is not None else []
        validate_analysis_payload(meta, self.events.rows, price_windows, bbo_windows, self.quality)

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
        validate_analysis_artifacts(out)
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
        progress_callback=None,
    ) -> "Analysis":
        """Run the full batch pipeline over raw parquet files."""
        from leadlag.analysis.binning import bin_to_vwap
        from leadlag.analysis.ema import compute_deviation, compute_ema
        from leadlag.analysis.detection import classify_signals, cluster_events_first, detect_events
        from leadlag.analysis.metrics import bootstrap_ci, compute_metrics, grid_search
        from leadlag.venues import BBO_UNAVAILABLE_VENUES, LEADERS, REGISTRY

        def progress(stage: str, message: str, value: float) -> None:
            if progress_callback:
                progress_callback(stage, message, value)

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
        analysis_id = make_analysis_id(collection_id, params)
        progress("files", "Resolving raw parquet files", 0.02)
        tick_files = _files_for(ticks_path_glob)
        bbo_files = _files_for(bbo_path_glob) if bbo_path_glob else []

        progress("ticks", f"Scanning {len(tick_files)} tick parquet files in batches", 0.08)
        tick_scan = _scan_ticks_batched(tick_files, bin_size_ms=bin_size_ms)
        if tick_scan["n_ticks"] <= 0:
            raise ValueError("No tick rows available for analysis")
        progress("ticks", f"Scanned {tick_scan['n_ticks']:,} tick rows", 0.18)

        all_venues_seen = list(tick_scan["venues"])
        leaders = [v for v in LEADERS if v in all_venues_seen]
        followers = sorted([v for v in all_venues_seen if v not in leaders])
        venues = leaders + followers

        progress("binning", f"Binning ticks into {bin_size_ms}ms VWAP series", 0.28)
        vwap_df, coverage = _build_vwap_from_binned_ticks(
            tick_scan["grouped_ticks"],
            venues,
            tick_scan["t_start_ms"],
            tick_scan["t_end_ms"],
            bin_size_ms=bin_size_ms,
        )
        t_start = tick_scan["t_start_ms"]
        progress("ema", f"Computing EMA / deviation for {len(venues)} venues", 0.38)
        ema_df = compute_ema(vwap_df, venues, ema_span_bins=ema_span_bins)
        dev_df, sigma = compute_deviation(vwap_df, ema_df, venues, ema_span_bins=ema_span_bins)

        progress("events", "Detecting lead-lag events", 0.48)
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

        progress("metrics", f"Computing follower metrics for {len(followers)} followers", 0.62)
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
        progress("grid", "Running grid search and attaching event summaries", 0.72)
        grid_df = grid_search(all_events, vwap_df, followers, fees_bps, bin_size_ms=bin_size_ms)
        _attach_grid_results(all_events, grid_df)
        events = _normalize_events(all_events)

        progress("bbo", f"Loading BBO from {len(bbo_files)} parquet files", 0.80)
        bbo_scan = _scan_bbo_batched(bbo_files, bin_size_ms=bin_size_ms, t_start_ms=t_start) if bbo_files else {
            "n_bbo": 0,
            "grouped_bbo": pd.DataFrame(),
            "venue_stats": {},
        }
        df_bbo = bbo_scan["grouped_bbo"]

        progress("artifacts", "Building event windows and quality artifacts", 0.88)
        price_windows = _build_price_windows(events, vwap_df, venues, bin_size_ms, window_ms)
        bbo_windows = _build_bbo_windows(events, df_bbo, venues, t_start, bin_size_ms, window_ms, BBO_UNAVAILABLE_VENUES)
        duration_s = max(0.0, (int(tick_scan["t_end_ms"]) - int(tick_scan["t_start_ms"])) / 1000.0)
        quality = _build_quality_from_scans(
            tick_scan,
            bbo_scan,
            venues,
            leaders,
            coverage,
            sigma,
            duration_s,
            bin_size_ms,
        )

        metrics_df = pd.DataFrame(metrics_rows)
        ci = _build_ci(grid_df, bootstrap_ci)

        meta = {
            "analysis_id": analysis_id,
            "collection_id": collection_id,
            "recording_id": collection_id,
            "params": params,
            "params_hash": _params_hash(params),
            "collection_files": {
                "ticks": [str(Path(f)) for f in tick_files],
                "bbo": [str(Path(f)) for f in bbo_files],
            },
            "t_start_ms": int(tick_scan["t_start_ms"]),
            "t_end_ms": int(tick_scan["t_end_ms"]),
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
            "n_ticks": int(tick_scan["n_ticks"]),
            "n_bbo": int(bbo_scan["n_bbo"]),
            "n_events": len(events),
            "n_signal_a": sum(1 for e in events if e["signal"] == "A"),
            "n_signal_b": sum(1 for e in events if e["signal"] == "B"),
            "n_signal_c": sum(1 for e in events if e["signal"] == "C"),
            "created_at_utc": utc_now_iso(),
            "source_data_layout_version": ANALYSIS_CONTRACT_VERSION,
        }
        progress("done", f"Analysis prepared: {len(events)} events", 0.96)

        return cls(
            analysis_id=analysis_id,
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


def load_analysis(
    analysis_id: str,
    data_dir: Path | str = DEFAULT_DATA_DIR,
    *,
    load_windows: bool = False,
    load_frames: bool = False,
) -> Analysis:
    root = Path(data_dir) / "analyses" / analysis_id
    if not root.is_dir():
        raise FileNotFoundError(f"Analysis directory not found: {root}")

    meta = json.loads((root / "meta.json").read_text())
    events = json.loads((root / "events.json").read_text())
    quality = json.loads((root / "quality.json").read_text()) if (root / "quality.json").exists() else {"venues": {}}
    ci = json.loads((root / "ci.json").read_text()) if (root / "ci.json").exists() else []
    analysis = Analysis(
        analysis_id=analysis_id,
        meta=meta,
        events=EventsTable(events),
        quality=quality,
        root_dir=root,
        price_windows=json.loads((root / "price_windows.json").read_text()) if load_windows and (root / "price_windows.json").exists() else None,
        bbo_windows=json.loads((root / "bbo_windows.json").read_text()) if load_windows and (root / "bbo_windows.json").exists() else None,
        ci=ci,
    )
    if load_frames:
        _ = analysis.vwap_df
        _ = analysis.ema_df
        _ = analysis.dev_df
        _ = analysis.bbo_df
    return analysis


def list_analyses(data_dir: Path | str = DEFAULT_DATA_DIR) -> list[dict]:
    root = Path(data_dir) / "analyses"
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
            "id": meta.get("analysis_id", d.name),
            "analysis_id": meta.get("analysis_id", d.name),
            "collection_id": meta.get("recording_id") or meta.get("collection_id"),
            "recording_id": meta.get("recording_id") or meta.get("collection_id"),
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


def _read_parquets(path_or_glob: str | list[str], *, columns: list[str] | None = None) -> pd.DataFrame:
    files = _files_for(path_or_glob)
    if not files:
        raise FileNotFoundError(f"No parquet files matched: {path_or_glob}")
    try:
        table = ds.dataset(files, format="parquet").to_table(columns=columns)
        return table.to_pandas(split_blocks=True, self_destruct=True)
    except Exception:
        dfs = []
        for f in files:
            try:
                tmp = pd.read_parquet(f, columns=columns)
                if len(tmp):
                    dfs.append(tmp)
            except Exception:
                continue
        if not dfs:
            return pd.DataFrame(columns=columns)
        return pd.concat(dfs, ignore_index=True)


def _iter_parquet_batches(files: list[str], *, columns: list[str], batch_rows: int = PARQUET_BATCH_ROWS):
    for file_path in files:
        try:
            pf = pq.ParquetFile(file_path)
            for batch in pf.iter_batches(batch_size=batch_rows, columns=columns):
                yield batch.to_pandas()
        except Exception:
            continue


def iter_ticks_batches(
    data_dir: Path | str = DEFAULT_DATA_DIR,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    venues: list[str] | None = None,
    columns: list[str] | None = None,
    batch_rows: int = PARQUET_BATCH_ROWS,
) -> Iterable[pd.DataFrame]:
    selected = columns or ["ts_ms", "price", "qty", "side", "venue"]
    files = _files_for_date_range(Path(data_dir) / "ticks", date_from=date_from, date_to=date_to)
    venue_set = set(venues or [])
    for batch in _iter_parquet_batches(files, columns=selected, batch_rows=batch_rows):
        if venue_set and "venue" in batch.columns:
            batch = batch[batch["venue"].astype(str).isin(venue_set)]
        if not batch.empty:
            yield batch.reset_index(drop=True)


def iter_bbo_batches(
    data_dir: Path | str = DEFAULT_DATA_DIR,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    venues: list[str] | None = None,
    columns: list[str] | None = None,
    batch_rows: int = PARQUET_BATCH_ROWS,
) -> Iterable[pd.DataFrame]:
    selected = columns or ["ts_ms", "bid_price", "bid_qty", "ask_price", "ask_qty", "venue"]
    files = _files_for_date_range(Path(data_dir) / "bbo", date_from=date_from, date_to=date_to)
    venue_set = set(venues or [])
    for batch in _iter_parquet_batches(files, columns=selected, batch_rows=batch_rows):
        if venue_set and "venue" in batch.columns:
            batch = batch[batch["venue"].astype(str).isin(venue_set)]
        if not batch.empty:
            yield batch.reset_index(drop=True)


def _init_tick_stats() -> dict[str, Any]:
    return {
        "ticks_total": 0,
        "zero_price_ticks": 0,
        "zero_qty_ticks": 0,
        "side_buy_count": 0,
        "side_sell_count": 0,
        "price_sample": [],
        "sample_seen": 0,
        "last_ts": None,
        "timeline_gaps": [],
    }


def _reservoir_sample(values: np.ndarray, store: list[float], *, seen: int, rng: random.Random, sample_size: int = PRICE_SAMPLE_SIZE) -> int:
    for value in values:
        if not np.isfinite(value):
            continue
        seen += 1
        if len(store) < sample_size:
            store.append(float(value))
            continue
        idx = rng.randint(1, seen)
        if idx <= sample_size:
            store[idx - 1] = float(value)
    return seen


def _scan_ticks_batched(tick_files: list[str], *, bin_size_ms: int) -> dict[str, Any]:
    if not tick_files:
        return {
            "n_ticks": 0,
            "t_start_ms": 0,
            "t_end_ms": 0,
            "venues": [],
            "grouped_ticks": pd.DataFrame(columns=["venue", "bin_idx", "vwap_num", "vwap_den", "tick_count"]),
            "venue_stats": {},
            "timeline_gaps": [],
        }

    rng = random.Random(0)
    venue_stats: dict[str, dict[str, Any]] = {}
    venues_seen: set[str] = set()
    seen_tick_rows: set[int] = set()
    t_start_ms: int | None = None
    t_end_ms: int | None = None

    for batch in _iter_parquet_batches(tick_files, columns=["ts_ms", "price", "qty", "side", "venue"]):
        if batch.empty:
            continue
        batch = batch.dropna(subset=["ts_ms", "price", "qty", "venue"]).copy()
        if batch.empty:
            continue
        batch["ts_ms"] = pd.to_numeric(batch["ts_ms"], errors="coerce")
        batch["price"] = pd.to_numeric(batch["price"], errors="coerce")
        batch["qty"] = pd.to_numeric(batch["qty"], errors="coerce")
        batch = batch.dropna(subset=["ts_ms", "price", "qty"])
        if batch.empty:
            continue
        batch = _dedupe_tick_batch(batch, seen_tick_rows)
        if batch.empty:
            continue
        batch["ts_ms"] = batch["ts_ms"].astype(np.int64)
        batch["venue"] = batch["venue"].astype(str)
        t_start_ms = int(batch["ts_ms"].min()) if t_start_ms is None else min(t_start_ms, int(batch["ts_ms"].min()))
        t_end_ms = int(batch["ts_ms"].max()) if t_end_ms is None else max(t_end_ms, int(batch["ts_ms"].max()))

        for venue, g in batch.groupby("venue", sort=False):
            venues_seen.add(venue)
            stats = venue_stats.setdefault(venue, _init_tick_stats())
            stats["ticks_total"] += int(len(g))
            stats["zero_price_ticks"] += int((g["price"] <= 0).sum())
            stats["zero_qty_ticks"] += int((g["qty"] <= 0).sum())
            side = g.get("side", pd.Series(dtype=str)).astype(str)
            stats["side_buy_count"] += int((side == "buy").sum())
            stats["side_sell_count"] += int((side == "sell").sum())
            prices = g["price"].to_numpy(dtype=float, copy=False)
            stats["sample_seen"] = _reservoir_sample(prices, stats["price_sample"], seen=stats["sample_seen"], rng=rng)

            ts_sorted = np.sort(g["ts_ms"].to_numpy(dtype=np.int64, copy=False))
            prev_ts = stats["last_ts"]
            if prev_ts is not None and len(ts_sorted) and int(ts_sorted[0] - prev_ts) > TIMELINE_GAP_MS:
                stats["timeline_gaps"].append({
                    "venue": venue,
                    "start_ms": int(prev_ts),
                    "end_ms": int(ts_sorted[0]),
                    "duration_s": float((int(ts_sorted[0]) - int(prev_ts)) / 1000.0),
                })
            if len(ts_sorted) > 1:
                diffs = np.diff(ts_sorted)
                gap_idx = np.where(diffs > TIMELINE_GAP_MS)[0]
                for idx in gap_idx:
                    stats["timeline_gaps"].append({
                        "venue": venue,
                        "start_ms": int(ts_sorted[idx]),
                        "end_ms": int(ts_sorted[idx + 1]),
                        "duration_s": float((int(ts_sorted[idx + 1]) - int(ts_sorted[idx])) / 1000.0),
                    })
            if len(ts_sorted):
                stats["last_ts"] = int(ts_sorted[-1])

    if t_start_ms is None or t_end_ms is None or not venues_seen:
        return {
            "n_ticks": 0,
            "t_start_ms": 0,
            "t_end_ms": 0,
            "venues": [],
            "grouped_ticks": pd.DataFrame(columns=["venue", "bin_idx", "vwap_num", "vwap_den", "tick_count"]),
            "venue_stats": {},
            "timeline_gaps": [],
        }

    grouped_parts: list[pd.DataFrame] = []
    seen_tick_rows = set()
    for batch in _iter_parquet_batches(tick_files, columns=["ts_ms", "price", "qty", "venue"]):
        if batch.empty:
            continue
        batch = batch.dropna(subset=["ts_ms", "price", "qty", "venue"]).copy()
        if batch.empty:
            continue
        batch["ts_ms"] = pd.to_numeric(batch["ts_ms"], errors="coerce")
        batch["price"] = pd.to_numeric(batch["price"], errors="coerce")
        batch["qty"] = pd.to_numeric(batch["qty"], errors="coerce")
        batch = batch.dropna(subset=["ts_ms", "price", "qty"])
        if batch.empty:
            continue
        batch = _dedupe_tick_batch(batch, seen_tick_rows)
        if batch.empty:
            continue
        batch["ts_ms"] = batch["ts_ms"].astype(np.int64)
        batch["venue"] = batch["venue"].astype(str)
        batch["bin_idx"] = ((batch["ts_ms"] - t_start_ms) // bin_size_ms).astype(np.int64)
        batch["pv"] = batch["price"] * batch["qty"]
        grouped_parts.append(
            batch.groupby(["venue", "bin_idx"], as_index=False)
            .agg(vwap_num=("pv", "sum"), vwap_den=("qty", "sum"), tick_count=("price", "count"))
        )

    grouped_ticks = pd.concat(grouped_parts, ignore_index=True) if grouped_parts else pd.DataFrame(columns=["venue", "bin_idx", "vwap_num", "vwap_den", "tick_count"])
    if not grouped_ticks.empty:
        grouped_ticks = (
            grouped_ticks.groupby(["venue", "bin_idx"], as_index=False)
            .agg(vwap_num=("vwap_num", "sum"), vwap_den=("vwap_den", "sum"), tick_count=("tick_count", "sum"))
        )
        grouped_ticks["vwap"] = grouped_ticks["vwap_num"] / grouped_ticks["vwap_den"]

    timeline_gaps = []
    for venue in sorted(venue_stats):
        timeline_gaps.extend(venue_stats[venue]["timeline_gaps"])

    return {
        "n_ticks": int(sum(int(v["ticks_total"]) for v in venue_stats.values())),
        "t_start_ms": int(t_start_ms),
        "t_end_ms": int(t_end_ms),
        "venues": sorted(venues_seen),
        "grouped_ticks": grouped_ticks,
        "venue_stats": venue_stats,
        "timeline_gaps": sorted(timeline_gaps, key=lambda row: (int(row["start_ms"]), row["venue"])),
    }


def _dedupe_tick_batch(batch: pd.DataFrame, seen_hashes: set[int]) -> pd.DataFrame:
    sig = pd.util.hash_pandas_object(batch[["ts_ms", "venue", "price", "qty"]], index=False).astype("uint64")
    mask = []
    for value in sig.tolist():
        key = int(value)
        if key in seen_hashes:
            mask.append(False)
        else:
            seen_hashes.add(key)
            mask.append(True)
    return batch.loc[mask].copy()


def _build_vwap_from_binned_ticks(
    grouped_ticks: pd.DataFrame,
    venues: list[str],
    t_start_ms: int,
    t_end_ms: int,
    *,
    bin_size_ms: int,
) -> tuple[pd.DataFrame, dict[str, float]]:
    n_bins = int((int(t_end_ms) - int(t_start_ms)) / bin_size_ms) + 1 if t_end_ms >= t_start_ms else 0
    grouped = grouped_ticks if grouped_ticks is not None else pd.DataFrame()
    vwap_dict: dict[str, pd.Series] = {}
    raw_coverage: dict[str, float] = {}
    for venue in venues:
        if not grouped.empty and "venue" in grouped:
            sub = grouped[grouped["venue"] == venue][["bin_idx", "vwap"]].set_index("bin_idx")["vwap"]
        else:
            sub = pd.Series(dtype=float)
        series = pd.Series(index=range(n_bins), dtype=float)
        if len(sub):
            series.loc[sub.index.astype(int)] = sub.values
        vwap_dict[venue] = series.ffill()
        raw_coverage[venue] = len(sub) / n_bins * 100 if n_bins else 0.0
    vwap_df = pd.DataFrame(vwap_dict)
    vwap_df.index.name = "bin_idx"
    vwap_df["ts_ms"] = t_start_ms + vwap_df.index * bin_size_ms
    return vwap_df, raw_coverage


def _init_bbo_stats() -> dict[str, Any]:
    return {"bbo_total": 0}


def _scan_bbo_batched(bbo_files: list[str], *, bin_size_ms: int, t_start_ms: int) -> dict[str, Any]:
    if not bbo_files:
        return {"n_bbo": 0, "grouped_bbo": pd.DataFrame(), "venue_stats": {}}

    venue_stats: dict[str, dict[str, Any]] = {}
    grouped_parts: list[pd.DataFrame] = []
    for batch in _iter_parquet_batches(bbo_files, columns=["ts_ms", "bid_price", "bid_qty", "ask_price", "ask_qty", "venue"]):
        if batch.empty:
            continue
        batch = batch.dropna(subset=["ts_ms", "bid_price", "ask_price", "venue"]).copy()
        if batch.empty:
            continue
        batch["ts_ms"] = pd.to_numeric(batch["ts_ms"], errors="coerce")
        batch["bid_price"] = pd.to_numeric(batch["bid_price"], errors="coerce")
        batch["ask_price"] = pd.to_numeric(batch["ask_price"], errors="coerce")
        batch["bid_qty"] = pd.to_numeric(batch.get("bid_qty", 0.0), errors="coerce").fillna(0.0)
        batch["ask_qty"] = pd.to_numeric(batch.get("ask_qty", 0.0), errors="coerce").fillna(0.0)
        batch = batch.dropna(subset=["ts_ms", "bid_price", "ask_price"])
        if batch.empty:
            continue
        batch["ts_ms"] = batch["ts_ms"].astype(np.int64)
        batch["venue"] = batch["venue"].astype(str)
        batch["bin_idx"] = ((batch["ts_ms"] - int(t_start_ms)) // bin_size_ms).astype(np.int64)
        grouped_parts.append(
            batch.sort_values(["venue", "bin_idx", "ts_ms"])
            .groupby(["venue", "bin_idx"], as_index=False)
            .tail(1)[["venue", "bin_idx", "ts_ms", "bid_price", "bid_qty", "ask_price", "ask_qty"]]
        )

    grouped_bbo = pd.concat(grouped_parts, ignore_index=True) if grouped_parts else pd.DataFrame(
        columns=["venue", "bin_idx", "ts_ms", "bid_price", "bid_qty", "ask_price", "ask_qty"]
    )
    if not grouped_bbo.empty:
        grouped_bbo = (
            grouped_bbo.sort_values(["venue", "bin_idx", "ts_ms"])
            .groupby(["venue", "bin_idx"], as_index=False)
            .tail(1)
            .reset_index(drop=True)
        )

    for batch in _iter_parquet_batches(bbo_files, columns=["ts_ms", "bid_price", "ask_price", "venue"]):
        if batch.empty:
            continue
        batch = batch.dropna(subset=["ts_ms", "bid_price", "ask_price", "venue"]).copy()
        if batch.empty:
            continue
        batch["venue"] = batch["venue"].astype(str)
        for venue, g in batch.groupby("venue", sort=False):
            stats = venue_stats.setdefault(venue, _init_bbo_stats())
            stats["bbo_total"] += int(len(g))

    return {
        "n_bbo": int(sum(int(v["bbo_total"]) for v in venue_stats.values())),
        "grouped_bbo": grouped_bbo,
        "venue_stats": venue_stats,
    }


def _files_for(path_or_glob: str | list[str] | None) -> list[str]:
    if path_or_glob is None:
        return []
    if isinstance(path_or_glob, list):
        files: list[str] = []
        for p in path_or_glob:
            files.extend(_expand_paths(p))
        return sorted(set(files))
    return _expand_paths(path_or_glob)


def _files_for_date_range(root: Path, *, date_from: str | None = None, date_to: str | None = None) -> list[str]:
    if not root.is_dir():
        return []
    from_date = pd.Timestamp(date_from).date() if date_from else None
    to_date = pd.Timestamp(date_to).date() if date_to else None
    files: list[str] = []
    for day_dir in sorted(root.iterdir()):
        if not day_dir.is_dir():
            continue
        try:
            day = pd.Timestamp(day_dir.name).date()
        except Exception:
            files.extend(str(p) for p in sorted(day_dir.rglob("*.parquet")))
            continue
        if from_date and day < from_date:
            continue
        if to_date and day >= to_date:
            continue
        files.extend(str(p) for p in sorted(day_dir.rglob("*.parquet")))
    return files


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


def _complete_meta(meta: dict, analysis_id: str, events: list[dict], quality: dict) -> dict:
    out = dict(meta)
    out.setdefault("analysis_id", analysis_id)
    out.setdefault("recording_id", out.get("collection_id", analysis_id.rsplit("_", 1)[0]))
    out.setdefault("collection_id", out["recording_id"])
    out.setdefault("params_hash", analysis_id.rsplit("_", 1)[-1] if "_" in analysis_id else "")
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
    out.setdefault("source_data_layout_version", ANALYSIS_CONTRACT_VERSION)
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


def _build_quality_from_scans(
    tick_scan: dict[str, Any],
    bbo_scan: dict[str, Any],
    venues: list[str],
    leaders: list[str],
    coverage: dict[str, float],
    sigma: dict[str, float],
    duration_s: float,
    bin_size_ms: int,
) -> dict:
    from leadlag.venues import BBO_UNAVAILABLE_VENUES, REGISTRY

    venue_stats = tick_scan.get("venue_stats", {})
    grouped_bbo = bbo_scan.get("grouped_bbo", pd.DataFrame())
    bbo_stats_by_venue = bbo_scan.get("venue_stats", {})
    grouped_ticks = tick_scan.get("grouped_ticks", pd.DataFrame())

    leader_samples: list[float] = []
    for leader in leaders:
        leader_samples.extend(list(venue_stats.get(leader, {}).get("price_sample", [])))
    leader_median = float(np.median(leader_samples)) if leader_samples else None

    venues_quality = {}
    for venue in venues:
        stats = venue_stats.get(venue, _init_tick_stats())
        ticks_total = int(stats.get("ticks_total", 0))
        bbo = grouped_bbo[grouped_bbo["venue"] == venue] if not grouped_bbo.empty and "venue" in grouped_bbo else pd.DataFrame()
        bbo_total = int(bbo_stats_by_venue.get(venue, {}).get("bbo_total", 0))
        cfg = REGISTRY.get(venue)

        if not grouped_ticks.empty:
            bin_counts = grouped_ticks[grouped_ticks["venue"] == venue]["tick_count"]
        else:
            bin_counts = pd.Series(dtype=float)
        ticks_per_s_max = float((bin_counts.max() / (bin_size_ms / 1000.0))) if len(bin_counts) else 0.0
        ticks_per_s_min = float((bin_counts.min() / (bin_size_ms / 1000.0))) if len(bin_counts) else 0.0

        sample = stats.get("price_sample", [])
        median_price = float(np.median(sample)) if sample else None
        dev = ((median_price - leader_median) / leader_median * 1e4) if median_price and leader_median else None
        side_buy_pct = (float(stats["side_buy_count"]) / ticks_total) if ticks_total else None
        side_sell_pct = (float(stats["side_sell_count"]) / ticks_total) if ticks_total else None
        gaps = list(stats.get("timeline_gaps", []))
        downtime_s = float(sum(g["duration_s"] for g in gaps))
        bbo_stats = _bbo_quality_stats(bbo)
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
            "downtime_s": downtime_s,
            "uptime_pct": max(0.0, 100.0 - (downtime_s / duration_s * 100.0)) if duration_s else 0.0,
            "zero_price_ticks": int(stats.get("zero_price_ticks", 0)),
            "zero_qty_ticks": int(stats.get("zero_qty_ticks", 0)),
            "side_buy_pct": side_buy_pct,
            "side_sell_pct": side_sell_pct,
            "flag": flag,
            "flag_reasons": reasons,
            "sigma": sigma.get(venue),
            **bbo_stats,
        }

    return {
        "duration_s": duration_s,
        "t_start_ms": int(tick_scan.get("t_start_ms", 0)),
        "t_end_ms": int(tick_scan.get("t_end_ms", 0)),
        "coverage_pct": coverage,
        "sigma_per_venue": sigma,
        "venues": venues_quality,
        "timeline_gaps": tick_scan.get("timeline_gaps", []),
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


def _bps_from_t0(values: list, rel: list[int]) -> list[float | None]:
    if not values:
        return []
    idx = next((i for i, x in enumerate(rel) if int(x) == 0), 0)
    base = values[idx] if idx < len(values) else None
    if base in (None, 0):
        base = next((v for v in values if v not in (None, 0)), None)
    if not base:
        return [None for _ in values]
    out = []
    for value in values:
        out.append(None if value is None else (float(value) / float(base) - 1.0) * 1e4)
    return out


def _style_fig(fig, title: str, x_title: str, y_title: str):
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        hovermode="x unified",
        xaxis_title=x_title,
        yaxis_title=y_title,
    )
    return fig
