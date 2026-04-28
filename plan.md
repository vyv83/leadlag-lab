Теперь у меня достаточно контекста. Приступаю к написанию полного исправленного ТЗ, интегрируя все 25 решений из критического разбора.

---

# LEADLAG PLATFORM — ПОЛНОЕ ТЕХНИЧЕСКОЕ ЗАДАНИЕ (v4 FINAL — ИСПРАВЛЕННОЕ)

---

## ЧАСТЬ 1: СИНТЕЗИРОВАННОЕ ЗАДАНИЕ ПОЛЬЗОВАТЕЛЯ

**Цель:** Разработать полноценное локальное веб-приложение для алготрейдинга (lead-lag стратегии), которое объединяет в себе весь пайплайн: сбор данных (коллектор), разработку и поиск стратегий, глубокий бэктестинг с графиками и статистикой, детальный просмотр каждой сделки, пейпер-трейдинг и последующий реал-трейдинг.

**Ключевые принципы и требования к архитектуре:**

1. **Jupyter Notebook как лаборатория (неотъемлемая часть приложения):** Разработка стратегии не должна сводиться к настройке YAML-конфигов или простых фильтров на панели. Ноутбук должен предоставлять полноценную возможность исследовать данные и писать произвольную логику на Python (кастомные фильтры волатильности, входы/выходы по BBO-спредам, сложные комбинации лидеров и ведомых).

2. **Связка «Ноутбук – Веб-приложение»:** После того как стратегия (Python-код с фильтрами и логикой) итерационно сформирована в ноутбуке, она сохраняется и бесшовно переносится в веб-приложение. В приложении эта стратегия детально, наглядно и глубоко исследуется с помощью графиков, эквити и тестов Монте-Карло.

3. **Глубокая детализация UI/UX:** Приложение должно стать удобным расширением текущего «костыльного» визуализатора. Требуется исчерпывающая проработка каждого экрана, таблицы и графика отталкиваясь от реальных задач пользователя. Например, на вкладке коллектора необходимо мониторить пинги, количество тиков, обрывы связи, время без обрывов и т.д. Должно быть учтено абсолютно всё, «лучше перебдеть, чем недобдеть».

4. **Формат итогового плана:** Предоставить детальное техническое задание на 10 из 10, жестко критикуя слабые места, продумав стек, пайплайн, контракты данных и пошаговый план разработки для безошибочной постановки задач AI-кодеру.

---

## ЧАСТЬ 2: ТЕХНИЧЕСКОЕ ЗАДАНИЕ

### Философия

Ноутбук — это лаборатория. Там пишется код, экспериментируется, фильтруется, пробуются разные входы/выходы. Результат работы ноутбука — это стратегия-объект (Python-класс с логикой). Не YAML-конфиг, а полноценная Python-логика.

Приложение — это инструмент для всего остального: сбор данных, детальный просмотр событий и сделок, бектест с графиками, пейпер, реал трейдинг. Ноутбук является частью приложения — открывается прямо из интерфейса, работает с теми же данными.

Критика предыдущих итераций: ноутбук нельзя упрощать до "конфига" или "перебора параметров". Визуализатор возник потому что в ноутбуке неудобно смотреть 500 событий детально. HTML explorer — правильное решение, надо развить до полноценного приложения. Третья критическая ошибка — игнорирование механики реального исполнения: спред расширяется на сигнале, маркет-ордер съедает половину спреда (slippage), maker/taker комиссии отличаются. Всё это должно быть видно в UI и заложено в бектест.

Философия в одном предложении: Jupyter — для исследования и написания стратегий; веб-приложение — для всего остального (сбор данных, детальный просмотр, бектест, пейпер, реал трейдинг), и они делят одни данные через Python-пакет `leadlag`.

```
┌─────────────────────────────────────────────────────┐
│                   ПРИЛОЖЕНИЕ                        │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │Коллектор │  │ Explorer │  │ Бектест / Пейпер │   │
│  │ (старт/  │  │ событий  │  │ / Реал трейдинг  │   │
│  │  стоп)   │  │          │  │                  │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │         JupyterLab (встроенный)             │    │
│  │   — исследование данных                     │    │
│  │   — написание стратегии (Python-класс)      │    │
│  │   — экспорт стратегии в приложение          │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

### Стек

- **Backend:** Python 3.11, FastAPI, uvicorn
- **Process management:** supervisord (коллектор, трейдер, монитор, API — независимые процессы)
- **Data:** Parquet (PyArrow/DuckDB для запросов), JSON/JSONL для журналов, .py файлы для стратегий
- **Frontend:** HTML + Plotly.js + vanilla JS (текущий подход — правильный)
- **Jupyter:** JupyterLab, отдельный процесс на порту 8888, открывается в новой вкладке из приложения
- **System monitoring:** psutil (CPU, RAM, Disk, Net), subprocess ping
- **Без:** PostgreSQL, Redis, Docker, React, npm, webpack

---

### Структура проекта

```
leadlag-platform/
│
├── leadlag/                    ← Python-пакет (ядро)
│   ├── venues/                 ← биржи (парсеры, registry)
│   ├── collector/              ← async WS engine
│   ├── analysis/               ← бинирование, детекция, метрики
│   ├── backtest/               ← event-driven бектестер (с slippage/spread)
│   ├── paper/                  ← paper trader
│   ├── live/                   ← реал трейдинг (фаза 6)
│   ├── realtime/               ← real-time детекция событий (для paper/live)
│   │   ├── bin_buffer.py       ← кольцевой буфер 50ms VWAP бинов
│   │   ├── ema_tracker.py      ← инкрементальная EMA: ema = α*price + (1-α)*ema_prev
│   │   ├── detector.py         ← детекция пересечения порога в реальном времени
│   │   └── bbo_tracker.py      ← текущий BBO snapshot для Context
│   ├── strategy.py             ← базовый класс Strategy + Order
│   ├── strategy_loader.py      ← загрузка .py файлов стратегий с валидацией
│   ├── monitor/                ← системный монитор (psutil, pings)
│   └── api/                    ← FastAPI routes
│
├── ui/                         ← HTML/JS фронтенд (9 экранов)
│   ├── index.html              ← dashboard (статус всего + системный монитор)
│   ├── collector.html          ← управление сбором
│   ├── explorer.html           ← event explorer (с BBO overlay)
│   ├── strategy.html           ← список стратегий, сравнение
│   ├── backtest.html           ← результаты бектеста (со slippage breakdown)
│   ├── trade.html              ← одна сделка крупно
│   ├── montecarlo.html         ← Monte Carlo
│   ├── paper.html              ← paper trading
│   └── quality.html            ← data quality по venue
│
├── notebooks/                  ← JupyterLab (исследование)
│   ├── explore.ipynb           ← EDA, поиск паттернов
│   └── strategy_dev.ipynb      ← разработка стратегий
│
├── data/
│   ├── ticks/YYYY-MM-DD/ticks_*.parquet  ← (30мин ротация)
│   ├── bbo/YYYY-MM-DD/bbo_*.parquet      ← (30мин ротация)
│   ├── sessions/               ← результаты анализа
│   ├── strategies/             ← .py файлы стратегий
│   ├── backtest/               ← результаты бектестов
│   ├── paper/                  ← JSONL журналы
│   └── .system_history.jsonl   ← ring buffer метрик системы (24h)
│
├── config/
│   ├── venues.yaml
│   └── platform.yaml
│
└── supervisord.conf            ← управление процессами
```

---

### Контракты между компонентами

**Контракт 1: Сырые данные (коллектор → анализ)**

Коллектор пишет файлы в поддиректории по типу и дате:

```
data/ticks/YYYY-MM-DD/ticks_YYYYMMDD_HHMMSS.parquet
  ts_ms(i64), ts_exchange_ms(i64), price(f64), qty(f64), side(str), venue(str)
  Ротация: каждые 30 минут. 
  Все qty нормализованы в BTC. Поле contract_size в venues.yaml — 
  справочное, в расчётах не используется (пересчёт сделан в парсерах).

data/bbo/YYYY-MM-DD/bbo_YYYYMMDD_HHMMSS.parquet
  ts_ms(i64), bid_price(f64), bid_qty(f64), ask_price(f64), ask_qty(f64), venue(str)
```

Сессия сбора идентифицируется по временной метке первого файла (SESSION_ID = `YYYYMMDD_HHMMSS` из имени файла). Все файлы `ticks_*` и `bbo_*` за один непрерывный сбор принадлежат одной сессии — определяется по времени в именах файлов (сканируются все подпапки `data/ticks/` и `data/bbo/`, разница между последовательными файлами ≤ 30мин + δ).

**Контракт 2: Результат анализа (анализ → UI/бектест)**

Сессия анализа идентифицируется составным ID: `{collection_session_id}_{params_hash}`, где `params_hash` — первые 8 символов SHA256 от JSON-строки параметров анализа (bin_size_ms, ema_span, threshold и т.д.). Это позволяет запускать анализ одних данных с разными параметрами.

```
data/sessions/{session_id}/
  ├── meta.json           # временной диапазон, venues, параметры анализа,
  │                       # params_hash, collection_files[]
  ├── events.json         # все события, каждое содержит:
  │                       #   bin_idx, ts_ms, signal (A/B/C),
  │                       #   direction, magnitude_sigma, leader,
  │                       #   lagging_followers[],
  │                       #   follower_metrics{fol: {lag_50, hit, mfe, mae}},
  │                       #   grid_results{fol: {delay_ms: {hold_ms: {gross, net}}}}
  │                       # НЕ содержит ценовые окна (они в price_windows.json)
  ├── price_windows.json  # VWAP ±10s для каждого события (для графиков)
  │                       #   [{bin_idx, rel_times_ms[],
  │                       #     venues: {venue: [prices]}}]
  ├── bbo_windows.json    # BBO ±10s для каждого события (для overlay на графике,
  │                       #   расчёта slippage в бектесте)
  │                       #   [{bin_idx, rel_times_ms[],
  │                       #     venues: {venue: {bid: [prices], ask: [prices],
  │                       #                      spread_bps: [values]}}}]
  └── quality.json        # покрытие бинов, ticks/s, аномалии по venue
