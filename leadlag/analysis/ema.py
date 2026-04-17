"""EMA baseline + per-venue deviation in sigma units.

Ported from analysis_full.txt (Ячейка 3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_ema(vwap_df: pd.DataFrame, venues: list[str], ema_span_bins: int = 200) -> pd.DataFrame:
    ema = {}
    for v in venues:
        ema[v] = vwap_df[v].ewm(span=ema_span_bins, adjust=False, min_periods=ema_span_bins).mean()
    return pd.DataFrame(ema)


def compute_deviation(
    vwap_df: pd.DataFrame,
    ema_df: pd.DataFrame,
    venues: list[str],
    ema_span_bins: int = 200,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Deviation in units of sigma: (vwap - ema) / (sigma_ema * vwap).

    sigma_ema is log-return std scaled by sqrt(ema_span_bins).
    """
    sigma = {}
    for v in venues:
        lr = np.log(vwap_df[v] / vwap_df[v].shift(1)).dropna()
        sigma[v] = float(lr.std() * np.sqrt(ema_span_bins)) if len(lr) else 0.0

    dev = {}
    for v in venues:
        s = sigma[v]
        if s > 0:
            dev[v] = (vwap_df[v] - ema_df[v]) / (s * vwap_df[v])
        else:
            dev[v] = pd.Series(0.0, index=vwap_df.index)
    return pd.DataFrame(dev), sigma
