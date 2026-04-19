# LeadLag Lab — Контекст для UX Prompt (doc #10)

> Связанные документы: 08_PHILOSOPHY_PIPELINE.md, 09_MANUAL_TEST_REPORT_2026-04-18.md, STRATEGY_DEVELOPMENT.md

---

## ФИЛОСОФИЯ ПРОЕКТА (читать внимательно — это основа всех решений)

### Суть

LeadLag Lab — это **исследовательская лаборатория**, а не торговый терминал и не no-code конструктор.

Пользователь — это **исследователь/quantitative analyst**, который выдвигает гипотезу о lead-lag эффекте между криптобиржами и проверяет её через последовательность всё более жёстких испытаний. Его инструмент — **Python + Jupyter**. Приложение — это **двигатель проверки**, а не замена ноутбуку.

### Почему Jupyter — главное

Стратегия — это **Python класс**. Не YAML конфиг. Не форма с полями. Не визуальный drag-and-drop конструктор. Исследователь пишет настоящий код: может импортировать pandas, numpy, scipy, определять вспомогательные функции, вычислять кастомные индикаторы (EMA, VWAP, BBO spread), применять сложную условную логику.

Ноутбук — это место итерации: изменил логику → запустил ячейку → увидел результат за секунды. Этот цикл должен быть быстрым и прямым.

**Что НЕЛЬЗЯ делать приложению:**
- Предлагать визуальный конструктор стратегий вместо ноутбука
- Дублировать тяжёлые вычисления (backtest, Monte Carlo) в ноутбуке
- Предлагать YAML/JSON конфиги как замену Python классу
- Скрывать сложность — исследователь хочет видеть реальные числа, не красивые упрощения

### Файл .py — единственный источник истины

```
notebooks/lighter_c_bbo_v2.ipynb  →  %%writefile  →  data/strategies/lighter_c_bbo_v2.py
                                                              ↓
                                                    Приложение загружает этот же файл
```

Один идентификатор везде: имя ноутбука = имя файла = ID стратегии. Никакой синхронизации, никаких расхождений.

Workflow ноутбука:
1. Копируешь `strategy_dev.ipynb` → переименовываешь (`lighter_c_bbo_v2.ipynb`)
2. Запускаешь ячейки: загрузка данных → `get_notebook_name()` → `STRATEGY_NAME = "lighter_c_bbo_v2"`
3. Ячейка с `%%writefile ../data/strategies/{STRATEGY_NAME}.py` (ПЕРВАЯ строка ячейки!) — пишешь стратегию
4. Запускаешь ячейку → файл создан/обновлён автоматически
5. Быстро тестируешь `on_event` на mock событии в ноутбуке
6. Переходишь в приложение → Strategies → Strategy уже видна → Run Backtest

### Пайплайн как последовательность гипотез

Исследователь не просто "запускает бектест". Он ведёт гипотезу через 7 уровней жёсткости:

```
1. Есть ли в данных lead-lag событие?          → Collector + анализ session
2. Видно ли его глазами?                        → Explorer
3. Можно ли формализовать как стратегию?        → JupyterLab
4. Выживает ли после fees/slippage/spread/BBO?  → Backtest
5. Устойчива ли по Monte Carlo?                 → Monte Carlo
6. Повторяется ли в realtime?                   → Paper Trading
7. Что улучшить?                               → Обратно в Notebook
```

**Каждый экран приложения = одно решение в этом процессе.** Если экран не помогает принять решение — он лишний или неправильно устроен.

### Что значит "принять исследовательское решение"

На каждом экране пользователь должен выйти с чётким ответом:
- **Collector**: "данные собираются нормально / нужно исправить venue X"
- **Quality**: "session пригодна / venue Y надо исключить из стратегии"
- **Explorer**: "паттерн виден, иду в ноутбук / паттерна нет, рано"
- **Strategies**: "стратегия валидна / вернуться в ноутбук, ошибка"
- **Backtest**: "Net PnL хороший / fees съедают всё / нужно улучшить логику входа"
- **Trade Inspector**: "сделка логична / ошибка в фильтре, улучшить в ноутбуке"
- **Monte Carlo**: "результат устойчив / слишком мало trades, нужно больше данных"
- **Paper**: "paper похож на backtest / есть execution drift, разбираемся"

Если пользователь не может сделать такой вывод — экран нужно улучшать.

### UX философия: минимализм power-user

**Модель**: Linear (issue tracker) — максимум полезного пространства, минимум декора.

- Каждый пиксель работает на исследование, не на красоту
- Клавиатурная навигация там где это естественно (стрелки по events в Explorer)
- Плотные данные предпочтительны пустому пространству
- Пользователь — эксперт, не нужны подсказки для очевидного
- НО: неочевидные исследовательские выводы должны быть явными (low-confidence warning, stale data)
- Декоративные анимации, большие пустые header-ы, marketing copy — не нужны

**Что НЕ трогать:**
- Никакой функциональности не удалять — только перегруппировывать и упрощать
- Бизнес-логику (backtest engine, Monte Carlo, strategy loader) — не трогать
- Данные и состояние — сохранять

---

## Приложение