```

Разделение данных: `events.json` содержит ТОЛЬКО метаданные и метрики (без ценовых массивов). `price_windows.json` содержит ценовые окна для графиков. Это предотвращает раздувание events.json до сотен МБ. При загрузке UI сначала грузит events.json (~5-20MB), затем price_windows.json (~50-200MB) лениво при навигации к конкретному событию.

**Контракт 3: Venue Config (config/venues.yaml)**

```yaml
venues:
  - name: "OKX Perp"
    role: leader
    ws_url: "wss://ws.okx.com:8443/ws/v5/public"
    ping_host: "ws.okx.com"
    parser: "parse_okx_trade"
    bbo_parser: "parse_okx_bbo"
    bbo_available: true                 # BBO парсер есть и данные поступают
    subscribe_msg:
      op: subscribe
      args: [{channel: trades, instId: BTC-USDT-SWAP}]
    bbo_subscribe_msg:
      op: subscribe
      args: [{channel: bbo-tbt, instId: BTC-USDT-SWAP}]
    keepalive:
      type: text_ping
      interval: 25
    taker_fee_bps: 5.0
    maker_fee_bps: 2.0
    contract_size: 1.0                  # справочное, qty в parquet уже в BTC
    enabled: true

  - name: "Bybit Perp"
    role: leader
    ws_url: "wss://stream.bybit.com/v5/public/linear"
    ping_host: "stream.bybit.com"
    parser: "parse_bybit_trade"
    bbo_parser: "parse_bybit_bbo"
    bbo_available: true
    subscribe_msg:
      op: subscribe
      args: ["publicTrade.BTCUSDT"]
    bbo_subscribe_msg:
      op: subscribe
      args: ["orderbook.1.BTCUSDT"]
    keepalive:
      type: ws_ping
      interval: 20
    taker_fee_bps: 5.5
    maker_fee_bps: 2.0
    contract_size: 1.0
    enabled: true

  - name: "Binance Perp"
    role: follower
    ws_url: "wss://fstream.binance.com/stream?streams=btcusdt@trade/btcusdt@bookTicker"
    ping_host: "fstream.binance.com"
    parser: "parse_binance_trade"
    bbo_parser: "parse_binance_bbo"
    bbo_available: true
    subscribe_msg: null                 # подписка через URL-параметры
    taker_fee_bps: 4.5
    maker_fee_bps: 2.0
    contract_size: 1.0
    enabled: true

  - name: "Binance Spot"
    role: follower
    ws_url: "wss://stream.binance.com:9443/stream?streams=btcusdt@trade/btcusdt@bookTicker"
    ping_host: "stream.binance.com"
    parser: "parse_binance_trade"
    bbo_parser: "parse_binance_bbo"
    bbo_available: true
    subscribe_msg: null
    taker_fee_bps: 10.0
    maker_fee_bps: 6.0
    contract_size: 1.0
    enabled: true

  - name: "Bybit Spot"
    role: follower
    ws_url: "wss://stream.bybit.com/v5/public/spot"
    ping_host: "stream.bybit.com"
    parser: "parse_bybit_trade"
    bbo_parser: "parse_bybit_bbo"
    bbo_available: true
    subscribe_msg:
      op: subscribe
      args: ["publicTrade.BTCUSDT"]
    bbo_subscribe_msg:
      op: subscribe
      args: ["orderbook.1.BTCUSDT"]
    keepalive:
      type: ws_ping
      interval: 20
    taker_fee_bps: 10.0
    maker_fee_bps: 6.0
    contract_size: 1.0
    enabled: true

  - name: "MEXC Perp"
    role: follower
    ws_url: "wss://contract.mexc.com/edge"
    ping_host: "contract.mexc.com"
    parser: "parse_mexc_trade"
    bbo_parser: null
    bbo_available: false                # BBO НЕ ДОСТУПЕН
    subscribe_msg:
      method: sub.deal
      param: {symbol: BTC_USDT}
    keepalive:
      type: json_ping
      msg: {method: ping}
      interval: 15
    taker_fee_bps: 2.0
    maker_fee_bps: 0.0
    contract_size: 0.0001              # справочное, пересчёт в парсере
    enabled: true

  - name: "Bitget Perp"
    role: follower
    ws_url: "wss://ws.bitget.com/v2/ws/public"
    ping_host: "ws.bitget.com"
    parser: "parse_bitget_trade"
    bbo_parser: "parse_bitget_bbo"
    bbo_available: true
    subscribe_msg:
      op: subscribe
      args: [{instType: USDT-FUTURES, channel: trade, instId: BTCUSDT}]
    bbo_subscribe_msg:
      op: subscribe
      args: [{instType: USDT-FUTURES, channel: books1, instId: BTCUSDT}]
    keepalive:
      type: text_ping
      interval: 30
    taker_fee_bps: 6.0
    maker_fee_bps: 2.0
    contract_size: 1.0
    enabled: true

  - name: "Gate Perp"
    role: follower
    ws_url: "wss://fx-ws.gateio.ws/v4/ws/usdt"
    ping_host: "fx-ws.gateio.ws"
    parser: "parse_gate_trade"
    bbo_parser: null
    bbo_available: false                # BBO НЕ ДОСТУПЕН
    subscribe_msg: DYNAMIC
    subscribe_factory: "make_gate_subscribe"
    keepalive:
      type: json_ping
      msg: {channel: futures.ping}
      interval: 15
    taker_fee_bps: 5.0
    maker_fee_bps: 2.0
    contract_size: 0.0001              # справочное
    enabled: true

  - name: "Hyperliquid Perp"
    role: follower
    ws_url: "wss://api.hyperliquid.xyz/ws"
    ping_host: "api.hyperliquid.xyz"
    parser: "parse_hyperliquid_trade"
    bbo_parser: null
    bbo_available: false                # BBO НЕ ДОСТУПЕН
    subscribe_msg:
      method: subscribe
      subscription: {type: trades, coin: BTC}
    taker_fee_bps: 3.5
    maker_fee_bps: 1.0
    contract_size: 1.0
    enabled: true

  - name: "Lighter Perp"
    role: follower
    ws_url: "wss://mainnet.zklighter.elliot.ai/stream"
    ping_host: "mainnet.zklighter.elliot.ai"
    parser: "parse_lighter_trade"
    bbo_parser: "parse_lighter_bbo"
    bbo_available: true
    subscribe_msg: DYNAMIC
    subscribe_factory: "make_lighter_subscribe"
    keepalive:
      type: ws_ping
      interval: 60
    taker_fee_bps: 0.0
    maker_fee_bps: 0.0
    contract_size: 1.0
    enabled: true

  - name: "edgeX Perp"
    role: follower
    ws_url: "wss://quote.edgex.exchange/api/v1/public/ws"
    ping_host: "quote.edgex.exchange"
    parser: "parse_edgex_trade"
    bbo_parser: "parse_edgex_bbo"
    bbo_available: true
    subscribe_msg:
      type: subscribe
      channel: "trades.10000001"
    bbo_subscribe_msg:
      type: subscribe
      channel: "bookTicker.all.1s"
    keepalive:
      type: edgex_pong
    taker_fee_bps: 2.6
    maker_fee_bps: 1.0
    contract_size: 1.0
    enabled: true

  - name: "Aster Perp"
    role: follower
    ws_url: "wss://fstream.asterdex.com/ws/btcusdt@aggTrade/btcusdt@bookTicker"
    ping_host: "fstream.asterdex.com"
    parser: "parse_aster_trade"
    bbo_parser: "parse_aster_bbo"
    bbo_available: true
    subscribe_msg: null
    taker_fee_bps: 2.0
    maker_fee_bps: 0.5
    contract_size: 1.0
    enabled: true
```

Парсеры остаются в Python (`leadlag/venues/parsers.py`) — YAML ссылается на имя функции. При добавлении новой биржи: добавить парсер в `parsers.py` + строку в `venues.yaml`. Перезапустить collector.

**Биржи БЕЗ BBO (bbo_available: false): MEXC Perp, Gate Perp, Hyperliquid Perp.**

Политика fallback при отсутствии BBO:
- Стратегия с `slippage_model='half_spread'` или `'full_spread'` на venue без BBO → автоматический fallback на `fixed_slippage_bps` (параметр стратегии, default=1.0 bps)
- В логе бектеста/пейпера предупреждение: "BBO not available for {venue}, using fixed slippage={N}bps"
- `ctx.bbo[venue]` для venue без BBO возвращает `BboSnapshot(available=False, spread_bps=None)`
- Стратегия, фильтрующая по `ctx.bbo[venue].spread_bps`, должна проверять `ctx.bbo[venue].available`

**Контракт 4: Стратегия (ноутбук → бектест/пейпер/реал)**

**КАНОНИЧЕСКОЕ ИМЯ МЕТОДА: `on_event()`** (не `generate_signal()`). Везде в коде, документации и примерах используется только `on_event`.

```python
# data/strategies/lighter_c_v1.py
from leadlag import Strategy, Order, Event, Context

class LighterCv1(Strategy):
    name = "lighter_c_v1"
    version = "2026-04-11"
    description = "Lighter Perp на Signal C, hold 30s, BBO filter"
    
    # Параметры — видны в UI, могут быть переопределены при запуске бектеста
    params = {
        'min_magnitude': 2.0,
        'hold_ms': 30000,
        'max_bbo_spread_bps': 2.0,       # Не входим если спред шире
        'entry_type': 'market',           # 'market' или 'limit'
        'slippage_model': 'half_spread',  # 'none', 'fixed', 'half_spread', 'full_spread'
        'fixed_slippage_bps': 1.0,        # fallback если BBO недоступен, или slippage_model='fixed'
        'position_mode': 'reject',        # 'reject' | 'stack' | 'reverse'
        'stop_loss_bps': None,            # None = отключен
        'take_profit_bps': None,          # None = отключен
    }
    
    def on_event(self, event: Event, ctx: Context) -> Order | None:
        """
        Вызывается и при бектесте, и при paper/live.
        event: детектированное событие
        ctx:   snapshot VWAP и BBO на момент события
        
        Возвращает Order для входа в сделку, или None для пропуска.
        """
        if event.signal != 'C':
            return None
        if 'Lighter Perp' not in event.lagging_followers:
            return None
        
        # BBO фильтр с проверкой доступности
        bbo = ctx.bbo.get('Lighter Perp')
        if bbo and bbo.available and bbo.spread_bps > self.params['max_bbo_spread_bps']:
            return None
        
        if event.magnitude_sigma < self.params['min_magnitude']:
            return None
        
        return Order(
            venue='Lighter Perp',
            side='buy' if event.direction > 0 else 'sell',
            qty_btc=0.001,
            entry_type=self.params['entry_type'],
            hold_ms=self.params['hold_ms'],
            stop_loss_bps=self.params.get('stop_loss_bps'),
            take_profit_bps=self.params.get('take_profit_bps'),
        )
```

Один и тот же файл, один и тот же метод `on_event()` — используется везде: в честном бектесте, в paper trader, в реал трейдинге. Никакой разницы в логике.

**Order dataclass:**

```python
@dataclass
class Order:
    venue: str
    side: str                          # 'buy' | 'sell'
    qty_btc: float
    entry_type: str = 'market'         # 'market' | 'limit'
    hold_ms: int = 30000
    stop_loss_bps: float | None = None     # SL в bps от entry, None = отключен
    take_profit_bps: float | None = None   # TP в bps от entry, None = отключен
```

**Логика выхода (приоритет):** SL/TP > hold_ms. Если SL или TP сработали до истечения hold_ms — позиция закрывается немедленно. Если не сработали — закрытие по hold_ms.

**Position management:** Режим определяется параметром `position_mode` в стратегии:
- `'reject'` (по умолчанию): если уже есть открытая позиция на этом venue — новый сигнал пропускается. В signals.jsonl записывается `action: "skip"`, `skip_reason: "position_already_open"`.
- `'stack'`: позиции накапливаются. long + long = 2x long. Каждая позиция закрывается независимо по своему hold_ms/SL/TP.
- `'reverse'`: при противоположном сигнале — закрытие текущей + открытие новой. При одинаковом направлении — reject.

**Контракт 5: Результат бектеста (бектест → UI)**

```
data/backtest/{strategy_name}_{timestamp}/
  ├── meta.json        # стратегия, период, параметры (включая slippage_model, entry_type),
  │                    # params_override (если были)
  ├── trades.json      # каждая сделка:
  │                    #   trade_id, signal_bin_idx, signal_type, direction,
  │                    #   magnitude_sigma, venue,
  │                    #   entry_ts_ms, exit_ts_ms,
  │                    #   entry_price_vwap, exit_price_vwap,
  │                    #   entry_price_exec, exit_price_exec,   (с учётом slippage)
  │                    #   slippage_entry_bps, slippage_exit_bps, slippage_total_bps,
  │                    #   spread_at_entry_bps, spread_at_exit_bps,
  │                    #   (spread = null для venue без BBO)
  │                    #   gross_pnl_bps,
  │                    #   fee_entry_bps, fee_exit_bps, fee_total_bps,
  │                    #   fee_type: 'taker'|'maker',
  │                    #   net_pnl_bps,                        (gross - fee - slippage)
  │                    #   hold_ms,
  │                    #   exit_reason: 'hold_expired'|'stop_loss'|'take_profit',
  │                    #   mfe_bps, mae_bps, mfe_time_ms, mae_time_ms,
  │                    #   bbo_spread_at_entry_bps, bbo_spread_at_exit_bps,
  │                    #   bbo_available: true|false,
  │                    #   n_lagging_at_signal, leader_dev_sigma
  ├── equity.json      # equity curve (РАСШИРЕННАЯ СХЕМА — 6 полей):
  │                    #   ts_ms, gross_equity_bps, post_fee_equity_bps,
  │                    #   net_equity_bps, drawdown_bps, trade_id
  ├── stats.json       # ВСЕ метрики (описаны ниже в Backtest UI)
  └── montecarlo.json  # результаты MC: N симуляций equity curves
