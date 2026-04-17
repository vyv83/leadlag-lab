"""Real-time first-crossing detector.

Wires per-venue BinBuffer + EmaTracker. When a leader's finalized bin crosses
±threshold σ AND enough followers are "not-yet-lagged" (|dev| < follower_max_dev),
emits an Event. Mirrors batch `detect_events_v3` semantics but incremental —
only one Event is emitted per crossing; re-crossing requires return inside
the threshold band first.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from leadlag.realtime.bin_buffer import BinBuffer
from leadlag.realtime.ema_tracker import EmaTracker
from leadlag.strategy import Event


class RealtimeDetector:
    def __init__(
        self,
        leaders: list[str],
        followers: list[str],
        session_start_ms: int,
        *,
        bin_size_ms: int = 50,
        ema_span: int = 200,
        threshold_sigma: float = 2.0,
        follower_max_dev: float = 0.5,
        on_event: Optional[Callable[[Event], None]] = None,
    ):
        self.leaders = list(leaders)
        self.followers = list(followers)
        self.bin_size_ms = bin_size_ms
        self.threshold = threshold_sigma
        self.follower_max_dev = follower_max_dev
        self.on_event = on_event

        self.buffers: dict[str, BinBuffer] = {
            v: BinBuffer(session_start_ms, bin_size_ms) for v in leaders + followers
        }
        self.emas: dict[str, EmaTracker] = {v: EmaTracker(ema_span) for v in leaders + followers}
        self._last_dev: dict[str, float] = {v: 0.0 for v in leaders + followers}
        self._armed: dict[str, bool] = {v: True for v in leaders}

    def on_tick(self, venue: str, ts_ms: int, price: float, qty: float) -> list[Event]:
        buf = self.buffers.get(venue)
        if buf is None:
            return []
        finalized = buf.add_tick(ts_ms, price, qty)
        events: list[Event] = []
        for bin_idx, vwap in finalized:
            _ema, _sigma, dev = self.emas[venue].update(vwap)
            self._last_dev[venue] = dev
            if venue in self.leaders:
                events += self._check_leader(venue, bin_idx, ts_ms, dev)
        for ev in events:
            if self.on_event:
                self.on_event(ev)
        return events

    def _check_leader(self, leader: str, bin_idx: int, ts_ms: int, dev: float) -> list[Event]:
        if abs(dev) < self.threshold:
            self._armed[leader] = True
            return []
        if not self._armed[leader]:
            return []
        direction = 1 if dev > 0 else -1
        lagging = [
            f for f in self.followers
            if abs(self._last_dev.get(f, 0.0)) < self.follower_max_dev
        ]
        self._armed[leader] = False
        ev = Event(
            bin_idx=int(bin_idx),
            ts_ms=int(ts_ms),
            signal="A",  # realtime lane — A/B/C classification is a batch concept
            direction=direction,
            magnitude_sigma=abs(dev),
            leader=leader,
            lagging_followers=lagging,
        )
        return [ev]
