"""Incremental 50ms VWAP bin buffer for a single venue.

On each tick:
  1. compute bin_idx = (ts_ms - session_start) // bin_size_ms
  2. accumulate price*qty and qty for the current bin
  3. when a tick crosses into a new bin, finalize the previous one —
     VWAP = Σ(p·q)/Σq, or last known price if Σq == 0

Finalized bins are emitted via an optional callback and also available
via .last_finalized / .history.
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Deque, Optional


class BinBuffer:
    def __init__(
        self,
        session_start_ms: int,
        bin_size_ms: int = 50,
        history_size: int = 20_000,
        on_finalize: Optional[Callable[[int, float], None]] = None,
    ):
        self.session_start_ms = session_start_ms
        self.bin_size_ms = bin_size_ms
        self._cur_bin: Optional[int] = None
        self._cur_pq = 0.0
        self._cur_q = 0.0
        self._last_price: Optional[float] = None
        self._on_finalize = on_finalize
        self.history: Deque[tuple[int, float]] = deque(maxlen=history_size)
        self.last_finalized: Optional[tuple[int, float]] = None

    def add_tick(self, ts_ms: int, price: float, qty: float) -> list[tuple[int, float]]:
        bin_idx = (ts_ms - self.session_start_ms) // self.bin_size_ms
        finalized: list[tuple[int, float]] = []
        if self._cur_bin is None:
            self._cur_bin = bin_idx
        elif bin_idx > self._cur_bin:
            finalized += self._flush_through(bin_idx)
        self._cur_pq += price * qty
        self._cur_q += qty
        self._last_price = price
        return finalized

    def _flush_through(self, new_bin: int) -> list[tuple[int, float]]:
        """Finalize current + any empty bins up to (but not including) new_bin."""
        out: list[tuple[int, float]] = []
        vwap = (self._cur_pq / self._cur_q) if self._cur_q > 0 else self._last_price
        if vwap is not None:
            out.append((self._cur_bin, vwap))
        self._cur_pq, self._cur_q = 0.0, 0.0
        # carry forward empty bins
        b = self._cur_bin + 1
        while b < new_bin:
            if self._last_price is not None:
                out.append((b, self._last_price))
            b += 1
        self._cur_bin = new_bin
        for b_idx, vw in out:
            self.history.append((b_idx, vw))
            self.last_finalized = (b_idx, vw)
            if self._on_finalize:
                self._on_finalize(b_idx, vw)
        return out

    def force_flush(self) -> list[tuple[int, float]]:
        if self._cur_bin is None:
            return []
        return self._flush_through(self._cur_bin + 1)
