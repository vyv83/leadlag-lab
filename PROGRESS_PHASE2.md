# Phase 2 Tree Sidebar — ЗАВЕРШЕНО

> Все задачи Phase 2 выполнены. Этот файл — финальная документация.

**Репозиторий:** `/root/projects/leadlag-lab/`
**Спецификация:** `14_PHASE2_TREE_SIDEBAR.md`

---

## Статус: ✅ ВСЁ СДЕЛАНО

### Batch 0: Backend Fixes ✅
- 0.1 — Fix missing MC run route decorator (`@app.post("/api/backtests/{bt_id}/montecarlo/run")`)
- 0.2 — Add 409 Conflict guard в `delete_strategy()` когда paper running

### Batch 1: CSS + sidebar.js + Trial ✅
- 1.1 — Sidebar CSS в `style.css` (`.sidebar`, `.app-main`, все `.sb-*`, `.page-title`)
- 1.2 — Создан `sidebar.js` (data loading, rendering, кэш, collapse, active state)
- 1.3 — Trial на `dashboard.html` ✅

### Batch 2: Rollout + Pipeline Fixes ✅
- 2.1 — `sidebar.js` подключён на всех 10 страницах
- 2.2 — Session dropdowns убраны из `explorer.html` и `quality.html`
- 2.3 — Page-title strips на всех 8 страницах с param ✅
- 2.5 — `refreshSidebar()` после мутаций (strategy, backtest, montecarlo)
- T1 — Dashboard CTA "No data yet — Collect Data →" ✅
- T3 — quality.html: bad venue → "Disable in Collector →" link ✅
- T4 — explorer.html: 0 events decision strip ✅
- T5 — explorer.html: no strategies → "Open Jupyter ↗" ✅
- T7 — backtest.html: 0 trades banner ✅
- T9 — backtest.html: Jupyter link в toolbar ✅
- T10 — montecarlo.html: [→ Start Paper] с `?strategy=X` ✅
- T11 — montecarlo.html: low-confidence hints ✅
- T16 — recordings.html: auto-navigate → quality после create analysis ✅

### Batch 3: Cleanup ✅
- 3.1 — header/nav удалены из всех 10 HTML
- 3.2 — `body > header { display: none; }` убран из style.css

---

## Ключевые файлы

| Файл | Что сделано |
|---|---|
| `leadlag/ui/sidebar.js` | Tree sidebar — data, render, cache, toggle, active, `window.refreshSidebar`, `window.insertPageTitle` |
| `leadlag/ui/style.css` | Sidebar CSS + page-title CSS, header убран |
| `leadlag/ui/dashboard.html` | Sidebar ✅, header убран, T1 CTA баннер |
| `leadlag/ui/collector.html` | Sidebar ✅, header убран |
| `leadlag/ui/recordings.html` | Sidebar ✅, header убран, page-title при `?id=X`, T16 auto-navigate |
| `leadlag/ui/explorer.html` | Sidebar ✅, session dropdown убран, page-title, T4+T5 |
| `leadlag/ui/quality.html` | Sidebar ✅, session dropdown убран, page-title, T3 disable link |
| `leadlag/ui/strategy.html` | Sidebar ✅, page-title, auto-select из `?strategy=X`, refreshSidebar |
| `leadlag/ui/backtest.html` | Sidebar ✅, page-title, T7+T9, refreshSidebar |
| `leadlag/ui/montecarlo.html` | Sidebar ✅, page-title, T10+T11, refreshSidebar |
| `leadlag/ui/paper.html` | Sidebar ✅, page-title при `?strategy=X` |
| `leadlag/ui/trade.html` | Sidebar ✅, page-title с ← → навигацией |
| `leadlag/api/app.py` | 0.1 MC route, 0.2 409 guard |

---

## Архитектура sidebar.js

**IIFE**, подключается после `app.js`. Использует хелперы из app.js: `fetchJSON`, `qs`, `el`, `fmt`, `signed`.

