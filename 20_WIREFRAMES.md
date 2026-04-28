# LeadLag Lab — Wireframes (doc #20)

> Основа: docs #16 (domain), #17 (controls), #18 (design system), #19 (frame)
> Формат: один экран за раз. Каждый блок содержит ASCII-схему, аннотации компонентов и правила состояний.
> Нотация: `[Component]` → класс из doc #18. `→ url` → навигация. `//` → пояснение.

**Working status**

- Этот файл — канонический рабочий документ для screen-by-screen wireframes.
- Dashboard ниже уже переписан на основе реального `dashboard.html`, но он пока **не финализирован**.
- Финальная переработка Dashboard отложена до конца, после core pipeline screens.
- Следующий экран, который нужно добавить в этот файл: `Quality`.

---

## Screen Decision Protocol

Этот файл хранит не только layout-идеи, но и продуктовые решения по экранам.

### Что считать source of truth

- `leadlag/ui/*.html` и API-код — это источник фактов:
  - какие данные реально есть,
  - какие поля реально приходят,
  - какие состояния уже существуют,
  - какие backend-actions доступны.
- Но текущий HTML **не считается автоматическим UX source of truth**.
- Если current UI конфликтует с docs `#13`, `#15`, `#16`, `#17`, `#19`, приоритет у docs и pipeline logic.

### Перед любым новым screen-spec нужно решить концепцию

Для каждого экрана сначала надо зафиксировать:

- роль экрана в pipeline;
- owner entity;
- связь menu и content;
- какие child nodes действительно нужны;
- какие кнопки / таблицы / charts / тексты:
  - `Keep`
  - `Move`
  - `Remove`
  - `Postpone`

Это особенно важно для спорных вещей вроде:

- `Collector` как single root vs вложенный runtime tree;
- `Recordings` как самостоятельная ветка vs продолжение Collector;
- `Ticks`, `BBO`, `Bins` как tree nodes vs page-only detail sections;
- placement для `Analyze`, `Run BT`, `Run MC`, `Start Paper`;
- размер и приоритет charts;
- где нужен list, а где detail;
- какие diagnostic tables действительно должны жить на экране.

### Важность элемента и footprint надо оценивать отдельно

Перед layout-решением по экрану нужно пройтись по ключевым элементам:

- primary / secondary / diagnostic actions;
- status blocks и alerts;
- charts;
- tables;
- text blocks;
- related entities.

Для каждого важного элемента нужно отдельно зафиксировать:

1. `Pipeline importance` (`0-10`)
2. `Spatial footprint` (`XS / S / M / L`)

Это разные вещи.

Правила:

- важный элемент не обязан быть большим;
- положение на экране зависит прежде всего от роли в pipeline;
- размер зависит от читаемости, плотности информации, частоты использования и нужды в сравнении;
- если элемент можно прочитать и понять компактно, его нельзя раздувать;
- минимализм в размерах считается default, пока нет сильной причины дать элементу больше места.

Особенно важно для charts:

- маленький chart допустим только если это действительно mini-chart / sparkline;
- если график нужен для чтения формы движения, а не просто для наличия, ему нужно дать достаточно площади;
- `важный график` и `большой график` не являются синонимами, но chart нельзя ужимать до бесполезного состояния.

Точно так же для text/table blocks:

- важная таблица может остаться компактной, если она нужна для быстрого scan + перехода в detail;
- важный текстовый статус или CTA может быть маленьким по размеру, но верхним по position priority;
- diagnostic logs, files и helper content обычно не должны доминировать в layout.

### Decision matrix обязателен для спорных мест

Если есть фундаментальная неоднозначность, нужно:

1. описать варианты,
2. жёстко покритиковать каждый,
3. поставить оценку `0-10`,
4. выбрать один вариант или вынести вопрос пользователю.

Правило автономности:

- если один вариант явно сильнее (`примерно 9-10/10`, остальные заметно слабее), ИИ принимает решение сам и объясняет почему;
- если варианты близки и trade-offs неочевидны, ИИ должен спросить пользователя до фиксации screen contract.

### HTML allowed only after concept contract

Порядок такой:

1. concept decisions,
2. wireframe/spec,
3. HTML mock,
4. iteration.

Если concept decisions не зафиксированы, HTML-прототип считается преждевременным.

### Screen copy ban

- В wireframe можно писать пояснения в markdown через `//` и bullets.
- Но сам экран не должен содержать explanatory copy, helper text, commentary blocks или sublabels, объясняющие решение.
- На экране допускаются только operational labels: названия сущностей, состояний, метрик, кнопок, empty/error states и danger warnings.

### Формат для всех следующих экранов

Начиная со следующего экрана, каждый новый block в этом файле должен включать:

```markdown
### N.0 Concept Contract
- Роль экрана в pipeline
- Owner entity
- Menu/content relationship
- Keep / Move / Remove / Postpone
- Pipeline importance ключевых элементов (`0-10`)
- Spatial footprint ключевых элементов (`XS / S / M / L`) + почему
- Однозначные решения
- Вопросы, которые нужно вынести пользователю
```

Это нужно, чтобы wireframe не превращался в прямую копию backend-first HTML.

Каждый `Concept Contract` обязан явно фиксировать не только `что важно`, но и `сколько места это должно занимать`.

---

## Экран 1 — Dashboard

**URL:** `dashboard.html`
**Тип:** `single`
**Статус:** provisional, не финальный dashboard contract

### 1.1 Sidebar State

- Активен top-level узел `Dashboard`.
- Sidebar использует frame из doc #19: ширина `380px`, независимый scroll, зоны `RUNTIME / DATA / RESEARCH / WORKBENCH`.
- Для Dashboard нет action rail и нет inline form. Это landing screen, не owner-экран для create/delete.
- В `RUNTIME` виден `Collector` со status badge `LIVE` / `idle`; в `DATA` и `RESEARCH` видны counts для `Recordings` и `Strategies`.

### 1.2 Context Bar

```text
● Dashboard  ·  runtime, health, latest pipeline snapshots          [toast zone]
```

- Слева: `.dot.blue` + `Dashboard` (`.label.mono`) + muted meta.
- Справа: toast slot для завершённых мутаций, например `analysis_20260425 ready · 165 events`.
- Dashboard не показывает нижнюю секцию `Related Entities`.

### 1.3 Content Sections

#### 1.3.1 Start Here Banner

- Компоненты: `.banner.warn`, text link / button-link.
- Реальные данные: баннер показывается, когда одновременно пусты `collections`, `sessions`, `strategies`.
- Текст из текущего HTML сохраняется по смыслу: `No data yet. Start here: Collect Data →`.
- Состояния:
  - Нормальное: баннер скрыт.
  - Пустое состояние первого запуска: баннер показан сразу под context bar.
  - Ошибка: если dashboard API не загрузился, вместо CTA показывается общий error banner.

#### 1.3.2 Top Summary Strip

