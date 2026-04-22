from pathlib import Path
import importlib
import json

import pandas as pd
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "leadlag" / "ui"


def test_phase_d_api_endpoints_for_ops(tmp_path, monkeypatch):
    data_dir = tmp_path
    (data_dir / ".collector_log.jsonl").write_text(
        json.dumps({"ts_ms": 1, "venue": "OKX Perp", "event_type": "connected", "message": "ok"}) + "\n"
    )
    (data_dir / ".collector_status.json").write_text(json.dumps({
        "running": True,
        "recording_id": "test",
        "start_time": 1,
        "planned_duration_s": 60,
        "venues": [{"name": "OKX Perp", "status": "ok", "ticks": 10}],
    }))
    ticks_dir = data_dir / "ticks" / "2026-04-17"
    ticks_dir.mkdir(parents=True)
    pd.DataFrame({
        "ts_ms": [1, 2],
        "ts_exchange_ms": [1, 2],
        "price": [100.0, 101.0],
        "qty": [0.1, 0.2],
        "side": ["buy", "sell"],
        "venue": ["OKX Perp", "OKX Perp"],
    }).to_parquet(ticks_dir / "ticks_20260417_000000.parquet")

    api_app = importlib.import_module("leadlag.api.app")
    monkeypatch.setattr(api_app, "DATA_DIR", data_dir)
    client = TestClient(api_app.app)

    venues = client.get("/api/venues")
    assert venues.status_code == 200, venues.text
    assert any(v["name"] == "OKX Perp" and "taker_fee_bps" in v for v in venues.json())

    processes = client.get("/api/system/processes")
    assert processes.status_code == 200, processes.text
    assert any(p["name"] == "leadlag-api" for p in processes.json())

    log = client.get("/api/collector/log?venue=OKX%20Perp&type=connected")
    assert log.status_code == 200, log.text
    assert log.json()[0]["message"] == "ok"

    files = client.get("/api/collector/files")
    assert files.status_code == 200, files.text
    assert files.json()[0]["rows"] == 2
    assert files.json()[0]["venues"] == ["OKX Perp"]


def test_phase_d_ui_contracts_are_operator_focused():
    dashboard = (UI / "dashboard.html").read_text()
    assert "/api/system/processes" in dashboard
    assert "/api/collector/status" in dashboard
    assert "Open Jupyter" in dashboard
    assert "Collector Status" in dashboard
    assert "Active Files" in dashboard
    assert "Pings to Venues" in dashboard

    collector = (UI / "collector.html").read_text()
    assert "/api/venues" in collector
    assert "/api/collector/log" in collector
    assert "/api/collector/files" in collector
    assert "Select All Leaders" in collector
    assert "ticks/s 1m" in collector
    assert "seconds idle" in collector
    assert "last error" in collector

    quality = (UI / "quality.html").read_text()
    assert "bad/warning" in quality
    assert "Timeline Gaps" in quality
    assert "BBO Analysis" in quality
    assert "Price deviation from leader" in quality
    assert "bin_coverage_pct" in quality
    assert "bbo_p95_spread_bps" in quality
    assert "displayModeBar:true" in quality.replace(" ", "")
