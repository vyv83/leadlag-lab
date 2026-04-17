# Критика реализации leadlag-lab

Аудит реализации относительно [plan.md](plan.md) и исходных ноутбуков (`collect_full.txt`, `analysis_full.txt`, `visualization_full.txt`).  
**Paper trading исключён из оценки по запросу.**

---

## Общая оценка: 4 / 10

| Компонент | Оценка | Комментарий |
|-----------|--------|-------------|
| Python-пакет (scaffold) | 6/10 | Структура есть, но баги и пропуски в логике |
| Backtest engine | 5/10 | Работает на happy path, но stats неполные, edge cases не обработаны |
| API (FastAPI) | 4/10 | ~20 из ~40 эндпоинтов плана реализованы |
| UI/UX | 2/10 | ~15-20% функциональности плана, нет интерактивности |
| Data contracts | 5/10 | Структура верная, но поля пустые или неполные |
| Deploy | 8/10 | systemd + nginx работают, README хороший |

---

## 1. Критические баги в Python-коде

### 1.1 `session.py` — `build_from_raw()` не заполняет price_windows и bbo_windows

`price_windows` и `bbo_windows` всегда пустые списки `[]`. Plan.md §contract 2 требует массив окон ±500 бинов вокруг каждого события с полями `event_idx`, `bins`, `vwap_leader`, `vwap_follower`, `ema`, `upper`, `lower`. Без этих данных:
- `explorer.html` не может показать график price window
- Backtest engine не имеет контекста для визуализации сделок

**Что делать:** реализовать сбор окон в `build_from_raw()` по аналогии с `analysis_full.txt` (секция построения графиков вокруг событий).

### 1.2 `backtest/engine.py` — `leader_dev_sigma` всегда None

В `_simulate_trade` записывается `leader_dev_sigma = ev.get('leader_dev_sigma')`, но events.json хранит поле как `leader_dev`. Результат — все сделки имеют `leader_dev_sigma: null`.

**Что делать:** `ev.get('leader_dev')` или нормализовать имя поля при создании events.

### 1.3 `analysis/detection.py` — hardcoded "OKX Perp" fallback

`compute_metrics()` использует `"OKX Perp"` как fallback leader для Signal C. Это некорректно — leader может быть Bybit Perp. Нужно брать leader из самого события.

### 1.4 `backtest/engine.py` — position_mode "reverse" теряет сделку

При `position_mode="reverse"` открытая позиция просто удаляется без записи закрывающего трейда. Это искажает equity curve и статистику.

**Что делать:** записать close trade с причиной `exit_reason="reversed"` перед открытием новой позиции.

### 1.5 `collector/writer.py` — crash на неверных типах

Если парсер вернёт строку вместо числа (или наоборот), PyArrow упадёт и весь writer task умрёт. Нет try/except вокруг записи.

### 1.6 `analysis/detection.py` vs `realtime/ema_tracker.py` — разные формулы sigma

Batch: `rolling std` (pandas). Realtime: `exponential weighted variance`. Это даёт разные значения sigma → разные пороги срабатывания → сигналы batch и realtime не совпадут.

**Что делать:** привести к единой формуле (exponential weighted) в обоих путях.

### 1.7 `strategy.py` — mutable default `params = {}`

```python
class Strategy:
    params = {}  # shared across all instances!
```

**Что делать:** `params: dict = field(default_factory=dict)` или инициализировать в `__init__`.

### 1.8 Нет logging нигде в кодовой базе

Ни один модуль не использует `logging`. Отладка в продакшене будет невозможна — только `print()` в stdout systemd journal.

**Что делать:** добавить `logging.getLogger(__name__)` во все модули, настроить формат в `api/__main__.py`.

---

## 2. Неполные data contracts (plan.md §contracts)

### 2.1 stats.json (Contract 5) — отсутствуют ~15 полей

Реализовано в `_build_stats()`:
- ✅ total_trades, win_rate, gross/net_pnl_bps, max_drawdown_bps, sharpe, fee_impact, by_entry_type, by_exit_reason, by_venue, by_spread_bucket

Отсутствуют (требуются планом):
- ❌ `profit_factor`
- ❌ `max_dd_duration_ms`
- ❌ `avg_win_bps`, `avg_loss_bps`
- ❌ `best_trade_bps`, `worst_trade_bps`
- ❌ `avg_hold_ms`
- ❌ `avg_mfe_bps`, `avg_mae_bps`, `mfe_mae_ratio`
- ❌ `trades_per_hour`
- ❌ `max_consecutive_wins`, `max_consecutive_losses`
- ❌ `avg_spread_at_entry_bps`
- ❌ `by_signal` (A/B/C breakdown)
- ❌ `by_direction` (long/short breakdown)
- ❌ `fee_pct_of_gross`, `slippage_pct_of_gross`
- ❌ `n_errors`

