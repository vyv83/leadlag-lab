# LeadLag Lab — Menu Controls Blueprint (doc #17)

> Статус: draft for iterative review
> Цель: договориться о контролсах меню до HTML-прототипа
> Этот документ не описывает backend-реализацию и не вводит новые сущности

---

## 1. Source of Truth

Этот blueprint опирается только на текущий проект:

- [README.md](README.md) — актуальный operational state
- [PROGRESS_PHASE2.md](PROGRESS_PHASE2.md) — актуальный status tree-sidebar rollout
- [REVIEW_PHASE2.md](REVIEW_PHASE2.md) — corrective review по Phase 2
- [13_ARCHITECTURE_DECISIONS.md](13_ARCHITECTURE_DECISIONS.md) — rename и UX-правила
- [15_PIPELINE_AUDIT.md](15_PIPELINE_AUDIT.md) — полный user pipeline и тупики
- [16_DOMAIN_MODEL.md](16_DOMAIN_MODEL.md) — сущности, ownership и canonical menu shape

Визуальные референсы:

- `image copy.png` — вдохновение для entity tree, menu grouping, action rail
- `image.png` — вдохновение для плотности, detail panel, summary cards, чистой sidebar/detail-композиции
- [23_MENU_CONTROLS_CATALOG.html](23_MENU_CONTROLS_CATALOG.html) — живой HTML-каталог control families и visual hierarchy

---

## 2. Hard Rules

### 2.1. Терминология

Публичные UX/API термины:

- `Recording`
- `Analysis`

Не возвращаем в публичный UX термины:

- `Session`
- `Collection`

### 2.2. Operational reality

Меню не должно создавать ложную картину архитектуры.

Поэтому:

- `collector` в `leadlag-lab` не отдельный systemd unit в меню;
- это runtime subprocess, стартуемый из API;
- systemd-level мышление допустимо только для `leadlag-lab`, `leadlag-monitor`, `leadlag-lab-jupyter` как operational context, но не как основа menu UX.

### 2.3. Domain-first

Меню строится вокруг сущностей и pipeline, а не вокруг произвольных страниц.

Страницы остаются surface для деталей:

- `Quality`
- `Explorer`
- `Strategy`
- `Backtest`
- `Monte Carlo`
- `Paper`
- `Trade`

Но сама структура меню должна следовать ownership из [16_DOMAIN_MODEL.md](16_DOMAIN_MODEL.md).

### 2.4. No fake power

Не добавляем контролсы, для которых нет проектной опоры в docs или текущем UX направлении.

Примеры того, чего сейчас не надо придумывать:

- drag-and-drop reorder
- arbitrary pin/favorite system
- bulk multi-select flows
- hidden command palette as main interaction model
- complex right-click menu as обязательный path

---

## 3. What Menu Must Do

Меню должно помогать пользователю пройти реальный pipeline:

1. Понять, жив ли runtime и collector.
2. Увидеть новые recordings.
3. Создать analysis из recording.
4. Перейти в `Quality` и `Explorer`.
5. Найти или открыть strategy.
6. Запустить backtest.
7. Перейти к Monte Carlo.
8. Перейти к Paper.
9. Удалять сущности без модалок, inline-confirm style.

Меню не должно пытаться заменить собой detail pages.

---

## 4. Core Menu Zones

Основа берётся из [16_DOMAIN_MODEL.md](16_DOMAIN_MODEL.md), но адаптируется под текущий продуктовый pipeline.

### 4.1. Top-Level Zones

```text
Dashboard
Collector
Recordings
Strategies
Jupyter
```

Почему именно так:

- `Dashboard` — operational landing
- `Collector` — старт pipeline
- `Recordings` — data -> analysis branch
- `Strategies` — research -> execution branch
- `Jupyter` — внешний, но центральный workbench

### 4.2. Что не выносим в top-level

Не делаем top-level пунктами:

- `Quality`
- `Explorer`
- `Backtests (All)`
- `Monte Carlo (All)`
- `Paper (All)`
- `Trades`

Причина:

- это либо page/view surfaces,
- либо производные сущности,
- либо secondary navigation.

Если глобальные срезы понадобятся позже, они могут появиться как secondary utility layer, но не как базовый skeleton первого prototype.

---

## 5. Menu Control Families

Ниже перечислены не конкретные кнопки одной страницы, а типы контролсов, которые допустимы в меню.

### 5.1. Structural Controls

#### A. Expand / Collapse

Назначение:

- открыть дочерние сущности
- закрыть длинные ветки

Применение:

