from leadlag import Strategy, Order


class ResearchMultiSignalV1(Strategy):
    name = "research_multi_signal_v1"
    version = "2026-04-19"
    description = (
        "Research strategy: Lighter Perp + MEXC Perp, all signals A/B/C, "
        "relaxed magnitude filter. Based on analysis_full.txt findings: "
        "Lighter C Net +5.94 bps [CI +3.69,+8.03], MEXC C Net +3.22 bps [CI +1.04,+5.70]."
    )
    params = {
        "signals": ["A", "B", "C"],
        "followers": ["Lighter Perp", "MEXC Perp"],
        "min_magnitude": 1.5,
        "hold_ms": 30000,
        "entry_type": "market",
        "qty_btc": 0.001,
    }

    def on_event(self, event, ctx):
        p = self.params

        if event.signal not in p["signals"]:
            return None
        if event.magnitude_sigma < p["min_magnitude"]:
            return None

        lagging = list(event.lagging_followers or [])
        venue = next((v for v in p["followers"] if v in lagging), None)
        if venue is None:
            return None

        return Order(
            venue=venue,
            side="buy" if event.direction > 0 else "sell",
            qty_btc=p["qty_btc"],
            entry_type=p["entry_type"],
            hold_ms=p["hold_ms"],
        )
