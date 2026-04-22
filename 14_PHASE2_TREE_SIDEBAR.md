# LeadLag Lab — Фаза 2: Tree Sidebar (doc #14)

> **Предусловие:** Фаза 1 (doc #13) должна быть завершена — все API endpoints, терминология Recording/Analysis, delete endpoints.  
> Связанные документы: 13_ARCHITECTURE_DECISIONS.md, 10_PROMPT_CONTEXT.md

---

## Суть изменения

Заменить горизонтальное меню на **persistent left sidebar** с деревом всех сущностей.

**Было:**
```
[Dashboard] [Collector] [Recordings] [Explorer] [Quality] [Strategies] [Backtests] [MC] [Paper] [Jupyter ↗]
── content ────────────────────────────────────────────────────────────────────────────────────────────────
```

**Стало:**
```
┌─────────────────┬──────────────────────────────────────────────────────────┐
│ leadlag         │                                                          │
│─────────────────│  <content area — текущие страницы без изменений>        │
│ ○ Dashboard     │                                                          │
│ ○ Collector ●   │                                                          │
│                 │                                                          │
│ DATA ─────────  │                                                          │
│ ▼ Apr 19 · 4h  │                                                          │
│   ▼ Analysis    │                                                          │
│     165e [Q][E] │                                                          │
│     → bt rv1 +115bps                                                       │
│   [+ Analyze]   │                                                          │
│ ▼ Apr 17 · 30m │                                                          │
│   ▼ Analysis    │                                                          │
│     22e  [Q][E] │                                                          │
│   [+ Analyze]   │                                                          │
│                 │                                                          │
│ RESEARCH ─────  │                                                          │
│ ▼ research_v1   │                                                          │
│   [nb ✓]        │                                                          │
│   → bt +115bps  │                                                          │
│   ● paper live  │                                                          │
│ ▼ baseline_c    │                                                          │
│   → bt +12bps   │                                                          │
│                 │                                                          │
│ → Jupyter ↗     │                                                          │
└─────────────────┴──────────────────────────────────────────────────────────┘
```

---

## Почему tree sidebar

| Проблема | Top nav (Ф1) | Tree sidebar (Ф2) |
|---|---|---|
| Видно что вообще есть | ✗ нет | ✓ всё в дереве |
| Пайплайн очевиден | частично (порядок пунктов) | ✓ структура дерева = пайплайн |
| CRUD доступен без навигации | ✗ надо зайти на страницу | ✓ delete прямо из дерева |
| M:N связь Strategy↔Analysis | скрыта | ✓ backtest виден под обоими |
| Orphaned entities (нет notebook) | ✗ не видно | ✓ badge ⚠ в дереве |
| Статус collector/paper | только на их страницах | ✓ live badge в sidebar |

---

## Модель дерева

### Проблема M:N: Backtest = Strategy × Analysis

Backtest — это результат пересечения. Он должен быть виден с двух сторон:

```
DATA секция:                     RESEARCH секция:
  Recording Apr 19                 Strategy research_v1
    Analysis 165e                    → bt Apr19 +115bps   ← тот же объект
      → bt research_v1 +115bps  ←   Paper: running
      → bt baseline_c +12bps        
```

Оба `→ bt` — это `<a href="backtest.html?id=bt_xxx">` — ссылки на ОДИН и тот же backtest.
Визуально: строки с `→` — это навигационные ссылки, не отдельные сущности.
Delete backtest — только из content area (не из sidebar), чтобы не путать откуда удаляется.

### Два раздела sidebar

**DATA** — с чего начинается исследование: данные  
**RESEARCH** — стратегии и их результаты

---

## Структура дерева (полная)

```
leadlag  [↺]                         ← logo → dashboard.html; [↺] = ручной refresh

○ Dashboard
○ Collector  [● live]               ← badge если collector.running
○ Paper      [● live]               ← всегда видна; badge если paper.running

━━━ DATA ━━━━━━━━━━━━━━━━━━━━━━━━━━━  ← кликабельный заголовок → recordings.html (список)
▼ Apr 19 · 4.0h · 11v              ← Recording: дата · длительность · n_venues
  ▼ Analysis · 165e  [Q][E]  [×]   ← [Q]=quality, [E]=explore, [×]=delete
      → bt research_v1  +115bps    ← Backtest link: strategy · net_pnl
      → bt baseline_c   +12bps
  ▼ Analysis · 98e   [Q][E]  [×]
      → bt research_v1  +44bps
  [+ Analyze]  [×]                  ← [+ Analyze]=новый analysis, [×]=delete Recording
▼ Apr 17 · 0.5h · 8v
  ▼ Analysis · 22e   [Q][E]  [×]
  [+ Analyze]  [×]
─── empty state ───
  (нет recordings) "No data yet — Start Collector →"

━━━ RESEARCH ━━━━━━━━━━━━━━━━━━━━━━  ← кликабельный заголовок → strategy.html (сравнение)
▼ research_multi_signal_v1 [nb✓]   ← Strategy · notebook badge
    → bt Apr19·Ana1  +115bps       ← Backtest link: recording_date · net_pnl
    → bt Apr19·Ana2  +44bps
    ● paper  running               ← Paper run badge (кликабельно → paper.html?strategy=X)
  [×]                               ← delete Strategy
▼ baseline_signal_c  [nb✓]
    → bt Apr19·Ana1  +12bps
  [×]
▼ codex_manual_20260418  [nb⚠]    ← notebook не найден
    ! notebook deleted — [Clean up]
  [×]
─── empty state ───
  (нет стратегий) "No strategies — Open Jupyter ↗"

→ Jupyter ↗                        ← внешняя ссылка
```

### Что исчезает из навигации (больше нет как standalone пунктов)

| Пункт | Почему убираем | Как теперь добраться |
|---|---|---|
| Explorer | всегда нужен контекст (какой Analysis?) | [E] кнопка на Analysis в дереве |
| Quality | всегда нужен контекст | [Q] кнопка на Analysis в дереве |
| Recordings | → DATA заголовок | клик на "DATA ━━━" → recordings.html |
| Strategies | → RESEARCH заголовок | клик на "RESEARCH ━━━" → strategy.html |
| Backtests | всегда конкретный bt_id | → bt ссылки в дереве |
| Monte Carlo | всегда от конкретного backtest | [→ Run Monte Carlo] в backtest.html |

### Badge правила

| Badge | Цвет | Условие |
|---|---|---|
| `● live` (collector) | green | `collector_status.running == true` |
| `● live` (paper) | green | `paper_status.running == true` |
| `[nb✓]` | green | `.ipynb` файл найден в `/api/notebooks` |
| `[nb⚠]` | yellow | `.py` есть, `.ipynb` не найден |
| `✓MC` | dim | у backtest есть montecarlo результат |
| `+Xbps` | green/red | net_pnl > 0 / < 0 |

### Notebook [nb⚠] — Clean up flow

```
▼ codex_manual  [nb⚠]
    ! notebook deleted — [Clean up]
```
`[Clean up]` → `strategy.html?strategy=codex_manual&confirm_delete=1`  
Страница показывает danger strip: "Notebook deleted externally. Remove strategy + backtests?"

---

## Навигация: context-aware pages

### Правило

> Страница открытая **без param** → режим списка/сравнения (таблица всех).  
> Страница открытая **с param** (из sidebar) → только detail этой сущности.

```js
// В каждой странице:
const entityParam = qs('strategy') || qs('session') || qs('id');
if (entityParam) {
  showDetailMode(entityParam);   // скрыть таблицу, показать detail
} else {
  showListMode();                // показать comparison/list таблицу
}
```

### По страницам

| Страница | Без param (заголовок секции) | С param (клик на entity) |
|---|---|---|
| **strategy.html** | таблица сравнения всех стратегий + Compare | detail одной стратегии |
| **backtest.html** | таблица всех backtests | detail одного backtest |
| **paper.html** | список всех paper sessions | detail+monitor одного |
| **recordings.html** | список всех recordings | Recording Detail + create analysis |
| **quality.html** | — (всегда с param) | quality одного Analysis |
| **explorer.html** | — (всегда с param) | события одного Analysis |
| **montecarlo.html** | — (всегда с param) | MC одного backtest |
| **trade.html** | — (всегда с param) | detail одного trade |

---

## Page title strip (все страницы с param)

Сейчас страницы не показывают что именно открыто. С sidebar это критично — нужен чёткий заголовок в content area.

### CSS

```css
/* ── Page Title Strip ── */
.page-title {
  padding: 6px 14px;
  border-bottom: 1px solid #21262d;
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 11px;
  flex-shrink: 0;
}
.page-title-name { color: #e6edf3; font-weight: 500; }
.page-title-meta { color: #8b949e; }
.page-title-actions { margin-left: auto; display: flex; gap: 5px; }
```

### Содержимое по страницам

```
quality.html?analysis=X
  "Analysis · Apr 19, 2026 · 165 events · 4.0h"   [Delete Analysis] [→ Explore Events]

explorer.html?analysis=X
  "Analysis · Apr 19, 2026 · 165 events"           [Delete Analysis]

backtest.html?id=X
  "research_v1 × Apr 19 · 88 trades · +115 bps"   [Delete] [→ Jupyter ↗]

montecarlo.html?bt_id=X
  "Monte Carlo · research_v1 × Apr 19"             [Delete MC]

paper.html?strategy=X
  "Paper · research_v1 · ● running"                [Stop] [Delete]

strategy.html?strategy=X
  "research_v1 · v2026-04-19"                      [Delete Strategy]

recordings.html?id=X
  "Recording · Apr 19, 2026 · 4.0h · 11 venues"   [Delete Recording]

trade.html?id=X
  "Trade #42 · research_v1 · Apr 19"               (nav: ← prev  next →)
```

---

## Что убирается с каждой страницы (дубли с sidebar)

| Страница | Убирается | Почему |
|---|---|---|
| **explorer.html** | `<select id="session">` dropdown | sidebar навигирует в контексте |
| **quality.html** | session-picker если был | то же |
| **strategy.html** | нижняя секция "Run Backtest" с двумя дропдаунами | заменяется detail panel (Фаза 1) |
| **strategy.html** | секция "Create Simple Strategy" | Jupyter-first философия (Фаза 1) |
| **backtest.html** | `<section id="list">` когда открыт с `?id=` | list mode остаётся для no-param |
| **paper.html** | strategy picker при старте если открыт с `?strategy=` | pre-filled из URL |
| **montecarlo.html** | нет пикеров, без изменений | — |

### Что НЕ убираем (похоже на дубль, но не является)

| Элемент | Почему оставляем |
|---|---|
| Radio стратегий в explorer.html "Run Backtest" | Это действие (combine analysis+strategy), не навигация |
| Radio analyses в strategy.html "Run Backtest" | То же самое |
| [→ Run Monte Carlo] в backtest.html | Workflow action, следующий шаг пайплайна |
| [→ Start Paper] в montecarlo.html | То же |
| [→ Jupyter ↗] везде где нужен | Всегда уместен как escape hatch |

---

## Критичные тупики из Pipeline Audit (файл 15) — фиксятся в Фазе 2

При обходе всех страниц для sidebar refactor — добавляем попутно. Стоимость ~0.

| Тупик | Страница | Исправление |
|---|---|---|
| **T4**: 0 events в Explorer | explorer.html | decision strip: "Try lower threshold → [Re-analyze]" + "Need more data → [Collector]" |
| **T7**: 0 trades в Backtest | backtest.html | banner: "0 trades — strategy never triggered. Check signal filter [→ Jupyter ↗]" |
| **T9**: нет [→ Jupyter] в Backtest | backtest.html | добавить в toolbar |
| **T10**: нет [→ Start Paper] в MC | montecarlo.html | добавить кнопку → paper.html?strategy=X |
| **T11**: нет hint в MC low confidence | montecarlo.html | "Refine strategy [→ Jupyter ↗]" + "Run on more data [→ Recordings]" |
| **T15**: delete strategy, paper running | app.py + danger strip | API 409 Conflict + "Stop paper trading first →" |
| **T16**: нет auto-navigate после create analysis | recordings.html JS | после успешного POST → navigate quality.html?analysis=X |
| **T5**: нет стратегий в Run Backtest | explorer.html | "No strategies yet — Open Jupyter ↗" вместо пустого radio |
| **T6**: 30с задержка новой стратегии | sidebar.js | [↺ Refresh] кнопка в sidebar header |

---

## Техническая архитектура

### 1. CSS Layout (изменения в style.css)

Текущий layout: `body` = block, `header` sticky top, `main` padding.

Новый layout: `body` = flex row.

```css
/* ── App Layout ── */
body { display: flex; height: 100vh; overflow: hidden; }

aside.sidebar {
  width: 200px;
  flex-shrink: 0;
  overflow-y: auto;
  background: #0d1117;
  border-right: 1px solid #21262d;
  display: flex;
  flex-direction: column;
  font-size: 11px;
}

.app-main {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

/* main остаётся как есть — padding: 10px 14px */

/* ── Sidebar: Header ── */
.sb-header {
  padding: 8px 10px;
  font-size: 13px;
  font-weight: 600;
  color: #e6edf3;
  border-bottom: 1px solid #21262d;
  flex-shrink: 0;
}
.sb-header a { color: inherit; text-decoration: none; }

/* ── Sidebar: Section labels ── */
.sb-section {
  padding: 10px 10px 2px;
  font-size: 9px;
  color: #484f58;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

/* ── Sidebar: Tree items ── */
.sb-item {
  display: flex;
  align-items: center;
  padding: 2px 10px;
  gap: 3px;
  cursor: pointer;
  color: #8b949e;
  white-space: nowrap;
  overflow: hidden;
  position: relative;
  border-radius: 0;
}
.sb-item:hover { background: #161b22; color: #c9d1d9; }
.sb-item.active { color: #f0f6fc; background: #1f6feb22; border-left: 2px solid #1f6feb; }
.sb-item a { color: inherit; text-decoration: none; flex: 1; overflow: hidden; text-overflow: ellipsis; }
.sb-item a:hover { text-decoration: none; }

.sb-i0 { padding-left: 10px; }
.sb-i1 { padding-left: 18px; }
.sb-i2 { padding-left: 28px; }
.sb-i3 { padding-left: 38px; }

/* Toggle arrow */
.sb-toggle { font-size: 9px; color: #484f58; flex-shrink: 0; }
.sb-toggle.open { color: #8b949e; }

/* Delete button — visible on hover */
.sb-del {
  display: none;
  margin-left: auto;
  flex-shrink: 0;
  color: #6e7681;
  font-size: 10px;
  padding: 0 2px;
  cursor: pointer;
  border-radius: 2px;
}
.sb-item:hover .sb-del { display: inline; }
.sb-del:hover { color: #f85149; background: #2d1a1a; }

/* Action links (+Analyze, →Jupyter) */
.sb-action {
  padding: 1px 10px;
  font-size: 10px;
  color: #3fb950;
  cursor: pointer;
}
.sb-action:hover { color: #56d364; }
.sb-action.muted { color: #484f58; }

/* Badges */
.sb-badge { font-size: 9px; flex-shrink: 0; }
.sb-badge.green  { color: #3fb950; }
.sb-badge.yellow { color: #d29922; }
.sb-badge.red    { color: #f85149; }
.sb-badge.dim    { color: #484f58; }

/* Backtest link rows */
.sb-bt { color: #6e7681; font-size: 10px; }
.sb-bt.pos { color: #3fb950; }
.sb-bt.neg { color: #f85149; }
```

### 2. sidebar.js (новый файл)

Архитектура: один файл, included в каждой странице после `app.js`.

```
sidebar.js
  ├── loadSidebarData()     — параллельный fetch всех API, кэш 30s
  ├── renderSidebar()       — строит дерево в <aside#sidebar>
  ├── renderRecordings()    — DATA секция
  ├── renderStrategies()    — RESEARCH секция
  ├── handleDelete()        — клик на [×] → navigate to entity page с ?confirm_delete=1
  └── refreshSidebar()      — экспортируемая функция, вызывается после мутаций
```

**Кэш:** `sessionStorage` с TTL 30 сек. После любой мутации (create/delete) вызов `refreshSidebar()` инвалидирует кэш и перерисовывает.

**Параллельные fetches:**
```js
const [collections, sessions, strategies, backtests, papers, notebooks, collStatus, paperStatus] =
  await Promise.allSettled([
    fetchJSON('/api/collections'),
    fetchJSON('/api/analyses'),
    fetchJSON('/api/strategies'),
    fetchJSON('/api/backtests'),
    fetchJSON('/api/paper/strategies'),
    fetchJSON('/api/notebooks'),          // новый endpoint из Фазы 1
    fetchJSON('/api/collector/status'),
    fetchJSON('/api/paper/status'),
  ]);
```

Все `allSettled` — если один endpoint упал, остальное рендерится.

**Delete flow из sidebar (без модалок):**

```js
function handleDelete(type, id) {
  // Не удаляем из sidebar — навигируем в content area с флагом
  const routes = {
    recording:  `recordings.html?id=${id}&confirm_delete=1`,
    analysis:   `quality.html?analysis=${id}&confirm_delete=1`,
    strategy:   `strategy.html?strategy=${id}&confirm_delete=1`,
  };
  location.href = routes[type];
  // Страница читает ?confirm_delete=1 и сразу показывает danger strip
}
```

Почему не удалять прямо из sidebar: sidebar узкий (200px) — нет места для cascade warning. Danger strip должен быть в content area где видно "удалит 3 backtests + MC".

### 3. Изменения HTML-страниц

**Каждая страница:** убрать `<header>/<nav>`, добавить `<aside>` + `.app-main`.

**Было:**
```html
<body>
<header><h1>leadlag</h1><nav>...</nav></header>
<main>...</main>
<script src="app.js"></script>
</body>
```

**Стало:**
```html
<body>
<aside class="sidebar" id="sidebar"></aside>
<div class="app-main">
  <main>...</main>
</div>
<script src="app.js"></script>
<script src="sidebar.js"></script>
</body>
```

Изменение механическое. 9 страниц × ~5 строк изменений = ~45 строк правок.

### 4. Активный элемент в дереве

Каждая страница определяет свой "active path" через `data-sidebar-active` attr или через имя файла:

```js
// sidebar.js читает текущую страницу
const page = location.pathname.split('/').pop();  // 'backtest.html'
const sid  = qs('session') || qs('id') || qs('strategy');
// подсвечивает нужный .sb-item
```

Для backtest: подсвечивается и `→ bt` под Recording/Analysis, и `→ bt` под Strategy (оба — ссылки на тот же backtest).

### 5. Refresh после мутаций

Каждая страница вызывает `refreshSidebar()` после create/delete:

```js
// В backtest.html после успешного запуска:
await postJSON('/api/backtests/run', {...});
refreshSidebar();  // sidebar перечитывает API и обновляется

// В strategy.html после удаления стратегии:
await fetch(api('/api/strategies/' + name), {method:'DELETE'});
refreshSidebar();
location.href = 'strategy.html';
```

---

## Что упрощается в Фазе 2

| Страница | Что упрощается |
|---|---|
| **recordings.html** | Убирается список recordings (теперь в sidebar). Остаётся как "Recording Detail" — детали + create analysis inline |
| **quality.html** | Убирается analysis-picker dropdown (sidebar навигирует сразу на `quality.html?analysis=X`) |
| **explorer.html** | Убирается session-picker dropdown (аналогично) |
| **strategy.html** | Убирается strategy-picker dropdown если был. Sidebar подсвечивает активную стратегию |
| **backtest.html** | Убирается backtest-picker если был |
| **montecarlo.html** | Без изменений — всегда открывается через конкретный bt_id |

---

## API Endpoints (все из Фазы 1 — обязательны перед Фазой 2)

```
GET    /api/notebooks                 # нужен для badge [nb✓]/[nb⚠] в sidebar
DELETE /api/notebooks/{name}          # delete из sidebar → content area confirm
DELETE /api/backtests/{id}            # delete из sidebar → content area confirm
DELETE /api/paper/{name}              # delete из paper.html
DELETE /api/collections/{id}          # delete recording → cascade
PATCH  /api/venues/{name}             # enable/disable venue (collector.html)
```

Sidebar читает `/api/collections`, `/api/analyses`, `/api/strategies`, `/api/backtests`, `/api/paper/strategies` — все уже существуют.

---

## Что НЕ меняем в Фазе 2

- Бэкенд логика (app.py) — только новые endpoints из Фазы 1
- Контент страниц — только layout (убрать header/nav, добавить sidebar)
- URL структура — все ссылки остаются
- app.js — только добавить `refreshSidebar()` вызовы в мутирующих функциях
- trade.html — не трогать, отличный экран

---

## Порядок реализации

| Шаг | Задача | Оценка |
|---|---|---|
| **CSS** | | |
| 1 | style.css: `.sidebar`, `.app-main`, все `.sb-*` классы | 2ч |
| 2 | style.css: `.page-title`, `.page-title-name`, `.page-title-meta`, `.page-title-actions` | 0.5ч |
| **sidebar.js** | | |
| 3 | `loadSidebarData()` — parallel fetches + sessionStorage cache 30s | 1ч |
| 4 | `renderSidebar()` — DATA секция: recordings → analyses → bt links | 3ч |
| 5 | `renderSidebar()` — RESEARCH секция: strategies → bt links → paper badge | 2ч |
| 6 | Badges: collector live, paper live, nb✓/nb⚠, bt +/- color | 1ч |
| 7 | Empty states: "No data → Collector", "No strategies → Jupyter" | 0.5ч |
| 8 | Кликабельные заголовки: DATA → recordings.html, RESEARCH → strategy.html | 0.5ч |
| 9 | `handleDelete()` → navigate с `?confirm_delete=1` | 1ч |
| 10 | `refreshSidebar()` — инвалидация кэша + перерисовка | 0.5ч |
| 11 | [↺ Refresh] кнопка в sidebar header (T6) | 0.5ч |
| **HTML страницы** | | |
| 12 | Все 9 страниц: убрать `<header>/<nav>`, добавить `<aside>` + `.app-main` | 2ч |
| 13 | Все страницы с param: добавить `.page-title` strip с нужным контентом | 2ч |
| 14 | Context-aware mode: страницы с `?param` скрывают list секцию | 1ч |
| 15 | explorer.html: убрать session-picker dropdown | 0.5ч |
| 16 | quality.html: убрать session-picker (если был) | 0.5ч |
| 17 | paper.html: pre-fill strategy из `?strategy=X` param | 0.5ч |
| 18 | recordings.html: упростить до Recording Detail (list переходит в sidebar) | 1ч |
| **Мутации + refresh** | | |
| 19 | Все мутирующие функции: добавить `refreshSidebar()` вызов | 1ч |
| 20 | Все страницы: читать `?confirm_delete=1` → показывать danger strip | 3ч |
| **Тупики из файла 15** | | |
| 21 | backtest.html: banner "0 trades" + [→ Jupyter ↗] в toolbar (T7, T9) | 0.5ч |
| 22 | montecarlo.html: [→ Start Paper] + low-confidence hints (T10, T11) | 0.5ч |
| 23 | explorer.html: decision strip improvements + empty state (T4, T5) | 1ч |
| 24 | recordings.html: auto-navigate → quality после create analysis (T16) | 0.5ч |
| 25 | app.py: 409 Conflict при delete strategy пока paper running (T15) | 1ч |
| — | **Итого** | **~28ч ≈ 3-4 дня** |

---

## Риски

| Риск | Вероятность | Митигация |
|---|---|---|
| 8 параллельных API вызовов = медленная загрузка sidebar | Medium | sessionStorage cache 30s; allSettled не блокирует при ошибке |
| Много recordings → длинный sidebar | Low | Показывать max 10 recordings, остальные под "Show more" |
| [×] случайно нажат | Low | Delete ведёт на страницу с danger strip, не удаляет сразу |
| Active highlight сбивается | Low | Читаем и pathname и ?session/id params |
