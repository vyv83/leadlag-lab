# Философия и реализация разработки стратегий

## Философия

### Ноутбук — лаборатория, приложение — двигатель

Фундаментальный принцип: **Jupyter ноутбук — это главный инструмент для исследования и создания стратегий. Приложение вторично — оно потребляет то, что создаёт ноутбук.**

#### Почему такая архитектура?

1. **Гибкость в исследовании**
   - Разработка стратегии требует экспериментов: пробуем разные фильтры, индикаторы, параметры, условия входа/выхода
   - Ноутбук даёт мгновенную обратную связь и визуализацию
   - Исследователь может добавлять произвольный Python код (EMA, кастомные индикаторы, доменная логика) без ограничений
   - Цикл итерации быстрый: изменил код → запустил ячейку → увидел результат

2. **Код настоящий, не конфигурация**
   - Стратегия — это **Python класс**, не YAML конфиг и не текстовый шаблон
   - Исследователь может:
     - Импортировать библиотеки (numpy, pandas, scipy, кастомные модули)
     - Определять вспомогательные методы (вычисление индикаторов, применение фильтров)
     - Использовать условную логику, циклы, вложенные функции
     - Тестировать пошагово в ноутбуке
   - Точно такой же код работает в приложении — никакого перевода

3. **Файл — источник истины**
   - Когда стратегия определена и сохранена, `.py` файл — это каноническая версия
   - И ноутбук и приложение загружают из одного файла
   - Нет дублирования, нет проблем синхронизации, нет расхождений
   - История сохраняется: `lighter_c_bbo.py`, `lighter_c_bbo_v2.py`, `lighter_c_bbo_v3.py`

4. **Ноутбук остаётся чистым**
   - Ноутбук только для **разработки стратегии**, не для тяжёлых вычислений
   - Никакого полного бектеста в ноутбуке (это медленно и должно быть в приложении)
   - Никакого Monte Carlo в ноутбуке (это в приложении)
   - Ноутбук сфокусирован на: загрузка данных → написание стратегии → быстрая проверка логики

5. **Приложение оптимизировано для анализа**
   - Приложение имеет полный бектест энджин со скольжением, комиссиями, управлением позициями
   - Приложение показывает сделки, кривую капитала, просадку, распределение Monte Carlo
   - Приложение предоставляет веб интерфейс для интерактивного исследования
   - Исследователь копирует имя стратегии в приложение, нажимает "бектест", получает полный анализ

---

## Реализация

### Структура файлов

```
notebooks/
├── strategy_dev.ipynb          # Шаблон — копируй это чтобы создать новые стратегии
├── lighter_c_bbo.ipynb         # Стратегия v1 → data/strategies/lighter_c_bbo.py
├── lighter_c_bbo_v2.ipynb      # Стратегия v2 → data/strategies/lighter_c_bbo_v2.py
└── lighter_c_spread.ipynb      # Другая стратегия → data/strategies/lighter_c_spread.py

data/strategies/
├── lighter_c_bbo.py            # Стратегия lighter_c_bbo
├── lighter_c_bbo_v2.py         # Стратегия lighter_c_bbo_v2
└── lighter_c_spread.py         # Стратегия lighter_c_spread
```

**Один идентификатор везде:**
- Имя ноутбука: `lighter_c_bbo_v2.ipynb`
- Имя файла: `lighter_c_bbo_v2.py`
- ID стратегии: `lighter_c_bbo_v2`

---

## Структура ноутбука

```
Ячейка 1: Markdown — описание
Ячейка 2: Импорты + Загрузить данные
Ячейка 3: Определение стратегии (%%writefile)
Ячейка 4+: Тесты и экспериментирование
```

---

## Пошаговый пример

### Ячейка 1: Описание

```markdown
# Лаборатория разработки стратегий

Скопируй этот ноутбук, переименуй его (например lighter_c_bbo_v2.ipynb) и развивай свою стратегию.
```

### Ячейка 2: Импорты + Загрузить данные

```python
import json
from pathlib import Path
import os
import numpy as np
import pandas as pd
from leadlag import list_analyses, load_analysis, Strategy, Order, Context, Event, BboSnapshot

DATA = '../data'
analyses = list_analyses(DATA)
analysis = load_analysis(analyses[0]['id'], data_dir=DATA)
events = analysis.events.filter(signal='C')

print(f"Загружена: {analysis.analysis_id}")
print(f"События: {events.count}")
```

