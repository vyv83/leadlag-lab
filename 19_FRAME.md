# LeadLag Lab — UI Frame (doc #19)

> Статус: decisions locked, основа для wireframes
> Все решения приняты в процессе обсуждения. Этот документ — контракт для всех экранов.

---

## 1. Layout

```
┌─────────────────────────────────────────────────────────────┐
│ SIDEBAR 380px          │ CONTENT                            │
│                        │                                    │
│ [header]               │ [context bar ~28px]                │
│ [sys-bar]              │ ──────────────────────────────────  │
│ [tree-scroll]          │ [sections]                         │
│   независимый скролл   │                                    │
│                        │ [nav context / related entities]   │
└─────────────────────────────────────────────────────────────┘
```

- Sidebar всегда присутствует на всех экранах
- Sidebar скроллится независимо от content
- Content не имеет "main" заголовка или зонального лейбла
- Никаких modal windows

---

## 2. Context Bar

Тонкая полоса (~28px) в самом верху content area. Не sticky — скроллится вместе с контентом.

```
● entity_name  ·  meta1  ·  meta2              [toast message ×]
```

**Левая часть:** dot + entity name (mono) + meta (muted)
- На list view (нет entity в URL): название секции, например `Recordings`
- На detail view: имя конкретной сущности + ключевые мета-данные

**Правая часть:** зона для toast notifications
- Появляется после мутации: `analysis_01 ready · 165 events →`
- Исчезает через 5s или по клику `×`
- Дизайн toasts — отдельная задача

**Нет кнопок действий** — они живут в sidebar action rail.

---

## 3. Navigation Model

### URL params
```
collector.html                    → Collector (все биржи)
collector.html?venue=binance      → Collector (фильтр: binance)
recordings.html                   → список всех Recordings
recordings.html?id=X              → Recording detail (в списке выделена)
quality.html?id=X                 → Recording quality
explorer.html?analysis=X          → Analysis explorer
strategy.html                     → список всех Strategies
strategy.html?strategy=X         → Strategy (в списке выделена + detail panel)
backtest.html?id=X                → Backtest detail
montecarlo.html?bt_id=X           → Monte Carlo detail
paper.html?strategy=X             → Paper Run detail
trade.html?id=X&bt=Y              → Trade inspector
```

### List view (нет entity в URL)
Экраны без entity показывают **полный список**:
- `recordings.html` → список всех recordings
- `strategy.html` → таблица всех strategies

### Sidebar active state
Sidebar подсвечивает активный узел по pathname + URL params.

---

## 4. Progress в Sidebar

Тонкий прогресс-бар появляется **под row** активной сущности пока идёт долгий job. **Без текста, без цифр — только шкала.**

```
▼ analysis_01  ·  165 ev
  [░░░░░░░░░░░░░░░░░░░░░░░░░]   ← тонкая полоска под row
```

Применяется для всех долгих операций:
- Analysis job → под Recording row
- Backtest job → под Strategy row
- MC run → под Backtest row
- Paper start → под Paper Run row
- Collector recording → под активной Recording row (прогресс = elapsed / planned_duration)

После завершения: бар исчезает, в context bar появляется toast.

Параллельно: прогресс-бар есть и в inline form (если пользователь не ушёл). Если ушёл — sidebar бар остаётся.

---

## 5. Related Entities (Nav Context)

Компактная секция внизу каждого content экрана. Показывается **всегда** — видны и родители и дети.

```
CONTEXT
  Recording  rec_20260422  →             ← parent (ссылка)
  Analysis   analysis_01   165 ev  →     ← current (без ссылки)
    Backtests
      bt_001   1.84x  88 trades  →       ← children (ссылки)
      bt_002   1.12x  43 trades  →
```

Правила:
- Только ключевые метрики, без деталей
- Всё что в этой секции — кликабельно и ведёт на соответствующий экран
- Если детей нет — секция показывает "No backtests yet" без CTA (CTA живёт в sidebar)
- На Trade screen: показывает backtest (parent) + соседние trades (навигация ← →)

---

## 6. Domain Model (обновлённый)

**Убраны из дерева:**
- `Collector Run` — не существует как entity
- `Venue` как domain entity — стала navigation filter

**Добавлено в Recording:**
- `start_time`, `planned_duration_s`, `status: recording | ready`
- Duration/time bounds принадлежат Recording, не Collector

**Sidebar дерево:**

