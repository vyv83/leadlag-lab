"""Follower metrics (lag_50/lag_80/hit/MFE/MAE) + grid search + bootstrap CI.

Ported from analysis_full.txt (Ячейка 4 v2).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_DELAY_GRID_MS = [0, 50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000]
DEFAULT_HOLD_GRID_MS = [100, 200, 500, 1000, 2000, 5000, 10000, 30000]


def compute_metrics(
    events: list[dict],
    vwap_df: pd.DataFrame,
    ema_df: pd.DataFrame,
    follower: str,
    bin_size_ms: int = 50,
    max_horizon_bins: int = 600,
    hit_window_bins: int = 40,
) -> list[dict]:
    fvals = vwap_df[follower].values
    n_bins = len(fvals)
    out: list[dict] = []
    for ev in events:
        if follower not in ev.get("lagging_followers", []):
            continue
        t0 = ev["bin_idx"]
        direction = ev["direction"]
        if t0 >= n_bins or np.isnan(fvals[t0]):
            continue
        p0 = fvals[t0]
        leader_name = _leader_for_metrics(ev, vwap_df)
        if leader_name is None:
            continue
        lvals = vwap_df[leader_name].values
        if t0 >= len(lvals) or np.isnan(lvals[t0]):
            continue
        l_ema0 = ema_df[leader_name].values[t0]
        if np.isnan(l_ema0):
            continue
        leader_move_abs = abs(lvals[t0] - l_ema0)
        if leader_move_abs < 1e-10:
            continue

        lag_50 = lag_80 = None
        mfe = mae = 0.0
        t50, t80 = 0.5 * leader_move_abs, 0.8 * leader_move_abs
        t_hit = t0 + hit_window_bins
        hit = int(direction * (fvals[t_hit] - p0) > 0) if t_hit < n_bins and not np.isnan(fvals[t_hit]) else None

        for t in range(t0 + 1, min(t0 + max_horizon_bins, n_bins)):
            if np.isnan(fvals[t]):
                continue
            move = direction * (fvals[t] - p0)
            if move > mfe:
                mfe = move
            if move < mae:
                mae = move
            if lag_50 is None and move >= t50:
                lag_50 = (t - t0) * bin_size_ms
            if lag_80 is None and move >= t80:
                lag_80 = (t - t0) * bin_size_ms

        out.append({
            "bin_idx": t0, "ts_ms": ev["ts_ms"], "signal": ev["signal"],
            "direction": direction, "follower": follower,
            "lag_50_ms": lag_50, "lag_80_ms": lag_80, "hit": hit,
            "mfe_bps": mfe / p0 * 10000, "mae_bps": mae / p0 * 10000,
            "leader_move_bps": leader_move_abs / lvals[t0] * 10000,
        })
    return out


def _leader_for_metrics(ev: dict, vwap_df: pd.DataFrame) -> str | None:
    if ev.get("leader") and ev.get("leader") != "confirmed":
        return ev["leader"]
    if ev.get("anchor_leader") in vwap_df.columns:
        return ev["anchor_leader"]
    confirmer = ev.get("confirmer_leader")
    if confirmer == "OKX Perp" and "Bybit Perp" in vwap_df.columns:
        return "Bybit Perp"
    if confirmer == "Bybit Perp" and "OKX Perp" in vwap_df.columns:
        return "OKX Perp"
    for candidate in ("OKX Perp", "Bybit Perp"):
        if candidate in vwap_df.columns:
            return candidate
    return None


def grid_search(
    events: list[dict],
    vwap_df: pd.DataFrame,
    followers: list[str],
    fees_bps: dict[str, float],
    signals: tuple[str, ...] = ("A", "B", "C"),
    delay_grid_ms: list[int] | None = None,
    hold_grid_ms: list[int] | None = None,
    bin_size_ms: int = 50,
) -> pd.DataFrame:
    delay_grid_ms = delay_grid_ms or DEFAULT_DELAY_GRID_MS
    hold_grid_ms = hold_grid_ms or DEFAULT_HOLD_GRID_MS
    rows: list[dict] = []
    for sig in signals:
        ev_list = [e for e in events if e["signal"] == sig]
        for fol in followers:
            fee = fees_bps.get(fol, 0.0)
            fvals = vwap_df[fol].values
            n = len(fvals)
            for ev in ev_list:
                if fol not in ev.get("lagging_followers", []):
                    continue
                t0, direction = ev["bin_idx"], ev["direction"]
                for d_ms in delay_grid_ms:
                    t_e = t0 + d_ms // bin_size_ms
                    if t_e >= n or np.isnan(fvals[t_e]):
                        continue
                    pe = fvals[t_e]
                    for h_ms in hold_grid_ms:
                        t_x = t_e + h_ms // bin_size_ms
                        if t_x >= n or np.isnan(fvals[t_x]):
                            continue
                        gross = direction * (fvals[t_x] - pe) / pe * 10000
                        rows.append({
                            "delay_ms": d_ms, "hold_ms": h_ms,
                            "gross_pnl_bps": gross,
                            "net_pnl_bps": gross - 2 * fee,
                            "hit": 1 if gross > 0 else 0,
                            "signal": sig, "follower": fol, "bin_idx": t0,
                        })
    return pd.DataFrame(rows)


def bootstrap_ci(vals, n_iter: int = 1000, seed: int | None = 42):
    rng = np.random.default_rng(seed)
    vals = np.asarray(vals)
    vals = vals[~np.isnan(vals)]
    if len(vals) < 3:
        return np.nan, np.nan, np.nan
    means = [float(rng.choice(vals, size=len(vals), replace=True).mean()) for _ in range(n_iter)]
    return float(vals.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))