```

**Именование PnL полей:**
- `net_pnl_bps` — в `trades.json`, означает PnL **одной сделки** (gross - fee - slippage)
- `total_net_pnl_bps` — в `stats.json`, означает **суммарный** PnL всех сделок
- `avg_trade_bps` — в `stats.json`, означает **средний** PnL за сделку

`signal_bin_idx` в каждой сделке — это ключевая связь. Кликаешь на сделку в `backtest.html` → переходишь в `explorer.html` и видишь то событие, ту сделку, с entry/exit отметками на графике.

**Модели проскальзывания (Slippage) в бектестере:**

| Модель | Формула | Когда использовать |
|--------|---------|-------------------|
| `none` | 0 bps | Идеалистичный бектест |
| `fixed` | N bps (параметр стратегии `fixed_slippage_bps`, default=1.0) | Быстрая оценка |
| `half_spread` | BBO spread / 2 на момент entry. **Если BBO недоступен → fallback на `fixed_slippage_bps`** | Реалистичный для market (**по умолчанию**) |
| `full_spread` | BBO spread на момент entry. **Если BBO недоступен → fallback на `fixed_slippage_bps`** | Пессимистичный для market |
| `custom` | Python функция в стратегии | Продвинутый |

Расчёт PnL в бектесте: **Net PnL = Gross PnL - Fee (round trip) - Slippage (round trip)**

- `entry_type='market'`: fee = taker_fee × 2, slippage = по модели (half_spread по умолчанию)
- `entry_type='limit'`: fee = maker_fee × 2, slippage = 0, НО: fill probability model

**Модель заполнения лимитных ордеров:**

```python
# Заполняется если цена касалась уровня лимитного ордера
# в течение первых 30% от hold_ms
LIMIT_FILL_WINDOW_PCT = 0.3  # 30% от hold_ms

# Для каждого лимитного ордера:
fill_window_ms = hold_ms * LIMIT_FILL_WINDOW_PCT
# Смотрим бины от entry до entry + fill_window_ms:
# Если цена в этом окне касалась entry_price → fill, hold начинается с момента fill
# Если цена НЕ касалась → сделка НЕ состоялась (не считается в статистике)

# fill_probability: бинарная (заполнился / нет), без рандома
# slippage для лимитных: 0 bps (по определению)
# В stats.json: by_entry_type.limit.avg_slippage_bps всегда = 0
# В stats.json: by_entry_type.limit.fill_rate = доля заполнившихся от общего числа попыток
```

---

### Секция: Real-time Pipeline (для Paper/Live Trading)

Весь описанный выше анализ (бинирование → EMA → детекция) работает в batch-режиме по parquet-файлам. Для paper/live trading необходим **инкрементальный конвейер** реального времени, реализованный в `leadlag/realtime/`:

**bin_buffer.py — кольцевой буфер 50ms VWAP:**

```python
class BinBuffer:
    """Кольцевой буфер, накапливающий тики и формирующий VWAP за 50ms бины.
    
    При получении тика:
    1. Определяет bin_idx = (tick.ts_ms - session_start) // BIN_SIZE_MS
    2. Накапливает price*qty и qty для текущего бина
    3. Когда новый тик приходит в следующий бин — финализирует предыдущий:
       vwap = sum(price*qty) / sum(qty), или last known price если qty=0
    4. Хранит последние N бинов (N=EMA_SPAN*3) в кольцевом буфере
    
    Для каждого venue — отдельный BinBuffer.
    """
    def __init__(self, bin_size_ms: int = 50, buffer_size: int = 600):
        ...
    
    def add_tick(self, ts_ms: int, price: float, qty: float) -> float | None:
        """Добавить тик. Вернуть finalized VWAP если бин завершён, иначе None."""
        ...
    
    def current_vwap(self) -> float:
        """Текущая VWAP (незавершённый бин или последний завершённый)."""
        ...
```

**ema_tracker.py — инкрементальная EMA:**

```python
class EmaTracker:
    """Инкрементальная EMA, обновляемая при каждом новом бине.
    
    Формула: ema_new = α * price + (1 - α) * ema_prev
    где α = 2 / (span + 1)
    
    Это математически эквивалентно pandas.ewm(span=N),
    но вычисляется инкрементально за O(1) на бин.
    """
    def __init__(self, span: int = 200):
        self.alpha = 2.0 / (span + 1)
        self.ema = None
        self.n_updates = 0
    
    def update(self, price: float) -> float:
        """Обновить EMA новым значением, вернуть текущую EMA."""
        if self.ema is None:
            self.ema = price
        else:
            self.ema = self.alpha * price + (1 - self.alpha) * self.ema
        self.n_updates += 1
        return self.ema
    
    @property
    def ready(self) -> bool:
        """True если набрано достаточно точек для стабильной EMA."""
        return self.n_updates >= 200  # EMA_SPAN_BINS * 2
```

**detector.py — детекция пересечения порога:**

```python
class RealtimeDetector:
    """Детектирует lead-lag события в реальном времени.
    
    Для каждого лидера:
    1. Получает новый VWAP бин из BinBuffer
    2. Обновляет EmaTracker
    3. Вычисляет deviation = (vwap - ema) / (sigma * vwap) в σ-единицах
    4. Отслеживает пересечение порога (was_above / is_above)
    5. При пересечении — проверяет followers (аналогично batch)
    6. Формирует Event + Context и передаёт стратегии
    
    sigma вычисляется скользящим окном по последним N бинам 
    (moving стандартное отклонение log-returns).
    """
    def __init__(self, leaders, followers, threshold_sigma=2.0, 
                 fol_max_dev=0.5, ema_span=200, bin_size_ms=50):
        ...
    
    def on_new_bin(self, venue: str, bin_idx: int, vwap: float) -> Event | None:
        """Вызывается при завершении каждого 50ms бина для каждого venue.
        Возвращает Event если обнаружен сигнал, иначе None."""
        ...
```

**bbo_tracker.py — BBO snapshot:**

```python
class BboTracker:
    """Хранит последний BBO snapshot для каждого venue.
    
    Обновляется при каждом BBO сообщении из WebSocket.
    Снимок захватывается в момент детекции события (в detector.py)
    и передаётся в Context стратегии.
    """
    def __init__(self):
        self.snapshots: dict[str, BboSnapshot] = {}
    
    def update(self, venue: str, bid: float, ask: float, 
               bid_qty: float, ask_qty: float):
        ...
    
    def snapshot(self, venue: str) -> BboSnapshot:
        """Получить текущий BBO. Если данных нет → BboSnapshot(available=False)."""
        ...
```

**Latency:** Весь real-time pipeline (от получения тика до вызова `on_event()`) должен работать за < 5ms. Основные затраты: JSON parsing (~0.1ms), bin update (~0.01ms), EMA update (~0.01ms), detector check (~0.1ms).

**Paper trader НЕ создаёт собственные WS-соединения.** Вместо этого коллектор (если запущен параллельно) расшаривает данные через IPC (Unix domain socket или asyncio.Queue в случае in-process). Если коллектор не запущен, paper trader поднимает свои WS-соединения только к venue, нужным стратегии (а не ко всем 12).

---

### Секция: Strategy Lifecycle (save → validate → load → execute)

**Сохранение стратегии из Jupyter:**

Используем `%%writefile` магическую ячейку. Пользователь пишет класс в ячейке, которая сохраняется как .py файл:

```python
%%writefile data/strategies/lighter_c_bbo_filter.py
from leadlag import Strategy, Order, Event, Context

class LighterCBboFilter(Strategy):
    name = "lighter_c_bbo_filter"
    ...
```

Альтернативно, `leadlag` предоставляет хелпер:

```python
from leadlag import save_strategy_source

# source — строка с исходным кодом класса
save_strategy_source("""
from leadlag import Strategy, Order, Event, Context

class LighterCBboFilter(Strategy):
    name = "lighter_c_bbo_filter"
    ...
""", path="data/strategies/lighter_c_bbo_filter.py")
```

Метод `Strategy.save()` НЕ ИСПОЛЬЗУЕТСЯ для сериализации класса из памяти в .py (это технически ненадёжно для Jupyter). Вместо этого `save()` сохраняет **результаты бектеста**: `result.save()`.

**Загрузка стратегии (`leadlag/strategy_loader.py`):**

```python
def load_strategy(path: str) -> Strategy:
    """Загрузить стратегию из .py файла.
    
    1. Проверка синтаксиса: compile(source, path, 'exec')
       → при ошибке: StrategyLoadError с номером строки и сообщением
    
    2. Изолированная загрузка: 
       spec = importlib.util.spec_from_file_location(module_name, path)
       module = importlib.util.module_from_spec(spec)
       spec.loader.exec_module(module)
    
    3. Поиск класса-наследника Strategy в module.__dict__
       → при ошибке: StrategyLoadError("No Strategy subclass found in {path}")
    
    4. Валидация:
       - Есть атрибут 'name' (str, непустой)
       - Есть атрибут 'params' (dict)
       - Есть метод 'on_event' (callable, принимает event + ctx)
       → при ошибке: StrategyValidationError с конкретным описанием
    
    5. Smoke test:
       - Создаём экземпляр: instance = StrategyClass()
       - Вызываем on_event(mock_event, mock_ctx) 
       - Проверяем что результат — Order | None
       → при ошибке: StrategyRuntimeError с traceback
    
    6. Возвращаем экземпляр
    """
    ...

def list_strategies(directory: str = "data/strategies/") -> list[dict]:
    """Сканирует директорию, загружает каждый .py файл,
    возвращает список {name, version, description, params, path, valid, error}.
    Вызывается при каждом GET /api/strategies — для 10-20 стратегий мгновенно.
    """
    ...
```

**Обнаружение новых стратегий/бектестов:** Сканирование директории при каждом API-запросе (`GET /api/strategies`, `GET /api/backtests`). Для 10-20 файлов — мгновенно (< 10ms). Кэширование не нужно.

---

### Секция: URL Contract (навигация между экранами)

Все переходы между экранами используют URL-параметры:

```
# Dashboard
index.html                                          ← главная

# Collector
collector.html                                      ← управление сбором

# Explorer
explorer.html?analysis={analysis_id}                  ← все события анализа
explorer.html?analysis={analysis_id}&event={bin_idx}  ← конкретное событие
explorer.html?analysis={analysis_id}&event={bin_idx}&mode=trade&backtest={bt_id}&trade={n}
                                                    ← событие с метками entry/exit из бектеста

# Strategy List
strategy.html                                       ← все стратегии

# Backtest
backtest.html?id={backtest_id}                      ← результаты бектеста

# Trade Inspector
trade.html?backtest={backtest_id}&trade={trade_id}  ← одна сделка крупно

# Monte Carlo
montecarlo.html?backtest={backtest_id}              ← MC для бектеста

# Paper Trading
paper.html                                          ← paper trading dashboard

