# 07 — КРИТИЧЕСКИЙ АУДИТ ПРОЕКТА vs PLAN.MD (v4 FINAL)

Дата: 2026-04-18

---

## ОБЩАЯ ОЦЕНКА

| Компонент | Оценка | Комментарий |
|-----------|--------|-------------|
| **Backend (Python-пакет)** | **7/10** | Ядро работает, контракты в основном соблюдены, но есть пробелы |
| **API (FastAPI)** | **7.5/10** | 90% эндпоинтов готовы, 3-4 отсутствуют, пара несовпадений форматов |
| **Backtest Engine** | **8/10** | Наиболее проработанная часть, все ключевые модели реализованы |
| **Paper Trading + Realtime** | **7/10** | Pipeline работает, IPC есть, но проверки детализации не хватает |
| **Collector** | **8/10** | Стабилен, все 12 бирж, ротация, BBO |
| **Strategy System** | **7/10** | Загрузчик + валидация работают, но notebook-связка сыровата |
| **Dashboard (UI)** | **5/10** | Базовая функциональность есть, 3 из 8 блоков плана отсутствуют |
| **Explorer (UI)** | **8/10** | Лучший экран проекта. Недочёты косметические |
| **Backtest (UI)** | **7/10** | Хороший, но не хватает 15+ stat-карточек и 2 breakdown-секции |
| **Trade Inspector (UI)** | **8/10** | Компактный, информативный. SL/TP линии не рисуются |
| **Monte Carlo (UI)** | **8.5/10** | Почти полный — все 4 графика + стат-карточки |
| **Paper Trading (UI)** | **7/10** | Живой equity + сигналы + позиции. Нет сравнения с бектестом |
| **Quality (UI)** | **7.5/10** | Таблица полная, 4 графика, но нет heatmap и timeline |
| **Strategy List (UI)** | **2/10** | Самый слабый экран. От плана реализовано ~20% |
| **Collector (UI)** | **6.5/10** | Функционален, не хватает цветов, спарклайнов, прогресс-бара |
| **CSS / Design System** | **7/10** | Тёмная тема, единообразие, но графики без явного height |

**ИТОГО: 7/10** — рабочий прототип, но не продукт.

---

## ВИЗУАЛИЗАЦИЯ СООТВЕТСТВИЯ ПАЙПЛАЙНУ

```
ПАЙПЛАЙН ПОЛЬЗОВАТЕЛЯ (plan.md §17)         СТАТУС
═══════════════════════════════════════════════════════════════

1. СБОР ДАННЫХ                              ✅ РАБОТАЕТ
   Dashboard → Start Collector              ⚠️ Нет popup выбора venues
   Коллектор пишет Parquet                  ✅ Все 12 бирж
   Мониторинг: ticks/s, pings               ⚠️ Pings без цветового кода

2. АНАЛИЗ                                    ✅ РАБОТАЕТ
   Dashboard → Run Analysis                 ⚠️ Нет popup выбора сессии
   Sessions с params_hash                   ✅
   Explorer открывает                       ✅

3. ИССЛЕДОВАНИЕ В EXPLORER                   ✅ РАБОТАЕТ (8/10)
   Фильтры signal/direction/magnitude       ✅
   Двойной субплот leader/follower           ✅
   BBO overlay                              ✅
   Таблица followers                        ✅
   Клавиатурная навигация                   ✅
   EMA baseline                             ❌ НЕТ

4. РАЗРАБОТКА В JUPYTER                      ⚠️ ЧАСТИЧНО (6/10)
   load_session, events.filter              ✅
   %%writefile стратегия                    ✅
   load_strategy + валидация                ✅
   run_backtest в ноутбуке                  ✅
   result.plot_equity(layers=True)          ⚠️ 3 слоя вместо 4
   events.grid_search                       ⚠️ Есть, но не документировано
   events[].plot()                          ⚠️ Нужно проверить

5. ДЕТАЛЬНЫЙ ПРОСМОТР В UI                   ⚠️ ЧАСТИЧНО (6/10)
   Strategy List → Run Backtest             ❌ Strategy.html почти пустой
   Backtest equity с слоями                ⚠️ 3 слоя, не 4
   Клик на сделку → trade.html              ✅
   Monte Carlo → p-value                    ✅
   "View Event" → explorer                  ✅

6. ИТЕРАЦИЯ                                  ⚠️ ЧАСТИЧНО (5/10)
   params_override в API                    ✅
   Quick params в UI                        ❌ Нет
   Strategy comparison                      ❌ НЕТ
   Simple mode creator                      ❌ НЕТ

7. PAPER TRADING                             ✅ РАБОТАЕТ (7/10)
   Запуск из UI                             ✅
   Live equity                              ✅
   Сигналы + позиции                        ✅
   Сравнение paper vs backtest              ❌ НЕТ

8. РЕАЛ ТРЕЙДИНГ                             ⏳ ОТЛОЖЕНО (Фаза 6)
```

