"""Lightweight artifact contract validation for analyses and backtests."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class ContractError(ValueError):
    """Raised when an on-disk artifact does not satisfy the public contract."""


ANALYSIS_META_REQUIRED = {
    "analysis_id",
    "recording_id",
    "params_hash",
    "collection_files",
    "t_start_ms",
    "t_end_ms",
    "duration_s",
    "bin_size_ms",
    "ema_span",
    "threshold_sigma",
    "venues",
    "leaders",
    "followers",
    "fees",
    "bbo_available",
    "n_ticks",
    "n_bbo",
    "n_events",
    "n_signal_a",
    "n_signal_b",
    "n_signal_c",
    "created_at_utc",
    "source_data_layout_version",
}

EVENT_REQUIRED = {
    "event_id",
    "bin_idx",
    "ts_ms",
    "time_utc",
    "signal",
    "direction",
    "magnitude_sigma",
    "leader",
    "leader_dev",
    "anchor_leader",
    "lagging_followers",
    "n_lagging",
    "follower_metrics",
    "grid_results",
    "quality_flags_at_event",
}

PRICE_WINDOW_REQUIRED = {"bin_idx", "rel_times_ms", "venues"}
BBO_WINDOW_REQUIRED = {"bin_idx", "rel_times_ms", "venues"}
BACKTEST_META_REQUIRED = {
    "backtest_id",
    "strategy_name",
    "strategy_version",
    "strategy_description",
    "strategy_params",
    "params_override",
    "analysis_id",
    "backtest_date_utc",
    "computation_time_s",
    "slippage_model",
    "fixed_slippage_bps",
    "entry_type",
    "position_mode",
    "data_contract_version",
    "engine_version",
}
TRADE_REQUIRED = {
    "trade_id",
    "signal_bin_idx",
    "signal_type",
    "direction",
    "magnitude_sigma",
    "venue",
    "side",
    "entry_type",
    "entry_ts_ms",
    "entry_time_utc",
    "exit_ts_ms",
    "exit_time_utc",
    "entry_price_vwap",
    "exit_price_vwap",
    "entry_price_exec",
    "exit_price_exec",
    "slippage_entry_bps",
    "slippage_exit_bps",
    "slippage_total_bps",
    "slippage_source_entry",
    "slippage_source_exit",
    "spread_at_entry_bps",
    "spread_at_exit_bps",
    "gross_pnl_bps",
    "fee_entry_bps",
    "fee_exit_bps",
    "fee_total_bps",
    "fee_type_entry",
    "fee_type_exit",
    "net_pnl_bps",
    "hold_ms",
    "planned_hold_ms",
    "exit_reason",
    "mfe_bps",
    "mae_bps",
    "mfe_time_ms",
    "mae_time_ms",
    "bbo_available",
    "n_lagging_at_signal",
    "leader_dev_sigma",
}
EQUITY_REQUIRED = {
    "ts_ms",
    "gross_equity_bps",
    "post_fee_equity_bps",
    "net_equity_bps",
    "drawdown_bps",
    "trade_id",
}
STATS_REQUIRED = {
    "total_net_pnl_bps",
    "total_gross_pnl_bps",
    "total_fees_bps",
    "total_slippage_bps",
    "n_trades",
    "n_errors",
    "win_rate",
    "profit_factor",
    "sharpe",
    "max_drawdown_bps",
    "avg_trade_bps",
    "by_signal",
    "by_venue",
    "by_direction",
    "by_entry_type",
    "by_spread_bucket",
    "by_exit_reason",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_from_ms(ts_ms: int | float | None) -> str | None:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def to_jsonable(value: Any) -> Any:
    """Convert pandas/numpy values and non-finite floats into strict JSON values."""
    if value is None:
        return None
    if value is pd.NA:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (datetime, pd.Timestamp)):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    return value


def write_json(path: Path, data: Any, *, indent: int | None = None) -> None:
    path.write_text(json.dumps(to_jsonable(data), indent=indent, allow_nan=False))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _require_keys(name: str, obj: dict, required: set[str]) -> None:
    missing = sorted(k for k in required if k not in obj)
    if missing:
        raise ContractError(f"{name} missing required keys: {', '.join(missing)}")


def validate_analysis_payload(
    meta: dict,
    events: list[dict],
    price_windows: list[dict],
    bbo_windows: list[dict],
    quality: dict,
) -> None:
    _require_keys("meta.json", meta, ANALYSIS_META_REQUIRED)
    if not isinstance(events, list):
        raise ContractError("events.json must be a list")
    for i, event in enumerate(events):
        _require_keys(f"events.json[{i}]", event, EVENT_REQUIRED)
        if event["signal"] not in {"A", "B", "C"}:
            raise ContractError(f"events.json[{i}].signal must be A/B/C")
        if event["direction"] not in {-1, 1}:
            raise ContractError(f"events.json[{i}].direction must be -1 or 1")
    for i, window in enumerate(price_windows):
        _require_keys(f"price_windows.json[{i}]", window, PRICE_WINDOW_REQUIRED)
    for i, window in enumerate(bbo_windows):
        _require_keys(f"bbo_windows.json[{i}]", window, BBO_WINDOW_REQUIRED)
    if not isinstance(quality, dict) or "venues" not in quality:
        raise ContractError("quality.json must contain a venues object")


def validate_backtest_payload(
    meta: dict,
    trades: list[dict],
    equity: list[dict],
    stats: dict,
) -> None:
    _require_keys("backtest meta.json", meta, BACKTEST_META_REQUIRED)
    for i, trade in enumerate(trades):
        _require_keys(f"trades.json[{i}]", trade, TRADE_REQUIRED)
    for i, row in enumerate(equity):
        _require_keys(f"equity.json[{i}]", row, EQUITY_REQUIRED)
    _require_keys("stats.json", stats, STATS_REQUIRED)


def validate_analysis_artifacts(root: Path) -> None:
    for name in ("meta.json", "events.json", "price_windows.json", "bbo_windows.json", "quality.json"):
        if not (root / name).exists():
            raise ContractError(f"missing analysis artifact: {root / name}")
    validate_analysis_payload(
        read_json(root / "meta.json"),
        read_json(root / "events.json"),
        read_json(root / "price_windows.json"),
        read_json(root / "bbo_windows.json"),
        read_json(root / "quality.json"),
    )


def validate_backtest_artifacts(root: Path) -> None:
    for name in ("meta.json", "trades.json", "equity.json", "stats.json"):
        if not (root / name).exists():
            raise ContractError(f"missing backtest artifact: {root / name}")
    validate_backtest_payload(
        read_json(root / "meta.json"),
        read_json(root / "trades.json"),
        read_json(root / "equity.json"),
        read_json(root / "stats.json"),
    )