- Источник: `renderTop(sys, collector, paper, collections, sessions, backtests, strategies)`.
- Компоненты: один `.panel` с компактной сеткой stat-items, внутри используются `.label.group`, `.chip`, `.badge.live/.idle`.
- Реальные поля:
  - `UTC` ← `sys.ts`
  - `Recordings` ← `collections.length`
  - `Analyses` ← `sessions.length`
  - `Strategies` ← `strategies.length`
  - `Backtests` ← `backtests.length`
  - `Collector` ← `collector.stale`, `collector.running`, `collector.recording_id`
  - `Paper` ← `paper.blocked`, `paper.mode`, `paper.running`
- Состояния:
  - Нормальное: все 7 summary items заполнены.
  - Collector stale: item показывает `stale <recording_id>`.
  - Collector stopped: item показывает `stopped`.
  - Paper blocked: item показывает `blocked: <mode>`.

#### 1.3.3 System Health

- Компоненты: `.panel` + metric cards + `chart-grid` из трёх charts.
- Реальные поля:
  - CPU ← `sys.cpu_percent`
  - RAM ← `sys.ram_used_gb`, `sys.ram_total_gb`, `sys.ram_percent`
  - Disk ← `sys.disk_used_gb`, `sys.disk_total_gb`
  - `data/` ← `sys.disk_data_gb`
  - Net recv / sent ← `sys.net_bytes_recv`, `sys.net_bytes_sent`
  - Charts из `/api/system/history?minutes=60`:
    - `CPU` ← `hist[].cpu_pct`
    - `RAM` ← `hist[].ram_used_gb`
    - `Network` ← `hist[].net_down_bps`, `hist[].net_up_bps`
- Состояния:
  - Нормальное: metric cards + все 3 графика.
  - Пустая история: metric cards остаются, chart area показывает muted placeholder `No history yet`.
  - Ошибка: секция заменяется error banner с retry.

#### 1.3.4 Processes and Pings

- Компоненты: `breakdown-grid` из двух `.panel` с таблицами.
- Реальные таблицы:
  - `Processes`
    - `name`
    - `status`
    - `pid`
    - `mem MB` ← `mem_mb`
    - `uptime` ← `uptime_s`
  - `Pings to Venues`
    - `venue`
    - `host`
    - `latency` ← `latency_ms`
    - `status`
- Состояния:
  - Нормальное: обе таблицы заполнены.
  - Нет данных по ping: пустая строка `No venue pings yet`.
  - Ошибка: соответствующая панель показывает error banner, соседняя панель остаётся доступной.

#### 1.3.5 Collector Status

- Это самая важная operational секция Dashboard.
- Компоненты: `.panel`, inline status banner, toolbar/action strip, table-scroll, venue table.
- Реальные элементы и данные:
  - Заголовок `Collector Status`
  - `staleBanner` + `staleAge` если `collector.stale === true`
  - Toolbar текущего HTML:
    - `Start Collection`
    - `Stop Collector`
    - `Clear stale status`
    - `Run Analysis`
    - `Open Collector`
    - `Open Latest Analysis`
  - Таблица `collectorVenues`:
    - `venue` ← `r.name`
    - `role`
    - `status`
    - `ticks`
    - `ticks/s` ← `ticks_per_s_1m`
    - `BBO`
    - `BBO/s` ← `bbo_per_s`
    - `reconnects`
    - `last tick UTC` ← `last_tick_ts`
    - `seconds idle`
    - `last price`
    - `last error`
  - Start form в текущем HTML:
    - `Duration h`
    - `Rotation m`
    - venue selection table: `use`, `venue`, `role`, `BBO`
    - presets: `Leaders`, `Followers`, `All`, `Clear`
- Состояния:
  - Running: `Stop Collector` enabled, stale banner hidden.
  - Stopped/idle: `Start Collection` enabled.
  - Stale snapshot: banner shown, venue table dimmed with stale state.
  - No venues: empty table + muted hint.

#### 1.3.6 Paper Trader

- Компоненты: `.panel` + stat cards + single CTA.
- Реальные поля from `renderPaperStatus(paper)`:
  - `Strategy` ← `paper.strategy`, `paper.strategy_version`
  - `Uptime` ← `paper.uptime_s`
  - `Today Equity` ← `paper.equity_today_bps`
  - `Trades Today` ← `paper.n_trades_closed`, hit rate from `paper.n_wins`
  - `Last Signal` ← `paper.last_signal_time`
  - `Status` ← `running` or `blocked: <mode>`
- Состояния:
  - Running: показываются все cards.
  - Stopped: показывается только compact card `Status = stopped`.
  - Blocked: `Status` item явно показывает block reason.

#### 1.3.7 Latest Pipeline Snapshots

- Компоненты: `breakdown-grid` из трёх таблиц.
- Цель: показать последний материал пайплайна, а не агрегированную essay-сводку.
- Таблица `Latest Recordings` (публично: `Recordings`, не `Collections`):
  - `id`
  - `range UTC` ← `t_start_ms → t_end_ms`
  - `ticks` ← `n_ticks`
  - `BBO` ← `n_bbo`
  - `venues` ← `n_venues`
  - `analysis` ← `latest_analysis_id`; если analysis ещё нет, показывать muted state `No analysis yet`
- Таблица `Latest Analyses` (не `Sessions`):
  - `id`
  - `date`
  - `events` ← `n_events`
  - `A/B/C` ← `n_signal_a`, `n_signal_b`, `n_signal_c`
  - `venues` ← `n_venues`
- Таблица `Latest Backtests`:
  - `id`
  - `strategy`
  - `trades` ← `n_trades`
  - `net` ← `total_net_pnl_bps`
  - `win` ← `win_rate`
  - `MC` ← `has_montecarlo`
- Состояния:
  - Нормальное: показываются до 8 последних строк в каждой таблице.
  - Нет recordings: в колонке `Recordings` пустой state `No recordings yet`.
  - Нет analyses/backtests: независимые empty states в соответствующих таблицах.

#### 1.3.8 Active Files

- Компоненты: `.panel` + `table-scroll`.
- Реальные поля:
  - `path`
  - `size MB` ← `size_mb`
  - `rows`
  - `time range UTC` ← `ts_min → ts_max`
  - `venues`
  - `modified UTC` ← `modified`
- Состояния:
  - Нормальное: показываются последние 8 файлов (`files.slice(-8).reverse()`).
  - Нет файлов: empty row `No active files`.
  - Ошибка: error banner в пределах секции.

### 1.4 Navigation

| Элемент | Destination |
|---|---|
| `Start here: Collect Data →` | `collector.html` |
| `Open Collector` | `collector.html` |
| `Open Latest Analysis` | `quality.html?id=<recording_id>` |
| `Latest Recordings` row | `recordings.html?id=X` |
| `Latest Analyses` row | `quality.html?id=<recording_id>` |
| `Latest Backtests` row | `backtest.html?id=X` |
| `MC` action in backtests table | `montecarlo.html?bt_id=X` |
| `Open Paper Dashboard` | `paper.html?strategy=X` if strategy known, otherwise `paper.html` |

