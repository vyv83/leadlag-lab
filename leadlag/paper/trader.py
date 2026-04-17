"""Paper trader orchestrator.

Feed it live ticks (`feed_tick`) and BBO updates (`feed_bbo`); it runs the
realtime detector, invokes `strategy.on_event`, simulates entry at the BBO
mid (adjusted for slippage model), and schedules exits on hold_ms / SL / TP.

All outputs go to `data/paper/{name}/`:
  - config.json    — strategy name, started_at, venues, position_mode
  - signals.jsonl  — one line per detected event (trade or skip + reason)
  - trades.jsonl   — one line per closed trade (full contract 5 shape)
  - equity.jsonl   — cumulative PnL snapshot at each close
  - positions.json — currently open positions (rewritten on change)
  - .paper_status.json (at data/.paper_status.json) — atomic status file
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from leadlag.backtest.slippage import compute_slippage_bps
from leadlag.realtime.bbo_tracker import BboTracker
from leadlag.realtime.detector import RealtimeDetector
from leadlag.strategy import Context, Event, Order, Strategy
from leadlag.venues.config import BBO_UNAVAILABLE_VENUES, REGISTRY


@dataclass
class _OpenPosition:
    trade_id: int
    venue: str
    side: str
    entry_ts_ms: int
    entry_price_exec: float
    entry_price_vwap: float
    qty_btc: float
    hold_ms: int
    stop_loss_bps: Optional[float]
    take_profit_bps: Optional[float]
    slippage_entry_bps: float
    slippage_source_entry: str
    spread_at_entry_bps: Optional[float]
    bbo_available: bool
    fee_type: str
    fee_entry_bps: float
    signal_bin_idx: int
    signal_type: str
    direction: int
    magnitude_sigma: float
    n_lagging: int
    mfe_bps: float = 0.0
    mae_bps: float = 0.0
    mfe_time_ms: int = 0
    mae_time_ms: int = 0


class PaperTrader:
    def __init__(
        self,
        strategy: Strategy,
        leaders: list[str],
        followers: list[str],
        *,
        session_start_ms: Optional[int] = None,
        bin_size_ms: int = 50,
        ema_span: int = 200,
        threshold_sigma: float = 2.0,
        follower_max_dev: float = 0.5,
        data_dir: Path | str = "data",
    ):
        self.strategy = strategy
        self.bbo = BboTracker()
        self.detector = RealtimeDetector(
            leaders, followers,
            session_start_ms=session_start_ms if session_start_ms is not None else int(time.time() * 1000),
            bin_size_ms=bin_size_ms, ema_span=ema_span,
            threshold_sigma=threshold_sigma, follower_max_dev=follower_max_dev,
            on_event=self._handle_event,
        )
        self.data_dir = Path(data_dir)
        self.name = getattr(strategy, "name", strategy.__class__.__name__)
        self.out_dir = self.data_dir / "paper" / self.name
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._trade_id = 0
        self.open: dict[str, list[_OpenPosition]] = {}
        self.cumulative_pnl_bps = 0.0
        self.started_at_ms = int(time.time() * 1000)
        self._write_config(leaders + followers)

    # ─── inputs ───

    def feed_tick(self, venue: str, ts_ms: int, price: float, qty: float) -> None:
        self._check_exits(ts_ms)
        self.detector.on_tick(venue, ts_ms, price, qty)
        self._track_mfe_mae(venue, ts_ms, price)

    def feed_bbo(self, venue: str, ts_ms: int, bid: float, ask: float,
                 bid_qty: float = 0.0, ask_qty: float = 0.0) -> None:
        self.bbo.update(venue, ts_ms, bid, ask, bid_qty, ask_qty)

    # ─── event handling ───

    def _handle_event(self, ev: Event) -> None:
        bbo_ctx = self.bbo.all(now_ms=ev.ts_ms)
        ctx = Context(ts_ms=ev.ts_ms, bbo=bbo_ctx,
                      positions={v: [asdict(p) for p in lst] for v, lst in self.open.items()},
                      params=self.strategy.params)
        order: Optional[Order] = None
        try:
            order = self.strategy.on_event(ev, ctx)
        except Exception as e:
            self._append_signal(ev, action="error", error=f"{type(e).__name__}: {e}")
            return

        if order is None:
            self._append_signal(ev, action="skip", skip_reason="strategy_returned_none")
            return

        position_mode = getattr(self.strategy, "position_mode",
                                 self.strategy.params.get("position_mode", "reject"))
        if self.open.get(order.venue):
            if position_mode == "reject":
                self._append_signal(ev, action="skip", skip_reason="position_already_open", order=order)
                return

        self._open_position(ev, order, bbo_ctx)

    def _open_position(self, ev: Event, order: Order, bbo_ctx: dict) -> None:
        snap = bbo_ctx.get(order.venue)
        spread = snap.spread_bps if snap and snap.available else None
        avail = bool(snap and snap.available)
        slip_model = self.strategy.params.get("slippage_model",
                                               getattr(self.strategy, "slippage_model", "half_spread"))
        fixed = float(self.strategy.params.get("fixed_slippage_bps",
                                                getattr(self.strategy, "fixed_slippage_bps", 1.0)))
        slip_bps, slip_src = compute_slippage_bps(slip_model, spread, avail, fixed)
        sign = 1 if order.side == "buy" else -1
        mid = None
        if snap and snap.available:
            mid = 0.5 * (snap.bid_price + snap.ask_price)
        if mid is None:
            lp = self.detector.buffers[order.venue].last_finalized
            mid = lp[1] if lp else None
        if mid is None:
            self._append_signal(ev, action="skip", skip_reason="no_reference_price", order=order)
            return
        entry_exec = mid * (1 + sign * slip_bps / 1e4)
        cfg = REGISTRY.get(order.venue)
        taker = float(cfg.taker_fee_bps) if cfg else 5.0
        maker = float(cfg.maker_fee_bps) if cfg else 2.0
        is_limit = order.entry_type == "limit"
        fee_entry = maker if is_limit else taker
        fee_type = "maker" if is_limit else "taker"
        pos = _OpenPosition(
            trade_id=self._trade_id, venue=order.venue, side=order.side,
            entry_ts_ms=ev.ts_ms, entry_price_exec=entry_exec, entry_price_vwap=mid,
            qty_btc=order.qty_btc, hold_ms=int(order.hold_ms or 30000),
            stop_loss_bps=order.stop_loss_bps, take_profit_bps=order.take_profit_bps,
            slippage_entry_bps=slip_bps, slippage_source_entry=slip_src,
            spread_at_entry_bps=spread, bbo_available=avail,
            fee_type=fee_type, fee_entry_bps=fee_entry,
            signal_bin_idx=ev.bin_idx, signal_type=ev.signal,
            direction=ev.direction, magnitude_sigma=ev.magnitude_sigma,
            n_lagging=len(ev.lagging_followers),
        )
        self._trade_id += 1
        self.open.setdefault(order.venue, []).append(pos)
        self._append_signal(ev, action="trade", order=order, spread_at_signal_bps=spread,
                            bbo_available=avail)
        self._write_positions()
        self._write_status()

    def _track_mfe_mae(self, venue: str, ts_ms: int, price: float) -> None:
        for p in self.open.get(venue, []):
            sign = 1 if p.side == "buy" else -1
            pnl_bps = sign * (price / p.entry_price_exec - 1.0) * 1e4
            dt = ts_ms - p.entry_ts_ms
            if pnl_bps > p.mfe_bps:
                p.mfe_bps, p.mfe_time_ms = pnl_bps, dt
            if pnl_bps < p.mae_bps:
                p.mae_bps, p.mae_time_ms = pnl_bps, dt

    def _check_exits(self, now_ms: int) -> None:
        for venue, lst in list(self.open.items()):
            keep: list[_OpenPosition] = []
            for p in lst:
                sign = 1 if p.side == "buy" else -1
                last = self.detector.buffers[venue].last_finalized
                price_ref = last[1] if last else p.entry_price_exec
                pnl_bps = sign * (price_ref / p.entry_price_exec - 1.0) * 1e4
                exit_reason = None
                if p.stop_loss_bps is not None and pnl_bps <= -abs(p.stop_loss_bps):
                    exit_reason = "stop_loss"
                elif p.take_profit_bps is not None and pnl_bps >= abs(p.take_profit_bps):
                    exit_reason = "take_profit"
                elif now_ms - p.entry_ts_ms >= p.hold_ms:
                    exit_reason = "hold_expired"
                if exit_reason:
                    self._close_position(p, now_ms, price_ref, exit_reason)
                else:
                    keep.append(p)
            if keep:
                self.open[venue] = keep
            else:
                self.open.pop(venue, None)

    def _close_position(self, p: _OpenPosition, now_ms: int, exit_price_vwap: float,
                        exit_reason: str) -> None:
        snap = self.bbo.snapshot(p.venue, now_ms)
        spread_exit = snap.spread_bps if snap.available else None
        slip_model = self.strategy.params.get("slippage_model",
                                               getattr(self.strategy, "slippage_model", "half_spread"))
        fixed = float(self.strategy.params.get("fixed_slippage_bps",
                                                getattr(self.strategy, "fixed_slippage_bps", 1.0)))
        slip_exit, slip_src_exit = compute_slippage_bps(slip_model, spread_exit, snap.available, fixed)
        sign = 1 if p.side == "buy" else -1
        exit_exec = exit_price_vwap * (1 - sign * slip_exit / 1e4)
        cfg = REGISTRY.get(p.venue)
        taker = float(cfg.taker_fee_bps) if cfg else 5.0
        fee_exit = taker  # close at market
        gross_bps = sign * (exit_price_vwap / p.entry_price_vwap - 1.0) * 1e4
        fee_total = p.fee_entry_bps + fee_exit
        slip_total = p.slippage_entry_bps + slip_exit
        net_bps = sign * (exit_exec / p.entry_price_exec - 1.0) * 1e4 - fee_total
        self.cumulative_pnl_bps += net_bps
        trade = {
            "trade_id": p.trade_id, "signal_bin_idx": p.signal_bin_idx,
            "signal_type": p.signal_type, "direction": p.direction,
            "magnitude_sigma": p.magnitude_sigma, "venue": p.venue, "side": p.side,
            "entry_ts_ms": p.entry_ts_ms, "exit_ts_ms": now_ms,
            "entry_price_vwap": p.entry_price_vwap, "exit_price_vwap": exit_price_vwap,
            "entry_price_exec": p.entry_price_exec, "exit_price_exec": exit_exec,
            "slippage_entry_bps": p.slippage_entry_bps, "slippage_exit_bps": slip_exit,
            "slippage_total_bps": slip_total,
            "slippage_source": p.slippage_source_entry,
            "spread_at_entry_bps": p.spread_at_entry_bps, "spread_at_exit_bps": spread_exit,
            "gross_pnl_bps": gross_bps,
            "fee_entry_bps": p.fee_entry_bps, "fee_exit_bps": fee_exit, "fee_total_bps": fee_total,
            "fee_type": p.fee_type, "net_pnl_bps": net_bps,
            "hold_ms": now_ms - p.entry_ts_ms, "exit_reason": exit_reason,
            "mfe_bps": p.mfe_bps, "mae_bps": p.mae_bps,
            "mfe_time_ms": p.mfe_time_ms, "mae_time_ms": p.mae_time_ms,
            "bbo_available": p.bbo_available, "n_lagging_at_signal": p.n_lagging,
        }
        self._append_line("trades.jsonl", trade)
        self._append_line("equity.jsonl", {
            "ts_ms": now_ms, "cumulative_pnl_bps": self.cumulative_pnl_bps,
            "trade_id": p.trade_id,
        })
        self._write_positions()
        self._write_status()

    # ─── persistence ───

    def _append_line(self, fname: str, obj: dict) -> None:
        with (self.out_dir / fname).open("a") as f:
            f.write(json.dumps(obj) + "\n")

    def _append_signal(self, ev: Event, action: str, skip_reason: Optional[str] = None,
                       order: Optional[Order] = None, error: Optional[str] = None,
                       spread_at_signal_bps: Optional[float] = None,
                       bbo_available: Optional[bool] = None) -> None:
        rec = {
            "ts_ms": ev.ts_ms, "signal_type": ev.signal,
            "magnitude": ev.magnitude_sigma, "direction": ev.direction,
            "leader": ev.leader, "lagging_followers": ev.lagging_followers,
            "action": action, "skip_reason": skip_reason, "error": error,
            "spread_at_signal_bps": spread_at_signal_bps,
            "bbo_available": bbo_available,
        }
        if order is not None:
            rec["order"] = {
                "venue": order.venue, "side": order.side,
                "entry_type": order.entry_type, "hold_ms": order.hold_ms,
                "qty_btc": order.qty_btc, "stop_loss_bps": order.stop_loss_bps,
                "take_profit_bps": order.take_profit_bps,
            }
        self._append_line("signals.jsonl", rec)

    def _write_config(self, venues: list[str]) -> None:
        (self.out_dir / "config.json").write_text(json.dumps({
            "strategy_name": self.name,
            "started_at_ms": self.started_at_ms,
            "venues_monitored": venues,
            "position_mode": getattr(self.strategy, "position_mode",
                                      self.strategy.params.get("position_mode", "reject")),
            "params": self.strategy.params,
        }, indent=2))

    def _write_positions(self) -> None:
        rows = []
        for lst in self.open.values():
            for p in lst:
                rows.append(asdict(p))
        (self.out_dir / "positions.json").write_text(json.dumps(rows, indent=2))

    def _write_status(self) -> None:
        status = {
            "running": True,
            "strategy": self.name,
            "started_at_ms": self.started_at_ms,
            "uptime_s": (int(time.time() * 1000) - self.started_at_ms) / 1000,
            "cumulative_pnl_bps": self.cumulative_pnl_bps,
            "n_open": sum(len(v) for v in self.open.values()),
            "n_trades_closed": self._trade_id - sum(len(v) for v in self.open.values()),
        }
        path = self.data_dir / ".paper_status.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(status))
        os.replace(tmp, path)
