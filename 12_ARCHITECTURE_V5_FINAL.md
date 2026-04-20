# LeadLag Platform — Финальная архитектура v6 (10/10)

Дата: 2026-04-20
История итераций: v1-v5 в чате; v6 финализирован после критики пользователя по 6 пунктам (live charts, unified app, manual position mgmt, UI perf, bar-only, get_notebook_name).

---

## 0. Исходная задача (повтор)

Локальное веб-приложение для алго-трейдинга lead-lag стратегий. Полный пайплайн в одном месте:

1. Сбор данных (коллектор, 12 бирж, BTC).
2. Разработка стратегий в JupyterLab как в **лаборатории** (полноценный Python).
3. Глубокий бэктест с реальностью исполнения (BBO-slippage, maker/taker fees).
4. Детальный просмотр каждой сделки.
5. Monte Carlo.
6. Paper trading.
7. **Real trading** (production-grade, с manual override).

Стек: FastAPI + vanilla HTML + **SolidJS (via esm.sh CDN)** + **Plotly.js WebGL** + Parquet + SQLite (WAL) + supervisord. Без Docker/React/PostgreSQL/Flutter/npm/webpack.

---

## 1. Философия (финализирована)

1. **Стратегия — Python-класс.** Источник истины — `.py` файл.
2. **Один класс везде.** Notebook → backtest → paper → live.
3. **Стратегия первична.** Владеет биннингом, детекцией, входом, выходом.
4. **Стратегия работает ТОЛЬКО с барами.** Тики — implementation detail BarBuilder-а.
5. **Реальность исполнения сквозная.** Spread/slippage/fees идентично считаются во всех путях.
6. **Режим — тип конкретного Run-а, не свойство приложения.** Приложение одно; Run — объект с типом (`backtest|paper|live|shadow|research`).
7. **Один идентификатор везде:** имя ноутбука = имя `.py` = `Strategy.name` = run namespace.
8. **Manual override — first-class feature.** Ручное вмешательство в live/paper через UI, не только автоматика.
9. **Локально, без build-step.** SolidJS через ESM CDN, Plotly.js через CDN.

---

## 2. Слои системы

```
┌──────────────────────────────────────────────────────────────────┐
│  UI (SolidJS via esm.sh + Plotly WebGL + Worker + msgpack + SSE) │
│  Pages: Home · Data · Lab · Strategies · Runs · Live Ops         │
└─────────────────────────────┬────────────────────────────────────┘
                              │ HTTP/2 + brotli, SSE, msgpack
┌─────────────────────────────┴────────────────────────────────────┐
│  FastAPI (REST + /events SSE + /data/*.msgpack)                  │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                  ┌───────────┴────────────┐
                  │    EventLoop (core)    │
                  └───────────┬────────────┘
                              │
      ┌───────────────┬───────┴────────┬───────────────┐
      ▼               ▼                ▼               ▼
 MarketDataSource  Strategy        Executor       Observability
 (Parquet|Live)    (user .py)      (Sim|Live)
      │               │                │
      ▼               ▼                ▼
 DataQualityGate   BarBuilder      RiskEngine (checks incl. manual)
 BarBuilder        (feeds bars)    OrderStateMachine
                                   PositionReconciler
                                   KillSwitch (gradient)
                                   ManualInterventionAPI ← new
                              │
                              ▼
                    ┌─────────────────┐
                    │  Хранилища       │
                    │  • parquet       │
                    │  • SQLite WAL    │
                    │  • .py strategies│
                    │  • .ipynb matched│
                    │  • YAML config   │
                    └─────────────────┘
```

---

## 3. Единый контракт стратегии: только бары

**Ключевой переход:** стратегия больше не видит тики. Единственный callback `on_bar`. Тики — внутри BarBuilder.

```python
@dataclass
class Bar:
    venue: str
    ts_ms: int
    vwap: float
    volume: float
    n_ticks: int
    is_final: bool      # True когда бин закрыт по времени (50ms прошло)
    is_update: bool     # True если вызван по приходу тика (partial bar, "last tick = close")
    age_ms: int

@dataclass
class BarSnapshot:
    ts_ms: int
    bars: dict[str, Bar]        # все текущие бары всех venues
    trigger_venue: str          # какой venue вызвал этот callback
```

### Контракт Strategy

