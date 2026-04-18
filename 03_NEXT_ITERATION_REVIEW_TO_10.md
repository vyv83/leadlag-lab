# Leadlag-lab — ревью следующей итерации и план доработок до 10/10

Дата ревью: 2026-04-17

Этот документ новый. Он не заменяет `02_FULL_REWORK_PLAN_TO_10.md` и не правит старые планы. Его задача — оценить текущую реализацию после уже сделанных доработок: что реально закрыто, что сделано формально, что не сделано, где продукт ушёл от исходной задачи пользователя, какие есть глюки, и что нужно чинить в следующей итерации.

## 0. Источники истины

Приоритеты источников:

1. `plan.md`, начало файла, раздел "Синтезированное задание пользователя" — главный источник истины.
2. Остальной `plan.md` — техническое описание целевого продукта.
3. `02_FULL_REWORK_PLAN_TO_10.md` — предыдущий план исправлений.
4. Фактический код, UI, тесты и локальные данные в текущей папке `leadlag-lab`.

Главная пользовательская задача не изменилась: нужен не набор страниц и не девелоперский scaffold, а локальное рабочее место алготрейдера для lead-lag research/trading. Пользователь должен без ручного ковыряния файлов пройти путь:

1. Собрать tick/BBO данные.
2. Увидеть, что данные качественные.
3. Запустить анализ и получить сессию событий.
4. Понять, какие лидеры и followers дают edge.
5. В Jupyter написать произвольную Python-стратегию.
6. Сохранить стратегию так, чтобы она появилась в приложении.
7. Запустить честный backtest с fees/slippage/spread/limit fill/SL/TP.
8. Разобрать equity, Monte Carlo и каждую сделку.
9. Перейти в paper/live на той же логике `Strategy.on_event()`.

## 1. Короткий вердикт

Предыдущая итерация существенно продвинула проект: появились реальные контракты session/backtest, BBO windows, Trade Inspector, Monte Carlo page, collector status/log, paper page и набор тестов. Это уже не тот пустой scaffold, который критиковался в `02_FULL_REWORK_PLAN_TO_10.md`.

Но продукт всё ещё не решает задачу пользователя на 10/10. Он ближе к "технически связанный прототип с большим количеством таблиц", чем к "наглядная, удобная, безключная, отзывчивая рабочая станция трейдера".

Главная проблема текущей итерации: многие пункты появились как факт наличия файла/страницы/эндпоинта, но пользовательский пайплайн всё ещё рвётся в нескольких местах.

Текущая общая оценка: 4.8/10.

| Область | Оценка сейчас | Комментарий |
|---|---:|---|
| Соответствие исходной задаче пользователя | 4/10 | Модули появились, но цельный workflow не доведён |
| Backend contracts | 6/10 | Session/backtest артефакты лучше, но API и качество данных неполные |
| Collector | 5/10 | Данные собирает, но статус/параметры/процессы ненадёжны |
| Analysis/session pipeline | 6/10 | Из raw parquet строится session, но из UI это не доступно |
| Jupyter workflow | 3/10 | Ноутбуки есть, helper есть, но интеграция с UI слабая |
| Strategy lifecycle | 3/10 | Список есть, создания/редактирования/сравнения почти нет |
| Backtest correctness | 6/10 | Базово работает, есть важные edge-case баги |
| Explorer UX | 5/10 | BBO overlay появился, но фильтры и фокус пользователя проблемные |
| Backtest/Trade UX | 5/10 | Уже полезно, но ещё не decision-grade |
| Monte Carlo | 4/10 | UI есть, но дефолтная математика вводит в заблуждение |
| Data Quality | 5/10 | Много полей, но часть метрик имитационная/неполная |
| Paper/realtime | 2/10 | Главный путь через collector IPC не реализован |
| Process architecture | 3/10 | systemd + in-memory Popen вместо устойчивого процесса |
| Tests/acceptance proof | 4/10 | 13 тестов проходят, но они в основном контрактные и синтетические |
| UI/UX в целом | 4/10 | Нагромождение таблиц, слабая навигация, мало подсказок "что делать дальше" |

## 2. Что проверено в этой итерации

Фактические проверки:

- Прочитаны `plan.md`, `02_FULL_REWORK_PLAN_TO_10.md`, `README.md`, `90_PROGRESS_LOG.md`, `91_LEGACY_CRITIQUE.md`.
- Проверены API routes в `leadlag/api/app.py`.
- Проверены `session.py`, `backtest/engine.py`, `montecarlo.py`, collector, monitor, paper, strategy loader.
- Проверены все HTML-страницы в `leadlag/ui/`.
- Запущены тесты через venv: `13 passed in 2.36s`.
- Проверена текущая папка `data/`: есть raw parquet и IPC/status файлы, но нет `data/sessions/`, `data/backtest/`, `data/strategies/`.
- Пробно построена session из текущих raw parquet во временную директорию: build успешный, 22 events, 10 Signal C, 11 venues, все session artifacts сохранились.
- Проверен фактический stale collector status: `.collector_status.json` говорит `running: true`, но `leadlag-collector` процесс не найден, статус устарел.
- Найден конкретный баг сетевого графика: monitor пишет `net_sent/net_recv`, dashboard читает `net_down_bps/net_up_bps`, поэтому график сети фактически рисует нули.

## 3. Что уже сделано после предыдущего плана

### 3.1 Backend/session/backtest

Сделано:

- `Session.build_from_raw()` теперь строит `price_windows.json`, `bbo_windows.json`, `vwap.parquet`, `ema.parquet`, `dev.parquet`, `bbo.parquet`, `metrics.parquet`, `grid.parquet`, `ci.json`.
- `load_session()` лениво подгружает windows и frames.
- `/api/backtests/run` теперь может запустить backtest по сохранённой session, если session уже есть.
- Backtest trades содержат entry/exit VWAP/Exec, slippage entry/exit, fee entry/exit, spread entry/exit, MFE/MAE, exit reason.
- Backtest stats расширены: profit factor, drawdown, win/loss, avg hold, MFE/MAE, by_signal, by_venue, by_direction, by_spread_bucket.
- `run_monte_carlo()` и endpoint `/api/backtests/{id}/montecarlo/run` появились.

