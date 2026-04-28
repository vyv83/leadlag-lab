# LeadLag Lab — Sprint Handoff (doc #22)

> Этот файл заменяет docs #13, #15, #16, #17, #18, #19, #21 для нового чата.
> Читать: этот файл → `20_WIREFRAMES.md` → реальный HTML следующего экрана → сначала audit/critique, потом только concept, и только потом HTML.

---

## Что такое LeadLag Lab и зачем он нужен

LeadLag Lab — инструмент для одного пользователя (quant-разработчика). Цель: найти и монетизировать lead-lag отношения между криптобиржами.

**Как это работает на практике:**
Некоторые биржи (лидеры: Binance, Bybit) двигают цену первыми. Другие (последователи: OKX, Deribit) следуют с задержкой 50–500ms. Если поймать этот момент — можно открыть позицию на follower до того, как его цена обновится.

**Что делает пользователь — строго по порядку:**

1. **Collect** — запускает сбор тиков и BBO со всех бирж одновременно. Данные пишутся в parquet-файлы с ротацией. Результат: `Recording` (completed session).

2. **Analyze** — запускает обработку записи: бинирует тики, считает EMA, находит события сигнала (A/B/C — lead/lag паттерны). Результат: `Analysis` (набор событий и метрик).

3. **Inspect quality** — оценивает качество данных записи: можно ли доверять этому `Recording`, какие venue портят картину, и стоит ли идти дальше в `Explorer`.

4. **Explore** — визуально инспектирует события на timeline, смотрит паттерны.

5. **Strategy** — пишет Jupyter notebook со стратегией, которая использует события из анализа. Стратегия — это код.

6. **Backtest** — прогоняет стратегию на исторических данных из Recording. Результат: P&L, trades, метрики.

7. **Monte Carlo** — стресс-тест бэктеста: случайные перестановки, чтобы проверить что результат не случайный.

8. **Paper** — запускает стратегию в режиме реального времени с виртуальными деньгами.

9. **Trade** — реальные деньги (последний шаг).

**Ключевые сущности и их отношения:**
```
Recording
  └─ Analysis (параметры обработки: bin_size, threshold, etc.)
       └─ Bins (производные данные)

Strategy (Jupyter notebook)
  └─ Backtest (запуск на конкретном Analysis + Recording)
       └─ Monte Carlo Run
       └─ Trades

Paper Run (реальное время, стратегия + venue)
  └─ Trades
```

---

## Что такое raw HTML и почему его нельзя копировать

В `leadlag-lab/leadlag/ui/` лежат рабочие HTML-файлы, написанные backend-разработчиком.

**Как они построены:**
- Плоский toolbar с кнопками: Start, Stop, Refresh, Analyze, Clear stale...
- Таблица на всю ширину без иерархии
- Никаких состояний (empty, running, error)
- Никакой визуальной приоритизации — всё одинаково важно
- API-структура = UI-структура (как бэк устроен, так и нарисовано)

**Что из них брать:**
- Реальные названия полей (как называются в API)
- Реальные данные (что реально приходит, какие метрики)
- Реальные действия (какие API calls существуют)
- Реальные состояния (что бывает когда нет данных, когда job бежит)

**Что из них НЕ брать:**
- Layout и порядок секций
- Набор кнопок как есть
- Визуальный вес элементов
- Плоскую иерархию

**Главное правило:** raw HTML — это источник фактов о данных, не источник UX-решений.

Но этого недостаточно. Для каждого нового экрана raw HTML нужно не просто "прочитать", а **жёстко раскритиковать**:
- какие элементы действительно помогают пользователю сделать следующий шаг pipeline;
- какие просто показывают всё подряд потому что так удобно бэку;
- какие важны как evidence, но не должны доминировать на первом экране;
- какие элементы вообще не нужны для core-job этого экрана.

Если этой критики нет в `20_WIREFRAMES.md`, значит экран ещё не изучен.

---

## Дизайн-философия (конспект)

**Позиция и размер — разные вещи:**
- Важность элемента определяет его позицию на экране (выше = важнее)
- Размер определяет читаемость, а не важность
- Важная кнопка может быть маленькой но стоять первой
- Большой график нужен только если на маленьком ничего не видно

**Три уровня действий на каждом экране:**
- Primary: одно-два действия которые делает пользователь 90% времени
- Secondary: действия которые нужны иногда
- Diagnostic: просмотр данных, логи, детали — нужны когда что-то не так

Diagnostic content не должен доминировать на экране.

**Состояния обязательны для каждой секции:**
- Нормальное (есть данные)
- Пустое (данных нет, первый запуск)
- Loading / Running
- Error

