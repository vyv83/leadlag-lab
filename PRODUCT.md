# LeadLag Lab — Product Context

`register: product`

## Product Purpose

LeadLag Lab is a local research workstation for lead-lag crypto trading.

Its job is not to "generate strategies from UI". Its job is to help a researcher:

1. collect raw market data,
2. turn that data into analyses,
3. inspect event quality and patterns,
4. develop strategies in Jupyter,
5. run realistic backtests,
6. validate robustness with Monte Carlo,
7. observe strategy behavior in paper trading.

The application serves the research workflow. It does not replace it.

## Primary User

The primary user is a technically capable researcher or trader who is comfortable with notebooks and Python code.

The user is exploring hypotheses, iterating quickly, and wants the UI to help with operational flow, validation, and inspection, not to hide the real mechanics.

## Core Product Principles

### Jupyter First

Notebook is the main strategy development surface.

- Strategy logic is real Python code.
- A strategy is a Python class, not a form builder, YAML config, or text prompt.
- The notebook writes the canonical `.py` strategy file.
- The UI consumes and runs that file.

### File Is Source of Truth

One identifier should stay aligned across notebook, Python file, and strategy id.

Examples:

- `lighter_c_bbo_v2.ipynb`
- `lighter_c_bbo_v2.py`
- `lighter_c_bbo_v2`

### UI Is For Analysis, Validation, and Operations

The application is optimized for:

- collector control,
- recording and analysis management,
- quality review,
- event exploration,
- backtesting,
- Monte Carlo validation,
- paper trading,
- trade inspection.

The application is not the primary place to author strategy logic from scratch.

### Domain First

The product is organized around entities and pipeline stages, not around arbitrary pages or dashboard widgets.

## Public Terminology

Use these terms in public UX:

- `Recording` = raw recorded market data
- `Analysis` = processed result of a recording

Do not use these as public UX terms:

- `Collection`
- `Session`

Internal API or Python names may still use legacy terms, but the user-facing contract should not.

## Core Workflow

```text
Dashboard
  -> Collector
  -> Recordings
  -> Quality
  -> Explorer
  -> Jupyter
  -> Strategy
  -> Backtest
  -> Monte Carlo
  -> Paper
  -> Trade
```

More concretely:

1. User starts or monitors collection.
2. Collector produces a `Recording`.
3. User creates one or more `Analysis` runs from that recording.
4. User checks quality and explores detected events.
5. If pattern looks promising, user formalizes strategy in Jupyter.
6. Strategy appears in the app and can be backtested on a selected analysis.
7. Good backtests can be stress-tested with Monte Carlo.
8. Robust strategies can be observed in paper trading.

## Core Entities

The product menu and navigation should be built around these entities:

- Collector
- Recording
- Analysis
- Strategy
- Notebook
- Backtest
- Monte Carlo
- Paper Run
- Trade

Important clarifications:

- `Venue` is a navigation filter and operational configuration surface, not a top-level domain entity.
- `Collector Run` is not treated as a standalone entity in the UI tree.
- `Backtest` belongs to `Strategy` in tree ownership, but references one `Analysis`.

## Product Rules

### Navigation

- Sidebar is always present.
- Quality, Explorer, Backtest, Monte Carlo, Paper, and Trade are detail surfaces, not top-level ownership roots.
- List views should show full lists when no entity is selected.

### Strategy Workflow

- Do not promote "simple strategy builder" flows as the primary path.
- Opening Jupyter is a first-class workflow action.
- Strategy params may be edited in UI as a convenience, but notebook-authored code remains canonical.

### Mutation UX

- No modal windows for core create/delete flows.
- Creation and run flows expand inline.
- Delete always uses inline confirmation with clear cascade consequences.
- Destructive actions must reflect true ownership and cascade behavior.

### Empty States

- First run must show a clear next step: collect data.
- If no strategies exist, UI should send the user to Jupyter, not to a fake builder.
- If no analysis or no backtest exists yet, the UI should explain the next pipeline step.

## Anti-Goals

Do not turn LeadLag Lab into:

- a no-code strategy builder,
- a page-centric admin panel detached from the pipeline,
- a systemd-monitoring dashboard pretending operations are the product,
- a UI that invents entities or actions unsupported by the real runtime.

## Source Documents

This file is a compact entry point. Detailed source material lives in:

- [README.md](README.md)
- [STRATEGY_DEVELOPMENT.md](STRATEGY_DEVELOPMENT.md)
- [13_ARCHITECTURE_DECISIONS.md](13_ARCHITECTURE_DECISIONS.md)
- [15_PIPELINE_AUDIT.md](15_PIPELINE_AUDIT.md)
- [16_DOMAIN_MODEL.md](16_DOMAIN_MODEL.md)
- [19_FRAME.md](19_FRAME.md)
