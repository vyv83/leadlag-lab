# 06 - Flutter UI Rework Plan

Дата: 2026-04-17

Этот документ описывает переход на Flutter после `05_PRE_FLUTTER_STABILIZATION_PLAN.md`.

Цель: полностью переосмыслить UI/UX, не потеряв ни одной важной функции текущего приложения, но перестав тащить за собой ограничения старого HTML/vanilla JS интерфейса.

## 0. Gate

Flutter не начинается, пока не пройден gate из `05_PRE_FLUTTER_STABILIZATION_PLAN.md`.

Причина:

- Flutter должен быть клиентом к стабильному API;
- нельзя строить новый красивый UI поверх stale status, broken analysis path и неверных расчётов;
- нельзя переделывать старый UI до идеала, если он всё равно будет заменён.

## 1. Product Goal

Новый Flutter UI должен быть не "страницы с таблицами", а рабочее место трейдера:

- видно, живы ли данные;
- видно, готова ли analysis session;
- видно, где edge;
- понятно, где fees/spread/slippage убивают edge;
- удобно писать/подхватывать Python strategy через Jupyter workflow;
- удобно запускать и сравнивать backtests;
- каждая сделка объяснима;
- Monte Carlo не просто рисуется, а помогает принять решение;
- Paper показывает drift от backtest и честно сообщает ограничения.

## 2. What Must Not Be Lost

Из legacy UI сохранить и расширить:

- Dashboard system/process/collector/paper summary;
- Collector start/stop/status/log/files;
- Quality venue metrics and flags;
- Explorer event list, filters, BBO overlay, lag markers, followers table;
- Trade mode in Explorer;
- Strategy list and backtest run;
- Backtest equity layers, stats, trades, distributions;
- Trade Inspector leader/follower/BBO/entry/exit/MFE/MAE/fees/slippage;
- Monte Carlo methods/charts/cards;
- Paper status, signals, positions, trades, equity;
- Jupyter entry point.

## 3. New Navigation Model

Use a pipeline-first navigation:

1. Home / Pipeline
2. Collect
3. Analyze
4. Explore
5. Strategies
6. Backtests
7. Trade Inspector
8. Robustness
9. Paper
10. Quality
11. Jupyter

Every screen should show:

- current state;
- primary next action;
- errors/blockers;
- last updated timestamp;
- link back to related artifacts.

## 4. Flutter Screen Map

### 4.1 Pipeline Home

Replaces legacy Dashboard as the main entry point.

Top sections:

- Platform status;
- Collector status;
- Latest collection;
- Latest analysis session;
- Latest strategy;
- Latest backtest;
- Paper status.

Primary CTA depends on state:

- no raw data -> `Start Collection`;
- raw data but no session -> `Run Analysis`;
- session but no strategy -> `Open Jupyter / Create Strategy`;
- strategy but no backtest -> `Run Backtest`;
- backtest exists -> `Inspect Results`;
- ready -> `Start Paper`.

### 4.2 Collect

Replaces Collector page.

Must include:

- venue health cards;
- compact live table;
- logs drawer;
- current files;
- start/stop/restart;
- no-data warnings;
- stale status recovery.

Avoid:

- giant always-visible 16-column table as primary UI.

### 4.3 Analyze

New explicit screen.

Must include:

- collections list;
- raw file summary;
- analysis params;
- run/analyze progress;
- result session card;
- quality preview;
- open Explorer CTA.

### 4.4 Explore

Most important research screen.

Layout:

- left event list with virtualized rows;
- top filter bar with chips;
- main two/three-panel chart;
- follower metrics drawer/table;
- event verdict panel.

Must fix from legacy:

- follower chart selector separate from follower filter;
- all events shown by default;
- BBO overlay clear;
- no-BBO states explicit;
- active filters visible;
- keyboard shortcuts scoped.

### 4.5 Strategies

Strategy lifecycle screen.

Must include:

- strategy library;
- source preview;
- validation status;
- params as form;
- advanced JSON override collapsed;
- latest backtest summary;
- Open in Jupyter;
- Run Backtest;
- Run Paper if ready.

Later:

- simple strategy builder;
- source editor if useful.

### 4.6 Backtests

Decision-grade backtest view.

Must include:

- verdict cards;
- equity layers;
- drawdown;
- fees/slippage impact;
- trade table with virtualization;
- filters sync charts;
- venue/signal/spread breakdown;
- open trade;
- run robustness.

