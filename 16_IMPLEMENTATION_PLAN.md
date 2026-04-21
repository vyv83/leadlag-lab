# LeadLag UI — Execution Plan (doc #16)

> **Для агента:** читай только этот файл. Никаких других документов не нужно.
> Выполняй пункты строго по порядку из CHECKLIST в конце.
> [ ] = не начато · [x] = сделано · [~] = частично

---

## КОНТЕКСТ ПРОЕКТА

**Что это:** Tornado веб-приложение для algotrading lead-lag стратегий.
**Где:** `/root/projects/leadlag/`
**Как запущено:** systemd сервис `leadlag-dashboard`, nginx reverse proxy на `/leadlag/`

**Ключевые файлы:**
```
/root/projects/leadlag/
├── dashboard/
│   ├── server.py          — URL routing, page handlers
│   ├── api.py             — все JSON API endpoints
│   ├── handlers.py        — HTML page handlers
│   ├── templates/
│   │   ├── base.html      — layout + sidebar (глобальный)
│   │   ├── overview.html  — /              (системный дашборд)
│   │   ├── events.html    — /events        (lead-lag события)
│   │   ├── backtest.html  — /backtest      (backtest результаты)
│   │   ├── paper.html     — /paper         (paper trading)
│   │   ├── research.html  — /research      (Jupyter + гайд)
│   │   ├── data_files.html — /files        (список parquet файлов)
│   │   └── settings.html  — /settings      (collector control + venues)
│   └── static/
│       ├── css/app.css    — все стили
│       └── js/
│           ├── app.js     — WebSocket client + DOM updates
│           ├── charts.js  — Chart.js wrappers
│           └── sidebar.js — СОЗДАТЬ НОВЫЙ ФАЙЛ
├── config/
│   ├── settings.py        — пути, порты (TICKS_DIR, BBO_DIR, DATA_DIR и т.д.)
│   └── venues.py          — конфиг всех бирж (VENUES dict)
├── data/
│   ├── ticks/             — parquet файлы по датам: data/ticks/YYYY-MM-DD/<venue>/ticks_*.parquet
│   ├── bbo/               — BBO данные
│   ├── backtest_results.json — ЕДИНСТВЕННЫЙ файл с результатами анализа
│   ├── paper_status.json  — статус paper trader
│   └── paper_trades/      — ежедневные JSONL с paper сделками
└── strategy/
    └── current_strategy.py — текущая стратегия (одна)
```

**Текущая навигация в sidebar (base.html):**
Overview → Events → Backtest → Paper Trading → Research → Data Files → Settings

**Проблемы которые решаем:**
1. Навигация не отражает pipeline (Research — точка входа, но стоит 5-й)
2. Sidebar плоский — нет иерархии DATA / ANALYSIS / RESEARCH
3. Events и Backtest — тупики без ссылок ("Run analysis in Jupyter" без CTA)
4. Sidebar footer всегда показывает "--" (не обновляется)
5. Нет кнопки Start для collector (только Stop/Restart)
6. Venue toggle кнопка Save делает вид что работает, но ничего не сохраняет
7. Страница называется "Settings" хотя там Collector Control

---

## ЦЕЛЕВОЙ РЕЗУЛЬТАТ

```
┌────────────────────────┬──────────────────────────────────────┐
│ LeadLag            [↺] │                                      │
│─────────────────────── │   <content area — без изменений>     │
│ ○ Overview             │                                      │
│ ○ Collector  [● 8v]    │                                      │
│                        │                                      │
│ ━━━ DATA ━━━━━━━━━━━━  │                                      │
│ ▶ Apr 19 · 4.2h · 8v  │                                      │
│ ▶ Apr 18 · 6.0h · 9v  │                                      │
│ ▶ Apr 17 · 2.1h · 8v  │                                      │
│                        │                                      │
│ ━━━ ANALYSIS ━━━━━━━━  │                                      │
│   Apr 19 · 165e · 4.2h │                                      │
│   [Events] [Backtest]  │                                      │
│                        │                                      │
│ ━━━ RESEARCH ━━━━━━━━  │                                      │
│ ▶ current_strategy     │                                      │
│   +45.2 bps · 88t      │                                      │
│   ● Paper: live 62t    │                                      │
│                        │                                      │
│ → Jupyter ↗            │                                      │
│────────────────────────│                                      │
│ ● Collector: 8v        │                                      │
│ ○ Paper: off           │                                      │
│ Storage: 1240 MB       │                                      │
└────────────────────────┴──────────────────────────────────────┘
```

**Sidebar читает данные из:**
- DATA секция: новый `/api/data/summary` (сканирует `data/ticks/` по датам)
- ANALYSIS секция: существующий `/api/backtest/results`
- RESEARCH секция: существующий `/api/paper/status`
- Footer: WebSocket статус (collector) + poll `/api/paper/status`

---

## ШАГ 1 — api.py: добавить три новых endpoint-а

**Файл:** `/root/projects/leadlag/dashboard/api.py`

Сначала прочитай файл чтобы найти место для вставки.
Ищи строку: `class SettingsVenuesAPI(JSONHandler):`

**1а. ЗАМЕНИТЬ класс SettingsVenuesAPI** (он сломан — ничего не сохраняет):