**Нет в интерфейсе:**
- Explanatory text ("This section shows...")
- Helper subtitles
- Commentary blocks
- Модальных окон

---

## Прототип — где что лежит

```
leadlag-lab-prototype/
  shared-base.css             ← canonical shared CSS source for all reusable prototype UI primitives
  shared-menu.js              ← sidebar (tree, action rail, delete confirm, зоны)
  23_MENU_CONTROLS_CATALOG.html  ← визуальный каталог компонентов (читать если нужен ref)
  codex-dark.html             ← не трогать при унификации prototype CSS

leadlag-lab/leadlag/ui/       ← raw backend HTML (только для извлечения данных/полей)
leadlag-lab/20_WIREFRAMES.md  ← писать wireframes сюда
```

**Зоны sidebar:** `RUNTIME` (Collector) → `DATA` (Recordings) → `RESEARCH` (Strategies) → `WORKBENCH` (Jupyter)

---

## Locked решения (не пересматривать)

**Frame:**
- Sidebar 380px, context bar ~28px не sticky, нет action кнопок в context bar
- Нет модальных окон
- Related Entities секция — всегда внизу экрана

**Collector (done):**
- Venue = navigation filter (`?venue=X`), не отдельная entity
- Analyze action живёт только в `recordings.html`
- Venue `enabled` toggle = единственный контрол (нет отдельного `use`)
- Нет Restart / Refresh кнопок (система real-time, тики)
- Control panel = merged: recording progress sub-row + inputs + KV strip
- Related Entities Collector'а: только recordings, не analyses
- Пока идёт capture, `Collector` владеет `recording in progress`; completed `Recording` появляется только после завершения capture и живёт в `Recordings`

**Quality (locked product decision, но экран открыт к перепроектированию):**
- `Quality` принадлежит `Recording`, не `Analysis`
- canonical route: `quality.html?id=<recording_id>`
- никаких `analysis` query params у `Quality` больше нет; `Explorer` живёт отдельно на своём `analysis` route
- `Delete Analysis` на этом экране отсутствует — управление жизненным циклом Analysis принадлежит `recordings.html`
- `Readiness Decision Strip` = единственный owner-level verdict surface; diagnostics не должны повторять тот же verdict ещё раз
- explanatory diagnostic copy на `Quality` запрещён; разрешены только operational labels, legends, counts, empty/error states
- если chart и raw table отвечают на один и тот же вопрос, expanded остаётся chart, а raw table уходит в collapsed evidence

**Actions:**
- Delete: только при selected row, inline confirm strip (уже в shared-menu.js)
- Progress bar в sidebar: тонкая линия под row активной сущности, без текста
- Expand/collapse blocks: один canonical `disclosure` pattern across screens and catalog, без локальных accordion variants

**Prototype integration:**
- Каждый новый prototype screen обязан иметь:
  - отдельный `.html` файл,
  - route из `shared-menu.js`,
  - совместимость со старыми `index.html?screen=...` deep-links если они ещё существуют,
  - один shared mock-data source для menu + page content, без двух разных hardcoded truth
- После изменения shared prototype scripts нужно bump-нуть query version в `<script src="...?...">`, иначе браузер может показать старую логику
- Экран не считается готовым, пока не проверен:
  - direct URL,
  - open from menu,
  - selected sidebar node,
  - content hydration без runtime errors
- Layout check обязателен:
  - длинные date/time ranges и ids не должны обрезаться без причины
  - desktop action columns не должны переносить badges/buttons на вторую строку по умолчанию
  - `Related Entities` должен быть одной и той же полной ширины на всех entity pages, а не жить в случайной локальной колонке
- Перед созданием новой UI-сущности или нового CSS-класса обязательно проверить:
  - нет ли уже подходящего элемента в `23_MENU_CONTROLS_CATALOG.html`,
  - нет ли уже такого паттерна в `collector.html` или других готовых prototype screens.
- Нельзя создавать новые сущности и классы, пока не доказано, что существующие элементы каталога и проекта реально не покрывают задачу.
- Если reusable pattern используется на нескольких prototype screens, он обязан быть вынесен в один shared prototype file, а не копироваться style-block'ами по страницам.
- Для disclosure / accordion pattern canonical source of truth = `leadlag-lab-prototype/shared-base.css`.
- Все prototype screens, кроме `codex-dark.html`, обязаны брать reusable base UI из `leadlag-lab-prototype/shared-base.css`; в локальном `<style>` разрешён только screen-specific слой.

---

## Что значит "изучи всё"

Если пользователь пишет:
- `изучи всё`
- `изучи экран`
- `сначала разберись`
- `сделай concept pass`
- `не начинай дизайн`

то это **НЕ** означает "можно после чтения сразу начать собирать HTML".

