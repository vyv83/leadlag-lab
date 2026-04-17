"""Slippage models. See plan.md §contract 5 (Модели проскальзывания)."""
from __future__ import annotations

from typing import Optional


def compute_slippage_bps(
    model: str,
    spread_bps: Optional[float],
    bbo_available: bool,
    fixed_slippage_bps: float,
) -> tuple[float, str]:
    """Return (slippage_bps, source).

    source ∈ {'none', 'fixed', 'bbo', 'fixed_fallback'}.
    """
    if model == "none":
        return 0.0, "none"
    if model == "fixed":
        return float(fixed_slippage_bps), "fixed"
    if model in ("half_spread", "full_spread"):
        if not bbo_available or spread_bps is None:
            return float(fixed_slippage_bps), "fixed_fallback"
        return (spread_bps / 2.0 if model == "half_spread" else float(spread_bps)), "bbo"
    raise ValueError(f"Unknown slippage_model: {model}")
