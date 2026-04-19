# LeadLag Lab Manual Pipeline Test Report

Дата: 2026-04-18
Тестировщик: Codex через SSH/API/Jupyter execution
Фокус: философия пайплайна из PHILOSOPHY_PIPELINE_MANUAL_TESTING.md

Главный критерий: каждый экран должен помогать создать, проверить или улучшить стратегию.

---

## Журнал

- 2026-04-18T15:22:01.966994+00:00 — создан отчет, начинаю smoke-test UI/API и notebook workflow.

---

## Findings


### 2026-04-18T15:22:35.573949+00:00 — Dashboard/UI/API smoke-test

Проверено:

- `https://vyv.ftp.sh/leadlag-lab/ui/dashboard.html` → 200 HTML.
- `style.css`, `app.js` под `/leadlag-lab/ui/` → 200.
- `/leadlag-lab/api/collections` → 200, есть collection `20260417_121202`.
- `/leadlag-lab/api/sessions` → 200, есть analyzed session `20260417_121202_b8e21fab`, events=22, A/B/C=7/5/10.
- `/leadlag-lab/api/strategies` → 200, есть valid strategy `baseline_signal_c`, last backtest net=-12.65 bps.

Хорошо:

- Пайплайн не пустой: есть данные, analyzed session, strategy и backtest. Это помогает пользователю сразу пройти философский путь Explorer → Strategy → Backtest.
- `app.js` base-path aware: `/api/...` корректно превращается в `/leadlag-lab/api/...` при открытии из `/leadlag-lab/ui/`.

```text
Screen: Entry URL
Problem: Короткий URL `/leadlag-lab/` отдает HTML dashboard, но правильный пользовательский вход фактически `/leadlag-lab/ui/dashboard.html`. Это легко путает тестировщика/пользователя.
Why it matters for strategy development: первый шаг пайплайна должен быть очевидным; пользователь не должен угадывать `/ui/`.
Expected behavior: `/leadlag-lab/` редиректит на `/leadlag-lab/ui/dashboard.html` или отдает корректный UI с тем же base path.
Proposed fix: добавить backend redirect/root route на `/ui/dashboard.html` или поправить root HTML/base links.
Priority: P2
```


### 2026-04-18T15:24:02.009869+00:00 — Notebook workflow: первый запуск копии

Действие:

- Создана копия `/root/projects/leadlag-lab/notebooks/codex_manual_strategy_20260418.ipynb` из `strategy_dev.ipynb`.
- Запущено выполнение через `jupyter nbconvert --execute --inplace`.

Результат:

- Выполнение падает в первой кодовой ячейке с `SyntaxError` на строке вывода fees.

```text
Screen: Notebook / Strategy Development Laboratory
Problem: Шаблон `strategy_dev.ipynb` не выполняется из-за SyntaxError в первой кодовой ячейке: вложенная f-string строка с escaped quotes ломает Python.
Why it matters for strategy development: пользователь не может пройти ключевой шаг философии: Load data → Define strategy → Save .py → Test. Пайплайн рвется до создания стратегии.
Expected behavior: копия notebook должна выполняться сверху вниз без ошибок на готовых данных.
Proposed fix: переписать строку fees preview без вложенной escaped f-string; добавить smoke-test notebook execution в CI/ручной чеклист.
Priority: P0
```

Дополнительное подозрение для проверки дальше:

- В следующей ячейке `%%writefile` стоит не первой строкой ячейки. В IPython cell magic обычно должна быть первой строкой, иначе ячейка тоже упадет.


### 2026-04-18T15:27:26.160802+00:00 — Notebook workflow: доработанная копия выполнена

Действие:

- Доработана тестовая копия `notebooks/codex_manual_strategy_20260418.ipynb` без изменения исходного `strategy_dev.ipynb`.
- Исправлен fees preview.
- `%%writefile` заменен на `save_strategy_source(...)`, чтобы стратегия сохранялась обычным Python-кодом и сразу валидировалась.
- Запуск `jupyter nbconvert --execute --inplace` прошел успешно.

