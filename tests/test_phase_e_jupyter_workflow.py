import json
from pathlib import Path

from leadlag import load_strategy, save_strategy_source, run_backtest
from tests.test_phase_a import LighterSignalC, _make_session


ROOT = Path(__file__).resolve().parents[1]


def test_save_strategy_source_and_notebook_plot_helpers(tmp_path):
    source = """
from leadlag import Strategy, Order

class DemoNotebookStrategy(Strategy):
    name = "demo_notebook_strategy"
    version = "test"
    description = "notebook save helper"
    params = {"hold_ms": 500}

    def on_event(self, event, ctx):
        if event.signal != "C":
            return None
        return Order(venue="Lighter Perp", side="buy", hold_ms=self.params["hold_ms"])
"""
    path = save_strategy_source(source, tmp_path / "strategies" / "demo.py")
    strategy = load_strategy(path)
    assert strategy.name == "demo_notebook_strategy"

    session = _make_session()
    event_fig = session.events.filter(signal="C")[0].plot(follower="Lighter Perp")
    assert len(event_fig.data) >= 2
    assert "Event" in event_fig.layout.title.text

    heatmap = session.events.filter(signal="C").plot_heatmap(
        x="delay_ms", y="hold_ms", metric="net_pnl_bps", follower="Lighter Perp"
    )
    assert heatmap.data

    result = run_backtest(LighterSignalC(), session)
    equity_fig = result.plot_equity(layers=True)
    assert len(equity_fig.data) >= 3
    assert result.plot_trades_scatter().data
    assert result.plot_spread_impact().data


def test_notebook_templates_are_valid_ipynb():
    for name in ("explore.ipynb", "strategy_dev.ipynb"):
        path = ROOT / "notebooks" / name
        data = json.loads(path.read_text())
        assert data["nbformat"] == 4
        assert data["cells"]
        assert data["metadata"]["kernelspec"]["language"] == "python"