# Data Quality
quality.html?id={recording_id}  ← качество данных записи
```

Все параметры — query string. При отсутствии обязательного параметра — UI показывает выбор (dropdown) доступных опций.

---

### Секция: Fallback Policies

**При отсутствии BBO:**
- Venue с `bbo_available: false`: MEXC Perp, Gate Perp, Hyperliquid Perp
- `ctx.bbo[venue]` → `BboSnapshot(available=False, spread_bps=None, bid=None, ask=None)`
- Slippage model `half_spread`/`full_spread` → fallback на `fixed_slippage_bps` (из params стратегии, default 1.0 bps)
- Стратегия с фильтром `max_bbo_spread_bps` на venue без BBO → фильтр НЕ применяется (BBO unknown, разрешаем вход), но в trade записывается `bbo_available: false`
- В логе и UI предупреждение: "⚠️ BBO unavailable for {venue}, used fixed slippage"

**При ошибке загрузки стратегии:**
- `GET /api/strategies` → стратегия появляется в списке с `valid: false`, `error: "описание ошибки"`
- `POST /api/backtests/run` для невалидной стратегии → HTTP 400, `{"error": "Strategy load failed: ..."}`
- В UI невалидная стратегия отображается красным с иконкой ⚠️

**При ошибке `on_event()` во время бектеста/пейпера:**
- Исключение ловится, событие пропускается
- В trades.json записывается: `{...event_info, action: "error", error: "traceback"}`
- Бектест продолжается (не падает)
- В stats.json: `n_errors: N` — количество ошибочных вызовов

---

### UI — 9 экранов (ПОЛНАЯ ДЕТАЛИЗАЦИЯ)

---

#### 1. Dashboard (index.html) — Статус всего + Системный монитор

Весь системный мониторинг встроен прямо на дашборд, компактно. Никакой отдельной вкладки.

**Верхняя панель — глобальный статус**

- Время работы платформы (uptime)
- Текущее UTC время (тикает, с пометкой «UTC»)
- Количество сессий сбора (всего / сегодня)
- Количество стратегий
- Количество бектестов
- Paper trader: running / stopped
- Collector: running / stopped / duration текущей сессии

**Блок "System Health" (компактная строка или 2 строки)**

- CPU: 12% ████░░░░ + sparkline за 1 час (мини-Plotly inline)
- RAM: 4.2/16 GB █████░░░ + sparkline за 1 час
- Disk: 180/500 GB ████████░░ (data/ = 45 GB отдельно подписано)
- Net: ↓ 12 Mbps ↑ 3 Mbps + sparkline за 1 час
- Обновляется каждые 5 секунд

**Блок "Pings to Venues" (компактная таблица, 2 колонки)**

- Для каждой из 12 бирж одна строка:
  - Venue name
  - Ping ms
  - Цвет: <30ms 🟢, 30-60ms 🟡, >60ms или timeout 🔴
- Обновляется каждые 10 секунд
- Если venue disabled — серый

**Блок "Processes & Active Files" (компактно)**

- Процессы (1 строка на процесс):
  - leadlag-api: ✅ running PID 1234 45MB
  - leadlag-collector: ✅ running PID 5678 280MB
  - leadlag-paper: ⏹ stopped
  - leadlag-monitor: ✅ running PID 3456 12MB
  - jupyter-lab: ✅ running PID 9012 512MB
- Активные файлы данных (последние 5):
  - Filename | Size MB | Rows | Time range
  - Ссылка "Show all files" → раскрывается полная таблица
- Total data/ usage: 45.2 GB

**Блок "Collector Status" (если running)**

- Таблица venues (12 строк):
  - Venue name
  - Role (leader/follower)
  - Status icon: зелёный (ok, ticks поступают), жёлтый (reconnecting), красный (dead >60s), серый (disabled)
  - Ticks count с начала сессии
  - Ticks/s (средний за последнюю минуту)
  - BBO count
  - BBO/s
  - Reconnects count за эту сессию
  - Время с последнего reconnect
  - Время с последнего тика (если >10s — жёлтый, >60s — красный)
  - Последняя цена
  - Median price за сессию (проверка адекватности — если далеко от других, красный)
- Итоговая строка: total ticks, total ticks/s, total BBO
- Прогресс-бар: сколько % от запланированного времени прошло
- Кнопки: Start (с настройками), Stop, Restart

**Блок "Последняя сессия анализа"**

- Analysis ID, дата, длительность
- Количество событий (A / B / C)
- Количество зелёных стратегий (net_lo > 0)
- Кнопка "Re-analyze"

**Блок "Paper Trader" (если running)**

- Стратегия: имя, версия
- Время работы
- Equity сегодня (bps)
- Сделок сегодня / hit rate
- Последний сигнал: время, тип, venue, результат
- Кнопка "Open Paper Dashboard"

**Блок "Quick Actions"**

- Start Collection (с popup: выбрать venues, duration)
- Run Analysis (выбрать recording)
- Open Jupyter (ссылка на :8888)
- Open Explorer

---

#### 2. Collector (collector.html)

**Панель управления**

- Статус: Running / Stopped
- Время работы текущей сессии (h:mm:ss тикает)
- Запланированное время
- Кнопки: Start, Stop, Restart

**Настройки запуска (доступны когда stopped)**

- Duration: input в часах (default 12)
- Venues checklist (все 12):
  - Чекбокс вкл/выкл
  - Имя
  - Role
  - Taker fee bps / Maker fee bps (показывает оба)
  - BBO: ✅ / — (bbo_available)
  - WS URL (серым, мелко)
  - Keepalive type
  - Последний известный статус подключения
- Кнопки: Select All Leaders, Select All Followers, Select All
- BIN_SIZE_MS: input (default 50)
- Rotation interval: input в минутах (default 30)

**Live monitor (когда running) — обновляется каждые 2s**

- Расширенная таблица venues:
  - Venue
  - Status (ok / reconnecting / dead)
  - Ticks total
  - Ticks/s (1 min avg)
  - Ticks/s (10 min avg)
  - BBO total
  - BBO/s
  - Reconnects
  - Last reconnect time
  - Last tick ts
  - Seconds since last tick
  - Last error message (если есть)
  - Uptime % (время ok / общее время)
  - Sparkline: ticks/s за последние 10 минут (мини-график в ячейке)

**Лог событий (внизу)**

- Scrollable лог:
  - Timestamp (UTC)
  - Venue
  - Event type: connected, reconnecting, error, writer_flush
  - Message
- Фильтр по venue и типу события
- Auto-scroll (можно отключить)

**Статистика файлов**

- Таблица parquet файлов текущей сессии:
  - Filename
  - Size (KB/MB)
  - Rows
  - Time range
  - Venues в файле
  - Total disk usage

---

#### 3. Explorer (explorer.html)

URL: `explorer.html?analysis={analysis_id}` или `explorer.html?analysis={analysis_id}&event={bin_idx}&mode=trade&backtest={bt_id}&trade={n}`

**Панель фильтров (верх)**

- Signal: кнопки All / A (OKX) / B (Bybit) / C (Confirmed)
- Leader mode: All / OKX only / Bybit only / Confirmed only
- Direction: All / UP / DOWN
- Follower (для нижнего графика): dropdown (все followers)
- Magnitude: range slider (min σ — max σ), показывает текущие значения
- Min lagging followers: slider 1-10
- Time range: от-до (если несколько сессий или длинная сессия)
- Analysis: dropdown (если несколько analyses)
- Кнопка Reset Filters
- Показатель: "Showing X of Y events"

**Список событий (левая колонка, скролл)**

- Для каждого события строка:
  - номер
  - Signal badge (A / B / C цветом)
  - Direction arrow (↑ зелёный / ↓ красный)
  - Magnitude (σ)
  - Time (HH:MM:SS.mmm UTC)
  - N lagging followers
  - Leader name
  - Если есть бектест — иконка "trade" (кликабельна → trade inspector)
- Сортировка: по времени, по magnitude, по количеству lagging
- Текущее выбранное событие подсвечено
- Keyboard navigation: ↑↓ или ←→

**Главный график (правая часть, верхний субплот: leader)**

- X: ms от события (t0 = 0)
- Y: bps от t0
- Линии leader(ов):
  - Если Signal A: только OKX (синий)
  - Если Signal B: только Bybit (оранжевый)
  - Если Signal C: оба (синий + оранжевый)
  - Если All: оба всегда, но неактивный серым
- Вертикальная линия t=0 (красный dash) — момент детекции
- Заливка перед t=0 (полупрозрачная красная) — "до сигнала"
- EMA baseline (тонкая серая линия) — если включено в настройках
- Hover: время (ms), цена (bps), venue name
- Zoom: только по X (горизонтальный), Y автомасштаб

**Главный график (нижний субплот: follower + BBO spread overlay)**

- Линия выбранного follower (зелёный)
- Вертикальная линия t=0
- Вертикальная линия lag_50 (зелёный dot) с подписью "lag50=Xms"
- Вертикальная линия lag_80 (жёлтый dot) с подписью "lag80=Xms"
- **BBO Spread Overlay (по умолчанию включён, toggle для отключения):**
  - Две тонкие линии: bid price и ask price (в bps от t0)
  - Заливка между bid и ask (полупрозрачная серая/красная) — видно расширение спреда в момент сигнала
  - Отдельная мини-ось Y справа: "spread bps"
  - Если venue без BBO → overlay не отображается, показывается плашка "BBO not available for {venue}"
  - Это критично для понимания: можно ли реально зайти в сделку по рыночной цене
- Если режим `mode=trade` (переход из бектеста):
  - Вертикальная линия entry (зелёный solid)
  - Вертикальная линия exit (красный solid)
  - Заливка между entry и exit (зелёная если profit, красная если loss)
  - MFE горизонтальная линия (максимум положительного движения)
  - MAE горизонтальная линия (максимум отрицательного движения)
  - Если SL/TP — горизонтальные пунктирные линии уровней

**Таблица followers (под графиком)**

- Для каждого follower (10 строк):
  - Venue name
  - In signal (✓ если в lagging_followers, dim если нет)
  - Lag 50% (ms)
  - Lag 80% (ms)
  - Hit (✓/✗ + зелёный/красный)
  - MFE (bps, зелёный)
  - MAE (bps, красный)
  - Taker Fee (bps)
  - Maker Fee (bps)
  - BBO available (✓/—)
  - Net at hold=2s, 5s, 10s, 30s (bps, зелёный/красный)
- Клик на строку → переключает follower на нижнем графике
- Выбранный follower подсвечен

**Overlay: все followers на одном графике (toggle)**

- Переключатель "Show all followers"
- Все 10 followers на одном графике разными цветами
- Leader(ы) жирнее, followers тоньше
- Hover показывает все цены

---

#### 4. Strategy List (strategy.html)

URL: `strategy.html`

**Таблица стратегий**

- Для каждой стратегии из data/strategies/ (сканирование при загрузке):
  - Имя
  - Версия (дата)
  - Описание
  - Valid (✅ / ⚠️ с error message)
  - Venues (которые торгует)
  - Signal type (A/B/C/any)
  - Entry type (market/limit)
  - Slippage model
  - Position mode (reject/stack/reverse)
  - Последний бектест:
    - Дата
    - N сделок
    - Total Net PnL (bps)
    - Avg trade (bps)
    - Hit rate %
    - Sharpe
    - Max drawdown (bps)
    - Equity curve sparkline (мини-график в ячейке)
  - Статус: has_backtest / has_paper / has_live
  - Кнопки: Run Backtest, View Backtest, Run Paper, Delete

**Сравнение стратегий**

- Чекбокс у каждой стратегии → выбрать 2-5 для сравнения
- Кнопка "Compare Selected"
- Таблица сравнения:
  - Метрики рядом: Sharpe, Max DD, Win Rate, Profit Factor, Avg Trade, N Trades, Fee Impact, Slippage Impact
  - Equity curves на одном графике (разные цвета)
  - Overlap сделок на timeline (видно когда стратегии торгуют одновременно)

**Создание стратегии из UI (простой режим)**

- Для тех случаев когда стратегия — простой набор фильтров без кастомного Python:
  - Leader mode: dropdown
  - Signal: checkboxes A/B/C
  - Threshold σ: slider
  - Followers: checkboxes
  - Delay: dropdown
  - Hold: dropdown
  - Entry type: market / limit (radio)
  - Slippage model: dropdown (none/fixed/half_spread/full_spread)
  - Fixed slippage bps: input (если slippage_model=fixed или fallback)
  - Max BBO spread bps: input (optional)
  - Stop loss bps: input (optional)
  - Take profit bps: input (optional)
  - Position mode: dropdown (reject/stack/reverse)
  - Кнопка Save → генерирует .py файл, прогоняет через strategy_loader.load_strategy() для валидации

---

#### 5. Backtest (backtest.html)

URL: `backtest.html?id={backtest_id}`

**Хедер**

- Стратегия: имя, версия
- Сессия данных: ID, дата, длительность
- Параметры стратегии (из .py файла params dict, включая entry_type, slippage_model)
- Params override (если были применены при запуске)
- Время расчёта бектеста

**Equity Curve (главный график)**

- X: время (UTC)
- Y1 (верхний): cumulative PnL (bps)
  - **Переключатель слоёв:** Gross → Gross-Fees → Gross-Fees-Slippage → Net
    - Видно вклад каждого компонента: серая линия (gross), оранжевая (после fees), красная (после slippage) = net
    - Данные берутся из equity.json: gross_equity_bps, post_fee_equity_bps, net_equity_bps
    - Это критично: если gross equity красивая, но net плоская — значит fees/slippage съедают всё
  - Точки: каждая сделка (зелёная если profit, красная если loss)
  - Размер точки пропорционален magnitude сделки
  - Клик на точку → `trade.html?backtest={id}&trade={n}`
- Y2 (нижний, мелкий): drawdown curve
  - Заливка от 0 до drawdown (красная)
  - Горизонтальная линия max drawdown
- Hover: дата, equity bps, drawdown bps, trade details если над точкой

**Таблица сделок**

- Полный список всех сделок:
  - номер
  - Time (UTC, HH:MM:SS.mmm)
  - Signal (A/B/C badge)
  - Direction (↑/↓)
  - Magnitude (σ)
  - Venue (follower)
  - Entry price (VWAP)
  - Entry price (Exec — с учётом slippage)
  - Exit price
  - Exit reason (hold_expired / stop_loss / take_profit)
  - Gross PnL (bps)
  - Fee (bps, с указанием maker/taker)
  - Slippage (bps) — если BBO unavailable, пометка "(fixed fallback)"
  - Net PnL (bps, после fees + slippage)
  - Spread at entry (bps) — или "N/A" для venue без BBO
  - Spread at exit (bps) — или "N/A"
  - Hold time (actual ms)
  - MFE (bps)
  - MAE (bps)
  - Entry-to-MFE time (ms)
  - Hit (✓/✗)
- Кнопка "Inspect" → `trade.html?backtest={id}&trade={n}`
- Кнопка "View Event" → `explorer.html?analysis={analysis_id}&event={bin_idx}`
- Сортировка по любому столбцу
- Фильтр: по signal, по venue, по PnL (profit only / loss only)
- Цветовая кодировка строк: зелёный фон для profit, красный для loss
- Итоговая строка: суммы, средние

**Статистика (карточки)**

- Total Net PnL (bps) — `total_net_pnl_bps`
- Total Net PnL (USD, при заданном размере позиции)
- Number of Trades
- Win Rate (%)
- Profit Factor (gross wins / gross losses)
- Sharpe Ratio (annualized или per-trade)
- Max Drawdown (bps)
- Max Drawdown Duration (ms)
- Average Trade (bps) — `avg_trade_bps`
- Average Win (bps)
- Average Loss (bps)
- Best Trade (bps)
- Worst Trade (bps)
- Average Hold Time (ms)
- Average MFE (bps)
- Average MAE (bps)
- MFE/MAE Ratio
- Trades per Hour
- Consecutive Wins (max streak)
- Consecutive Losses (max streak)
- **Fee & Slippage Impact:**
  - Total Gross PnL (bps)
  - Total Fees (bps)
  - Total Slippage (bps)
  - Total Net PnL (bps)
  - Fee % of Gross (какой % от gross equity съели комиссии)
  - Slippage % of Gross (какой % съело проскальзывание)
- **By Entry Type:**
  - Market: N trades, avg fee bps, avg slippage bps, win rate
  - Limit: N trades, avg fee bps, fill rate %, win rate
- **By Spread Bucket at Entry:**
  - 0-1 bps: N trades, avg net PnL, win rate
  - 1-2 bps: N trades, avg net PnL, win rate
  - 2-5 bps: N trades, avg net PnL, win rate
  - \>5 bps: N trades, avg net PnL, win rate
  - N/A (BBO unavailable): N trades, avg net PnL, win rate
  - Видно: прибыльны ли сделки при широком спреде, или только при узком

**Распределения (5 мини-графиков)**

- Гистограмма PnL per trade (bps) — с нормальным наложением
- Гистограмма hold times (ms)
- Scatter: magnitude σ vs trade PnL (есть ли корреляция?)
- Scatter: time of day (UTC) vs trade PnL (есть ли временные паттерны?)
- Scatter: spread at entry bps vs trade PnL — есть ли влияние спреда на результат?

**По venue (если стратегия торгует несколько followers)**

- Таблица: venue → N trades, win rate, avg PnL, sharpe, avg spread, avg slippage
- Equity curve per venue (на одном графике)

**По signal type**

- Таблица: signal → N trades, win rate, avg PnL
- Если стратегия использует A+B+C — видно какой тип лучше

---

#### 6. Trade Inspector (trade.html)

URL: `trade.html?backtest={backtest_id}&trade={trade_id}`

**Хедер**

- Сделка #N из #Total
- Стратегия: имя
- Signal: A/B/C
- Direction: UP/DOWN
- Magnitude: σ
- Result: +X.XX bps (зелёный) или -X.XX bps (красный)
- Exit reason: hold_expired / stop_loss / take_profit
- Кнопки: ← Prev, Next →
- Кнопка: "View in Explorer" → `explorer.html?analysis={id}&event={bin_idx}`

**Верхний график: Leader**

- X: ms от события
- Y: bps от t0
- Leader price(s):
  - Signal A: OKX
  - Signal B: Bybit
  - Signal C: оба
- Вертикальная линия t=0 (красный dash)
- Вертикальная линия entry time (зелёный solid)
- Вертикальная линия exit time (красный/зелёный solid)
- Если Signal C: аннотация "confirmer lag = Xms"

**Нижний график: Follower + BBO Subplot (по умолчанию ВКЛЮЧЁН)**

- Follower price line (зелёный)
- Вертикальная линия t=0
- Вертикальная линия entry (с аннотацией "ENTRY @ $XX,XXX.X (VWAP) / $XX,XXX.X (Exec)")
- Вертикальная линия exit (с аннотацией "EXIT @ $XX,XXX.X")
- Горизонтальная линия entry price (серый dash)
- Заливка между entry и exit:
  - Зелёная если profit
  - Красная если loss
- MFE точка (зелёный маркер) с аннотацией "+X.XX bps @ +Yms"
- MAE точка (красный маркер) с аннотацией "-X.XX bps @ +Yms"
- Если stop loss / take profit заданы — горизонтальные пунктирные линии уровней
- **BBO subplot (по умолчанию ВКЛЮЧЁН, если bbo_available для venue):**
  - Bid-ask spread follower'а в окне сделки (отдельная ось Y)
  - Видно: спред расширялся при сигнале? При entry? При exit?
  - Entry/exit отмечены на графике спреда
  - Аннотация: "spread@entry = X.XX bps", "spread@exit = X.XX bps"
  - Если BBO недоступен → subplot скрыт, плашка "BBO not available"

**Боковая панель метрик**

- Entry time (UTC, ms)
- Exit time (UTC, ms)
- Hold time (ms)
- Exit reason (hold_expired / stop_loss / take_profit)
- Entry price VWAP
- Entry price Exec (с slippage)
- Exit price VWAP
- Exit price Exec
- Slippage entry (bps) — с пометкой "(fixed fallback)" если BBO недоступен
- Slippage exit (bps)
- Slippage total (bps)
- Gross PnL (bps)
- Fee entry (bps) — с указанием maker/taker
- Fee exit (bps)
- Fee total (bps, round trip)
- Net PnL (bps)
- MFE (bps)
- MAE (bps)
- MFE time (ms from entry)
- MAE time (ms from entry)
- BBO spread at entry (bps) — или "N/A"
- BBO spread at exit (bps) — или "N/A"
- Signal magnitude (σ)
- N lagging followers at signal
- Leader deviation at signal (σ)

**Все followers overlay (toggle)**

- 10 followers на одном графике
- Видно: кто ещё двигался, кто не двигался
- Помогает понять: сигнал реальный или шум

---

#### 7. Monte Carlo (montecarlo.html)

URL: `montecarlo.html?backtest={backtest_id}`

**Настройки**

- Количество симуляций: input (default 10000)
- Метод:
  - Trade shuffle (перемешать порядок сделок)
  - Return shuffle (перемешать returns)
  - Block bootstrap (блоки по N сделок)
- Кнопка: Run (может считаться 5-30 секунд)

**Equity Curves график**

- X: trade number (1, 2, ..., N)
- Y: cumulative PnL (bps)
- 1000 серых линий (симуляции) — тонкие, полупрозрачные. Хранится 1000 кривых в montecarlo.json (~500KB — приемлемо)
- 1 зелёная/красная линия — реальная equity
- 5th и 95th percentile: две линии (жёлтые dash)
- Median симуляций: синяя линия

**Гистограмма финального PnL**

- X: final PnL (bps)
- Y: count
- Распределение финальных PnL всех симуляций
- Вертикальная линия: реальный финальный PnL (зелёный/красный)
- Заливка: площадь хуже реального (для p-value визуализации)

**Гистограмма Sharpe Ratio**

- То же самое но для Sharpe каждой симуляции

**Гистограмма Max Drawdown**

- Распределение max DD симуляций vs реальный

**Статистика (карточки)**

- p-value (% симуляций с PnL ≥ реального)
- Percentile реальной стратегии (e.g., "95th percentile")
- Median simulation PnL
- 5th percentile PnL (worst case)
- 95th percentile PnL (best case)
- Probability of profit (% симуляций с PnL > 0)
- Реальный PnL vs median (разница)
- Реальный Sharpe vs median Sharpe
- Реальный Max DD vs median Max DD

---

#### 8. Paper Trading (paper.html)

URL: `paper.html`

**Статус (верх)**

- Strategy: имя, версия
- Status: Running / Stopped
- Running since: дата, время (UTC)
- Uptime: h:mm:ss (тикает)
- Кнопки: Start (выбрать стратегию), Stop, Restart

**Venue connectivity (таблица)**

- Те же столбцы что в Collector, но:
  - Дополнительно: "Used by strategy" (✓ если venue участвует)
  - Подсветка: если venue нужен стратегии но disconnected — красный alert
  - Paper trader подключается ТОЛЬКО к venue, нужным стратегии (не ко всем 12)

**Live Equity (главный график, обновляется каждые 5s)**

- X: время (UTC)
- Y: cumulative PnL (bps)
- Реальная equity line (зелёная)
- Backtest equity line (серый dash) — для сравнения
- Точки: каждая сделка
- Hover: details сделки

**Последние сигналы (таблица, обновляется)**

- Время (UTC)
- Signal type (A/B/C)
- Direction
- Magnitude σ
- Action: TRADE / SKIP (причина скипа: "follower not lagging", "below threshold", "BBO spread too wide", "position_already_open")
- Если TRADE: venue, entry price, current PnL (если ещё в позиции), или final PnL (если закрыта)
- Spread at signal (bps) — видно был ли спред широким. "N/A" если BBO unavailable

**Текущие открытые позиции**

- Venue
- Direction
- Entry price
- Current price
- Unrealized PnL (bps)
- Time in position (ms)
- Stop loss level (если задан)
- Take profit level (если задан)
- Time to auto-close (countdown если hold_ms задан)

**Сделки сегодня (таблица)**

- Те же столбцы что в Backtest trades table (включая spread, slippage)
- Итоговая строка: net PnL today, win rate today

**Статистика за весь период paper trading**

- Те же карточки что в Backtest stats
- Дополнительно:
  - Days active
  - Trades per day (avg)
  - Best day (bps)
  - Worst day (bps)
  - Equity by day (bar chart)

**Сравнение с бектестом**

- Таблица: метрика → backtest → paper → разница
- Equity overlay на одном графике (backtest vs paper)
- Drift analysis: paper отклоняется от backtest? В какую сторону?

---

#### 9. Data Quality (quality.html)

URL: `quality.html?id={recording_id}`

**Сводная таблица по venues (для выбранной записи)**

- Venue
- Role
- Total ticks
- Ticks/s (avg)
- Ticks/s (max)
- Ticks/s (min non-zero)
- Bin coverage % (% бинов с хотя бы 1 тиком, до ffill)
- Total BBO updates
- BBO/s (avg)
- BBO coverage %
- BBO available (✓/—)
- Median price
- Price deviation from OKX median (bps) — если сильно отличается, проблема
- Reconnects count
- Total downtime (seconds)
- Uptime %
- Zero-price ticks
- Zero-qty ticks
- Side distribution: buy% / sell%
- Flag: 🟢 good / 🟡 warning / 🔴 bad

**Критерии флагов**

- 🔴 bad: bin coverage < 1%, или ticks/s < 0.1, или 0 тиков вообще, или median price отличается от лидеров > 100 bps
- 🟡 warning: bin coverage < 5%, или ticks/s < 1.0, или reconnects > 10, или uptime < 95%
- 🟢 good: всё остальное

**Timeline (график)**

- X: время (весь период сессии, UTC)
- Y: venues (12 строк)
- Каждая venue — горизонтальная полоса:
  - Зелёный: данные поступают
  - Красный: нет данных (gap > 10s)
  - Серый: не активен
- Hover: точное время gap, reconnect event

**Ticks/s over time (график)**

- X: время (UTC)
- Y: ticks/s (per venue или total)
- Линии для каждой venue (разные цвета)
- Видно: когда волатильность → больше тиков
- Видно: когда venue отвалилась (линия падает в 0)
- Toggle: показать/скрыть отдельные venues

**Bin coverage heatmap**

- X: время (1-minute buckets)
- Y: venues
- Цвет: % заполненных 50ms-бинов в этой минуте
- Тёмный = 0%, яркий = 20%+
- Видно: паттерны пустых периодов

**Price consistency check**

- Для каждого момента времени (каждую секунду):
  - Медианная цена лидеров
  - Отклонение каждого follower от медианы (bps)
- График: X=время (UTC), Y=отклонение, линии per venue
- Аномалии: если отклонение > 50 bps — точка подсвечена красным
- Таблица аномалий: время, venue, отклонение, возможная причина

**BBO analysis (для venues с BBO)**

- Таблица:
  - Venue
  - BBO available (✓/—)
  - Median spread (bps)
  - Mean spread (bps)
  - Max spread (bps)
  - Spread percentiles: p50, p95, p99
  - % времени со спредом > 5 bps
- График: spread over time per venue

---

### 10. Jupyter Integration

Не отдельный экран, а:

- Кнопка "Open Jupyter" в navbar → открывает localhost:8888 в новой вкладке
- JupyterLab запущен как отдельный supervisord процесс
- В том же Python environment что и leadlag пакет

**Что должен уметь пакет leadlag в ноутбуке:**

```python
from leadlag import load_session, list_sessions
from leadlag import Strategy, Order, Event, Context
from leadlag import run_backtest, run_monte_carlo