### 1.5 Delta from current HTML

- Встроить Dashboard в frame из doc #19: sidebar `380px`, context bar, content sections без isolated plain `<main>`.
- Переименовать публичные лейблы `Collections` → `Recordings`, `Sessions` → `Analyses`; API имена можно не менять.
- Сохранить реальные content sections из текущего HTML, но убрать из wireframe выдуманные блоки `Active Jobs` и отдельный `Paper Runs` list, которых в коде нет.
- `Open Latest Analysis` и строки `Latest Analyses` должны вести в canonical detail `quality.html?id=<recording_id>`; переход в `Explorer` остаётся отдельным analysis-centric path.
- Кнопку `Analyze` из колонки `Latest Recordings` убрать с Dashboard и перевести этот action на `recordings.html?id=X&action=analyze`, чтобы Dashboard не создавал analysis напрямую.
- `Start Collection` не должен открывать modal `<dialog>`: заменить на inline expand в `collector.html` или на переход в Collector, потому что modals запрещены doc #13 и #19.
- Для всех секций явно описать состояния `loading / empty / error`; текущий HTML почти везде предполагает только happy path.
- `Collector Status` нужно стилизовать через tokens и badge semantics из docs #18-19: stale, running, idle, venue health.
- `Active Files` оставить последней low-priority секцией, но визуально тише, чем pipeline blocks выше.

---

## Экран 2 — Collector

**URL:** `collector.html[?venue=X]`
**Тип:** `single + filter`

### 2.1 Sidebar State

- Активен top-level узел `Collector` в зоне `RUNTIME`.
- Если открыт `collector.html` без query param, в sidebar выделен узел `Collector`.
- Если открыт `collector.html?venue=binance`, выделен дочерний venue-row `binance`, а родитель `Collector` остаётся open.
- Venue в sidebar трактуется как navigation filter, а не отдельная domain entity.
- Для sidebar collector-ветки допустимы только status badge и summary chip (`LIVE` / `idle`, event-rate или venues count). Start/Stop controls не переносятся в row.

### 2.2 Context Bar

```text
● Collector  ·  all venues  ·  runtime subprocess                  [toast zone]
```

- Без `?venue=`:
  - label: `Collector`
  - meta: `all venues`
- С `?venue=X`:
  - label: `Collector`
  - meta: `venue filter: X`
- Правая зона: toast после мутаций вроде `collector started`, `collector stopped`, `venue disabled`, `recording ready`.

### 2.3 Content Sections

#### 2.3.1 Control Bar

- Компоненты: `.panel`, compact inline controls, action buttons.
- Это главная operational секция экрана.
- Реальные поля из текущего HTML:
  - `Duration h` ← `#durationHours`
  - `Rotation m` ← `#rotation`
  - selection presets:
    - `Leaders`
    - `Followers`
    - `All`
    - `Clear`
    - `WS URLs`
  - run controls:
    - `Start`
    - `Stop`
    - `Restart`
    - `Refresh`
    - `Clear stale`
    - `Analyze`
  - current status kv:
    - `running`
    - `proc alive`
    - `recording id`
    - `started UTC`
    - `planned`
    - `rotation`
    - `updated UTC`
    - `state`
- Состояния:
  - Idle: `Start` enabled, `Stop` disabled.
  - Running: `Stop` enabled, `Start` disabled.
  - Stale: `Clear stale` visible, status `state = stale`.
  - No recordings yet: `Analyze` disabled.
  - Error: top-level error banner for failed start/stop/restart action.

#### 2.3.2 Recording Progress

- Эта секция обязательна по doc #19, хотя в текущем HTML её ещё нет отдельным блоком.
- Компоненты: `.panel`, thin progress bar, status chip, muted meta.
- Реальные / required data:
  - `recording_id`
  - `start_time`
  - `planned_duration_s`
  - progress = elapsed / planned duration
  - `running` / `stale` / `stopped`
- Состояния:
  - Running: блок показан с progress bar.
  - Stale: блок показан с warn state.
  - Stopped: блок скрыт.
  - Unknown timing: вместо progress процента показывается indeterminate thin bar.

#### 2.3.3 Venue Selection

- Компоненты: `.panel`, `table-scroll`, inline toggles/checks.
- Реальная таблица `#venueConfig`:
  - `use`
  - `venue`
  - `role`
  - `taker`
  - `maker`
  - `BBO`
  - `keepalive`
  - `enabled`
  - `WS URL` (optional diagnostic column)
- Состояния:
  - Нормальное: таблица всех venues.
  - `?venue=X`: строка `X` pinned/visible first; остальные либо скрыты, либо de-emphasized по filter mode.
  - `WS URLs` off: колонка `WS URL` скрыта.
  - Error: если `/api/venues` не загрузился, показывается error banner вместо таблицы.
- Примечание:
  - текущий HTML показывает `enabled` только как read-only checkmark;
  - target state по doc #13 и #15: здесь должны быть реальные enable/disable toggles с `PATCH /api/venues/{name}`.

#### 2.3.4 Live Monitor

- Компоненты: `.panel`, wide connection table, inline spark bars.
- Реальная таблица `#live`:
  - `venue`
  - `role`
  - `status`
  - `ticks`
  - `ticks/s 1m`
  - `ticks/s 10m`
  - `BBO`
  - `BBO/s`
  - `reconnects`
  - `last reconnect`
  - `last tick`
  - `seconds idle`
  - `last price`
  - `median price`
  - `last error`
  - `uptime %`
- Состояния:
  - Running: таблица fully populated and polling.
  - Stale: statuses forced into stale state.
  - Stopped: table remains visible with latest snapshot or idle values.
  - `?venue=X`: only that venue shown.
  - No venues selected: empty table + muted hint.

#### 2.3.5 Live Charts

- Эта секция нужна по doc #19, но в текущем HTML отсутствует.
- Компоненты: `chart-grid`, one tick chart + one candlestick/price chart.
- Required data:
  - latest per-venue ticks over trailing window
  - venue filter integration with `?venue=X`
- Состояния:
  - Running: charts visible.
  - Stopped: section hidden or replaced by `No live recording`.
  - `?venue=X`: only one venue plotted.
  - No tick history endpoint: section replaced by muted placeholder until backend support exists.

#### 2.3.6 Ping Chart

- Эта секция нужна по doc #19 как separate visibility layer over venue connectivity.
- Компоненты: single chart with one line per venue + checkboxes.
- Required data:
  - ping history timeline per venue
  - current filter state
- Состояния:
  - Default: all enabled venues visible.
  - `?venue=X`: only one line visible, other checkboxes disabled/hidden.
  - No history: placeholder `No ping history yet`.

#### 2.3.7 Collector Log

- Компоненты: `.panel`, filter toolbar, scrollable log surface.
- Реальные controls:
  - `Venue` filter ← `#logVenue`
  - `Type` filter ← `#logType`
  - `Auto-scroll`
- Реальные log fields:
  - `ts_ms`
  - `venue`
  - `event_type`
  - `message`