```python
from config.settings import PROJECT_DIR as _PROJECT_DIR
import json as _json_mod

_VENUES_OVERRIDE = _PROJECT_DIR / "config" / "venues_override.json"

class SettingsVenuesAPI(JSONHandler):
    def post(self):
        try:
            body = _json_mod.loads(self.request.body)
            enabled = body.get("enabled", [])
            _VENUES_OVERRIDE.parent.mkdir(exist_ok=True)
            _VENUES_OVERRIDE.write_text(_json_mod.dumps({"enabled": enabled}, indent=2))
            self.write_json({"ok": True, "saved": len(enabled)})
        except Exception as e:
            self.write_json({"ok": False, "error": str(e)})
```

**1б. ДОБАВИТЬ после класса CollectorStopAPI** новый класс CollectorStartAPI:

Ищи строку: `class CollectorStopAPI(JSONHandler):`
После всего блока этого класса добавить:

```python
class CollectorStartAPI(JSONHandler):
    def post(self):
        ok, out = _run_systemctl("start", "leadlag-collector")
        self.write_json({"ok": ok, "output": out})
```

**1в. ДОБАВИТЬ в конец файла** новый класс DataSummaryAPI:

```python
class DataSummaryAPI(JSONHandler):
    """Сканирует data/ticks/ и возвращает список дней с метриками."""
    def get(self):
        from config.settings import TICKS_DIR
        days = []
        if not TICKS_DIR.exists():
            self.write_json(days)
            return
        try:
            date_dirs = sorted(
                [d for d in TICKS_DIR.iterdir() if d.is_dir()],
                reverse=True
            )
        except Exception:
            self.write_json(days)
            return

        for date_dir in date_dirs:
            try:
                venue_dirs = [d for d in date_dir.iterdir() if d.is_dir()]
                all_files  = [f for vd in venue_dirs for f in vd.glob("*.parquet")]
                if not all_files:
                    continue
                total_bytes = sum(f.stat().st_size for f in all_files)
                mtimes      = [f.stat().st_mtime for f in all_files]
                duration_h  = round((max(mtimes) - min(mtimes)) / 3600, 1) if len(mtimes) > 1 else 0
                days.append({
                    "date":      date_dir.name,
                    "n_venues":  len(venue_dirs),
                    "size_mb":   round(total_bytes / 1024 / 1024, 1),
                    "duration_h": duration_h,
                    "files":     len(all_files),
                })
            except Exception:
                continue

        self.write_json(days[:30])
```

---

## ШАГ 2 — server.py: зарегистрировать новые routes

**Файл:** `/root/projects/leadlag/dashboard/server.py`

Прочитай файл. Найди список URL patterns (список с `(r"/api/...", ...)`).

**2а. Добавить импорт** в блок импортов из api.py:
Найди строку с импортами из `api` (что-то вроде `from .api import ...` или `from dashboard.api import ...`).
Добавить к существующим импортам: `CollectorStartAPI, DataSummaryAPI`

**2б. Добавить routes** в список URL patterns рядом с другими `/api/collector/` routes:
```python
(r"/api/collector/start", CollectorStartAPI),
(r"/api/data/summary", DataSummaryAPI),
```

---

## ШАГ 3 — config/venues.py: применять override при старте

**Файл:** `/root/projects/leadlag/config/venues.py`

Прочитай файл. Найди самый конец — после определения `VENUES = {...}` и `LEADERS`, `FOLLOWERS`, `FEES`.

Добавить В САМЫЙ КОНЕЦ файла:

```python
def _apply_venue_overrides(venues_dict):
    """Читает config/venues_override.json и применяет enabled/disabled."""
    from pathlib import Path
    import json
    override_path = Path(__file__).parent / "venues_override.json"
    if not override_path.exists():
        return venues_dict
    try:
        data = json.loads(override_path.read_text())
        enabled_set = set(data.get("enabled", list(venues_dict.keys())))
        for name, cfg in venues_dict.items():
            cfg.enabled = name in enabled_set
    except Exception:
        pass
    return venues_dict

VENUES = _apply_venue_overrides(VENUES)
```

---

## ШАГ 4 — app.css: добавить все новые стили

**Файл:** `/root/projects/leadlag/dashboard/static/css/app.css`

Добавить В САМЫЙ КОНЕЦ файла:

```css
/* ════════════════════════════════════════════════════
   SIDEBAR TREE — динамическое дерево состояния
   ════════════════════════════════════════════════════ */

/* Sidebar flex layout */
.sidebar {
    display: flex !important;
    flex-direction: column !important;
}
.sidebar-nav { flex-shrink: 0; }

.sidebar-tree {
    flex: 1;
    overflow-y: auto;
    min-height: 0;       /* критично для flex + overflow */
    padding-bottom: 4px;
}

/* Section dividers */
.sb-section {
    padding: 10px 14px 2px;
    font-size: 9px;
    color: #484f58;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    user-select: none;
    margin-top: 4px;
}

/* Tree rows */
.sb-row {
    display: flex;
    align-items: center;
    padding: 2px 10px 2px 14px;
    font-size: 11px;
    color: #8b949e;
    gap: 4px;
    line-height: 1.6;
    box-sizing: border-box;
}
.sb-row.clickable { cursor: pointer; }
.sb-row.clickable:hover { background: #161b22; color: #c9d1d9; }

/* Indentation */
.sb-i0 { padding-left: 14px; }
.sb-i1 { padding-left: 24px; }
.sb-i2 { padding-left: 34px; }

/* Arrow toggle */
.sb-arrow { font-size: 8px; color: #484f58; flex-shrink: 0; width: 10px; }

/* Badges */
.sb-badge { font-size: 9px; flex-shrink: 0; }
.sb-badge.green  { color: #3fb950; }
.sb-badge.yellow { color: #d29922; }
.sb-badge.red    { color: #f85149; }
.sb-badge.dim    { color: #484f58; }
.sb-badge.blue   { color: #58a6ff; }

/* Small action buttons */
.sb-action {
    display: inline-block;
    padding: 1px 6px;
    font-size: 10px;
    color: #58a6ff;
    border: 1px solid #1f6feb55;
    border-radius: 3px;
    cursor: pointer;
    text-decoration: none;
    white-space: nowrap;
}
.sb-action:hover {
    background: #1f6feb;
    color: #fff;
    text-decoration: none;
    border-color: #1f6feb;
}

/* Sidebar refresh button in header */
.sb-refresh {
    background: none;
    border: none;
    color: #484f58;
    cursor: pointer;
    font-size: 13px;
    padding: 0 2px;
    line-height: 1;
    margin-left: auto;
}
.sb-refresh:hover { color: #8b949e; }

/* Nav section labels (flat nav) */
.nav-section-label {
    padding: 10px 14px 2px;
    font-size: 9px;
    color: #484f58;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    user-select: none;
}

/* ── Empty states ────────────────────────────────── */
.empty-state {
    padding: 20px 16px;
    text-align: center;
}
.empty-state-title {
    font-size: 13px;
    color: #c9d1d9;
    margin-bottom: 6px;
}
.empty-state-text {
    font-size: 12px;
    color: #8b949e;
    margin-bottom: 12px;
}

/* ── Pipeline CTA strip (overview) ──────────────── */
.pipeline-cta {
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12px;
    color: #8b949e;
    border-left: 3px solid #1f6feb;
    flex-wrap: wrap;
    margin-bottom: 16px;
}
.pipeline-cta .cta-step {
    color: #58a6ff;
    font-weight: 600;
    white-space: nowrap;
}
```

---

## ШАГ 5 — sidebar.js: создать новый файл

**Файл:** `/root/projects/leadlag/dashboard/static/js/sidebar.js` **(СОЗДАТЬ)**

