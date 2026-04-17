from pathlib import Path


UI = Path(__file__).resolve().parents[1] / "leadlag" / "ui"


def test_explorer_implements_lazy_bbo_and_trade_mode_contract():
    html = (UI / "explorer.html").read_text()
    assert "/api/sessions/${sessionId}/events" in html
    assert "/api/sessions/${selectedSession()}/event/${selectedBin}" in html
    assert "Show BBO Overlay" in html
    assert "BBO not available for" in html
    assert "bbo_window" in html
    assert "lag_50_ms" in html
    assert "lag_80_ms" in html
    assert "mode === \"trade\"" in html
    assert "entry_ts_ms" in html
    assert "exit_ts_ms" in html
    assert "keydown" in html
    assert "Plotly.react" in html
    assert "displayModeBar: true" in html
    assert "Show All Followers" in html


def test_trade_inspector_exposes_execution_and_reason_fields():
    html = (UI / "trade.html").read_text()
    assert "/api/backtests/${bt}/trade/${tid}" in html
    assert "View in Explorer" in html
    assert "entry_price_vwap" in html
    assert "entry_price_exec" in html
    assert "exit_price_vwap" in html
    assert "exit_price_exec" in html
    assert "slippage_source_entry" in html
    assert "slippage_source_exit" in html
    assert "fee_type_entry" in html
    assert "fee_type_exit" in html
    assert "mfe_bps" in html
    assert "mae_bps" in html
    assert "exit_reason" in html
    assert "spread_at_entry_bps" in html
    assert "BBO not available for" in html
    assert "Plotly.react" in html
    assert "displayModeBar: true" in html