- Состояния:
  - Нормальное: newest logs visible, auto-scroll on by default.
  - `?venue=X`: venue filter preselected to `X`.
  - No logs: muted empty state.
  - Error: error banner replaces log box.

#### 2.3.8 Files

- Компоненты: `.panel`, compact table.
- Реальная таблица `#files`:
  - `path`
  - `size`
  - `rows`
  - `time range UTC`
  - `venues`
- Состояния:
  - Нормальное: latest 12 files shown in reverse order.
  - No files: `No collector files yet`.
  - `?venue=X`: table filtered to files containing venue `X`.

#### 2.3.9 Related Entities

- Collector не имеет owned children как domain entity, но related context внизу экрана нужен.
- Показывать:
  - current active recording if exists → `recordings.html?id=X`
  - latest ready recording → `recordings.html?id=X`
  - latest analysis if created from newest recording → `quality.html?id=<recording_id>`
- Если ничего ещё нет:
  - `No recordings yet`

### 2.4 Navigation

| Элемент | Destination |
|---|---|
| sidebar `Collector` row | `collector.html` |
| sidebar venue row | `collector.html?venue=X` |
| active recording in related entities | `recordings.html?id=X` |
| latest ready recording in related entities | `recordings.html?id=X` |
| latest analysis in related entities | `quality.html?id=<recording_id>` |
| stale warning / collector error CTA | `collector.html` |

### 2.5 Delta from current HTML

- Встроить Collector в frame из doc #19: sidebar `380px`, context bar, sections, related entities.
- Добавить venue filter mode через `collector.html?venue=X`; current HTML this does not drive section filtering.
- `Venue Selection` перевести из read-only `enabled` column в реальные enable/disable toggles с `PATCH /api/venues/{name}`.
- `Analyze` убрать из primary collector control bar: canonical analysis creation flow должен жить в `recordings.html`, не в Collector.
- Добавить отдельный `Recording Progress` block вместо того, чтобы прятать recording state только в `kv` status.
- Добавить `Live Charts` section:
  - tick chart 5 min
  - candlestick / price chart 5 min
- Добавить `Ping Chart` section с историей latency по venue.
- `Live Monitor` оставить как detail diagnostics, но при `?venue=X` фильтровать до одной venue.
- `Collector Log` должен уметь открываться уже с preselected venue filter из `quality.html?venue=X`-style hints.
- `Files` оставить как lower-priority operational block, не как главное содержание экрана.
- Все create/run flows должны быть inline; modal windows не использовать.

---

## Экран 3 — Recordings

**URL:** `recordings.html[?id=X][&action=analyze][&confirm_delete=1]`
**Тип:** `list + inline detail`

### 3.0 Concept Contract

- Роль экрана в pipeline:
  - первый data screen после завершения сбора;
  - место, где пользователь выбирает `Recording`, оценивает что запись получилась, и запускает `Analysis`;
  - canonical bridge между `Collector` и `Quality`.
- Owner entity:
  - page owner = `Recordings` group;
  - selected detail owner = `Recording`;
  - `Analysis` показывается здесь как owned child выбранного `Recording`, но не как самостоятельный owner экрана.
- Menu/content relationship:
  - sidebar already owns tree `Recordings -> Recording -> Analysis`;
  - content area не должна дублировать весь tree во всю высоту;
  - content показывает compact list всех recordings и один selected recording detail ниже/рядом в той же странице.
- Keep:
  - merge hint `<45 min`;
  - recording summary fields;
  - analyses list with real metrics;
  - inline `New Analysis` form;
  - inline delete confirm for recording and analysis;
  - auto-navigate to `quality.html?id=<recording_id>` after analysis job completes.
- Move:
  - analysis create form из "у каждой записи раскрыто всё сразу" в selected recording detail;
  - delete triggers из всегда-видимых destructive buttons в selected-row/detail state;
  - generic status line в toast / banner / inline progress state.
- Remove:
  - pattern "все recordings раскрыты одновременно";
  - повторяющиеся toolbar headers, где summary и actions смешаны в одну строку без иерархии;
  - глобальный page-top `Loading...` как единственное состояние секции.
- Postpone:
  - compare analyses;
  - bulk delete / batch analyze;
  - any file-level raw parquet diagnostics on this page;
  - extra recording charts until there is a real product reason and endpoint support.
- Pipeline importance ключевых элементов:
  - selected recording summary: `10/10`
  - `Run Analysis` action: `10/10`
  - analyses table of selected recording: `9/10`
  - recording list / picker: `9/10`
  - analysis job progress: `8/10`
  - delete recording / analysis: `4/10`
  - merge hint: `3/10`
- Spatial footprint ключевых элементов:
  - recording list: `M`
    - нужен scan по нескольким recordings, но это не главный detail surface;
  - selected recording summary + actions: `S`
    - важный блок, но информация компактная;
  - analyses table: `M`
    - это главный downstream material, таблице нужна читаемая ширина;
  - new analysis form: `S`
    - параметров мало, форма должна быть inline и плотной;
  - analysis job progress: `XS`
    - high-importance, low-footprint status strip;
  - delete confirm strips: `XS`
    - destructive state должен быть заметен, но временный;
  - merge hint: `XS`
    - informational warning, не должен доминировать.
- Decision matrix:
  - вариант A: full accordion list, где каждая запись раскрывается прямо в общем потоке
    - проблема: page дублирует sidebar tree, быстро превращается в длинную ленту, `Analyze` формы начинают конкурировать между собой;
    - оценка: `3/10`
  - вариант B: чистый detail page только для `?id=X`, а список целиком уходит в sidebar
    - проблема: слишком резкий прыжок между list-state и detail-state, `recordings.html` без `id` становится почти пустым;
    - оценка: `6/10`
  - вариант C: compact recordings list + один selected inline detail block на этой же странице
    - сильные стороны: сохраняет list view из doc #19, не дублирует sidebar полностью, даёт нормальное место для analyses и `Run Analysis`;
    - оценка: `9/10`
  - выбран вариант C.
- Однозначные решения:
  - `Analyze` остаётся canonical action этого экрана и этого owner-level;
  - параметры analysis живут только в content inline form, не в sidebar;
  - `Quality` и `Explore` остаются child-level context links у каждой analysis;
  - `Delete` показывается только в selected/detail state, не в каждой collapsed row;
  - page without data должна отправлять пользователя обратно в `Collector`.
- Вопросы, которые нужно вынести пользователю:
  - нет; по текущим docs и raw HTML решение достаточно однозначно.

### 3.1 Sidebar State

- Активен top-level узел `Recordings` в зоне `DATA`.
- При `recordings.html` без `?id=` выделен group node `Recordings`.
- При `recordings.html?id=X`:
  - в sidebar выделен row `Recording X`;
  - его parent `Recordings` открыт;
  - если есть выбранный `Analysis` через переход в `quality.html` или `explorer.html`, текущий page ownership всё равно остаётся за `Recording`.
