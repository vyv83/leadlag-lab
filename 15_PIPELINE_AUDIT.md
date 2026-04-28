# LeadLag Lab — Полный аудит пайплайна (doc #15)

> Проверка всех пользовательских потоков: добавление, редактирование, удаление, итерация.  
> Найденные тупики помечены ⚠ ТУПИК. Исправления помечены → FIX.

---

## Полное дерево действий

```
СТАРТ
│
├── [A] ПЕРВЫЙ ЗАПУСК (нет данных)
│   Dashboard открыт, DATA пуст, RESEARCH пуст
│   ⚠ ТУПИК: нет CTA что делать дальше
│   → FIX: dashboard или sidebar показывает "Start here: collect data →"
│
├── [1] СБОР ДАННЫХ
│   │
│   ├── 1.1 Настроить venues
│   │   sidebar → Collector → список venue с enable/disable toggles
│   │   ✓ OK (Phase 1: PATCH /api/venues/{name})
│   │
│   ├── 1.2 Запустить collector
│   │   collector.html → duration, rotation_s → [Start]
│   │   sidebar badge: Collector ● live
│   │   ✓ OK
│   │
│   ├── 1.3 Мониторинг
│   │   collector.html: live logs, per-venue metrics
│   │   dashboard.html: CPU/RAM/network
│   │   ✓ OK
│   │
│   ├── 1.4 Остановить (досрочно или по таймеру)
│   │   collector.html → [Stop]
│   │   ✓ OK
│   │
│   └── 1.5 Recording появляется в sidebar
│       DATA → ▼ Apr 19 · 4h · 11v
│       ⚠ ТУПИК: пользователь не знает что нужно создать Analysis
│       → FIX: при появлении нового recording sidebar показывает подсказку
│              "New recording ready → [+ Analyze]" или пульсирующий badge
│
├── [2] СОЗДАНИЕ ANALYSIS
│   │
│   ├── 2.1 Создать первый Analysis
│   │   sidebar → [+ Analyze] под Recording
│   │   → recordings.html?id=X&action=analyze
│   │   форма: threshold_sigma [1.5], bin_size_ms [50], confirm_window_bins [3]
│   │   → [Run Analysis]
│   │   ✓ OK
│   │
│   ├── 2.2 После создания
│   │   ⚠ ТУПИК: куда попадает пользователь?
│   │   → FIX: auto-navigate → quality.html?id=REC_X
│   │          sidebar refresh → Analysis появляется под Recording
│   │
│   ├── 2.3 Создать ещё один Analysis (другие параметры)
│   │   sidebar → [+ Analyze] на том же Recording снова
│   │   → та же форма с другими params
│   │   → второй Analysis появляется под тем же Recording
│   │   ✓ OK (можно сравнивать сколько events при разных threshold)
│   │
│   └── 2.4 Удалить Analysis
│       sidebar → [×] на Analysis → quality.html?id=REC_X
│       danger strip: "Removes: N backtests + MC. Recording remains."
│       ⚠ EDGE CASE: если идёт анализ (in progress) — блокировать
│       → FIX: API проверяет статус перед удалением
│       [Confirm] → удалён → navigate → recordings.html (или sidebar)
│       ✓ OK после FIX
│
├── [3] ПРОВЕРКА КАЧЕСТВА ДАННЫХ
│   │
│   ├── 3.1 Открыть Quality
│   │   sidebar → [Q] на Analysis → quality.html?id=REC_X
│   │   page title: "Recording · Apr 19 · 4.0h · 11 venues"
│   │   ✓ OK
│   │
│   ├── 3.2 Качество хорошее
│   │   recommendations: все "safe"
│   │   → [→ Explore Events] CTA → explorer.html?analysis=X
│   │   ✓ OK (кнопка нужна, сейчас, возможно, её нет явно)
│   │   → FIX: убедиться что CTA "Explore Events →" присутствует
│   │
│   ├── 3.3 Venue с плохим качеством
│   │   recommendation: "exclude binance — high gap rate"
│   │   ⚠ ТУПИК: как действовать? Нет прямой ссылки
│   │   → FIX: action hint "Disable in Collector →" ведёт на
│   │          collector.html?action=disable&venue=binance
│   │          collector.html читает param → venue уже отмечен к отключению
│   │
│   ├── 3.4 Мало событий (< 20)
│   │   banner "Low sample" уже есть (Phase 1) ✓
│   │   CTA: "Collect more data →" → collector.html
│   │   ⚠ CTA может отсутствовать
│   │   → FIX: добавить ссылку в banner
│   │
│   └── 3.5 Удалить Analysis (плохие данные, не нужен)
│       Delete action в selected Analysis context
│       → danger strip inline → [Confirm] → navigate → recording detail
│       ✓ OK
│
├── [4] ИССЛЕДОВАНИЕ СОБЫТИЙ
│   │
│   ├── 4.1 Открыть Explorer
│   │   sidebar → [E] на Analysis → explorer.html?analysis=X
│   │   page title: "Analysis · Apr 19 · 165 events"
│   │   ✓ OK
│   │
│   ├── 4.2 Фильтрация событий
│   │   signal A/B/C, direction UP/DOWN, magnitude, follower
│   │   keyboard navigation: ← → по events
│   │   ✓ OK
│   │
│   ├── 4.3 Паттерн виден
│   │   decision strip: "Pattern found → formalize in Jupyter"
│   │   sidebar → Jupyter ↗ → JupyterLab
│   │   ✓ OK
│   │
│   ├── 4.4 Паттерна нет (0 событий или слабые)
│   │   decision strip: "No pattern"
│   │   ⚠ ТУПИК: что делать? Нет вариантов действия
│   │   → FIX: decision strip показывает варианты:
│   │          "Try lower threshold → [Re-analyze]"  (ссылка на recordings.html с формой)
│   │          "Collect more data → [Collector]"
│   │
│   └── 4.5 Запустить Backtest прямо из Explorer
│       Run Backtest секция внизу страницы (Phase 1)
│       radio: выбрать стратегию → [▶ Run]
│       → "Running..." → [→ View Backtest] → backtest.html?id=X
│       ✓ OK (если стратегии уже есть)
│       ⚠ EDGE CASE: стратегий ещё нет
│       → FIX: если список стратегий пуст — показать "No strategies yet → Open Jupyter ↗"
│
├── [5] НАПИСАНИЕ СТРАТЕГИИ В JUPYTER
│   │
│   ├── 5.1 Создать новую стратегию
│   │   Jupyter ↗ → JupyterLab
│   │   File Browser → копировать strategy_dev.ipynb → переименовать
│   │   Запустить → get_notebook_name() → STRATEGY_NAME = "my_strategy"
│   │   Написать класс MyStrategy(Strategy)
│   │   Ячейка с %%writefile → запустить → .py создан
│   │   ✓ OK (workflow задокументирован в STRATEGY_DEVELOPMENT.md)
│   │
│   ├── 5.2 Стратегия появляется в sidebar
│   │   sidebar polling 30s → RESEARCH: ▼ my_strategy [nb✓]
│   │   ⚠ ЗАДЕРЖКА: до 30 секунд пользователь не видит стратегию
│   │   → FIX: кнопка [↺ Refresh] в sidebar header (ручной refresh)
│   │
│   ├── 5.3 Итерация (изменить стратегию)
│   │   Jupyter → открыть тот же .ipynb → изменить → %%writefile → запустить
│   │   .py перезаписывается, старые backtests сохраняются (у них свои данные)
│   │   ✓ OK — backtests immutable, не зависят от текущей версии .py
│   │
│   ├── 5.4 Изменить только params (без Jupyter)
│   │   sidebar → стратегия → strategy.html?strategy=X
│   │   detail panel → Params (inline editor) → [Save Params]
│   │   POST /api/strategies/save с обновлённым кодом
│   │   ⚠ НЮАНС: params внутри Python-кода. Inline editor редактирует только
│   │             словарь params = {...}. Остальной код не затрагивается.
│   │   ✓ OK для быстрой подстройки threshold/hold_ms
│   │
│   └── 5.5 Удалить notebook
│       ─── Путь A: из нашего приложения ───
│       strategy.html?strategy=X → [Delete Strategy]
│       danger strip: "Removes: .ipynb + .py + N backtests + MC + paper runs"
│       [Confirm] → всё удалено → navigate → strategy list
│       ✓ OK
│
│       ─── Путь B: удалил в JupyterLab напрямую ───
│       .ipynb удалён в file browser JupyterLab
│       sidebar (после refresh): ▼ my_strategy [nb⚠]
│                                  ! notebook deleted — [Clean up]
│       [Clean up] → strategy.html?strategy=X&confirm_delete=1
│       danger strip: "Notebook deleted externally. Remove strategy + backtests?"
│       [Confirm] → .py + backtests + MC + paper удалены
│       ✓ OK — нет тупика, всегда есть путь к очистке
│
├── [6] BACKTEST
│   │
│   ├── 6.1 Запустить backtest
│   │   ─── Путь A: из Explorer (analysis-centric) ───
│   │   explorer.html?analysis=X → Run Backtest → radio стратегий → [▶ Run]
│   │   ✓ OK
│   │
│   │   ─── Путь B: из Strategy detail (strategy-centric) ───
│   │   strategy.html?strategy=X → Run Backtest → radio analyses → [▶ Run]
│   │   ✓ OK
│   │
│   ├── 6.2 Результаты — хороший PnL, достаточно trades
│   │   backtest.html?id=X
│   │   equity curve, KPIs, trades table
│   │   [Run Monte Carlo →] кнопка ✓ (уже есть в коде: mcLink)
│   │   [Open Analysis in Explorer →] ✓ (уже есть: sessionLink)
│   │   ✓ OK
│   │
│   ├── 6.3 Результаты — 0 trades
│   │   ⚠ ТУПИК: что делать? Нет CTA
│   │   → FIX: banner "0 trades — strategy never triggered.
│   │          Check signal filter in Jupyter → [Jupyter ↗]"
│   │
│   ├── 6.4 Результаты — мало trades (< 20)
│   │   banner "Low sample" уже есть (Phase 1) ✓
│   │   CTA "→ Explorer" уже есть ✓
│   │
│   ├── 6.5 Результаты — fees съедают всё
│   │   trades table показывает fee breakdown
│   │   ⚠ ТУПИК: явного CTA "увеличь hold_ms" нет
│   │   → FIX: Trade Inspector показывает fee/slippage breakdown
│   │          Hint: "High fees — consider increasing hold_ms in params"
│   │          ссылка → strategy.html?strategy=X (params editor)
│   │
│   ├── 6.6 Открыть Trade Inspector
│   │   backtest.html → клик на trade в таблице → trade.html?id=X&bt=Y
│   │   ← → навигация между trades ✓
│   │   [← Back to Backtest] ✓
│   │
│   └── 6.7 Удалить backtest
│       backtest.html → [Delete Backtest]
│       danger strip: "Removes backtest + Monte Carlo results"
│       [Confirm] → navigate → strategy.html?strategy=X
│       sidebar refresh → bt link исчезает
│       ✓ OK
│
├── [7] MONTE CARLO
│   │
│   ├── 7.1 Запустить MC
│   │   backtest.html → [Run Monte Carlo →] → montecarlo.html?bt_id=X
│   │   ✓ OK
│   │
│   ├── 7.2 Результат — robust (p-value < 0.05, хорошая устойчивость)
│   │   ⚠ ТУПИК: нет кнопки "→ Start Paper Trading"
│   │   → FIX: добавить [→ Start Paper Trading] в montecarlo.html
│   │          → paper.html?strategy=X (strategy из bt metadata)
│   │
│   ├── 7.3 Результат — низкая устойчивость
│   │   charts dimmed (Phase 1 ✓)
│   │   ⚠ ТУПИК: что улучшать? Нет CTA к Jupyter
│   │   → FIX: добавить hint "Low confidence — refine entry logic [→ Jupyter ↗]"
│   │          и "Run on more data [→ Recordings]"
│   │
│   ├── 7.4 Перезапустить MC с другими параметрами
│   │   montecarlo.html → [Re-run] → форма n_simulations, method inline → [Run]
│   │   ⚠ ТУПИК: неясно есть ли сейчас такая кнопка
│   │   → FIX: добавить inline re-run форму
│   │
│   └── 7.5 Удалить MC результаты
│       montecarlo.html → [Delete MC Results]
│       danger strip: "Backtest results remain"
│       [Confirm] → navigate → backtest.html?id=X
│       ✓ OK
│
├── [8] PAPER TRADING
│   │
│   ├── 8.1 Запустить paper trading
│   │   ─── Путь A: из Monte Carlo ───
│   │   montecarlo.html → [→ Start Paper] → paper.html?strategy=X
│   │   strategy pre-filled из URL param ✓ (после FIX)
│   │
│   │   ─── Путь B: из Strategy detail ───
│   │   strategy.html?strategy=X → [Start Paper]
│   │   → paper.html?strategy=X
│   │   ✓ OK
│   │
│   ├── 8.2 Мониторинг (live)
│   │   equity, trades, signals, positions, venues
│   │   sidebar badge: ● paper live ✓
│   │   banner "Collector stale" если нет свежих данных ✓ (уже в коде)
│   │   ✓ OK
│   │
│   ├── 8.3 Paper ≈ Backtest (гипотеза подтверждена)
│   │   comparison section в paper.html
│   │   ⚠ ТУПИК: нет явного "confirmed" состояния и нет ссылки на конкретный backtest для сравнения
│   │   → FIX: paper.html показывает "Compare with backtest: [bt_20260419 →]"
│   │          ссылка берётся из strategy metadata (last backtest)
│   │
│   ├── 8.4 Paper ≠ Backtest (execution drift)
│   │   ⚠ ТУПИК: как анализировать расхождение? Нет инструментов
│   │   → FIX: paper.html Trade Inspector для paper trades
│   │          + comparison chart paper equity vs backtest equity
│   │          + hint "Significant drift — check entry timing in Jupyter [→]"
│   │
│   ├── 8.5 Остановить paper trading
│   │   paper.html → [Stop]
│   │   ⚠ EDGE CASE: если пытаешься удалить стратегию пока paper running
│   │   → FIX: DELETE /api/strategies/{name} возвращает 409 если paper running
│   │          danger strip показывает "Stop paper trading first →"
│   │
│   └── 8.6 Удалить paper run
│       paper.html → [Delete] на сессии
│       standalone, нет cascade
│       [Confirm] → navigate → strategy.html?strategy=X
│       ✓ OK
│
└── [9] ИТЕРАЦИЯ (петли назад)
    │
    ├── 9.1 Backtest плохой → улучшить стратегию
    │   backtest.html → [→ Jupyter ↗]
    │   ⚠ ТУПИК: такой кнопки нет сейчас
    │   → FIX: добавить [→ Jupyter ↗] в toolbar backtest.html
    │   Jupyter → открыть тот же .ipynb → изменить логику → %%writefile
    │   → запустить новый backtest
    │   ✓ OK после FIX
    │
    ├── 9.2 Quality плохая → пересобрать данные
    │   quality.html → [Re-analyze] (другие params) → recordings.html с формой
    │   quality.html → "Disable venue →" → collector.html?disable=X
    │   Collector → новый run → новый Recording → новый Analysis
    │   ✓ OK после FIX (ссылка на disable venue)
    │
    ├── 9.3 Explorer: нет паттерна → попробовать другой threshold
    │   explorer.html → decision strip: "Try lower threshold → [Re-analyze]"
    │   → recordings.html?id=X&action=analyze (форма с текущими params pre-filled)
    │   ✓ OK после FIX
    │
    └── 9.4 Monte Carlo: слабый → больше данных
        montecarlo.html → hint → Collector → новый Recording →
        новый Analysis → новый Backtest → новый MC
        ✓ OK — путь существует, просто длинный
```

