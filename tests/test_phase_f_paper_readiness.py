import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "leadlag" / "ui"


def test_paper_current_endpoints_and_stats(tmp_path, monkeypatch):
    paper_dir = tmp_path / "paper" / "demo"
    paper_dir.mkdir(parents=True)
    (tmp_path / ".paper_status.json").write_text(json.dumps({"running": True, "strategy": "demo"}))
    (tmp_path / ".paper_venues.json").write_text(json.dumps([
        {"venue": "OKX Perp", "role": "leader", "used_by_strategy": True, "status": "monitoring"}
    ]))
    (paper_dir / "trades.jsonl").write_text(
        json.dumps({"ts_ms": 1, "trade_id": 0, "net_pnl_bps": 2.0, "fee_total_bps": 0.5, "slippage_total_bps": 0.2}) + "\n" +
        json.dumps({"ts_ms": 2, "trade_id": 1, "net_pnl_bps": -1.0, "fee_total_bps": 0.5, "slippage_total_bps": 0.2}) + "\n"
    )
    (paper_dir / "signals.jsonl").write_text(json.dumps({"ts_ms": 1, "signal_type": "C", "action": "trade"}) + "\n")
    (paper_dir / "equity.jsonl").write_text(json.dumps({"ts_ms": 2, "cumulative_pnl_bps": 1.0}) + "\n")
    (paper_dir / "positions.json").write_text("[]")

    api_app = importlib.import_module("leadlag.api.app")
    monkeypatch.setattr(api_app, "DATA_DIR", tmp_path)
    client = TestClient(api_app.app)

    assert client.get("/api/paper/trades").json()[0]["trade_id"] == 0
    assert client.get("/api/paper/signals").json()[0]["signal_type"] == "C"
    assert client.get("/api/paper/equity").json()[0]["cumulative_pnl_bps"] == 1.0
    assert client.get("/api/paper/positions").json() == []
    assert client.get("/api/paper/venues").json()[0]["venue"] == "OKX Perp"
    stats = client.get("/api/paper/stats").json()
    assert stats["n_trades"] == 2
    assert stats["total_net_pnl_bps"] == 1.0
    assert stats["win_rate"] == 0.5


def test_paper_ui_and_daemon_contracts():
    html = (UI / "paper.html").read_text()
    assert "/api/paper/start" in html
    assert "/api/paper/stop" in html
    assert "/api/paper/venues" in html
    assert "/api/paper/signals?last=40" in html
    assert "/api/paper/positions" in html
    assert "/api/paper/stats" in html
    assert "Venue Connectivity" in html
    assert "Live Equity" in html
    assert "Open Positions" in html
    assert "Closed Trades" in html

    daemon = (ROOT / "leadlag" / "paper" / "__main__.py").read_text()
    assert "collector_ipc_pending" in daemon
    assert "_ws_venue_task" in daemon
    assert "venues = list(dict.fromkeys(leaders + followers))" in daemon
