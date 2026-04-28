# LeadLag Lab — Фаза 1: UX & CRUD Fixes (doc #13)

> **Это Фаза 1.** Фаза 2 (tree sidebar) описана в 14_PHASE2_TREE_SIDEBAR.md  
> Статус: проектное решение, ждёт реализации  
> Связанные документы: 10_PROMPT_CONTEXT.md, 09_MANUAL_TEST_REPORT_2026-04-18.md, 14_PHASE2_TREE_SIDEBAR.md

---

## Проблемы которые решаем

| # | Проблема | Severity |
|---|---|---|
| 1 | Терминология: Collection (raw data) vs Session (analysis) — пользователь называет "сессией" то что в коде Collection | Critical |
| 2 | Нет страницы где видно список записей и можно создать новый анализ из них | High |
| 3 | Run Backtest: два дропдауна без контекста внизу страницы — непонятно что к чему | High |
| 4 | Нет удаления Backtest, Paper run — накапливаются без контроля | High |
| 5 | Удаление Стратегии ломает backtests (orphaned data), нет предупреждения | High |
| 6 | Notebook удалить нельзя из UI, нет индикации "notebook missing" для стратегии | Medium |
| 7 | Params стратегии нельзя редактировать в UI без Jupyter | Medium |
| 8 | Venue enable/disable нет в UI (хардкод в config.py) | Medium |
| 9 | "Create Simple Strategy" на strategy.html нарушает Jupyter-first философию | Medium |
| 10 | Нет предупреждения что два Recording < 45 мин сливаются в одно | Low |

---

## Архитектурные решения

### 1. Переименование терминологии (единый публичный контракт)

| Было (в коде / UI) | Стало (в UI) | Почему |
|---|---|---|
| Collection | **Recording** | Это то что collector записал — raw data |
| Session | **Analysis** | Это результат обработки recording — detected events |

Публичный контракт использует `/api/collections`, `/api/analyses`. Старый `/api/sessions` не является частью актуальной системы.

### 2. Модель сущностей и связей

```
Venue (config.py, enabled/disabled)
    │
    └──► Collector (process: start/stop)
              │ пишет rotating raw parquet files (ticks/BBO, каждые rotation_s сек)
              ▼
         Recording (raw files, auto-grouped по временному gap < 45 мин)
              │  analyze() с параметрами (threshold_sigma, bin_size_ms...)
              │  из одного Recording можно создать N Analysis с разными params
              ▼
         Analysis (detected lead-lag events, качество, BBO coverage)
              │
              └────────────────────────────────────────┐
                                                        │ backtest(strategy × analysis)
Notebook (.ipynb, в JupyterLab)                        │
    │ %%writefile                                       │
    ▼                                                   │
Strategy (.py) ─────────────────────────────────────►─┘
    │                                                   │
    │                                           Backtest Run
    │                                               │
    │                                               └──► Monte Carlo
    │
    └──► Paper Trading Run
              │
              └──► Paper Trades

Trade Inspector ◄── открывается из Backtest или Paper
```

### 3. Cascade Delete Rules

```
Delete Recording  → удалит: N analyses + их backtests + MC
Delete Analysis   → удалит: N backtests + MC  (Recording остаётся — можно re-analyze)
Delete Notebook   → удалит: .ipynb + .py (strategy) + N backtests + MC + N paper runs
Delete Strategy   → удалит: .py + N backtests + MC + N paper runs + .ipynb (если есть)
Delete Backtest   → удалит: MC если есть
Delete Paper Run  → standalone, нет cascade
```

**Notebook и Strategy — одинаковый каскад.** Удаление с любой стороны чистит всё.  
Один API endpoint: `DELETE /api/strategies/{name}?include_notebook=true/false`

**Проблема: удаление из JupyterLab напрямую (вне нашего приложения)**

Если пользователь удалил `.ipynb` через файловый браузер JupyterLab — приложение не получает событие.  
Решение: при загрузке sidebar/strategy.html проверять `GET /api/notebooks` vs список стратегий.  
Если `.ipynb` не найден, но `.py` существует → показывать `[nb⚠]` badge + кнопку **"Clean up"**.  
Clean up = удалить `.py` + backtests + paper (тот же каскад, инициируется пользователем вручную).

### 4. UX паттерн: без модальных окон

