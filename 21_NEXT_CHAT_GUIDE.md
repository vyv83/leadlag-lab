# LeadLag Lab — Guide for Next Chat (doc #21)

> Цель: следующий чат продолжает `20_WIREFRAMES.md` по одному экрану за раз, на основе реального проекта, без выдуманных секций и без возврата к Dashboard раньше времени.

---

## Текущий статус

- `20_WIREFRAMES.md` теперь является каноническим working doc для wireframes.
- В `#20` уже есть **provisional Dashboard section**, переписанная на основе реального `dashboard.html`.
- Но Dashboard пока **не должен быть следующим экраном для доработки**. Его финальная сборка отложена до конца, когда будут уточнены остальные screens.
- `Collector` и `Recordings` уже зафиксированы как пройденные core screens.
- Следующий экран по pipeline и по приоритету сейчас: **Quality**.

Следующий чат должен:

1. перечитать `20_WIREFRAMES.md` как формат и стиль screen-spec,
2. изучить реальные HTML-экраны,
3. сначала решить фундаментальные product/UI-вопросы по экрану,
4. только потом дописать **следующий экран** в `#20`,
5. не возвращаться к финальному Dashboard, пока не проработаны core screens.

Прямо сейчас это означает:

1. не переделывать заново `Collector`,
2. не переделывать заново `Recordings`, если нет нового продуктового решения,
3. идти дальше в `Quality`.

---

## Порядок чтения (строго)

### Шаг 1 — product + design entry points

```
leadlag-lab/PRODUCT.md
leadlag-lab/DESIGN.md
```

### Шаг 2 — дизайн-система, pipeline и frame decisions

```
menu-sprint/codex-dark.html              ← canonical visual reference (читать весь HTML)
leadlag-lab/STRATEGY_DEVELOPMENT.md      ← философия и workflow разработки стратегий (что делает пользователь на практике)
leadlag-lab/13_ARCHITECTURE_DECISIONS.md ← rename-правила, UX-решения по архитектуре
leadlag-lab/15_PIPELINE_AUDIT.md         ← полный user pipeline, тупики, реальные переходы
leadlag-lab/16_DOMAIN_MODEL.md
leadlag-lab/17_MENU_CONTROLS_BLUEPRINT.md
leadlag-lab/18_DESIGN_SYSTEM.md
leadlag-lab/19_FRAME.md
leadlag-lab/20_WIREFRAMES.md             ← канонический working doc
```

### Шаг 3 — реальные экраны (все)

```
leadlag-lab/leadlag/ui/dashboard.html
leadlag-lab/leadlag/ui/collector.html
leadlag-lab/leadlag/ui/recordings.html
leadlag-lab/leadlag/ui/quality.html
leadlag-lab/leadlag/ui/explorer.html
leadlag-lab/leadlag/ui/strategy.html
leadlag-lab/leadlag/ui/backtest.html
leadlag-lab/leadlag/ui/montecarlo.html
leadlag-lab/leadlag/ui/paper.html
leadlag-lab/leadlag/ui/trade.html
leadlag-lab/leadlag/ui/menu-prototype.html
```

