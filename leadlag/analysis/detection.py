"""Event detection: first-crossing threshold + clustering + A/B/C classification.

Ported from analysis_full.txt (Ячейка 3, v3 detector).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def detect_events(
    leader: str,
    followers: list[str],
    dev_df: pd.DataFrame,
    t_start: int,
    bin_size_ms: int = 50,
    threshold: float = 2.0,
    follower_max_dev: float = 0.5,
    ema_span_bins: int = 200,
    detection_window_bins: int = 10,
) -> list[dict]:
    """Catch the FIRST bin where |leader_dev| >= threshold (not-above -> above).

    A follower is "lagging" if its max excursion in the signal direction over
    the last `detection_window_bins` bins is below `follower_max_dev` sigma.
    """
    leader_dev = dev_df[leader].values
    n = len(leader_dev)
    events: list[dict] = []
    was_above = False

    for t in range(ema_span_bins * 2, n):
        if np.isnan(leader_dev[t]):
            was_above = False
            continue
        is_above = abs(leader_dev[t]) >= threshold

        if is_above and not was_above:
            direction = 1 if leader_dev[t] > 0 else -1
            magnitude = abs(leader_dev[t])
            lagging: list[str] = []

            for fol in followers:
                fvals = dev_df[fol].values
                if t >= len(fvals) or np.isnan(fvals[t]):
                    continue
                win_start = max(0, t - detection_window_bins)
                window = fvals[win_start:t + 1]
                window = window[~np.isnan(window)]
                if len(window) == 0:
                    continue
                if direction > 0:
                    fol_max_in_dir = max(0.0, float(window.max()))
                else:
                    fol_max_in_dir = max(0.0, -float(window.min()))
                if fol_max_in_dir < follower_max_dev:
                    lagging.append(fol)

            if lagging:
                events.append({
                    "bin_idx": int(t),
                    "ts_ms": int(t_start + t * bin_size_ms),
                    "direction": int(direction),
                    "magnitude_sigma": float(magnitude),
                    "leader": leader,
                    "leader_dev": float(leader_dev[t]),
                    "lagging_followers": list(lagging),
                    "n_lagging": len(lagging),
                })

        was_above = is_above

    return events


def cluster_events_first(events: list[dict], gap_bins: int = 60) -> list[dict]:
    if not events:
        return []
    sorted_ev = sorted(events, key=lambda e: e["bin_idx"])
    clusters, current = [], [sorted_ev[0]]
    for ev in sorted_ev[1:]:
        if ev["bin_idx"] - current[-1]["bin_idx"] <= gap_bins:
            current.append(ev)
        else:
            clusters.append(current)
            current = [ev]
    clusters.append(current)
    return [cl[0] for cl in clusters]


def classify_signals(
    clustered_by_leader: dict[str, list[dict]],
    bin_size_ms: int = 50,
    confirm_window_bins: int = 10,
    anchor_leader_fallback: str = "OKX Perp",
) -> list[dict]:
    """Split events into Signal A (OKX solo), B (Bybit solo), C (dual-confirmed).

    Signal C takes `lagging_followers` from the ANCHOR (earlier leader), because
    by the time the confirmer fires, followers may have already reacted.
    A/B events that overlap a C cluster are removed.
    """
    okx_events = clustered_by_leader.get("OKX Perp", [])
    bybit_events = clustered_by_leader.get("Bybit Perp", [])

    signal_a = [dict(e, signal="A", anchor_leader=e.get("leader")) for e in okx_events]
    signal_b = [dict(e, signal="B", anchor_leader=e.get("leader")) for e in bybit_events]

    signal_c: list[dict] = []
    used_bybit: set[int] = set()

    for ev_o in okx_events:
        for j, ev_b in enumerate(bybit_events):
            if j in used_bybit:
                continue
            if (abs(ev_o["bin_idx"] - ev_b["bin_idx"]) <= confirm_window_bins
                    and ev_o["direction"] == ev_b["direction"]):
                anchor = ev_o if ev_o["bin_idx"] <= ev_b["bin_idx"] else ev_b
                confirmer = ev_b if ev_o["bin_idx"] <= ev_b["bin_idx"] else ev_o
                if not anchor["lagging_followers"]:
                    used_bybit.add(j)
                    break
                signal_c.append(dict(
                    anchor,
                    signal="C",
                    magnitude_sigma=max(anchor["magnitude_sigma"], confirmer["magnitude_sigma"]),
                    leader="confirmed",
                    anchor_leader=anchor["leader"],
                    confirmer_leader=confirmer["leader"],
                    confirmer_bin=confirmer["bin_idx"],
                    confirmer_lag_ms=(confirmer["bin_idx"] - anchor["bin_idx"]) * bin_size_ms,
                    lagging_followers=list(anchor["lagging_followers"]),
                    n_lagging=len(anchor["lagging_followers"]),
                ))
                used_bybit.add(j)
                break

    # Collect bin indices absorbed by C so we can drop overlapping A/B.
    c_bins: set[int] = set()
    for ev_c in signal_c:
        t0, d = ev_c["bin_idx"], ev_c["direction"]
        c_bins.add(t0)
        for ev_o in okx_events:
            if abs(ev_o["bin_idx"] - t0) <= confirm_window_bins and ev_o["direction"] == d:
                c_bins.add(ev_o["bin_idx"])
        for ev_b in bybit_events:
            if abs(ev_b["bin_idx"] - t0) <= confirm_window_bins and ev_b["direction"] == d:
                c_bins.add(ev_b["bin_idx"])

    a_clean = [e for e in signal_a if e["bin_idx"] not in c_bins]
    b_clean = [e for e in signal_b if e["bin_idx"] not in c_bins]
    return a_clean + b_clean + signal_c
