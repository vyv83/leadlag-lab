# Leadlag-lab: полный план доработок до 10/10

Дата: 2026-04-17

## 0. Прямой вердикт

Текущая реализация не решает исходную задачу пользователя. Это не полноценное приложение для lead-lag research/trading, а тонкий scaffold вокруг части notebook-кода.

Текущая оценка:

| Область | Оценка |
|---|---:|
| Понимание и реализация пользовательского пайплайна | 2/10 |
| Backend/data contracts | 3/10 |
| Collector/monitoring | 3/10 |
| Analysis/session layer | 3/10 |
| Jupyter strategy workflow | 1/10 |
| Backtest correctness | 3/10 |
| Explorer/Backtest/Trade UX | 2/10 |
| Monte Carlo | 0/10 |
| Data quality UX | 2/10 |
| Paper/realtime readiness | 2/10 |
| Tests/acceptance proof | 0/10 |
| Итоговая оценка сейчас | 2/10 |

Если реализовать все доработки из этого документа и прогнать acceptance-проверки на реальных данных, тогда задача пользователя будет решена на 10/10: пользователь сможет открыть приложение, собрать/проверить данные, найти lead-lag паттерны, написать стратегию в Jupyter, честно бэктестить ее, разбирать сделки и принять решение о paper/live без ручных обходов.

## 0.1. Режим модели для реализации

Новый агент должен начинать реализацию на `gpt-5.4` с reasoning `xhigh`, потому что первые фазы требуют восстановления контрактов данных, проверки исходной задачи, чтения текущей реализации и аккуратного проектирования без потери деталей.

Обязательное правило остановки:

- после того как фазы A и B из раздела 10 реализованы, протестированы и закоммичены, агент должен остановиться;
- агент должен прямо написать пользователю: "Переключи новый диалог на `gpt-5.4 high` для оставшейся реализации";
- до этого момента не надо снижать reasoning, потому что риск пропустить контракт, поле, кнопку или UX-сценарий выше экономии;
- после переключения на `high` можно продолжать UI polish, расширение экранов, допиливание тестов и менее рискованные фазы;
- если в ходе работы обнаружится, что фазы A/B оказались неполными или acceptance не проходит, агент остается на `xhigh` и сначала закрывает блокеры.

## 1. Первый источник истины: задача пользователя

Пользователь хочет не набор страниц и не "визуализатор". Пользователь хочет рабочее место алготрейдера для lead-lag стратегий.

Целевая задача:

1. Собрать качественные tick/BBO данные по BTC с нескольких бирж.
2. Понять, какие лидеры двигаются первыми и какие followers реально лагают.
3. Увидеть каждое событие глазами трейдера: цена, lag, BBO spread, fees, можно ли было реально войти.
4. Писать произвольную Python-стратегию в Jupyter, а не тыкать только YAML/фильтры.
5. Перенести эту стратегию в приложение без переписывания логики.
6. Запустить честный backtest с fees/slippage/spread/limit fill/SL/TP/position mode.
7. Разобрать equity, распределения, Monte Carlo и каждую сделку.
8. Итерировать стратегию быстро: Jupyter -> save -> app -> backtest -> inspect -> refine.
9. После доверия к backtest перейти в paper/live pipeline с тем же `on_event()`.

Ключевой UX-критерий:

Пользователь открывает приложение и без знания внутреннего кода понимает:

- данные собираются или нет;
- какие биржи живые/мертвые;
- какие события есть и почему они интересны;
- на каком follower стоит торговать;
- где стратегия зарабатывает, а где fees/slippage съедают edge;
- какие конкретные сделки хорошие/плохие и почему;
- достаточно ли robust стратегия по Monte Carlo;
- что нужно поменять в стратегии дальше.

## 2. Вторичный источник истины: `plan.md`

План корректно описывает продукт, но текущая реализация выполняет только малую часть. Особенно не выполнены:

- связка Jupyter <-> web app;
- session contract с `price_windows`, `bbo_windows`, `metrics`, `grid`, `ci`;
- полноценный Explorer с BBO overlay и trade mode;
- Trade Inspector;
- Monte Carlo;
- strategy lifecycle;
- data quality как диагностический экран;
- process architecture;
- acceptance-проверки на реальных данных.

## 3. Главная проблема текущей реализации

Сейчас проект устроен как "тонкий FastAPI + простые HTML-таблицы + куски notebook logic".

Это не совпадает с продуктом, потому что продукт должен помогать принимать торговое решение, а текущий UI почти не отвечает на вопросы трейдера:

- где edge;
- где latency/lag;
- где плохие данные;
- где широкий spread;
- где проскальзывание;
- почему сделка открылась/пропущена;
- почему сделка выиграла/проиграла;
- насколько результат статистически надежен.

## 4. Что было недостаточно в прошлых отчетах

Прошлые отчеты нашли часть технических багов, но не разобрали продукт целиком.