**Никаких modal windows.** Вместо них:

#### Inline Danger Strip (для delete)
Клик [Delete] → элемент трансформируется inline (не float, не overlay):
```
⚠ Delete "research_multi_signal_v1"?
Removes: 3 backtests · 1 Monte Carlo · 1 paper run
Notebook: [✓ also delete .ipynb]  [keep .ipynb]
[Confirm Delete]  [Cancel]
```
После confirm → элемент fade out + **bottom toast** на 5 сек:
```
Deleted research_multi_signal_v1 (3 backtests removed)  [Undo]
```
Undo реализуется через soft-delete (5 сек window) на бэкенде, либо просто восстановление файлов.

#### Inline Expand (для create / run)
Клик [+ New Analysis] или [Run Backtest] → секция **раскрывается inline** ниже кнопки.  
Клик снова или [Cancel] → сворачивается. Нет оверлея, нет blur.

---

## Изменения по страницам

### NEW: recordings.html

**Новая страница** в навигации между Collector и Explorer.

> ⚠ **Коллизия с Фазой 2:** В Фазе 2 sidebar-дерево берёт на себя список recordings + analyses и делает эту страницу избыточной как "список". Поэтому:
> - **Если Фаза 2 не скоро** — делать полный список (описание ниже)
> - **Если Фаза 2 следует быстро** — делать только как "Recording Detail" страницу (`recordings.html?id=XXX`), без списка. Список будет в sidebar.

Зачем: сейчас нет ни одной страницы где можно:
- увидеть все recordings списком
- создать Analysis из Recording
- удалить Recording или Analysis

Содержимое (полная версия):
- Список Recordings (дата, длительность, n_venues, размер, n_analyses)
- Каждый Recording раскрывается: список его Analyses (id, дата, n_events, threshold_sigma)
- [+ New Analysis] → раскрывается inline форма: threshold_sigma, bin_size_ms, confirm_window_bins → [Run]
- [Delete Recording] → inline danger strip (с предупреждением о cascade)
- На каждом Analysis: [View Quality] [Explore] [Delete Analysis] → inline danger strip
- Предупреждение: "Recordings separated by < 45 min are merged automatically"

### collector.html (minor)

- Добавить toggle enable/disable для каждого venue (нужен PATCH /api/venues/{name})
- Rename "session" → "recording" в лейблах
- Убрать дублирующий список sessions если есть

### quality.html (minor)

- Rename owner framing from "analysis" to "recording"; Quality больше не держит Analysis context
- Не показывать [Delete Analysis] как owner-level action страницы; удаление Analysis живёт вне quality owner surface
- Добавить кнопку [Re-analyze] → ведёт на recordings.html с нужным recording раскрытым

### explorer.html (add Run Backtest inline)

Добавить секцию внизу страницы (после decision strip):

```
─── Run Backtest with this Analysis ───────────────────
Strategy:  ○ research_multi_signal_v1  (last: +115bps, 88 trades)
           ○ baseline_signal_c         (last: +12bps, 31 trades)
           ○ codex_manual_20260418     (no backtests yet)
Override:  [{"hold_ms":30000}                        ]
[▶ Run Backtest]  → после запуска: "Running... [→ View Backtest]"
────────────────────────────────────────────────────────
```

Список стратегий — radio buttons (не dropdown). Если стратегий > 5, добавить фильтр-поиск.

### strategy.html (significant rework)

**Убрать:**
- Секцию "Run Backtest" (две дропдауна внизу страницы) — заменить inline detail
- Секцию "Create Simple Strategy" — нарушает Jupyter-first философию

**Добавить inline detail panel** (обновляется при клике на строку таблицы):

```
────────────────────────────────────────────────────────
research_multi_signal_v1  · v2026-04-19
Notebook: ✓ research_multi_signal_v1.ipynb  [Open ↗]  [Delete notebook]
       ⚠ или: "No notebook — create in Jupyter"

Params (click value to edit inline):
  threshold_sigma: 1.5    hold_ms: 30000    venue: lighter
  entry_type: market      max_spread_bps: 8
  [Save Params]

─── Run Backtest ────────────────────────────────────────
○ 20260419_080345 · 165 events · 4h  ← recommended
○ 20260417_121202 · 22 events · 30min
Override: [                           ]
[▶ Run]

─── Backtests (3) ───────────────────────────────────────
bt_20260419_123521  Apr 19  88 trades  +115bps  SR 0.31  ✓MC  [View] [Delete]
bt_20260418_091234  Apr 18  45 trades  +32bps   SR 0.12       [View] [Delete]

─── Paper Runs (1) ──────────────────────────────────────
paper_...  Apr 19  running  62 trades  [View] [Stop] [Delete]

[Delete Strategy] → inline danger strip
────────────────────────────────────────────────────────
```

