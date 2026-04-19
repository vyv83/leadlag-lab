from leadlag import Strategy, Order

class MyStrategy(Strategy):
    version = "2026-04-18"
    description = "Strategy template"
    params = {
        "signal": "C",
        "follower": "Lighter Perp",
        "min_magnitude": 2.0,
        "hold_ms": 30000,
    }

    def on_event(self, event, ctx):
        p = self.params

        if event.signal != p["signal"]:
            return None
        if p["follower"] not in event.lagging_followers:
            return None
        if event.magnitude_sigma < p["min_magnitude"]:
            return None

        return Order(
            venue=p["follower"],
            side="buy" if event.direction > 0 else "sell",
            qty_btc=0.001,
            entry_type="market",
            hold_ms=p["hold_ms"],
        )