```python
from leadlag import Strategy, Order, Signal, Exit
from leadlag.bars import TimeBinning
from leadlag.utils import EmaTracker, CrossingDetector, Confirmer
from leadlag.notebook import get_notebook_name

STRATEGY_NAME = get_notebook_name()          # "lighter_c_bbo_v2"

class LighterCv2(Strategy):
    name = STRATEGY_NAME                      # один идентификатор везде
    version = "2026-04-20"
    description = "Lighter Perp на Signal C, BBO filter, SL/TP"

    bar_builder = TimeBinning(50)
    leaders = ["OKX Perp", "Bybit Perp"]
    followers = ["Lighter Perp"]

    params = {
        "sigma": 2.0,
        "follower_max_dev": 0.5,
        "confirm_window_ms": 500,
        "hold_ms": 30_000,
        "max_spread_bps": 2.0,
        "slippage_model": "half_spread",
        "react_to_partial": True,             # реагировать на is_update=True (live-instant)
        "stop_loss_bps": None,
        "take_profit_bps": None,
        "position_mode": "reject",
        "qty_btc": 0.001,
    }

    def setup(self, ctx):
        self.emas = {v: EmaTracker(200) for v in ctx.venues}
        self.xings = {v: CrossingDetector(self.params["sigma"]) for v in self.leaders}
        self.confirm = Confirmer(window_ms=self.params["confirm_window_ms"])
        # Warmup из истории — identично в backtest/paper/live
        for v in ctx.venues:
            for bar in ctx.warmup.bars(v, last_n=400):
                self.emas[v].update(bar.vwap)

    def on_bar(self, snap, ctx):
        """Unified callback. Called:
          - on bar finalization (is_final=True) — guarantee in all modes
          - on tick update (is_update=True) — in live/paper if react_to_partial
        """
        bar = snap.bars[snap.trigger_venue]

        # Filter: ждём финальный бар если partial не интересует
        if bar.is_update and not self.params["react_to_partial"]:
            return

        # === Detection ===
        _, _, dev = self.emas[snap.trigger_venue].update(bar.vwap)
        if snap.trigger_venue in self.leaders:
            if (x := self.xings[snap.trigger_venue].update(dev)):
                classification = "C" if self.confirm.register(snap.trigger_venue, x, snap.ts_ms) else "A"
                ctx.emit(Signal(
                    ts_ms=snap.ts_ms, leader=snap.trigger_venue,
                    direction=x.direction, magnitude=x.mag,
                    classification=classification,
                    lagging=[f for f in self.followers
                             if abs(self.emas[f].dev) < self.params["follower_max_dev"]],
                ))

        # === Exit management (на баре, а не на тике) ===
        for pos in ctx.positions.open():
            b = snap.bars.get(pos.venue)
            if b and self._should_exit(pos, b):
                ctx.close(pos, reason=self._exit_reason(pos, b))

    def on_signal(self, sig, ctx):
        """Optional. Without this method — strategy is signal-only (research)."""
        if ctx.data_quality.degraded:
            return None
        if sig.classification != "C":
            return None
        venue = next((f for f in self.followers if f in sig.lagging), None)
        if not venue:
            return None
        bbo = ctx.bbo.get(venue)
        if bbo.available and bbo.spread_bps > self.params["max_spread_bps"]:
            return None
        return Order(
            venue=venue,
            side="buy" if sig.direction > 0 else "sell",
            qty_btc=self.params["qty_btc"],
            entry_type="market",
            hold_ms=self.params["hold_ms"],
            stop_loss_bps=self.params["stop_loss_bps"],
            take_profit_bps=self.params["take_profit_bps"],
        )

    def on_order_event(self, evt, ctx):
        """React to order lifecycle: ACCEPTED, PARTIAL, FILLED, REJECTED, CANCELLED,
        MANUAL_INTERVENTION (user closed position / moved SL / flattened venue)."""
        if evt.kind == "rejected":
            ctx.obs.counter("rejects").inc(labels={"venue": evt.venue, "reason": evt.reason})
        if evt.kind == "manual_intervention":
            ctx.obs.counter("manual_interventions").inc(labels={"action": evt.action})
```

**Нет `on_position_tick`.** SL/TP/hold управляется внутри `on_bar` (в live `is_update=True` работает как tick-resolution exit).

---

## 4. BarBuilder: тики внутри, бары снаружи

```python
class BarBuilder(ABC):
    """Converts tick stream to bar events. Hides ticks from strategy."""

    def on_tick(self, tick: Tick) -> list[BarEvent]:
        """Returns:
          - BarEvent(is_update=True): partial bar обновлён тиком (live/paper)
          - BarEvent(is_final=True):  бар закрыт по времени (все режимы)
        In backtest: ТОЛЬКО is_final events (для скорости; can be overridden
        with `replay_ticks=True` для байт-идентичной paper/live parity).
        """

class TimeBinning(BarBuilder):
    def __init__(self, bin_size_ms: int, emit_partial: bool = True):
        ...

class VolumeBinning(BarBuilder):
    def __init__(self, volume_btc: float):
        ...

class AdaptiveBinning(BarBuilder):
    def __init__(self, vol_window_ms: int, target_bars_per_sec: int):
        ...
```

**Как это работает:**
- Live/Paper: каждый tick → BarBuilder.on_tick → обновляет partial bar → emits `is_update` → BarEvent доходит до strategy.on_bar. Когда time crosses bin boundary → `is_final` BarEvent.
- Backtest: читаем тики из parquet → feed в BarBuilder → по умолчанию только `is_final` events (скорость). Опционально `replay_ticks=True` → все `is_update` events тоже (для byte-identical parity с live).
- Monte Carlo: deterministic replay с seed.

