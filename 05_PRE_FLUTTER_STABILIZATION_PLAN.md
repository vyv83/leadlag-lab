# 05 - Pre-Flutter Stabilization Plan

Дата: 2026-04-17

Этот документ — единственный рабочий план перед переходом на Flutter.

Он объединяет выводы:

- `03_NEXT_ITERATION_REVIEW_TO_10.md`;
- `04_DEEP_AUDIT_REPORT.md`;
- текущего состояния кода и данных.

Цель: не довести старый HTML UI до идеала, а стабилизировать backend/API/data contracts и убрать ложные UI-состояния, чтобы Flutter строился на прочном основании.

## 0. Жёсткое Решение

Не чинить всё перед Flutter.

Перед Flutter исправляем только то, что:

- ломает core workflow;
- портит расчёты;
- врёт пользователю;
- делает API нестабильным для будущего Flutter-клиента;
- мешает создать demo-ready путь от raw data до backtest.

Всё остальное переносится в `06_FLUTTER_UI_REWORK_PLAN.md`.

## 1. Fix Before Flutter

Это обязательные P0/P1, без которых Flutter будет построен на песке.

### 1.1 Collections And Analysis API

Проблема:

- raw parquet есть;
- `data/sessions/` может отсутствовать;
- UI/API не умеет сделать analyzed session из raw collection.

Сделать:

- `GET /api/collections`;
- `POST /api/collections/{collection_id}/analyze`;
- optional `GET /api/analysis/jobs/{job_id}` если анализ станет async;
- Dashboard action `Run Analysis`;
- Collector action `Analyze this collection`;
- после анализа открыть `explorer.html?session={session_id}`.

Acceptance:

- На текущих raw parquet пользователь из UI получает saved session.

### 1.2 Demo-Ready Baseline

Проблема:

- нет сохранённых sessions/backtests/strategies;
- пользователь открывает почти пустое приложение.

Сделать:

- создать baseline strategy в `data/strategies/`;
- построить session из текущего raw data;
- запустить baseline backtest;
- Dashboard должен показывать latest collection -> latest session -> latest backtest.

Acceptance:

- Новый пользователь видит один полный рабочий путь без shell.

### 1.3 Collector Stale Status

Проблема:

- `.collector_status.json` может говорить `running: true`, хотя процесс умер;
- API смешивает file status и in-memory `COLLECTOR_PROC`.

Сделать:

- TTL для collector status, например 10-30 секунд;
- `stale: true`;
- computed `running_effective`;
- UI state `stale`;
- кнопка или endpoint очистки stale status;
- paper не должен уходить в pending из-за stale collector.

Acceptance:

- Устаревший status file не блокирует Start и не показывает зелёный running.

### 1.4 Dashboard Network Chart

Проблема:

- monitor пишет `net_sent/net_recv`;
- dashboard читает `net_down_bps/net_up_bps`;
- chart рисует нули.

Сделать:

- считать rates в monitor или API;
- привести fields к `net_down_bps`, `net_up_bps`;
- подписать units как `bytes/s` или `Mbps`.

Acceptance:

- Во время активного collector network chart не плоский ноль.

### 1.5 Collector Parameters Truthfulness

Проблема:

- collector UI не должен смешивать raw collection и analysis params;
- `rotation_s` относится к raw collection;
- `bin_size_ms` относится к analysis и не должен выглядеть как параметр записи raw parquet.

Сделать:

- оставить в collector UI только реальные параметры raw collection;
- `rotation_s` реально поддерживать в collector CLI/status;
- `bin_size_ms` задавать только при создании Analysis.

- `--rotation-s` в collector CLI;
- writer_task принимает rotation;
- status показывает фактическую rotation.

Acceptance:

- Ни одно поле запуска collector не является декоративным.

### 1.6 Venue Connected But No Data

Проблема:

- venue может быть WS-connected, но иметь 0 ticks/BBO;
- UI показывает `ok` и `uptime 100%`.

Сделать:

- status `connected_no_data` после N секунд без tick;
- severity warning в Dashboard/Collector;
- quality flag `connected_no_data`;
- проверить Aster parser/subscription.

Acceptance:

- Aster-like state не отображается как healthy.

### 1.7 Explorer Filter Correctness

Проблемы:

- follower dropdown по умолчанию фильтрует events;
- Reset не сбрасывает follower;
- OKX/Bybit filter неверно пропускает confirmed events;
- keyboard nav срабатывает внутри inputs/selects.

Сделать:

- разделить `chart follower` и `filter by follower`;
- default event list = all events;
- Reset clears all filters;
- OKX/Bybit checks use `anchor_leader`/actual leader, not `leader === "confirmed"`;
- keyboard nav ignores `input`, `select`, `textarea`.

Acceptance:

- Первый open Explorer показывает все events.
- Arrow keys in input не меняют selected event.

### 1.8 Backtest Fee And Position Correctness

Проблемы:

- limit fee policy конфликтует между plan/code comment/paper;
- reverse mode очищает open position без close trade.

Сделать:

- принять один explicit contract по limit fee;
- привести backtest, paper, UI labels, comments к одному контракту;
- если выбираем plan.md: limit = maker x2;
- если выбираем "exit always market": обновить plan/reference docs и UI labels;
- reverse mode должен генерировать close trade с `exit_reason="reversed"`.