---

## 1. BACKEND — ПОДРОБНЫЙ АУДИТ

### 1.1 API-эндпоинты: план vs реальность

```
ЭНДПОИНТ                              СТАТУС   ПРИМЕЧАНИЕ
───────────────────────────────────────────────────────────
SYSTEM
GET  /api/system/stats                ✅
GET  /api/system/history              ✅
GET  /api/system/pings                ✅
GET  /api/system/files                ✅
GET  /api/system/processes            ✅

COLLECTOR
GET  /api/collector/status            ✅        + поле proc_alive
POST /api/collector/start             ✅
POST /api/collector/stop              ✅
GET  /api/collector/log               ✅
GET  /api/collector/files             ✅
POST /api/collector/clear-stale       ➕        Вне плана, полезно

SESSIONS
GET  /api/sessions                    ✅
GET  /api/sessions/{id}/meta          ✅
GET  /api/sessions/{id}/events        ✅
GET  /api/sessions/{id}/event/{idx}   ✅
GET  /api/sessions/{id}/quality       ✅
POST /api/sessions/{id}/analyze       ✅
DELETE /api/sessions/{id}             ❌        НЕТ

STRATEGIES
GET  /api/strategies                  ⚠️       Нет version, last_backtest_summary
GET  /api/strategies/{name}           ✅
DELETE /api/strategies/{name}         ✅

BACKTESTS
GET  /api/backtests                   ✅
GET  /api/backtests/{id}/meta         ⚠️       Через generic artifact route
GET  /api/backtests/{id}/trades       ⚠️       Через generic artifact route
GET  /api/backtests/{id}/equity       ⚠️       Через generic artifact route
GET  /api/backtests/{id}/stats        ⚠️       Через generic artifact route
GET  /api/backtests/{id}/trade/{n}    ✅
POST /api/backtests/run               ✅        + params_override
GET  /api/backtests/{id}/montecarlo   ❌        НЕТ (POST для запуска есть)
POST /api/backtests/{id}/montecarlo/run ✅

PAPER
GET  /api/paper/status                ✅        + extra fields (can_trade, blocked)
POST /api/paper/start                 ✅
POST /api/paper/stop                  ✅
GET  /api/paper/trades                ✅
GET  /api/paper/equity                ✅
GET  /api/paper/signals               ✅
GET  /api/paper/positions             ✅
GET  /api/paper/stats                 ✅
GET  /api/paper/venues                ✅
```

**Отсутствующие эндпоинты:**
- `DELETE /api/sessions/{id}` — нельзя удалить сессию из UI
- `GET /api/backtests/{id}/montecarlo` — результаты MC нельзя получить через API (только через файловую систему)
- Отдельные routes для meta/trades/equity/stats заменены generic `/{artifact}` — функционально работает, но не соответствует контракту

**Несоответствия форматов:**
- `GET /api/strategies` не возвращает `version` и `last_backtest_summary` — стратегия в UI не показывает дату версии и последний бектест

### 1.2 Backtest Engine — детальные пробелы

**Что работает:**
- ✅ Position modes: reject / stack / reverse
- ✅ Slippage models: none / fixed / half_spread / full_spread + BBO fallback
- ✅ Fees: taker для market, maker для limit
- ✅ Limit fill model: 30% window, binary fill
- ✅ SL/TP priority over hold_ms
- ✅ MFE/MAE tracking
- ✅ Equity curve: gross, post_fee, net, drawdown
- ✅ Stats: by_signal, by_venue, by_direction, by_spread_bucket

**Что не хватает:**