**Тики полностью скрыты от стратегии.** Стратегия не знает, было ли 1 или 1000 тиков в баре.

---

## 5. Run — first-class object (не режимы приложения)

### Модель

```sql
strategy_runs(
  run_id         TEXT PK,        -- uuid
  strategy_name  TEXT,            -- = имя ноутбука = имя .py
  strategy_hash  TEXT,            -- sha256 файла .py
  version        TEXT,            -- атрибут класса
  run_type       TEXT,            -- 'backtest' | 'paper' | 'live' | 'shadow' | 'research'
  params_json    TEXT,            -- effective params (default + override)
  session_id     TEXT NULL,       -- для backtest/research
  started_at_ms  INTEGER,
  ended_at_ms    INTEGER NULL,
  status         TEXT,            -- 'running' | 'completed' | 'failed' | 'killed' | 'swapped'
  outcome_json   TEXT NULL        -- final stats, error reason, etc.
)
```

### UI: нет «переключения режима приложения»

**Главные страницы приложения** (и всё):
- **Home** — Dashboard: статус всего (uptime, CPU/RAM, last data session, active runs, live market mini-chart).
- **Data** — Collector, Quality, Live Market Chart (см. §6).
- **Lab** — link to JupyterLab + Explorer events (research signal analysis).
- **Strategies** — список всех `.py` стратегий (матчинг с `.ipynb`), для каждой: последний backtest sparkline, список её Runs.
- **Runs** — **универсальная таблица всех запусков** любого типа (backtest/paper/live/shadow/research) с фильтрами: по стратегии, по типу, по статусу, по дате. Клик → детальная страница Run-а.
- **Live Ops** — панель для ACTIVE running live/paper runs: positions, orders, risk, kill, **manual interventions**.

«Запустить стратегию» → модалка New Run:
- Select Strategy (dropdown)
- Select Type: Backtest / Paper / Shadow / Live (с confirmation) / Research
- Select Session (если backtest/research)
- Params override (optional)
- For Live: mandatory checkbox «I confirm live trading, max exposure X BTC»
- [Run]

**Нет отдельных «paper-приложений» и «live-приложений».** Одно приложение, один UI, разные типы Run-ов.

---

## 6. Live Price Chart — reusable component

```
<LivePriceChart
  venues=["OKX Perp", "Bybit Perp", "Lighter Perp", ...]
  time_range="5m"
  show_bbo_band={true}
  show_signals_from_run={run_id_optional}
  show_trades_from_run={run_id_optional}
/>
```

**Где используется:**
- **Dashboard** (Home): always visible, последние 5 минут всех venues.
- **Collector page**: большой чарт при активном сборе, видишь рынок глазами.
- **Paper / Live Ops page**: чарт с overlay сигналов и entry/exit живого run-а.
- **Strategies page**: mini-sparkline превью.

**Реализация:**
- Data source: SSE `/events/live_prices` — streaming updates.
- Rendering: Plotly WebGL (`scattergl`) для 12 линий × 6000 точек (5 мин × 20/s).
- Decimation: LTTB при zoom out.
- BBO band: semi-transparent fill между bid и ask (per venue, optional toggle).
- Signal/trade overlay: vertical markers из SSE stream.

**Нагрузка:** 12 линий × 20 точек/с × 5 мин = 72k точек в памяти. WebGL рендерит легко. Obновление: инкрементальное (append last point, drop old).

---

## 7. Manual Position Management

### UI в Live Ops page

**Positions table** (для активного run):

| venue | side | qty | entry | current | unrealized bps | age | SL | TP | Actions |
|---|---|---|---|---|---|---|---|---|---|
| Lighter | long | 0.001 | 68123 | 68141 | +2.6 | 12s | — | — | `Close` `Limit` `SL` `TP` `Reduce` |

**Actions:**
- **Close Now** (market) → confirm modal → Manual Close order.
- **Close at Limit** → modal с price input → Manual Limit Order.
- **Move SL** → input new SL bps → update position metadata.
- **Move TP** → input new TP bps.
- **Reduce** → slider % → Manual partial close.

**Group actions:**
- **Flatten Venue** — закрыть все позиции на venue маркетом.
- **Flatten All** — закрыть все позиции run-а.

### Контракт

```python
@dataclass
class ManualOrder(Order):
    origin: str = "manual"
    operator: str | None = None     # кто нажал (future: auth)
    correlation_id: str | None = None
```

**Flow:**
1. UI POST `/api/runs/{run_id}/positions/{pos_id}/close` → server
2. Server создаёт ManualOrder → RiskEngine check (даже manual проходит через risk для sanity) → Executor.submit
3. WAL запись `origin='manual'`
4. Event → OrderStateMachine → strategy.on_order_event(kind="manual_intervention", action="close")

