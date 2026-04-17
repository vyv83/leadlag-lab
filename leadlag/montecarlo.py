"""Monte Carlo robustness checks for saved or in-memory backtest results."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from leadlag.contracts import write_json


@dataclass
class MonteCarloResult:
    backtest_id: str | None
    n_simulations: int
    method: str
    p_value: float
    percentile: float
    real_pnl: float
    median_sim_pnl: float
    pnl_5th: float
    pnl_95th: float
    prob_of_profit: float
    sim_equity_curves: list[list[float]]
    sim_final_pnls: list[float]
    sim_sharpes: list[float]
    sim_max_dds: list[float]

    def summary(self) -> dict:
        return {
            "p_value": self.p_value,
            "percentile": self.percentile,
            "real_pnl": self.real_pnl,
            "median_sim_pnl": self.median_sim_pnl,
            "pnl_5th": self.pnl_5th,
            "pnl_95th": self.pnl_95th,
            "prob_of_profit": self.prob_of_profit,
        }

    def to_dict(self) -> dict:
        return {
            "backtest_id": self.backtest_id,
            "n_simulations": self.n_simulations,
            "method": self.method,
            **self.summary(),
            "sim_equity_curves": self.sim_equity_curves,
            "sim_final_pnls": self.sim_final_pnls,
            "sim_sharpes": self.sim_sharpes,
            "sim_max_dds": self.sim_max_dds,
        }

    def save(self, backtest_dir: Path | str) -> Path:
        path = Path(backtest_dir) / "montecarlo.json"
        write_json(path, self.to_dict(), indent=2)
        return path


def run_monte_carlo(
    result: Any,
    n: int = 10_000,
    *,
    method: str = "trade_shuffle",
    block_size: int = 10,
    seed: int | None = 42,
    keep_curves: int = 1_000,
) -> MonteCarloResult:
    """Run robustness simulations over trade net PnL.

    ``result`` can be a BacktestResult or any object with ``trades`` and
    optional ``meta`` attributes.
    """
    trades = list(getattr(result, "trades", []) or [])
    returns = np.array([float(t.get("net_pnl_bps", 0.0)) for t in trades], dtype=float)
    returns = returns[np.isfinite(returns)]
    rng = np.random.default_rng(seed)
    n = int(n)
    if n <= 0:
        raise ValueError("n must be positive")

    if len(returns) == 0:
        sims = np.zeros((n, 0), dtype=float)
    else:
        sims = _simulate_returns(returns, n, method, block_size, rng)
    equity = sims.cumsum(axis=1) if sims.size else sims
    finals = equity[:, -1] if equity.shape[1] else np.zeros(n)
    sharpes = np.array([_sharpe(row) for row in sims])
    max_dds = np.array([_max_drawdown(row.cumsum()) for row in sims]) if sims.size else np.zeros(n)
    real_pnl = float(returns.sum()) if len(returns) else 0.0
    real_rank = float((finals <= real_pnl).mean() * 100.0) if len(finals) else 0.0
    p_value = float((finals >= real_pnl).mean()) if len(finals) else 1.0
    sample_n = min(int(keep_curves), n)
    sample_idx = np.linspace(0, n - 1, sample_n, dtype=int) if sample_n else []
    backtest_id = None
    meta = getattr(result, "meta", {}) or {}
    if isinstance(meta, dict):
        backtest_id = meta.get("backtest_id")
    return MonteCarloResult(
        backtest_id=backtest_id,
        n_simulations=n,
        method=method,
        p_value=p_value,
        percentile=real_rank,
        real_pnl=real_pnl,
        median_sim_pnl=float(np.median(finals)) if len(finals) else 0.0,
        pnl_5th=float(np.percentile(finals, 5)) if len(finals) else 0.0,
        pnl_95th=float(np.percentile(finals, 95)) if len(finals) else 0.0,
        prob_of_profit=float((finals > 0).mean()) if len(finals) else 0.0,
        sim_equity_curves=equity[sample_idx].round(6).tolist() if sample_n and equity.size else [],
        sim_final_pnls=finals.round(6).tolist(),
        sim_sharpes=sharpes.round(6).tolist(),
        sim_max_dds=max_dds.round(6).tolist(),
    )


def _simulate_returns(returns: np.ndarray, n: int, method: str, block_size: int, rng: np.random.Generator) -> np.ndarray:
    if method in {"trade_shuffle", "return_shuffle"}:
        return np.array([rng.permutation(returns) for _ in range(n)])
    if method == "block_bootstrap":
        block_size = max(1, int(block_size))
        rows = []
        for _ in range(n):
            picked = []
            while len(picked) < len(returns):
                start = int(rng.integers(0, len(returns)))
                block = returns[start:start + block_size]
                if len(block) < block_size:
                    block = np.concatenate([block, returns[: block_size - len(block)]])
                picked.extend(block.tolist())
            rows.append(picked[: len(returns)])
        return np.array(rows, dtype=float)
    raise ValueError(f"Unknown Monte Carlo method: {method}")


def _sharpe(vals: np.ndarray) -> float:
    std = float(vals.std(ddof=0))
    return float(vals.mean() / std) if std > 0 else 0.0


def _max_drawdown(equity: np.ndarray) -> float:
    if equity.size == 0:
        return 0.0
    peaks = np.maximum.accumulate(equity)
    dd = equity - peaks
    return float(dd.min())
