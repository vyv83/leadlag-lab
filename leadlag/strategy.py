"""Strategy base class + Event + Order + Context dataclasses.

See plan.md §contract 4 for the full spec. This is the minimal surface Phase 1
exposes so strategy files can be written and loaded; Phase 2 wires it into the
backtest engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BboSnapshot:
    venue: str
    available: bool = True
    bid_price: Optional[float] = None
    bid_qty: Optional[float] = None
    ask_price: Optional[float] = None
    ask_qty: Optional[float] = None
    spread_bps: Optional[float] = None


@dataclass
class Event:
    bin_idx: int
    ts_ms: int
    signal: str  # 'A' | 'B' | 'C'
    direction: int  # +1 | -1
    magnitude_sigma: float
    leader: str
    lagging_followers: list[str]
    follower_metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Order:
    venue: str
    side: str  # 'buy' | 'sell'
    entry_type: str = "market"  # 'market' | 'limit'
    limit_price: Optional[float] = None
    hold_ms: Optional[int] = None
    delay_ms: int = 0
    stop_loss_bps: Optional[float] = None
    take_profit_bps: Optional[float] = None
    qty_btc: float = 0.01
    tag: Optional[str] = None


@dataclass
class Context:
    ts_ms: int
    bbo: dict[str, BboSnapshot] = field(default_factory=dict)
    positions: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)


class Strategy:
    """Base class. Subclass and implement `on_event`.

    Attributes:
        name: strategy identifier shown in UI
        params: default parameters (overridable at runtime via params_override)
        slippage_model: 'none' | 'fixed' | 'half_spread' | 'full_spread'
        fixed_slippage_bps: fallback when BBO unavailable
        position_mode: 'allow_multi' | 'reject' | 'replace'
    """

    name: str = "UnnamedStrategy"
    params: dict[str, Any] = {}
    slippage_model: str = "half_spread"
    fixed_slippage_bps: float = 1.0
    position_mode: str = "reject"

    def __init__(self):
        # Strategy subclasses commonly define ``params`` at class level so the
        # UI can inspect defaults. Copy it per instance to avoid cross-run leaks
        # when backtests apply params_override.
        self.params = dict(getattr(self.__class__, "params", {}) or {})

    def on_event(self, event: Event, ctx: Context) -> Optional[Order]:
        raise NotImplementedError
