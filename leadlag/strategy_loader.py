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


def export_strategy(cls, path: str | Path) -> Path:
    """Export a Strategy subclass defined in a notebook to a .py file.

    Searches IPython's input history for the cell where ``cls`` was defined
    and writes the full cell content (imports + class + helpers) as a
    standalone ``.py`` file loadable by ``load_strategy()``.

    Falls back to ``inspect.getsource()`` when not running inside Jupyter.

    Usage (in a notebook cell)::

        export_strategy(MyStrategy, '../data/strategies/my_strategy.py')
    """
    path = Path(path)
    source = _extract_strategy_source(cls)
    compile(source, str(path), "exec")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    load_strategy(path)
    return path


def _extract_strategy_source(cls) -> str:
    """Get the full source of the cell defining *cls*."""
    class_name = cls.__name__

    # --- try IPython input history first (works in Jupyter) ------------------
    try:
        ip = __builtins__["get_ipython"]() if isinstance(__builtins__, dict) else getattr(__builtins__, "get_ipython", None)
        if ip is None:
            raise NameError
    except (NameError, KeyError, TypeError):
        ip = None

    if ip is None:
        try:
            # maybe get_ipython is in caller's globals (Jupyter injects it)
            import builtins
            ip = getattr(builtins, "get_ipython", lambda: None)()
        except Exception:
            ip = None

    if ip is not None:
        history = ip.user_ns.get("In") or []
        # walk backwards to find the most recent cell defining this class
        for cell_source in reversed(list(history)):
            if not isinstance(cell_source, str):
                continue
            if f"class {class_name}" in cell_source and "Strategy" in cell_source:
                return cell_source.rstrip() + "\n"

    # --- fallback: inspect.getsource (works for file-backed classes) ---------
    source = inspect.getsource(cls)
    # getsource returns only the class; prepend detected imports
    leadlag_names = [n for n in ("Strategy", "Order", "Event", "Context", "BboSnapshot") if n in source]
    header = f"from leadlag import {', '.join(leadlag_names)}\n\n\n" if leadlag_names else ""
    return header + source.rstrip() + "\n"


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