### 2.2 quality.json (Contract 2) — минимальная реализация

Сохраняются только `total_ticks`, `total_bbo`, `venues_with_ticks`. План требует ~20 метрик: gap distribution, duplicate rate, timestamp monotonicity, venue coverage %, median tick interval, BBO staleness.

---

## 3. Отсутствующие API эндпоинты

| Эндпоинт | Статус |
|-----------|--------|
| `POST /api/sessions/{id}/analyze` | ❌ не реализован |
| `DELETE /api/sessions/{id}` | ❌ |
| `GET /api/system/processes` | ❌ |
| `GET /api/collector/log` | ❌ |
| `POST /api/backtests/{id}/montecarlo/run` | ❌ |
| `GET /api/backtests/{id}/montecarlo` | ❌ |
| `GET /api/backtests/compare` | ❌ |
| `POST /api/strategies` (create/upload) | ❌ |
| `PUT /api/strategies/{name}` (edit) | ❌ |

Всего реализовано ~22 из ~35-40 требуемых планом эндпоинтов.

---

## 4. UI — главная проблема (2/10)

### 4.1 Полностью отсутствующие страницы

- **montecarlo.html** — план требует полноценный Monte Carlo UI: параметры рандомизации, equity fan chart, confidence bands, distribution гистограммы. Не создан вообще.

### 4.2 dashboard.html

| Фича по плану | Реализовано |
|--------------|-------------|
| CPU sparkline (60 мин) | ✅ |
| Exchange ping таблица | ✅ |
| Количество сессий/стратегий/бектестов | ✅ (частично) |
| Collector status badge | ❌ |
| Paper trader status badge | ❌ |
| Disk usage bar | ❌ |
| Last collection summary | ❌ |
| Quick-action кнопки | ❌ |

### 4.3 explorer.html — сильно урезан

| Фича по плану | Реализовано |
|--------------|-------------|
| Events таблица с фильтрами | ✅ (базово) |
| Price window chart (Plotly) | ✅ (одна линия) |
| BBO spread overlay | ❌ |
| Split-panel (leader + follower) | ❌ |
| Lag markers на графике | ❌ |
| Keyboard navigation (←/→ между событиями) | ❌ |
| Event detail sidebar | ❌ |
| Export CSV/JSON | ❌ |

### 4.4 backtest.html — raw JSON вместо UI

| Фича по плану | Реализовано |
|--------------|-------------|
| Equity curve (gross/net/post_fee layers) | ✅ |
| Trades таблица | ✅ (базово) |
| Stats — structured cards/KPIs | ❌ (raw JSON dump) |
| Drawdown subplot | ❌ |
| PnL distribution histogram | ❌ |
| MFE/MAE scatter plot | ❌ |
| Trade duration distribution | ❌ |
| By-venue/by-signal breakdown charts | ❌ |
| Comparison mode (overlay 2 backtests) | ❌ |

### 4.5 trade.html — key-value dump, нет графиков

План требует:
- ❌ Price window chart (leader + follower + entry/exit markers)
- ❌ BBO snapshot visualization
- ❌ Timeline (entry → hold → exit)
- Есть только key-value пары (✅ но без форматирования)

### 4.6 strategy.html

| Фича по плану | Реализовано |
|--------------|-------------|
| Список стратегий | ✅ |
| Run backtest form | ✅ |
| Просмотр кода стратегии | ❌ |
| Редактор стратегии (in-browser) | ❌ |
| Upload/create стратегия | ❌ |
| Comparison table | ❌ |

### 4.7 quality.html — минимальная

Показывает 4 колонки (venue, ticks, bbo, σ). План требует ~20 колонок + 2 графика (gap distribution, tick rate timeline).

### 4.8 collector.html

| Фича по плану | Реализовано |
|--------------|-------------|
| Start/Stop | ✅ |
| Duration/venues inputs | ✅ |
| Parquet file list | ✅ |
| Live per-venue tick rate | ❌ |
| Live per-venue BBO rate | ❌ |
| Connection status badges | ❌ |
| Log viewer (tail) | ❌ |

### 4.9 Общие UX проблемы (все страницы)

- **Timestamps** показаны как raw milliseconds (`1712844000000`). План требует `HH:MM:SS.mmm UTC`.
- **Нет loading states** — при загрузке данных пустая страница.
- **Нет error states** — при ошибке API ничего не происходит.
- **Нет empty states** — "нет данных" не показывается.
- **Нет сортировки таблиц** — план требует clickable headers.
- **Нет пагинации** — при 1000+ trades/events таблица будет неюзабельной.
- **`displayModeBar: false`** — отключает zoom на всех Plotly графиках, хотя план требует horizontal zoom + range slider.
- **Навигация** неконсистентна — некоторые страницы имеют breadcrumbs, другие нет.
- **Нет responsive design** — на мобильном всё сломается.
- **Нет темы** — тёмная тема есть, но нет toggle и нет адаптации Plotly графиков под тему.