# Список доступных сессий
list_sessions()
# → [{'id': '20260411_164417_a3f2c1b0', 'collection': '20260411_164417',
#     'date': '2026-04-11', 'duration_h': 12, 
#     'ticks': 3243939, 'events': 519}, ...]

# Загрузить сессию
s = load_session('20260411_164417_a3f2c1b0')

# Доступные данные
s.vwap_df          # DataFrame, бинированные VWAP
s.dev_df           # DataFrame, девиации от EMA в σ
s.ema_df           # DataFrame, EMA baselines
s.events           # EventList — удобная обёртка
s.bbo_df           # DataFrame, BBO данные (если есть)
s.ticks_df         # DataFrame, сырые тики (ленивая загрузка — большие)
s.meta             # dict с параметрами сессии
s.quality          # data quality метрики

# Работа с событиями — фильтрация
events = s.events
events.count                    # 519
events.filter(signal='C')       # EventList, 229 событий
events.filter(signal='C', min_magnitude=2.5, 
              follower='Lighter Perp')  # более узкий фильтр
events.filter(leader_mode='confirmed')
events.filter(direction=1)      # только UP
events.filter(time_range=('16:00', '22:00'))  # по UTC часам
events.filter(min_lagging=5)    # минимум 5 lagging followers

# Метрики по событиям
events.filter(signal='C').stats('Lighter Perp')
# → {'count': 73, 'hit_rate': 0.81, 'mean_lag_50_ms': 200,
#    'mean_mfe_bps': 10.76, 'mean_mae_bps': -1.42, ...}