Стратегия может реагировать (например, перестать открывать новые после интервенции) но НЕ может отменить manual — user override имеет приоритет.

### Безопасность

- Manual action требует confirm модалку.
- Flatten All требует input phrase «FLATTEN».
- Rate limit: не более 10 manual actions/мин (защита от кликера).
- Audit log: всё в `manual_actions_log` таблице.

---

## 8. Хранилища

| Данные | Формат | Путь | Почему |
|---|---|---|---|
| Тики | Parquet, per venue per date, 30-мин ротация | `data/ticks/YYYY-MM-DD/<venue>/ticks_*.parquet` | Bulk, колонный, DuckDB predicate pushdown |
| BBO | Parquet, per venue per date | `data/bbo/YYYY-MM-DD/<venue>/bbo_*.parquet` | То же |
| Пре-вычисленные 50ms бары | Parquet, per venue per date | `data/bars/50ms/YYYY-MM-DD/<venue>/bars_*.parquet` | 5-10× ускорение бэктеста |
| Сигналы стратегии | Parquet, per strategy per run | `data/strategies/<name>/signals/<run_id>.parquet` | Explorer, append-only |
| Сессии анализа | JSON/msgpack | `data/sessions/<id>/*.json` | Baseline research артефакты |
| Результаты бэктеста | JSON | `data/backtest/<run_id>/*.json` | UI |
| **Operational state** | **SQLite WAL** | `data/state.db` | Orders/positions/runs/fills/kill_events/manual_actions |
| Strategies | `.py` | `data/strategies/*.py` | Источник истины |
| Notebooks | `.ipynb` | `notebooks/*.ipynb` | Матчинг по имени со стратегиями |
| Configs | YAML | `config/*.yaml` | Human-editable |
| IPC status | atomic JSON | `data/.{collector,run_<id>}_status.json` | UI polling fallback |

**DuckDB поверх Parquet** для бэктеста и Explorer. **aiosqlite** для state.

---

## 9. Единый event loop

```python
async def run(source, strategy, executor, risk, reconciler, dq_gate,
              manual_api, observability, ctx):
    strategy.setup(ctx)
    bar_builder = strategy.bar_builder

    async for event in source.stream():
        dq_gate.observe(event)
        ctx.data_quality = dq_gate.snapshot()

        if event.kind == "tick":
            # BarBuilder consumes ticks, produces BarEvents
            bar_events = bar_builder.on_tick(event)
            for be in bar_events:
                snap = ctx.snapshot_bars(be)
                signals = ctx.collect_emits(lambda: strategy.on_bar(snap, ctx))
                for sig in signals:
                    signal_store.append(sig)
                    if hasattr(strategy, "on_signal") and ctx.run_type != "research":
                        if (order := strategy.on_signal(sig, ctx)):
                            decision = await risk.check(order, ctx)
                            if decision.accept:
                                await executor.submit(order)
                            else:
                                observability.counter("risk_rejects").inc(
                                    labels={"reason": decision.reason})

        elif event.kind == "bbo":
            ctx.bbo.update(event.venue, event.snapshot)

        elif event.kind == "manual":
            order = manual_api.build_order(event)
            decision = await risk.check(order, ctx)
            if decision.accept:
                await executor.submit(order)
                strategy.on_order_event(ManualEvent(...), ctx)

        elif event.kind == "order_event":
            await order_sm.apply(event)
            strategy.on_order_event(event, ctx)

        elif event.kind == "reconcile":
            await reconciler.check(ctx)
```

**Один цикл.** `source`, `executor`, `reconciler` — зависят от `run_type`. Остальное идентично.

| Run type | Source | Executor | Reconciler | Bar replay |
|---|---|---|---|---|
| `backtest` | ParquetSource | Simulated | off | finals only (default) |
| `research` | ParquetSource | — (orders ignored) | off | finals only |
| `paper` | LiveFeedSource | Simulated | simulated | finals + updates |
| `shadow` | LiveFeedSource | Simulated (logs "would have") | off | finals + updates |
| `live` | LiveFeedSource | Live | real | finals + updates |

---

## 10. Real trading stack

### 10.1 Executor (Live)

Per-venue adapter с общим интерфейсом: `submit(order, client_order_id)`, `cancel(cid)`, `query_order(cid)`, `fetch_positions()`, `stream_order_events()`, `round_qty/price`.

### 10.2 Order lifecycle

```
PENDING_SEND → SENT → ACCEPTED → (PARTIAL*) → FILLED
                       └───────→ REJECTED
                       └───────→ CANCELLED
```

**WAL-before-send:** SQLite пишет `PENDING_SEND` с `client_order_id=uuid` до отправки. На crash recovery — query exchange.

### 10.3 RiskEngine