---

## 5. Расхождения с ноутбуками

### 5.1 `analysis_full.txt` → `analysis/`

- Grid search в ноутбуке перебирает `delay × hold × threshold`. В реализации `detection.py` threshold фиксирован (`sigma_threshold` kwarg), grid search в `metrics.py` перебирает только `delay × hold`.
- Bootstrap CI в ноутбуке использует `np.random.choice` с replacement по событиям. Реализация делает то же — ✅ корректно.
- Кластеризация: ноутбук использует 60-bin gap. Реализация — тоже ✅.
- Ноутбук вычисляет `return_std` через `rolling(200).std()`. Реализация — аналогично, но realtime путь использует EWM variance (расхождение, см. §1.6).

### 5.2 `collect_full.txt` → `collector/`

- 17 парсеров портированы корректно ✅.
- Keepalive / backoff логика соответствует ✅.
- Writer rotation 30 мин + zstd — ✅.
- Отсутствует: парсер для **dYdX v4** (есть в ноутбуке, нет в registry). Venue count в registry = 12, но ноутбук подключается к 13+ endpoints.

---

## 6. Что нужно доработать для 10/10

### Приоритет 1 — Критические баги (блокируют корректность)

1. Заполнить `price_windows` и `bbo_windows` в `Session.build_from_raw()`.
2. Исправить `leader_dev_sigma` → `leader_dev` в backtest engine.
3. Убрать hardcoded "OKX Perp" fallback в `compute_metrics()`.
4. Записывать close trade при `position_mode="reverse"`.
5. Унифицировать sigma computation (batch vs realtime).
6. Исправить mutable default `params = {}` в `Strategy`.
7. Добавить try/except в writer task.

### Приоритет 2 — Неполные data contracts

8. Добавить ~15 недостающих полей в `_build_stats()`.
9. Расширить `quality.json` до полного набора метрик.
10. Валидировать все JSON контракты при записи (schema validation).

### Приоритет 3 — Отсутствующие API эндпоинты

11. Реализовать все ~15 недостающих эндпоинтов (см. §3).
12. Добавить `POST /api/sessions/{id}/analyze` для пересчёта сессии.
13. Реализовать Monte Carlo endpoint.

### Приоритет 4 — UI (основной объём работы, ~70% от общего)

14. **montecarlo.html** — создать с нуля: equity fan, confidence bands, distribution histograms.
15. **explorer.html** — добавить BBO overlay, split-panel, lag markers, keyboard nav, export.
16. **backtest.html** — structured stats cards, drawdown subplot, PnL histogram, MFE/MAE scatter, comparison mode.
17. **trade.html** — price window chart с маркерами entry/exit, BBO visualization, timeline.
18. **strategy.html** — code viewer, in-browser editor, upload, comparison table.
19. **quality.html** — расширить до 20 колонок + 2 графика.
20. **collector.html** — live per-venue rates, connection badges, log viewer.
21. **dashboard.html** — collector/paper status badges, disk usage, quick actions.
22. **Все страницы:** human-readable timestamps, loading/error/empty states, сортировка таблиц, пагинация, zoom на графиках, консистентная навигация.

### Приоритет 5 — Инфраструктура

23. Добавить `logging` во все модули.
24. Добавить unit tests (хотя бы для analysis pipeline + backtest engine).
25. Добавить `--log-level` CLI flag.

---

## 7. Ответы на вопросы

### После внесения доработок, план будет реализован на 10/10?

**Да**, если реализовать все пункты из §6 (25 пунктов). Текущий код — работающий scaffold. Архитектура правильная, модульная структура соответствует плану. Баги исправимы. Основной объём недостающей работы — UI (~70% усилий). Backend-ядро (collector, analysis, backtest) нуждается в точечных исправлениях, а не переписывании.

### Пользователь сможет удобно и интуитивно решить задачу?

**Сейчас — нет.** UI в текущем виде — это developer prototype: raw JSON, миллисекунды вместо времени, нет обратной связи при действиях, нет zoom на графиках, нет Monte Carlo.

**После доработок — да**, при условии что:
- Все графики интерактивны (zoom, hover, markers)
- Timestamps человекочитаемы
- Есть loading/error/empty states
- Навигация консистентна
- Monte Carlo страница реализована полностью
- Strategy editor позволяет создавать/редактировать стратегии без CLI
- Quality/Collector страницы дают полную картину состояния данных

Проект потребует примерно столько же усилий на доработку UI/UX, сколько было потрачено на весь текущий scaffold.

---

*Дата аудита: 2026-04-16*