- На recording-row в sidebar допустимы:
  - summary chip: duration или venue count;
  - primary inline action: `Analyze`;
  - optional danger trigger: `Delete` только для selected row.
- На analysis-row в sidebar допустимы:
  - context links `Quality` / `Explorer`;
  - primary action `Run BT`;
  - optional danger trigger `Delete`.

### 3.2 Context Bar

```text
● Recordings  ·  all completed data captures                      [toast zone]
```

- Без `?id=`:
  - label: `Recordings`
  - meta: `all completed data captures`
- С `?id=X`:
  - label: `Recording`
  - meta: `Apr 19, 2026 · 4.0h · 11 venues` from `t_start_ms`, `t_end_ms`, `n_venues`
- Правая зона:
  - toast / mutation status:
    - `analysis_20260419_... ready · 165 events`
    - `Deleting rec_...`
    - `Deleted analysis_...`

### 3.3 Content Sections

#### 3.3.1 Merge Hint

- Компоненты: `.banner.warn`
- Реальный факт из current HTML:
  - показывается, если recordings list не пустой
  - текст по смыслу: recordings separated by less than `45 min` are merged automatically
- Состояния:
  - Есть recordings: banner shown above list
  - Empty: banner hidden

#### 3.3.2 Recordings List

- Компоненты: `.panel`, compact selectable table/list rows
- Это primary navigation surface внутри страницы, но не главный diagnostic block.
- Реальные summary fields per recording:
  - `id`
  - `t_start_ms -> t_end_ms`
  - duration from `t_end_ms - t_start_ms`
  - `n_venues`
  - `n_ticks`
  - derived `analyses.length`
- Структура row:
  - line 1: `id`
  - line 2 / summary chips: date range, duration, venues, ticks, analyses count
  - selected row gets stronger surface treatment
- Состояния:
  - Loading: skeleton / muted rows inside panel
  - Empty: decision strip `No recordings yet` + CTA `Start in Collector →`
  - Normal: all recordings listed
  - `?id=X`: matching row selected and scrolled into view if needed

#### 3.3.3 Selected Recording Summary

- Компоненты: `.panel`, compact stat strip, action rail, optional danger strip host
- Показывается:
  - только когда есть selected recording;
  - default selection = first available recording if page opened without `?id=`.
- Реальные fields:
  - `id`
  - `t_start_ms`
  - `t_end_ms`
  - duration
  - `n_venues`
  - `n_ticks`
  - derived analyses count
- Primary action:
  - `New Analysis`
- Secondary actions:
  - `Open Collector`
- Danger:
  - `Delete Recording`
- Состояния:
  - Normal: summary + actions visible
  - `confirm_delete=1` or delete click: inline danger strip expands under actions
  - Delete in progress: strip remains, controls disabled, toast/status updates

#### 3.3.4 Analyses of This Recording

- Компоненты: `.panel`, `table-scroll`, row actions
- Это главный downstream content block на экране.
- Реальные columns from current HTML:
  - `analysis`
  - `date`
  - `events` ← `n_events`
  - `A/B/C` ← `n_signal_a`, `n_signal_b`, `n_signal_c`
  - `venues` ← `n_venues`
  - `actions`
- Action set per row:
  - `Quality`
  - `Explore`
  - `Delete`
- Состояния:
  - No analyses yet: empty state `No analyses yet`
  - Normal: one row per analysis linked to this recording
  - Delete analysis expanded: inline danger strip under that row
  - After successful delete: table refreshes, recording remains selected

#### 3.3.5 New Analysis Inline Form

- Компоненты: `.panel` or `.inline-expand` attached directly below selected recording summary
- Trigger:
  - `New Analysis`
  - also auto-open if URL contains `action=analyze`
- Реальные params:
  - `threshold_sigma`
  - `bin_size_ms`
  - `confirm_window_bins`
  - `ema_span_bins`
- Controls:
  - `Run Analysis`
  - `Cancel`
- Состояния:
  - Collapsed by default
  - Expanded idle: inputs editable
  - Running:
    - inputs disabled
    - progress bar visible
    - progress text from job `message` / `stage`
  - Completed:
    - progress reaches `100%`
    - result line shows analysis id + events count
    - page auto-navigates to `quality.html?id=<recording_id>`
  - Failed:
    - inline error text
    - progress state switches to failed

#### 3.3.6 Analysis Job Progress

- Компоненты: thin progress strip + muted status text
- Реальные fields from polling:
  - `job_id`
  - `progress`
  - `message`
  - `stage`
  - `status`
  - `analysis_id`
  - `events_count` or `n_events`
- Поведение:
  - progress visible both in inline form and sidebar active recording row
  - polling timeout after current hard limit (`600` attempts in raw code) should surface explicit timeout error
- Состояния:
  - `queued`
  - `running`
  - `completed`
  - `failed`
  - `timeout`

#### 3.3.7 Related Entities

- Секция обязательна и всегда внизу экрана.
- Для selected recording показывать:
  - parent-ish upstream context:
    - `Collector` → `collector.html`
  - owned children:
    - analyses linked to this recording
  - downstream links:
    - latest `Quality`
    - latest `Explorer`
- Если analyses ещё нет:
  - `No analyses yet`

### 3.4 Navigation

| Элемент | Destination |
|---|---|
| sidebar `Recordings` group | `recordings.html` |
| recording row in page list | `recordings.html?id=X` |
| `Start in Collector →` empty CTA | `collector.html` |
| `Open Collector` | `collector.html` |
| `New Analysis` | `recordings.html?id=X&action=analyze` |
| analysis `Quality` | `quality.html?id=<recording_id>` |
| analysis `Explore` | `explorer.html?analysis=X` |
| successful analysis completion | `quality.html?id=<recording_id>` |

### 3.5 Delta from current HTML

- Перестроить страницу из "каждая запись сразу развёрнута" в `compact list + one selected detail`.
- Сохранить все реальные data fields и actions, но убрать визуальную плоскость, где summary, children и destructive actions смешаны в одну ленту.
- Сделать `Recording` canonical selected owner на странице; `Analysis` остаётся child block, а не отдельным полноправным header на этом экране.
- `New Analysis` оставить inline на странице, потому что doc #18 запрещает parameter forms в sidebar.
- `Delete Recording` и `Delete Analysis` оставить inline, но показывать их только в selected/detail context, чтобы collapsed rows не превращались в danger soup.
- Пустое состояние усилить до pipeline-next-step CTA: не просто `No recordings yet`, а переход в `Collector`.
- `Loading`, `running`, `failed`, `timeout` states для analysis job описать явно; current HTML partially handles them, но wireframe должен сделать их first-class.
- `renderPageTitle` metadata сохранить в context bar, а не в отдельной плоской header row внутри content.
- Не добавлять сюда charts, file diagnostics или quality-like venue breakdown: этот экран про выбор recording и запуск analysis, а не про детальный forensic review.

---

## Экран 4 — Quality

**URL:** `quality.html?id=X[&filter=bad]`
**Тип:** `recording diagnostic detail`

### 4.0 Concept Contract