# Grid search — перебор параметров
events.grid_search(
    followers=['Lighter Perp', 'MEXC Perp', 'edgeX Perp'],
    delays_ms=[0, 50, 100, 200],
    holds_ms=[1000, 5000, 10000, 30000],
)
# → DataFrame с gross/net PnL для каждой комбинации

# Визуализация в ноутбуке (Plotly inline)
events[0].plot()                  # один event: leader + follower
events[0].plot(follower='MEXC Perp')  # конкретный follower
events.filter(signal='C').plot_equity('Lighter Perp', hold_ms=30000)
events.plot_lag_distribution('Lighter Perp')  # гистограмма lag_50
events.plot_magnitude_distribution()           # гистограмма σ
events.plot_heatmap(x='delay_ms', y='hold_ms', metric='net_pnl',
                    follower='Lighter Perp', signal='C')

# Написание стратегии — в отдельной %%writefile ячейке:
```

```python
%%writefile data/strategies/lighter_c_bbo_filter.py
from leadlag import Strategy, Order, Event, Context

class LighterCBboFilter(Strategy):
    name = "lighter_c_bbo_filter"
    version = "2026-04-15"
    description = "Lighter on Signal C with BBO spread filter"
    
    params = {
        'signal': 'C',
        'min_magnitude': 2.0,
        'follower': 'Lighter Perp',
        'hold_ms': 30000,
        'max_spread_bps': 2.0,
        'entry_type': 'market',
        'slippage_model': 'half_spread',
        'fixed_slippage_bps': 1.0,
        'position_mode': 'reject',
        'stop_loss_bps': None,
        'take_profit_bps': None,
    }
    
    def on_event(self, event: Event, ctx: Context) -> Order | None:
        if event.signal != self.params['signal']:
            return None
        if self.params['follower'] not in event.lagging_followers:
            return None
        if event.magnitude_sigma < self.params['min_magnitude']:
            return None
        
        bbo = ctx.bbo.get(self.params['follower'])
        if bbo and bbo.available and bbo.spread_bps > self.params['max_spread_bps']:
            return None
        
        return Order(
            venue=self.params['follower'],
            side='buy' if event.direction > 0 else 'sell',
            qty_btc=0.001,
            entry_type=self.params['entry_type'],
            hold_ms=self.params['hold_ms'],
            stop_loss_bps=self.params.get('stop_loss_bps'),
            take_profit_bps=self.params.get('take_profit_bps'),
        )
```

```python
# Далее в следующей ячейке:
from leadlag import load_strategy

# Загрузка и валидация
strat = load_strategy('data/strategies/lighter_c_bbo_filter.py')
print(f"Loaded: {strat.name}, params: {strat.params}")

# Бектест в ноутбуке
result = run_backtest(strat, s)
result.summary()
# → {'n_trades': 68, 'total_net_pnl_bps': 362.7, 'total_gross_pnl_bps': 387.2,
#    'total_fees_bps': 0.0, 'total_slippage_bps': 24.5,
#    'win_rate': 0.82, 'sharpe': 0.58, 'max_dd_bps': 12.3,
#    'avg_trade_bps': 5.33, 'avg_spread_at_entry_bps': 0.72}
result.trades_df        # DataFrame всех сделок (со slippage, spread)
result.equity_df        # DataFrame equity curve (6 полей)
result.plot_equity()    # inline Plotly
result.plot_equity(layers=True)  # Gross → -Fees → -Slippage → Net
result.plot_trade(0)    # первая сделка крупно
result.plot_trades_scatter()  # magnitude vs PnL
result.plot_spread_impact()   # spread at entry vs PnL

# Бектест с ПЕРЕОПРЕДЕЛЕНИЕМ параметров (без редактирования .py файла)
result2 = run_backtest(strat, s, params_override={'max_spread_bps': 3.0})
# → стратегия получает обновлённые params, .py файл не меняется

# Monte Carlo
mc = run_monte_carlo(result, n=10000)
mc.summary()
# → {'p_value': 0.012, 'percentile': 98.8, ...}
mc.plot()               # equity curves + histogram