По каждому экрану зафиксировать:
- Что реально показывается (секции, таблицы, charts, panels)
- Какие реальные данные используются (названия полей, метрики)
- Что не работает или выглядит неправильно (несоответствие docs #16-19)
- Что хорошо и надо сохранить

---

## AI Working Protocol (обязательно)

### 1. Сначала понять продукт, а не копировать экран

- Текущий `leadlag/ui/*.html` — это **источник фактов о данных, API и состояниях**, но не финальный UX source of truth.
- Нужно исходить из product pipeline и domain model, а не из того, как backend-first экран был когда-то собран.
- Если текущий HTML конфликтует с docs `#13`, `#15`, `#16`, `#17`, `#19`, приоритет у docs.

Прямое правило:

- **не копировать текущий экран целиком только потому, что он уже существует;**
- **не переносить все текущие кнопки, таблицы и блоки без product-критики;**
- **не считать backend-структуру автоматически правильной для UX.**
- **не добавлять на экран helper text, explanatory subtitles и commentary; пояснения допустимы только в docs и code comments.**

### 2. Перед wireframe нужно решить концепцию экрана

До написания screen-spec ИИ обязан разобраться с фундаментальными вопросами экрана.

Для каждого экрана и связанных menu nodes нужно ответить:

- Какова роль экрана в user pipeline?
- Какая сущность владеет этим экраном?
- Что должно жить в sidebar, а что только в content area?
- Какие действия являются primary, secondary, diagnostic?
- Какие кнопки надо **оставить / перенести / убрать / отложить**?
- Какие таблицы и графики реально нужны, а какие backend-случайность?
- Какие секции слишком малы или бесполезны для чтения реальных данных?
- Как sidebar и content связаны между собой?
- Что делает `?venue=X`, `?id=X`, `?analysis=X` и как это влияет на весь экран?

Типичные вопросы, которые надо решить явно, а не замолчать:

- `Collector` — single root или вложенный `collector_run_*`?
- `Recordings` — это top-level data branch или вторичный список внутри Collector?
- `Ticks`, `BBO`, `Bins` — это menu/tree nodes или только content/detail sections?
- `Analyze` должен жить на Collector или на Recording?
- Нужны ли все текущие toolbar buttons, или часть из них надо убрать?
- Какого размера должен быть каждый chart, чтобы на нём было что-то видно?

Если эти вопросы не разобраны, **нельзя переходить к HTML mock**.

### 3. ИИ обязан отдельно оценивать важность элемента и его footprint

Перед layout-решением ИИ должен пройтись по ключевым элементам экрана:

- primary / secondary / diagnostic actions,
- charts,
- tables,
- status blocks,
- alerts,
- text sections,
- related entities.

Для каждого важного элемента надо оценить **две разные вещи**:

1. **Важность в pipeline (`0-10`)**
2. **Нужный spatial footprint (`XS / S / M / L`)**

Это не одно и то же.

Прямые правила:

- важный элемент **не обязан** быть большим;
- размер зависит не только от важности, но и от того, сколько пространства реально нужно для чтения, сравнения или действия;
- если элемент можно понять в компактной форме, он должен остаться компактным;
- минимализм в размерах важен, раздувать layout "на всякий случай" нельзя.

Примеры:

- критичный status badge или primary CTA может быть очень важным, но занимать мало места;
- важная таблица не обязана становиться огромной, если пользователю нужен только короткий scan + переход в detail;
- chart можно делать большим только если без этого на нём невозможно прочитать структуру данных;
- log, files, debug blocks, helper text почти всегда secondary или diagnostic и не должны съедать экран.

Отдельное правило для графиков:

- `tick`, `candlestick`, `latency`, `equity` charts должны получать размер исходя из читаемости паттерна, а не просто из "это график";
- если график нужен для детального чтения формы сигнала, он должен получить достаточно ширины и высоты;
- если график играет только роль ориентира, достаточно компактного sparkline / mini-chart;
- нельзя делать маленький chart-card, на котором в реальной работе ничего не видно.

Позиция элемента на экране зависит прежде всего от его роли в pipeline.
Размер элемента зависит от:

- важности,
- частоты использования,
- плотности информации,
- необходимости сравнения,
- читаемости.

Если элемент важен, но по природе компактен, он должен быть **вверху и компактным**, а не искусственно раздутым.

### 4. ИИ обязан делать decision matrix, а не выбирать на глаз

Если по экрану есть важная неоднозначность, ИИ должен:

1. перечислить 2-4 разумных варианта,
2. жёстко покритиковать каждый,
3. поставить оценку `0-10`,
4. выбрать один вариант или вынести вопрос пользователю.

Это касается:

- menu hierarchy,
- ownership,
- screen sections,
- element importance and footprint,
- chart sizing,
- button sets,
- CTA placement,
- detail vs inline decisions,
- empty states,
- cross-screen navigation.

### 5. Когда ИИ решает сам, а когда спрашивает пользователя

ИИ **решает сам**, если:

- один вариант явно доминирует,
- остальные решения заметно слабее,
- разница не косметическая, а продуктовая,
- примерный паттерн оценки: `9-10/10` против `0-4/10`.

В этом случае ИИ:

- принимает решение сам,
- **обязательно объясняет пользователю, почему это решение выбрано**.

ИИ **спрашивает пользователя**, если:

- варианты близки по качеству,
- trade-offs неочевидны,
- несколько решений выглядят примерно одинаково жизнеспособными,
- выбор меняет ощущение продукта или рабочий стиль пользователя.

Важное правило:

- ИИ не должен задавать вопрос только потому, что поленился дочитать код или docs.
- Отсутствие вопросов допустимо только когда решение действительно стало однозначным после анализа.

### 6. Правильный порядок работы

Для каждого нового экрана:

1. Прочитать docs и реальный код.
2. Выписать фундаментальные вопросы экрана.
3. Оценить важность и footprint ключевых элементов.
4. Сделать decision matrix по спорным местам.
5. Зафиксировать product/UI choice.
6. Только потом писать wireframe в `#20`.
7. Только после этого делать HTML mock.

Если пользователю трудно воспринимать чистый текст:

- сначала всё равно нужен concept pass,
- затем короткий wireframe/spec,
- затем сразу HTML mock этого же экрана,
- но **не наоборот**.

### 6.1. Prototype Integration Checklist (обязательно)

После того как HTML mock экрана собран, его нельзя считать готовым, пока не выполнены все пункты ниже.

1. **Файл страницы создан и открывается напрямую**
   - пример: `recordings.html?id=X`
   - нельзя ограничиваться `index.html?screen=...` placeholder-shell

2. **Страница подключена к prototype menu/router**
   - если в prototype используется `shared-menu.js`, новый экран обязан иметь route оттуда;
   - если есть legacy redirect через `index.html?screen=...`, его тоже нужно обновить, чтобы старые deep-link не вели в пустой placeholder

3. **Данные страницы и sidebar согласованы**
   - mock-данные для menu tree и content area не должны жить в двух несвязанных hardcoded копиях;
   - для prototype нужно использовать один shared source of truth, например общий `mock-data.js`

4. **URL params согласованы с frame**
   - screen должен поддерживать canonical params из `19_FRAME.md`
   - пример: `recordings.html?id=X`, `quality.html?id=X`, `collector.html?venue=X`

5. **Кэш не должен скрывать правки**
   - при изменении shared prototype scripts (`shared-menu.js`, shared data, routing helpers) нужно bump-нуть query version в `<script src="...?...">`

6. **Runtime-проверка обязательна до сдачи**
   - открыть экран по прямому URL;
   - открыть его из menu;
   - проверить, что sidebar selection, content data и actions соответствуют одному и тому же entity;
   - проверить, что страница не падает на старте из-за `history`, route mapping, missing globals или script-order bugs

7. **Нельзя оставлять “визуально есть HTML, но JS не гидратился”**
   - если на экране виден дефолтный placeholder, `—`, пустые таблицы или несогласованные ids, это не “почти готово”, а broken state;
   - нужно поймать runtime error и починить до handoff

8. **Колонки и footer обязаны проверяться на реальных строках**
   - длинные ids, date/time ranges, badges и action sets нельзя оценивать на коротких dummy-строках;
   - если важное значение режется по умолчанию, нужно переработать grid/table widths, а не мириться с ellipsis как с нормой;
   - action columns не должны переносить badges и кнопки на вторую строку в desktop layout, если только это не осознанный responsive state;
   - `Related Entities` внизу entity-screen должен иметь единообразную полную ширину content area, а не зависеть от ширины локальной колонки конкретной страницы

### 7. Чего делать нельзя

Плохой режим работы:

- тяп-ляп переносить существующий backend-экран в prototype;
- не задаваться вопросом, зачем нужна каждая кнопка;
- путать важность элемента с его физическим размером;
- рисовать маленькие chart-cards, на которых ничего не видно;
- раздувать текст, таблицы или списки только потому, что они "важные";
- писать в интерфейсе тексты вроде `this mock shows...`;
- добавлять случайные footer / helper blocks без product-смысла;
- считать menu уже решённым и не связывать его с content;
- сначала лепить HTML, а потом задним числом пытаться объяснить логику.

Хороший режим работы:

- сначала product reasoning,
- потом menu/content contract,
- потом screen spec,
- потом prototype.

---

## Что значит "хороший wireframe"

Плохо (тяп-ляп):
- придуманные секции без опоры на реальный HTML
- абстрактные placeholder-названия вместо реальных полей
- не учтены реальные состояния (что показывается когда нет данных, когда job бежит)
- нет связи с реальным API-контрактом

Хорошо:
- каждая секция wireframe = реальная секция из существующего HTML-экрана
- поля называются так же как в реальном коде (или как должны называться после рефакторинга по docs #16-19)
- описаны все состояния: пустое, loading, error, нормальное
- указано что убрать/переделать по сравнению с текущим HTML
- зафиксированы фундаментальные product-решения по экрану, а не только layout
- wireframe = спецификация для HTML-разработчика, не essay

---

## Формат каждого экрана в #20

```markdown
## Экран N — Name

**URL:** `name.html[?params]`
**Тип:** single / list+detail

### N.0 Concept Contract
- Роль экрана в pipeline
- Какая сущность владеет экраном
- Какие menu nodes и child nodes для него принципиальны
- Что `Keep / Move / Remove / Postpone`
- Какие элементы имеют pipeline importance `0-10`
- Какой footprint нужен ключевым элементам (`XS / S / M / L`) и почему
- Какие решения уже однозначны
- Какие вопросы требуют user choice

### N.1 Sidebar State
(что выделено, есть ли action rail, какие кнопки)

### N.2 Context Bar
(dot, entity name, meta, toast)

### N.3 Content Sections
(секции сверху вниз, каждая с:)
- Название секции
- Компоненты из doc #18
- Реальные поля и данные
- Состояния: нормальное / пустое / ошибка

### N.4 Navigation
(таблица: элемент → destination URL)

### N.5 Delta from current HTML
(что изменить относительно leadlag/ui/name.html)
```

---

## Приоритет экранов

Делать по одному за разговор, в порядке pipeline:

1. Collector
2. Recordings
3. Quality
4. Explorer
5. Strategy
6. Backtest
7. Monte Carlo
8. Paper
9. Trade
10. Dashboard — только в самом конце, как synthesis screen

---

## Dashboard Status

Dashboard сейчас **не является следующим экраном для wireframe-работы**.

Почему:

- это synthesis screen, который должен собираться после уточнения остальных screens,
- иначе туда легко притащить сырые wide tables и случайные блоки из detail pages,
- уже есть provisional Dashboard spec в `#20`, этого достаточно до финальной итерации.

Если позже возвращаться к Dashboard, помнить жёсткие правила:

- `CPU / RAM / Disk / Network` остаются на Dashboard обязательно,
- Dashboard = triage + orientation + next step,
- full detail tables не тащим на главную.

Shortlist будущего финального Dashboard:

1. `System Health Strip`
2. `Runtime Services`
3. `Active Recording`
4. `Active Paper Run`
5. `Recordings Ready Queue`
6. `Latest Analyses`
7. `Backtest Highlights`
8. `Attention / Next Actions`

Чего не должно быть на финальном Dashboard как full blocks:

- full `Collector Live Monitor`
- full `Venue Summary`
- full `Strategies` table
- full `Trades` tables
- full `Files` table
- full Monte Carlo charts

---

## Полезные скиллы

- `/impeccable` — после написания wireframe, если нужно итерировать UI
- `/critique` — критика текущего HTML до написания wireframe
- `/extract` — извлечь design patterns из codex-dark.html в system.md

---

## Важные решения из doc #19 (не забыть)

- Sidebar 380px (не 320px как в doc #18 — doc #19 обновляет)
- Context bar ~28px, не sticky, нет кнопок действий
- Related Entities секция — всегда внизу, кроме Dashboard
- Progress bar в sidebar — под row активной сущности, без текста
- Collector/Venue — venue это navigation filter, не domain entity
- Delete — только при selected row, inline confirm strip
- Overflow `...` — не использовать в первом прототипе

---

## Menu Thinking Rule

Menu нельзя считать заранее решённым.

Следующий чат обязан дорабатывать menu contract вместе с screen contract, когда появляются фундаментальные решения по:

- `Collector`
- `Recordings`
- `Analyses`
- `Ticks`
- `BBO`
- `Bins`
- `Backtests`
- `Paper`

Правило:

- если screen concept меняет ownership, вложенность или primary action, это надо сразу отражать в menu reasoning;
- нельзя сначала "как-нибудь" сделать screen, а menu думать потом;
- menu и content проектируются вместе, потому что это один UX-контракт.
