"""Event-driven backtest engine.

Consumes a Session (with vwap_df, optional bbo_df) and a Strategy, simulates
market or limit entries, walks forward bin-by-bin to resolve SL/TP/hold exits,
and emits a BacktestResult conforming to plan.md §contract 5.

Key behaviours:
  - Position modes: 'reject' | 'stack' | 'reverse'
  - Slippage models: none | fixed | half_spread | full_spread (with fixed fallback)
  - Fees: market = taker×2, limit = maker+taker (close at market)
  - Limit fills: must touch limit_price within LIMIT_FILL_WINDOW_PCT of hold_ms
  - MFE/MAE tracked in bps relative to exec entry price
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from leadlag.backtest.slippage import compute_slippage_bps
from leadlag.strategy import BboSnapshot, Context, Event, Order, Strategy
from leadlag.venues.config import BBO_UNAVAILABLE_VENUES, REGISTRY


LIMIT_FILL_WINDOW_PCT = 0.30
SPREAD_BUCKETS_BPS = [0.5, 1.0, 2.0, 5.0]


@dataclass
class BacktestResult:
    strategy_name: str
    session_id: str
    params: dict
    trades: list[dict]
    equity: list[dict]
    stats: dict
    meta: dict = field(default_factory=dict)

    def save(self, data_dir: Path | str = "data") -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = Path(data_dir) / "backtest" / f"{self.strategy_name}_{ts}"
        out.mkdir(parents=True, exist_ok=True)
        (out / "meta.json").write_text(json.dumps({**self.meta, "params": self.params,
                                                    "strategy_name": self.strategy_name,
                                                    "session_id": self.session_id,
                                                    "created_at": ts}, indent=2))
        (out / "trades.json").write_text(json.dumps(self.trades))
        (out / "equity.json").write_text(json.dumps(self.equity))
        (out / "stats.json").write_text(json.dumps(self.stats, indent=2))
        return out

    def plot_equity(self, layers: bool = False):
        """Minimal renderer — returns a DataFrame suitable for notebook display."""
        df = pd.DataFrame(self.equity)
        if df.empty:
            return df
        cols = ["ts_ms", "net_equity_bps"]
        if layers:
            cols = ["ts_ms", "gross_equity_bps", "post_fee_equity_bps", "net_equity_bps", "drawdown_bps"]
        return df[cols]


def run_backtest(
    strategy: Strategy,
    session,
    params_override: Optional[dict] = None,
    data_dir: Path | str = "data",
) -> BacktestResult:
    if session.vwap_df is None:
        raise ValueError("Session has no vwap_df; use Session.build_from_raw() or attach vwap_df before backtesting.")

    params = {**getattr(strategy, "params", {}), **(params_override or {})}
    strategy.params = params
    bin_size_ms = int(session.params.get("bin_size_ms", 50))
    t_start_ms = int(session.quality.get("t_start_ms") or session.meta.get("t_start_ms") or 0)

    vwap_df = session.vwap_df
    bbo_lookup = _BboLookup(session.bbo_df)

    events_sorted = sorted(session.events.rows, key=lambda e: e["bin_idx"])

    position_mode = getattr(strategy, "position_mode", params.get("position_mode", "reject"))
    slippage_model = params.get("slippage_model", getattr(strategy, "slippage_model", "half_spread"))
    fixed_slippage = float(params.get("fixed_slippage_bps", getattr(strategy, "fixed_slippage_bps", 1.0)))

    open_positions: dict[str, list[dict]] = {}  # venue -> list of {exit_bin_idx, side}
    trades: list[dict] = []
    trade_id = 0

    for ev_row in events_sorted:
        ev = _to_event(ev_row)
        bbo_ctx = _bbo_context_at(bbo_lookup, ev.ts_ms)
        ctx = Context(ts_ms=ev.ts_ms, bbo=bbo_ctx, positions=dict(open_positions), params=params)

        order = strategy.on_event(ev, ctx)
        if order is None:
            continue
        if order.venue not in vwap_df.columns:
            continue

        # Position management.
        open_on_venue = open_positions.get(order.venue, [])
        if open_on_venue:
            if position_mode == "reject":
                continue
            if position_mode == "reverse":
                same_dir = any(p["side"] == order.side for p in open_on_venue)
                if same_dir:
                    continue
                open_positions[order.venue] = []  # close immediately (modeled as skip — spec allows)
            # 'stack' → just append

        trade = _simulate_trade(
            trade_id=trade_id,
            event=ev,
            order=order,
            vwap_df=vwap_df,
            bbo_lookup=bbo_lookup,
            bin_size_ms=bin_size_ms,
            slippage_model=slippage_model,
            fixed_slippage_bps=fixed_slippage,
        )
        if trade is None:
            continue

        trades.append(trade)
        open_positions.setdefault(order.venue, []).append({
            "exit_bin_idx": trade["_exit_bin_idx"],
            "side": order.side,
        })
        # Purge expired.
        for v, lst in list(open_positions.items()):
            open_positions[v] = [p for p in lst if p["exit_bin_idx"] > ev.bin_idx]
        trade_id += 1

    for t in trades:
        t.pop("_exit_bin_idx", None)

    equity = _build_equity(trades)
    stats = _build_stats(trades, equity, params)

    meta = {
        "strategy_description": getattr(strategy, "description", ""),
        "params_override": params_override or {},
        "slippage_model": slippage_model,
        "position_mode": position_mode,
    }
    return BacktestResult(
        strategy_name=getattr(strategy, "name", strategy.__class__.__name__),
        session_id=session.session_id,
        params=params,
        trades=trades,
        equity=equity,
        stats=stats,
        meta=meta,
    )


# ─── internals ───

class _BboLookup:
    """Per-venue sorted BBO frames with binary-search lookup by ts_ms."""

    def __init__(self, bbo_df: Optional[pd.DataFrame]):
        self.per_venue: dict[str, pd.DataFrame] = {}
        if bbo_df is None or len(bbo_df) == 0:
            return
        for venue, g in bbo_df.groupby("venue"):
            g = g.sort_values("ts_ms").reset_index(drop=True)
            self.per_venue[venue] = g

    def at(self, venue: str, ts_ms: int) -> Optional[dict]:
        g = self.per_venue.get(venue)
        if g is None or len(g) == 0:
            return None
        i = int(np.searchsorted(g["ts_ms"].values, ts_ms, side="right")) - 1
        if i < 0:
            return None
        r = g.iloc[i]
        bid, ask = float(r["bid_price"]), float(r["ask_price"])
        if not (bid > 0 and ask > 0):
            return None
        mid = 0.5 * (bid + ask)
        spread_bps = (ask - bid) / mid * 1e4 if mid > 0 else None
        return {
            "bid_price": bid, "ask_price": ask,
            "bid_qty": float(r.get("bid_qty", 0.0)), "ask_qty": float(r.get("ask_qty", 0.0)),
            "spread_bps": spread_bps,
        }


def _bbo_context_at(lookup: _BboLookup, ts_ms: int) -> dict[str, BboSnapshot]:
    out: dict[str, BboSnapshot] = {}
    for venue in REGISTRY:
        if venue in BBO_UNAVAILABLE_VENUES:
            out[venue] = BboSnapshot(venue=venue, available=False)
            continue
        snap = lookup.at(venue, ts_ms)
        if snap is None:
            out[venue] = BboSnapshot(venue=venue, available=False)
        else:
            out[venue] = BboSnapshot(venue=venue, available=True, **snap)
    return out


def _to_event(row: dict) -> Event:
    return Event(
        bin_idx=int(row["bin_idx"]),
        ts_ms=int(row.get("ts_ms", 0)),
        signal=row.get("signal", ""),
        direction=int(row.get("direction", 0)),
        magnitude_sigma=float(row.get("magnitude_sigma", 0.0)),
        leader=row.get("leader", ""),
        lagging_followers=list(row.get("lagging_followers", [])),
        follower_metrics=row.get("follower_metrics", {}),
        extra={k: v for k, v in row.items() if k not in {
            "bin_idx", "ts_ms", "signal", "direction", "magnitude_sigma",
            "leader", "lagging_followers", "follower_metrics",
        }},
    )


def _simulate_trade(
    trade_id: int,
    event: Event,
    order: Order,
    vwap_df: pd.DataFrame,
    bbo_lookup: _BboLookup,
    bin_size_ms: int,
    slippage_model: str,
    fixed_slippage_bps: float,
) -> Optional[dict]:
    venue = order.venue
    sign = 1 if order.side == "buy" else -1
    hold_ms = int(order.hold_ms or 30000)
    hold_bins = max(1, hold_ms // bin_size_ms)
    delay_bins = max(0, int(order.delay_ms or 0) // bin_size_ms)

    entry_bin = event.bin_idx + delay_bins
    if entry_bin >= len(vwap_df):
        return None
    entry_ts_ms = int(vwap_df["ts_ms"].iloc[entry_bin]) if "ts_ms" in vwap_df.columns else event.ts_ms + delay_bins * bin_size_ms

    cfg = REGISTRY.get(venue)
    taker = float(cfg.taker_fee_bps if cfg else 5.0)
    maker = float(cfg.maker_fee_bps if cfg else 2.0)

    bbo_entry = bbo_lookup.at(venue, entry_ts_ms)
    bbo_available = (venue not in BBO_UNAVAILABLE_VENUES) and (bbo_entry is not None)
    spread_entry = bbo_entry["spread_bps"] if bbo_entry else None

    is_limit = order.entry_type == "limit"
    if is_limit:
        entry_price_vwap = float(vwap_df[venue].iloc[entry_bin])
        limit_price = order.limit_price if order.limit_price is not None else entry_price_vwap
        fill_window = max(1, int(hold_bins * LIMIT_FILL_WINDOW_PCT))
        fill_bin = None
        for b in range(entry_bin, min(entry_bin + fill_window, len(vwap_df))):
            p = float(vwap_df[venue].iloc[b])
            if (sign > 0 and p <= limit_price) or (sign < 0 and p >= limit_price):
                fill_bin = b
                break
        if fill_bin is None:
            return None
        entry_bin = fill_bin
        entry_price_vwap = limit_price
        entry_price_exec = limit_price
        slippage_entry_bps, slip_src_entry = 0.0, "none"
        fee_entry = maker
        fee_type = "maker"
    else:
        entry_price_vwap = float(vwap_df[venue].iloc[entry_bin])
        slippage_entry_bps, slip_src_entry = compute_slippage_bps(
            slippage_model, spread_entry, bbo_available, fixed_slippage_bps,
        )
        entry_price_exec = entry_price_vwap * (1 + sign * slippage_entry_bps / 1e4)
        fee_entry = taker
        fee_type = "taker"

    # Walk forward, resolve SL/TP/hold.
    sl = order.stop_loss_bps
    tp = order.take_profit_bps
    exit_bin = min(entry_bin + hold_bins, len(vwap_df) - 1)
    exit_reason = "hold_expired"
    mfe_bps, mae_bps = 0.0, 0.0
    mfe_time_ms, mae_time_ms = 0, 0

    for b in range(entry_bin + 1, min(entry_bin + hold_bins + 1, len(vwap_df))):
        p = float(vwap_df[venue].iloc[b])
        pnl_bps = sign * (p / entry_price_exec - 1.0) * 1e4
        dt_ms = (b - entry_bin) * bin_size_ms
        if pnl_bps > mfe_bps:
            mfe_bps, mfe_time_ms = pnl_bps, dt_ms
        if pnl_bps < mae_bps:
            mae_bps, mae_time_ms = pnl_bps, dt_ms
        if sl is not None and pnl_bps <= -abs(sl):
            exit_bin, exit_reason = b, "stop_loss"
            break
        if tp is not None and pnl_bps >= abs(tp):
            exit_bin, exit_reason = b, "take_profit"
            break

    exit_price_vwap = float(vwap_df[venue].iloc[exit_bin])
    exit_ts_ms = int(vwap_df["ts_ms"].iloc[exit_bin]) if "ts_ms" in vwap_df.columns else entry_ts_ms + (exit_bin - entry_bin) * bin_size_ms

    bbo_exit = bbo_lookup.at(venue, exit_ts_ms)
    spread_exit = bbo_exit["spread_bps"] if bbo_exit else None
    slippage_exit_bps, slip_src_exit = compute_slippage_bps(
        slippage_model, spread_exit, bbo_exit is not None and venue not in BBO_UNAVAILABLE_VENUES, fixed_slippage_bps,
    )
    exit_price_exec = exit_price_vwap * (1 - sign * slippage_exit_bps / 1e4)
    fee_exit = taker  # always close at market

    gross_pnl_bps = sign * (exit_price_vwap / entry_price_vwap - 1.0) * 1e4
    fee_total = fee_entry + fee_exit
    slip_total = slippage_entry_bps + slippage_exit_bps
    net_pnl_bps = sign * (exit_price_exec / entry_price_exec - 1.0) * 1e4 - fee_total

    return {
        "trade_id": trade_id,
        "signal_bin_idx": event.bin_idx,
        "signal_type": event.signal,
        "direction": event.direction,
        "magnitude_sigma": event.magnitude_sigma,
        "venue": venue,
        "side": order.side,
        "entry_type": order.entry_type,
        "entry_ts_ms": entry_ts_ms,
        "exit_ts_ms": exit_ts_ms,
        "entry_price_vwap": entry_price_vwap,
        "exit_price_vwap": exit_price_vwap,
        "entry_price_exec": entry_price_exec,
        "exit_price_exec": exit_price_exec,
        "slippage_entry_bps": slippage_entry_bps,
        "slippage_exit_bps": slippage_exit_bps,
        "slippage_total_bps": slip_total,
        "slippage_source": slip_src_entry,
        "spread_at_entry_bps": spread_entry,
        "spread_at_exit_bps": spread_exit,
        "gross_pnl_bps": gross_pnl_bps,
        "fee_entry_bps": fee_entry,
        "fee_exit_bps": fee_exit,
        "fee_total_bps": fee_total,
        "fee_type": fee_type,
        "net_pnl_bps": net_pnl_bps,
        "hold_ms": (exit_bin - entry_bin) * bin_size_ms,
        "exit_reason": exit_reason,
        "mfe_bps": mfe_bps,
        "mae_bps": mae_bps,
        "mfe_time_ms": mfe_time_ms,
        "mae_time_ms": mae_time_ms,
        "bbo_spread_at_entry_bps": spread_entry,
        "bbo_spread_at_exit_bps": spread_exit,
        "bbo_available": bbo_available,
        "n_lagging_at_signal": len(event.lagging_followers),
        "leader_dev_sigma": event.extra.get("leader_dev_sigma"),
        "_exit_bin_idx": exit_bin,
    }


def _build_equity(trades: list[dict]) -> list[dict]:
    rows: list[dict] = []
    gross, post_fee, net, peak = 0.0, 0.0, 0.0, 0.0
    for t in sorted(trades, key=lambda x: x["exit_ts_ms"]):
        gross += t["gross_pnl_bps"]
        post_fee += t["gross_pnl_bps"] - t["fee_total_bps"]
        net += t["net_pnl_bps"]
        peak = max(peak, net)
        rows.append({
            "ts_ms": t["exit_ts_ms"],
            "gross_equity_bps": gross,
            "post_fee_equity_bps": post_fee,
            "net_equity_bps": net,
            "drawdown_bps": net - peak,
            "trade_id": t["trade_id"],
        })
    return rows


def _build_stats(trades: list[dict], equity: list[dict], params: dict) -> dict:
    if not trades:
        return {"n_trades": 0}
    df = pd.DataFrame(trades)
    net = df["net_pnl_bps"]
    wins = (net > 0).sum()
    stats = {
        "n_trades": len(df),
        "win_rate": float(wins / len(df)),
        "total_net_pnl_bps": float(net.sum()),
        "total_gross_pnl_bps": float(df["gross_pnl_bps"].sum()),
        "total_fee_bps": float(df["fee_total_bps"].sum()),
        "total_slippage_bps": float(df["slippage_total_bps"].sum()),
        "avg_trade_bps": float(net.mean()),
        "median_trade_bps": float(net.median()),
        "std_trade_bps": float(net.std(ddof=0)),
        "sharpe": float(net.mean() / net.std(ddof=0)) if net.std(ddof=0) > 0 else 0.0,
        "max_drawdown_bps": float(min((e["drawdown_bps"] for e in equity), default=0.0)),
        "fee_impact": {
            "gross_bps": float(df["gross_pnl_bps"].sum()),
            "fees_bps": float(df["fee_total_bps"].sum()),
            "slippage_bps": float(df["slippage_total_bps"].sum()),
            "net_bps": float(net.sum()),
        },
        "by_entry_type": _by_group(df, "entry_type"),
        "by_exit_reason": _by_group(df, "exit_reason"),
        "by_venue": _by_group(df, "venue"),
        "by_spread_bucket": _by_spread_bucket(df),
    }
    if "entry_type" in df.columns and (df["entry_type"] == "limit").any():
        # Fill rate proxy: included limit trades / attempted (we only record filled; log attempts?)
        stats["by_entry_type"].setdefault("limit", {})["avg_slippage_bps"] = 0.0
    return stats


def _by_group(df: pd.DataFrame, col: str) -> dict:
    out = {}
    for key, g in df.groupby(col):
        out[str(key)] = {
            "n": int(len(g)),
            "win_rate": float((g["net_pnl_bps"] > 0).mean()),
            "avg_pnl_bps": float(g["net_pnl_bps"].mean()),
            "avg_fee_bps": float(g["fee_total_bps"].mean()),
            "avg_slippage_bps": float(g["slippage_total_bps"].mean()),
        }
    return out


def _by_spread_bucket(df: pd.DataFrame) -> dict:
    if "spread_at_entry_bps" not in df.columns:
        return {}
    out = {}
    buckets = SPREAD_BUCKETS_BPS
    s = df["spread_at_entry_bps"]
    mask_na = s.isna()
    if mask_na.any():
        g = df[mask_na]
        out["no_bbo"] = {"n": int(len(g)), "avg_pnl_bps": float(g["net_pnl_bps"].mean())}
    prev = 0.0
    for hi in buckets:
        g = df[(~mask_na) & (s > prev) & (s <= hi)]
        if len(g):
            out[f"<= {hi} bps"] = {"n": int(len(g)), "avg_pnl_bps": float(g["net_pnl_bps"].mean())}
        prev = hi
    g = df[(~mask_na) & (s > prev)]
    if len(g):
        out[f"> {prev} bps"] = {"n": int(len(g)), "avg_pnl_bps": float(g["net_pnl_bps"].mean())}
    return out