| Функция | План | Реальность |
|---------|------|------------|
| Equity 4 слоя (Gross → -Fees → -Slippage → Net) | 4 линии | 3 линии (нет post_fee→net шага с slippage отдельно) |
| `post_fee_equity_bps` поле | В equity.json | Есть ✅ |
| Stats: consecutive wins/losses | В stats.json | ❌ Нет |
| Stats: MFE/MAE Ratio | В stats.json | ❌ Нет |
| Stats: trades_per_hour | В stats.json | ❌ Нет |
| Stats: max_dd_duration_ms | В stats.json | ❌ Нет |
| Stats: avg_win_bps / avg_loss_bps | В stats.json | ❌ Нет |
| Stats: best/worst trade | В stats.json | ❌ Нет |
| Stats: fee_pct_of_gross / slippage_pct_of_gross | В stats.json | ❌ Нет |
| Stats: by_entry_type (market/limit) | В stats.json | ❌ Нет |
| Stats: by_exit_reason (hold/sl/tp) | В stats.json | ❌ Нет |
| Entry-to-MFE time | В trades | ❌ Нет |

### 1.3 Стратегия — пробелы в данных

`GET /api/strategies` возвращает: `{name, path, valid, error, class_name, description, params}`

**Отсутствует:**
- `version` — дата версии стратегии
- `last_backtest_summary` — вся колонка последнего бектеста
- `venues` — какие биржи торгует
- `signal_type` — какие сигналы (A/B/C)
- `entry_type` — market/limit
- `slippage_model`
- `position_mode`
- `has_backtest / has_paper / has_live` — статусные флаги

Без этих данных strategy.html не может показать полноценную таблицу.

### 1.4 Notebook API — пробелы

План описывает богатый API для ноутбука. Проверка:

| Метод | Статус |
|-------|--------|
| `load_session(id)` | ✅ |
| `session.events.filter(...)` | ✅ |
| `events.filter(signal='C').stats('Lighter Perp')` | ⚠️ Частично |
| `events.grid_search(...)` | ✅ |
| `events[0].plot()` | ❌ Нужно проверить |
| `events.plot_equity(...)` | ❌ Нужно проверить |
| `run_backtest(strat, session)` | ✅ |
| `result.summary()` | ✅ |
| `result.plot_equity(layers=True)` | ⚠️ 3 слоя не 4 |
| `result.plot_trade(n)` | ⚠️ Нужно проверить |
| `run_monte_carlo(result)` | ⚠️ Нужно проверить |
| `result.save()` | ✅ |

---

## 2. UI/UX — ПОЭКРАННЫЙ АУДИТ

### 2.1 Dashboard (dashboard.html) — 5/10

**Отсутствует полностью:**
- ❌ **Платформенный uptime** — нигде не показывается
- ❌ **Блок "Последняя сессия анализа"** — нет событий A/B/C, нет кнопки "Open in Explorer"
- ❌ **Блок "Paper Trader"** — только статус в картах, нет equity, trades, last signal
- ❌ **Quick Actions popup** — Start Collection без выбора venues/duration

**Частично:**
- ⚠️ **UTC время** — показывается, но не тикает динамически (нужен setInterval)
- ⚠️ **System Health sparklines** — есть, но не интегрированы в строку с метрикой (отдельные графики ниже)
- ⚠️ **Pings** — нет цветового кода (🟢<30ms 🟡30-60ms 🔴>60ms)
- ⚠️ **Collector Status** — нет прогресс-бара, нет median price, нет status icons
- ⚠️ **Processes** — нет total data/ usage
- ⚠️ **Active Files** — нет "Show all files" (expand/collapse)

**Удобство:**
- Карточки глобального статуса слишком мелкие — `minmax(150px, 1fr)` для 7 карточек на 1400px = ~200px каждая. Достаточно.
- Навигация работает. Кнопки есть.
- Нет визуальной группировки блоков — всё идёт сплошным потоком секций.

### 2.2 Collector (collector.html) — 6.5/10

**Отсутствует:**
- ❌ **Цветовой код статуса venue** — только текст "ok"/"reconnecting"/"dead", без 🟢🟡🔴
- ❌ **Sparkline ticks/s** — нет мини-графика в ячейке таблицы
- ❌ **Прогресс-бар длительности** — нет визуального прогресса
- ❌ **Кнопка Restart** — только Start/Stop
- ❌ **Median price** — нет колонки для проверки адекватности