Это означает обязательную остановку на стадии исследования. На этой стадии нужно:
1. перечитать `22_SESSION.md`;
2. найти и прочитать соответствующий raw HTML в `leadlag/ui/`;
3. выписать факты о данных, действиях, состояниях;
4. жёстко раскритиковать raw screen именно как продуктовый экран;
5. разложить элементы по полезности и важности;
6. записать результат в `20_WIREFRAMES.md`.

Пока эти шаги не сделаны, экран считается **не изученным**.

---

## Антипаттерны (что считается провалом)

Ниже перечислено то, что делать нельзя. Если агент это сделал — значит он сорвал процесс, даже если HTML формально работает.

1. Прочитать raw HTML и сразу перейти к прототипу, не сделав critique/matrix в `#20`.
2. Путать "источник фактов" с "источником layout-решений" и переносить структуру страницы по инерции.
3. Начать спорить про CSS/menu/runtime до того, как зафиксирована продуктовая роль экрана.
4. Вкладываться в перенос/интеграцию раньше, чем доказано, что выбран правильный functional surface.
5. Делать "примерно хороший UI", не доказав, что он закрывает полный job-to-be-done этого экрана.
6. Добавлять или убирать controls, не пройдя через явную критику: зачем пользователь на этом экране вообще должен их видеть.
7. Считать экран "done" только потому, что он открылся без runtime errors.

Работающий HTML без product audit — это не progress, а риск закрепить неправильную модель.

### Конкретный failure mode, который уже случился

На предыдущем заходе агент слишком рано переключился в implementation mode:
- увидел "следующий экран = Quality";
- быстро зафиксировал owner/navigation решения;
- почти сразу начал собирать prototype screen и menu/runtime integration;
- начал спорить про route, shared-menu, cache-busting, layout и delete flows;
- при этом не сделал полноценный raw functional audit и не довёл его до `#20`.

Почему это плохо:
- был потрачен ресурс на HTML до того, как был доказан правильный functional surface;
- обсуждение сместилось с сути экрана на перенос/починку реализации;
- ошибки продуктового уровня всплыли поздно, когда код уже был написан;
- агент начал "чинить мусор", а не проектировать экран с нуля правильно.

Именно против этого сценария написан жёсткий протокол ниже.

---

## Как работать с новым экраном (жёсткий протокол)

Это обязательная последовательность. Нарушать её нельзя.

### Шаг 1 — Понять экран как продукт
Ответить на вопросы:
- Какова роль этого экрана в pipeline? Что пользователь пришёл сюда сделать?
- Какая сущность владеет этим экраном?
- Что является primary action, что secondary, что diagnostic?
- Что показывать когда данных нет (empty state)?

### Шаг 2 — Изучить raw HTML как источник фактов
Выписать:
- Реальные поля (имена из API)
- Реальные действия (API calls)
- Реальные состояния которые уже обрабатываются

### Шаг 3 — Жёстко раскритиковать raw screen как продукт
Обязательно ответить:
- Что в raw экране помогает пользователю выполнить core-job?
- Что мешает, отвлекает или маскирует главный decision point?
- Какие блоки нужны как evidence, но не должны жить "над fold"?
- Какие элементы вообще бесполезны для core-job и должны быть выброшены?

Для **каждого значимого raw элемента** обязательно зафиксировать в `20_WIREFRAMES.md`:
- Functional value: `0–10`
- Pipeline importance: `0–10`
- User need coverage: `must-have` / `supporting` / `optional` / `waste`
- Spatial footprint: `XS / S / M / L`
- Keep / Move / Remove / Postpone
- Короткую жёсткую причину, почему именно так

### Шаг 4 — Проверить покрытие задач пользователя
Нужно перечислить, какие задачи пользователь должен уметь сделать на этом экране **на 100%**.

Для каждой задачи:
- задача пользователя;
- какие данные/controls для неё нужны;
- что есть в raw;
- чего не хватает в raw;
- насколько текущий raw экран закрывает её: `0–10`.

Если полный набор задач не выписан, нельзя переходить дальше.

### Шаг 4.1 — Для diagnostic screens: exhaustive slice sweep

Если экран по своей природе diagnostic / forensic / quality-heavy, недостаточно назвать 2–3 очевидных chart'а.

Нужно:
- перечислить максимально полный набор возможных разрезов;
- не лениться и не останавливаться на первых 5 идеях;
- для каждого разреза определить:
  - на какой вопрос пользователя он отвечает;
  - какая форма представления лучше всего подходит;
  - насколько он уникален vs дублирует другой разрез;
  - насколько он обязателен именно для этого экрана.

