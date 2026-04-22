from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from leadlag import (
    Context,
    Event,
    Order,
    Analysis,
    Strategy,
    iter_bbo_batches,
    iter_ticks_batches,
    list_analyses,
    load_analysis,
    run_backtest,
    run_monte_carlo,
)


BASE_TS = 1_714_000_000_000


class LighterSignalC(Strategy):
    name = "lighter_signal_c"
    version = "test"
    description = "Signal C synthetic test"
    params = {
        "entry_type": "market",
        "slippage_model": "half_spread",
        "fixed_slippage_bps": 1.0,
        "position_mode": "reject",
        "hold_ms": 500,
    }

    def on_event(self, event: Event, ctx: Context) -> Order | None:
        if event.signal != "C":
            return None
        if "Lighter Perp" not in event.lagging_followers:
            return None
        return Order(
            venue="Lighter Perp",
            side="buy" if event.direction > 0 else "sell",
            entry_type=self.params["entry_type"],
            hold_ms=self.params["hold_ms"],
            qty_btc=0.001,
        )


def test_public_api_session_backtest_and_monte_carlo(tmp_path: Path):
    analysis = _make_analysis()
    analysis.save(tmp_path)

    listed = list_analyses(tmp_path)
    assert listed[0]["id"] == analysis.analysis_id
    assert listed[0]["n_signal_c"] == 1

    loaded = load_analysis(analysis.analysis_id, tmp_path)
    assert loaded._vwap_df is None
    assert loaded.events.filter(signal="C").count == 1
    assert loaded.events.filter(signal="C", follower="Lighter Perp", min_magnitude=2.0).count == 1
    assert loaded.event_detail(20)["price_window"]["venues"]["Lighter Perp"]

    result = run_backtest(LighterSignalC(), loaded)
    assert result.trades
    trade = result.trades[0]
    assert trade["slippage_source_entry"] == "bbo"
    assert trade["fee_type_entry"] == "taker"
    assert trade["entry_time_utc"].endswith("Z")
    assert result.stats["n_trades"] == 1
    assert result.stats["total_net_pnl_bps"] < result.stats["total_gross_pnl_bps"]

    bt_dir = result.save(tmp_path)
    assert (bt_dir / "meta.json").exists()
    assert (bt_dir / "trades.json").exists()
    assert (bt_dir / "equity.json").exists()
    assert (bt_dir / "stats.json").exists()

    mc = run_monte_carlo(result, n=100, seed=1)
    assert mc.n_simulations == 100
    assert "p_value" in mc.summary()


