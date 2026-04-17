"""Incremental EMA + rolling return-std tracker.

Matches `pandas.Series.ewm(span=N, adjust=False).mean()` and a Welford-style
running std of log-returns. Acceptance criterion (plan.md §Phase 5): within
0.1% of pandas batch result.

Usage:
    t = EmaTracker(span=200)
    for price in prices:
        ema, sigma, deviation_sigma = t.update(price)
"""
from __future__ import annotations

import math
from typing import Optional


class EmaTracker:
    def __init__(self, span: int = 200):
        self.span = span
        self.alpha = 2.0 / (span + 1.0)
        self.ema: Optional[float] = None
        self._prev_price: Optional[float] = None
        self._ret_ema = 0.0
        self._ret_var_ema = 0.0
        self._count = 0

    def update(self, price: float) -> tuple[float, float, float]:
        """Return (ema, sigma, deviation_sigma) after ingesting `price`."""
        if self.ema is None:
            self.ema = price
        else:
            self.ema = self.alpha * price + (1 - self.alpha) * self.ema
        if self._prev_price is not None and self._prev_price > 0:
            r = math.log(price / self._prev_price)
            self._ret_ema = self.alpha * r + (1 - self.alpha) * self._ret_ema
            diff = r - self._ret_ema
            self._ret_var_ema = self.alpha * (diff * diff) + (1 - self.alpha) * self._ret_var_ema
            self._count += 1
        self._prev_price = price
        sigma_ret = math.sqrt(self._ret_var_ema)
        sigma = sigma_ret * math.sqrt(self.span)
        dev_log = math.log(price / self.ema) if self.ema and price > 0 else 0.0
        dev_sigma = dev_log / sigma if sigma > 0 else 0.0
        return self.ema, sigma, dev_sigma