### Ячейка 3: Определение стратегии

Сначала получаем имя ноутбука:

```python
def get_notebook_name():
    """Получить имя текущего ноутбука из файла сессии ядра Jupyter"""
    runtime_dir = Path(os.environ.get('JUPYTER_RUNTIME_DIR', '~/.jupyter/runtime')).expanduser()
    for session_file in runtime_dir.glob('kernel-*.json'):
        try:
            session_data = json.loads(session_file.read_text())
            jupyter_session = session_data.get('jupyter_session', '')
            if jupyter_session and '.ipynb' in jupyter_session:
                return Path(jupyter_session).stem
        except:
            pass
    return "strategy"

STRATEGY_NAME = get_notebook_name()
print(f"Стратегия: {STRATEGY_NAME}")
```

Потом определяем стратегию и сохраняем в файл:

```python
%%writefile ../data/strategies/{STRATEGY_NAME}.py
from leadlag import Strategy, Order

class MyStrategy(Strategy):
    version = "2026-04-18"
    
    params = {
        "signal": "C",
        "follower": "Lighter Perp",
        "min_magnitude": 2.0,
        "hold_ms": 30000,
    }

    def on_event(self, event, ctx):
        """Основная логика стратегии"""
        p = self.params
        
        if event.signal != p["signal"]:
            return None
        if p["follower"] not in event.lagging_followers:
            return None
        if event.magnitude_sigma < p["min_magnitude"]:
            return None
        
        return Order(
            venue=p["follower"],
            side="buy" if event.direction > 0 else "sell",
            qty_btc=0.001,
            entry_type="market",
            hold_ms=p["hold_ms"],
        )
```

**Как это работает:**
1. `get_notebook_name()` читает имя текущего ноутбука из файла сессии Jupyter
2. `STRATEGY_NAME` получает значение (например `lighter_c_bbo_v2`)
3. `%%writefile` сохраняет ячейку в файл `data/strategies/lighter_c_bbo_v2.py`
4. Когда ты редактируешь и перезапускаешь ячейку, файл обновляется автоматически

### Ячейка 4: Быстрый тест

```python
from leadlag import load_strategy

# Загружаем стратегию
strat = load_strategy(f'../data/strategies/{STRATEGY_NAME}.py')
print(f"Загружена: {STRATEGY_NAME}")

# Создаём mock событие
event = Event(
    bin_idx=0, ts_ms=0, signal='C', direction=1,
    magnitude_sigma=3.0, leader='OKX Perp', lagging_followers=['Lighter Perp']
)
ctx = Context(ts_ms=0, bbo={'Lighter Perp': BboSnapshot('Lighter Perp', spread_bps=1.5)})

# Вызываем стратегию
order = strat.on_event(event, ctx)
print(f"Ордер: {order}")
```

### Ячейка 5: Экспериментирование

```python
# Меняем параметры и проверяем
strat.params['min_magnitude'] = 5.0
order = strat.on_event(event, ctx)
print(f"С жёстким фильтром: {order}")

# Восстанавливаем
strat.params['min_magnitude'] = 2.0
```

---

## Полный пример со своим индикатором

### Ячейка 3: Стратегия с EMA

```python
%%writefile ../data/strategies/{STRATEGY_NAME}.py
import pandas as pd
from leadlag import Strategy, Order

class MyStrategy(Strategy):
    version = "2026-04-18"
    
    params = {
        "signal": "C",
        "follower": "Lighter Perp",
        "min_magnitude": 2.0,
        "hold_ms": 30000,
        "ema_span": 20,
    }

    def compute_ema(self, prices, span):
        """Инициализация: вычисляем EMA"""
        return pd.Series(prices).ewm(span=span).mean().values

    def on_event(self, event, ctx):
        """Реализация: логика стратегии с EMA"""
        p = self.params
        
        # Базовые проверки
        if event.signal != p["signal"]:
            return None
        if p["follower"] not in event.lagging_followers:
            return None
        if event.magnitude_sigma < p["min_magnitude"]:
            return None
        
        # Дополнительная проверка через EMA
        # В реальности prices были бы из ctx или session
        test_prices = [100, 101, 102, 101, 103, 104, 103, 105, 106, 105]
        ema = self.compute_ema(test_prices, span=p["ema_span"])
        current_price = test_prices[-1]
        ema_value = ema[-1]
        
        # Проверяем условие
        if current_price < ema_value:
            return None
        
        return Order(
            venue=p["follower"],
            side="buy" if event.direction > 0 else "sell",
            qty_btc=0.001,
            entry_type="market",
            hold_ms=p["hold_ms"],
        )
```