Оценка: стало заметно лучше, но ещё не "trustworthy trading engine".

### 3.2 UI

Сделано:

- Dashboard показывает system cards, CPU/RAM/Network charts, pings, processes, collector venues, latest sessions/backtests, files.
- Collector page показывает venue selection, start/stop/restart, status, live table, log, files.
- Explorer получил session dropdown, filters, event table, BBO overlay, lag markers, trade mode, followers table.
- Backtest page получил equity layers, drawdown subplot, histograms/scatters, breakdown tables, filters, trade links.
- Trade Inspector получил chart with leader/follower/BBO/entry/exit/MFE/MAE annotations и execution side panel.
- Monte Carlo page создан.
- Quality page расширен до venue summary, charts, timeline gaps, BBO table.
- Paper page создан.

Оценка: страницы есть, но UX ещё выглядит как инженерный мониторинг, а не как удобное рабочее место трейдера.

### 3.3 Collector/monitor/paper

Сделано:

- Collector пишет raw parquet, `.collector_status.json`, `.collector_log.jsonl`.
- Monitor daemon пишет `.system_history.jsonl`, `.ping_cache.json`.
- API умеет читать pings, files, processes, collector log/status.
- Paper daemon и UI появились.

Оценка: как прототип работает, но операционная надёжность низкая.

### 3.4 Tests

Сделано:

- Есть 13 тестов, все проходят.
- Тесты покрывают synthetic session/backtest/Monte Carlo API, UI-contract strings, ops endpoints, Jupyter helpers, paper endpoints.

Недостаток:

- Тесты в основном проверяют наличие строк/эндпоинтов, а не реальный браузерный UX, Plotly rendering, performance, stale states, real data acceptance.

## 4. Что не сделано или сделано формально

### 4.1 Нет UI-пути "raw data -> analyzed session"

Это главный разрыв пайплайна.

Факт:

- В `data/` сейчас есть raw parquet: `ticks/2026-04-17/...` и `bbo/2026-04-17/...`.
- `data/sessions/` отсутствует.
- `data/backtest/` отсутствует.
- `data/strategies/` отсутствует.
- В API нет `POST /api/sessions/{id}/analyze`.
- В UI нет кнопки `Run Analysis`, которая реально строит session из raw collection.

Почему это критично:

- Пользователь может собрать данные, но не может из приложения перейти к Explorer.
- Dashboard показывает `Open Latest Session`, но session нет.
- Explorer пустой.
- Backtest невозможен без session и strategy.

Нужно:

- Реализовать raw collection registry.
- Реализовать `/api/collections` и `/api/sessions/analyze` или `/api/collections/{id}/analyze`.
- Добавить Dashboard action `Run Analysis`.
- Добавить экран/модал анализа: выбрать collection, параметры `bin_size_ms`, `ema_span`, `threshold_sigma`, `follower_max_dev`, `cluster_gap_bins`, `confirm_window_bins`, `window_ms`.
- После анализа автоматически открыть `explorer.html?session={new_id}`.

Приоритет: P0.

### 4.2 Нет demo-ready состояния проекта

Факт:

- Есть raw data, но нет сохранённой analyzed session.
- Нет стратегий в `data/strategies`.
- Нет backtests.

Для пользователя приложение при открытии выглядит полупустым, хотя данные уже собраны.

Нужно:

- После успешного анализа текущих raw данных сохранить session в `data/sessions`.
- Добавить хотя бы одну baseline strategy в `data/strategies/lighter_c_baseline.py`.
- Запустить baseline backtest и сохранить в `data/backtest`.
- Dashboard должен показывать "последний готовый путь": latest collection -> latest analysis -> latest backtest.

Приоритет: P0.

### 4.3 Jupyter всё ещё не является центром стратегии

Сделано:

- `notebooks/explore.ipynb` и `notebooks/strategy_dev.ipynb` существуют.
- `save_strategy_source()` есть.
- Plot helpers есть.

Не сделано:

- UI не показывает корректный Jupyter process именно для `leadlag-lab`.
- Dashboard link `http://127.0.0.1:8888` не учитывает nginx/base URL/token/current Jupyter base path.
- Strategy page не имеет `Open in Jupyter`.
- Нет "сохранённая из Jupyter стратегия появилась в UI" acceptance на реальном файловом сценарии.
- Нет явной инструкции в UI: "Пиши Python-логику в Jupyter, сохрани сюда, потом жми Run Backtest".

Где ушли от задачи:

- Исходная задача говорит: Jupyter — лаборатория, web app — исследование/бэктест/исполнение.
- Текущая UI-реализация делает Strategy page как простую таблицу файлов и JSON override input.

Приоритет: P0/P1.

### 4.4 Paper trading формально есть, но главный режим не работает

Факт:

- Если collector running, `leadlag.paper.__main__` выставляет mode `collector_ipc_pending` и просто ждёт.
- Collector IPC (`data/.collector.sock` или equivalent stream) не реализован.
- Это специально написано в коде как pending.

Почему это критично:

- План требует: paper trader не создаёт двойные WS, а получает данные от collector.
- Текущий paper при running collector не торгует.
- Если collector status stale `running: true`, paper может бесконечно перейти в pending, хотя collector уже мёртв.

Дополнительный критичный разрыв:

- Realtime detector сейчас emits `signal="A"` for all realtime events.
- Большинство стратегий по плану работают на Signal C.
- Значит paper/live не воспроизводит batch/backtest semantics и не запустит Signal C strategy так же, как backtest.

Приоритет: P0.

## 5. Где реализация ушла от исходной задачи

### 5.1 Вместо рабочего места трейдера получился набор админ-таблиц

Почти все страницы построены как таблицы с raw-ish полями. Это хорошо для разработчика, но плохо для пользователя, который хочет быстро ответить:

- данные сейчас надёжные или нет;
- где edge;
- где fees/slippage съели edge;
- какую стратегию запускать;
- какая конкретная причина у плохой сделки;
- что поменять дальше.

Нужно добавить decision UX:

- верхние verdict-блоки: "Data usable / risky / bad", "Edge survives fees", "Spread too wide", "Strategy robust / not robust";
- подсказки next action;
- цветовые флаги не только в таблицах, но и в summary;
- меньше равноправных таблиц, больше иерархии "главное -> детали".

### 5.2 Нет цельного pipeline в UI

Целевой путь из `plan.md`:

Dashboard -> Start Collector -> Run Analysis -> Explorer -> Jupyter -> Strategy -> Backtest -> Trade Inspector -> Monte Carlo -> Paper.

Текущий путь:

- Start Collector есть.
- Run Analysis нет.
- Explorer требует уже готовую session.
- Strategy требует уже готовый `.py` файл.
- Backtest требует session + strategy.
- Paper формально стартует, но collector IPC pending.

Главный workflow рвётся в четырёх местах: analysis, strategy creation, paper IPC, realtime Signal C parity.

### 5.3 Process architecture ушла от плана

План: supervisord/независимые процессы, API не должен терять управление collector/paper после рестарта.

Текущее:

- API запускает collector/paper через `subprocess.Popen` и хранит процесс в глобальной переменной.
- После рестарта API управление процессом потеряно.
- `read_collector_status()` верит файлу без проверки stale TTL.
- systemd есть только для API и monitor.
- Нет unit/process manager для collector, paper, Jupyter в `leadlag-lab`.

Нужно:

- или вернуться к supervisord как в плане;
- или официально принять systemd как замену и сделать collector/paper отдельными управляемыми unit/template services;
- убрать in-memory Popen как источник истины.

### 5.4 UI делает пользователя ответственным за внутренности

Примеры:

- Strategy page просит руками ввести `params_override (JSON)`.
- Нет форм по основным параметрам стратегии.
- Нет объяснения `slippage_model`, `entry_type`, `position_mode`.
- Ошибки API часто показываются raw JSON или вообще через `alert("bad JSON")`.

Нужно:

- формы вместо raw JSON там, где параметры известны;
- JSON override оставить как advanced;
- inline validation;
- понятные сообщения, что пользователь может сделать дальше.

## 6. P0 глюки и блокеры следующей итерации

### P0.1 Нет Run Analysis из UI/API

Симптом:

- Raw parquet есть, но sessions нет.
- Пользователь не может получить Explorer без Python shell.

Файлы:

- `leadlag/api/app.py`
- `leadlag/session.py`
- `leadlag/ui/dashboard.html`
- новый UI/modal для analysis

Что сделать:

- `GET /api/collections` — показать raw collection sessions из `data/ticks` и `data/bbo`.
- `POST /api/collections/{collection_id}/analyze` — запустить `Session.build_from_raw()`.
- `GET /api/analysis/jobs/{id}` или synchronous response для малых данных.
- Dashboard: кнопка `Run Analysis`.
- Collector page: после stop показать `Analyze this collection`.

Acceptance:

- После текущих raw parquet пользователь нажимает `Run Analysis`, получает session, Explorer открывает события.

### P0.2 Collector status stale и вводит UI в заблуждение

Факт на текущей машине:

- `.collector_status.json`: `running: true`, updated `2026-04-17T13:09:53Z`.
- Текущее время проверки было позднее.
- `leadlag-collector` process не найден.
- Dashboard/Collector всё равно ориентируются на `st.running`.

Что ломается:

- Start может быть disabled, хотя collector не работает.
- Paper может уйти в `collector_ipc_pending`.
- Пользователь думает, что сбор идёт, хотя данные не обновляются.

Что сделать:

- В `read_collector_status()` добавить `stale_after_s`, например 10 секунд.
- Если `updated_at_ms` старше TTL и процесса нет, возвращать `running=false`, `status=stale`, `stale=true`.
- UI показывать красный `stale` и кнопку `Clear stale status`.
- API stop должен уметь очищать stale status.
- `api_collector_status` не должен смешивать file running и in-memory `proc_alive` без итогового computed state.

Acceptance:

- Если статус-файл старше 10 секунд, UI явно показывает `stale`, Start доступен.

### P0.3 График сети на Dashboard не работает

Факт:

- `leadlag/monitor/daemon.py` пишет в `.system_history.jsonl` поля `net_sent`, `net_recv`.
- `leadlag/ui/dashboard.html` строит график из `net_down_bps`, `net_up_bps`.
- Результат: график сети получает `0` через fallback `|| 0`.

Что сделать:

- В monitor daemon считать delta bytes / delta seconds и писать `net_down_bps`, `net_up_bps`.
- Либо в API `read_history()` преобразовывать cumulative counters в rates.
- Dashboard axis подписать как `bytes/s` или `Mbps`, лучше `Mbps`.

Acceptance:

- При активном collector network chart не плоский ноль.

### P0.4 Collector UI отправляет параметры, backend их игнорирует

Факт:

- Collector UI отправляет `bin_size_ms` и `rotation_s`.
- `/api/collector/start` принимает только `duration_s` и `venues`.
- `leadlag.collector.__main__` не принимает `--bin-size-ms` и `--rotation-s`.
- `writer.py` использует константу `ROTATION_INTERVAL_SEC = 1800`.

Почему это плохо:

- Пользователь видит поля, которые не работают.
- Это подрывает доверие ко всем настройкам.

Что сделать:

- Добавить CLI args `--rotation-s`, `--bin-size-ms` если bin size нужен collector metadata/status.
- Передавать rotation в writer_task.
- Показывать фактические параметры текущего сбора в status.
- Если параметр не применяется, убрать поле из UI.

Acceptance:

- При `rotation_s=60` parquet file rotates roughly every minute.

### P0.5 Paper mode не совместим с backtest Signal C