# Сохранение результатов бектеста → приложение подхватывает
result.save()
# → data/backtest/lighter_c_bbo_filter_20260415_143000/
#   meta.json, trades.json, equity.json, stats.json
```

---

### 11. API Endpoints (для UI)

**System (для Dashboard)**

- `GET /api/system/stats` → `{cpu_percent, cpu_per_core: [], ram_total_gb, ram_used_gb, ram_percent, disk_total_gb, disk_used_gb, disk_data_gb, net_bytes_sent, net_bytes_recv}`
- `GET /api/system/history?minutes=60` → `[{ts, cpu, ram_gb, disk_gb, net_down_bps, net_up_bps}]` — ring buffer из `.system_history.jsonl`
- `GET /api/system/pings` → `[{venue, host, latency_ms, status: 'ok'|'timeout'|'error'}]`
- `GET /api/system/files` → `[{path, size_mb, rows, ts_min, ts_max, modified}]`
- `GET /api/system/processes` → `[{name, status, pid, mem_mb, uptime_s}]` — через supervisord XML-RPC

**Collector**

- `GET /api/collector/status` → `{running, recording_id, start_time, planned_duration_s, venues: [{name, status, ticks, bbo, reconnects, last_tick_ts, last_error, uptime_pct}]}`
- `POST /api/collector/start` body: `{venues: [], duration_s, rotation_s}` → `{recording_id? | pid}`
- `POST /api/collector/stop` → `{ok}`
- `GET /api/collector/log` query: `?since_ts=X&venue=Y&type=Z` → `[{ts, venue, event_type, message}]`
- `GET /api/collector/files` → `[{filename, size_kb, rows, time_range, venues}]`

**Analyses**

- `GET /api/analyses` → `[{id, analysis_id, recording_id, params_hash, date, duration_h, n_ticks, n_events, n_venues}]`
- `GET /api/analyses/{id}/meta` → `{analysis_id, recording_id, params, time_range, venues, quality_summary}`
- `GET /api/analyses/{id}/events` query: `?signal=C&min_mag=2.0&follower=Lighter&direction=1&min_lagging=3` → `[{event with all metrics, БЕЗ ценовых окон}]`
- `GET /api/analyses/{id}/event/{bin_idx}` → `{event + price_window (из price_windows.json) + bbo_window (из bbo_windows.json) для графика}`
- `GET /api/analyses/{id}/quality` → `{venue quality metrics}`
- `POST /api/collections/{id}/analyze` body: `{params}` → `{ok, analysis_id, events_count}`
- `DELETE /api/analyses/{id}` → `{ok}`

**Strategies**

- `GET /api/strategies` → `[{name, version, description, params, valid, error, last_backtest_summary}]` — сканирует `data/strategies/` через `strategy_loader.list_strategies()`
- `GET /api/strategies/{name}` → `{full strategy info + source code}`
- `DELETE /api/strategies/{name}` → `{ok}`

**Backtests**

- `GET /api/backtests` → `[{id, strategy, analysis_id, date, summary_stats}]`
- `GET /api/backtests/{id}/meta` → `{strategy, analysis_id, params, params_override, slippage_model, entry_type}`
- `GET /api/backtests/{id}/trades` → `[{trade details including slippage, spread, fee_type, exit_reason, bbo_available}]`
- `GET /api/backtests/{id}/equity` → `[{ts_ms, gross_equity_bps, post_fee_equity_bps, net_equity_bps, drawdown_bps, trade_id}]`
- `GET /api/backtests/{id}/stats` → `{all stats including fee_impact, by_spread_bucket, by_entry_type}`
- `GET /api/backtests/{id}/trade/{n}` → `{single trade + price_window + bbo_window}`
- `POST /api/backtests/run` body: `{strategy_name, analysis_id, params_override: {key: value} | null}` → `{backtest_id}`
- `GET /api/backtests/{id}/montecarlo` → `{mc results}`
- `POST /api/backtests/{id}/montecarlo/run` body: `{n_simulations, method}` → `{ok}`

**Paper Trading**

- `GET /api/paper/status` → `{running, strategy, uptime, equity_today}`
- `POST /api/paper/start` body: `{strategy_name}` → `{ok}`
- `POST /api/paper/stop` → `{ok}`
- `GET /api/paper/trades` query: `?since_ts=X` → `[{trade including slippage, spread}]`
- `GET /api/paper/equity` → `[{ts_ms, equity_bps}]`
- `GET /api/paper/signals` query: `?last=20` → `[{signal + action + reason + spread_at_signal_bps}]`
- `GET /api/paper/positions` → `[{open positions}]`
- `GET /api/paper/stats` → `{all stats}`
- `GET /api/paper/venues` → `[{venue connectivity status}]`

---

### 12. Структура данных на диске

```
data/
├── ticks/
│   └── 2026-04-11/
│       ├── ticks_20260411_164417.parquet
│       └── ticks_20260411_171417.parquet
├── bbo/
│   └── 2026-04-11/
│       ├── bbo_20260411_164417.parquet
│       └── bbo_20260411_171417.parquet
│
├── sessions/
│   └── 20260411_164417_a3f2c1b0/      (collection_id + params_hash)
│       ├── meta.json
│       │   {session_id, collection_session_id, params_hash,
│       │    collection_files: ["ticks/2026-04-11/ticks_20260411_164417.parquet", ...],
│       │    t_start, t_end, duration_s, bin_size_ms,
│       │    ema_span, threshold, venues, n_events, n_ticks,
│       │    leaders, followers, 
│       │    fees: {venue: {taker_bps, maker_bps}},
│       │    bbo_available: {venue: true|false}}
│       ├── events.json
│       │   [{bin_idx, ts_ms, signal, direction, magnitude_sigma,
│       │     leader, leader_dev, lagging_followers[], n_lagging,
│       │     confirmer_leader, confirmer_lag_ms,
│       │     follower_metrics: {fol: {
│       │       lag_50_ms, lag_80_ms, hit, mfe_bps, mae_bps,
│       │       grid: {delay_ms: {hold_ms: {gross_bps, net_bps}}}
│       │     }}
│       │   }]
│       │   # НЕ содержит rel_times_ms и venues prices (они в price_windows.json)
│       ├── price_windows.json
│       │   [{bin_idx, rel_times_ms[],
│       │     venues: {venue: [prices]}}]
│       ├── bbo_windows.json
│       │   [{bin_idx, rel_times_ms[],
│       │     venues: {venue: {bid: [prices], ask: [prices], spread_bps: [values]}}}]
│       │   # Только venues с bbo_available=true
│       ├── metrics.parquet
│       │   bin_idx, signal, follower, lag_50_ms, lag_80_ms,
│       │   hit, mfe_bps, mae_bps, leader_move_bps
│       ├── grid.parquet
│       │   delay_ms, hold_ms, gross_pnl_bps, net_pnl_bps,
│       │   hit, signal, follower, bin_idx
│       ├── ci.json
│       │   [{follower, signal, delay_ms, hold_ms, n,
│       │     net_mean, net_lo, net_hi, gross_mean,
│       │     hit_mean, hit_lo, hit_hi, sharpe}]
│       └── quality.json
│           {venues: {venue: {
│             ticks_total, ticks_per_s, bbo_total, bin_coverage_pct,
│             bbo_available, median_price, reconnects, downtime_s, 
│             uptime_pct, zero_prices, zero_qty, side_buy_pct,
│             price_deviation_from_leader_bps, flag,
│             bbo_median_spread_bps, bbo_mean_spread_bps,
│             bbo_max_spread_bps, bbo_p95_spread_bps,
│             bbo_pct_above_5bps
│           }},
│           timeline_gaps: [{venue, start_ms, end_ms, duration_s}]}
│
├── strategies/
│   ├── lighter_c_v1.py
│   ├── lighter_c_bbo_filter.py
│   └── mexc_multi_signal.py
│
├── backtest/
│   └── lighter_c_bbo_filter_20260415_143000/
│       ├── meta.json
│       │   {strategy_name, strategy_version, strategy_params,
│       │    params_override: {key: value} | null,
│       │    session_id, backtest_date, computation_time_s,
│       │    slippage_model, entry_type, position_mode}
│       ├── trades.json
│       │   [{trade_id, signal_bin_idx, signal_type, direction,
│       │     magnitude_sigma, venue,
│       │     entry_ts_ms, exit_ts_ms,
│       │     entry_price_vwap, exit_price_vwap,
│       │     entry_price_exec, exit_price_exec,
│       │     hold_ms,
│       │     exit_reason: "hold_expired"|"stop_loss"|"take_profit",
│       │     gross_pnl_bps,
│       │     fee_entry_bps, fee_exit_bps, fee_total_bps,
│       │     fee_type: "taker"|"maker",
│       │     slippage_entry_bps, slippage_exit_bps, slippage_total_bps,
│       │     slippage_source: "bbo"|"fixed_fallback",
│       │     net_pnl_bps,
│       │     spread_at_entry_bps, spread_at_exit_bps,
│       │     bbo_available: true|false,
│       │     mfe_bps, mae_bps, mfe_time_ms, mae_time_ms,
│       │     n_lagging_at_signal, leader_dev_sigma}]
│       ├── equity.json
│       │   [{ts_ms, gross_equity_bps, post_fee_equity_bps,
│       │     net_equity_bps, drawdown_bps, trade_id}]
│       ├── stats.json
│       │   {total_net_pnl_bps, total_gross_pnl_bps,
│       │    total_fees_bps, total_slippage_bps,
│       │    fee_pct_of_gross, slippage_pct_of_gross,
│       │    n_trades, n_errors,
│       │    win_rate, profit_factor,
│       │    sharpe, max_drawdown_bps, max_dd_duration_ms,
│       │    avg_trade_bps, avg_win_bps, avg_loss_bps,
│       │    best_trade_bps, worst_trade_bps, avg_hold_ms,
│       │    avg_mfe_bps, avg_mae_bps, mfe_mae_ratio,
│       │    trades_per_hour, max_consec_wins, max_consec_losses,
│       │    avg_spread_at_entry_bps, avg_slippage_bps,
│       │    by_signal: {A: {...}, B: {...}, C: {...}},
│       │    by_venue: {venue: {...}},
│       │    by_direction: {up: {...}, down: {...}},
│       │    by_entry_type: {
│       │      market: {n, avg_fee_bps, avg_slippage_bps, win_rate, avg_pnl_bps},
│       │      limit: {n, avg_fee_bps, fill_rate, win_rate, avg_pnl_bps}
│       │    },
│       │    by_spread_bucket: {
│       │      "0-1": {n, avg_net_pnl_bps, win_rate},
│       │      "1-2": {n, avg_net_pnl_bps, win_rate},
│       │      "2-5": {n, avg_net_pnl_bps, win_rate},
│       │      "5+":  {n, avg_net_pnl_bps, win_rate},
│       │      "N/A": {n, avg_net_pnl_bps, win_rate}
│       │    },
│       │    by_exit_reason: {
│       │      hold_expired: {n, avg_pnl_bps, win_rate},
│       │      stop_loss: {n, avg_pnl_bps},
│       │      take_profit: {n, avg_pnl_bps}
│       │    }}
│       └── montecarlo.json
│           {n_simulations, method, 
│            p_value, percentile, 
│            real_pnl, median_sim_pnl,
│            pnl_5th, pnl_95th,
│            prob_of_profit,
│            sim_equity_curves: [[pnl_1, pnl_2, ...], ...],  # 1000 кривых (~500KB)
│            sim_final_pnls: [pnl_1, pnl_2, ...],  # all 10000
│            sim_sharpes: [...],
│            sim_max_dds: [...]}
│
├── paper/
│   └── lighter_c_bbo_filter/
│       ├── config.json
│       │   {strategy_name, started_at, venues_monitored, position_mode}
│       ├── trades.jsonl
│       │   {trade_id, ...same as backtest trades including slippage, spread,
│       │    exit_reason, bbo_available, slippage_source...}\n
│       ├── signals.jsonl
│       │   {ts_ms, signal_type, magnitude, direction,
│       │    action: "trade"|"skip"|"error",
│       │    skip_reason: "follower_not_lagging"|"below_threshold"|
│       │                 "bbo_spread_too_wide"|"position_already_open"|null,
│       │    error: "traceback"|null,
│       │    spread_at_signal_bps,   # null если BBO unavailable
│       │    bbo_available,
│       │    order: {...} if trade}\n
│       ├── equity.jsonl
│       │   {ts_ms, cumulative_pnl_bps, open_positions: [...]}\n
│       └── positions.json
│           [{venue, direction, entry_ts, entry_price, 
│             qty_btc, stop_loss, take_profit, auto_close_ts}]
│
├── .collector_status.json      # Атомарная запись: write .tmp → os.rename()
│   {running, session_id, start_time, venues: [{name, status, ticks, ...}]}
│
├── .paper_status.json          # Атомарная запись: write .tmp → os.rename()
│   {running, strategy, uptime, equity_today, ...}
│
├── .system_history.jsonl
│   {ts, cpu_pct, ram_used_gb, disk_used_gb, net_down_bps, net_up_bps}\n
│   # Каждые 5 секунд. Rotation: только последние 24 часа.
│
└── .ping_cache.json
    {ts, venues: {venue: {host, latency_ms, status}}}
    # Обновляется каждые 10 секунд. Атомарная запись через .tmp + rename.