```javascript
/**
 * sidebar.js — динамическое дерево состояния системы LeadLag.
 *
 * Читает данные из:
 *   /api/data/summary      — список дней с parquet данными
 *   /api/backtest/results  — результаты последнего анализа
 *   /api/paper/status      — статус paper trader
 *
 * Экспортирует: window.refreshSidebar() — вызывать после мутаций
 */
(function () {
    'use strict';

    var BASE = window.BASE || '';
    var _cache = null;
    var _cacheTs = 0;
    var CACHE_TTL = 30000; // 30 секунд

    // ── Загрузка данных ──────────────────────────────────────────────
    function loadData(force) {
        var now = Date.now();
        if (!force && _cache && (now - _cacheTs) < CACHE_TTL) {
            return Promise.resolve(_cache);
        }
        return Promise.all([
            fetchJSON('/api/data/summary').catch(function () { return []; }),
            fetchJSON('/api/backtest/results').catch(function () { return null; }),
            fetchJSON('/api/paper/status').catch(function () { return null; }),
        ]).then(function (results) {
            _cache = { days: results[0], bt: results[1], paper: results[2] };
            _cacheTs = Date.now();
            return _cache;
        });
    }

    function fetchJSON(path) {
        return fetch(BASE + path).then(function (r) {
            if (!r.ok) throw new Error(r.status);
            return r.json();
        });
    }

    // ── Render ───────────────────────────────────────────────────────
    function renderSidebar(force) {
        var tree = document.getElementById('sb-tree');
        if (!tree) return;

        loadData(force).then(function (data) {
            tree.innerHTML = buildHTML(data);
        }).catch(function () {
            tree.innerHTML = '<div class="sb-row sb-i1" style="color:#484f58;font-size:10px">Load error</div>';
        });
    }

    function buildHTML(data) {
        var html = '';
        var page = location.pathname.replace(BASE, '') || '/';

        // ── DATA ─────────────────────────────────────────────────────
        html += '<div class="sb-section">Data</div>';

        var days = data.days || [];
        if (days.length === 0) {
            html += '<div class="sb-row sb-i1" style="font-size:10px;color:#484f58">' +
                'No data &nbsp;<a href="' + BASE + '/settings" class="sb-action">Collector →</a></div>';
        } else {
            var show = days.slice(0, 7);
            for (var i = 0; i < show.length; i++) {
                var day = show[i];
                var label = formatDate(day.date);
                var dur   = day.duration_h > 0 ? day.duration_h + 'h' : '—';
                var ven   = day.n_venues  > 0 ? day.n_venues  + 'v' : '';
                html += '<div class="sb-row sb-i0 clickable" ' +
                    'onclick="location.href=\'' + BASE + '/files\'" ' +
                    'title="' + esc(day.date) + ': ' + day.size_mb + ' MB, ' + day.files + ' files">' +
                    '<span class="sb-arrow">▶</span>' +
                    '<span>' + esc(label) + '</span>' +
                    '<span class="sb-badge dim" style="margin-left:auto">' + dur + ' · ' + ven + '</span>' +
                    '</div>';
            }
            if (days.length > 7) {
                html += '<div class="sb-row sb-i1" style="color:#484f58;font-size:10px">+' +
                    (days.length - 7) + ' more</div>';
            }
        }

        // ── ANALYSIS ─────────────────────────────────────────────────
        html += '<div class="sb-section">Analysis</div>';

        var bt = data.bt;
        if (!bt || bt.error) {
            html += '<div class="sb-row sb-i1" style="font-size:10px;color:#484f58">' +
                'No results &nbsp;<a href="' + BASE + '/research" class="sb-action">Lab →</a></div>';
        } else {
            var evCount = bt.events_count || 0;
            var dsH     = bt.dataset_hours || '?';
            var updated = bt.updated ? shortDate(bt.updated) : '—';
            var bestPnl = getBestPnl(bt);
            var pnlHtml = '';
            if (bestPnl !== null) {
                var pnlColor = bestPnl >= 0 ? '#3fb950' : '#f85149';
                var pnlSign  = bestPnl >= 0 ? '+' : '';
                pnlHtml = ' &nbsp;<span style="color:' + pnlColor + '">' +
                    pnlSign + bestPnl.toFixed(1) + ' bps</span>';
            }

            html += '<div class="sb-row sb-i0" style="flex-direction:column;align-items:flex-start;' +
                'padding:3px 14px 4px;gap:3px">' +
                '<div style="display:flex;align-items:center;gap:5px;width:100%;font-size:10px">' +
                '<span style="color:#c9d1d9">' + evCount + ' events</span>' +
                '<span class="sb-badge dim">' + dsH + 'h</span>' +
                pnlHtml +
                '<span class="sb-badge dim" style="margin-left:auto">' + esc(updated) + '</span>' +
                '</div>' +
                '<div style="display:flex;gap:4px">' +
                '<a href="' + BASE + '/events" class="sb-action' + (page === '/events' ? ' active' : '') + '">Events</a>' +
                '<a href="' + BASE + '/backtest" class="sb-action' + (page === '/backtest' ? ' active' : '') + '">Backtest</a>' +
                '</div>' +
                '</div>';
        }

        // ── RESEARCH ─────────────────────────────────────────────────
        html += '<div class="sb-section">Research</div>';

        var paper   = data.paper || {};
        var running = !!paper.running;

        // Имя стратегии
        var stratName = 'current_strategy';
        if (paper.strategy_description && paper.strategy_description !== 'none') {
            // берём первые 28 символов description
            var desc = paper.strategy_description;
            stratName = desc.length > 28 ? desc.slice(0, 28) + '…' : desc;
        }

        html += '<div class="sb-row sb-i0 clickable" onclick="location.href=\'' + BASE + '/paper\'">' +
            '<span class="sb-arrow">▶</span>' +
            '<span style="color:#c9d1d9">' + esc(stratName) + '</span>' +
            '</div>';

        // Backtest stats под стратегией
        if (bt && !bt.error) {
            var pnl2 = getBestPnl(bt);
            var n2   = bt.ci_table && bt.ci_table.length ? (bt.ci_table[0].count || '') : '';
            if (pnl2 !== null) {
                var col2 = pnl2 >= 0 ? '#3fb950' : '#f85149';
                var sign2 = pnl2 >= 0 ? '+' : '';
                html += '<div class="sb-row sb-i1" style="font-size:10px">' +
                    '<span style="color:' + col2 + '">' + sign2 + pnl2.toFixed(1) + ' bps</span>' +
                    (n2 ? '<span class="sb-badge dim" style="margin-left:4px">· ' + n2 + 't</span>' : '') +
                    '</div>';
            }
        }

        // Paper статус
        if (running) {
            var trades2 = paper.total_trades || 0;
            var ppnl    = (paper.total_pnl_bps || 0).toFixed(1);
            var pcol    = (paper.total_pnl_bps || 0) >= 0 ? '#3fb950' : '#f85149';
            html += '<div class="sb-row sb-i1">' +
                '<span class="sb-badge green">●</span>&nbsp;' +
                '<span style="font-size:10px">Paper: ' + trades2 + 't</span>' +
                '<span style="color:' + pcol + ';font-size:10px;margin-left:4px">' + ppnl + ' bps</span>' +
                '</div>';
        } else {
            html += '<div class="sb-row sb-i1" style="color:#484f58;font-size:10px">' +
                '<span class="sb-badge dim">○</span>&nbsp;Paper: off</div>';
        }

        // ── Jupyter link ──────────────────────────────────────────────
        html += '<div style="height:6px"></div>';
        html += '<div class="sb-row sb-i0 clickable" ' +
            'onclick="window.open(\'' + BASE + '/lab/\',\'_blank\')" ' +
            'style="color:#484f58;font-size:11px">→ Jupyter ↗</div>';

        return html;
    }

    // ── Helpers ──────────────────────────────────────────────────────
    function getBestPnl(bt) {
        if (!bt || !bt.ci_table || !bt.ci_table.length) return null;
        var best = bt.ci_table.reduce(function (a, b) {
            return Number(a.net_pnl || 0) >= Number(b.net_pnl || 0) ? a : b;
        });
        return Number(best.net_pnl || 0);
    }

    function formatDate(dateStr) {
        try {
            var d = new Date(dateStr + 'T00:00:00Z');
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
        } catch (e) { return dateStr; }
    }

    function shortDate(ts) {
        try {
            var d = new Date(ts);
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        } catch (e) { return String(ts).slice(0, 10); }
    }

    function esc(s) {
        return String(s || '').replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    // ── Public API ───────────────────────────────────────────────────
    window.refreshSidebar = function () {
        _cache = null;
        _cacheTs = 0;
        renderSidebar(true);
    };

    // ── Init ─────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function () {
        renderSidebar(false);
        setInterval(function () { renderSidebar(false); }, 30000);
    });

}());
```