Факт:

- Batch analysis классифицирует A/B/C.
- Realtime detector всегда создаёт `signal="A"`.
- Signal C strategy из Jupyter/backtest в paper не будет получать те же события.

Что сделать:

- Реализовать realtime two-leader confirmation для Signal C.
- Сохранить semantics: anchor leader, confirmer leader, confirmer lag, lagging followers from anchor.
- Добавить parity test на одном synthetic stream: batch events и realtime events совпадают по direction/signal/followers в допустимом окне.

Acceptance:

- Strategy, торгующая только `event.signal == "C"`, открывает paper trades при C-confirmed realtime событии.

### P0.6 Paper collector IPC pending ничего не делает

Факт:

- Если collector running, paper не подключается к WS и не получает данные.
- Вместо этого mode = `collector_ipc_pending`.

Что сделать:

- Реализовать collector -> paper IPC.
- Минимум для следующей итерации: если IPC нет, UI должен честно писать "Paper cannot run while collector is running until IPC is implemented" и предлагать остановить collector.
- Лучше: Unix socket/JSONL stream/ring buffer, где collector публикует ticks/BBO.

Acceptance:

- При running collector paper получает live ticks/BBO без двойных WS и пишет signals/trades.

### P0.7 Monte Carlo по умолчанию вводит в заблуждение

Факт:

- Default method `trade_shuffle` просто перемешивает те же returns.
- Итоговый final PnL при перестановке сделок не меняется.
- `p_value`, `percentile`, `final PnL histogram` для default метода становятся статистически сомнительными или вырожденными.

Что сделать:

- Разделить методы:
  - `trade_shuffle` — только order/drawdown robustness, без p-value по final PnL.
  - `bootstrap` — sampling with replacement для final PnL distribution.
  - `block_bootstrap` — для сохранения серийности.
- Default сделать `bootstrap` или `block_bootstrap`.
- UI явно объясняет метод.
- Cards показывают `order robustness` отдельно от `edge significance`.

Acceptance:

- Default Monte Carlo имеет невырожденную final PnL distribution при N trades > 1.

### P0.8 Backtest limit fee не соответствует plan.md

План:

- `entry_type='limit'`: fee = maker_fee x 2, slippage = 0.

Текущий backtest:

- Entry fee maker.
- Exit fee maker if limit in `_simulate_trade()`? В коде `fee_exit = maker if is_limit else taker`.
- Но комментарий в engine говорит "limit = maker+taker", а paper close использует taker.
- Поведение и документация расходятся.

Что сделать:

- Зафиксировать одну политику из `plan.md`: maker x 2 для limit.
- Backtest, paper, docs, UI labels привести к одному.
- `stats.by_entry_type.limit.fill_rate` показывать отдельно.

Acceptance:

- Тест: limit trade total fee == maker_fee_bps * 2.

### P0.9 Backtest reverse mode теряет закрывающую сделку

Факт:

- При `position_mode="reverse"` open positions просто очищаются.
- Equity/statistics не получают закрытие старой позиции с `exit_reason="reversed"`.

Что сделать:

- При reverse сначала закрывать старую позицию отдельным trade.
- Потом открывать новую.
- Добавить stats `by_exit_reason.reversed`.

Acceptance:

- Тест: reverse produces close trade with `exit_reason="reversed"` before new trade.

### P0.10 Explorer default follower filter скрывает события

Факт:

- Follower dropdown по умолчанию выбирает первого follower.
- `applyFilters()` всегда фильтрует events по выбранному follower.
- Нет варианта `All`.

Почему это плохо:

- Пользователь открывает session и видит не все события.
- Summary "Showing X of Y" не объясняет, что включён follower filter.
- Это искажает первое восприятие edge.

Что сделать:

- Добавить Follower filter = `All` отдельно от "selected follower for chart".
- Или разделить controls:
  - `Filter by follower`
  - `Chart follower`
- Reset должен сбрасывать follower filter в `All`.

Acceptance:

- При первом открытии Explorer показывает все events.

### P0.11 Explorer leader mode OKX/Bybit filter неверен для confirmed events

Факт:

- Для `leaderMode === "okx"` confirmed events проходят из-за `e.leader == "confirmed"`, даже если `anchor_leader` Bybit.
- Аналогично для Bybit.

Что сделать:

- OKX only должен проверять `anchor_leader == "OKX Perp"` или `leader == "OKX Perp"`.
- Bybit only должен проверять `anchor_leader == "Bybit Perp"` или `leader == "Bybit Perp"`.
- Confirmed only отдельно: `signal == "C"`.

Acceptance:

- Фильтр OKX only не показывает confirmed events с Bybit anchor.

## 7. P1 проблемы, которые мешают 10/10

### P1.1 Strategy page слишком слабая

Текущее:

- Таблица: name, class, valid, description, params.
- Форма Run backtest: strategy, session, raw JSON override, Run.

Не хватает по plan.md:

- version;
- source view;
- source editor/create/upload;
- validation with line number;
- Open in Jupyter;
- Run Paper;
- Delete per row;
- last backtest summary;
- N trades, total net, avg trade, win rate, Sharpe, max DD;
- equity sparkline;
- compare selected;
- simple strategy builder.

Что сделать:

- Перестроить page вокруг lifecycle:
  - Strategy library table.
  - Strategy detail drawer.
  - Run Backtest form with human fields.
  - Advanced JSON override collapsed.
  - Source viewer/editor.
  - Compare mode.

### P1.2 Dashboard не даёт "что делать дальше"

Текущее:

- Cards и таблицы есть.
- Но нет guidance.

Проблемы:

- Strategies card пишет "scan in Strategies" вместо count.
- Нет `Run Analysis`.
- Нет `Restart Collector`.
- `Open Jupyter` hardcoded и может не открыть нужный Jupyter.
- Active files берутся не по modified-time, а фактически могут быть не latest.
- Если один API call падает, весь dashboard может показать global error.

Что сделать:

- Добавить блок `Next Action`.
- Добавить pipeline strip:
  - Collection: raw data exists / stale / running.
  - Analysis: session exists / missing.
  - Strategy: strategy exists / missing.
  - Backtest: latest exists / missing.
  - Paper: ready / blocked.
- Сделать partial failure rendering.

### P1.3 Collector metrics не соответствуют названиям

Текущее:

- `ticks_per_s_1m` и `ticks_per_s_10m` считаются как average since session start.
- `median_price` = last_price.
- `uptime_pct` = 100 if current status ok else 0.
- `last_error` остаётся после recover и выглядит как актуальная ошибка.

Что сделать:

- Хранить rolling counters по 1m/10m.
- Считать actual median/last/price deviation.
- Считать uptime as ok_seconds / elapsed_seconds.
- Разделить `last_error` и `last_error_cleared_at`.
- Добавить status severity по idle seconds.

### P1.4 Quality metrics частично декоративные

Проблемы:

- `bbo_coverage_pct` возвращает 100, если есть spread series, а не реальное покрытие времени.
- `reconnects` в quality всегда 0, потому что reconnect logs не интегрированы с session quality.
- Нет duplicate rate.
- Нет timestamp monotonicity.
- Нет median tick interval.
- Нет BBO staleness.
- Нет gap distribution histogram.
- Нет timeline chart, только таблица gaps и bar charts.

Что сделать:

- Quality должен использовать raw parquet + collector log/status.
- Считать metrics по времени, не только агрегаты.
- Добавить chart gaps over time, ticks/s timeline, BBO staleness timeline.

### P1.5 Backtest UI ещё не decision-grade

Что есть:

- Equity chart, drawdown, histograms, scatter, tables.

Что не хватает:

- отдельный слой `Gross - Fees - Slippage` как явная линия;
- explanation cards: "fees consumed X% gross", "slippage consumed Y% gross";
- max DD line;
- distribution filters sync with trades table;
- CSV export;
- clickable sortable headers;
- pagination/virtualization;
- compare 2-5 backtests.

### P1.6 Trade Inspector показывает график, но не объясняет сделку

Что есть:

- Leader/follower/BBO/entry/exit/MFE/MAE annotations.

Что не хватает:

- "Why this trade won/lost" summary.
- Горизонтальные SL/TP линии, сейчас в основном annotation labels.
- Явные MFE/MAE markers на follower curve.
- Spread at entry/exit badges next to chart.
- Link to previous/next losing/profitable trade.
- Если `event_error` есть, UI должен показать его, а не пытаться рисовать NaN.

### P1.7 Jupyter link/process неправильны для текущего окружения

Факт:

- В process list есть Jupyter из другого проекта: `/root/projects/leadlag/notebooks`, base url `/leadlag/lab/`, token.
- Dashboard link ведёт на `http://127.0.0.1:8888` без base_url/token.

Что сделать:

- Явно запустить Jupyter для `leadlag-lab/notebooks`.
- Настроить link через config/API: `/api/system/jupyter`.
- UI должен показывать status/link/token policy.

### P1.8 API errors inconsistent

Проблемы:

- Где-то `HTTPException(404, "strategy not found")`.
- Где-то detail dict.
- UI часто показывает raw JSON.
- Strategy page использует `alert("bad JSON")`.

Что сделать:

- Единый error envelope:
  - `error.code`
  - `error.message`
  - `error.details`
  - `suggested_action`
- UI common error component.

### P1.9 Process detection ненадёжна

Факт:

- `system_processes()` ищет substrings в `cmdline`.
- Может ловить случайные команды, тестовые процессы, старый Jupyter из другого проекта.

Что сделать:

- Использовать pid files/systemd/supervisord as source of truth.
- В UI показывать "managed/unmanaged".

### P1.10 Current raw sample has missing Aster data

Факт:

- Collector стартовал с Aster.
- В текущем ticks parquet venues: 11 venues, Aster отсутствует.
- В bbo parquet venues: 8 venues, Aster отсутствует.
- В логах есть Aster connected.

Что сделать:

- Проверить `parse_aster_trade`, `parse_aster_bbo`.
- В collector live table должен быть obvious warning: connected but 0 ticks/BBO after N seconds.
- Quality should flag "connected_no_data".

## 8. Screen-by-screen review: поля, кнопки, UX

### 8.1 Dashboard

Текущая оценка: 4.5/10.

Текущие поля:

| Поле | Статус | Проблема |
|---|---|---|
| UTC | частично | Показывает время snapshot, не тикающие часы |
| Sessions | есть | Count есть, но sessions сейчас 0 |
| Strategies | плохо | Вместо count текст "scan in Strategies" |
| Backtests | есть | Count есть, но backtests сейчас 0 |
| Collector | есть | Верит stale `running` |
| Paper | есть | Не объясняет blocked/pending modes |
| CPU/RAM/Disk/data | есть | Нормально для прототипа |
| Net recv/sent cards | есть | Cumulative bytes без human units |
| Network chart | сломан | Читает несуществующие `net_down_bps/net_up_bps` |
| Processes | есть | Substring matching, false positives |
| Pings | есть | Нет цветовой severity и disabled state |
| Collector venues | есть | Может показывать stale running |
| Latest sessions/backtests | есть | Но нет empty guidance |
| Active files | есть | Сортировка не гарантирует latest by modified |

Текущие кнопки:

| Кнопка | Статус | Проблема |
|---|---|---|
| Start Collection | есть | Disabled может быть неверным из-за stale status; запускает default 1h без явных настроек |
| Stop Collector | есть | Работает только для in-memory proc; после API restart не управляет старым процессом |
| Open Collector | есть | Ок |
| Open Latest Session | есть | Disabled только визуально; при 0 sessions ведёт в пустой Explorer |
| Open Jupyter | плохо | Hardcoded URL не учитывает deployment/token/base URL |

Нужные кнопки:

- `Run Analysis`;
- `Restart Collector`;
- `Analyze latest collection`;
- `Open latest backtest`;
- `Open strategy lab`;
- `Clear stale collector status`;
- `Show all files`.