**URL**: `https://vyv.ftp.sh/leadlag-lab/ui/dashboard.html`

**API base**: `http://localhost:8899` (app.js автоматически добавляет `/leadlag-lab/` prefix)

**UI файлы** — редактировать здесь:
```
/root/projects/leadlag-lab/leadlag/ui/
├── dashboard.html      ← Главный экран: состояние системы + быстрый старт
├── collector.html      ← Управление сбором данных
├── quality.html        ← Качество session перед анализом
├── explorer.html       ← Исследование lead-lag событий
├── strategy.html       ← Список стратегий + запуск backtest
├── backtest.html       ← Результаты backtest + trades
├── trade.html          ← Trade Inspector (отдельная сделка)
├── montecarlo.html     ← Monte Carlo robustness check
├── paper.html          ← Paper trading realtime
├── app.js              ← Shared: base path, API calls, navigation
└── style.css           ← Global styles
```

**Backend**: `/root/projects/leadlag-lab/leadlag/api/app.py`

**Данные**:
```
data/strategies/   ← .py файлы стратегий (из ноутбука через %%writefile)
data/sessions/     ← analyzed sessions
data/ticks/        ← raw parquet tick data (по датам)
data/bbo/          ← BBO parquet data (по датам)
```

**JupyterLab**: `https://vyv.ftp.sh/leadlag-lab/lab/`

---

## Текущее состояние данных

- **Session**: `20260417_121202_b8e21fab` — 30 мин, 22 events (7A/5B/10C), 11 venues
- **Strategies**: `baseline_signal_c`, `codex_manual_strategy_20260418`, `research_multi_signal_v1`
- **research_multi_signal_v1**: Signals A+B+C, Lighter Perp + MEXC Perp, min_magnitude 1.5 — даст больше trades когда накопятся данные
- **Collector**: работает, пишет файлы каждые 30 мин
- **Когда будет больше данных**: после 2+ часов → Dashboard → Run Analysis → новая session с 150+ events

---

## Приоритизированные доработки (из 09_MANUAL_TEST_REPORT)

### P1 — Мешает принять торговое решение

**[Backtest] Low sample warning**
- Проблема: 1 trade показывает зелёные KPI без предупреждения — выглядит как успех
- Нужно: banner "⚠️ Low sample: N trades. Results not statistically reliable." + CTA "Back to Notebook"
- Условие показа: `n_trades < 20`

**[Dashboard + Collector] Stale collector**
- Проблема: при `stale=true` venue metrics (ticks/s, BBO/s, idle) выглядят как живые данные
- Нужно: banner "Collector stopped / stale since [time]", приглушить live metrics, подпись "Last snapshot [age]"

**[Strategies] Нечитаемые действия**
- Проблема: кнопки `BT Paper Live`, символ ▶, `view`, `paper`, `×` — непонятны новому пользователю
- Нужно: явные текстовые кнопки "Run Backtest", "View Backtest", "Start Paper", "Delete"
- Добавить next-step hint per strategy

### P2 — Замедляет исследование

**[Explorer] Нет исследовательского CTA**
- После выбора события нет подсказки "что смотреть дальше"
- Нужно: decision strip под chart: "Follower: X | lag50: Yms | BBO: ok/wide | → Open Notebook"

**[Monte Carlo] Бессмысленные charts при N<20**
- При вырожденном распределении fan/distribution charts визуально странные
- Нужно: при `n_trades < 20` — warning prominent + charts muted/collapsed ("Show anyway")

**[Quality] Нет action hint**
- Venue summary показывает проценты без вывода — пользователь не знает что делать
- Нужно: label рядом с каждым venue: ✅ Safe / ⚠️ Low coverage / ❌ No BBO — exclude

### P3 — Polish

**Entry URL**: GET `/leadlag-lab/` должен redirect → `/leadlag-lab/ui/dashboard.html`

---

## Минимальный контракт стратегии

```python
from leadlag import Strategy, Order

class MyStrategy(Strategy):
    name = "strategy_id"        # = имя файла = имя ноутбука
    version = "2026-04-19"
    description = "..."
    params = { ... }

    def on_event(self, event, ctx) -> Order | None:
        # event.signal: 'A' | 'B' | 'C'
        # event.direction: +1 (up) | -1 (down)
        # event.magnitude_sigma: float
        # event.lagging_followers: list[str]
        # ctx.bbo: dict[venue, BboSnapshot]
        return Order(venue=..., side='buy'|'sell', qty_btc=0.001,
                     entry_type='market', hold_ms=30000)
```

---

## Как работать с браузером

Использовать **Playwright MCP** для всех взаимодействий с браузером:
- Проверять каждое изменение через браузер
- Делать скриншоты после каждого этапа
- Проверять console errors и failed requests
- Тестировать на desktop и tablet viewport

---

## Полные документы (если нужен полный контекст)

- `STRATEGY_DEVELOPMENT.md` — философия notebook-first, структура ноутбука, примеры
- `08_PHILOSOPHY_PIPELINE.md` — детальный пайплайн по шагам, чеклист скриншотов, definition of done
- `09_MANUAL_TEST_REPORT_2026-04-18.md` — полный отчёт ручного тестирования