- Роль экрана в pipeline:
  - первый forensic review выбранного `Recording` после того, как по нему уже был сделан хотя бы один `Analysis`;
  - место, где пользователь решает, можно ли доверять сигналу и идти дальше в `Explorer` / `Strategy`;
  - canonical checkpoint между `Recordings` и `Explorer`.
- Owner entity:
  - page owner = selected `Recording`;
- `Analysis` не участвует в route или page state этого экрана;
  - venue rows на странице — diagnostic sub-objects, не отдельные domain entities.
- Menu/content relationship:
  - sidebar owns tree `Recordings -> Recording -> Analysis`;
  - при открытом `quality.html?id=X` активен row `Recording X`;
- analyses остаются child context только в sidebar и на `recordings.html`, но не в state самого `Quality`.
- Keep:
  - quality readiness decision strip;
  - venue flags and recommendations;
  - `Show only bad/warning` filter;
- action `Back to Recording`;
  - timeline gaps and BBO quality diagnostics;
  - recording file integrity diagnostics for the selected `Recording`;
- real metrics: `bin_coverage_pct`, `bbo_coverage_pct`, `price_deviation_from_leader_bps`, `reconnects`, `downtime_s`.
- Move:
  - analysis summary cards из "одинаковые KPI tiles" в compact recording summary + stat strip;
  - venue recommendation from isolated last column semantics into row-level actionable review.
- Remove:
  - pattern where charts dominate above the decision about whether analysis is usable;
  - equal visual weight for all diagnostics regardless of severity;
  - giant top toolbar as the main structural header.
- Postpone:
  - saved quality presets;
  - compare two analyses side by side;
  - printable PDF / elaborate report builder;
  - per-venue deep drilldown pages.
- Pipeline importance ключевых элементов:
  - quality decision / proceed readiness: `10/10`
  - flagged venues table: `10/10`
- `Back to Recording` action: `7/10`
  - recording quality summary identity + counts: `9/10`
  - timeline gaps diagnostics: `7/10`
  - BBO diagnostics: `7/10`
  - recording file integrity diagnostics: `8/10`
  - delete analysis: `4/10`
- Spatial footprint ключевых элементов:
  - recording summary + action rail: `S`
    - важный блок, но данные компактные;
  - decision strip: `XS`
    - high-importance gate, должен быть заметным и коротким;
  - flagged venues table: `L`
    - это главный рабочий surface, rows нужно сравнивать по нескольким метрикам;
  - supporting diagnostics grid: `M`
    - достаточно места для trend/gap scan, но не больше главной таблицы;
  - related entities: `S`
    - нужен для pipeline navigation, не для глубокого анализа.
- Decision matrix:
  - вариант A: оставить страницу как raw diagnostics dashboard с множеством равновесных charts
    - проблема: useful facts есть, но главный вопрос "recording usable or not?" теряется в визуальном шуме;
    - оценка: `4/10`
  - вариант B: радикально ужать экран до одного pass/fail verdict + списка bad venues
    - проблема: слишком агрессивно выбрасывает supporting evidence, пользователь не сможет понять характер проблем перед следующим research step;
    - оценка: `6/10`
  - вариант C: compact recording summary + readiness strip + large venue review table + secondary diagnostics below
    - сильные стороны: сохраняет реальные forensic данные, но держит ownership на `Recording`, а не на производном `Analysis`;
    - оценка: `9/10`
  - выбран вариант C.
- Однозначные решения:
- `Recording` — canonical owner этого экрана;
- `Quality` не держит analysis context вообще: ни в URL, ни в summary, ни в related entities;
  - `Show only bad/warning` остаётся page-level filter, а не sidebar-state;
  - venue diagnostics остаются page content, не tree nodes;
  - `Quality` self-link inside analysis action strip is forbidden;
  - `Run BT` is not a required inline action on this screen;
  - `Related Entities` must list only factual linked entities, not abstract destinations like generic `strategies`;
  - delete analysis belongs to `recordings.html`, not to `quality.html`; Quality не управляет жизненным циклом Analysis.
- Вопросы, которые нужно вынести пользователю:
  - нет; page ownership полностью закреплён за `Recording`.

### 4.0.1 Exhaustive Diagnostic Slice Sweep

Экран нужно проектировать не от "какие chart'ы красиво смотрятся", а от "какие разрезы реально отвечают на вопросы о качестве данных `Recording`".

Широкий перебор кандидатов делается на стадии мышления/обсуждения, но в этот документ попадает только итоговый shortlist ниже.

### 4.0.2 Diagnostic Cuts — Final Selection

#### Mandatory cuts

Без этих разрезов screen не закрывает core job:

1. `Composite reliability quadrant`
   - why: лучший single-glance summary по venue;
   - encoding:
     - X = `bin_coverage_pct`
     - Y = `price_deviation_from_leader_bps`
     - bubble size = `downtime_s`
     - color = `flag`
   - что отвечает: какие venue одновременно полные, стабильные и не разваливаются по времени.

2. `Coverage by time bucket`
   - why: average coverage скрывает локальные провалы;
   - encoding:
     - X = time buckets across recording
     - Y = venue
     - color = coverage tier
   - что отвечает: где именно во времени была проблема.

3. `Gap severity distribution`
   - why: count gaps без масштаба проблемы слишком слаб;
   - encoding:
     - histogram by duration buckets (`<1s`, `1–5s`, `5–30s`, `30s+`)
   - что отвечает: это мелкий шум или catastrophic continuity failure.

4. `Gap downtime share by venue`
   - why: нужен ranked view, кто больше всех испортил запись;
   - encoding:
     - horizontal bars sorted descending
   - что отвечает: каких venue стоит бояться в первую очередь.

5. `BBO spread distribution`
   - why: один `p95` недостаточен, нужны tails;
   - encoding:
     - box plot per venue
   - что отвечает: где execution cost structurally bad.

6. `Leader deviation distribution`
   - why: нужно отличать outliers от structural drift;
   - encoding:
     - box/violin per venue
   - что отвечает: насколько venue вообще синхронен с лидером.

7. `Time-bucket overall quality ribbon`
   - why: нужен one-dimensional temporal summary для scan;
   - encoding:
     - thin ribbon / stacked health strip across recording time
     - aggregated from gaps/coverage/deviation
   - что отвечает: запись локально испорчена или системно плоха вся.

#### Strong but not mandatory in first pass

- `Event support by venue`
  - брать только если есть reference analysis;
  - показывает, какие venue реально влияют на downstream event set.

- `Event loss under venue exclusion`
  - очень сильный decision aid;
  - можно добавить как phase 2 inside Quality, если данные доступны недорого.

- `Spread by time bucket`
  - полезен для execution windows;
  - но сначала важнее общий temporal ribbon + spread distribution.

- `Deviation spikes over time`
  - хорошее доказательство для noisy venues;
  - вторично по отношению к distribution + quadrant.

- `Multi-metric heatmap`
  - хорош как dense summary;
  - но легко дублирует quadrant + table + time heatmap.

