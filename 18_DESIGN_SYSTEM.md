# LeadLag Lab — Design System (doc #18)

> Источник: `menu-sprint/codex-dark.html`
> Статус: canonical reference для всех экранов
> Этот документ читается в начале каждого чата перед реализацией HTML-экрана
> Visual companion: [23_MENU_CONTROLS_CATALOG.html](23_MENU_CONTROLS_CATALOG.html)

---

## 1. Токены

### 1.1. Цвета

```css
--bg:             #171a1d;   /* фон всего приложения */
--sidebar:        #1d2126;   /* фон sidebar */
--surface-hover:  #252a30;   /* hover по row */
--surface-active: #2b3138;   /* selected row */
--border:         #39414b;   /* основная граница */
--border-dim:     #2b323a;   /* тихая граница (subtree, разделители) */
--text:           #ece2d1;   /* основной текст */
--text-muted:     #9d9181;   /* вторичный текст, group-labels, meta */
--text-dim:       #c5b8a4;   /* промежуточный — chip, ghost buttons */
--green:          #79c7a1;   /* live, running, ok, nb✓ */
--amber:          #d2a25f;   /* idle, nb⚠, warn */
--red:            #cf7b6c;   /* low-sample, danger, error */
--blue:           #7ab7c6;   /* neutral info (Dashboard, Ticks, BBO) */
--purple:         #a88bbe;   /* MC badge */
--accent:         #86c3ba;   /* selected border, primary buttons, logo */
--panel:          #252a30;   /* поверхность панелей */
--panel-alt:      #21262b;   /* чуть темнее panel (chip bg, header btn bg) */
--line:           #4a5561;   /* hover border у header-btn */
```

### 1.2. Типографика

```css
--mono: 'JetBrains Mono', monospace;

/* Шкала */
9px   — badge text, chip text, meta secondary
10px  — meta, header-btn, rail-btn, group label, sys-bar
11px  — brand-title, label.mono, content placeholder
12px  — label (основной), html/body base
```

Правила:
- Весь интерфейс — монопространственный шрифт
- `letter-spacing: 0.04em` — uppercase labels, brand, buttons
- `letter-spacing: 0.08em` — brand-sub, content placeholder
- `letter-spacing: 0.1em` — group label
- `-webkit-font-smoothing: antialiased` — обязательно

### 1.3. Радиусы и отступы

```css
border-radius: 3px   /* badge, chip, rail-btn, dc-btn */
border-radius: 4px   /* header-btn */
border-radius: 5px   /* brand-logo */
border-radius: 50%   /* dot, sys-dot */

/* Sidebar row padding */
padding: 4px 10px 4px 12px

/* Action rail padding */
padding: 4px 12px 5px 26px

/* Delete confirm padding */
padding: 5px 12px 5px 26px

/* Header padding */
padding: 10px 12px 9px
```

### 1.4. Sidebar

```css
--sidebar-w: 320px;
```

---

## 2. Layout

### 2.1. Базовая структура

```
.app                     display: flex; height: 100vh
├── .sidebar             width: 320px; flex-shrink: 0
│   ├── .header          brand + refresh button
│   ├── .sys-bar         system status dots
│   └── .tree-scroll     flex: 1; overflow-y: auto
└── .main (или <main>)   flex: 1; содержимое экрана
```

### 2.2. Main zone

Main — это всё что правее sidebar. Внутри каждого экрана своя структура, но общий паттерн:

```
.main
├── .page-title          заголовок страницы (entity name + meta + actions)
└── .page-body           основной контент (panels, tables, charts)
```

---

## 3. Sidebar компоненты

### 3.1. Header

```html
<div class="header">
  <div class="brand">
    <div class="brand-logo"></div>
    <div class="brand-text">
      <div class="brand-title">LeadLag Lab</div>
      <div class="brand-sub">Terminal</div>
    </div>
  </div>
  <button class="header-btn">⟳ Refresh</button>
</div>
```

### 3.2. Sys-bar

```html
<div class="sys-bar">
  <div class="sys-item">
    <div class="sys-dot green"></div>
    <span>LIVE</span>
  </div>
  <div class="sys-item">
    <div class="sys-dot green"></div>
    <span>2.4k ev/s</span>
  </div>
  <div class="sys-item" style="margin-left: auto;">
    <span>04:12:33</span>
  </div>
</div>
```