- `Collector`
- `Recording`
- `Analysis`
- `Strategy`
- `Backtest`
- `Paper Run`

Не применять:

- для одношаговых page links без children

#### B. Node Navigate

Назначение:

- открыть detail page или релевантный view

Применение:

- click по label node
- отдельная зона label, не конфликтующая с action buttons

Правило:

- label ведёт в canonical detail/view
- expand control не должен ломать navigation

### 5.2. Status Controls

#### C. Status Badge

Назначение:

- быстро показать runtime или health state

Допустимые состояния из проекта:

- `LIVE`
- `running`
- `idle`
- `nb✓`
- `nb⚠`
- `low sample`
- `MC`

Правило:

- badge сообщает state, но не заменяет основное действие

#### D. Count / Summary Chip

Назначение:

- показать число дочерних сущностей или короткий KPI

Примеры:

- `12`
- `3 analyses`
- `24 trades`
- `2.4k ev/s`

Правило:

- чип короткий
- не превращается в вторую строку метрик-таблицы

### 5.3. Action Controls

#### E. Primary Inline Action

Назначение:

- действие, которое двигает pipeline вперёд

Разрешённые типы:

- `Analyze`
- `Run BT`
- `Run MC`
- `Start Paper`
- `Open Jupyter`
- `Refresh`

Правило:

- не более 1 primary action на node-row
- если действий больше, остальные уходят в detail view или overflow

#### F. Context Link

Назначение:

- быстрый переход в релевантный специальный экран

Разрешённые типы:

- `Quality`
- `Explorer`
- `View`
- `Open Notebook`

Правило:

- context links особенно уместны для `Analysis`
- эти ссылки не меняют ownership tree

#### G. Overflow / More

Назначение:

- редкие или вторичные действия

Применение:

- три точки `...`
- вторичный слой действий

Только если реально нужен.
На первом prototype лучше минимизировать.

#### H. Danger Trigger

Назначение:

- инициировать delete flow

Правило из проекта:

- не modal
- не browser confirm
- дальше должен открываться inline confirmation strip

Меню может содержать только trigger:

- `Delete`
- `×`
- trash icon

Сама полная confirmation UI может жить в detail zone или разворачиваться inline под node.

---

## 6. Entity-by-Entity Control Map

Это главная часть документа: какие контролсы допустимы для каждой сущности.

### 6.1. Dashboard

Роль:

- landing point
- системная обзорная точка

Контролсы в меню:

- `Navigate`
- optional `active` highlight

Не нужно:

- row actions
- delete
- status overload

### 6.2. Collector

Роль:

- начало pipeline
- runtime surface

Контролсы:

- `Navigate`
- `Expand/Collapse`
- `LIVE/running/idle badge`
- compact summary chip: venues count or event rate
- optional `Refresh`

Не нужно прямо в меню первого prototype:

- `Start`
- `Stop`
- per-venue toggles

Почему:

- эти действия лучше остаются на `collector.html`
- иначе row перегрузится и будет путаница между runtime state и configuration

### 6.3. Recording

Роль:

- контейнер raw market data
- точка входа в analyses

Контролсы:

- `Expand/Collapse`
- `Navigate`
- summary line: date/time, duration, venue count, events size summary
- primary action: `Analyze`
- optional danger trigger: `Delete`

Важно:

- `Analyze` — ключевой pipeline action, его надо сделать заметным
- именно `Recording` должен visibly подталкивать пользователя к созданию `Analysis`

### 6.4. Analysis

Роль:

- главный исследовательский узел после recording

Контролсы:

- `Navigate`
- `Status badge` если нужен: `low sample`
- summary chip: events count
- context links: `Quality`, `Explorer`
- primary action: `Run BT`
- optional danger trigger: `Delete`

Правило:

- `Quality` и `Explorer` должны быть быстрыми и очевидными
- `Run BT` допустим прямо из analysis-row, потому что это зафиксировано в pipeline-аудите

### 6.5. Strategy

Роль:

- исследовательский артефакт пользователя
- владелец backtests и paper runs в tree ownership

Контролсы:

- `Expand/Collapse`
- `Navigate`
- notebook badge: `nb✓` или `nb⚠`
- primary action: `Open Notebook` или `Run BT`
- optional secondary action: `Start Paper`
- optional danger trigger: `Delete`

Замечание:

- у strategy потенциально много действий;
- поэтому на первом prototype надо выбрать один главный CTA для row и не пытаться уместить всё сразу.

Предлагаемый приоритет:

1. `Run BT`
2. `Open Notebook`
3. `Start Paper`
4. `Delete`