#### Remove / overlap / postpone

- `Ticks/s avg`
  - слабый proxy, не screen-level metric.

- `Coverage distribution histogram`
  - уступает ranked venue view.

- `Composite magic score`
  - скрывает reasoning и провоцирует ложную уверенность.

- `generic multi-chart wall`
  - не добавляет ясности и конкурирует с main decision.

- `Buy/sell imbalance sanity`
  - слабая связь с задачей screen.

- `Parameter sensitivity across analyses`
  - это уже compare-analysis tooling, не first-pass Quality.

### 4.0.3 Quality Cleanup Rules

- `Readiness Decision Strip` = единственный owner-level verdict surface.
- Summary показывает только factual context:
  - window
  - duration
  - venue count
  - flags
  - ticks
  - BBO
- Summary и diagnostic panels не должны повторять второй global verdict badge.
- Diagnostic panels используют только operational labels:
  - title
  - chip
  - legend
  - empty/error state
- Explanatory subtitles, commentary notes и helper copy внутри diagnostics запрещены.
- Никакой `selected analysis` строки на экране нет.
- Любой analysis strip below summary запрещён.
- `Related Entities` не дублирует plain `Analysis` identity row.
- Верхний summary/stat pattern должен использовать collector-like `ctrl-kv-*` semantics.
- Expand/collapse blocks must use one canonical `disclosure` pattern across screens and catalog.
- Новые локальные visual classes допустимы только для genuinely new diagnostics:
  - quadrant
  - ribbon
  - matrix
  - file lanes
  - distributions
- Если visible chart уже отвечает на top-level question, raw evidence table уходит в collapsed disclosure.
- `Timeline Gaps` = collapsed evidence block below visible gap diagnostics.
- `BBO Analysis` table = collapsed evidence block below visible BBO distribution.
- `Recording Files`:
  - compact factual summary visible,
  - continuity lanes + files table inside disclosure,
  - no narrative diagnosis prose.

### 4.1 Sidebar State

- Активен row `Recording X`.
- Parent group `Recordings` открыт; analyses могут оставаться раскрыты как child context.
- `Quality` не становится top-level node и не дублируется как отдельный branch.
- На analysis-row допустимы:
  - context links `Quality` / `Explorer`;
  - primary action `Run BT`;
  - optional danger trigger `Delete`.
- На parent recording-row допустим:
  - action `Analyze`;
  - navigation back to `recordings.html?id=<recording_id>`.

### 4.2 Context Bar

```text
● Recording  ·  Apr 25, 2026 · 4.0h · 11 venues                 [toast zone]
```

- label: `Recording`
- meta:
  - date from recording time range;
  - duration from recording span;
  - venue count from `n_venues`
- правая зона:
  - mutation toasts:
    - `Exported report`
    - `Deleted analysis_...`
    - `Showing 3 flagged venues`

### 4.3 Content Sections

#### 4.3.1 Empty / Missing State

- Если `?id=` отсутствует:
  - panel state `Select a Recording from Recordings`
  - CTA `Open Recordings →`
- Если recording id не найден:
  - error panel `Recording not found`
  - CTA back to parent list `Recordings →`

#### 4.3.2 Recording Quality Summary

- Компоненты: `.panel`, collector-style compact KV strip, action rail
- Реальные fields:
  - `recording_id`
  - `t_start_ms`
  - `t_end_ms`
  - `duration_s`
  - derived venue counts: `good`, `warning`, `bad`
- Secondary actions:
  - `Back to Recording`
- Danger: нет. Delete Analysis живёт в `recordings.html`, не здесь.
- Состояния:
  - Normal: summary stats visible
- Explicit cleanup rule:
  - summary may show factual counts only;
  - summary must not restate the same verdict already expressed by the decision strip.

#### 4.3.3 Readiness Decision Strip

- Компоненты: `decision strip` / strong inline banner
- Основан на реальных rules из current HTML:
  - есть `bad` venues → `exclude from strategy before proceeding`
  - bad нет, но есть `warning` → `use with caution`
  - только `good` → `safe to proceed to Explorer`
- Controls:
  - optional `Re-analyze`
- Состояния:
  - No venues: hidden
  - `bad`
  - `warning`
  - `ok`
- Cleanup rule:
  - это единственный owner-level verdict block;
  - downstream diagnostics may show evidence, but must not restate a second global verdict.

#### 4.3.4 Venue Review Table

- Компоненты: `.panel`, `table-scroll`, page-level filters
- Это главный content surface на странице.
- Filters:
  - `Show only bad/warning`
  - `Show all`
- Реальные columns:
  - `venue`
  - `role`
  - `flag`
  - `reasons`
  - `recommendation`
  - `ticks`
  - `ticks/s avg`
  - `bin coverage`
  - `BBO`
  - `BBO coverage`
  - `median price`
  - `leader dev`
  - `reconnects`
  - `downtime`
- Recommendation semantics:
  - bad venue → `Exclude from strategy`
  - no BBO → `Avoid for execution-cost strategies`
  - low coverage → `Use with caution`
  - healthy → `Safe for strategy`
- Состояния:
  - Loading: muted rows / skeleton
  - Normal: all venues
  - Filtered: only `warning` + `bad`
  - No flagged venues under bad-only filter: compact empty `No warning or bad venues`

#### 4.3.5 Supporting Diagnostics

- Компоненты: `diagnostic stack` with one high-value overview row + temporal row + forensic rows
- Rule:
  - графики здесь не "украшения", а разные диагностические lenses;
  - каждый chart обязан отвечать на свой отдельный вопрос;
  - overlapping charts не допускаются.
  - explanatory copy inside panels is forbidden; title + chip + legend + empty state are enough.
