"""50ms VWAP binning with ffill.

Ported from analysis_full.txt (Ячейка 2).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def bin_to_vwap(
    df_ticks: pd.DataFrame,
    venues: list[str],
    bin_size_ms: int = 50,
) -> tuple[pd.DataFrame, int, dict[str, float]]:
    """Bin raw ticks into per-venue VWAP time series.

    Returns:
        vwap_df: index=bin_idx, columns=venues (+ ts_ms + {leader}_logret added later)
        t_start: ms timestamp of bin 0
        raw_coverage: venue -> % of bins with at least one tick (pre-ffill)
    """
    df = df_ticks.copy()
    t_start = int(df["ts_ms"].min())
    t_end = int(df["ts_ms"].max())
    n_bins = int((t_end - t_start) / bin_size_ms) + 1

    df["bin_idx"] = ((df["ts_ms"] - t_start) // bin_size_ms).astype(int)
    df["pv"] = df["price"] * df["qty"]

    grouped = (
        df.groupby(["venue", "bin_idx"])
        .agg(vwap_num=("pv", "sum"), vwap_den=("qty", "sum"), tick_count=("price", "count"))
        .reset_index()
    )
    grouped["vwap"] = grouped["vwap_num"] / grouped["vwap_den"]

    vwap_dict: dict[str, pd.Series] = {}
    raw_coverage: dict[str, float] = {}
    for venue in venues:
        sub = grouped[grouped["venue"] == venue][["bin_idx", "vwap"]].set_index("bin_idx")["vwap"]
        series = pd.Series(index=range(n_bins), dtype=float)
        series.loc[sub.index] = sub.values
        vwap_dict[venue] = series.ffill()
        raw_coverage[venue] = len(sub) / n_bins * 100 if n_bins else 0.0

    vwap_df = pd.DataFrame(vwap_dict)
    vwap_df.index.name = "bin_idx"
    vwap_df["ts_ms"] = t_start + vwap_df.index * bin_size_ms
    return vwap_df, t_start, raw_coverage