Один async mutex. Проверяет (все пути, включая manual):
- Max venue exposure
- Daily loss limit
- Rate limit per venue (leaky bucket)
- Reject cooldown
- Testnet/prod consistency

### 10.4 PositionReconciler

Каждые 30s: `adapter.fetch_positions()` vs SQLite. Grace window 5s. Mismatch → kill level Orange + alert.

### 10.5 KillSwitch (градиент)

| Level | Триггеры | Действия |
|---|---|---|
| **Green** | норма | работает |
| **Yellow** | DQ degraded ≥60s, 3 reject/60s | не открывает новые; существующие по SL/TP/hold |
| **Orange** | DQ degraded ≥5 min, reconciler mismatch | graceful exit лимитными ордерами |
| **Red** | manual kill, unresolvable mismatch, daily_loss_limit | market close всех, cancel pending, stop run |

### 10.6 Graceful swap

1. v2 в shadow (тот же feed, виртуальные ордера).
2. UI diff: сигналы/what-if ордера v1 vs v2.
3. Commit → v1 не открывает новые → ждём закрытия → v2 берёт feed.

---

## 11. UI performance

### Почему не Flutter

- Plotly.js для финансовых чартов — зрелое; Flutter аналоги слабее.
- Локальное приложение одного пользователя — нативность не даёт ничего.
- 3 месяца миграции блокирует прогресс.
- SolidJS+WebGL+Worker = ~95% производительности Flutter за 5% усилий.

### Выбранный стек (без build-step)

```html
<!-- index.html -->
<script type="importmap">{
  "imports": {
    "solid-js": "https://esm.sh/solid-js@1.8/dist/solid.js",
    "solid-js/web": "https://esm.sh/solid-js@1.8/web/dist/web.js",
    "msgpack": "https://esm.sh/@msgpack/msgpack@3",
    "plotly.js-gl2d-dist": "https://cdn.plot.ly/plotly-gl2d-2.34.0.min.js"
  }
}</script>
<script type="module" src="/ui/app.js"></script>
```

### Меры ускорения (итоговые)

| Мера | Effект |
|---|---|
| Plotly WebGL (`scattergl`) | 10× больших датасетов |
| Virtual scrolling (event list, trades table) | N× для длинных таблиц |
| Web Worker для парсинга msgpack + обработки | Main thread свободен |
| SSE для live (Prices, Events, Orders) | 0 задержка |
| LTTB decimation при zoom out | 10-50× рендера |
| Lazy loading price_windows | Instant initial load |
| MessagePack binary protocol | 3-5× меньше, 2× parse |
| SolidJS fine-grained reactivity | 2-5× vs vanilla re-render |
| HTTP/2 + brotli (uvicorn flag) | 3-5× throughput |
| IndexedDB cache для historical data | Instant повторный load |

### Что рендерим через WebGL

- Live Price Chart (12 venues × 5 min).
- Explorer main charts (leader + follower windows).
- Backtest equity curve (10k points + trade markers).
- Monte Carlo fan chart (1000 lines).

### Что через virtual scroll

- Events list (500-5000).
- Trades table (100-1000 per backtest).
- Orders table, Logs.

### Ожидаемая производительность

- Open Explorer с сессией 500 events: **~500 ms** (было: 2-5 s).
- Filter events: **<50 ms** (было: 500 ms).
- Swap event в chart: **<100 ms** (было: 500 ms).
- Live Price Chart update: **60 fps** с 72k точек.
- Backtest page initial render: **<300 ms**.

---

## 12. Notebook ↔ Strategy binding (get_notebook_name pattern)

### Один идентификатор везде

```python
# В пакете leadlag:
from leadlag.notebook import get_notebook_name

def get_notebook_name() -> str:
    """Return current notebook name from Jupyter kernel session file."""
    runtime_dir = Path(os.environ.get('JUPYTER_RUNTIME_DIR',
                                        '~/.jupyter/runtime')).expanduser()
    for session_file in runtime_dir.glob('kernel-*.json'):
        try:
            data = json.loads(session_file.read_text())
            sess = data.get('jupyter_session', '')
            if sess and '.ipynb' in sess:
                return Path(sess).stem
        except Exception:
            continue
    return "unnamed_strategy"
```

### Workflow

```python
# Cell 2:
STRATEGY_NAME = get_notebook_name()       # "lighter_c_bbo_v2"
print(f"Strategy will be saved as: {STRATEGY_NAME}")
```

```python
# Cell 3:
%%writefile ../data/strategies/{STRATEGY_NAME}.py
from leadlag import Strategy, Order
class LighterCBboV2(Strategy):
    name = "lighter_c_bbo_v2"       # = notebook stem
    ...
```

### Инвариант: один ID на всех уровнях