```
RUNTIME
  ● Collector  [LIVE / idle]     → collector.html
      binance  [LIVE]            → collector.html?venue=binance
      bybit    [LIVE]            → collector.html?venue=bybit
      okx      [idle]            → collector.html?venue=okx

DATA
  Recordings                     → recordings.html
    ● rec_20260425  [░░░░]       → recordings.html?id=rec_20260425
    ○ rec_20260422  4h · 11v     → recordings.html?id=rec_20260422
      Analyses
        analysis_01  165 ev      → quality.html?id=<recording_id>
          Bins                   → (inline в quality/explorer, нет отдельного экрана)

RESEARCH
  Strategies                     → strategy.html
    momentum_v1  [nb✓]  2 BT    → strategy.html?strategy=momentum_v1
      Notebook                   → Jupyter ↗ (external)
      Backtests
        bt_001  [MC]  1.84x     → backtest.html?id=bt_001
          Monte Carlo Runs
            mc_001  500 runs    → montecarlo.html?bt_id=bt_001
        bt_002  1.12x           → backtest.html?id=bt_002
      Paper Runs
        paper_001  [running]    → paper.html?strategy=momentum_v1

WORKBENCH
  Jupyter ↗                      → external link
```

---

## 7. Collector Screen Structure

Самый богатый экран. Данные реальтайм (polling 5s).

**Если `?venue=X`:** все секции фильтруются по этой бирже.

```
[Control bar]
  Duration · Rotation · [Start] [Stop] [Restart]  +  статус текущей записи

[Recording progress]   ← только если recording активна
  ● rec_20260425  [░░░░░░░░░░░░░░░░░░░░]

[Charts]               ← только если collector running
  [Tick chart 5min]  |  [Candlestick chart 5min]

[Ping chart]
  Одна линия на биржу. Checkboxes для фильтрации видимости.
  Если ?venue=X — остальные скрыты, чекбокс недоступен.

[Connection table]
  venue · role · ticks/s · BBO/s · ping ms · reconnects · uptime% · status

[Files]
  path · size · rows · time range · venues

[Log]
  Фильтр: venue, type. Auto-scroll.
```

**Что нужно добавить в backend:**
- `GET /api/collector/ticks?venue=X&window_s=300` — последние N секунд тиков из parquet для live chart
- Ping history (`.ping_history.jsonl`) — для ping chart timeline

---

## 8. Action Rules (финальные)

- **Delete** — только при selected row, для всех сущностей
- **Кнопки в content** — не дублируем sidebar. Только если без них совсем неудобно
- **Inline forms** — раскрываются под кнопкой, никогда modal
- **Delete confirm** — inline strip, никогда browser confirm или modal
- **Overflow `...`** — не используем в первом прототипе
- **4 кнопки в action rail** — максимум, компактные, без переноса

---

## 9. Pipeline Map (финальный)

```
Dashboard ──────────────────────────────► Collector
Collector ──(запись завершена)──────────► Recordings (sidebar обновляется)
Recordings ──(Analyze → job)────────────► Quality     [auto-navigate]
Quality ───────────────────────────────► Explorer    [CTA]
Quality ──(bad venue)──────────────────► Collector   [hint link ?venue=X]
Explorer ──(pattern → Jupyter)─────────► Jupyter ↗
Explorer ──(no pattern)────────────────► Recordings  [re-analyze link]
Explorer ──(Run BT)────────────────────► Backtest    [navigate after job]
Strategy ──(Run BT)────────────────────► Backtest    [navigate after job]
Strategy ──(Open Notebook)─────────────► Jupyter ↗
Strategy ──(Start Paper)───────────────► Paper
Backtest ──(Run MC)────────────────────► Monte Carlo
Backtest ──(trade click)───────────────► Trade
Backtest ───────────────────────────────► Jupyter ↗
Monte Carlo ──(Start Paper)────────────► Paper
Monte Carlo ──(low confidence)─────────► Jupyter ↗
Monte Carlo ──(more data)──────────────► Recordings
Paper ──(trade click)──────────────────► Trade
Trade ──(← back)───────────────────────► Backtest / Paper
```

---

## 10. Screens List

| # | Экран | URL | List / Detail |
|---|---|---|---|
| 1 | Dashboard | `dashboard.html` | single |
| 2 | Collector | `collector.html[?venue=X]` | single + filter |
| 3 | Recordings | `recordings.html[?id=X]` | list + inline detail |
| 4 | Quality | `quality.html?id=X` | detail |
| 5 | Explorer | `explorer.html?analysis=X` | detail |
| 6 | Strategy | `strategy.html[?strategy=X]` | list + inline detail |
| 7 | Backtest | `backtest.html?id=X` | detail |
| 8 | Monte Carlo | `montecarlo.html?bt_id=X` | detail |
| 9 | Paper | `paper.html?strategy=X` | detail |
| 10 | Trade | `trade.html?id=X&bt=Y` | detail |