---

## Сводная таблица тупиков

| # | Где | Тупик | Исправление |
|---|---|---|---|
| T1 | Dashboard (fresh) | Нет CTA что делать | "Start here: Collect data →" на dashboard |
| T2 | Recording появился | Непонятно что делать дальше | Подсказка/badge рядом с новым recording в sidebar |
| T3 | quality.html: bad venue | Нет action "disable venue" | Link "Disable in Collector →" в recommendation |
| T4 | explorer.html: 0 events | Нет вариантов действия | Decision strip: "Try lower threshold →" и "More data →" |
| T5 | explorer.html: нет стратегий | Run Backtest бесполезен | "No strategies — Open Jupyter ↗" вместо пустого radio |
| T6 | sidebar: новая стратегия | Задержка 30 сек | Кнопка [↺ Refresh] в sidebar header |
| T7 | backtest.html: 0 trades | Нет CTA | Banner "0 trades — check logic [→ Jupyter ↗]" |
| T8 | backtest.html: high fees | Нет hint | Trade Inspector hint "increase hold_ms → params editor" |
| T9 | backtest.html | Нет [→ Jupyter] кнопки | Добавить в toolbar |
| T10 | montecarlo.html: robust | Нет [→ Start Paper] | Добавить кнопку → paper.html?strategy=X |
| T11 | montecarlo.html: low confidence | Нет CTA | Hint "Refine strategy [→ Jupyter]" + "More data [→ Recordings]" |
| T12 | montecarlo.html | Нет Re-run с параметрами | Inline re-run форма |
| T13 | paper.html | Нет ссылки на backtest для сравнения | "Compare with: [bt_xxx →]" из strategy metadata |
| T14 | paper.html: drift | Нет инструментов анализа | Paper trade inspector + comparison chart |
| T15 | Delete strategy: paper running | Cascade ломает running paper | API 409 + "Stop paper first →" в danger strip |
| T16 | Analysis создан | Нет auto-navigate | Auto → `quality.html?id=<recording_id>` после создания |