Было упущено:

- полная пользовательская цепочка от collector до решения о paper/live;
- Jupyter как центральная лаборатория;
- обязательные поля session/backtest/quality contracts;
- подробный UX каждого экрана;
- каждая кнопка и ее состояние;
- стратегия как единый Python-класс для backtest/paper/live;
- Monte Carlo как обязательный блок принятия решения;
- acceptance-тесты, доказывающие 10/10;
- то, что "исправить P0" не равно "пользователь получил продукт".

## 5. Критические текущие дефекты

### P0. Приложение не может выполнить основной путь "Strategy -> Run Backtest" из UI

Факт:

- `POST /api/backtests/run` грузит session через `load_session()`.
- `load_session()` не загружает `vwap_df`, `bbo_df`, `ema_df`, `dev_df`.
- `run_backtest()` требует `session.vwap_df`.
- UI-кнопка Run Backtest приводит к падению backend.

Файлы:

- `leadlag/session.py:233`
- `leadlag/backtest/engine.py:75`
- `leadlag/api/app.py:220`

Доработка:

- session должен сохранять/грузить все данные, нужные backtest;
- API должен возвращать корректную ошибку, если session неполная;
- UI должен показывать понятное сообщение, а не ломаться.

### P0. Нет реального session contract из плана

Сейчас session сохраняет в основном `meta.json`, `events.json`, `quality.json`.

Не хватает обязательных артефактов:

- `price_windows.json`;
- `bbo_windows.json`;
- `metrics.parquet`;
- `grid.parquet`;
- `ci.json`;
- ссылки на `collection_files`;
- quality timeline/gaps/BBO stats.

Без этого Explorer, Trade Inspector, Quality и backtest не могут стать тем инструментом, который описан в задаче.

### P0. Нет notebook workflow

В проекте нет `notebooks/`, нет переписанных notebook-клиентов, нет `list_sessions`, нет `save_strategy_source`, нет `run_monte_carlo`.

Это ломает главный принцип: Jupyter является лабораторией, web app является рабочим местом анализа.

### P0. Explorer не отвечает на главный вопрос "можно ли было реально войти"

Сейчас Explorer показывает таблицу и простой price chart. Нет:

- BBO bid/ask overlay;
- spread axis;
- lag_50/lag_80 markers;
- follower metrics table;
- trade mode with entry/exit;
- selected event deep-link;
- keyboard navigation;
- local instant filtering;
- all followers overlay.

### P0. Trade Inspector практически отсутствует

Текущий `trade.html` показывает key-value dump. Это не инспектор сделки.

Должно быть:

- лидерский график;
- follower график;
- BBO subplot;
- entry/exit annotations;
- VWAP/Exec prices;
- SL/TP lines;
- MFE/MAE markers;
- Prev/Next navigation;
- link back to event and backtest.

### P0. Monte Carlo отсутствует

Нет `montecarlo.html`, нет `run_monte_carlo`, нет endpoint запуска, нет `montecarlo.json`.

Без Monte Carlo пользователь не может понять, является ли результат стратегии статистически надежным.

### P0. Backtest engine не годится как источник доверия

Найденные проблемы:

- position cleanup происходит после новой сделки, из-за чего `reject` может ошибочно пропускать будущие сигналы;
- limit-fill обновляет `entry_bin`, но не пересчитывает `entry_ts_ms` и BBO at fill;
- `limit` fee задан как maker+taker, хотя план требует maker x2 для limit;
- fill attempts не сохраняются, поэтому нет честного `fill_rate`;
- `slippage_source` хранит только entry source;
- `leader_dev_sigma` теряется из-за несовпадения названий;
- errors in `on_event()` не пишутся как action/error и могут валить backtest;
- `params` мутируются на объекте стратегии и могут течь между прогонами;
- нет custom slippage model.

### P0. Data quality почти не реализован

Текущий quality экран показывает только ticks/BBO/sigma.

Нет:

- flags good/warning/bad;
- timeline gaps;
- ticks/s over time;
- bin coverage heatmap;
- price consistency;
- BBO spread p50/p95/p99;
- reconnects/downtime/uptime;
- zero price/zero qty/side distribution;
- price deviation from leader.

### P0. Collector не дает операторской уверенности

Текущий collector UI умеет start/stop и показывает список parquet файлов.

Нет:

- venue checklist with 12 venues;
- role/fees/BBO/WS/keepalive;
- live ticks/s 1m/10m;
- BBO/s;
- reconnects;
- seconds since last tick;
- last error;
- uptime pct;
- sparkline;
- structured collector log;
- rows/time range/venues in parquet files;
- `.collector_status.json` writer.

### P1. API не покрывает план

Missing/weak endpoints:

- `POST /api/sessions/{id}/analyze`;
- `DELETE /api/sessions/{id}`;
- `GET /api/system/processes`;
- `GET /api/collector/log`;
- `GET /api/collector/files`;
- `POST /api/backtests/{id}/montecarlo/run`;
- `POST /api/paper/start`;
- `POST /api/paper/stop`;
- `GET /api/paper/stats`;
- `GET /api/paper/venues`.

### P1. Process architecture не соответствует плану

План требует supervisord и независимые процессы. Текущая реализация:

- systemd вместо supervisord;
- collector запускается из API через in-memory `COLLECTOR_PROC`;
- после рестарта API управление collector теряется;
- Jupyter process отсутствует;
- paper daemon отсутствует;
- collector -> paper IPC отсутствует.

### P1. Нет реального acceptance proof

Нет тестов. Нет проверки:

- `s.events.filter(signal='C').count == 229`;
- 519 events load < 2s;
- chart redraw < 200ms;
- BBO overlay visible;
- backtest API success;
- trade inspector shows price/BBO windows;
- collector status fresh every 2s;
- paper does not double-connect WS;
- UI handles errors.

## 6. Данные и контракты: что надо реализовать

### 6.1 Raw data contract

Должно быть:

- `data/ticks/YYYY-MM-DD/ticks_YYYYMMDD_HHMMSS.parquet`;
- `data/bbo/YYYY-MM-DD/bbo_YYYYMMDD_HHMMSS.parquet`;
- rotation строго по `rotation_s`;
- session id определяется началом непрерывного сбора;
- qty normalized to BTC;
- timestamp UTC everywhere.

Поля ticks:

| Поле | Обязательно | Назначение |
|---|---:|---|
| `ts_ms` | да | local receive timestamp UTC |
| `ts_exchange_ms` | да | exchange event timestamp |
| `price` | да | trade price |
| `qty` | да | normalized BTC amount |
| `side` | да | `buy`/`sell`/`unknown` |
| `venue` | да | canonical venue name |

Поля BBO:

| Поле | Обязательно | Назначение |
|---|---:|---|
| `ts_ms` | да | local receive timestamp UTC |
| `bid_price` | да | best bid |
| `bid_qty` | да | best bid qty |
| `ask_price` | да | best ask |
| `ask_qty` | да | best ask qty |
| `venue` | да | canonical venue name |

### 6.2 Session contract

`meta.json` должен содержать:

- `session_id`;
- `collection_session_id`;
- `params_hash`;
- `collection_files`;
- `t_start_ms`;
- `t_end_ms`;
- `duration_s`;
- `bin_size_ms`;
- `ema_span`;
- `threshold_sigma`;
- `follower_max_dev`;
- `cluster_gap_bins`;
- `confirm_window_bins`;
- `venues`;
- `leaders`;
- `followers`;
- `fees`;
- `bbo_available`;
- `n_ticks`;
- `n_bbo`;
- `n_events`;
- `n_signal_a`;
- `n_signal_b`;
- `n_signal_c`;
- `created_at_utc`;
- `source_data_layout_version`.

`events.json` должен содержать на event:

- `event_id`;
- `bin_idx`;
- `ts_ms`;
- `time_utc`;
- `signal`;
- `direction`;
- `magnitude_sigma`;
- `leader`;
- `leader_dev`;
- `anchor_leader`;
- `confirmer_leader`;
- `confirmer_bin`;
- `confirmer_lag_ms`;
- `lagging_followers`;
- `n_lagging`;
- `follower_metrics`;
- `grid_results`;
- `quality_flags_at_event`.

`price_windows.json` должен содержать:

- `bin_idx`;
- `rel_times_ms`;
- `venues.{venue}`;
- values as price array;
- enough window for event/trade view, minimum ±10s.

`bbo_windows.json` должен содержать:

- `bin_idx`;
- `rel_times_ms`;
- `venues.{venue}.bid`;
- `venues.{venue}.ask`;
- `venues.{venue}.spread_bps`;
- only venues with BBO;
- explicit absence for no-BBO venues in API response.

`metrics.parquet` должен содержать:

- `bin_idx`;
- `signal`;
- `follower`;
- `lag_50_ms`;
- `lag_80_ms`;
- `hit`;
- `mfe_bps`;
- `mae_bps`;
- `leader_move_bps`.

`grid.parquet` должен содержать:

- `bin_idx`;
- `signal`;
- `follower`;
- `delay_ms`;
- `hold_ms`;
- `gross_pnl_bps`;
- `net_pnl_bps`;
- `hit`;
- `fee_bps`.

`ci.json` должен содержать:

- `follower`;
- `signal`;
- `delay_ms`;
- `hold_ms`;
- `n`;
- `net_mean`;
- `net_lo`;
- `net_hi`;
- `gross_mean`;
- `hit_mean`;
- `hit_lo`;
- `hit_hi`;
- `sharpe`;
- `classification`: `profit`/`marginal`/`loss`.

`quality.json` должен содержать per venue:

- `role`;
- `ticks_total`;
- `ticks_per_s_avg`;
- `ticks_per_s_max`;
- `ticks_per_s_min_nonzero`;
- `bin_coverage_pct`;
- `bbo_total`;
- `bbo_per_s_avg`;
- `bbo_coverage_pct`;
- `bbo_available`;
- `median_price`;
- `price_deviation_from_leader_bps`;
- `reconnects`;
- `downtime_s`;
- `uptime_pct`;
- `zero_price_ticks`;
- `zero_qty_ticks`;
- `side_buy_pct`;
- `side_sell_pct`;
- `flag`;
- `flag_reasons`;
- `bbo_median_spread_bps`;
- `bbo_mean_spread_bps`;
- `bbo_max_spread_bps`;
- `bbo_p95_spread_bps`;
- `bbo_p99_spread_bps`;
- `bbo_pct_above_5bps`.

### 6.3 Backtest contract

`meta.json` должен содержать:

- `backtest_id`;
- `strategy_name`;
- `strategy_version`;
- `strategy_description`;
- `strategy_params`;
- `params_override`;
- `session_id`;
- `backtest_date_utc`;
- `computation_time_s`;
- `slippage_model`;
- `fixed_slippage_bps`;
- `entry_type`;
- `position_mode`;
- `data_contract_version`;
- `engine_version`.

`trades.json` должен содержать на trade:

- `trade_id`;
- `signal_bin_idx`;
- `signal_type`;
- `direction`;
- `magnitude_sigma`;
- `venue`;
- `side`;
- `entry_type`;
- `entry_ts_ms`;
- `entry_time_utc`;
- `exit_ts_ms`;
- `exit_time_utc`;
- `entry_price_vwap`;
- `exit_price_vwap`;
- `entry_price_exec`;
- `exit_price_exec`;
- `slippage_entry_bps`;
- `slippage_exit_bps`;
- `slippage_total_bps`;
- `slippage_source_entry`;
- `slippage_source_exit`;
- `spread_at_entry_bps`;
- `spread_at_exit_bps`;
- `gross_pnl_bps`;
- `fee_entry_bps`;
- `fee_exit_bps`;
- `fee_total_bps`;
- `fee_type_entry`;
- `fee_type_exit`;
- `net_pnl_bps`;
- `hold_ms`;
- `planned_hold_ms`;
- `exit_reason`;
- `stop_loss_bps`;
- `take_profit_bps`;
- `mfe_bps`;
- `mae_bps`;
- `mfe_time_ms`;
- `mae_time_ms`;
- `bbo_available`;
- `n_lagging_at_signal`;
- `leader_dev_sigma`;
- `skip_or_error_reference` if generated from an event error.

`stats.json` должен содержать:

- all totals from plan;
- `profit_factor`;
- `avg_win_bps`;
- `avg_loss_bps`;
- `best_trade_bps`;
- `worst_trade_bps`;
- `max_dd_duration_ms`;
- `avg_hold_ms`;
- `avg_mfe_bps`;
- `avg_mae_bps`;
- `mfe_mae_ratio`;
- `trades_per_hour`;
- `max_consec_wins`;
- `max_consec_losses`;
- `n_errors`;
- `n_skipped_position_already_open`;
- `n_limit_attempts`;
- `n_limit_filled`;
- `limit_fill_rate`;
- `by_signal`;
- `by_venue`;
- `by_direction`;
- `by_entry_type`;
- `by_spread_bucket`;
- `by_exit_reason`;
- `by_hour_utc`.

## 7. Screen-by-screen доработка UI/UX

### 7.1 Dashboard

Текущая оценка: 2/10.

Текущие проблемы:

- нет глобального статуса платформы;
- нет uptime;
- нет UTC clock;
- нет counts sessions/strategies/backtests;
- нет paper/collector state в верхней панели;
- нет process table;
- нет active file rows/time range;
- нет collector venue status;
- нет last analysis block;
- нет quick actions;
- нет Open Jupyter.

Обязательные поля:

- Platform uptime;
- Current UTC time;
- Sessions total/today;
- Strategies count;
- Backtests count;
- Collector status + current duration;
- Paper status + equity today;
- CPU/RAM/Disk/Net current values;
- CPU/RAM/Disk/Net sparklines;
- Pings per venue;
- Processes: api/collector/paper/monitor/jupyter with PID/mem/uptime;
- Active files latest 5;
- Data directory usage;
- Last analysis: session id/date/duration/A/B/C count/green strategies;
- Last paper signal/trade if running.

Обязательные кнопки:

- `Start Collection`;
- `Stop Collector`;
- `Restart Collector`;
- `Run Analysis`;
- `Open Jupyter`;
- `Open Explorer`;
- `Open Paper Dashboard`;
- `Show all files`;
- `Re-analyze`;
- `Open latest session`.

Состояния кнопок:

- `Start Collection` disabled while collector running;
- `Stop Collector` disabled while stopped;
- `Run Analysis` disabled if no raw collection;
- `Open Explorer` disabled if no analyzed session;
- errors shown inline, not alert-only.

### 7.2 Collector

Текущая оценка: 2/10.

Обязательные поля настроек:

- Running/Stopped;
- current session id;
- uptime h:mm:ss;
- planned duration;
- Duration hours input;
- Bin size ms input;
- Rotation interval minutes input;
- Venue checklist for all 12 venues;
- for each venue: name, role, taker fee, maker fee, BBO available, WS URL, keepalive type, enabled.

Обязательные кнопки:

- `Start`;
- `Stop`;
- `Restart`;
- `Select All Leaders`;
- `Select All Followers`;
- `Select All`;
- `Clear Selection`;
- `Show/Hide WS URLs`;
- `Refresh Status`;
- `Download/Export Log` optional.

Live monitor table fields:

- Venue;
- Role;
- Status;
- Ticks total;
- Ticks/s 1m;
- Ticks/s 10m;
- BBO total;
- BBO/s;
- Reconnects;
- Last reconnect UTC;
- Last tick UTC;
- Seconds since last tick;
- Last price;
- Median price;
- Last error;
- Uptime %;
- ticks/s sparkline.

Log fields:

- Timestamp UTC;
- Venue;
- Event type;
- Message;
- filters by venue/type;
- auto-scroll toggle.

Files table fields:

- Filename;
- Size;
- Rows;
- ts_min;
- ts_max;
- Venues;
- Created/modified UTC;
- Total disk usage.

### 7.3 Explorer

Текущая оценка: 2/10.

Explorer должен быть главным рабочим экраном анализа события.

Обязательные фильтры:

- Signal buttons: `All`, `A`, `B`, `C`;
- Leader mode: `All`, `OKX only`, `Bybit only`, `Confirmed only`;
- Direction: `All`, `UP`, `DOWN`;
- Follower dropdown;
- Magnitude range slider;
- Min lagging slider;
- Time range from/to UTC;
- Session dropdown;
- `Reset Filters`.

Обязательные кнопки/toggles:

- `Reset Filters`;
- `Prev Event`;
- `Next Event`;
- `Show BBO Overlay`;
- `Show All Followers`;
- `Open Trade`;
- `View Backtest`;
- keyboard navigation up/down/left/right.

Event list fields:

- event number;
- signal badge;
- direction arrow;
- magnitude sigma;
- UTC time;
- n lagging followers;
- leader/confirmed;
- trade icon if linked to backtest trade;
- selected row highlight.

Leader chart:

- x relative ms;
- y bps from t0;
- OKX/Bybit lines;
- t=0 vertical line;
- pre-signal shaded region;
- EMA baseline toggle;
- hover with ms/price/venue.

Follower chart:

- selected follower line;
- t=0 line;
- lag_50 marker;
- lag_80 marker;
- entry/exit if mode=trade;
- MFE/MAE if mode=trade;
- SL/TP lines if mode=trade;
- BBO bid/ask lines;
- spread fill;
- right axis spread bps;
- no-BBO banner.

Followers table fields:

- Venue;
- In signal;
- Lag 50 ms;
- Lag 80 ms;
- Hit;
- MFE bps;
- MAE bps;
- Taker fee;
- Maker fee;
- BBO available;
- Net at 2s;
- Net at 5s;
- Net at 10s;
- Net at 30s.

Acceptance:

- 519 events load under 2s;
- selecting event redraws chart under 200ms;
- `?session=X&event=Y` opens selected event;
- `mode=trade&backtest=X&trade=Y` draws entry/exit.

### 7.4 Strategy List

Текущая оценка: 2/10.

Strategy table fields:

- Name;
- Version;
- Description;
- Valid status;
- Error message with line number;
- Venues traded;
- Signal type;
- Entry type;
- Slippage model;
- Position mode;
- Last backtest date;
- N trades;
- Total net PnL;
- Avg trade;
- Hit rate;
- Sharpe;
- Max drawdown;
- Equity sparkline;
- Has backtest;
- Has paper;
- Has live.

Buttons per strategy:

- `Run Backtest`;
- `View Backtest`;
- `Run Paper`;
- `Open Source`;
- `Open in Jupyter`;
- `Delete`.

Comparison controls:

- checkbox per strategy;
- `Compare Selected`;
- equity overlay;
- metric comparison table;
- timeline overlap.

Simple strategy builder fields:

- strategy name;
- description;
- leader mode;
- signal checkboxes A/B/C;
- threshold sigma;
- followers;
- delay;
- hold;
- entry type;
- slippage model;
- fixed slippage bps;
- max BBO spread bps;
- stop loss bps;
- take profit bps;
- position mode.

Builder buttons:

- `Validate`;
- `Save`;
- `Run Backtest`;
- `Open Generated Source`.