**Частично:**
- ⚠️ **WS URLs** — показываются по умолчанию, план говорит "серым, мелко"
- ⚠️ **Venue selection** — чекбоксы есть, но нет кнопок "Select All Leaders/Followers"

**Удобство:**
- Лог-бокс 420px — хорошо, но нет авто-скролла по умолчанию (только toggle)
- Таблица venues при 12 строках не влезает — нужен scroll

### 2.3 Explorer (explorer.html) — 8/10

**Лучший экран проекта.** Основная функциональность реализована.

**Отсутствует:**
- ❌ **EMA baseline** — серая линия EMA на графике (toggle)
- ❌ **Magnitude range slider** — input field вместо slider с min-max
- ❌ **SL/TP горизонтальные пунктирные линии** в trade mode — код поддерживает, но не рендерит

**Косметика:**
- ⚠️ Signal badge: текст "A"/"B"/"C" вместо цветных бейджей
- ⚠️ Direction: текст "UP"/"DOWN" вместо зелёных/красных стрелок ↑↓
- ⚠️ Followers table: "yes"/"no" вместо ✓/✗ с цветами
- ⚠️ BBO available: "yes"/"N/A" вместо ✓/—

**Удобство:**
- Сетка `42% / 1fr` — хороший баланс. Список событий слева, график справа.
- `max-height: 780px` для event panel — правильно, скроллится.
- Клавиатурная навигация ✅
- BBO overlay toggle ✅
- Click на follower row переключает график ✅
- "Show all followers" overlay ✅

**Размеры графиков:** `height: 420px` по умолчанию. Для двойного субплота это впритык — leader subplot получается ~200px, follower ~200px. Для детального просмотра хочется 550-620px. Нет явного ресайза.

### 2.4 Strategy List (strategy.html) — 2/10 ❌ КРИТИЧЕСКОЕ ОТСТАВАНИЕ

**Самый проблемный экран. От плана реализовано ~20%.**

**Текущее состояние:**
Таблица с 5 колонками: name, class, valid, description, params + секция "Run Backtest" с выбором стратегии и сессии.

**Отсутствует ПОЛНОСТЬЮ:**

1. **10 из 15 колонок таблицы:**
   - Version (дата)
   - Venues
   - Signal type (A/B/C)
   - Entry type
   - Slippage model
   - Position mode
   - Last backtest date
   - Last backtest metrics (PnL, hit rate, Sharpe, etc.)
   - Equity sparkline
   - Status (has_backtest / has_paper / has_live)

2. **Сравнение стратегий:**
   - Чекбоксы выбора 2-5 стратегий
   - Кнопка "Compare Selected"
   - Таблица сравнения метрик
   - Equity curves на одном графике
   - Timeline overlap сделок

3. **Simple Mode Creator:**
   - Форма с dropdowns/checkboxes/inputs для создания простой стратегии
   - Leader mode, Signal, Threshold, Followers, Delay, Hold
   - Entry type, Slippage model, Spread filter
   - SL/TP, Position mode
   - Кнопка Save → .py file

4. **Кнопки на строку:**
   - Run Backtest
   - View Backtest
   - Run Paper
   - Delete

**Влияние на пайплайн:** Пользователь НЕ МОЖЕТ из UI:
- Сравнить две стратегии
- Создать простую стратегию без ноутбука
- Быстро запустить бектест/пейпер для конкретной стратегии
- Понять какая стратегия лучше без ручного просмотра

### 2.5 Backtest (backtest.html) — 7/10

**Хороший экран, но не хватает деталлизации.**

**Equity Curve:**
- ✅ 3 слоя (Gross, Post-Fee, Net) — переключатель работает
- ❌ **4-й слой** (Gross-Fees-Slippage как промежуточный) — отсутствует
- ❌ **Размер точек** — фиксированный `size: 7`, план требует пропорционально magnitude
- ✅ Клик на точку → trade.html
- ✅ Drawdown subplot