Результат:

- Создан файл `data/strategies/codex_manual_strategy_20260418.py`.
- `/leadlag-lab/api/strategies` видит стратегию как `valid=true`.
- Быстрый `on_event` test возвращает `Order` для подходящего Signal C mock event.

Хорошо:

- Философия “notebook -> .py strategy -> app sees strategy” подтверждена на доработанной копии.
- `save_strategy_source` удобнее и безопаснее, чем raw `%%writefile`: он компилирует и валидирует стратегию сразу.

```text
Screen: Notebook / Strategy Export
Problem: Исходный шаблон использует `%%writefile` внутри ячейки после Python-кода; это хрупко и, вероятно, не выполнится как ожидается.
Why it matters for strategy development: пользователь может написать стратегию, но не получить `.py` файл или получить файл с неожиданным именем.
Expected behavior: экспорт стратегии должен быть явным, валидируемым и понятным: `save_strategy_source` или `export_strategy` с печатью итогового пути.
Proposed fix: заменить `%%writefile` в `strategy_dev.ipynb` на Python export helper; добавить вывод `Saved strategy: ...` и `Loaded: ...`.
Priority: P0
```

```text
Screen: Notebook / Strategy Naming
Problem: Автоматическое имя стратегии из имени notebook зависит от Jupyter runtime session и плохо работает в non-interactive execution/nbconvert.
Why it matters for strategy development: стратегия должна называться по notebook predictably; иначе пользователь не понимает, какой `.py` появился в Strategies.
Expected behavior: имя стратегии явно показывается перед export; для автоматических запусков есть override/env или helper, который надежно знает notebook filename.
Proposed fix: добавить `LEADLAG_STRATEGY_NAME` override и/или более надежный helper; в UI/Jupyter показывать финальное имя до записи файла.
Priority: P1
```


### 2026-04-18T15:28:35.889988+00:00 — Strategy -> Backtest -> Trade -> Monte Carlo

Действие:

- Запущен backtest для `codex_manual_strategy_20260418` на session `20260417_121202_b8e21fab`.
- Проверены backtest meta/trades artifacts.
- Проверены публичные UI routes `backtest.html?id=...` и `trade.html?backtest=...&trade=0`.
- Запущен Monte Carlo для нового backtest.

Результат:

- Backtest создан: `codex_manual_strategy_20260418_20260418_152758`.
- Trades: 1.
- Net PnL: +9.0257 bps.
- Fees: 0.0 bps, slippage: 0.2774 bps, spread at entry: 0.4228 bps.
- Trade route → 200.
- Monte Carlo route работает и возвращает warning `n_trades_lt_20_monte_carlo_is_low_confidence`.

Хорошо:

- Механика перехода Notebook strategy → Strategies API → Backtest → Trade detail → Monte Carlo работает.
- Monte Carlo не молчит о малой выборке; warning важен для принятия исследовательского решения.

```text
Screen: Backtest / Monte Carlo
Problem: Тестовая стратегия дает только 1 trade; результат механически положительный, но исследовательски невалидный.
Why it matters for strategy development: пользователь может увидеть зеленые цифры и переоценить стратегию, если UI недостаточно громко показывает small sample risk.
Expected behavior: при малом числе trades Backtest и Monte Carlo должны явно показывать low-confidence warning до любых выводов о качестве.
Proposed fix: на Backtest header/KPI добавить видимый warning, если `n_trades < 20` или MC вернул low confidence; CTA должен вести назад в Notebook/Explorer для расширения фильтров/данных.
Priority: P1
```


### 2026-04-18T15:30:08.125005+00:00 — Collector / Explorer / Quality / Paper smoke-test

Проверено:

- `/api/collector/status` отвечает; collector stopped, `stale=true`, last session `20260418_143631`.
- `/api/system/pings` отвечает; venues ping statuses mostly `ok`, но часть latency высокая (~250ms).
- `/api/paper/status` отвечает; paper stopped, not blocked.
- `/api/system/processes` отвечает; leadlag-api, monitor, jupyter alive; collector/paper stopped.
- `/api/sessions/20260417_121202_b8e21fab/events` отвечает; Explorer route с session → 200.
- Quality route с session → 200; quality API содержит coverage, BBO, gaps/spread data.

Хорошо:

- Explorer HTML содержит нужные элементы философии: Signal filters, direction, follower filter, chart follower, BBO overlay, EMA baseline, followers table, lag/MFE/MAE/grid data, keyboard navigation.
- Quality HTML содержит coverage heatmap, timeline gaps и BBO analysis — это важно перед созданием стратегии.
- Paper status явно доступен, даже когда stopped.

```text
Screen: Collector / Dashboard Collector Status
Problem: API возвращает общий `stale=true`, но venue rows внутри snapshot выглядят как `status=ok`, с ticks/s и seconds_since_last_tick около нуля относительно старого update time.
Why it matters for strategy development: пользователь может решить, что collector живой и данные продолжают собираться, хотя snapshot устарел. Это ломает первый шаг пайплайна: нельзя писать стратегию на основании непонятного состояния сбора.
Expected behavior: когда collector stale, все venue rows визуально должны быть помечены stale/old snapshot; idle time лучше показывать относительно текущего времени или показывать snapshot age отдельно крупно.
Proposed fix: в UI при `stale=true` override статусы venues на stale и добавить заметный banner `Collector stopped/stale since ...`; скрыть/приглушить live metrics или подписать `last snapshot`.
Priority: P1
```

```text
Screen: Quality
Problem: Quality API показывает низкую bin coverage по ряду venues, но без визуального скриншота пока не подтверждено, насколько ясно UI объясняет: это нормальная sparse tick coverage или риск для анализа.
Why it matters for strategy development: пользователь должен понять, можно ли доверять session и какие venues исключить до notebook.
Expected behavior: Quality должен не просто показывать проценты, а объяснять action: usable / caution / exclude, особенно для venues без BBO.
Proposed fix: добавить decision hints рядом с Venue Summary: `safe for strategy`, `BBO unavailable`, `low coverage`, `exclude from execution-cost-sensitive strategy`.
Priority: P2
```

```text
Screen: Visual manual testing capability
Problem: В текущей среде нет Playwright/Chromium, поэтому Codex не может сам сделать браузерные скриншоты UI.
Why it matters for strategy development: часть чеклиста философии зависит от визуальной оценки chart readability, layout и понятности CTA.
Expected behavior: либо пользователь присылает screenshots, либо в среду добавляется браузерный runner для screenshot-based manual QA.
Proposed fix: для следующего визуального прохода использовать пользовательские скриншоты или установить/подключить Playwright runner.
Priority: P3
```


### 2026-04-18T15:41:39.687200+00:00 — Browser visual smoke with Playwright

Установлено локально для тестирования:

- Playwright npm package.
- Chromium в workspace `.ms-playwright`.
- Скрипт `visual_smoke.js` открыл 8 экранов и сохранил screenshots.

Скриншоты загружены на сервер:

- `/root/projects/leadlag-lab/manual_test_screenshots_2026-04-18/dashboard.png`
- `/root/projects/leadlag-lab/manual_test_screenshots_2026-04-18/collector.png`
- `/root/projects/leadlag-lab/manual_test_screenshots_2026-04-18/quality.png`
- `/root/projects/leadlag-lab/manual_test_screenshots_2026-04-18/explorer.png`
- `/root/projects/leadlag-lab/manual_test_screenshots_2026-04-18/strategies.png`
- `/root/projects/leadlag-lab/manual_test_screenshots_2026-04-18/backtest.png`
- `/root/projects/leadlag-lab/manual_test_screenshots_2026-04-18/montecarlo.png`
- `/root/projects/leadlag-lab/manual_test_screenshots_2026-04-18/paper.png`
- `/root/projects/leadlag-lab/manual_test_screenshots_2026-04-18/visual_smoke_results.json`