### 7.5 Backtest

Текущая оценка: 2/10.

Header fields:

- strategy name/version;
- session id/date/duration;
- params;
- params override;
- computation time;
- slippage model;
- position mode.

Equity graph controls:

- layer toggle: `Gross`, `Gross - Fees`, `Gross - Fees - Slippage`, `Net`;
- drawdown subplot;
- trade markers;
- click marker -> Trade Inspector.

Trades table fields:

- Inspect button;
- View Event button;
- trade id;
- time UTC;
- signal;
- direction;
- magnitude;
- venue;
- entry VWAP;
- entry exec;
- exit VWAP;
- exit exec;
- exit reason;
- gross pnl;
- fee bps with maker/taker;
- slippage bps with source;
- net pnl;
- spread entry;
- spread exit;
- hold actual;
- MFE;
- MAE;
- entry-to-MFE;
- hit;
- BBO available.

Filters/buttons:

- signal filter;
- venue filter;
- PnL filter;
- exit reason filter;
- spread bucket filter;
- sort by any column;
- `Inspect`;
- `View Event`;
- `Run Monte Carlo`;
- `Export JSON/CSV`.

Stats cards:

- all stats listed in plan;
- fee and slippage impact;
- by entry type;
- by spread bucket;
- by venue;
- by signal;
- by direction.

Charts:

- PnL histogram;
- hold histogram;
- magnitude vs PnL;
- time of day vs PnL;
- spread vs PnL;
- equity by venue.

### 7.6 Trade Inspector

Текущая оценка: 1/10.

Header fields:

- trade number / total;
- strategy;
- signal;
- direction;
- magnitude;
- result bps;
- exit reason.

Buttons:

- `Prev`;
- `Next`;
- `View in Explorer`;
- `Back to Backtest`;
- `Toggle BBO`;
- `Show All Followers`.

Leader chart:

- leader prices in bps;
- t0;
- entry;
- exit;
- confirmer lag annotation for Signal C.

Follower chart:

- follower price;
- entry/exit annotations with VWAP/Exec;
- entry price line;
- profit/loss region fill;
- MFE marker;
- MAE marker;
- SL line;
- TP line.

BBO subplot:

- spread over time;
- bid/ask;
- entry/exit markers;
- spread@entry;
- spread@exit;
- no-BBO banner.

Side metrics:

- entry/exit UTC;
- hold ms;
- exit reason;
- VWAP/Exec prices;
- slippage entry/exit/total;
- slippage source entry/exit;
- fees entry/exit/total;
- net/gross;
- MFE/MAE;
- BBO spreads;
- signal magnitude;
- n lagging;
- leader deviation.

### 7.7 Monte Carlo

Текущая оценка: 0/10.

Required page: `montecarlo.html`.

Fields:

- backtest id;
- simulations count default 10000;
- method: trade shuffle, return shuffle, block bootstrap;
- block size if block bootstrap;
- random seed optional.

Buttons:

- `Run`;
- `Cancel` if long-running;
- `Back to Backtest`;
- `Refresh Results`.

Charts:

- simulated equity curves;
- real equity;
- 5th/95th percentiles;
- median simulation;
- final PnL histogram;
- Sharpe histogram;
- max drawdown histogram.

Cards:

- p-value;
- percentile;
- median sim PnL;
- 5th PnL;
- 95th PnL;
- probability of profit;
- real vs median PnL;
- real vs median Sharpe;
- real vs median max DD.

### 7.8 Paper Trading

Текущая оценка: 2/10.

Even if paper was excluded from one audit request, it is part of the original product. A 10/10 plan cannot ignore it.

Backend requirements:

- `python -m leadlag.paper` daemon/entrypoint;
- `POST /api/paper/start`;
- `POST /api/paper/stop`;
- no double WS if collector running;
- IPC collector socket or explicit fallback;
- strategy-specific venue connections only;
- limit fill handling;
- skip reasons;
- live stats.

UI fields:

- strategy name/version;
- status;
- running since UTC;
- uptime;
- equity today;
- venue connectivity table;
- live equity vs backtest;
- recent signals;
- open positions;
- trades today;
- full-period stats;
- backtest vs paper comparison.

Buttons:

- `Start`;
- `Stop`;
- `Restart`;
- `Select Strategy`;
- `Open Backtest`;
- `Open Trade`;
- `Open Event`;
- `Refresh`.

### 7.9 Data Quality

Текущая оценка: 2/10.

Summary fields:

- session id;
- time range UTC;
- duration;
- venues count;
- total ticks;
- total BBO;
- A/B/C events;
- bad/warning/good venue counts.

Venue table fields:

- Venue;
- Role;
- Total ticks;
- Ticks/s avg;
- Ticks/s max;
- Ticks/s min non-zero;
- Bin coverage %;
- Total BBO updates;
- BBO/s avg;
- BBO coverage %;
- BBO available;
- Median price;
- Price deviation from OKX median;
- Reconnects;
- Downtime seconds;
- Uptime %;
- Zero price ticks;
- Zero qty ticks;
- Side buy/sell %;
- Flag;
- Flag reasons.