**Stats Cards — 12 из ~30+:**
- ✅ Total Net, Trades, Win Rate, PF, Sharpe, Max DD, Avg Trade, Fees, Slippage, Avg Spread, Avg MFE, Avg MAE
- ❌ **Total Net USD**
- ❌ **Max DD Duration**
- ❌ **Avg Win / Avg Loss**
- ❌ **Best / Worst Trade**
- ❌ **Avg Hold Time**
- ❌ **MFE/MAE Ratio**
- ❌ **Trades per Hour**
- ❌ **Consecutive Wins/Losses**
- ❌ **Fee % of Gross**
- ❌ **Slippage % of Gross**

**Trades Table — 22 из ~23 колонок:**
- ✅ Почти все колонки на месте
- ❌ **Entry-to-MFE time (ms)** — отсутствует

**Breakdowns:**
- ✅ Fee & Slippage Impact — есть, но без %
- ✅ By Spread Bucket — есть
- ✅ By Signal — есть
- ✅ By Venue — есть, но без sharpe и equity per venue
- ❌ **By Entry Type** (market/limit) — отсутствует
- ❌ **By Exit Reason** (hold_expired/stop_loss/take_profit) — отсутствует

**Distributions:**
- ✅ Все 5 мини-графиков: PnL, hold times, magnitude scatter, time scatter, spread scatter

**Удобство:**
- Фильтры по signal/venue/PnL/exit — работают
- Цветовые строки (profit/loss) — работают
- Summary row внизу — есть
- Размеры distribution charts: `minmax(360px, 1fr)` grid — хорошо, но нет явного height (Plotly auto)

### 2.6 Trade Inspector (trade.html) — 8/10

**Хорошо:**
- ✅ Dual subplot (leader + follower)
- ✅ Entry/exit vertical lines + annotations
- ✅ Green/red fill between entry/exit
- ✅ MFE/MAE markers
- ✅ BBO subplot toggle
- ✅ All followers overlay toggle
- ✅ Metrics sidebar (30+ полей)
- ✅ Navigation: Prev/Next, View in Explorer, Back to Backtest

**Отсутствует:**
- ❌ **SL/TP горизонтальные пунктирные линии** — если заданы в сделке
- ❌ **Confirmer lag annotation** для Signal C ("confirmer lag = Xms")

**Удобство:**
- Сетка `1fr / 330px` — график широкий, sidebar компактный. Хорошо.
- Sidebar: `kv` grid 200px/1fr — читабельно.
- Кнопки навигации очевидны.

### 2.7 Monte Carlo (montecarlo.html) — 8.5/10

**Лучший по полноте экран.**

- ✅ Выбор метода (4 варианта)
- ✅ Настройки (simulations, block size, seed)
- ✅ Equity fan chart (1000 кривых)
- ✅ 3 гистограммы: PnL, Sharpe, Max DD
- ✅ Stat cards: p-value, percentile, median, 5th/95th, prob of profit
- ✅ Method help text
- ✅ Confidence warnings

**Мелочь:**
- ⚠️ Нет аннотации на equity fan: реальная линия должна быть зелёная/красная, percentiles — жёлтые dashed. Нужно проверить визуально.

### 2.8 Paper Trading (paper.html) — 7/10

**Есть:**
- ✅ Start/Stop/Restart
- ✅ Status cards
- ✅ Live equity chart
- ✅ Recent signals table
- ✅ Open positions
- ✅ Closed trades
- ✅ Stats

**Отсутствует:**
- ❌ **Сравнение paper vs backtest** — нет overlay equity, нет drift analysis, нет таблицы метрик side-by-side
- ❌ **Venue connectivity table** — нет таблицы со статусом подключений к биржам
- ❌ **Equity by day** bar chart
- ❌ **Статистика за весь период** (days active, best/worst day, trades per day)

### 2.9 Quality (quality.html) — 7.5/10

**Есть:**
- ✅ Venue summary table (20+ колонок)
- ✅ 4 bar charts (coverage, ticks/s, spread, deviation)
- ✅ Timeline gaps
- ✅ BBO analysis
- ✅ Color coding (green/yellow/red flags)
- ✅ Filter: show only bad/warning

**Отсутствует:**
- ❌ **Timeline визуализация** — нет графика "горизонтальные полосы" (зелёный=данные, красный=gap)
- ❌ **Ticks/s over time** — нет графика по времени
- ❌ **Bin coverage heatmap** — нет тепловой карты (X=время, Y=venues, цвет=coverage)
- ❌ **Price consistency check** — нет графика отклонения от медианы по времени