---

## Что работает хорошо (не трогать)

| Что | Почему хорошо |
|---|---|
| backtest.html → [Run Monte Carlo] | Уже есть `mcLink` в коде |
| backtest.html → [Open Analysis in Explorer] | Уже есть `sessionLink` в коде |
| paper.html: "Collector stale" banner | Уже реализован (Phase 1) |
| Backtest: Low sample banner < 20 trades | Уже реализован (Phase 1) |
| trade.html: ← → навигация между trades | Отличная реализация |
| Jupyter ↗ в sidebar | Всегда доступен |
| strategy_dev.ipynb workflow (%%writefile) | Хорошо задокументирован |
| MC: charts dim при low confidence | Уже реализован (Phase 1) |

---

## Приоритизация исправлений

### Включены в Фазу 2 (14_PHASE2_TREE_SIDEBAR.md, шаги 21-25)

Фиксятся попутно при обходе страниц для sidebar refactor — стоимость ~0:

- **T4**: Explorer 0 events → decision strip improvements
- **T5**: нет стратегий в Run Backtest → empty state hint
- **T6**: 30с задержка sidebar → [↺ Refresh] кнопка
- **T7**: 0 trades → banner + [→ Jupyter ↗]
- **T9**: нет [→ Jupyter] в backtest.html → добавить в toolbar
- **T10**: MC good → нет [→ Start Paper] → добавить кнопку
- **T11**: MC low confidence → нет CTA → добавить hint
- **T15**: delete strategy пока paper running → 409 + объяснение
- **T16**: auto-navigate после create analysis → recordings.html JS

### Оставшиеся (сделать попутно когда страница открыта)

- **T1**: dashboard пуст при fresh start → "Start here" CTA
- **T2**: новый recording без подсказки → sidebar badge или hint
- **T3**: bad venue в quality.html → "Disable in Collector →" link
- **T12**: MC re-run без параметров → inline re-run форма
- **T13**: нет ссылки на backtest в paper.html → "Compare with: bt_xxx →"
- **T14**: paper drift анализ → comparison chart + trade inspector