Charts:

- timeline gaps;
- ticks/s over time;
- bin coverage heatmap;
- price consistency;
- BBO spread over time.

BBO analysis table:

- Venue;
- BBO available;
- median spread;
- mean spread;
- max spread;
- p50;
- p95;
- p99;
- % time spread > 5 bps.

Buttons:

- `Recompute Quality`;
- `Open Session in Explorer`;
- `Show only bad`;
- `Show gaps`;
- `Export report`.

## 8. Jupyter integration до 10/10

Нужно реализовать:

- `notebooks/explore.ipynb`;
- `notebooks/strategy_dev.ipynb`;
- navbar button `Open Jupyter`;
- supervisord/system process for Jupyter;
- same venv as app;
- `list_sessions()`;
- `load_session()` with full lazy data access;
- `save_strategy_source()`;
- `run_monte_carlo()`;
- `EventsTable.filter()` with `min_magnitude`, `follower`, `leader_mode`, `direction`, `time_range`, `min_lagging`;
- `EventsTable.stats(follower)`;
- `EventsTable.grid_search()`;
- plotting helpers:
  - `event.plot()`;
  - `events.plot_lag_distribution()`;
  - `events.plot_magnitude_distribution()`;
  - `events.plot_heatmap()`;
  - `result.plot_equity(layers=True)`;
  - `result.plot_trade(n)`;
  - `result.plot_trades_scatter()`;
  - `result.plot_spread_impact()`.

Acceptance:

- notebooks reproduce `analysis_full.txt` results;
- `Signal C == 229` on reference data;
- strategy written in notebook appears in Strategy List without restart;
- backtest result saved in notebook appears in Backtest UI.

## 9. Backend/API доработки

Required system endpoints:

- `/api/system/stats`;
- `/api/system/history`;
- `/api/system/pings`;
- `/api/system/files`;
- `/api/system/processes`.

Required collector endpoints:

- `/api/collector/status`;
- `/api/collector/start`;
- `/api/collector/stop`;
- `/api/collector/log`;
- `/api/collector/files`.

Required session endpoints:

- `/api/sessions`;
- `/api/sessions/{id}/meta`;
- `/api/sessions/{id}/events`;
- `/api/sessions/{id}/event/{bin_idx}`;
- `/api/sessions/{id}/quality`;
- `/api/sessions/{id}/analyze`;
- `DELETE /api/sessions/{id}`.

Required strategy endpoints:

- `/api/strategies`;
- `/api/strategies/{name}`;
- `POST /api/strategies/save`;
- `POST /api/strategies/validate`;
- `DELETE /api/strategies/{name}`.

Required backtest endpoints:

- `/api/backtests`;
- `/api/backtests/{id}/meta`;
- `/api/backtests/{id}/trades`;
- `/api/backtests/{id}/equity`;
- `/api/backtests/{id}/stats`;
- `/api/backtests/{id}/trade/{n}`;
- `/api/backtests/run`;
- `/api/backtests/{id}/montecarlo`;
- `/api/backtests/{id}/montecarlo/run`.

Required paper endpoints:

- `/api/paper/status`;
- `/api/paper/start`;
- `/api/paper/stop`;
- `/api/paper/trades`;
- `/api/paper/equity`;
- `/api/paper/signals`;
- `/api/paper/positions`;
- `/api/paper/stats`;
- `/api/paper/venues`.

API rules:

- all runtime errors become structured JSON errors;
- no silent `pass` around parser/collector failures without log;
- every response that includes time also includes UTC display-friendly field or frontend formatter contract;
- large arrays are lazy-loaded;
- UI never needs to parse raw files directly.

## 10. Implementation order

### Phase A: make core pipeline real

1. Implement full session artifacts.
2. Implement `load_session()` lazy frames.
3. Fix backtest engine correctness.
4. Fix `/api/backtests/run`.
5. Add integration tests for session -> backtest -> save -> UI artifacts.

Definition of done:

- UI Run Backtest works from saved session;
- event detail returns price/BBO windows;
- `Signal C == 229` on reference data or documented data mismatch.

### Phase B: make Explorer/Trade usable

1. Rebuild Explorer around event list + two-subplot chart + BBO overlay.
2. Implement trade mode.
3. Build real Trade Inspector.
4. Add URL param handling.

Definition of done:

- user can click a losing trade and see exactly whether price, fees, spread, or timing caused it.

### Phase C: make Backtest decision-grade

1. Stats cards.
2. Equity layers.
3. Distribution charts.
4. Spread impact charts.
5. Venue/signal breakdowns.
6. Monte Carlo.

Definition of done:

- user can decide whether a strategy has real edge, not just positive gross PnL.