### Ячейка 4: Тестирование индикатора

```python
strat = load_strategy(f'../data/strategies/{STRATEGY_NAME}.py')

# Тестовые цены
prices = [100, 101, 102, 101, 103, 104, 103, 105, 106, 105]

# Вызов: вычисляем EMA
ema = strat.compute_ema(prices, span=3)

print(f"Цены: {prices}")
print(f"EMA:  {list(ema)}")

# Результат:
# Цены: [100, 101, 102, 101, 103, 104, 103, 105, 106, 105]
# EMA:  [100.0, 100.5, 101.17, 101.09, 102.02, 103.01, 103.01, 104.0, 105.0, 105.0]
```

### Ячейка 5: Экспериментирование с параметрами

```python
# Пробуем разные span значения
strat.params['ema_span'] = 5
ema_5 = strat.compute_ema(prices, span=5)
print(f"EMA span=5:  {list(ema_5)}")

strat.params['ema_span'] = 10
ema_10 = strat.compute_ema(prices, span=10)
print(f"EMA span=10: {list(ema_10)}")
```

---

## Рабочий процесс

### Шаг 1: Копируешь шаблон
```bash
cp notebooks/strategy_dev.ipynb notebooks/lighter_c_bbo_v2.ipynb
```

### Шаг 2: Открываешь в JupyterLab
```
Открываешь lighter_c_bbo_v2.ipynb
```

### Шаг 3: Запускаешь ячейки
- Ячейка 2: загружаешь данные
- Ячейка 3: автоматически создаёшь файл `data/strategies/lighter_c_bbo_v2.py`
- Ячейка 4+: тестируешь логику

### Шаг 4: Итерируешь
- Редактируешь Ячейку 3: добавляешь фильтры, индикаторы
- Запускаешь Ячейку 3: файл обновляется
- Запускаешь Ячейку 4+: проверяешь результаты
- Повторяешь пока логика тебя не устроит

### Шаг 5: В приложении
1. Открываешь дашборд → Стратегии
2. Видишь `lighter_c_bbo_v2` в списке
3. Нажимаешь "Бектест"
4. Приложение запускает полный бектест, Monte Carlo, показывает результаты

---

## Ключевые принципы

1. **Один идентификатор везде**
   - Имя ноутбука = имя файла = ID стратегии
   - Никаких дублирования, никаких несоответствий

2. **Ноутбук — единственный источник**
   - Определяешь стратегию в ноутбуке через `%%writefile`
   - Приложение загружает готовый файл
   - Никакого обратного инжиниринга

3. **Класс самодостаточен**
   - Все импорты в начале файла
   - Вся логика внутри класса или его методов
   - Нет внешнего состояния

4. **Параметры управляют поведением**
   - Всё что может меняться — в `params` словаре
   - Логика использует `self.params`
   - Не нужно редактировать код для разных значений

5. **Тесты быстрые**
   - Ноутбук для проверки логики (100ms)
   - Приложение для полного бектеста (минуты)

6. **Приложение оптимизировано**
   - Реалистичный бектест со скольжением и комиссиями
   - Monte Carlo, графики, детальный анализ
   - Можно запускать несколько стратегий параллельно

---

## Почему этот дизайн?

**Проблема:** Текстовые шаблоны и дублирование кода
- Нельзя использовать импорты
- Нельзя вызывать функции библиотек
- Файл и ноутбук расходятся
- Лишние идентификаторы

**Решение:** Один источник истины
- Стратегия — это настоящий Python класс
- Ноутбук и приложение загружают один файл
- Имя автоматически из ноутбука
- Никаких дублирования и синхронизации

---

## Резюме

**Ноутбук — это твоя лаборатория.** Ты пишешь настоящий Python код, тестируешь пошагово, итерируешь быстро. Когда логика готова, ты сохраняешь её через `%%writefile`. Файл автоматически получает имя и становится доступен приложению.

Никаких шаблонов, никаких строк, никакого ручного именования. Просто настоящий код от исследования в продакшен.