Результат browser smoke:

- Dashboard → OK, no console errors, no failed requests.
- Collector → OK, no console errors, no failed requests.
- Quality → OK, no console errors, no failed requests.
- Explorer → OK, no console errors, no failed requests.
- Strategies → OK, no console errors, no failed requests.
- Backtest → OK, no console errors, no failed requests.
- Monte Carlo → OK, no console errors, no failed requests.
- Paper → OK, no console errors, no failed requests.

Визуальные/продуктовые замечания:

```text
Screen: Backtest
Problem: Backtest с 1 trade выглядит визуально как полноценный успешный результат: зеленые KPI, equity/distribution charts, no prominent low-sample warning.
Why it matters for strategy development: философия требует принимать исследовательское решение, а не радоваться equity curve. 1 trade не должен выглядеть как стратегия-кандидат.
Expected behavior: при `n_trades < 20` Backtest должен показывать заметный warning рядом с KPI/header и CTA `Go back to Notebook/Explorer; increase sample`.
Proposed fix: добавить low sample banner в Backtest, аналогичный Monte Carlo warning.
Priority: P1
```

```text
Screen: Strategies
Problem: Actions/status визуально сжаты: `BT Paper Live`, кнопка с символом ▶, `view`, `paper`, `×`. Для нового пользователя непонятно, что означает статус и какой следующий правильный шаг.
Why it matters for strategy development: экран Strategies должен быть мостом из notebook в тяжелые проверки. Сейчас он больше похож на техническую таблицу.
Expected behavior: действия должны быть явными: `Run backtest`, `View latest backtest`, `Start paper`, `Delete`; статус paper/live не должен выглядеть активным, если нет paper/live данных.
Proposed fix: заменить компактные action labels на текстовые кнопки и добавить next-step hint per strategy.
Priority: P2
```

```text
Screen: Monte Carlo
Problem: Для 1 trade Monte Carlo честно показывает warning, но графики/оси становятся почти бессмысленными/визуально странными, потому что распределение вырожденное.
Why it matters for strategy development: пользователь может пытаться интерпретировать графики, хотя математически там почти нечего читать.
Expected behavior: при low sample показывать warning + muted/disabled charts или explanatory empty-state вместо полноценного fan/distribution.
Proposed fix: если `n_trades < 20`, оставить summary/warning, но подписать charts как low confidence или свернуть их за `show anyway`.
Priority: P2
```

```text
Screen: Dashboard / Collector
Problem: В Dashboard stale collector уже подсвечен как `stale`, но рядом остаются live-looking values ticks/s, BBO/s, seconds idle. Визуально это все еще выглядит как текущий поток.
Why it matters for strategy development: пользователь должен без сомнений понимать: данные сейчас не собираются, это старый snapshot.
Expected behavior: stale snapshot должен быть визуально отделен от live monitor, например banner + dimmed metrics + snapshot age.
Proposed fix: при stale добавить `Snapshot age`, приглушить live metrics и переименовать секцию в `Last Collector Snapshot`.
Priority: P1
```

```text
Screen: Explorer
Problem: Explorer функционально богатый и работает, но первый экран плотный: много фильтров, таблица событий, график и followers table без явного `what to look for next`.
Why it matters for strategy development: философия говорит “видно ли событие глазами → появляются идеи условий стратегии”. Новичку нужен исследовательский CTA.
Expected behavior: после выбора события UI подсказывает: check lagging follower, spread/BBO, net grid, then open notebook/create strategy.
Proposed fix: добавить небольшой decision strip: `Pattern visible? follower X lag50=... BBO ok? Open notebook / copy strategy template`.
Priority: P2
```

