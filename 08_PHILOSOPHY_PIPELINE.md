# LeadLag Lab: Philosophy, Pipeline, Manual Testing

Дата: 2026-04-18

---

## 1. Философия проекта

LeadLag Lab — это лаборатория разработки и проверки lead-lag стратегий.

Главный принцип:

**Jupyter Notebook — лаборатория. Приложение — двигатель проверки.**

Стратегия создается в ноутбуке как настоящий Python-класс. Не YAML, не форма, не визуальный конструктор как основной путь. Исследователь должен иметь полную свободу Python: `pandas`, `numpy`, свои фильтры, индикаторы, вспомогательные функции, быстрые эксперименты.

После этого стратегия сохраняется в `.py` файл в `data/strategies/`. Этот файл становится источником истины. Приложение не переписывает стратегию и не переводит ее в другой формат. Оно загружает тот же самый Python-код и прогоняет его через тяжелые проверки: backtest, execution costs, Monte Carlo, trade inspection, paper trading.

Цель проекта — не просто нарисовать красивую equity curve. Цель — провести торговую гипотезу через последовательность все более жестких проверок:

1. Есть ли в данных lead-lag событие?
2. Видно ли его глазами в Explorer?
3. Можно ли формализовать его как стратегию?
4. Выживает ли стратегия после fees, slippage, spread, BBO и position rules?
5. Устойчива ли она по Monte Carlo?
6. Повторяется ли поведение в paper trading?
7. Что нужно улучшить в стратегии или в инструменте?

Приложение должно помогать принимать исследовательские решения. Оно не должно подменять лабораторию.

---

## 2. Рабочий пайплайн

### Шаг 1. Сбор данных

Экран: `Collector` или `Dashboard`

Задача:

Запустить сбор raw данных по выбранным venues, duration и rotation.

Ожидаемый результат:

- collector запущен;
- venues подключаются;
- ticks/BBO пишутся;
- видно ticks/s, BBO/s, reconnects, idle time;
- появляются parquet-файлы;
- нет явных dead/reconnecting проблем на нужных биржах.

Решение после шага:

- если данные собираются плохо, стратегия не создается;
- сначала исправляются venues, latency, gaps, BBO, coverage.

Примечание:

- `bin_size_ms` не относится к raw collection;
- размер бина выбирается позже, на этапе создания Analysis из Recording.

---

### Шаг 2. Анализ raw collection

Экран: `Dashboard` или `Collector`

Задача:

Запустить анализ последнего Recording.

Ожидаемый результат:

- создается Analysis;
- у Analysis есть events;
- есть counts по Signal A/B/C;
- Analysis открывается в Explorer.

Решение после шага:

- если events мало или они странные, нужно менять параметры анализа;
- если events есть, переходим к визуальному исследованию.

---

### Шаг 3. Исследование событий

Экран: `Explorer`

Задача:

Посмотреть реальные lead-lag события глазами.

Проверить:

- фильтры Signal A/B/C;
- direction UP/DOWN;
- magnitude;
- leader mode;
- follower filter;
- chart follower;
- BBO overlay;
- EMA baseline;
- follower table;
- lag_50 / lag_80;
- MFE / MAE;
- grid results;
- keyboard navigation.

Ожидаемый результат:

- видно, кто лидер;
- видно, какой follower запаздывает;
- видно, есть ли полезное окно входа;
- видно, не съедает ли идею spread/BBO;
- появляются идеи для условий стратегии.

Решение после шага:

- если визуально события неубедительны, стратегию писать рано;
- если паттерн виден, переходим в notebook.

---

### Шаг 4. Создание стратегии в Notebook

Экран: `JupyterLab`

Задача:

Создать или скопировать notebook для разработки стратегии.

Главное правило:

**Стратегия создается в notebook и сохраняется как Python-файл.**

Типовой процесс:

1. Открыть notebook разработки стратегии.
2. Загрузить Analysis через `load_session`.
3. Отфильтровать events.
4. Изучить статистику и отдельные events.
5. Написать Strategy class.
6. Сохранить стратегию в `data/strategies/<strategy_id>.py`.
7. Быстро проверить `load_strategy`.
8. Быстро проверить `on_event` на одном или нескольких событиях.

Минимальный контракт стратегии:

- `name`
- `version`
- `description`
- `params`
- `on_event(event, ctx)`

Стратегия должна возвращать `Order` или `None`.

Решение после шага:

- если стратегия не загружается, исправить notebook/file;
- если логика работает на отдельных событиях, перейти к полному backtest.

---