- Notebook file: `notebooks/lighter_c_bbo_v2.ipynb`
- Strategy file: `data/strategies/lighter_c_bbo_v2.py`
- Strategy.name: `"lighter_c_bbo_v2"`
- Signal log: `data/strategies/lighter_c_bbo_v2/signals/*.parquet`
- Run namespace: `strategy_runs WHERE strategy_name='lighter_c_bbo_v2'`

### UI линковка

Strategies page сканирует `data/strategies/*.py` и `notebooks/*.ipynb` и показывает:
- **Edit in Notebook** (если матчинг `.ipynb` есть) → открывает `http://localhost:8888/lab/tree/notebooks/<name>.ipynb`
- **Create Notebook** (если только `.py`) → генерирует `.ipynb` из шаблона и открывает.

### Защита от коллизий

- Loader проверяет: `Strategy.name == Path(file).stem`. Иначе — warning.
- Два файла с одним `name` → loader ошибка.
- CI lint: scan `.py` файлов, проверяет consistency.

---

## 13. DataQualityGate

```python
@dataclass
class DataQuality:
    overall: str                       # "green" | "yellow" | "red"
    venue_status: dict[str, str]       # per-venue: "ok" | "stale" | "gap" | "outlier"
    gaps_last_min: int
    stale_venues: list[str]
    bbo_divergence_bps: float          # cross-venue spread outlier
    local_time_drift_ms: float

    @property
    def degraded(self) -> bool:
        return self.overall != "green"
```

Пороги в `platform.yaml`: `stale_threshold_ms`, `gap_threshold_ms`, `bbo_divergence_bps`, `time_drift_ms`.

Strategy читает `ctx.data_quality.degraded`; сама решает что делать. Gate тоже может автоматически повысить kill level.

---

## 14. Нагрузка

| Этап | Throughput | Latency | CPU | RAM |
|---|---|---|---|---|
| Collector (12 venues × 300 msg/s) | 3600 msg/s peak | — | 30% 1 core | 300 MB |
| BarBuilder (finals): 50ms × 12 | 240/s | 0.1 ms | <1% | 50 MB |
| BarBuilder (updates, react_to_partial): 1000+/s | ≤ tick rate | 0.05 ms | 1-3% | — |
| Strategy on_bar | 240-3600/s | 0.1-1 ms | <5% | 10 MB |
| Strategy on_signal | 0.01-1/s | 0.1 ms | — | — |
| RiskEngine | = on_signal | 0.1 ms | — | — |
| Executor live | = on_signal | 50-200 ms (сеть) | — | — |
| SQLite WAL write | per order | ~1 ms | — | — |
| DQ gate | = tick rate | O(1) | <1% | — |
| Reconciler | 1/30s | 100-500 ms | 0% | — |
| Backtest 24h (finals only) | 17M bar events | 1-3 min | 1 core | 500 MB |
| Backtest 24h (replay_ticks) | 20M tick events | 5-15 min | 1 core | 500 MB |
| Monte Carlo 1000 runs (trade bootstrap) | — | 10 s | 1 core | 200 MB |
| UI Explorer (WebGL) 500 events | — | 500 ms client | — | 30 MB typed arr |

**Bottleneck в live: сеть до бирж, не CPU.** VPS близко к бирже.

**Backpressure:** bounded `asyncio.Queue(maxsize=10_000)` → drop + counter + DQ deteriorated.

**Disk:** ~4 GB/день суммарно → ~120 GB/мес → 720 GB за 6 мес. Auto-archive на NAS.

---

## 15. UI — страницы приложения

**6 страниц + reusable Live Price Chart:**

### Home
- Global status: uptime, CPU/RAM/Disk/Net sparklines, pings to 12 venues
- Processes state
- **Live Price Chart** (5 min, all venues)
- Active runs cards (paper/live)
- Last data session summary
- Quick actions: Start Collection, New Run, Open Notebook

### Data
- **Collector**: start/stop, venue checklist, live monitor (SSE): ticks/s, BBO/s, reconnects, sparklines per venue, logs. Embedded Live Price Chart.
- **Quality** (`?session=X`): coverage heatmap, gaps, BBO analysis, flags per venue.

### Lab
- **Notebook launcher**: список `notebooks/*.ipynb`, кнопка Open → JupyterLab.
- **Explorer** (`?session=X&strategy=Y`): читает SignalLog research-стратегии; filters; event-centric chart (leader+follower+BBO overlay+lag_50/80); followers table; keyboard nav.

### Strategies
- Таблица всех `.py`: name (с notebook match indicator), version, valid, venues, last backtest sparkline, runs count by type.
- Compare Selected.
- **Edit in Notebook** button (if matched `.ipynb`).
- Run Launcher modal.

### Runs
- **Единая таблица всех запусков** (backtest/paper/live/shadow/research).
- Filters: strategy, type, status, date range.
- Click row → Run Detail page:
  - For backtest: equity (Gross→-Fees→-Slippage→Net), trades, stats, breakdowns, distributions, link to Trade Inspector.
  - For paper/live: live equity (SSE), signals stream, skipped, open positions (с manual actions!), closed trades.
  - For research: SignalLog summary, link to Explorer.
  - For shadow: diff с parent live run.