### Phase D: make data collection trustworthy

1. `.collector_status.json` writer.
2. collector logs.
3. venue diagnostics.
4. files metadata.
5. quality timeline/gaps/BBO analysis.

Definition of done:

- user can tell in 10 seconds whether the data is good enough to trust.

### Phase E: restore Jupyter as laboratory

1. notebooks directory;
2. helper API;
3. plotting API;
4. save strategy helper;
5. Jupyter process/nav.

Definition of done:

- user can iterate strategy code without leaving the intended workflow.

### Phase F: paper/realtime closure

1. paper daemon;
2. API start/stop;
3. collector IPC;
4. venue-only connections;
5. live paper UI;
6. paper vs backtest drift.

Definition of done:

- same strategy file runs in backtest and paper, with comparable metrics.

## 11. Дополнения из `91_LEGACY_CRITIQUE.md`, которые надо добавить в основной план

Внешняя критика полезна как инженерный bug checklist. Эти пункты стоит явно добавить в основной rework-plan:

1. Writer hardening.

Добавить в `collector/writer.py` валидацию типов перед PyArrow, try/except вокруг flush, запись ошибки в collector log и статус venue/writer. Writer не должен молча умирать из-за одного плохого сообщения парсера.

2. Batch/realtime parity по sigma.

Сейчас batch и realtime могут использовать разные формулы sigma, поэтому paper/live сигналы могут не совпадать с backtest. Нужно выбрать одну формулу, описать ее в контракте и добавить parity-test на одном и том же потоке бинов.

3. Reverse position accounting.

Для `position_mode="reverse"` надо закрывать старую позицию отдельной сделкой с `exit_reason="reversed"`, а не просто удалять ее из `open_positions`.

4. Logging как обязательный слой.

Добавить `logging.getLogger(__name__)` во все backend-модули, единый формат логов, `--log-level` для CLI, отдельные structured events для collector/backtest/paper ошибок.

5. Schema validation.

Добавить проверку JSON/Parquet contracts при записи: session artifacts, backtest artifacts, collector status, paper status. Минимум через Pydantic/dataclasses validation или JSON schema.

6. UI table mechanics.

Явно добавить сортировку, пагинацию/виртуализацию для больших таблиц, human-readable UTC formatting, loading/error/empty states и включенный Plotly modebar/zoom там, где план требует интерактивный анализ.

7. Backtest comparison.

Добавить `GET /api/backtests/compare` или эквивалентный UI/API сценарий сравнения 2-5 backtests, потому что Strategy comparison без сравнения результатов backtest неполон.

8. Quality metrics expansion.

Добавить в quality не только flags/BBO spreads/gaps, но и duplicate rate, timestamp monotonicity, median tick interval, BBO staleness, gap distribution.

9. Optional venue parity check.

Проверить список venue из исходных ноутбуков против `config/venues.yaml` и `REGISTRY`. Если dYdX v4 был реально в ноутбуке или пользовательском сборе, добавить его или явно зафиксировать, почему он исключен.

Эти пункты не меняют главный вывод моего плана, но делают его сильнее как инженерную спецификацию.

## 12. Acceptance checklist for 10/10

The project is 10/10 only when all checks pass:

- `from leadlag import load_session, list_sessions, run_backtest, run_monte_carlo` works.
- `load_session(reference).events.filter(signal='C').count == 229`.
- notebooks reproduce original notebook metrics.
- Strategy saved in Jupyter appears in UI.
- Run Backtest button works from UI.
- backtest has full `trades/equity/stats/montecarlo` artifacts.
- Explorer loads 519 events under 2s.
- Explorer click redraws under 200ms.
- BBO overlay visible for venues with BBO.
- No-BBO banner visible for MEXC/Gate/Hyperliquid.
- Trade Inspector shows leader/follower/BBO/entry/exit/MFE/MAE.
- Backtest UI shows fee and slippage impact clearly.
- Monte Carlo page shows p-value and percentile.
- Dashboard shows processes, pings, active files, collector state.
- Collector UI shows live per-venue health and logs.
- Quality UI flags bad venues and shows BBO spread stats.
- UTC displayed everywhere.
- API errors are structured and visible in UI.
- Collector status updates atomically every 2s.
- Paper start/stop works and does not double-connect when collector is running.
- No critical path depends on manual file editing outside Jupyter strategy workflow.
- Tests cover the above.

## 13. Final answer: will the user get 10/10 after this rework?

Yes, if and only if the full plan in this document is implemented and acceptance-tested on real data.

No, if only the earlier P0/P1 fixes are implemented. Earlier fixes would make parts of the system run, but the user still would not have the product described by the original task.

The real target is not "pages exist". The real target is: user opens the app, sees trustworthy data, finds lead-lag events, writes Python strategy in Jupyter, backtests it honestly, inspects every weakness, validates robustness, and knows the next trading decision.