---

## 3. CSS / DESIGN SYSTEM — 7/10

**Положительное:**
- Тёмная тема `#0e1117` — последовательно
- Навигация единообразна на всех экранах
- `style.css` — один файл, 89 строк, без фреймворка — соответствует плану
- Profit/loss цвета: `#3fb950` (зелёный), `#f85149` (красный)
- Metric cards: единообразные, `min-height: 74px`

**Проблемы:**

1. **Графики без явного height в Plotly:**
   - `plotLayout` не задаёт `height`. Plotly использует default ~450px
   - Для equity curve с drawdown subplot — мало. Нужно ~550px
   - Для Explorer dual subplot — тоже впритык
   - **Решение:** Добавить `height: 520` в plotLayout или задать per-chart

2. **Font-size 13px для таблиц** — мелковат для десктопа. 14px лучше для чтения.

3. **Нет визуальной иерархии:**
   - h2 (15px) и h3 (13px) слишком близки к font-size body (14px)
   - Metric-label (12px) vs metric-value (18px) — хорошо, но между секциями нет отступов > 32px

4. **Нет scroll-shadow:**
   - `.event-panel` с `max-height: 780px` и `overflow: auto` — нет визуального индикатора что можно скроллить

5. **Кнопки:**
   - Серые, без акцента. Primary action (Start, Run) не выделены
   - Нет confirmation dialogs на деструктивные действия (Stop, Delete)

6. **Таблицы:**
   - Нет sticky headers — при скролле заголовки теряются
   - Нет alternating row colors — только hover
   - Нет column resize

---

## 4. КРИТИЧЕСКИЕ БЛОКИРОВЩИКИ ПАЙПЛАЙНА

### B1. Strategy.html — почти пустой (2/10)

**Проблема:** Пользователь не может управлять стратегиями из UI. Это разрывает цикл:
```
Исследовать → НАПИСАТЬ СТРАТЕГИЮ → [СРАЗУ ТЕСТИРОВАТЬ ИЗ UI] ← НЕ РАБОТАЕТ
```

Приходится: запустить бектест → вернуться в strategy.html → увидеть только список имён → пойти в backtest.html искать результат.

**Что нужно:**
1. Полная таблица с колонками из плана
2. Кнопки Run Backtest / View Backtest / Run Paper / Delete на каждой строке
3. Strategy comparison
4. Simple mode creator

### B2. Dashboard — нет блоков Paper и Last Session

**Проблема:** Пользователь не видит состояние paper trading и последней сессии анализа на главной странице. Приходится переключаться между вкладками.

### B3. Backtest stats — 18 отсутствующих метрик

**Проблема:** Без consecutive wins/losses, avg win/loss, best/worst, fee%, slippage% — нельзя оценить устойчивость стратегии. Это критично для принятия решения "запускать paper или нет".

### B4. Нет popup для Start Collection

**Проблема:** При нажатии "Start Collection" нет диалога выбора venues и duration. Перекидывает на collector.html, но без преднастройки.

---

## 5. ЧТО МЕШАЕТ РАБОТЕ — UX-ТРИГГЕРЫ

### UX-1. Нет цветового кода в ping-таблице
Таблица показывает ms, но не визуализирует. <30ms должно быть зелёным, 30-60 жёлтым, >60 красным. Сейчас — просто числа.

### UX-2. Signal badges — текст вместо цветов
В Explorer: "A" "B" "C" — просто текст. Планировались цветные бейджи (A=синий, B=оранжевый, C=зелёный). Это ускоряет восприятие в 3-5 раз при просмотре 500 событий.

### UX-3. Followers table — "yes"/"no" вместо ✓/✗
"In signal: yes", "Hit: yes", "BBO: yes" — много текста. Заменить на ✓ (зелёный), ✗ (красный), — (серый).

### UX-4. Нет sort в таблицах
Ни в одной таблице нет сортировки по клику на заголовок. Для trades table (50-200 строк) это критично.

### UX-5. Нет sticky headers
При скролле trades table или quality table заголовки уходят за экран.

### UX-6. Нет loading states
Переход между экранами — белый flash. Нет спиннера при загрузке trades/equity.

### UX-7. Graph hover неполный
В equity chart hover показывает только equity value, но не trade details (signal, venue, PnL). Нужно rich tooltip.