- **Trade Inspector** (sub-page for click on trade): one trade large, BBO overlay, entry/exit, MFE/MAE, SL/TP, link to Explorer.
- **Monte Carlo** (sub-page): fan, p-value, distributions.

### Live Ops (active runs only)
- Tab **Overview**: live equity, signals/min, key metrics.
- Tab **Positions**: open positions table с **Manual Actions** (Close/Limit/SL/TP/Reduce/Flatten).
- Tab **Orders**: lifecycle timeline, rejects, fills.
- Tab **Risk**: current exposure, daily PnL vs limit, rate limiter state.
- Tab **Kill & Swap**: kill_events log, current level (Green/Yellow/Orange/Red), manual kill button, graceful swap UI.
- **Live Price Chart** with signals/trades overlay.

---

## 16. Косяки и их решения (финальный чеклист)

### Время и данные
1. Canonical `local_ts_ms` + NTP (chrony) + drift monitor.
2. Watermark для late ticks: `bin_size + 100ms`.
3. WS reconnect >5s → venue_status=stale → strategy игнорирует.
4. Forward-fill empty bins — BinBuffer последней ценой.
5. Out-of-order: external merge sort (ParquetSource + DuckDB) / sorted queue в live.
6. Parquet `schema_version` в `_metadata`.

### Исполнение (live)
7. client_order_id + WAL-before-send.
8. Partial fills policy: `cancel_remainder` default.
9. Order rejected: counter + 3/min → defensive.
10. Risk engine mutex.
11. Reconciler grace window 5s.
12. Rate limit per venue (leaky bucket).
13. Venue lot/tick rounding в adapter.
14. Order.time_in_force, post_only, IOC/FOK.
15. Testnet/prod switch в venues.yaml + UI badge.
16. API keys chmod 600, gitignore, logs regex-mask.

### Управление риском
17. Kill switch gradient (Green/Yellow/Orange/Red).
18. Degraded ≥5 min → Orange, не сразу Red.
19. Try/except вокруг callbacks; 3 exceptions/min → stop.
20. Graceful swap через shadow.
21. Hot reload запрещён в live (только swap).
22. Crash recovery: SQLite read → reconcile → start.

### Manual override
23. **Manual Close / Limit / Move SL/TP / Reduce / Flatten** через UI.
24. Manual actions проходят RiskEngine.
25. Audit log `manual_actions` таблица.
26. Rate limit 10 manual/min.
27. Confirmation модалки + Flatten All требует input "FLATTEN".
28. strategy.on_order_event(kind="manual_intervention") для реакции.

### Качество данных
29. DataQualityGate с пороговыми метриками.
30. Cold start warmup из parquet history.

### Операционное
31. Disk monitor + prediction + <10 GB alert.
32. Backup cron: `VACUUM INTO` + rsync daily.
33. WS bounded queue 10k.
34. JupyterLab 127.0.0.1 + token only.
35. Funding rates opt-in `account_funding: bool`.

### Deterministic & testing
36. Golden tests: strategy × session → expected equity (1e-9).
37. Three-mode parity: backtest(finals only) ≡ paper_shadow_replay ≡ live_shadow_replay на сигналах.
38. Synthetic fixtures: `make_synthetic_session()`.
39. CI lint: `Strategy.name == file.stem`.

### UI
40. SolidJS + Plotly WebGL + Worker + msgpack + SSE.
41. Virtual scrolling везде где >100 строк.
42. Lazy loading heavy data.
43. IndexedDB cache.
44. Keyboard shortcuts (H/D/L/S/R/O, ←→ для nav).
45. URL bookmarks stateless.

### Notebook
46. `get_notebook_name()` в пакете.
47. Strategy.name = notebook stem = file stem (CI enforced).
48. UI "Edit in Notebook" button линкует JupyterLab.

---

## 17. Deployment

```
supervisord manages:
├── leadlag-api         (FastAPI + SSE, port 8000)
├── leadlag-collector   (WS + parquet writer daemon)
├── leadlag-monitor     (psutil, pings, .system_history.jsonl)
└── jupyter-lab         (127.0.0.1 + token)

Runs (paper/live/shadow/research) — subprocess, управляется через /api/runs/*
Один active live за раз (v1), один active paper за раз (v1).
```

**OS requirements:** chrony (NTP), ufw (firewall, localhost only external-facing), logrotate, cron (backup).

**Configs:**
- `config/venues.yaml` — biryhi, parsers, fees, lot/tick sizes
- `config/platform.yaml` — DQ thresholds, kill levels, backup paths, API binding
- `config/credentials.yaml` — API keys (chmod 600, gitignore)

**Backup daily:**
```bash
sqlite3 data/state.db "VACUUM INTO '/backup/state-$(date +%F).db'"
rsync -av --delete data/ /nas/leadlag/data/
```