### backtest.html (minor)

- Добавить [Delete Backtest] → inline danger strip: "Delete bt_xxx? Monte Carlo results also removed."

### paper.html (minor)

- На каждую paper session: [Delete] → inline danger strip (standalone, нет cascade)

### montecarlo.html (minor)

- Добавить [Delete MC Results] → inline: "Delete Monte Carlo? Backtest results remain."

### dashboard.html (minor)

- Rename "sessions" → "analyses" / "recordings" где уместно

---

## Новые API endpoints

```
GET    /api/notebooks                    # список .ipynb файлов в notebooks/

DELETE /api/strategies/{name}           # РАСШИРИТЬ: добавить query param:
                                        #   ?include_notebook=true  → удалить .ipynb тоже
                                        # Каскад всегда: .py + backtests + MC + paper runs
                                        # include_notebook=true (default) когда удаляем через UI

PATCH  /api/venues/{name}               # {"enabled": bool} — persist в config/venues.json

DELETE /api/backtests/{id}              # удалить папку backtest (+ MC)
DELETE /api/paper/{name}               # удалить paper session директорию

DELETE /api/collections/{id}           # удалить raw parquet files + все связанные analyses
```

`DELETE /api/notebooks/{name}` — отдельный endpoint НЕ нужен.  
Всё через `DELETE /api/strategies/{name}?include_notebook=true`.

`PATCH /api/strategies/{name}/params` — опционально (можно использовать существующий POST /api/strategies/save).

---

## Навигация (обновлённый порядок, Фаза 1)

```
Dashboard | Collector | Recordings | Explorer | Quality | Strategies | Backtests | Monte Carlo | Paper | Jupyter ↗
```

Изменение: добавлен **Recordings** между Collector и Explorer.  
Логика пайплайна: Collect → See Recordings → Check Quality → Explore Events → Strategy → Backtest → MC → Paper.

> В Фазе 2 эта горизонтальная nav заменяется на left sidebar tree — см. 14_PHASE2_TREE_SIDEBAR.md.

---

## Что НЕ меняем

- API endpoint names (Collection/Session в URL остаются)  
- Внутренние имена в Python коде  
- trade.html — отличный экран, не трогать  
- Файловую структуру стратегий  
- JupyterLab workflow (%%writefile остаётся единственным способом создать стратегию)

---

## Почему "Create Simple Strategy" секция удаляется

Философия проекта: стратегия — это Python класс, не форма с полями.  
Секция "Simple Strategy Builder" в strategy.html противоречит этому напрямую.  
Если исследователю нужно создать стратегию — он открывает Jupyter (кнопка в навигации).  
Builder создаёт иллюзию что можно обойтись без кода — вредная иллюзия для quant researcher.

---

## Приоритет реализации

| Приоритет | Задача | Файлы |
|---|---|---|
| P0 | Создать recordings.html (новая страница) | recordings.html + /api/collections DELETE |
| P0 | strategy.html: убрать нижний Run Backtest + Create Builder, добавить detail panel | strategy.html |
| P0 | Переименовать Collection→Recording, Session→Analysis везде в UI labels | все .html |
| P1 | explorer.html: добавить inline Run Backtest секцию | explorer.html |
| P1 | DELETE /api/backtests/{id} + кнопка в backtest.html | app.py + backtest.html |
| P1 | Notebook API (list + delete) + badge в strategy.html | app.py + strategy.html |
| P2 | PATCH /api/venues/{name} + toggle в collector.html | app.py + collector.html |
| P2 | DELETE /api/paper/{name} + кнопка в paper.html | app.py + paper.html |
| P3 | Inline params editor в strategy detail panel | strategy.html |
| P3 | Bottom toast undo после удаления | style.css + app.js |