---

## ШАГ 6 — base.html: заменить sidebar

**Файл:** `/root/projects/leadlag/dashboard/templates/base.html`

Прочитай файл. Найди весь блок `<nav class="sidebar">...</nav>` (примерно строки 13-47).
**Заменить его целиком на:**

```html
<nav class="sidebar">
    <div class="sidebar-header">
        <a href="{{ B }}/" style="color:inherit;text-decoration:none">
            <span class="logo">LeadLag</span>
        </a>
        <button class="sb-refresh" onclick="refreshSidebar()" title="Refresh sidebar">↺</button>
        <span id="ws-status" class="ws-dot" title="WebSocket" style="margin-left:4px">●</span>
    </div>

    <div class="sidebar-nav">
        <a href="{{ B }}/" class="nav-item {% if current_path == '/' %}active{% end %}">
            <span class="nav-icon">&#9635;</span> Overview
        </a>
        <a href="{{ B }}/settings" class="nav-item {% if current_path == '/settings' %}active{% end %}">
            <span class="nav-icon">&#9881;</span> Collector
        </a>
    </div>

    <div class="sidebar-tree" id="sb-tree">
        <div class="sb-row sb-i1" style="color:#484f58;font-size:10px">Loading…</div>
    </div>

    <div class="sidebar-footer" id="sidebar-status">
        <div class="status-item">
            <span id="sb-collector-dot" class="status-dot gray">●</span>
            <span id="sb-collector-label">Collector: —</span>
        </div>
        <div class="status-item">
            <span id="sb-paper-dot" class="status-dot gray">●</span>
            <span id="sb-paper-label">Paper: —</span>
        </div>
        <div class="status-item" id="sb-storage">Storage: —</div>
    </div>
</nav>
```

Также найти строку `<script src="{{ B }}/static/js/app.js"></script>` в конце body.
**Добавить ПОСЛЕ неё:**
```html
<script src="{{ B }}/static/js/sidebar.js"></script>
```

---

## ШАГ 7 — app.js: добавить обновление sidebar footer

**Файл:** `/root/projects/leadlag/dashboard/static/js/app.js`

Прочитай файл целиком.

**7а.** Найди место где обрабатываются данные из WebSocket (ищи `onmessage` или функцию которая обновляет статус venue — что-то вроде `function updateStatus` или `ws.onmessage`).
После того как эта функция получает данные о venues/статусе — добавить вызов:
```javascript
updateSidebarFooter(data);
```
где `data` — объект со статусом (тот же что обновляет остальной UI).

**7б.** В конец файла добавить:

```javascript
// ── Sidebar footer updaters ──────────────────────────────────────
function updateSidebarFooter(status) {
    var venues  = status.venues || {};
    var vals    = Object.values(venues);
    var active  = vals.filter(function(v) { return v.status === 'ok' && v.rate > 0; }).length;
    var running = active > 0;

    var dot   = document.getElementById('sb-collector-dot');
    var label = document.getElementById('sb-collector-label');
    if (dot)   dot.className   = 'status-dot ' + (running ? 'green' : 'gray');
    if (label) label.textContent = running ? 'Collector: ' + active + 'v' : 'Collector: off';

    var storageMb = ((status.files || {}).total_mb) || 0;
    var storEl = document.getElementById('sb-storage');
    if (storEl) storEl.textContent = 'Storage: ' + storageMb + ' MB';
}

function pollPaperFooter() {
    fetch((window.BASE || '') + '/api/paper/status')
        .then(function(r) { return r.json(); })
        .then(function(s) {
            var dot   = document.getElementById('sb-paper-dot');
            var label = document.getElementById('sb-paper-label');
            if (dot)   dot.className   = 'status-dot ' + (s.running ? 'green' : 'gray');
            if (label) label.textContent = s.running
                ? 'Paper: ' + (s.total_trades || 0) + 't'
                : 'Paper: off';
        }).catch(function() {});
}

document.addEventListener('DOMContentLoaded', function() {
    pollPaperFooter();
    setInterval(pollPaperFooter, 15000);
});
```

---

## ШАГ 8 — events.html: убрать dead-end, добавить CTA

**Файл:** `/root/projects/leadlag/dashboard/templates/events.html`

Прочитай файл. Найди JS блок где при ошибке загрузки или пустых данных ставится текст.

Найди строку содержащую: `No backtest results`
Заменить весь innerHTML на котором она находится (и похожий в catch-блоке) на:

```javascript
'<tr><td colspan="7"><div class="empty-state">' +
'<div class="empty-state-title">No analysis results yet</div>' +
'<div class="empty-state-text">Run <code>research.ipynb</code> in JupyterLab (cells 1–8) to detect lead-lag events.</div>' +
'<a href="' + (window.BASE || '') + '/research" class="btn btn-primary" style="margin-top:8px">Open Lab →</a>' +
'</div></td></tr>'
```

Найди строку содержащую: `Failed to load results`
Заменить на:
```javascript
'<tr><td colspan="7"><div class="empty-state">' +
'<div class="empty-state-title">Failed to load results</div>' +
'<a href="' + (window.BASE || '') + '/research" class="btn" style="margin-top:8px">Open Lab →</a>' +
'</div></td></tr>'
```

---

## ШАГ 9 — backtest.html: убрать dead-end, добавить CTA

**Файл:** `/root/projects/leadlag/dashboard/templates/backtest.html`

Прочитай файл. Найди строку содержащую: `No backtest results yet`
(Это в `{% if not results %}` блоке, примерно строки 17-20.)

Заменить весь `<span class="text-dim">No backtest results yet...</span>` на:

```html
<div class="empty-state">
    <div class="empty-state-title">No backtest results yet</div>
    <div class="empty-state-text">Run <code>research.ipynb</code> in JupyterLab (cells 1–8) to generate results.</div>
    <a href="{{ B }}/research" class="btn btn-primary" style="margin-top:8px">Open Lab →</a>
</div>
```

---

## ШАГ 10 — settings.html: переименовать и добавить Start

**Файл:** `/root/projects/leadlag/dashboard/templates/settings.html`

**10а.** Найти `<h1>Settings</h1>` — заменить на `<h1>Collector</h1>`

**10б.** Найти `<div class="toolbar">` внутри карточки Collector Control.
Заменить содержимое toolbar на:
```html
<button class="btn btn-primary" onclick="collectorAction('start')">Start</button>
<button class="btn" onclick="collectorAction('restart')">Restart</button>
<button class="btn btn-danger" onclick="collectorAction('stop')">Stop</button>
<span id="collector-action-result" class="text-dim"></span>
```

---

---

## ШАГ 11 — api.py: CRUD DELETE endpoints

**Файл:** `/root/projects/leadlag/dashboard/api.py`

Добавить в конец файла (после `DataSummaryAPI`):

```python
class BacktestClearAPI(JSONHandler):
    """DELETE /api/backtest/results — удалить backtest_results.json."""
    def delete(self):
        path = DATA_DIR / "backtest_results.json"
        try:
            if path.exists():
                path.unlink()
            self.write_json({"ok": True})
        except Exception as e:
            self.write_json({"ok": False, "error": str(e)})


class PaperClearAPI(JSONHandler):
    """POST /api/paper/clear — сбросить paper trading (статус + все трейды)."""
    def post(self):
        errors = []
        # Очистить paper_status.json
        status_path = DATA_DIR / "paper_status.json"
        try:
            if status_path.exists():
                status_path.unlink()
        except Exception as e:
            errors.append(str(e))
        # Удалить все JSONL файлы трейдов
        trade_dir = DATA_DIR / "paper_trades"
        if trade_dir.exists():
            for f in trade_dir.glob("*.jsonl"):
                try:
                    f.unlink()
                except Exception as e:
                    errors.append(str(e))
        self.write_json({"ok": not errors, "errors": errors})


class ResearchRunsAPI(JSONHandler):
    """GET /api/research/runs — список папок экспериментов."""
    def get(self):
        runs_dir = DATA_DIR / "research_runs"
        if not runs_dir.exists():
            self.write_json([])
            return
        runs = []
        for d in sorted(runs_dir.iterdir(), reverse=True):
            if d.is_dir():
                try:
                    size_mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                    runs.append({
                        "id": d.name,
                        "size_mb": round(size_mb / 1024 / 1024, 1),
                    })
                except Exception:
                    runs.append({"id": d.name, "size_mb": 0})
        self.write_json(runs[:50])


class ResearchRunDeleteAPI(JSONHandler):
    """DELETE /api/research/runs/{id} — удалить папку эксперимента."""
    def delete(self, run_id):
        import shutil
        # Санитизация: не допускать path traversal
        run_id = run_id.replace("/", "").replace("..", "")
        run_path = DATA_DIR / "research_runs" / run_id
        try:
            if run_path.exists() and run_path.is_dir():
                shutil.rmtree(run_path)
                self.write_json({"ok": True, "deleted": run_id})
            else:
                self.write_json({"ok": False, "error": "not found"})
        except Exception as e:
            self.write_json({"ok": False, "error": str(e)})
```

---

## ШАГ 12 — server.py: зарегистрировать CRUD routes

**Файл:** `/root/projects/leadlag/dashboard/server.py`

**12а. Добавить импорты** к существующей строке импортов из api:
```python
BacktestClearAPI, PaperClearAPI, ResearchRunsAPI, ResearchRunDeleteAPI,
```

**12б. Добавить routes** в список URL patterns:
```python
(r"/api/backtest/results", BacktestClearAPI),   # DELETE метод
(r"/api/paper/clear", PaperClearAPI),
(r"/api/research/runs", ResearchRunsAPI),
(r"/api/research/runs/(.+)", ResearchRunDeleteAPI),
```

