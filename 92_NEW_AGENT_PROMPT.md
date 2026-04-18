# 92 - Archived Next Agent Prompt

Статус: archive/reference.

Этот prompt был написан до решения о pre-Flutter stabilization и Flutter-переосмыслении UI. Не использовать его как текущий план реализации. Актуальный порядок работы теперь:

1. `AGENTS.md`
2. `00_DOCS_PIPELINE.md`
3. `plan.md`
4. `05_PRE_FLUTTER_STABILIZATION_PLAN.md`
5. `06_FLUTTER_UI_REWORK_PLAN.md`
6. `03_NEXT_ITERATION_REVIEW_TO_10.md`
7. `04_DEEP_AUDIT_REPORT.md`

Ниже сохранён старый текст только для истории.

## Old Prompt

Copy this into a new Codex dialog started in `/root/projects/leadlag-lab`.

```text
Ты работаешь в репозитории /root/projects/leadlag-lab.

Модель: gpt-5.4, reasoning: xhigh.

Твоя задача: реализовать проект leadlag-lab до 10/10 по исходной задаче пользователя. Не начинай с кодинга вслепую. Сначала прочитай документы в таком порядке:

1. AGENTS.md
2. plan.md, особенно ЧАСТЬ 1: СИНТЕЗИРОВАННОЕ ЗАДАНИЕ ПОЛЬЗОВАТЕЛЯ
3. 02_FULL_REWORK_PLAN_TO_10.md
4. 91_LEGACY_CRITIQUE.md
5. README.md и текущую реализацию, относящуюся к первой фазе

Первый источник истины: задача пользователя в plan.md. План и критика вторичны. Текущая реализация не является источником истины, если она противоречит задаче.

Не реализуй "страницы ради страниц" и не делай placeholders. Цель: пользователь открывает приложение и интуитивно решает задачу lead-lag research/trading: сбор данных, качество, Explorer событий, Jupyter strategy workflow, честный backtest, Trade Inspector, Monte Carlo, paper/live готовность.

Начни только с Phase A из 02_FULL_REWORK_PLAN_TO_10.md:

- восстановить core pipeline;
- session artifacts по контракту: meta/events/price_windows/bbo_windows/quality;
- lazy load_session/list_sessions;
- публичный Python API: load_session, list_sessions, run_backtest, run_monte_carlo;
- backtest API path;
- schema validation;
- tests/acceptance for Phase A.

После Phase A переходи к Phase B:

- Explorer;
- lazy event window loading;
- BBO overlay;
- no-BBO states;
- event table mechanics;
- Trade Inspector with leader/follower/BBO/entry/exit/MFE/MAE/fees/slippage/reasons.

Используй Context7 MCP для актуальной документации библиотек, если трогаешь FastAPI, PyArrow, DuckDB, Plotly, pandas, Pydantic, psutil, websockets, uvicorn или Jupyter API. Не используй Context7 как источник продуктовых требований.

После реализации и проверки Phase A + Phase B сделай commit и остановись. Напиши пользователю: "Переключи новый диалог на gpt-5.4 high для оставшейся реализации". До этого не переключайся на high, если acceptance Phase A/B не проходит.

Работай аккуратно:

- читай текущие файлы перед правками;
- не откатывай чужие изменения;
- добавляй тесты вместе с кодом;
- запускай релевантные проверки;
- коммить маленькими фазовыми коммитами;
- в финальном ответе всегда указывай, что сделано, какие тесты прошли, что осталось.
```