### UX-8. Нет keyboard shortcuts
Plan описывает ↑↓ для Explorer — есть. Но нет hotkeys для других экранов:
- Backtest: ←→ для prev/next trade
- Trade: ←→ prev/next trade (уже есть кнопки, но не hotkeys)
- Dashboard: 1-9 для навигации между экранами

---

## 6. ОШИБКИ И БАГИ

### BUG-1. Equity Curve — 3 слоя вместо 4
Plan требует Gross → Gross-Fees → Gross-Fees-Slippage → Net (4 линии). Реализация: Gross, Post-Fee, Net (3 линии). Пользователь не видит отдельно вклад slippage.

### BUG-2. Point size не пропорционален magnitude
`marker: { size: 7 }` — фиксированный. Должен быть `size: 3 + magnitude * 2` или подобное.

### BUG-3. `GET /api/strategies` — неполный ответ
Нет `version`, `last_backtest_summary`, статусных флагов. strategy.html не может отрендерить полную таблицу даже если бы хотела.

### BUG-4. Trade mode в Explorer — SL/TP линии не рисуются
Код поддерживает SL/TP, но в рендере графика нет `shapes` для горизонтальных пунктирных линий stop_loss/take_profit.

### BUG-5. Monte Carlo GET endpoint отсутствует
`GET /api/backtests/{id}/montecarlo` не реализован. POST для запуска есть, но результат можно получить только через файловую систему.

### BUG-6. Explorer — EMA baseline не реализована
В фильтрах нет toggle "Show EMA baseline", в chart нет серой линии EMA.

---

## 7. РАЗМЕРЫ И РАСКЛАДКА — ЧТО НЕ ТАК

### Layout проблемы:

1. **Dashboard**: Всё идёт одним потоком секций. Нет визуальной группировки. "System Health" → "Processes" → "Pings" → "Collector" — сливается.

2. **Backtest**: Stats cards (12 шт) в `auto-fit, minmax(150px, 1fr)` — на 1400px это ~9 карточек в ряд, 3 во втором. Выглядит как мозаика без логики. Лучше сгруппировать: PnL блок | Risk блок | Execution блок.

3. **Explorer event panel**: `minmax(360px, 42%)` — на 1400px = ~590px для списка. Это много. 360px достаточно. Больше места графику.

4. **Trade sidebar**: `330px` фиксировано. На широком экране — нормально. На <1200px — тесно. Но media query переключает на `1fr`.

5. **Charts**: Нет явного height. Plotly default ~450px. Для equity с drawdown subplot нужно 550-600px. Для Explorer dual subplot — тоже.

---

## 8. ПРИОРИТЕТЫ ИСПРАВЛЕНИЙ

### P0 — Блокирует пайплайн (1-2 дня)
1. **strategy.html** — полная таблица + кнопки Run/View/Delete (минимум, comparison и creator позже)
2. **BUG-3** — `/api/strategies` enrichment (version, last_backtest_summary, status flags)
3. **BUG-1** — Equity 4-й слой (slippage breakdown)

### P1 — Критично для принятия решений (2-3 дня)
4. **Backtest stats** — добавить 18 недостающих метрик в engine + UI
5. **By Entry Type / By Exit Reason** — breakdowns в backtest.html
6. **UX-2/3** — Signal badges, follower indicators (✓/✗)
7. **Dashboard** — блоки Paper Trader + Last Analysis Session

### P2 — Удобство работы (3-5 дней)
8. **UX-1** — Ping color coding
9. **UX-4** — Table sorting
10. **UX-5** — Sticky headers
11. **Chart heights** — явные размеры
12. **BUG-2** — Point size proportional to magnitude
13. **BUG-4** — SL/TP lines in Explorer trade mode
14. **BUG-5** — GET montecarlo endpoint
15. **Paper vs Backtest comparison** в paper.html

### P3 — Косметика и polish (3-5 дней)
16. **Strategy comparison** (выбор 2-5, таблица, equity overlay)
17. **Simple mode creator** (форма генерации .py)
18. **Quality timeline/heatmap** визуализации
19. **Loading states** на всех экранах
20. **EMA baseline toggle** в Explorer
21. **Start Collection popup** с venue selection
22. **Keyboard shortcuts** для навигации