Минимальный стандарт:
- сначала exhaustive list кандидатов;
- потом жёсткая оценка `0–10`;
- потом shortlist обязательных, полезных, дублирующих и бесполезных;
- только потом переход к screen structure.

Если этого шага нет, diagnostic screen считается недоисследованным.

Важно:
- exhaustive sweep делать нужно;
- но в финальный документ не нужно сваливать длинный dump из 20–50 кандидатов;
- думать широко надо в чате или во внутренних рассуждениях;
- в `20_WIREFRAMES.md` должен попадать только результат:
  - final shortlist,
  - optional shortlist,
  - explicit reject list,
  - короткая причина выбора.

Иначе `#20` превращается из spec в мусорный research log.

### Шаг 4.2 — Никаких narrative выводов без явного источника

Если экран содержит diagnostic / forensic blocks, агенту запрещено придумывать "умные" выводы в стиле:
- `X lines up with Y`
- `problem is only partially storage-driven`
- `issue likely upstream in feed quality`

если для этого нет одного из двух:

1. backend already returns this exact derived conclusion as data, или
2. в `20_WIREFRAMES.md` заранее зафиксирован явный deterministic rule-table:
   - какие входные поля используются,
   - какое условие срабатывает,
   - какой короткий output label разрешён.

Правила:
- prototype must not simulate expert reasoning with prose;
- causal language is forbidden unless backed by explicit product logic;
- if there is no explicit rule engine, show only factual evidence:
  - statuses
  - counts
  - notes
  - timestamps
  - flags
- "умно звучащий текст" без source of truth считается фантазией, а не UX.

### Шаг 5 — Проработать варианты
Если есть неоднозначность: 2–4 варианта → критика каждого → оценка 0–10 → выбор.
Если один вариант явно сильнее (9–10 vs остальные ≤4) — решить самому, объяснить почему.
Если варианты близки — спросить пользователя.

### Шаг 6 — Написать Concept Contract в `20_WIREFRAMES.md`
До HTML в `#20` должны появиться все артефакты:
- role / owner / primary-secondary-diagnostic split;
- raw facts inventory;
- raw critique with 0–10 scoring;
- user-task coverage matrix with 0–10 scoring;
- options / decision matrix;
- final concept contract;
- explicit list of useless elements to exclude from design.

### Шаг 7 — Остановиться и свериться
После заполнения `#20` нужно остановиться и проверить:
- действительно ли экран уже понят как продукт;
- есть ли жёсткое объяснение, почему каждый крупный блок нужен или не нужен;
- не началась ли преждевременная возня с layout/runtime/menu.

Если пользователь просил сначала "изучить", "разобрать", "сделать concept pass", то на этом шаге **нужно остановиться** и не начинать HTML, пока пользователь явно не переведёт работу в implementation phase.

### Шаг 8 — Собрать HTML прототип
Копировать CSS и компоненты из `collector.html`. Не изобретать новые классы без необходимости.

### Шаг 9 — Подключить экран к prototype runtime
Обязательно:
- добавить route в `shared-menu.js`
- синхронизировать menu data и page data через shared source
- обновить legacy redirects если они ещё используются
- bump-нуть version query на shared scripts
- проверить direct open и open from menu

---

## Definition of Done для стадии concept

Экран считается готовым к HTML только если одновременно выполнены все условия:
- owner экрана определён и защищён аргументами;
- raw screen разобран по фактам;
- raw screen раскритикован по функционалу, а не только по визуалу;
- полезность крупных элементов оценена по шкале `0–10`;
- покрытие задач пользователя оценено по шкале `0–10`;
- список `что оставить / что убрать / что опустить` записан явно;
- в `#20` уже есть решение, а не просто размышления;
- пользователь не просил остановиться на стадии concept.

Если хотя бы одного пункта нет, переход в HTML запрещён.

---

## Статус экранов

1. ✓ **Collector** — `leadlag-lab-prototype/collector.html`
2. ✓ **Recordings** — `leadlag-lab-prototype/recordings.html`
3. ⟳ **Quality** — `leadlag-lab-prototype/quality.html` — в процессе; owner=Recording исправлен, концепт зафиксирован в `20_WIREFRAMES.md`, прототип частично собран — **не завершён**
4. → **Explorer** — только после завершения `Quality`
5. Strategy
6. Backtest
7. Monte Carlo
8. Paper
9. Trade
10. Dashboard — последний (synthesis screen)

---

## Обновлять этот файл после каждого экрана

После завершения экрана добавить в таблицу выше `✓ done` и записать любые новые locked решения в секцию выше.

Если экран пришлось reopen-нуть из-за слабого product pass, это тоже нужно фиксировать в этой таблице, а не замалчивать.