**Bootstrap:** создаёт `<aside#sidebar>`, оборачивает `<main>` в `.app-main`.

**Data:** `loadSidebarData(forceFresh)` — 8 параллельных fetch через `Promise.allSettled`:
- `/api/collections`, `/api/sessions`, `/api/strategies`, `/api/backtests`
- `/api/notebooks`, `/api/collector/status`, `/api/paper/status`, `/api/paper/strategies`
- sessionStorage cache, ключ `"sidebar_cache"`, TTL 30s

**Render:** `renderSidebar(data)` → header + static links + DATA section + RESEARCH section + Jupyter footer.

**Public API:**
- `window.refreshSidebar(forceFresh)` — инвалидирует кэш, перечитывает и перерисовывает
- `window.insertPageTitle(nameHtml, metaText, actionsHtml)` — вставляет/заменяет `.page-title` в начало `<main>`

**Связь recordings↔sessions:** `session.id.startsWith(rec.id.split("_").slice(0,3).join("_"))`

**Active highlight:** по `location.pathname` + `qs("session")` + `qs("id")` + `qs("strategy")`

**Delete routing:** `[×]` → navigate на `страница.html?id=X&confirm_delete=1` (danger strip на той странице)

---

## Page Title Strips (2.3) — реализованы

Каждая страница вызывает `window.insertPageTitle(nameHtml, metaText, actionsHtml)` из sidebar.js после загрузки данных:

| Страница | Вызов | Данные |
|---|---|---|
| `quality.html` | `load(id)` → `renderPageTitle()` | `payload.quality`, `payload.meta` |
| `explorer.html` | `loadSession(sid)` → `renderPageTitle(sid)` | `meta` от `/api/sessions/{id}/meta` |
| `backtest.html` | `init()` → `renderPageTitle()` | `meta`, `stats` |
| `montecarlo.html` | `loadBacktest(id)` → `renderPageTitle()` | `meta` |
| `paper.html` | `refresh()` → `renderPageTitle(status)` | `status` от `/api/paper/status` |
| `strategy.html` | `renderDetail(name)` → `renderPageTitle(strat)` | `strat` из allStrategies |
| `recordings.html` | init → `renderPageTitle(urlId)` если `?id=X` | `recordings` array |
| `trade.html` | `load()` → `renderPageTitle()` | `payload.trade`, `payload.meta` |

---

## Pipeline Tупики — итоговая таблица

| # | Где | Исправление | Статус |
|---|---|---|---|
| T1 | Dashboard (fresh) | "No data yet — Collect Data →" баннер | ✅ |
| T2 | Новый recording | sidebar.js покажет его сразу при refresh | ✅ (sidebar решает) |
| T3 | quality.html bad venue | "Disable in Collector →" ссылка в `qualityHint()` | ✅ |
| T4 | explorer 0 events | Decision strip "Try lower threshold → Re-analyze" + "Collect more data" | ✅ |
| T5 | explorer нет стратегий | "No strategies yet — Open Jupyter ↗" | ✅ |
| T6 | sidebar 30s delay | [↺ Refresh] кнопка в sidebar header | ✅ (в sidebar.js) |
| T7 | backtest 0 trades | `#zeroTradesBanner` + Jupyter link | ✅ |
| T9 | backtest нет Jupyter | `<a id="jupyterBtLink">` в toolbar | ✅ |
| T10 | MC → нет [→ Start Paper] | `mcPaperLink.href = paper.html?strategy=X` | ✅ |
| T11 | MC low confidence | `#mcLowConfHints` с двумя кнопками | ✅ |
| T15 | delete strategy пока paper running | 409 + "Stop paper first" | ✅ (Batch 0.2) |
| T16 | create analysis → куда? | auto-navigate `quality.html?session=X` | ✅ |

Оставшиеся тупики (T8, T12, T13, T14) — advanced features, не входили в Phase 2 scope.