---

## 18. Тестирование

```
tests/
├── unit/             # bar_builder, ema, loader, risk, manual_api, kill_gradient
├── integration/      # backtest_end_to_end, paper_live_parity, crash_recovery,
│                      graceful_swap, manual_intervention_flow
├── synthetic/        # detection_parity (batch vs realtime bar-only)
└── fixtures/         # golden_session_small.parquet, golden_backtest_result.json
```

**CI checks:**
- Unit + integration pass.
- Three-mode parity invariant (backtest-finals ≡ paper-shadow ≡ live-shadow-replay на сигналах).
- Golden backtest regression (1e-9 tolerance).
- `Strategy.name == Path(file).stem` lint.
- mypy + ruff.

---

## 19. Фазы разработки

| Фаза | Длительность | Deliverable |
|---|---|---|
| **1. Core package** | 1-2 нед | `leadlag/` (contracts, bars with unified Bar model, utils, loader, sessions, Parquet I/O, DuckDB, SQLite schema, `get_notebook_name`). |
| **2. Event loop + backtest + simulated executor** | 1 нед | EventLoop, ParquetSource, Sim executor, slippage models, BacktestResult. Golden tests. |
| **3. Web stack + SolidJS UI base** | 1.5 нед | FastAPI + SSE + msgpack, SolidJS bootstrap, Home + Strategies + Runs + Explorer + Backtest + Trade Inspector. |
| **4. Collector daemon + Data + Live Price Chart** | 0.5 нед | WS engine, parquet writer, Collector UI, Quality UI, reusable LivePriceChart. |
| **5. Monte Carlo + Compare + Lab polish** | 0.5 нед | MC, strategy compare, Explorer filters, keyboard nav. |
| **6. Paper + DQ gate + shadow** | 1 нед | LiveFeedSource, DataQualityGate, shadow mode, Paper tab в Runs. |
| **7. Real trading infra** | 2 нед | LiveVenueAdapters (OKX, Bybit, Binance), RiskEngine, OrderStateMachine, Reconciler, KillSwitch gradient, WAL recovery, testnet. |
| **8. Live Ops UI + Manual Interventions** | 1 нед | Live Ops page (Overview, Positions with manual actions, Orders, Risk, Kill & Swap). |
| **9. Hardening + CI parity** | 1 нед | Все косяки §16, three-mode parity в CI, backup, production checklist. |

**~10 недель до production.**

---

## 20. Инварианты

1. **Один класс, один код-путь.** Все Run types используют одни on_bar/on_signal/on_order_event.
2. **Three-mode parity (CI):** backtest-finals ≡ paper-shadow ≡ live-shadow-replay на сигналах.
3. **WAL-before-send.** Нет отправки без записи в SQLite.
4. **client_order_id идемпотентность.** Recovery возможен всегда.
5. **Canonical local clock.**
6. **DQ gate не overridable стратегией.**
7. **Kill gradient, not binary.**
8. **Run type — конфиг запуска, не свойство класса.**
9. **Strategy.name = notebook stem = file stem.**
10. **Стратегия видит только бары.** Тики спрятаны за BarBuilder.
11. **Manual override имеет приоритет над стратегией.**

---

## 21. Что НЕ делаем в v1

- Multi-asset (только BTC).
- Multiple simultaneous live strategies (один live за раз).
- Mobile UI.
- Alerting (Telegram/email) — v2.
- Strategy marketplace.
- Distributed execution.
- ML strategies (только rule-based).
- Cross-venue arb (hedging).
- Authentication (localhost only).

---

## 22. Definition of Done для v1

Пользователь может:

1. Запустить коллектор на 12 venues, видеть Live Price Chart всех venues, ticks/s, pings.
2. В JupyterLab: `STRATEGY_NAME = get_notebook_name()`, написать класс, `%%writefile` — один идентификатор везде.
3. В UI Strategies: увидеть стратегию с матчингом на notebook, кнопка Edit in Notebook.
4. Runs page → New Run → Backtest → результаты в той же таблице Runs.
5. Клик в trade → Trade Inspector (BBO overlay) → View in Explorer.
6. Monte Carlo.
7. New Run → Paper → смотреть live equity + Live Price Chart с signal overlay.
8. New Run → Shadow на параллельной стратегии → сравнение diff.
9. New Run → Live (с confirmation) → реальные ордера; Live Ops page.
10. **Manual Close** одной позиции → проходит через RiskEngine → реконсил синхронизирует.
11. **Flatten All** в аварии.
12. Graceful swap стратегии без потери позиций.
13. Kill switch Red → market close всех → Green после фикса → продолжение.
14. Crash API в середине live → restart → recovery с reconcile → продолжение.
15. UI работает **плавно** (<500ms open, <50ms filter, 60fps live chart).

---

**Это и есть архитектура 10/10.**
