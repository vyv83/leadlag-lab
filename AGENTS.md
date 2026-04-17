# AGENTS.md

This repository is a local lead-lag trading research application. The next agent must treat this file as operational guidance, not as a replacement for the product plan.

## Source Of Truth Order

1. User task in [plan.md](/root/projects/leadlag-lab/plan.md), especially `ЧАСТЬ 1: СИНТЕЗИРОВАННОЕ ЗАДАНИЕ ПОЛЬЗОВАТЕЛЯ`.
2. Product/technical plan in [plan.md](/root/projects/leadlag-lab/plan.md).
3. Main implementation plan in [FULL_REWORK_PLAN_TO_10.md](/root/projects/leadlag-lab/FULL_REWORK_PLAN_TO_10.md).
4. Supplemental critique checklist in [CRITIQUE.md](/root/projects/leadlag-lab/CRITIQUE.md).

If these documents conflict, the original user goal wins over the plan, and the plan wins over current implementation.

## Model Mode Rule

Start the new implementation dialog on `gpt-5.4` with reasoning `xhigh`.

Mandatory stop rule:

- Complete and verify Phase A and Phase B from [FULL_REWORK_PLAN_TO_10.md](/root/projects/leadlag-lab/FULL_REWORK_PLAN_TO_10.md).
- Commit those changes.
- Stop and tell the user: `Переключи новый диалог на gpt-5.4 high для оставшейся реализации`.
- Do not switch earlier if core data contracts, session loading, Explorer, or Trade Inspector acceptance checks are still failing.

Rationale: Phase A/B are the highest-risk phases because they define data contracts, backtest integration, session artifacts, event loading, and trader-facing inspection UX. Later work can usually be done safely on `high`.

## Required Reading Before Editing

Before making code changes, read:

- [plan.md](/root/projects/leadlag-lab/plan.md)
- [FULL_REWORK_PLAN_TO_10.md](/root/projects/leadlag-lab/FULL_REWORK_PLAN_TO_10.md)
- [CRITIQUE.md](/root/projects/leadlag-lab/CRITIQUE.md)
- [README.md](/root/projects/leadlag-lab/README.md), if present
- relevant current source files for the phase being implemented

Do not implement from memory. Check the actual code and current behavior.

## Implementation Order

Use the phase order from `FULL_REWORK_PLAN_TO_10.md`:

- Phase A: core pipeline, session artifacts, `load_session`, backtest API path, tests.
- Phase B: Explorer and Trade Inspector UX.
- Phase C: Backtest and Monte Carlo.
- Phase D: Collector, Quality, Dashboard.
- Phase E: Jupyter strategy workflow.
- Phase F: Paper/realtime closure.

Paper trading is part of the final 10/10 target because it exists in the original user task. Do not start with paper trading, but do not delete it from the final scope.

## Product Bar

The target is not "pages exist". The target is that a user can open the app and intuitively:

- see whether data collection is healthy;
- understand which venues are alive or broken;
- inspect lead-lag events with price and BBO context;
- understand whether spread, fees, slippage, and latency destroy the edge;
- write a Python strategy in Jupyter and use the same logic in the app;
- run a realistic backtest;
- inspect every trade;
- run Monte Carlo robustness checks;
- decide what to change next without editing hidden files manually.

Every field, button, chart, table, and API response should serve one of those jobs.

## MCP And Docs

Context7 MCP has been configured globally for Codex on this machine:

```bash
codex mcp add context7 -- npx -y @upstash/context7-mcp
```

In a fresh session, use Context7 for current library documentation when touching FastAPI, PyArrow, DuckDB, Plotly, pandas, Pydantic, psutil, websockets, uvicorn, or Jupyter-related APIs.

Do not use Context7 as product truth. Product truth is the user's task and repository plans.

If Context7 is unavailable in a fresh session, continue from local code and official docs only when needed.

## Engineering Rules

- Do not create placeholder UI or empty routes just to satisfy a checklist.
- Do not silently drop fields from plan contracts.
- Do not make `events.json` carry large price/BBO arrays; use lazy window artifacts as specified.
- Keep UTC display consistent everywhere.
- Use structured API errors visible in UI.
- Preserve notebook-to-app strategy flow.
- Keep batch and realtime signal math consistent.
- Validate JSON/Parquet contracts where artifacts are written.
- Add or update tests with each phase.
- Run the narrow relevant tests before committing.

## Git Rules

- Baseline initial commit: `b590c81 Initial leadlag-lab snapshot`.
- Work in small phase commits.
- Do not rewrite history unless the user explicitly asks.
- Do not revert user changes.
- If unexpected unrelated changes appear, stop and ask the user how to proceed.

## Phase Acceptance

Use the acceptance checklist in [FULL_REWORK_PLAN_TO_10.md](/root/projects/leadlag-lab/FULL_REWORK_PLAN_TO_10.md) as the final gate.

Important early gates:

- `from leadlag import load_session, list_sessions, run_backtest, run_monte_carlo` works.
- `load_session(reference).events.filter(signal='C').count == 229` works on the reference session if available.
- Explorer can load all events without embedding all chart windows in the events table.
- Clicking an event opens a trader-readable view with leader/follower price, BBO, spread, entry/exit, fees/slippage, MFE/MAE, and reason fields.
- Backtest output contains inspectable trades, equity, stats, and Monte Carlo artifacts.

