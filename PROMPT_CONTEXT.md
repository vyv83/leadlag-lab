# LeadLag Lab — Контекст для UX Prompt

## Философия (ОБЯЗАТЕЛЬНО прочитать)

**Ноутбук — лаборатория. Приложение — двигатель проверки.**

Стратегия пишется в Jupyter как Python класс → сохраняется через `%%writefile` в `.py` файл → приложение загружает тот же файл без трансформаций.

Пайплайн пользователя:
1. **Collector** — собрать данные по биржам
2. **Dashboard / Collector** — запустить анализ collection → получить session с events
3. **Explorer** — исследовать lead-lag события глазами (паттерн, follower, BBO, lag)
4. **JupyterLab** — написать стратегию как Python класс, сохранить через `%%writefile`
5. **Strategies** — убедиться что стратегия видна (valid=true), запустить backtest
6. **Backtest** — оценить gross/net PnL, fees, slippage, trades breakdown
7. **Trade Inspector** — разобрать отдельные сделки
8. **Monte Carlo** — проверить устойчивость (достаточно ли trades для CI)
9. **Paper** — запустить в realtime, сравнить с backtest

**Главный критерий**: каждый экран помогает ПРИНЯТЬ ИССЛЕДОВАТЕЛЬСКОЕ РЕШЕНИЕ, а не просто показывает данные.

---

## Приложение

**URL**: `https://vyv.ftp.sh/leadlag-lab/ui/dashboard.html`

**API**: `http://localhost:8899/api/...`

**UI файлы** (редактировать здесь):
```
/root/projects/leadlag-lab/leadlag/ui/
├── dashboard.html
├── collector.html
├── explorer.html
├── quality.html
├── strategy.html    ← Strategies screen
├── backtest.html
├── trade.html       ← Trade Inspector
├── montecarlo.html
├── paper.html
├── app.js           ← shared JS (base path, API calls)
└── style.css
```

**Backend**:
```
/root/projects/leadlag-lab/leadlag/api/app.py
```

**Данные**:
```
data/strategies/   ← .py файлы стратегий
data/sessions/     ← analyzed sessions
data/ticks/        ← raw parquet tick data
data/bbo/          ← BBO parquet data
```

**JupyterLab**: `https://vyv.ftp.sh/leadlag-lab/lab/`

---

## Текущие данные

- **Session**: `20260417_121202_b8e21fab` — 30 мин, 22 events (7A/5B/10C)
- **Strategies**: `baseline_signal_c`, `codex_manual_strategy_20260418`, `research_multi_signal_v1`
- **Collector**: работает, накапливает свежие данные (rotation 30 мин)
- **Когда анализировать**: после накопления 2+ часов данных → запустить analyze через Dashboard

---

## Приоритеты доработок (из ручного тестирования 2026-04-18)

### P0 — Рвёт пайплайн
*(уже исправлено: strategy_dev.ipynb восстановлен)*

### P1 — Мешает принять торговое решение

**Backtest / low sample warning**
- При `n_trades < 20` нет явного warning рядом с KPI
- 1 trade визуально выглядит как "успешный" результат с зелёными KPI
- Нужно: видимый banner при малой выборке + CTA "вернись в notebook"

**Dashboard / Collector — stale state**
- При `stale=true` venue rows всё равно показывают "живые" метрики ticks/s
- Пользователь не понимает что данные не собираются
- Нужно: banner "Collector stopped/stale since ...", приглушить live metrics, подпись "last snapshot"

**Strategies — непонятные действия**
- Кнопки `BT Paper Live`, символ ▶, `view`, `paper`, `×` — неясны новому пользователю
- Нужно: текстовые кнопки "Run backtest", "View backtest", "Start paper", "Delete"

### P2 — Замедляет исследование

**Explorer — нет исследовательского CTA**
- После выбора события нет подсказки "что смотреть дальше"
- Нужно: decision strip "Pattern visible? follower lag50=... BBO ok? → Open notebook"

**Monte Carlo — графики при low sample**
- При N<20 fan/distribution charts бессмысленны (вырожденное распределение)
- Нужно: warning + muted/disabled charts или "show anyway" collapse

**Quality — нет action hints**
- Venue summary показывает проценты но не говорит: usable / caution / exclude
- Нужно: decision label рядом с каждым venue

**Strategies — action labels**
- Кнопки нечитаемы, нет next-step hint per strategy

### P3 — Polish

**Entry URL**: `/leadlag-lab/` должен редиректить на `/leadlag-lab/ui/dashboard.html`

---

## Философия UX (для prompt)

**Минимализм как у Linear**: максимум полезного пространства, минимум отвлекающих элементов.
- Всё через клавиатуру где возможно
- Приоритет скорости и интуитивности для power users
- Каждый экран = одно исследовательское решение

**Жёсткие правила**:
- НИЧЕГО НЕ УДАЛЯТЬ из функциональности
- Только упрощать, перегруппировывать, улучшать hierarchy и flow
- Сохранять все данные, состояние и бизнес-логику

---

## Известные особенности

- `app.js` base-path aware: `/api/...` → `/leadlag-lab/api/...` автоматически
- Стратегия: Python класс с `name`, `version`, `description`, `params`, `on_event(event, ctx) → Order | None`
- Monte Carlo предупреждает при `n_trades < 20` через `n_trades_lt_20_monte_carlo_is_low_confidence`
- Playwright MCP использовать для всех браузерных проверок

---

## Полные документы (если нужно больше контекста)

- Философия разработки стратегий: `STRATEGY_DEVELOPMENT.md`
- Философия пайплайна и план ручного тестирования: `PHILOSOPHY_PIPELINE_MANUAL_TESTING.md`
- Отчёт ручного тестирования 2026-04-18: `MANUAL_PIPELINE_TEST_REPORT_2026-04-18.md`
