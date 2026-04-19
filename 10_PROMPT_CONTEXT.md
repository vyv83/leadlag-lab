# LeadLag Lab — Контекст для UX Prompt (doc #10)

> Связанные документы: 08_PHILOSOPHY_PIPELINE.md, 09_MANUAL_TEST_REPORT_2026-04-18.md, STRATEGY_DEVELOPMENT.md

---

## ФИЛОСОФИЯ ПРОЕКТА (читать внимательно — это основа всех решений)

### Суть

LeadLag Lab — это **исследовательская лаборатория**, а не торговый терминал и не no-code конструктор.

Пользователь — **исследователь/quantitative analyst**, который выдвигает гипотезу о lead-lag эффекте между криптобиржами и проверяет её через последовательность всё более жёстких испытаний. Его инструмент — **Python + Jupyter**. Приложение — это **двигатель проверки**, а не замена ноутбуку.

### Почему Jupyter — главное

Стратегия — это **Python класс**. Не YAML конфиг. Не форма с полями. Не визуальный drag-and-drop конструктор. Исследователь пишет настоящий код: импортирует pandas, numpy, scipy, определяет вспомогательные функции, считает кастомные индикаторы (EMA, VWAP, BBO spread), применяет сложную условную логику.

Ноутбук — место итерации: изменил → запустил ячейку → увидел результат за секунды.

**Что НЕЛЬЗЯ делать приложению:**
- Предлагать визуальный конструктор вместо ноутбука
- Дублировать тяжёлые вычисления (backtest, Monte Carlo) в ноутбуке
- Предлагать YAML/JSON конфиги как замену Python классу
- Скрывать сложность — исследователь хочет реальные числа, не упрощения

### Файл .py — единственный источник истины

```
notebooks/lighter_c_bbo_v2.ipynb  →  %%writefile  →  data/strategies/lighter_c_bbo_v2.py
                                                              ↓
                                                    Приложение загружает этот же файл
```

Один идентификатор везде: имя ноутбука = имя файла = ID стратегии.

Workflow ноутбука (уже работает корректно в strategy_dev.ipynb):
1. Копируешь `strategy_dev.ipynb` → переименовываешь (`lighter_c_bbo_v2.ipynb`)
2. Запускаешь — `get_notebook_name()` читает имя файла → `STRATEGY_NAME = "lighter_c_bbo_v2"`
3. Ячейка с `%%writefile ../data/strategies/{STRATEGY_NAME}.py` (ПЕРВАЯ строка ячейки) — пишешь стратегию
4. Запускаешь → файл создан, стратегия видна в приложении автоматически

### Пайплайн — 7 уровней проверки гипотезы

Исследователь не просто "запускает бектест". Он ведёт гипотезу через нарастающую жёсткость:

```
1. Есть ли в данных lead-lag событие?          → Collector + анализ session
2. Видно ли его глазами?                        → Explorer
3. Можно ли формализовать как стратегию?        → JupyterLab
4. Выживает ли после fees/slippage/spread/BBO?  → Backtest
5. Устойчива ли по Monte Carlo?                 → Monte Carlo
6. Повторяется ли в realtime?                   → Paper Trading
7. Что улучшить?                               → Обратно в Notebook
```

**Каждый экран = одно решение.** Если экран не помогает принять решение — он неправильно устроен.

### Решение на каждом экране

- **Collector**: "данные собираются нормально / нужно исправить venue X"
- **Quality**: "session пригодна / venue Y надо исключить из стратегии"
- **Explorer**: "паттерн виден, иду в ноутбук / паттерна нет, рано"
- **Strategies**: "стратегия валидна / вернуться в ноутбук, ошибка"
- **Backtest**: "Net PnL хороший / fees съедают всё / нужно улучшить логику входа"
- **Trade Inspector**: "сделка логична / ошибка в фильтре, улучшить в ноутбуке"
- **Monte Carlo**: "результат устойчив / слишком мало trades, нужно больше данных"
- **Paper**: "paper похож на backtest / есть execution drift, разбираемся"

### UX: минимализм power-user (модель — Linear)