### 4.7 Trade Inspector

Must answer: why did this trade win or lose?

Must include:

- leader chart;
- follower chart;
- BBO/spread panel;
- entry/exit;
- SL/TP lines;
- MFE/MAE markers;
- execution breakdown;
- fees/slippage/spread explanation;
- prev/next;
- back to event/backtest.

### 4.8 Robustness

Monte Carlo and robustness.

Must include:

- method selector with explanations;
- warning for small sample;
- non-degenerate default;
- percentile bands;
- final PnL, Sharpe, max DD histograms;
- real markers on all histograms;
- p-value explained plainly.

### 4.9 Paper

Must include:

- readiness checklist;
- live status;
- blocked state if IPC unavailable;
- venue connectivity;
- recent signals;
- open positions;
- paper trades;
- paper vs backtest drift.

### 4.10 Quality

Must answer in 10 seconds: can this data be trusted?

Must include:

- overall verdict;
- venue flags;
- ticks/BBO coverage;
- gaps timeline;
- BBO staleness/spread;
- price consistency;
- actionable recommendations.

## 5. API Contracts Flutter Needs

Flutter should not read raw files directly.

Required stable APIs:

- `GET /api/collections`;
- `POST /api/collections/{id}/analyze`;
- `GET /api/sessions`;
- `GET /api/sessions/{id}/meta`;
- `GET /api/sessions/{id}/events`;
- `GET /api/sessions/{id}/event/{bin_idx}`;
- `GET /api/sessions/{id}/quality`;
- `GET /api/strategies`;
- `GET /api/strategies/{name}`;
- `POST /api/strategies/validate`;
- `POST /api/strategies/save`;
- `GET /api/backtests`;
- `POST /api/backtests/run`;
- `GET /api/backtests/{id}/meta`;
- `GET /api/backtests/{id}/stats`;
- `GET /api/backtests/{id}/equity`;
- `GET /api/backtests/{id}/trades`;
- `GET /api/backtests/{id}/trade/{trade_id}`;
- `POST /api/backtests/{id}/montecarlo/run`;
- `GET /api/backtests/{id}/montecarlo`;
- `GET /api/collector/status`;
- `POST /api/collector/start`;
- `POST /api/collector/stop`;
- `GET /api/collector/log`;
- `GET /api/collector/files`;
- `GET /api/paper/status`;
- `POST /api/paper/start`;
- `POST /api/paper/stop`;
- `GET /api/paper/signals`;
- `GET /api/paper/trades`;
- `GET /api/paper/equity`;
- `GET /api/paper/positions`;
- `GET /api/system/stats`;
- `GET /api/system/history`;
- `GET /api/system/processes`;
- `GET /api/system/jupyter`.

## 6. State Model

Use explicit states:

- `missing`;
- `ready`;
- `running`;
- `stale`;
- `blocked`;
- `error`;
- `empty`;
- `loading`.

Avoid ambiguous booleans like only `running: true/false`.

Every stale/blocker state must include:

- reason;
- timestamp;
- suggested action.

## 7. Migration Strategy

Do not big-bang rewrite all screens.

### Flutter MVP 1

- App shell;
- Pipeline Home;
- Explore.

Why:

- Home validates the whole workflow;
- Explore validates the hardest research UI.

### Flutter MVP 2

- Backtests;
- Trade Inspector;
- Robustness.

### Flutter MVP 3

- Strategies;
- Analyze;
- Collect;
- Quality.

### Flutter MVP 4

- Paper;
- Jupyter integration polish;
- final responsive/desktop polish.

## 8. Legacy UI Policy

Keep legacy HTML UI as debug fallback until Flutter has parity.

Do not add major new UX to legacy unless:

- it fixes a lie;
- it fixes data correctness;
- it unblocks Flutter API;
- it is required for pre-Flutter gate.

After Flutter parity:

- hide legacy UI behind `/ui-legacy/` or keep only for debugging;
- new primary route should point to Flutter app.

## 9. Definition Of Done For Flutter

Flutter UI reaches 10/10 when:

- user can complete the whole workflow without shell;
- every primary screen has clear next action;
- no screen silently displays stale data as healthy;
- Explorer makes events understandable;
- Backtest explains edge after fees/slippage/spread;
- Trade Inspector explains individual trades;
- Monte Carlo is statistically honest;
- Paper state is honest and comparable to backtest;
- all API errors are visible and actionable;
- large event/trade tables stay responsive.