### Шаг 5. Управление стратегией

Экран: `Strategies`

Задача:

Убедиться, что сохраненная из notebook стратегия видна приложению.

Проверить:

- стратегия появилась в таблице;
- `valid = true`;
- видны `version`, `description`, `venues`, `signal`, `entry`, `slippage`, `position`;
- видна история последнего backtest, если он уже был;
- работает Run Backtest;
- работает View Backtest;
- работает Compare Selected для нескольких стратегий.

Ожидаемый результат:

- notebook-файл стал частью приложения;
- можно запускать тяжелые проверки без ручного кода.

Решение после шага:

- если стратегия невалидна, возвращаемся в notebook;
- если валидна, запускаем backtest.

---

### Шаг 6. Полный Backtest

Экран: `Backtests`

Задача:

Проверить стратегию на Analysis с учетом execution reality.

Проверить:

- Gross equity;
- Gross - Fees;
- Gross - Fees - Slippage;
- Net equity;
- drawdown;
- trades table;
- entry/exit prices;
- fees;
- slippage;
- spread;
- MFE/MAE;
- entry-to-MFE;
- exit reason;
- breakdown by signal;
- breakdown by venue;
- breakdown by entry type;
- breakdown by exit reason;
- breakdown by spread bucket.

Ожидаемый результат:

- понятно, зарабатывает ли стратегия до costs;
- понятно, что именно съедают fees/slippage;
- понятно, на каких venues/signals strategy работает;
- понятно, какие trades надо изучить руками.

Решение после шага:

- если Net плохой, вернуться в notebook и изменить логику;
- если Net хороший, открыть плохие и хорошие trades в Trade Inspector;
- если результат выглядит устойчивым, перейти к Monte Carlo.

---

### Шаг 7. Детальный просмотр сделок

Экран: `Trade Inspector`

Задача:

Понять, почему конкретная сделка дала profit/loss.

Проверить:

- leader/follower chart;
- entry line;
- exit line;
- BBO overlay;
- all followers overlay;
- MFE marker;
- MAE marker;
- SL/TP lines;
- exit reason;
- spread at entry/exit;
- fee/slippage source;
- link back to Explorer.

Ожидаемый результат:

- понятно, была ли сделка логичной;
- понятно, ошибка в стратегии или в данных;
- появляются идеи новых фильтров.

Решение после шага:

- если сделки визуально плохие, вернуться в notebook;
- если сделки выглядят логично, перейти к robustness проверке.

---

### Шаг 8. Monte Carlo

Экран: `Monte Carlo`

Задача:

Проверить устойчивость backtest результата.

Проверить:

- method;
- number of simulations;
- p-value;
- percentile;
- probability of profit;
- final PnL distribution;
- Sharpe distribution;
- Max DD distribution;
- warnings.

Ожидаемый результат:

- понятно, насколько результат похож на устойчивый эффект;
- понятно, не является ли equity случайной удачей.

Решение после шага:

- если robustness слабая, вернуться в notebook;
- если robustness приемлемая, можно запускать paper.

---

### Шаг 9. Paper Trading

Экран: `Paper`

Задача:

Запустить стратегию в paper mode и сравнить с backtest ожиданиями.

Проверить:

- strategy selected;
- status running/can trade;
- venue connectivity;
- live equity;
- recent signals;
- skipped signals;
- open positions;
- closed trades;
- paper stats;
- paper vs backtest overlay;
- drift between paper and backtest.

Ожидаемый результат:

- видно, повторяется ли логика стратегии в realtime;
- видно, есть ли проблемы с connectivity/BBO;
- видно, отличается ли execution от backtest.

Решение после шага:

- если paper хуже backtest, найти причину: data latency, spread, signal mismatch, slippage, bad filters;
- если paper похож на backtest, стратегия кандидат на следующую фазу.

---

## 3. План ручного тестирования по пайплайну

Этот план используется так:

1. Пользователь проходит шаг пайплайна руками.
2. Делает скриншот экрана.
3. Отправляет скриншот.
4. Мы вместе фиксируем:
   - что работает;
   - что мешает;
   - что непонятно;
   - какие доработки нужны;
   - приоритет доработок.

Работа всегда направлена на одну цель:

**создать стратегию в notebook и проверить ее до уровня, где понятно, стоит ли запускать paper trading.**

---

## 4. Чеклист скриншотов

### 4.1 Dashboard

Скриншоты:

- общий Dashboard;
- popup Start Collection;
- Collector Status block;
- Paper Trader block;
- Latest Analyses block;

Что оцениваем:

- понятно ли состояние системы;
- видно ли, что делать дальше;
- хватает ли информации без переходов по вкладкам.

---

### 4.2 Collector

Скриншоты:

- Control + Venue Selection;
- Live Monitor;
- Collector Log;
- Files.

Что оцениваем:

- удобно ли выбрать venues;
- видно ли проблемы подключения;
- достаточно ли ticks/s, BBO/s, idle, price, reconnects;
- понятно ли, можно ли запускать analysis.

---

### 4.3 Quality

Скриншоты:

- Venue Summary;
- Quality Charts;
- Coverage heatmap;
- Timeline gaps;
- BBO Analysis.

Что оцениваем:

- можно ли доверять Analysis;
- какие venues надо исключить;
- есть ли gaps;
- есть ли spread/BBO проблемы.

---

### 4.4 Explorer

Скриншоты:

- список events с фильтрами;
- chart одного Signal C;
- BBO overlay on/off;
- EMA baseline on/off;
- followers table;
- несколько хороших и плохих событий.

Что оцениваем:

- виден ли lead-lag паттерн;
- понятно ли, какой follower использовать;
- понятно ли, какие фильтры нужны в стратегии;
- удобно ли быстро просматривать события.

---

### 4.5 Notebook

Скриншоты:

- загрузка Analysis;
- фильтрация events;
- stats/grid search;
- ячейка Strategy class;
- сохранение `.py`;
- `load_strategy`;
- быстрый вызов `on_event`.

Что оцениваем:

- удобно ли создавать стратегию;
- не мешает ли notebook workflow;
- понятно ли, как стратегия попадает в приложение;
- хватает ли helper API.

---

### 4.6 Strategies

Скриншоты:

- таблица стратегий;
- валидная новая стратегия;
- Run Backtest;
- last backtest summary;
- Compare Selected;
- Simple Strategy Creator, если используется как scaffold.

Что оцениваем:

- видна ли стратегия из notebook;
- понятно ли, что было протестировано;
- удобно ли сравнивать версии;
- не подменяет ли UI notebook-разработку.

---

### 4.7 Backtest

Скриншоты:

- header/meta;
- KPI cards;
- equity layers;
- distributions;
- breakdowns;
- trades table;
- фильтры trades.

Что оцениваем:

- можно ли принять решение по стратегии;
- видно ли влияние fees/slippage;
- понятно ли, где стратегия работает и где ломается;
- какие trades надо открыть в инспекторе.

---

### 4.8 Trade Inspector

Скриншоты:

- profitable trade;
- losing trade;
- BBO overlay;
- all followers overlay;
- SL/TP lines, если заданы;
- metrics sidebar;
- View in Explorer.

Что оцениваем:

- объяснима ли сделка;
- понятно ли, была ли ошибка стратегии;
- какие новые условия добавить в notebook.

---

### 4.9 Monte Carlo

Скриншоты:

- settings;
- equity fan;
- distributions;
- p-value/percentile/probability cards;
- warnings.

Что оцениваем:

- выглядит ли стратегия устойчивой;
- достаточно ли trades;
- можно ли переходить к paper.

---

### 4.10 Paper

Скриншоты:

- status cards;
- venue connectivity;
- live equity;
- recent signals;
- open positions;
- closed trades;
- paper stats;
- paper vs backtest.

Что оцениваем:

- повторяется ли backtest в realtime;
- есть ли execution drift;
- какие сигналы skipped и почему;
- что менять в стратегии.

---

## 5. Формат плана доработок после скриншотов

После каждого набора скриншотов формируем список:

```text
Screen:
Problem:
Why it matters for strategy development:
Expected behavior:
Proposed fix:
Priority: P0/P1/P2/P3
```

Приоритеты:

- `P0` — рвет пайплайн создания/тестирования стратегии.
- `P1` — мешает принять торговое решение.
- `P2` — замедляет исследование.
- `P3` — polish, визуальная ясность, удобство.

---

## 6. Definition of Done

Проект считается доведенным до нужного рабочего состояния, когда пользователь может:

1. Собрать данные.
2. Проанализировать Recording.
3. Найти паттерн в Explorer.
4. Создать стратегию в notebook.
5. Сохранить стратегию как `.py`.
6. Увидеть стратегию в UI.
7. Запустить backtest.
8. Разобрать сделки.
9. Проверить Monte Carlo.
10. Запустить paper.
11. Сравнить paper с backtest.
12. Вернуться в notebook и улучшить стратегию.

Главный критерий:

**каждый экран должен помогать создать, проверить или улучшить стратегию.**