### 6.6. Backtest

Роль:

- результат прогона стратегии на analysis

Контролсы:

- `Expand/Collapse` если под ним показываем `Monte Carlo`
- `Navigate`
- summary metrics: trades, pnl, sharpe
- status chip: `MC` если MC уже есть
- primary action: `Run MC`
- optional context link: `View`
- optional danger trigger: `Delete`

Правило:

- `Backtest` должен явно показывать связь с quality результата, а не просто id

### 6.7. Monte Carlo

Роль:

- validation step после backtest

Контролсы:

- `Navigate`
- compact summary: runs count, p-value or robustness metric
- primary action: `Start Paper` только если это реально выбранный CTA уровня node
- optional danger trigger: `Delete`

Ограничение:

- не перегружать row статистикой;
- MC detail всё равно живёт на своей странице.

### 6.8. Paper Run

Роль:

- operational live-ish execution branch

Контролсы:

- `Navigate`
- status badge: `LIVE` or `running`
- compact summary: trades, uptime
- primary action: `View`
- optional secondary action: `Stop`
- optional danger trigger: `Delete`

Замечание:

- `Stop` важен, но опасен по визуальному весу;
- в первом prototype его надо показать аккуратно, без превращения строки в control panel.

### 6.9. Jupyter

Роль:

- внешний workbench

Контролсы:

- `Navigate/Open`
- внешний link affordance

Не нужно:

- expand tree
- delete
- runtime badges

---

## 7. Control Priority Rules

Чтобы меню не превратилось в noisy action table, нужны жёсткие ограничения.

### 7.1. Per Row Limit

На одной строке node допустимо одновременно показывать:

- 1 structural affordance
- 1 main label area
- 1 short state badge
- 1 short summary chip
- 1 primary action
- 1 danger trigger

Всё остальное:

- во вторую строку,
- в expanded content,
- или на detail page.

### 7.2. Action Hierarchy

Порядок важности:

1. Navigate
2. Primary pipeline action
3. State visibility
4. Danger trigger
5. Secondary actions

Если строка перегружена, secondary actions удаляются первыми.

### 7.3. No action soup

Нельзя делать строки вида:

`Quality | Explorer | Run BT | Run MC | Start Paper | Open | Compare | Delete`

Это ломает читаемость и убивает tree nature.

---

## 8. Recommended First-Prototype Shape

Это не финальный UI, а рекомендуемая starting point композиция для standalone HTML.

### 8.1. Recording branch

```text
Recordings
  Recording
    [Analyze]
    Analysis
      [Quality] [Explorer] [Run BT] [Delete]
```

### 8.2. Strategy branch

```text
Strategies
  Strategy [nb✓]
    [Run BT] [Open Notebook] [Delete]
    Backtest [MC]
      [Run MC] [View] [Delete]
      Monte Carlo
        [Start Paper] [Delete]
    Paper Run [LIVE]
      [View] [Stop] [Delete]
```

### 8.3. Collector branch

```text
Collector [LIVE]
  summary: venues / event-rate
```

Collector branch на первом prototype должен быть проще остальных.

---

## 9. What Must Not Be Solved Inside Menu

Меню не должно брать на себя:

- полные forms параметров
- analysis params editor
- strategy params editor
- full delete explanation text
- backtest equity / stats detail
- venue diagnostics
- trade inspection
- multi-step wizard flows

Это всё остаётся на страницах.

---

## 10. Open Questions For Next Iteration

Это вопросы, которые надо решить до HTML-шаблона или внутри первой html-итерации.

1. Должны ли `Backtests`, `Monte Carlo`, `Paper` иметь глобальные top-level aggregate views, или в prototype остаёмся только на ownership-tree?
2. Что является главным row-action для `Strategy`: `Run BT` или `Open Notebook`?
3. Показываем ли `Delete` у `Recording` и `Analysis` прямо в collapsed row, или только внутри expanded/detail state?
4. Нужен ли `Overflow (...)` уже в первом prototype, или лучше сначала проверить более жёсткий minimal action set?
5. Хотим ли мы визуально разделять зоны как в `image copy.png` (`Runtime / Data / Research / Workbench`) или оставить более простой product layout как в `image.png`?

---

## 11. Proposed Outcome Of This Document

После согласования этого файла следующий артефакт должен быть только один:

- standalone `HTML` menu prototype with mock data

Требования к нему:

- без backend
- без API integration
- только project-true terminology
- только controls, разрешённые этим blueprint
- визуально вдохновлён текущими референсами, но не копирующий их буквально
