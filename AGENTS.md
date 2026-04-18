# AGENTS.md

This repository is a local lead-lag trading research application. The next agent must treat this file as operational guidance, not as a replacement for the product plan.

## Source Of Truth Order

1. User task in [plan.md](/root/projects/leadlag-lab/plan.md), especially `ЧАСТЬ 1: СИНТЕЗИРОВАННОЕ ЗАДАНИЕ ПОЛЬЗОВАТЕЛЯ`.
2. Product/technical plan in [plan.md](/root/projects/leadlag-lab/plan.md).
3. Active pre-Flutter implementation plan in [05_PRE_FLUTTER_STABILIZATION_PLAN.md](/root/projects/leadlag-lab/05_PRE_FLUTTER_STABILIZATION_PLAN.md).
4. Current iteration review in [03_NEXT_ITERATION_REVIEW_TO_10.md](/root/projects/leadlag-lab/03_NEXT_ITERATION_REVIEW_TO_10.md).
5. Supplemental independent audit in [04_DEEP_AUDIT_REPORT.md](/root/projects/leadlag-lab/04_DEEP_AUDIT_REPORT.md).
6. Historical full rework plan in [02_FULL_REWORK_PLAN_TO_10.md](/root/projects/leadlag-lab/02_FULL_REWORK_PLAN_TO_10.md).
7. Legacy critique checklist in [91_LEGACY_CRITIQUE.md](/root/projects/leadlag-lab/91_LEGACY_CRITIQUE.md).

If these documents conflict, the original user goal wins over the plan, and the plan wins over current implementation.

## Model Mode Rule

Start the new implementation dialog on `gpt-5.4` with reasoning `xhigh`.

Mandatory stop rule:

- Complete and verify the active pre-Flutter gate in [05_PRE_FLUTTER_STABILIZATION_PLAN.md](/root/projects/leadlag-lab/05_PRE_FLUTTER_STABILIZATION_PLAN.md).
- Commit those changes.
- Stop and ask the user before starting the Flutter implementation from [06_FLUTTER_UI_REWORK_PLAN.md](/root/projects/leadlag-lab/06_FLUTTER_UI_REWORK_PLAN.md).
- Do not start Flutter while core data/API contracts, analysis creation, collector truthfulness, Explorer filters, backtest correctness, or Monte Carlo honesty checks are still failing.

Rationale: the pre-Flutter gate is the highest-risk stage because it defines the stable API and truthfulness contract that the new Flutter UI will depend on.

## Required Reading Before Editing

Before making code changes, read:

- [plan.md](/root/projects/leadlag-lab/plan.md)
- [00_DOCS_PIPELINE.md](/root/projects/leadlag-lab/00_DOCS_PIPELINE.md)
- [05_PRE_FLUTTER_STABILIZATION_PLAN.md](/root/projects/leadlag-lab/05_PRE_FLUTTER_STABILIZATION_PLAN.md)
- [03_NEXT_ITERATION_REVIEW_TO_10.md](/root/projects/leadlag-lab/03_NEXT_ITERATION_REVIEW_TO_10.md)
- [04_DEEP_AUDIT_REPORT.md](/root/projects/leadlag-lab/04_DEEP_AUDIT_REPORT.md)
- [02_FULL_REWORK_PLAN_TO_10.md](/root/projects/leadlag-lab/02_FULL_REWORK_PLAN_TO_10.md)
- [README.md](/root/projects/leadlag-lab/README.md), if present
- relevant current source files for the phase being implemented

Do not implement from memory. Check the actual code and current behavior.

## Implementation Order

Use the active pre-Flutter order from `05_PRE_FLUTTER_STABILIZATION_PLAN.md`:

- S1: Analysis path.
- S2: Demo baseline.
- S3: Ops truth.
- S4: Research truth.
- S5: Paper honesty.

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

## Pre-Flutter Acceptance

Use the acceptance checklist in [05_PRE_FLUTTER_STABILIZATION_PLAN.md](/root/projects/leadlag-lab/05_PRE_FLUTTER_STABILIZATION_PLAN.md) as the next gate before Flutter.

Important early gates:

- `from leadlag import load_session, list_sessions, run_backtest, run_monte_carlo` works.
- `load_session(reference).events.filter(signal='C').count == 229` works on the reference session if available.
- Explorer can load all events without embedding all chart windows in the events table.
- Clicking an event opens a trader-readable view with leader/follower price, BBO, spread, entry/exit, fees/slippage, MFE/MAE, and reason fields.
- Backtest output contains inspectable trades, equity, stats, and Monte Carlo artifacts.