- Максимум полезного пространства, минимум декора
- Плотные данные лучше пустого пространства
- Клавиатурная навигация там где естественно (Explorer: стрелки по events)
- Пользователь — эксперт, не нужны подсказки для очевидного
- НО: неочевидные выводы должны быть явными (low-confidence, stale data, action hints)
- Никаких декоративных анимаций, больших пустых header-ов, marketing copy

---

## Приложение

**URL**: `https://vyv.ftp.sh/leadlag-lab/ui/dashboard.html`

**API base**: `http://localhost:8899` (app.js автоматически добавляет prefix)

**UI файлы** — редактировать здесь:
```
/root/projects/leadlag-lab/leadlag/ui/
├── dashboard.html      ← состояние системы + быстрый старт
├── collector.html      ← управление сбором данных
├── quality.html        ← качество session перед анализом
├── explorer.html       ← исследование lead-lag событий
├── strategy.html       ← список стратегий + запуск backtest
├── backtest.html       ← результаты backtest + trades
├── trade.html          ← Trade Inspector (отдельная сделка)
├── montecarlo.html     ← Monte Carlo robustness check
├── paper.html          ← Paper trading realtime
├── app.js              ← Shared: base path, API calls, navigation
└── style.css           ← Global styles
```

**Backend**: `/root/projects/leadlag-lab/leadlag/api/app.py`

**JupyterLab**: `https://vyv.ftp.sh/leadlag-lab/lab/`

---

## Текущее состояние данных

- **Session**: `20260417_121202_b8e21fab` — 30 мин, 22 events (7A/5B/10C)
- **Strategies**: `baseline_signal_c`, `codex_manual_strategy_20260418`, `research_multi_signal_v1`
- **research_multi_signal_v1**: Signals A+B+C, Lighter Perp + MEXC Perp, min_magnitude 1.5
- **Collector**: работает, накапливает данные (rotation 30 мин)

---

## Что уже сделано (не переделывать)

Исправлено в предыдущей сессии на основе 09_MANUAL_TEST_REPORT:
- **backtest.html**: banner "Low-sample: < 20 trades" с CTA → Explorer
- **dashboard.html**: banner "Collector stopped — last snapshot (X old)" при `stale=true`, таблица venues получает класс `stale-table`
- **strategy.html**: кнопки переименованы в "Run backtest", "View backtest", "Start paper", "Delete"
- **quality.html**: колонка recommendation с action hints (safe/caution/exclude)
- **montecarlo.html**: charts dim (opacity 0.35, pointer-events none) при `n_trades_lt_20_monte_carlo_is_low_confidence`
- **explorer.html**: decision strip добавлен
- **strategy_dev.ipynb**: восстановлен %%writefile workflow (разбит на 2 ячейки)

---

## Что ещё нужно сделать (актуальные задачи)

Провести полный UX audit и улучшить всё приложение согласно философии выше.
Использовать результаты визуального тестирования (Playwright MCP) для проверки каждого экрана.

Приоритеты для аудита:
- Проверить что уже сделанные исправления работают корректно визуально
- Найти дублирующийся функционал между экранами
- Проверить единство user flow: каждый экран ведёт к следующему шагу пайплайна
- Проверить что на каждом экране есть чёткий ответ на исследовательский вопрос

Оставшееся из отчёта:
- **P3**: GET `/leadlag-lab/` → redirect на `/leadlag-lab/ui/dashboard.html`
- **P2**: Explorer — проверить что decision strip реально работает и понятен
- **P2**: Monte Carlo — проверить что muted charts выглядят правильно
- **P2**: Quality — проверить что recommendation column понятна

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
        # event.direction: +1 | -1
        # event.magnitude_sigma: float
        # event.lagging_followers: list[str]
        return Order(venue=..., side='buy'|'sell', qty_btc=0.001,
                     entry_type='market', hold_ms=30000)
```

---

## Полные документы

- `STRATEGY_DEVELOPMENT.md` — философия notebook-first, структура ноутбука, примеры
- `08_PHILOSOPHY_PIPELINE.md` — детальный пайплайн по шагам, definition of done
- `09_MANUAL_TEST_REPORT_2026-04-18.md` — полный отчёт с findings и скриншотами
