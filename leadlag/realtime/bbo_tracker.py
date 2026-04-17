"""Per-venue last-BBO tracker.

Stores the latest bid/ask for each venue, computes spread in bps, and
produces `BboSnapshot` objects for strategy `Context`.
"""
from __future__ import annotations

import time
from typing import Optional

from leadlag.strategy import BboSnapshot
from leadlag.venues.config import BBO_UNAVAILABLE_VENUES


class BboTracker:
    def __init__(self, staleness_ms: int = 5000):
        self.staleness_ms = staleness_ms
        self._last: dict[str, tuple[int, float, float, float, float]] = {}
        # venue -> (ts_ms, bid, bid_qty, ask, ask_qty)

    def update(self, venue: str, ts_ms: int, bid: float, ask: float,
               bid_qty: float = 0.0, ask_qty: float = 0.0) -> None:
        if bid > 0 and ask > 0:
            self._last[venue] = (ts_ms, bid, bid_qty, ask, ask_qty)

    def snapshot(self, venue: str, now_ms: Optional[int] = None) -> BboSnapshot:
        if venue in BBO_UNAVAILABLE_VENUES:
            return BboSnapshot(venue=venue, available=False)
        rec = self._last.get(venue)
        if rec is None:
            return BboSnapshot(venue=venue, available=False)
        ts_ms, bid, bid_qty, ask, ask_qty = rec
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        if now - ts_ms > self.staleness_ms:
            return BboSnapshot(venue=venue, available=False)
        mid = 0.5 * (bid + ask)
        spread_bps = (ask - bid) / mid * 1e4 if mid > 0 else None
        return BboSnapshot(venue=venue, available=True, bid_price=bid, ask_price=ask,
                           bid_qty=bid_qty, ask_qty=ask_qty, spread_bps=spread_bps)

    def all(self, now_ms: Optional[int] = None) -> dict[str, BboSnapshot]:
        from leadlag.venues.config import REGISTRY
        return {v: self.snapshot(v, now_ms) for v in REGISTRY}