Sys-dot states:
- `.sys-dot.green` — с `box-shadow: 0 0 4px rgba(121,199,161,0.45)`
- `.sys-dot.amber`
- `.sys-dot.red`

### 3.3. Tree Row

Трёхколоночная grid:

```css
.row {
  display: grid;
  grid-template-columns: 12px minmax(0, 1fr) auto;
  align-items: center;
  gap: 5px;
  padding: 4px 10px 4px 12px;
  border-left: 2px solid transparent;
}
```

Колонки:
1. `.twisty` — chevron expand/collapse (12×12px)
2. `.row-main` — dot + label + meta
3. `.row-right` — badge + chip

```html
<div class="row">
  <button class="twisty"><!-- svg chevron --></button>
  <div class="row-main">
    <div class="row-line">
      <span class="dot green"></span>
      <span class="label mono">entity_name</span>
    </div>
    <div class="meta">secondary info</div>
  </div>
  <div class="row-right">
    <span class="badge live">LIVE</span>
    <span class="chip">4h</span>
  </div>
</div>
```

### 3.4. Label варианты

```css
.label          /* font-size: 12px; font-weight: 500 */
.label.mono     /* font-size: 11px; font-family: mono */
.label.group    /* font-size: 10px; font-weight: 600; text-transform: uppercase;
                   letter-spacing: 0.1em; color: var(--text-muted) */
```

Правило:
- `entity` типы (recording, analysis, strategy, backtest, ...) → `.label.mono`
- group-заголовки (Recordings, Analyses, Backtests, ...) → `.label.group`
- top-level фиксированные (Dashboard, Collector, Jupyter) → `.label`

### 3.5. Dot

```css
.dot.green  /* #79c7a1 */
.dot.amber  /* #d2a25f */
.dot.red    /* #cf7b6c; box-shadow: 0 0 3px rgba(207,123,108,0.45) */
.dot.blue   /* #7ab7c6 */
.dot.none   /* background: transparent */
```

Размер: 6×6px, `border-radius: 50%`.

Семантика dot по сущности:

| Сущность | Состояние | Dot |
|---|---|---|
| Collector | running/live | green |
| Collector | idle/stopped | amber |
| Recording | есть данные | green |
| Analysis | много событий (≥50) | green |
| Analysis | мало событий | amber |
| Analysis | low sample (<20) | red |
| Strategy | nb✓ | green |
| Strategy | nb⚠ | amber |
| Backtest | есть trades | green |
| Paper Run | running | green |
| Paper Run | stopped | amber |
| Dashboard | — | blue |
| Ticks, BBO, Bins | — | blue |
| Jupyter | — | blue |

### 3.6. Badge

```css
.badge {
  font-size: 9px; font-weight: 700; letter-spacing: 0.06em;
  padding: 1px 5px; border-radius: 3px; border: 1px solid;
}

.badge.live, .badge.running  { color: var(--green); border-color: rgba(121,199,161,0.36); background: rgba(121,199,161,0.12); }
.badge.idle                  { color: var(--amber); border-color: rgba(210,162,95,0.34);  background: rgba(210,162,95,0.12);  }
.badge.low-sample            { color: var(--red);   border-color: rgba(207,123,108,0.34); background: rgba(207,123,108,0.12); }
.badge.nb-ok                 { color: var(--green); border-color: rgba(121,199,161,0.36); background: rgba(121,199,161,0.12); }
.badge.nb-warn               { color: var(--amber); border-color: rgba(210,162,95,0.34);  background: rgba(210,162,95,0.12);  }
.badge.mc                    { color: var(--purple);border-color: rgba(168,139,190,0.34); background: rgba(168,139,190,0.12); }
```