- Final diagnostic block set:
  - `Diagnostic Overview Row`
    - `Venue Reliability Quadrant`
      - X = `bin_coverage_pct`
      - Y = `price_deviation_from_leader_bps`
      - bubble size = `downtime_s`
      - color = `flag`
  - `Overall Quality Timeline Ribbon`
    - full-width navigator above all other temporal diagnostics
    - role: navigator / summary layer, not venue-level evidence
    - answers: `when was the recording broadly healthy / degraded / broken?`
    - must aggregate to a fixed max resolution:
      - default target: `24–60` buckets max for full recording
      - if recording is longer, bucket width grows instead of adding unlimited segments
    - time labels must be sparse:
      - show only major ticks such as hourly marks
      - exact interval goes to hover / detail state
    - when user selects a degraded interval here, lower temporal diagnostics should sync to that range
  - `Coverage by Time Bucket`
    - full-width primary temporal detail block
    - venue × time heatmap по `bin_coverage_pct`
    - role: forensic explainer, not top-level navigator
    - answers: `which venues broke, and in which interval?`
    - must not duplicate the overall ribbon:
      - ribbon = aggregate recording state over time
      - heatmap = per-venue breakdown for a selected or current time window
    - scaling rules:
      - do not render unlimited buckets
      - if time range is large, this block should show a selected window rather than the entire recording at full granularity
      - time labels must be sparse major ticks, not every bucket
      - problematic venues sort first; healthy venues may collapse behind `Show all`
      - horizontal scroll is acceptable only as a secondary fallback, not the primary scaling strategy
  - `Temporal Interaction Contract`
    - top ribbon and lower heatmap do related but different jobs.
    - top ribbon:
      - summary navigator across the full recording duration
      - fixed max summary resolution for available width
    - lower heatmap:
      - detailed per-venue explainer for the currently selected time window
      - may use the same bucket set narrowed to the selected range
      - or may use finer bins inside that range if backend supports it
    - selected interval must come from real time boundaries, not from arbitrary visual slot count.
    - implementation must not hardcode a universal rule such as `always show 4 buckets`.
    - any `4-bucket` zoom in prototype is only a mock simplification to demonstrate the interaction, not a product requirement.
    - on real data, lower detail resolution must be adaptive to:
      - recording duration
      - available horizontal width
      - number of venues shown
      - density needed for readable venue comparison
    - when user selects an interval in the top ribbon:
      - lower heatmap must visibly re-render to that selected time window
      - time axis must be recomputed for that window
      - labels must stay readable without collisions
      - out-of-window data must not still occupy full-range grid geometry
    - if backend cannot provide finer detail than the top navigator:
      - lower heatmap may narrow to the same bucket set inside the selected range
      - but the UI must still make drill-down state visually obvious
  - `Temporal Integrity Support Row`
    - `Gap Severity Histogram`
      - duration buckets for timeline gaps
    - `Gap Downtime by Venue`
      - ranked bars
    - `Timeline Gaps Evidence`
      - exact start/end rows in collapsed disclosure
  - `Execution + Consistency Row`
    - `BBO Spread Distribution`
      - per-venue box plots
    - `Leader Deviation Distribution`
      - per-venue box/violin
    - `BBO Evidence`
      - factual per-venue BBO table in collapsed disclosure
- Explicitly reject in first pass:
  - standalone `Ticks/s avg` chart
  - standalone `Bin coverage` bar chart if quadrant + heatmap already exist
  - generic `Coverage heatmap` detached from time dimension
  - duplicated temporal blocks that answer the same question at the same resolution
  - generic chart-wall copied from raw HTML
- Состояния:
  - no gaps: explicit `No timeline gaps`
  - no BBO: explicit `BBO unavailable`
  - normal: compact but information-dense evidence blocks below main table
- Cleanup rules:
  - no helper subtitles like `This chart shows...`
  - no commentary notes under charts
  - collapsed evidence tables are preferred when a visible chart already answers the same top-level question

#### 4.3.6 Recording Files

- Компоненты: `secondary forensic block` for stored files belonging to the selected `Recording`
- Purpose:
  - показать, сколько файлов физически хранит эта запись;
  - показать, нет ли anomalies in storage continuity;
  - объяснить, совпадают ли venue gaps / coverage failures с file-level problems.
- Rule:
  - это не file manager;
  - это diagnostic evidence for recording quality;
  - block lives below main diagnostics, not above the verdict.
  - temporal file continuity is tertiary evidence, not a main timeline peer.
- Keep:
  - `File Integrity Summary`
  - `File Continuity Strip`
  - `Files Table`
- `File Continuity Strip`:
  - should be collapsed or visually secondary by default
  - appears expanded only when anomalies exist or user asks for storage evidence
  - must not compete with `Overall Quality Timeline` or `Coverage by Time Bucket`
  - uses the same time axis semantics, but as storage evidence, not as a primary navigator
- `File Integrity Summary`:
  - total files
  - total size
  - covered time range
  - expected vs actual file count
  - files with anomalies
  - missing intervals count
  - partial / truncated files count
- Do not add:
  - narrative diagnosis labels like `storage healthy` / `storage needs review` if they merely restate anomaly counts
- `File Continuity Strip`:
  - compact timeline of file segments for this recording
  - states:
    - `ok`
    - `gap-before`
    - `gap-after`
    - `overlap`
    - `partial`
    - `suspiciously-small`
- `Files Table`:
  - must stay dense and scan-friendly
  - should not contain long prose explanations inside cells
  - keep columns factual:
    - file
    - shard
    - start
    - end
    - duration
    - size
    - ticks
    - status
    - note
- `Files Table` columns:
  - `file`
  - `venue / shard`
  - `start UTC`
  - `end UTC`
  - `duration`
  - `size`
  - `ticks`
  - `status`
  - `note`
- Explicitly reject:
  - project-wide file browser
  - live file growth monitor
  - delete / rename / download actions
  - storage admin controls
  - duplicated anomaly bullet lists that restate file statuses already visible in continuity strip or files table
  - narrative forensic prose not backed by deterministic rules or backend fields
- States:
  - no file metadata available: `File diagnostics unavailable`
  - files healthy: `No storage anomalies detected`
  - anomalies found: surface count + factual signals

#### 4.3.7 Related Entities

- Секция обязательна и всегда внизу экрана.
- Для selected recording показывать:
  - owner:
    - `Recording` → `recordings.html?id=<recording_id>`
  - downstream references:
    - related backtests if/when available
- Если downstream data ещё нет:
  - `No backtests yet`

### 4.4 Navigation

| Элемент | Destination |
|---|---|
| sidebar recording row | `quality.html?id=X` |
| analysis row `Quality` context link | `quality.html?id=<recording_id>` |
| `Back to Recording` | `recordings.html?id=<recording_id>` |
| `Re-analyze` | `recordings.html?id=<recording_id>&action=analyze` |
| `Open Recordings →` empty CTA | `recordings.html` |

### 4.5 Delta from current HTML

- Сохранить все реальные quality metrics и venue flags, но переставить decision-making выше charts.
- Перестроить top area из flat toolbar + anonymous cards в recording owner summary + action rail.
- Сделать venue table главным рабочим surface вместо набора равноценных chart blocks.
- Пересобрать diagnostics не как "несколько случайных charts", а как curated slice system:
  - reliability,
  - continuity,
  - execution quality,
  - temporal stability,
  - no analysis bridge on Quality.
- Добавить file-level forensic layer:
  - file integrity,
  - continuity between files,
  - correlation between storage anomalies and quality failures.
- Оставить supporting diagnostics ниже и компактнее, чтобы они объясняли flags, а не конкурировали с ними.
- `Delete Analysis` убрать с этого экрана полностью: управление жизненным циклом Analysis принадлежит `recordings.html`.
- Итоговая screen structure сверху вниз:
  - `Context Bar`
  - `Recording Quality Summary`
  - `Readiness Decision Strip`
  - `Reference Analysis Strip`
  - `Venue Filters`
  - `Venue Review Table`
  - `Diagnostic Overview Row`
  - `Temporal Integrity Row`
  - `Execution + Consistency Row`
  - optional `Analysis Bridge Row`
  - `Recording Files`
  - `Timeline Gaps Table`
  - `BBO Analysis Table`
  - `Related Entities`

---