Главная UX-доработка:

- Сделать Dashboard не монитором всего подряд, а "control room" с понятным next action.

### 8.2 Collector

Текущая оценка: 5/10.

Текущие поля:

| Поле | Статус | Проблема |
|---|---|---|
| Duration hours | есть | Default 1h, плановый workflow чаще 12h |
| Bin size ms | обманчиво | UI отправляет, backend игнорирует |
| Rotation minutes | обманчиво | UI отправляет, writer игнорирует |
| Venue checkbox | есть | Работает для start |
| Role/taker/maker/BBO/keepalive/enabled/WS URL | есть | Нормально, но таблица плотная |
| Running/proc/session/started/planned/updated | есть | Нет computed stale status |
| Live ticks/s 1m/10m | mislabeled | На деле average since start |
| Last reconnect/last tick/idle/error | есть | Last error не очищается after recovery |
| Median price | неверно | В live status это last price |
| Uptime % | неверно | 100/0 by current status |
| Log | есть | Нет export; filter type зависит от уже отфильтрованных rows |
| Files | есть | Нет total disk/current session grouping |

Текущие кнопки:

| Кнопка | Статус | Проблема |
|---|---|---|
| Select All Leaders | есть | Ок |
| Select All Followers | есть | Ок |
| Select All | есть | Ок |
| Clear Selection | есть | Ок |
| Show/Hide WS URLs | есть | Ок, но table width прыгает |
| Start | частично | Игнорирует bin/rotation; stale issue |
| Stop | частично | Только in-memory proc |
| Restart | частично | Не передаёт bin/rotation |
| Refresh Status | есть | Ок |

Нужные кнопки:

- `Analyze this collection`;
- `Clear stale status`;
- `Export Log`;
- `Show current session files only`;
- `Open Quality after analysis`.

### 8.3 Explorer

Текущая оценка: 5/10.

Что хорошо:

- Есть lazy loading event detail.
- Есть BBO overlay.
- Есть lag50/lag80 markers.
- Есть trade mode.
- Есть keyboard navigation.
- Есть followers table.

Текущие поля/фильтры:

| Поле | Статус | Проблема |
|---|---|---|
| Session | есть | Ок |
| Signal All/A/B/C | есть | Не сохраняется из URL |
| Leader mode | баг | OKX/Bybit incorrectly include all confirmed events |
| Direction | есть | Ок |
| Follower | опасно | Одновременно chart follower и фильтр; default скрывает events |
| Min sigma | есть | Number input вместо range slider; нет max/current |
| Min lagging | есть | Number input вместо slider |
| UTC from/to | есть | Только HH:MM, без даты; для multi-day session плохо |
| Sort | есть | Select вместо clickable headers |
| Show BBO Overlay | есть | Ок |
| Show All Followers | есть | Может загромождать chart |
| Summary | есть | Не объясняет активные фильтры |

Текущие кнопки:

| Кнопка | Статус | Проблема |
|---|---|---|
| Reset Filters | частично | Не сбрасывает follower/show toggles |
| Prev Event | есть | Ок |
| Next Event | есть | Ок |
| Open Trade | только trade mode | Нет links from events to matching trades generally |
| View Backtest | только trade mode | Ок |

Нужные доработки:

- Разделить `Filter follower` и `Chart follower`.
- Добавить `All followers/events` default.
- Fix leader filters.
- Добавить visible chips активных фильтров.
- Добавить pagination/virtualization.
- Добавить event detail sidebar: leader/confirmer/followers/quality flags.
- Добавить "why this event matters" summary: best follower, best net hold, max spread.

### 8.4 Strategy

Текущая оценка: 2.5/10.

Текущие поля:

| Поле | Статус | Проблема |
|---|---|---|
| name/class/valid/description/params | есть | Слишком мало |
| Strategy select | есть | Нет disabled empty state |
| Session select | есть | Нет disabled empty state |
| params_override JSON | есть | User-hostile |

Текущие кнопки:

| Кнопка | Статус | Проблема |
|---|---|---|
| Run | есть | Ошибки raw JSON; нет loading; нет structured validation |

Нужные кнопки:

- `Open Source`;
- `Edit Source`;
- `Validate`;
- `Save`;
- `Open in Jupyter`;
- `Run Backtest`;
- `View Latest Backtest`;
- `Run Paper`;
- `Delete`;
- `Compare Selected`;
- `Create Simple Strategy`.

Главная доработка:

- Strategy page должна стать мостом Jupyter -> app, а не только формой запуска.

### 8.5 Backtest

Текущая оценка: 5.5/10.

Текущие поля:

| Поле | Статус | Проблема |
|---|---|---|
| Header meta | есть | Нет friendly summary/verdict |
| KPIs | есть | Хороший прогресс |
| Equity gross/post_fee/net/drawdown | есть | Нет отдельного explicit `Gross - Fees - Slippage` layer |
| PnL/hold/magnitude/time/spread charts | есть | Не связаны с фильтрами таблицы |
| Fee/slippage impact | есть | Нужна интерпретация |
| By spread/venue/signal | есть | Нет by direction/hour UI table despite stats |
| Trades table | есть | Очень широкая, без pagination/virtualization |

Текущие кнопки/controls:

| Элемент | Статус | Проблема |
|---|---|---|
| Run Monte Carlo | есть | Текст link всегда "Run", даже если уже есть MC |
| Open Session in Explorer | есть | Ок |
| Export JSON | есть | Нет CSV |
| Layer toggles | есть | Не хватает slippage-separated layer |
| Filters signal/venue/pnl/exit/spread/sort | есть | Нет clickable table headers |
| Inspect/View Event | есть | Ок |

Нужные доработки:

- Add comparison mode.
- Add CSV export.
- Add verdict cards.
- Add pagination/virtualization.
- Add "fees/slippage ate edge" warning.

### 8.6 Trade Inspector

Текущая оценка: 5/10.