Один badge на row (правило из doc #17).

### 3.7. Chip

```css
.chip {
  font-size: 9px; font-weight: 600; color: var(--text-dim);
  background: var(--panel-alt); border: 1px solid var(--border);
  border-radius: 3px; padding: 1px 5px;
}
```

Короткий: `4h`, `3`, `165 ev`, `2.4k ev/s`, `2 BT`.

Правило:
- chip пассивный, не action
- chip должен выглядеть тише, чем button
- если рядом есть buttons, chip не должен повторять их контраст и affordance один в один
- в content panels summary metrics по умолчанию лучше собирать в quiet summary line, а не в ряд button-like pills

### 3.8. Subtree

```css
.subtree {
  margin-left: 12px;
  padding-left: 8px;
  border-left: 1px solid var(--border-dim);
}
```

### 3.9. Scrollbar

```css
scrollbar-width: thin;
scrollbar-color: var(--border) transparent;
/* webkit: width 4px, thumb background var(--border) */
```

---

## 4. Action компоненты

### 4.1. Action Rail

Появляется под выбранным row. Привязана к selected entity.

```html
<div class="action-rail">
  <button class="rail-btn primary">Run BT</button>
  <button class="rail-btn ghost">Open Notebook</button>
  <button class="rail-btn warn">Start Paper</button>
  <button class="rail-btn danger">Delete</button>
</div>
```

```css
.action-rail {
  display: flex; flex-wrap: wrap; gap: 4px;
  padding: 4px 12px 5px 26px;
  background: #1b2026;
  border-left: 2px solid var(--accent);
  border-bottom: 1px solid var(--border-dim);
}

.rail-btn {
  font: 10px/1 var(--mono); font-weight: 600;
  letter-spacing: 0.04em;
  padding: 3px 8px; border-radius: 3px; border: 1px solid;
}

.rail-btn.primary { color: var(--accent);    border-color: rgba(134,195,186,0.32); background: rgba(134,195,186,0.10); }
.rail-btn.primary:hover { background: rgba(134,195,186,0.18); border-color: rgba(134,195,186,0.46); }

.rail-btn.warn    { color: var(--amber);     border-color: rgba(210,162,95,0.32);  background: rgba(210,162,95,0.08);  }
.rail-btn.warn:hover    { background: rgba(210,162,95,0.16); }

.rail-btn.ghost   { color: var(--text-dim);  border-color: var(--border);          background: transparent; }
.rail-btn.ghost:hover   { background: var(--panel-alt); color: var(--text); }

.rail-btn.danger  { color: #df9b90;          border-color: rgba(207,123,108,0.24); background: transparent; }
.rail-btn.danger:hover  { background: rgba(207,123,108,0.10); border-color: rgba(207,123,108,0.38); }
```

Лимит: максимум 4 кнопки на rail (правило из doc #17 §7).

### 4.2. Delete Confirm Strip

Заменяет action rail после нажатия кнопки danger.

```html
<div class="delete-confirm">
  <span>Delete "entity_name"?</span>
  <button class="dc-btn confirm">Yes, Delete</button>
  <button class="dc-btn cancel">Cancel</button>
</div>
```

```css
.delete-confirm {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 12px 5px 26px;
  background: rgba(207,123,108,0.10);
  border-left: 2px solid var(--red);
  border-bottom: 1px solid rgba(207,123,108,0.18);
  font-size: 10px; color: #e5a399;
}

.dc-btn { font: 10px/1 var(--mono); font-weight: 700; padding: 3px 8px; border-radius: 3px; border: 1px solid; }
.dc-btn.confirm { color: #efb0a4; border-color: rgba(207,123,108,0.42); background: rgba(207,123,108,0.14); }
.dc-btn.confirm:hover { background: rgba(207,123,108,0.22); }
.dc-btn.cancel  { color: var(--text-dim); border-color: var(--border); background: transparent; }
.dc-btn.cancel:hover  { background: var(--panel-alt); color: var(--text); }
```

### 4.3. Header Button

```html
<button class="header-btn">⟳ Refresh</button>
```

```css
.header-btn {
  background: var(--panel-alt); border: 1px solid var(--border);
  color: var(--text-dim); border-radius: 4px;
  padding: 3px 8px; font: 10px/1.4 var(--mono);
  letter-spacing: 0.04em;
}
.header-btn:hover { background: var(--panel); border-color: var(--line); color: var(--text); }
```

---

## 5. Main zone компоненты

Эти компоненты используются на страницах справа от sidebar. Стиль выводится из дизайн-системы sidebar — тот же цветовой язык, те же токены.

### 5.1. Page Title Strip

```html
<div class="page-title">
  <div class="page-title-main">
    <span class="page-title-name">entity_name</span>
    <span class="page-title-meta">Apr 22 · 4h · 165 events</span>
  </div>
  <div class="page-title-actions">
    <!-- те же .rail-btn классы -->
  </div>
</div>
```

Стиль: фон `--panel-alt`, border-bottom `--border`, padding `10px 20px`. Высота фиксированная, не переносится.

### 5.2. Panel / Card

```css
.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 12px 16px;
}

.panel-title {
  font-size: 10px; font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.1em; text-transform: uppercase;
  margin-bottom: 8px;
}
```

### 5.3. KPI / Stat Row

```html
<div class="stat-row">
  <div class="stat-item">
    <div class="stat-label">Trades</div>
    <div class="stat-value">1 284</div>
  </div>
  <div class="stat-item">
    <div class="stat-label">PnL</div>
    <div class="stat-value green">+1.84x</div>
  </div>
</div>
```

```css
.stat-label { font-size: 9px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; }
.stat-value { font-size: 14px; font-weight: 600; color: var(--text); margin-top: 2px; }
.stat-value.green  { color: var(--green); }
.stat-value.amber  { color: var(--amber); }
.stat-value.red    { color: var(--red); }
```

### 5.4. Banner / Alert Strip

```html
<div class="banner warn">
  <span class="banner-icon">⚠</span>
  <span class="banner-text">Low sample — fewer than 20 events</span>
  <a class="banner-link" href="#">Collect more data →</a>
</div>
```

```css
.banner {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 16px;
  border-left: 3px solid;
  font-size: 11px;
}
.banner.warn   { background: rgba(210,162,95,0.08);  border-color: var(--amber); color: var(--amber); }
.banner.danger { background: rgba(207,123,108,0.08); border-color: var(--red);   color: var(--red);   }
.banner.info   { background: rgba(122,183,198,0.08); border-color: var(--blue);  color: var(--blue);  }
.banner-link   { margin-left: auto; color: inherit; opacity: 0.8; text-decoration: none; white-space: nowrap; }
.banner-link:hover { opacity: 1; }
```

### 5.5. Table

```css
.data-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.data-table th {
  font-size: 9px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--text-muted);
  padding: 6px 8px; border-bottom: 1px solid var(--border);
  text-align: left;
}
.data-table td {
  padding: 5px 8px; border-bottom: 1px solid var(--border-dim);
  color: var(--text);
}
.data-table tr:hover td { background: var(--surface-hover); cursor: pointer; }
.data-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.data-table .green { color: var(--green); }
.data-table .red   { color: var(--red); }
```

### 5.6. Inline Form / Expand

```html
<div class="inline-form">
  <div class="form-row">
    <label class="form-label">threshold_sigma</label>
    <input class="form-input" type="number" value="1.5">
  </div>
  <div class="form-actions">
    <button class="rail-btn primary">Run</button>
    <button class="rail-btn ghost">Cancel</button>
  </div>
</div>
```

```css
.inline-form {
  padding: 10px 16px;
  background: var(--panel-alt);
  border-top: 1px solid var(--border-dim);
  border-bottom: 1px solid var(--border-dim);
}
.form-row { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.form-label { font-size: 10px; color: var(--text-muted); width: 140px; flex-shrink: 0; }
.form-input {
  background: var(--bg); border: 1px solid var(--border);
  color: var(--text); font: 11px var(--mono);
  padding: 3px 8px; border-radius: 3px; width: 120px;
}
.form-input:focus { outline: none; border-color: var(--accent); }
.form-actions { display: flex; gap: 6px; margin-top: 8px; }
```

### 5.6.1. Checkbox / Boolean Option

Checkbox нужен для локальных view-options, а не для persistent enable/disable state.

Использовать для:
- `Auto-scroll`
- `Show BBO`
- `Show EMA`
- `Show all followers`

Не использовать для:
- venue enable/disable
- runtime on/off
- любой state, который выглядит как переключатель-конфиг

Для persistent on/off использовать toggle/switch, а не браузерный checkbox.

```html
<label class="check">
  <input type="checkbox" checked>
  <span class="check-box" aria-hidden="true"></span>
  <span class="check-label">Auto-scroll</span>
</label>
```

```css
.check {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  min-height: 16px;
}
.check input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.check-box {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--bg);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 100ms, border-color 100ms, box-shadow 100ms;
}
.check-box::after {
  content: "";
  width: 5px;
  height: 9px;
  border-right: 2px solid transparent;
  border-bottom: 2px solid transparent;
  transform: rotate(45deg) scale(0.7);
  transform-origin: center;
  opacity: 0;
  transition: opacity 100ms, transform 100ms, border-color 100ms;
  margin-top: -1px;
}
.check-label {
  font-size: 10px;
  color: var(--text-dim);
  letter-spacing: 0.02em;
}
.check:hover .check-box {
  border-color: var(--line);
  background: var(--panel-alt);
}
.check input:checked + .check-box {
  border-color: rgba(134,195,186,0.56);
  background: rgba(134,195,186,0.14);
  box-shadow: inset 0 0 0 1px rgba(134,195,186,0.14);
}
.check input:checked + .check-box::after {
  opacity: 1;
  transform: rotate(45deg) scale(1);
  border-color: var(--accent);
}
.check input:focus-visible + .check-box {
  outline: 1px solid rgba(134,195,186,0.9);
  outline-offset: 2px;
}
```

Правило:
- checkbox не должен рендериться в системном синем стиле браузера;
- check-mark использует `--accent`, а не random OS color;
- label живёт справа и набирается тем же mono, что и остальные controls.

### 5.6.2. Switch / Persistent Enabled State

Switch нужен для настроек, которые меняют состояние runtime/config и читаются как `on/off`.

Использовать для:
- `Enabled`
- `Venue enabled`
- `Notebook sync on/off`
- любой persistent config flag

Не использовать для:
- `Auto-scroll`
- одноразовых filters
- временных display options

```html
<label class="toggle">
  <input type="checkbox" checked>
  <span class="toggle-track"></span>
</label>
```

```css
.toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}
.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}
.toggle-track {
  width: 28px;
  height: 15px;
  background: var(--border);
  border-radius: 999px;
  position: relative;
  transition: background 120ms;
}
.toggle-track::after {
  content: "";
  position: absolute;
  width: 11px;
  height: 11px;
  top: 2px;
  left: 2px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: transform 120ms, background 120ms;
}
.toggle input:checked + .toggle-track {
  background: rgba(134,195,186,0.3);
}
.toggle input:checked + .toggle-track::after {
  transform: translateX(13px);
  background: var(--accent);
}
```

Правило:
- switch остаётся компактным и не превращается в жирный SaaS-тумблер;
- `on` state читается через accent-tinted track + светлый knob;
- для table cell switch центрируется и не липнет к левому краю колонки.

### 5.7. Decision Strip / Empty State

```html
<div class="decision-strip">
  <span class="decision-text">No pattern found</span>
  <a class="rail-btn ghost" href="#">Try lower threshold →</a>
  <a class="rail-btn ghost" href="#">Collect more data →</a>
</div>
```

```css
.decision-strip {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 10px 16px;
  background: var(--panel-alt);
  border: 1px solid var(--border-dim);
  border-radius: 4px;
  font-size: 11px; color: var(--text-muted);
}
.decision-text { margin-right: auto; }
```

---

## 6. Состояния интерактивности

### Selected row

```css
.tree-item.selected > .row {
  background: var(--surface-active);
  border-left-color: var(--accent);
}
```

### Hover

```css
transition: background 80ms;   /* row hover */
transition: all 80ms;          /* rail-btn hover */
transition: background 100ms, color 100ms, border-color 100ms;  /* header-btn */
```

### Twisty (chevron)

```css
.twisty svg { transition: transform 120ms; }
.tree-item.open > .row .twisty svg { transform: rotate(90deg); }
```

---

## 7. Семантика entity → цвет

| Тип | Dot | Badge | Chip пример |
|---|---|---|---|
| Dashboard | blue | — | — |
| Collector | green/amber | LIVE / idle | 2.4k ev/s |
| Collector Run | green | running | 4 venues |
| Venue | green/amber | LIVE / idle | — |
| Recording | green | — | 4h |
| Ticks | blue | — | — |
| BBO | blue | — | — |
| Analysis | green/amber/red | low-sample | 165 ev |
| Bins | blue | — | — |
| Strategy | green/amber | nb✓ / nb⚠ | 2 BT |
| Notebook | green/amber | nb✓ / nb⚠ | — |
| Backtest | green | MC (если есть) | 1.84x |
| Monte Carlo | green/amber | MC | 500 runs |
| Paper Run | green/amber | running / LIVE | 32 trades |
| Trade | green | — | — |
| Jupyter | blue | — | — |

---

## 8. Что не входит в систему (hard rules)

Из doc #17 §2.4 и §9:

- Нет drag-and-drop
- Нет multi-select bulk flows
- Нет right-click menu как обязательного пути
- Нет modal windows
- Нет inline forms параметров внутри sidebar
- Нет tooltip tooltips как основного information path
- `Delete` → всегда через inline confirm strip, никогда browser confirm