def test_backtest_api_path_returns_structured_artifacts(tmp_path: Path, monkeypatch):
    analysis = _make_analysis()
    analysis.save(tmp_path)
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True)
    (strategies_dir / "lighter_signal_c.py").write_text(
        """
from leadlag import Strategy, Order

class LighterSignalC(Strategy):
    name = "lighter_signal_c"
    version = "test"
    description = "API synthetic test"
    params = {
        "entry_type": "market",
        "slippage_model": "half_spread",
        "fixed_slippage_bps": 1.0,
        "position_mode": "reject",
        "hold_ms": 500,
    }

    def on_event(self, event, ctx):
        if event.signal != "C" or "Lighter Perp" not in event.lagging_followers:
            return None
        return Order(venue="Lighter Perp", side="buy", entry_type="market", hold_ms=500, qty_btc=0.001)
"""
    )

    api_app = importlib.import_module("leadlag.api.app")

    monkeypatch.setattr(api_app, "DATA_DIR", tmp_path)
    client = TestClient(api_app.app)

    response = client.post(
        "/api/backtests/run",
        json={"strategy_name": "lighter_signal_c", "analysis_id": analysis.analysis_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["n_trades"] == 1

    detail = client.get(f"/api/backtests/{body['backtest_id']}/trade/0")
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["event"]["signal"] == "C"
    assert payload["price_window"]["venues"]["Lighter Perp"]
    assert payload["bbo_window"]["venues"]["Lighter Perp"]["spread_bps"]
    assert "MEXC Perp" in payload["no_bbo_venues"]

    mc = client.post(f"/api/backtests/{body['backtest_id']}/montecarlo/run", json={"n": 50})
    assert mc.status_code == 200, mc.text
    assert (tmp_path / "backtest" / body["backtest_id"] / "montecarlo.json").exists()


def test_delete_analysis_cascades_related_backtests(tmp_path: Path, monkeypatch):
    analysis = _make_analysis()
    analysis.save(tmp_path)
    bt_dir = run_backtest(LighterSignalC(), analysis).save(tmp_path)

    api_app = importlib.import_module("leadlag.api.app")
    monkeypatch.setattr(api_app, "DATA_DIR", tmp_path)
    monkeypatch.setattr(api_app, "COLLECTOR_PROC", None)
    monkeypatch.setattr(api_app, "PAPER_PROC", None)
    client = TestClient(api_app.app)

    assert bt_dir.exists()

    deleted = client.delete(f"/api/analyses/{analysis.analysis_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["removed_backtests"] == 1
    assert not (tmp_path / "analyses" / analysis.analysis_id).exists()
    assert not bt_dir.exists()


def test_build_from_raw_uses_batched_tick_scan(tmp_path: Path):
    ticks_dir = tmp_path / "ticks" / "2026-04-19"
    bbo_dir = tmp_path / "bbo" / "2026-04-19"
    ticks_dir.mkdir(parents=True)
    bbo_dir.mkdir(parents=True)

    tick_rows = []
    bbo_rows = []
    for i in range(500):
        ts = BASE_TS + i * 50
        okx_price = 100_000.0 + (25.0 if i >= 260 else 0.0)
        bybit_price = 100_001.0 + (22.0 if i >= 261 else 0.0)
        lighter_price = 50_000.0 + max(0, i - 266) * 2.2
        for venue, price in [
            ("OKX Perp", okx_price),
            ("Bybit Perp", bybit_price),
            ("Lighter Perp", lighter_price),
        ]:
            tick_rows.append({
                "ts_ms": ts,
                "price": price,
                "qty": 0.01,
                "side": "buy" if i % 2 == 0 else "sell",
                "venue": venue,
            })
            bbo_rows.append({
                "ts_ms": ts,
                "bid_price": price - 1.0,
                "bid_qty": 1.0,
                "ask_price": price + 1.0,
                "ask_qty": 1.0,
                "venue": venue,
            })

    pd.DataFrame(tick_rows).to_parquet(ticks_dir / "ticks_demo.parquet")
    pd.DataFrame(bbo_rows).to_parquet(bbo_dir / "bbo_demo.parquet")

    analysis = Analysis.build_from_raw(
        "20260419_000000",
        [str(ticks_dir / "ticks_demo.parquet")],
        [str(bbo_dir / "bbo_demo.parquet")],
        bin_size_ms=50,
        ema_span_bins=50,
        threshold_sigma=1.0,
        confirm_window_bins=5,
    )

    assert analysis.meta["n_ticks"] == len(tick_rows)
    assert analysis.quality["venues"]["Lighter Perp"]["ticks_total"] == 500
    assert analysis.quality["venues"]["Lighter Perp"]["side_buy_pct"] == 0.5
    assert analysis.vwap_df is not None
    assert len(analysis.vwap_df) == 500
    assert analysis.events.count >= 1


def test_public_batch_iterators_filter_by_date_and_venue(tmp_path: Path):
    ticks_dir = tmp_path / "ticks" / "2026-04-19"
    bbo_dir = tmp_path / "bbo" / "2026-04-19"
    ticks_dir.mkdir(parents=True)
    bbo_dir.mkdir(parents=True)

    pd.DataFrame([
        {"ts_ms": BASE_TS, "price": 100.0, "qty": 0.1, "side": "buy", "venue": "OKX Perp"},
        {"ts_ms": BASE_TS + 50, "price": 101.0, "qty": 0.1, "side": "sell", "venue": "Lighter Perp"},
    ]).to_parquet(ticks_dir / "ticks_demo.parquet")

    pd.DataFrame([
        {"ts_ms": BASE_TS, "bid_price": 99.5, "bid_qty": 1.0, "ask_price": 100.5, "ask_qty": 1.0, "venue": "OKX Perp"},
        {"ts_ms": BASE_TS + 50, "bid_price": 100.5, "bid_qty": 1.0, "ask_price": 101.5, "ask_qty": 1.0, "venue": "Lighter Perp"},
    ]).to_parquet(bbo_dir / "bbo_demo.parquet")

    tick_batches = list(iter_ticks_batches(tmp_path, date_from="2026-04-19", date_to="2026-04-20", venues=["OKX Perp"], batch_rows=1))
    bbo_batches = list(iter_bbo_batches(tmp_path, date_from="2026-04-19", date_to="2026-04-20", venues=["Lighter Perp"], batch_rows=1))

    assert sum(len(b) for b in tick_batches) == 1
    assert tick_batches[0]["venue"].iloc[0] == "OKX Perp"
    assert sum(len(b) for b in bbo_batches) == 1
    assert bbo_batches[0]["venue"].iloc[0] == "Lighter Perp"


def _make_analysis() -> Analysis:
    venues = ["OKX Perp", "Bybit Perp", "Lighter Perp", "MEXC Perp"]
    rows = []
    for i in range(80):
        ts = BASE_TS + i * 50
        leader_move = 25 if i >= 20 else 0
        follower_move = max(0, i - 20) * 2.5
        rows.append({
            "ts_ms": ts,
            "OKX Perp": 100_000 + leader_move,
            "Bybit Perp": 100_001 + leader_move * 0.9,
            "Lighter Perp": 50_000 + follower_move,
            "MEXC Perp": 50_005 + follower_move * 0.8,
        })
    vwap_df = pd.DataFrame(rows)
    vwap_df.index.name = "bin_idx"
    ema_df = vwap_df.copy()
    dev_df = vwap_df.copy()
    bbo_df = pd.DataFrame(
        {
            "ts_ms": vwap_df["ts_ms"],
            "venue": "Lighter Perp",
            "bid_price": vwap_df["Lighter Perp"] - 1.0,
            "bid_qty": 1.0,
            "ask_price": vwap_df["Lighter Perp"] + 1.0,
            "ask_qty": 1.0,
        }
    )
    event = {
        "event_id": 0,
        "bin_idx": 20,
        "ts_ms": int(vwap_df["ts_ms"].iloc[20]),
        "time_utc": "2024-04-27T00:26:41Z",
        "signal": "C",
        "direction": 1,
        "magnitude_sigma": 2.5,
        "leader": "confirmed",
        "leader_dev": 2.5,
        "anchor_leader": "OKX Perp",
        "confirmer_leader": "Bybit Perp",
        "confirmer_bin": 21,
        "confirmer_lag_ms": 50,
        "lagging_followers": ["Lighter Perp", "MEXC Perp"],
        "n_lagging": 2,
        "follower_metrics": {
            "Lighter Perp": {"lag_50_ms": 150, "lag_80_ms": 250, "hit": 1, "mfe_bps": 5.0, "mae_bps": -0.5}
        },
        "grid_results": {
            "Lighter Perp": {"0": {"500": {"gross_bps": 4.0, "net_bps": 3.0, "hit": 1, "fee_bps": 0.0}}}
        },
        "quality_flags_at_event": [],
    }
    price_window = {
        "bin_idx": 20,
        "rel_times_ms": [int((i - 20) * 50) for i in range(10, 31)],
        "venues": {venue: [float(vwap_df[venue].iloc[i]) for i in range(10, 31)] for venue in venues},
    }
    bbo_window = {
        "bin_idx": 20,
        "rel_times_ms": price_window["rel_times_ms"],
        "venues": {
            "Lighter Perp": {
                "bid": [float(vwap_df["Lighter Perp"].iloc[i] - 1.0) for i in range(10, 31)],
                "ask": [float(vwap_df["Lighter Perp"].iloc[i] + 1.0) for i in range(10, 31)],
                "spread_bps": [0.4 for _ in range(10, 31)],
            }
        },
    }
    quality = {
        "duration_s": 4.0,
        "t_start_ms": BASE_TS,
        "t_end_ms": BASE_TS + 79 * 50,
        "coverage_pct": {venue: 100.0 for venue in venues},
        "sigma_per_venue": {venue: 0.0001 for venue in venues},
        "venues": {
            venue: {
                "role": "leader" if venue in {"OKX Perp", "Bybit Perp"} else "follower",
                "ticks_total": 80,
                "ticks_per_s_avg": 20.0,
                "ticks_per_s_max": 20.0,
                "ticks_per_s_min_nonzero": 20.0,
                "bin_coverage_pct": 100.0,
                "bbo_total": 80 if venue == "Lighter Perp" else 0,
                "bbo_per_s_avg": 20.0 if venue == "Lighter Perp" else 0.0,
                "bbo_coverage_pct": 100.0 if venue == "Lighter Perp" else 0.0,
                "bbo_available": venue == "Lighter Perp",
                "median_price": 50_000.0,
                "price_deviation_from_leader_bps": 0.0,
                "reconnects": 0,
                "downtime_s": 0.0,
                "uptime_pct": 100.0,
                "zero_price_ticks": 0,
                "zero_qty_ticks": 0,
                "side_buy_pct": 0.5,
                "side_sell_pct": 0.5,
                "flag": "good",
                "flag_reasons": [],
            }
            for venue in venues
        },
        "timeline_gaps": [],
    }
    meta = {
        "analysis_id": "synthetic_abcdef12",
        "collection_id": "synthetic",
        "recording_id": "synthetic",
        "params": {"bin_size_ms": 50},
        "params_hash": "abcdef12",
        "collection_files": {"ticks": [], "bbo": []},
        "t_start_ms": BASE_TS,
        "t_end_ms": BASE_TS + 79 * 50,
        "duration_s": 4.0,
        "bin_size_ms": 50,
        "ema_span": 200,
        "threshold_sigma": 2.0,
        "venues": venues,
        "leaders": ["OKX Perp", "Bybit Perp"],
        "followers": ["Lighter Perp", "MEXC Perp"],
        "fees": {
            "OKX Perp": {"taker_bps": 5.0, "maker_bps": 2.0},
            "Bybit Perp": {"taker_bps": 5.5, "maker_bps": 2.0},
            "Lighter Perp": {"taker_bps": 0.0, "maker_bps": 0.0},
            "MEXC Perp": {"taker_bps": 2.0, "maker_bps": 0.0},
        },
        "bbo_available": {"OKX Perp": False, "Bybit Perp": False, "Lighter Perp": True, "MEXC Perp": False},
        "n_ticks": 320,
        "n_bbo": 80,
        "n_events": 1,
        "n_signal_a": 0,
        "n_signal_b": 0,
        "n_signal_c": 1,
        "created_at_utc": "2024-04-27T00:26:40Z",
        "source_data_layout_version": "analysis.v1",
    }
    return Analysis(
        "synthetic_abcdef12",
        meta,
        [event],
        quality,
        price_windows=[price_window],
        bbo_windows=[bbo_window],
        vwap_df=vwap_df,
        ema_df=ema_df,
        dev_df=dev_df,
        bbo_df=bbo_df,
    )
