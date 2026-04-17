from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_phase_a import LighterSignalC, _make_session
from leadlag import run_backtest


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "leadlag" / "ui"


def test_backtest_page_is_decision_grade():
    html = (UI / "backtest.html").read_text()
    assert "Gross - Fees" in html
    assert "drawdown_bps" in html
    assert "PnL per trade" in html
    assert "Hold times" in html
    assert "Magnitude vs PnL" in html
    assert "Time of day vs PnL" in html
    assert "Spread at entry vs PnL" in html
    assert "Fee & Slippage Impact" in html
    assert "By Spread Bucket" in html
    assert "By Venue" in html
    assert "By Signal" in html
    assert "Run Monte Carlo" in html
    assert "View Event" in html
    assert "displayModeBar: true" in html
    assert "plotly_click" in html


def test_montecarlo_page_runs_and_renders_robustness_contract():
    html = (UI / "montecarlo.html").read_text()
    assert "/api/backtests/${currentId}/montecarlo/run" in html
    assert "/api/backtests/${id}/montecarlo" in html
    assert "Equity Curves" in html
    assert "Final PnL" in html
    assert "Sharpe" in html
    assert "Max Drawdown" in html
    assert "p-value" in html
    assert "Percentile" in html
    assert "Probability Profit" in html
    assert "Block bootstrap" in html
    assert "displayModeBar: true" in html


def test_montecarlo_api_and_backtest_list_include_phase_c_summary(tmp_path, monkeypatch):
    session = _make_session()
    session.save(tmp_path)
    result = run_backtest(LighterSignalC(), session)
    bt_dir = result.save(tmp_path)

    import importlib

    api_app = importlib.import_module("leadlag.api.app")
    monkeypatch.setattr(api_app, "DATA_DIR", tmp_path)
    client = TestClient(api_app.app)

    listed = client.get("/api/backtests")
    assert listed.status_code == 200, listed.text
    row = listed.json()[0]
    assert row["avg_trade_bps"] == result.stats["avg_trade_bps"]
    assert row["has_montecarlo"] is False

    run = client.post(f"/api/backtests/{bt_dir.name}/montecarlo/run", json={"n_simulations": 100})
    assert run.status_code == 200, run.text
    assert "p_value" in run.json()

    mc = client.get(f"/api/backtests/{bt_dir.name}/montecarlo")
    assert mc.status_code == 200, mc.text
    assert mc.json()["n_simulations"] == 100
