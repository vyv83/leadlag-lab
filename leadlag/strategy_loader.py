"""Load a Strategy subclass from a .py file with validation.

Usage:
    from leadlag import load_strategy
    strat = load_strategy('data/strategies/my_strategy.py')
"""
from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

from leadlag.strategy import Strategy


def load_strategy(path: str | Path) -> Strategy:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Strategy file not found: {path}")

    spec = importlib.util.spec_from_file_location(f"leadlag_strategy_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load strategy module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    strat_classes = [
        obj for name, obj in vars(mod).items()
        if inspect.isclass(obj) and issubclass(obj, Strategy) and obj is not Strategy
    ]
    if not strat_classes:
        raise ValueError(f"{path}: no Strategy subclass defined")
    if len(strat_classes) > 1:
        raise ValueError(f"{path}: multiple Strategy subclasses ({[c.__name__ for c in strat_classes]}); expected one")

    cls = strat_classes[0]

    if not callable(getattr(cls, "on_event", None)):
        raise ValueError(f"{cls.__name__}: must define on_event(event, ctx)")

    sig = inspect.signature(cls.on_event)
    positional = [p for p in sig.parameters.values() if p.name != "self"]
    if len(positional) < 2:
        raise ValueError(
            f"{cls.__name__}.on_event must accept (event, ctx); got signature {sig}"
        )

    return cls()


def save_strategy_source(source: str, path: str | Path) -> Path:
    """Save a strategy .py file from a notebook cell and validate it immediately."""
    path = Path(path)
    compile(source, str(path), "exec")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    load_strategy(path)
    return path


def list_strategies(directory: str | Path = "data/strategies") -> list[dict]:
    root = Path(directory)
    if not root.is_dir():
        return []
    rows = []
    for path in sorted(root.glob("*.py")):
        row = {"path": str(path), "name": path.stem, "valid": True, "error": None}
        try:
            strategy = load_strategy(path)
            row.update({
                "name": getattr(strategy, "name", path.stem),
                "version": getattr(strategy, "version", ""),
                "description": getattr(strategy, "description", ""),
                "params": getattr(strategy, "params", {}),
            })
        except Exception as exc:
            row["valid"] = False
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return rows