Acceptance:

- test фиксирует limit fee contract;
- test фиксирует reverse close trade.

### 1.9 Monte Carlo Honesty

Проблемы:

- default `trade_shuffle` вырожден по final PnL;
- small-n p-value вводит в заблуждение;
- Run button можно нажать повторно.

Сделать:

- default method = bootstrap with replacement или block bootstrap;
- `trade_shuffle` использовать как order/drawdown robustness, не final edge significance;
- warning when `n_trades < 20`;
- disable Run while executing;
- hide/show method-specific controls.

Acceptance:

- Default Monte Carlo не имеет degenerate final PnL distribution при N > 1.
- UI предупреждает при малом числе сделок.

### 1.10 Paper Honesty Before Full IPC

Проблемы:

- collector IPC не реализован;
- realtime detector не даёт Signal C;
- paper может выглядеть running, но не торговать.

Сделать минимум:

- если collector running и IPC нет, UI явно показывает blocked state;
- stale collector не должен блокировать paper;
- paper page объясняет supported signal mode;
- realtime Signal C parity занести как blocker для real paper/live.

Preferred:

- реализовать collector -> paper IPC;
- реализовать realtime Signal C.

Acceptance minimum:

- Paper не молчит в `collector_ipc_pending`; пользователь видит почему trades нет.

## 2. Make Honest Before Flutter

Эти пункты не делают legacy UI красивым, но убирают ложь.

- Dashboard strategy card показывает count, не placeholder.
- Jupyter link либо работает через API/config, либо показывает "not configured".
- Net recv/sent cards имеют units.
- Empty states говорят next action.
- API errors показываются readable, не raw alert/raw JSON.
- Backtest zero-trades и no-session states не ломают charts.
- Quality negative values не окрашиваются как error только из-за знака.
- Trade Inspector не показывает misleading `MFE +0.00 @ 0ms`, если MFE не было.

## 3. Carry To Flutter

Не делать глубоко в legacy HTML UI:

- полный visual redesign;
- идеальная навигация;
- responsive/mobile polish;
- full Strategy source editor;
- Strategy builder;
- Backtest comparison;
- advanced table virtualization;
- full Quality timeline visualization;
- trade loss explanation engine;
- paper-vs-backtest overlay;
- global help/tooltips everywhere.

Эти задачи проектируются в `06_FLUTTER_UI_REWORK_PLAN.md`.

## 4. Do Not Fix In Legacy UI Unless Blocking

Не тратить время до Flutter на:

- глубокую красоту CSS;
- полную унификацию всех таблиц;
- сложную pagination framework;
- pixel-perfect chart layout;
- новые decorative components;
- mobile UX для legacy UI.

Legacy HTML должен стать truthful debug/control UI, не финальным продуктом.

## 5. Implementation Order

### S1 - Analysis Path

1. Add collection discovery.
2. Add analysis endpoint.
3. Add Dashboard/Collector `Run Analysis`.
4. Save current raw sample as session.
5. Add tests.

### S2 - Demo Baseline

1. Add baseline strategy.
2. Run baseline backtest.
3. Make Dashboard show complete path.
4. Add empty-state guidance.

### S3 - Ops Truth

1. Stale collector status.
2. Network rates.
3. Collector parameter truthfulness.
4. Venue `connected_no_data`.
5. Process state cleanup.

### S4 - Research Truth

1. Explorer filters.
2. Backtest fee contract.
3. Reverse mode.
4. Monte Carlo method/default/warnings.
5. Trade Inspector misleading MFE/MAE display.

### S5 - Paper Honesty

1. Stale collector interaction.
2. Clear blocked state for IPC pending.
3. Document/show realtime signal limitations.
4. Decide if IPC/Signal C are before Flutter or first backend task during Flutter.

## 6. Tests Required Before Flutter

Minimum tests:

- `test_collections_list_from_raw_parquet`;
- `test_analysis_endpoint_creates_session`;
- `test_collector_status_stale_returns_not_running`;
- `test_monitor_history_has_network_rates`;
- `test_explorer_filter_logic_default_all_events`;
- `test_explorer_keyboard_nav_ignores_inputs`;
- `test_limit_fee_contract`;
- `test_reverse_mode_generates_reversed_close_trade`;
- `test_montecarlo_default_not_degenerate`;
- `test_paper_ipc_pending_is_reported_as_blocked`.

## 7. Gate To Start Flutter

Flutter can start when:

- [ ] `GET /api/collections` works.
- [ ] `Run Analysis` creates a session from raw parquet.
- [ ] Dashboard shows latest collection/session/backtest.
- [ ] Explorer opens all events by default.
- [ ] Backtest runs from UI against baseline strategy.
- [ ] Trade Inspector opens a baseline trade.
- [ ] Monte Carlo default is honest and non-degenerate.
- [ ] Collector stale status is handled.
- [ ] Network chart uses real rates.
- [ ] Collector UI has no ignored params.
- [ ] Venue with 0 ticks is warning, not ok.
- [ ] P0 tests pass.

Do not wait for:

- perfect legacy UI;
- full Strategy editor;
- full Paper/live readiness;
- full mobile polish;
- Flutter-level visual design.
