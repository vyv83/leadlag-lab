from leadlag import Order, Strategy


class BaselineSignalC(Strategy):
    name = "baseline_signal_c"
    version = "2026-04-17"
    description = "Demo baseline: Signal C, first lagging follower, market entry, 30s hold."

    params = {
        "signal": "C",
        "min_magnitude": 2.0,
        "followers": ["Lighter Perp", "Binance Perp", "Bitget Perp", "edgeX Perp", "MEXC Perp"],
        "hold_ms": 30000,
        "entry_type": "market",
        "slippage_model": "half_spread",
        "fixed_slippage_bps": 1.0,
        "position_mode": "reject",
        "stop_loss_bps": None,
        "take_profit_bps": None,
        "qty_btc": 0.001,
    }

    def on_event(self, event, ctx):
        if event.signal != self.params["signal"]:
            return None
        if event.magnitude_sigma < float(self.params["min_magnitude"]):
            return None

        lagging = list(event.lagging_followers or [])
        preferred = [v for v in self.params["followers"] if v in lagging]
        venue = (preferred or lagging or [None])[0]
        if venue is None:
            return None

        return Order(
            venue=venue,
            side="buy" if event.direction > 0 else "sell",
            entry_type=self.params["entry_type"],
            hold_ms=int(self.params["hold_ms"]),
            stop_loss_bps=self.params.get("stop_loss_bps"),
            take_profit_bps=self.params.get("take_profit_bps"),
            qty_btc=float(self.params["qty_btc"]),
        )