```

---

### 13. Process Architecture

```
supervisord
├── leadlag-api          (uvicorn, port 8899)
│   └── FastAPI app
│       └── serves /api/* and /ui/*
│
├── leadlag-collector    (python scripts/collect.py)
│   └── async WS engine
│       └── writes data/ticks/YYYY-MM-DD/ticks_*.parquet, data/bbo/YYYY-MM-DD/bbo_*.parquet
│       └── writes data/.collector_status.json (атомарно: .tmp + rename)
│
├── leadlag-paper        (python scripts/paper_trade.py)
│   └── Подключается ТОЛЬКО к venue нужным стратегии (не ко всем 12)
│   └── Если коллектор запущен — получает данные через IPC (Unix socket)
│   └── Если коллектор не запущен — свои WS-подключения
│   └── realtime/ pipeline: BinBuffer → EmaTracker → Detector → Strategy.on_event()
│   └── writes data/paper/{strategy}/trades.jsonl
│   └── writes data/.paper_status.json (атомарно)
│
├── leadlag-monitor      (python scripts/monitor.py)
│   └── Каждые 5s: psutil → data/.system_history.jsonl
│   └── Каждые 10s: ping venues → data/.ping_cache.json (атомарно)
│   └── Rotation: хранит только 24 часа в .system_history.jsonl
│
└── jupyter-lab          (jupyter lab, port 8888)
    └── notebooks/ directory
    └── same venv as leadlag
```

**Inter-process communication:**

- Collector → API: shared JSON status file (`data/.collector_status.json`), обновляется каждые 2 секунды коллектором. **Атомарная запись:** коллектор пишет в `.collector_status.json.tmp`, затем `os.rename('.collector_status.json.tmp', '.collector_status.json')`. Rename — атомарная операция на POSIX, гарантирует что API никогда не прочитает частично записанный файл. API читает при каждом запросе `/api/collector/status`.
- Paper → API: аналогично (`data/.paper_status.json`, через `.tmp` + `rename`)
- Monitor → API: `data/.system_history.jsonl` (append-only, rotation через truncation при размере > 5MB) и `data/.ping_cache.json` (атомарно через `.tmp` + `rename`)
- Collector → Paper (IPC): если оба запущены одновременно, paper trader подписывается на данные коллектора через Unix domain socket (`data/.collector.sock`). Коллектор шлёт тики и BBO в реальном времени. Это избегает двойных WS-соединений к биржам.
- Analysis — не daemon, запускается как subprocess из API при `POST /api/collections/{id}/analyze`
- Backtest — не daemon, запускается как subprocess из API при `POST /api/backtests/run`
- Monte Carlo — не daemon, запускается как subprocess

---

### 14. Context — разная конструкция в разных режимах

Стратегия получает `ctx: Context` с `ctx.bbo[venue]`. Интерфейс одинаковый, реализация разная:

```python
@dataclass
class BboSnapshot:
    available: bool            # True если BBO данные есть для этого venue
    bid_price: float | None
    bid_qty: float | None
    ask_price: float | None
    ask_qty: float | None
    spread_bps: float | None   # (ask - bid) / mid * 10000, None если unavailable
    ts_ms: int | None          # timestamp снэпшота

class Context:
    bbo: dict[str, BboSnapshot]
    vwap: dict[str, float]
    
    @classmethod
    def from_backtest(cls, event, session_data, bbo_windows) -> "Context":
        """Строится из предвычисленных bbo_windows.json.
        Для venue без BBO → BboSnapshot(available=False, ...)"""
        ...
    
    @classmethod  
    def from_live(cls, bbo_tracker: BboTracker, bin_buffers: dict) -> "Context":
        """Строится из live BBO snapshot (bbo_tracker.py) 
        и текущих VWAP из bin_buffers.
        BBO snapshot захватывается в момент детекции события в detector.py.
        Для venue без парсера BBO → BboSnapshot(available=False, ...)"""
        ...
```

---

### 15. Часовой пояс

Все `ts_ms` хранятся в UTC. Все UI показывают время с явной пометкой **UTC**:
- Формат: `HH:MM:SS.mmm UTC`
- На Dashboard и Collector — текущее время показывается как «14:32:15 UTC»
- В таблицах — колонка «Time (UTC)»
- В будущем можно добавить переключатель UTC/Local, но в первой версии — только UTC

---

### 16. Что НЕ делать в первой версии

- Multi-asset (только BTC)
- Real trading (только paper)
- Authentication (localhost only)
- Docker
- npm / webpack / build step
- PostgreSQL / Redis / Kafka
- WebSocket для UI (polling достаточен)
- Mobile responsive (desktop only)
- Dark/light theme toggle (только dark)
- User settings persistence (hardcoded defaults)
- Multiple simultaneous paper traders (один за раз)
- Strategy marketplace / sharing
- Alerting system (Telegram и т.д.) — только в Phase 6
- UTC/Local toggle (только UTC)

---

### 17. Пайплайн пользователя (полный)

```
1. СБОР ДАННЫХ
   Dashboard → Start Collector → 12 часов
   Или: supervisord автоматически каждую ночь
   Мониторинг: Dashboard показывает ticks/s, pings, CPU/RAM
   Данные: data/ticks/YYYY-MM-DD/ticks_*.parquet, data/bbo/YYYY-MM-DD/bbo_*.parquet

2. АНАЛИЗ
   Dashboard → Run Analysis → выбрать сессию + параметры
   Результат: data/sessions/{collection_id}_{params_hash}/ готов
   Можно запустить несколько анализов с разными параметрами на одних данных

3. ИССЛЕДОВАНИЕ В EXPLORER
   Explorer → смотришь события → понимаешь какие
   followers лагируют на каких сигналах
   Видишь BBO спред overlay → понимаешь можно ли реально войти
   Для venue без BBO — overlay отсутствует, плашка "BBO not available"
   
   Открываешь Jupyter (кнопка в navbar)

4. РАЗРАБОТКА СТРАТЕГИИ В JUPYTER
   from leadlag import load_session
   session = load_session('20260411_164417_a3f2c1b0')
   
   # Исследуешь как хочешь — полный Python
   events = session.events
   events.filter(signal='C').plot_lag_distribution('Lighter Perp')
   
   # Пишешь стратегию с BBO фильтром и slippage моделью
   # В %%writefile ячейке
   
   # Загружаешь и тестируешь
   strat = load_strategy('data/strategies/my_strategy.py')
   result = run_backtest(strat, session)
   result.summary()
   result.plot_equity(layers=True)  # Gross → -Fees → -Slippage → Net

5. ДЕТАЛЬНЫЙ ПРОСМОТР В ПРИЛОЖЕНИИ
   Strategy List → my_strategy → Run Backtest
   (можно с params_override: POST /api/backtests/run {params_override: {max_spread_bps: 3.0}})
   Backtest → equity curve (Gross/Net переключатель), каждая сделка
   Клик на сделку → trade.html?backtest={id}&trade={n} (с BBO subplot)
   Кнопка "View Event" → explorer.html?analysis={id}&event={bin_idx}
   Monte Carlo → montecarlo.html?backtest={id} → p-value

6. ИТЕРАЦИЯ
   Видишь проблему (напр. все убытки при spread > 3 bps) →
   открываешь Jupyter → добавляешь фильтр max_spread_bps →
   %%writefile → load_strategy → run_backtest → repeat
   
   Или: быстрая итерация через params_override в API 
   (без правки .py файла)

7. PAPER TRADING
   Strategy List → Run Paper → 
   Paper page → live equity
   Paper trader подключается только к нужным venue
   Real-time pipeline: BinBuffer → EmaTracker → Detector → on_event()
   
8. РЕАЛ ТРЕЙДИНГ (позже)
   Когда paper results убедили →
   Live trader (отдельный модуль)
```

---

### 18. Как формулировать задачи для AI-разработчика

Главная проблема — "AI недопонял и сделал не то" — возникает когда задача дана как описание желаемого результата без точных входных/выходных данных.

**Правило:** каждая задача должна содержать: 1) точный вход (файл/структура данных), 2) точный выход, 3) критерий приёмки.

**Пример плохой задачи:** "Сделай explorer для событий"

**Пример хорошей задачи:**

> Создай файл `ui/explorer.html`. На вход: JSON структура из `data/sessions/{id}/events.json` (формат описан ниже) и `data/sessions/{id}/price_windows.json` + `data/sessions/{id}/bbo_windows.json`. Events загружаются через `fetch('/api/analyses/{id}/events')` при старте страницы. Price/BBO windows загружаются через `fetch('/api/analyses/{id}/event/{bin_idx}')` при клике на конкретное событие (lazy loading).
> 
> URL параметры: `session` (обязательный), `event` (опциональный — если задан, сразу открывать это событие), `mode` (опциональный — `event` по умолчанию, `trade` для режима с entry/exit метками), `backtest` и `trade` (для mode=trade).
> 
> UI состоит из: панели управления (фильтры: signal A/B/C, leader, follower, min_magnitude slider), списка событий слева (скролл, 500 строк, отображает: номер, signal, direction ↑↓, magnitude, ts в UTC), главного графика справа (2 субплота: leader bps от t0, follower bps от t0 с BBO spread overlay по умолчанию включённым — заливка между bid и ask, вертикальная линия t=0, вертикальные линии lag_50ms и lag_80ms), таблицы метрик всех followers внизу (включая taker и maker fee для каждой venue, колонка BBO available).
> 
> Для venue без BBO (MEXC, Gate, Hyperliquid): BBO overlay не рисуется, показывается плашка "BBO not available for {venue}".
> 
> Требования: при клике на событие в списке — график и таблица обновляются без перезагрузки страницы. Фильтры мгновенно фильтруют список без запросов к серверу. BBO overlay: bid/ask линии + полупрозрачная заливка спреда. Стиль: тёмный фон #0f1117, как в текущем `explorer.html` (прилагается).
> 
> Критерий приёмки: открывается в браузере, 500 событий загружаются за < 2 секунд, фильтрация мгновенная, график перерисовывается при клике, BBO spread виден на нижнем субплоте. URL с ?analysis=X&event=Y открывает нужное событие.

---

### 19. Фазы разработки с критериями приёмки

**Фаза 1 (1-2 недели): Python-пакет leadlag/**

- Вход: текущий код трёх ноутбуков
- Выход: pip-installable пакет
- Критерий: `from leadlag import load_session; s = load_session('20260411_164417_a3f2c1b0')` работает, `s.events.filter(signal='C').count` возвращает 229
- Критерий: все текущие ноутбуки переписаны на импорты из leadlag и дают те же результаты
- Критерий: `s.bbo_df` доступен и содержит данные BBO
- Критерий: `leadlag/strategy_loader.py` корректно загружает .py файл, валидирует on_event(), ловит синтаксические ошибки
- Критерий: данные читаются из `data/ticks/YYYY-MM-DD/ticks_*.parquet` (структурированное хранение)
- Критерий: session_id включает params_hash

**Фаза 2 (1 неделя): Strategy + Backtest engine (с Slippage/Spread/SL/TP)**

- Вход: Strategy class (с on_event, entry_type, slippage_model, stop_loss_bps, take_profit_bps, position_mode), Session object (с BBO данными)
- Выход: BacktestResult с trades (включая slippage_bps, spread_at_entry_bps, fee_type, exit_reason, bbo_available, slippage_source), equity (с gross_equity_bps/post_fee_equity_bps/net_equity_bps — 6 полей), stats (включая fee_impact, by_spread_bucket, by_entry_type, by_exit_reason)
- Критерий: бектест LighterCv1 (signal=C, hold=30s, delay=0, entry_type=market, slippage=half_spread) даёт Net PnL < Gross PnL (slippage учтён). В trades.json есть slippage_bps > 0 для маркетных ордеров, slippage_source="bbo".
- Критерий: бектест на MEXC Perp (bbo_available=false) с slippage=half_spread → fallback на fixed_slippage_bps, slippage_source="fixed_fallback" в trades.json
- Критерий: бектест с stop_loss_bps=5.0 → некоторые сделки закрываются с exit_reason="stop_loss"
- Критерий: position_mode="reject" → при двух сигналах подряд на один venue — второй пропускается
- Критерий: `result.save()` создаёт правильную структуру файлов, `result.plot_equity()` рендерит в ноутбуке
- Критерий: `result.plot_equity(layers=True)` показывает 3 линии: Gross, Post-Fee, Net
- Критерий: `run_backtest(strat, s, params_override={'max_spread_bps': 3.0})` работает — параметры переопределяются без правки .py файла

**Фаза 3 (1 неделя): API + Explorer + Backtest UI**

- Вход: `data/sessions/`, `data/backtest/`
- Выход: FastAPI (все эндпоинты) + explorer.html + backtest.html + trade.html + strategy.html + montecarlo.html
- Критерий: `explorer.html?analysis=X` загружает 519 событий за < 2 секунд, фильтры работают мгновенно, клик на событие перерисовывает график за <200ms, BBO overlay виден на нижнем субплоте для venue с BBO, скрыт для venue без BBO
- Критерий: `backtest.html?id=X` показывает equity с переключателем слоёв (Gross/Fees/Slippage/Net), trades с колонками slippage и spread, stats включают fee_impact и by_spread_bucket
- Критерий: `trade.html?backtest=X&trade=Y` показывает BBO subplot по умолчанию (если доступен), entry/exit аннотации содержат VWAP и Exec цены, SL/TP линии если заданы
- Критерий: все URL-параметры (session, event, backtest, trade, mode) корректно обрабатываются
- Критерий: IPC файлы (`.collector_status.json`, `.paper_status.json`, `.ping_cache.json`) читаются без ошибок (атомарная запись)

**Фаза 4 (1 неделя): Dashboard + Collector UI + Data Quality**

- Вход: running collector process, leadlag-monitor daemon
- Выход: `index.html`, `collector.html`, `quality.html`
- Критерий: Dashboard показывает CPU/RAM/Disk/Net sparklines (обновление каждые 5s), пинги до бирж (обновление каждые 10s), процессы с PID и памятью, активные файлы
- Критерий: можно запустить/остановить коллектор из UI, live ticks/s обновляется
- Критерий: `quality.html?id=REC_X` показывает красные флаги для Aster/Binance, BBO analysis с медианными спредами, колонку BBO available
- Критерий: время везде отображается с пометкой UTC

**Фаза 5 (1 неделя): Paper Trading + Real-time Pipeline**

- Вход: стратегия + live WS данные
- Выход: `leadlag/realtime/` (BinBuffer, EmaTracker, RealtimeDetector, BboTracker) + paper trader daemon + `paper.html`
- Критерий: `BinBuffer` корректно бинирует тики в 50ms VWAP, `EmaTracker.update()` даёт значения ±0.1% от batch `pandas.ewm()`
- Критерий: `RealtimeDetector` детектирует пересечения порога с latency < 5ms
- Критерий: paper trader запускается, получает live данные (через IPC от коллектора или свои WS), генерирует сигналы, записывает виртуальные сделки (с учётом slippage и spread), UI показывает equity в реальном времени
- Критерий: signals.jsonl записывает spread_at_signal_bps (null для venue без BBO), skip_reason включает "bbo_spread_too_wide" и "position_already_open"
- Критерий: paper trader НЕ создаёт двойные WS к биржам если коллектор запущен

**Фаза 6 (отдельно, позже): Real Trading**

- После того как paper trading работает стабильно несколько недель
- Monte Carlo polish
- Strategy comparison
- Alerts (optional)
- Real trading preparation
