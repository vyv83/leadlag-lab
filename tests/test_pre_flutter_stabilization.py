from __future__ import annotations

import copy
import importlib
import json
import time
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from leadlag import Context, Event, Order, Strategy, run_backtest, run_monte_carlo
from leadlag.backtest import BacktestResult
from leadlag.monitor.snapshot import read_collector_status, read_history
from tests.test_phase_a import _make_analysis


BASE_TS = 1_714_500_000_000
ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "leadlag" / "ui"


def test_collections_list_from_raw_parquet(tmp_path: Path, monkeypatch):
    _write_raw_collection(tmp_path)
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/collections")

    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["n_tick_files"] == 1
    assert row["n_bbo_files"] == 1
    assert row["n_ticks"] > 0
    assert "OKX Perp" in row["venues"]
    assert "tick_file_paths" not in row


def test_analysis_endpoint_creates_session(tmp_path: Path, monkeypatch):
    _write_raw_collection(tmp_path)
    client = _client(tmp_path, monkeypatch)
    collection_id = client.get("/api/collections").json()[0]["id"]

    response = client.post(
        f"/api/collections/{collection_id}/analyze",
        json={
            "params": {
                "ema_span_bins": 5,
                "threshold_sigma": 1.0,
                "follower_max_dev": 0.5,
                "cluster_gap_bins": 5,
                "confirm_window_bins": 5,
                "detection_window_bins": 3,
                "window_ms": 500,
            }
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["analysis_id"]
    job = None
    for _ in range(40):
        job = client.get(body["status_url"]).json()
        if job["status"] == "completed":
            break
        time.sleep(0.05)
    assert job is not None
    assert job["status"] == "completed"
    assert job["events_count"] >= 1
    assert (tmp_path / "analyses" / body["analysis_id"] / "events.json").exists()
    events = client.get(f"/api/analyses/{body['analysis_id']}/events").json()
    assert any(e["signal"] == "C" for e in events)


def test_collector_status_stale_returns_not_running(tmp_path: Path):
    old_ms = int((time.time() - 60) * 1000)
    (tmp_path / ".collector_status.json").write_text(json.dumps({
        "running": True,
        "recording_id": "old",
        "updated_at_ms": old_ms,
        "venues": [{"name": "Aster Perp", "status": "ok", "ticks": 0}],
    }))

    status = read_collector_status(tmp_path, stale_after_s=30)

    assert status["stale"] is True
    assert status["running"] is False
    assert status["running_effective"] is False
    assert status["file_running"] is True


def test_monitor_history_has_network_rates(tmp_path: Path):
    now = int(time.time() * 1000)
    rows = [
        {"ts": now - 5000, "cpu_pct": 1, "ram_used_gb": 1, "disk_used_gb": 1, "net_sent": 1000, "net_recv": 2000},
        {"ts": now, "cpu_pct": 2, "ram_used_gb": 1, "disk_used_gb": 1, "net_sent": 6000, "net_recv": 12000},
    ]
    (tmp_path / ".system_history.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    history = read_history(tmp_path, minutes=10)

    assert history[-1]["net_up_bps"] == 1000
    assert history[-1]["net_down_bps"] == 2000


def test_explorer_filter_logic_default_all_events():
    html = (UI / "explorer.html").read_text()

    assert 'id="filterFollower"' in html
    assert 'id="chartFollower"' in html
    assert 'const follower = document.getElementById("filterFollower").value' in html
    assert 'const actualLeader = e.anchor_leader || e.leader' in html
    assert '["OKX Perp", "confirmed"]' not in html
    assert '["leaderMode", "direction", "filterFollower"' in html


def test_explorer_keyboard_nav_ignores_inputs():
    html = (UI / "explorer.html").read_text()

    assert "tagName" in html
    assert '["input", "select", "textarea"].includes(tag)' in html
    assert "moveEvent(1)" in html


def test_limit_fee_contract():
    class LimitOkx(Strategy):
        name = "limit_okx"
        params = {"entry_type": "limit", "position_mode": "reject", "hold_ms": 500}

        def on_event(self, event: Event, ctx: Context) -> Order | None:
            return Order(venue="OKX Perp", side="buy", entry_type="limit", hold_ms=500)

    result = run_backtest(LimitOkx(), _make_analysis())

    trade = result.trades[0]
    assert trade["fee_type_entry"] == "maker"
    assert trade["fee_type_exit"] == "maker"
    assert trade["fee_total_bps"] == 4.0


def test_reverse_mode_generates_reversed_close_trade():
    class ReverseLighter(Strategy):
        name = "reverse_lighter"
        params = {"entry_type": "market", "position_mode": "reverse", "hold_ms": 2000, "slippage_model": "none"}

        def on_event(self, event: Event, ctx: Context) -> Order | None:
            return Order(
                venue="Lighter Perp",
                side="buy" if event.direction > 0 else "sell",
                entry_type="market",
                hold_ms=2000,
            )

    analysis = _make_analysis()
    second = copy.deepcopy(analysis.events.rows[0])
    second.update({
        "event_id": 1,
        "bin_idx": 25,
        "ts_ms": int(analysis.vwap_df["ts_ms"].iloc[25]),
        "direction": -1,
        "signal": "C",
        "anchor_leader": "Bybit Perp",
        "confirmer_leader": "OKX Perp",
    })
    analysis.events.rows.append(second)
    analysis.meta["n_events"] = 2

    result = run_backtest(ReverseLighter(), analysis)

    assert len(result.trades) == 2
    assert result.trades[0]["exit_reason"] == "reversed"
    assert result.trades[0]["hold_ms"] == 250
    assert result.stats["by_exit_reason"]["reversed"]["n"] == 1


def test_montecarlo_default_not_degenerate():
    result = BacktestResult(
        strategy_name="demo",
        analysis_id="analysis",
        params={},
        trades=[
            {"trade_id": 0, "net_pnl_bps": 1.0},
            {"trade_id": 1, "net_pnl_bps": -2.0},
            {"trade_id": 2, "net_pnl_bps": 3.0},
        ],
        equity=[],
        stats={},
    )

    mc = run_monte_carlo(result, n=200, seed=7)

    assert mc.method == "bootstrap"
    assert len(set(mc.sim_final_pnls)) > 1
    assert "n_trades_lt_20_monte_carlo_is_low_confidence" in (mc.warnings or [])


def test_paper_ipc_pending_is_reported_as_blocked(tmp_path: Path, monkeypatch):
    (tmp_path / ".paper_status.json").write_text(json.dumps({
        "running": False,
        "strategy": "baseline_signal_c",
        "mode": "collector_ipc_pending",
        "blocked": True,
        "blocked_reason": "collector_ipc_not_implemented",
    }))
    client = _client(tmp_path, monkeypatch)

    status = client.get("/api/paper/status").json()

    assert status["blocked"] is True
    assert status["can_trade"] is False
    assert status["running_effective"] is False


def _client(data_dir: Path, monkeypatch) -> TestClient:
    api_app = importlib.import_module("leadlag.api.app")
    monkeypatch.setattr(api_app, "DATA_DIR", data_dir)
    monkeypatch.setattr(api_app, "COLLECTOR_PROC", None)
    monkeypatch.setattr(api_app, "PAPER_PROC", None)
    return TestClient(api_app.app)


def _write_raw_collection(root: Path) -> None:
    ticks = []
    bbo = []
    for i in range(80):
        ts = BASE_TS + i * 50
        okx = 100_000 + (100 if i >= 20 else 0)
        bybit = 100_000 + (100 if i >= 21 else 0)
        lighter = 50_000 + (60 if i >= 28 else 0)
        for venue, price in (("OKX Perp", okx), ("Bybit Perp", bybit), ("Lighter Perp", lighter)):
            ticks.append({
                "ts_ms": ts,
                "ts_exchange_ms": ts,
                "price": float(price),
                "qty": 1.0,
                "side": "buy",
                "venue": venue,
            })
            bbo.append({
                "ts_ms": ts,
                "bid_price": float(price - 1),
                "bid_qty": 1.0,
                "ask_price": float(price + 1),
                "ask_qty": 1.0,
                "venue": venue,
            })
    ticks_dir = root / "ticks" / "2026-04-17"
    bbo_dir = root / "bbo" / "2026-04-17"
    ticks_dir.mkdir(parents=True)
    bbo_dir.mkdir(parents=True)
    pd.DataFrame(ticks).to_parquet(ticks_dir / "ticks_20260417_000000.parquet")
    pd.DataFrame(bbo).to_parquet(bbo_dir / "bbo_20260417_000000.parquet")