⚠ Внимание: `/api/backtest/results` уже зарегистрирован как GET через `BacktestResultsAPI`.
Tornado маршрутизирует по классу, не по методу. Нужно **объединить в один класс** или сделать
отдельный URL `DELETE /api/backtest/clear`. Используем отдельный URL:

```python
(r"/api/backtest/clear", BacktestClearAPI),   # вместо /api/backtest/results
(r"/api/paper/clear", PaperClearAPI),
(r"/api/research/runs", ResearchRunsAPI),
(r"/api/research/runs/(.+)", ResearchRunDeleteAPI),
```

И в `BacktestClearAPI.delete` выше — метод уже написан для `DELETE`, но поскольку вызов
из JS удобнее через `fetch(..., {method:'DELETE'})`, можно оставить как есть.

---

## ШАГ 13 — backtest.html: кнопка Clear Results + inline danger strip

**Файл:** `/root/projects/leadlag/dashboard/templates/backtest.html`

В секции `{% if results %}` найти конец блока `.info-bar` (примерно строка 19).
Добавить после `</div>` info-bar:

```html
<div class="toolbar" style="margin-top:8px">
    <button class="btn btn-danger" onclick="showClearConfirm()">Clear Results</button>
    <span id="clear-confirm" style="display:none">
        ⚠ Delete backtest_results.json? All analysis data will be lost.
        &nbsp;<button class="btn btn-danger" onclick="clearBacktest()">Confirm Delete</button>
        &nbsp;<button class="btn" onclick="hideClearConfirm()">Cancel</button>
    </span>
    <span id="clear-result" class="text-dim"></span>
</div>
```

В блок `{% block scripts %}` добавить JS:

```javascript
function showClearConfirm() {
    document.getElementById('clear-confirm').style.display = 'inline';
}
function hideClearConfirm() {
    document.getElementById('clear-confirm').style.display = 'none';
}
function clearBacktest() {
    fetch((window.BASE || '') + '/api/backtest/clear', {method: 'DELETE'})
        .then(r => r.json())
        .then(d => {
            hideClearConfirm();
            const el = document.getElementById('clear-result');
            if (d.ok) {
                el.textContent = 'Cleared. Reload to see empty state.';
                el.className = 'text-positive';
                setTimeout(() => location.reload(), 1500);
            } else {
                el.textContent = 'Error: ' + (d.error || '?');
                el.className = 'text-negative';
            }
        });
}
```

---

## ШАГ 14 — paper.html: кнопка Clear Paper Data + inline danger strip

**Файл:** `/root/projects/leadlag/dashboard/templates/paper.html`

Найти `<div class="card" id="paper-status-card">`. Добавить toolbar сразу после `</div>` info-bar:

```html
<div class="toolbar" style="margin-top:8px">
    <button class="btn btn-danger" onclick="showPaperClearConfirm()">Clear Paper Data</button>
    <span id="paper-clear-confirm" style="display:none">
        ⚠ Delete all paper trades and reset status?
        &nbsp;<button class="btn btn-danger" onclick="clearPaperData()">Confirm</button>
        &nbsp;<button class="btn" onclick="hidePaperClearConfirm()">Cancel</button>
    </span>
    <span id="paper-clear-result" class="text-dim"></span>
</div>
```

Добавить в `{% block scripts %}` перед закрывающим `</script>`:

```javascript
function showPaperClearConfirm() {
    document.getElementById('paper-clear-confirm').style.display = 'inline';
}
function hidePaperClearConfirm() {
    document.getElementById('paper-clear-confirm').style.display = 'none';
}
function clearPaperData() {
    fetch((window.BASE || '') + '/api/paper/clear', {method: 'POST'})
        .then(r => r.json())
        .then(d => {
            hidePaperClearConfirm();
            const el = document.getElementById('paper-clear-result');
            if (d.ok) {
                el.textContent = 'Cleared.';
                el.className = 'text-positive';
                setTimeout(() => location.reload(), 1500);
            } else {
                el.textContent = 'Error: ' + (d.errors || []).join(', ');
                el.className = 'text-negative';
            }
        });
}
```

---

## ШАГ 15 — data_files.html: добавить Research Runs секцию с удалением

**Файл:** `/root/projects/leadlag/dashboard/templates/data_files.html`

Прочитай файл. В конец `{% block content %}` (перед `{% end %}`) добавить новую карточку:

```html
<!-- Research Runs -->
<div class="card">
    <h2>Research Runs</h2>
    <table class="data-table" id="runs-table">
        <thead>
            <tr><th>Run ID</th><th class="num">Size</th><th></th></tr>
        </thead>
        <tbody id="runs-tbody">
            <tr><td colspan="3" class="text-dim">Loading...</td></tr>
        </tbody>
    </table>
</div>
```

Добавить в `{% block scripts %}`:

```javascript
function loadResearchRuns() {
    fetch((window.BASE || '') + '/api/research/runs')
        .then(r => r.json())
        .then(runs => {
            const tbody = document.getElementById('runs-tbody');
            if (!runs.length) {
                tbody.innerHTML = '<tr><td colspan="3" class="text-dim">No research runs</td></tr>';
                return;
            }
            tbody.innerHTML = runs.map(r => `
                <tr id="run-row-${CSS.escape(r.id)}">
                    <td style="font-family:monospace;font-size:11px">${r.id}</td>
                    <td class="num">${r.size_mb} MB</td>
                    <td>
                        <span id="del-confirm-${CSS.escape(r.id)}" style="display:none">
                            <button class="btn btn-danger" style="font-size:10px"
                                onclick="deleteRun('${r.id.replace(/'/g,"\\'")}')">Delete</button>
                            <button class="btn" style="font-size:10px"
                                onclick="document.getElementById('del-confirm-${CSS.escape(r.id)}').style.display='none'">×</button>
                        </span>
                        <button class="btn" style="font-size:10px"
                            onclick="document.getElementById('del-confirm-${CSS.escape(r.id)}').style.display='inline';this.style.display='none'">🗑</button>
                    </td>
                </tr>
            `).join('');
        }).catch(() => {
            document.getElementById('runs-tbody').innerHTML =
                '<tr><td colspan="3" class="text-dim">Failed to load</td></tr>';
        });
}

function deleteRun(runId) {
    fetch((window.BASE || '') + '/api/research/runs/' + encodeURIComponent(runId), {method: 'DELETE'})
        .then(r => r.json())
        .then(d => {
            if (d.ok) {
                const row = document.getElementById('run-row-' + CSS.escape(runId));
                if (row) row.remove();
            }
        });
}

document.addEventListener('DOMContentLoaded', loadResearchRuns);
```

---

## CHECKLIST (для агента: помечай выполненные)

```
BACKEND:
[ ] Шаг 1а: api.py — заменить SettingsVenuesAPI (сохранение venue override в JSON)
[ ] Шаг 1б: api.py — добавить CollectorStartAPI
[ ] Шаг 1в: api.py — добавить DataSummaryAPI
[ ] Шаг 2:  server.py — зарегистрировать CollectorStartAPI + DataSummaryAPI
[ ] Шаг 3:  config/venues.py — добавить _apply_venue_overrides()

FRONTEND:
[ ] Шаг 4:  app.css — добавить все стили в конец файла
[ ] Шаг 5:  sidebar.js — создать новый файл
[ ] Шаг 6:  base.html — заменить sidebar nav на новую структуру
[ ] Шаг 7а: app.js — найти WS handler и добавить вызов updateSidebarFooter(data)
[ ] Шаг 7б: app.js — добавить updateSidebarFooter() и pollPaperFooter() в конец
[ ] Шаг 8:  events.html — заменить dead-end тексты на empty-state с CTA
[ ] Шаг 9:  backtest.html — заменить dead-end текст на empty-state с CTA
[ ] Шаг 10а: settings.html — h1 Settings → h1 Collector
[ ] Шаг 10б: settings.html — добавить Start кнопку в toolbar

CRUD:
[ ] Шаг 11: api.py — добавить BacktestClearAPI, PaperClearAPI, ResearchRunsAPI, ResearchRunDeleteAPI
[ ] Шаг 12: server.py — зарегистрировать /api/backtest/clear, /api/paper/clear, /api/research/runs
[ ] Шаг 13: backtest.html — добавить Clear Results кнопку + inline danger strip
[ ] Шаг 14: paper.html — добавить Clear Paper Data кнопку + inline danger strip
[ ] Шаг 15: data_files.html — добавить Research Runs секцию с кнопками удаления

ПРОВЕРКА:
[ ] Открыть /leadlag/ в браузере — sidebar рендерится
[ ] Sidebar DATA секция показывает даты (или "No data")
[ ] Sidebar ANALYSIS секция показывает events count или "No results"
[ ] Sidebar RESEARCH секция показывает стратегию и paper статус
[ ] Кнопка ↺ обновляет sidebar
[ ] /leadlag/events — если нет данных, видна кнопка "Open Lab →"
[ ] /leadlag/backtest — если нет данных, видна кнопка "Open Lab →"
[ ] /leadlag/settings — заголовок "Collector", есть кнопка Start
[ ] /leadlag/settings — Save & Restart venues реально пишет venues_override.json
[ ] /leadlag/backtest — кнопка "Clear Results" открывает подтверждение, после confirm удаляет данные
[ ] /leadlag/paper — кнопка "Clear Paper Data" сбрасывает трейды и статус
[ ] /leadlag/files — секция Research Runs показывает список, кнопка 🗑 удаляет запись
```

---

## ВОЗМОЖНЫЕ ПРОБЛЕМЫ

**Import ошибки в api.py:**
Проверь что в начале api.py есть `import json` (он обычно есть).
`PROJECT_DIR` импортируется из `config.settings` — проверь что там есть этот символ.

**sidebar.js не загружается:**
Проверь что в base.html тег `<script src="{{ B }}/static/js/sidebar.js">` стоит ПОСЛЕ `app.js`.

**DataSummaryAPI возвращает пустой список:**
Путь `TICKS_DIR` определён в `config/settings.py` как `DATA_DIR / "ticks"`.
Проверь что папка существует: `ls /root/projects/leadlag/data/ticks/`

**venues_override.json не создаётся:**
Путь `PROJECT_DIR / "config" / "venues_override.json"` = `/root/projects/leadlag/config/venues_override.json`
Папка config уже существует — файл создастся при первом Save.

**Sidebar footer не обновляется (Collector: —):**
app.js получает данные через WebSocket. Найди в app.js где данные применяются к DOM
(search: `venues`, `ticks`, `rate`) — там же добавь `updateSidebarFooter(data)`.