Текущие поля:

| Поле | Статус | Проблема |
|---|---|---|
| Trade number/strategy/venue/result | есть | Ок |
| Entry/exit/VWAP/Exec/slippage/fees | есть | Хорошо |
| MFE/MAE/spread/BBO/n lagging/leader dev | есть | Хорошо |
| Chart leader/follower/BBO | есть | Есть, но annotations overload |

Текущие кнопки:

| Кнопка | Статус | Проблема |
|---|---|---|
| Prev/Next | есть | Ок |
| View in Explorer | есть | Ок |
| Back to Backtest | есть | Ок |
| Toggle BBO | есть | Ок |
| Show All Followers | есть | Может загромождать |

Нужные доработки:

- Горизонтальные SL/TP lines, не только labels.
- MFE/MAE as markers on curve.
- "Loss reason" diagnosis.
- Handle missing event payload safely.
- Add spread badges at entry/exit.

### 8.7 Monte Carlo

Текущая оценка: 4/10.

Текущие поля:

| Поле | Статус | Проблема |
|---|---|---|
| Backtest select | есть | Ок |
| Simulations | есть | No progress/cancel |
| Method | есть | Default misleading |
| Block size | есть | Visible even when not block bootstrap |
| Seed | есть | Ок |
| Cards p-value/percentile/PnL/probability | есть | Semantics confusing for trade_shuffle |
| Equity fan/hists | есть | Final hist degenerate for trade_shuffle |

Текущие кнопки:

| Кнопка | Статус | Проблема |
|---|---|---|
| Run | есть | Sync wait, no cancel |
| Refresh Results | есть | Ок |
| Back to Backtest | есть | Ок |

Нужные доработки:

- Default bootstrap with replacement.
- Explain methods.
- Hide block size unless block bootstrap.
- Add Cancel/progress for long runs.
- Add real vs median Sharpe/maxDD cards.

### 8.8 Paper

Текущая оценка: 2.5/10.

Текущие поля:

| Поле | Статус | Проблема |
|---|---|---|
| Strategy select | есть | No empty state if no strategies |
| Duration | есть | Ок |
| Status cards | есть | Does not explain collector_ipc_pending as blocked |
| Venue connectivity | есть | From static `.paper_venues`, not robust live health |
| Live equity | есть | No backtest comparison line |
| Signals/positions/trades/stats | есть | No links to event/trade/backtest |

Текущие кнопки:

| Кнопка | Статус | Проблема |
|---|---|---|
| Start | частично | Can start blocked pending mode |
| Stop | частично | In-memory proc issue |
| Restart | частично | Same |
| Refresh | есть | Ок |

Критичные доработки:

- Implement collector IPC.
- Implement Signal C realtime parity.
- Fix stale collector interaction.
- Add Open Backtest/Open Trade/Open Event links.
- Add paper vs backtest drift chart.

### 8.9 Quality

Текущая оценка: 5/10.

Текущие поля:

| Поле | Статус | Проблема |
|---|---|---|
| Session/time/duration/venues/ticks/BBO/events/flags | есть | Хорошо |
| Venue summary many columns | есть | Dense; some metrics weak |
| Coverage/ticks/BBO spread/price dev charts | есть | Good start |
| Timeline gaps table | есть | Нет visual timeline |
| BBO analysis table | есть | Coverage/staleness incomplete |

Текущие кнопки:

| Кнопка | Статус | Проблема |
|---|---|---|
| Show only bad/warning | есть | Ок |
| Show all | есть | Ок |
| Open Session in Explorer | есть | Ок |
| Export report | есть | Ок |

Нужные кнопки:

- `Recompute Quality`;
- `Show gaps on timeline`;
- `Open bad venue details`;
- `Compare venues`.

## 9. Backend/API gap list

Нужно добавить или усилить:

| Endpoint | Статус сейчас | Нужно |
|---|---|---|
| `GET /api/collections` | нет | List raw collection sessions |
| `POST /api/collections/{id}/analyze` | нет | Build session from raw |
| `POST /api/sessions/{id}/analyze` | нет | Re-analyze with new params |
| `DELETE /api/sessions/{id}` | нет | Delete bad analysis |
| `POST /api/strategies/save` | нет | Save source from UI/Jupyter API |
| `POST /api/strategies/validate` | нет | Validate without save |
| `PUT /api/strategies/{name}` | нет | Edit source |
| `GET /api/backtests/compare` | нет | Compare 2-5 backtests |
| `POST /api/paper/start` | есть | Needs blocked/stale/IPC handling |
| `GET /api/system/jupyter` | нет | Correct Jupyter link/status |
| `GET /api/system/history` | есть | Needs network rates |

API rules to enforce:

- all errors use same structured envelope;
- no stale IPC status interpreted as running;
- large UI arrays are paginated or virtualized;
- UI should not parse raw files directly;
- params accepted by UI must be honored by backend.

## 10. Data/contract issues

### Session contract

Сильные стороны:

- Required artifacts now exist when session is built.
- Probe build from current raw data succeeded.

Недостатки:

- UI cannot create session.
- `_read_parquets()` silently skips unreadable parquet files.
- Quality reconnects/downtime not integrated with collector log.
- No duplicate/timestamp/staleness contract.
- No saved session exists in current `data/`.

### Backtest contract

Сильные стороны:

- Trade fields mostly rich.
- Stats much better than previous iteration.

Недостатки:

- Reverse mode bug.
- Limit fee policy mismatch.
- Limit attempts not visible per event/trade; fill failures don't have audit trail.
- Strategy errors increment count but no error artifacts for inspection.

### Paper contract

Недостатки:

- Paper trade `entry_type` is hardcoded `"market"` on close even when order may be limit-like.
- No collector IPC.
- No realtime C signal.
- No full stats parity with backtest.

## 11. UI/UX общий разбор

### Нагромождение

Почти все страницы одновременно показывают слишком много таблиц. Для опытного разработчика это терпимо; для пользователя, который хочет принять торговое решение, это утомительно.

Что изменить:

- На каждом экране сверху должен быть verdict summary.
- Таблицы ниже должны быть drill-down, не основное впечатление.
- Разделить operational monitoring и research decision views.

### Меню

Проблемы:

- Навигация непоследовательна: разные страницы показывают разные наборы ссылок.
- Нет активного пункта меню.
- Нет pipeline order.

Что сделать:

- Единый nav на всех страницах:
  - Dashboard
  - Collector
  - Analysis
  - Explorer
  - Strategies
  - Backtests
  - Monte Carlo
  - Paper
  - Quality
  - Jupyter
- Подсвечивать active page.
- Добавить breadcrumb/deep links.

### Расположение элементов

Проблемы:

- Верхние toolbars переполнены.
- Много controls одного веса.
- Критичные actions (`Run Analysis`, `Open Jupyter`, `Run Backtest`) не выделены как main CTA.
- На wide screens таблицы выглядят как spreadsheet, а не workflow.

Что сделать:

- Primary action button на каждом экране.
- Secondary actions группировать.
- Advanced params collapse.
- Sticky selected event/trade summary.

### Размеры и читаемость

Проблемы:

- Много мелкого текста 13px.
- Широкие таблицы требуют горизонтального сканирования.
- Нет column freezing для event/trade tables.
- Нет pagination.

Что сделать:

- Larger summary typography.
- Table density toggle.
- Sticky headers.
- Column groups.
- Pagination/virtualization.

### Ошибки/loading/empty states

Проблемы:

- Empty states есть частично, но не объясняют следующий шаг.
- Loading states минимальные.
- Error states raw.

Что сделать:

- На пустом Explorer: "No analyzed sessions. Run Analysis from Dashboard."
- На пустой Strategy: "No strategies. Open Jupyter template or create simple strategy."
- На пустом Backtest: "No backtests. Choose strategy + session."
- Errors with suggested action.

## 12. Следующая итерация: порядок работ

### Фаза N1 — восстановить главный UI pipeline

Приоритет: P0.

Задачи:

1. Add collection discovery.
2. Add Run Analysis endpoint.
3. Add Run Analysis UI on Dashboard/Collector.
4. Save session from current raw data.
5. Add baseline strategy.
6. Run baseline backtest and make Dashboard non-empty.

Definition of done:

- Fresh user opens app and sees at least one complete path: raw collection -> session -> events -> strategy -> backtest.

### Фаза N2 — исправить операционные глюки collector/dashboard

Приоритет: P0.

Задачи:

1. Fix stale collector status.
2. Fix network chart.
3. Make bin_size/rotation either real or removed.
4. Fix process source of truth.
5. Add stale/blocked UI states.

Definition of done:

- Dashboard never says collector running if no fresh status/process exists.
- Network chart shows real rates.

### Фаза N3 — исправить Explorer filters and decision UX

Приоритет: P0/P1.

Задачи:

1. Split follower filter and chart follower.
2. Fix leader mode.
3. Add active filter chips.
4. Add event verdict panel.
5. Add pagination/virtualization.

Definition of done:

- First open shows all events.
- User can see best follower/net/spread for selected event without reading raw table.

### Фаза N4 — Strategy lifecycle

Приоритет: P1.

Задачи:

1. Source view/editor.
2. Validate endpoint.
3. Save endpoint.
4. Open in Jupyter.
5. Last backtest summary.
6. Compare selected.
7. Simple strategy builder.

Definition of done:

- User can create or save strategy and run backtest without shell/manual file editing.

### Фаза N5 — Backtest/Trade/Monte Carlo correctness

Приоритет: P0/P1.

Задачи:

1. Fix limit fee policy.
2. Fix reverse close trade.
3. Add fill failure audit.
4. Fix Monte Carlo methods/default.
5. Add trade loss reason panel.
6. Add CSV export and compare.

Definition of done:

- Backtest result explains not only "what happened" but "why edge survives or dies".

### Фаза N6 — Paper/realtime parity

Приоритет: P0, но после N1/N2 можно делать отдельно.

Задачи:

1. Realtime Signal C confirmation.
2. Batch/realtime sigma parity.
3. Collector IPC.
4. Paper mode blocked state until IPC ready.
5. Paper vs backtest drift.

Definition of done:

- Same strategy file can run in backtest and paper with comparable event semantics.

## 13. Acceptance checklist for next review

Следующая итерация считается успешной, если:

- `GET /api/collections` shows current raw collection.
- User clicks `Run Analysis` and gets a saved session.
- `explorer.html?session=X` opens all events by default.
- Dashboard network chart is non-zero during active traffic.
- Stale `.collector_status.json` is shown as stale, not running.
- Collector rotation setting actually changes rotation or field is removed.
- Strategy page can open source and validate strategy.
- There is at least one baseline strategy in `data/strategies`.
- User can run backtest from UI without raw JSON.
- Backtest limit fee matches plan.
- Reverse mode records `exit_reason="reversed"`.
- Monte Carlo default is not degenerate.
- Paper does not silently enter pending; it either trades via IPC or shows a clear blocked state.
- Realtime detector can produce Signal C or paper docs/UI clearly say only A mode is supported.
- Empty states tell the user the next action.
- Tests include at least one browser-level or JS-level check for the dashboard network data and Explorer filters.

## 14. Итог

Текущая реализация уже заметно выросла после прошлого плана, но она пока не стала продуктом на 10/10. Самый большой риск теперь не в отсутствии файлов, а в ложном ощущении готовности: страницы есть, графики есть, тесты проходят, но пользовательский путь всё ещё ломается на analysis, strategy lifecycle, stale process state, paper IPC и realtime/backtest parity.

Следующая итерация должна быть не "добавить ещё таблиц", а "сшить пользовательский путь и убрать ложные состояния". После N1-N3 продукт станет заметно ближе к исходной задаче: пользователь откроет приложение, увидит, что делать дальше, и сможет пройти от сырых данных до события и бэктеста без ручных обходов.
