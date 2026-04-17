"""WS message parsers for all 12 venues + registration into REGISTRY.

Ported verbatim from collect_full.txt (notebook prototype). Parser signature:
    fn(msg: dict, ts_local_ms: int) -> list[tick_dict] | bbo_dict | None

All qty values are normalized to BTC inside the parser (contract_size is
reference-only and not applied downstream).
"""
import json
import time
import urllib.request

from leadlag.venues.config import VenueConfig, register_venue


# ══════════════ TRADES: LEADERS ══════════════

def parse_okx_trade(msg, ts):
    if msg.get("arg", {}).get("channel") != "trades" or "data" not in msg:
        return []
    return [
        {"ts_ms": ts, "ts_exchange_ms": int(d["ts"]),
         "price": float(d["px"]), "qty": float(d["sz"]), "side": d["side"]}
        for d in msg["data"]
    ]


def parse_bybit_trade(msg, ts):
    if not msg.get("topic", "").startswith("publicTrade") or "data" not in msg:
        return []
    return [
        {"ts_ms": ts, "ts_exchange_ms": int(d["T"]),
         "price": float(d["p"]), "qty": float(d["v"]), "side": d["S"].lower()}
        for d in msg["data"]
    ]


# ══════════════ TRADES: FOLLOWERS CEX ══════════════

def parse_binance_trade(msg, ts):
    data = msg.get("data", msg)
    if data.get("e") != "trade":
        return []
    p, q = float(data["p"]), float(data["q"])
    if p <= 0 or q <= 0:
        return []
    return [{"ts_ms": ts, "ts_exchange_ms": int(data["T"]),
             "price": p, "qty": q,
             "side": "sell" if data.get("m") else "buy"}]


def parse_mexc_trade(msg, ts):
    if msg.get("channel") != "push.deal":
        return []
    return [
        {"ts_ms": ts, "ts_exchange_ms": int(d["t"]),
         "price": float(d["p"]), "qty": float(d["v"]) * 0.0001,
         "side": "buy" if d.get("T") == 1 else "sell"}
        for d in msg.get("data", [])
    ]


def parse_bitget_trade(msg, ts):
    if msg.get("arg", {}).get("channel") != "trade" or "data" not in msg:
        return []
    return [
        {"ts_ms": ts, "ts_exchange_ms": int(d["ts"]),
         "price": float(d["price"]), "qty": float(d["size"]),
         "side": d["side"].lower()}
        for d in msg["data"]
    ]


def parse_gate_trade(msg, ts):
    if msg.get("channel") != "futures.trades" or msg.get("event") != "update":
        return []
    ticks = []
    for d in msg.get("result", []):
        size = d.get("size", 0)
        ts_ex = d.get("create_time_ms", int(d.get("create_time", 0)) * 1000)
        ticks.append({"ts_ms": ts, "ts_exchange_ms": int(ts_ex),
                      "price": float(d["price"]),
                      "qty": abs(size) * 0.0001,
                      "side": "buy" if size > 0 else "sell"})
    return ticks


# ══════════════ TRADES: FOLLOWERS DEX ══════════════

def parse_hyperliquid_trade(msg, ts):
    if msg.get("channel") != "trades":
        return []
    ticks = []
    for d in msg.get("data", []):
        raw = str(d.get("side", "")).lower()
        if raw in ("b", "buy", "long"):
            side = "buy"
        elif raw in ("a", "sell", "short"):
            side = "sell"
        else:
            side = "unknown"
        ticks.append({"ts_ms": ts, "ts_exchange_ms": int(d.get("time", 0)),
                      "price": float(d["px"]), "qty": float(d["sz"]),
                      "side": side})
    return ticks


def parse_lighter_trade(msg, ts):
    if msg.get("type") != "update/trade":
        return []
    return [
        {"ts_ms": ts, "ts_exchange_ms": int(d.get("timestamp", 0)),
         "price": float(d["price"]), "qty": float(d["size"]),
         "side": "sell" if d.get("is_maker_ask") else "buy"}
        for d in msg.get("trades", [])
    ]


def parse_edgex_trade(msg, ts):
    if msg.get("type") != "quote-event":
        return []
    content = msg.get("content", {})
    if not content.get("channel", "").startswith("trades."):
        return []
    return [
        {"ts_ms": ts, "ts_exchange_ms": int(d.get("time", 0)),
         "price": float(d["price"]), "qty": float(d["size"]),
         "side": "sell" if d.get("isBuyerMaker") else "buy"}
        for d in content.get("data", [])
    ]


def parse_aster_trade(msg, ts):
    data = msg.get("data", msg)
    if data.get("e") != "aggTrade":
        return []
    return [{"ts_ms": ts, "ts_exchange_ms": int(data["T"]),
             "price": float(data["p"]), "qty": float(data["q"]),
             "side": "sell" if data.get("m") else "buy"}]


# ══════════════ BBO PARSERS ══════════════

def parse_okx_bbo(msg, ts):
    if msg.get("arg", {}).get("channel") != "bbo-tbt" or "data" not in msg:
        return None
    d = msg["data"][0]
    return {"ts_ms": ts,
            "bid_price": float(d["bids"][0][0]), "bid_qty": float(d["bids"][0][1]),
            "ask_price": float(d["asks"][0][0]), "ask_qty": float(d["asks"][0][1])}


def parse_bybit_bbo(msg, ts):
    if not msg.get("topic", "").startswith("orderbook.1") or "data" not in msg:
        return None
    d = msg["data"]
    b, a = d.get("b", []), d.get("a", [])
    if not b or not a:
        return None
    return {"ts_ms": ts,
            "bid_price": float(b[0][0]), "bid_qty": float(b[0][1]),
            "ask_price": float(a[0][0]), "ask_qty": float(a[0][1])}


def parse_binance_bbo(msg, ts):
    data = msg.get("data", msg)
    if data.get("e") in ("trade", "aggTrade") or "b" not in data or "a" not in data:
        return None
    return {"ts_ms": ts,
            "bid_price": float(data["b"]), "bid_qty": float(data["B"]),
            "ask_price": float(data["a"]), "ask_qty": float(data["A"])}


def parse_bitget_bbo(msg, ts):
    if msg.get("arg", {}).get("channel") != "books1" or "data" not in msg:
        return None
    d = msg["data"][0]
    b, a = d.get("bids", []), d.get("asks", [])
    if not b or not a:
        return None
    return {"ts_ms": ts,
            "bid_price": float(b[0][0]), "bid_qty": float(b[0][1]),
            "ask_price": float(a[0][0]), "ask_qty": float(a[0][1])}


def parse_lighter_bbo(msg, ts):
    if msg.get("type") != "update/ticker":
        return None
    t = msg.get("ticker", {})
    b, a = t.get("b", {}), t.get("a", {})
    if not b.get("price") or not a.get("price"):
        return None
    return {"ts_ms": ts,
            "bid_price": float(b["price"]), "bid_qty": float(b["size"]),
            "ask_price": float(a["price"]), "ask_qty": float(a["size"])}


def parse_edgex_bbo(msg, ts):
    if msg.get("type") != "quote-event":
        return None
    content = msg.get("content", {})
    if not content.get("channel", "").startswith("bookTicker"):
        return None
    for d in content.get("data", []):
        if str(d.get("contractId")) == "10000001":
            bp = float(d.get("bestBidPrice", 0))
            ap = float(d.get("bestAskPrice", 0))
            if bp > 0 and ap > 0:
                return {"ts_ms": ts,
                        "bid_price": bp, "bid_qty": float(d.get("bestBidSize", 0)),
                        "ask_price": ap, "ask_qty": float(d.get("bestAskSize", 0))}
    return None


def parse_aster_bbo(msg, ts):
    return parse_binance_bbo(msg, ts)


# ══════════════ DYNAMIC SUBSCRIBE FACTORIES ══════════════

def make_gate_subscribe():
    return {"time": int(time.time()), "channel": "futures.trades",
            "event": "subscribe", "payload": ["BTC_USDT"]}


_lighter_market_id_cache = None


def make_lighter_subscribe():
    global _lighter_market_id_cache

    if _lighter_market_id_cache is not None:
        btc_id = _lighter_market_id_cache
    else:
        btc_id = 1
        urls = [
            "https://mainnet.zklighter.elliot.ai/api/v1/markets",
            "https://zklighter.elliot.ai/api/v1/markets",
        ]
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0", "Accept": "application/json"})
                resp = urllib.request.urlopen(req, timeout=10)
                markets = json.loads(resp.read())
                for m in markets:
                    if "BTC" in m.get("symbol", "").upper():
                        btc_id = m.get("market_index", m.get("market_id", 1))
                        break
                _lighter_market_id_cache = btc_id
                break
            except Exception:
                continue
        if _lighter_market_id_cache is None:
            _lighter_market_id_cache = btc_id

    return [
        {"type": "subscribe", "channel": f"trade/{btc_id}"},
        {"type": "subscribe", "channel": f"ticker/{btc_id}"},
    ]


# ══════════════ VENUE REGISTRATION ══════════════

REGISTRY_CONFIGS = [
    VenueConfig(name="OKX Perp", role="leader",
                ws_url="wss://ws.okx.com:8443/ws/v5/public",
                subscribe_msg={"op": "subscribe", "args": [{"channel": "trades", "instId": "BTC-USDT-SWAP"}]},
                parser=parse_okx_trade,
                bbo_subscribe_msg={"op": "subscribe", "args": [{"channel": "bbo-tbt", "instId": "BTC-USDT-SWAP"}]},
                bbo_parser=parse_okx_bbo,
                keepalive_type="text_ping", keepalive_interval=25,
                taker_fee_bps=5.0, maker_fee_bps=2.0),
    VenueConfig(name="Bybit Perp", role="leader",
                ws_url="wss://stream.bybit.com/v5/public/linear",
                subscribe_msg={"op": "subscribe", "args": ["publicTrade.BTCUSDT"]},
                parser=parse_bybit_trade,
                bbo_subscribe_msg={"op": "subscribe", "args": ["orderbook.1.BTCUSDT"]},
                bbo_parser=parse_bybit_bbo,
                keepalive_type="ws_ping", keepalive_interval=20,
                taker_fee_bps=5.5, maker_fee_bps=2.0),
    VenueConfig(name="Binance Perp", role="follower",
                ws_url="wss://fstream.binance.com/stream?streams=btcusdt@trade/btcusdt@bookTicker",
                subscribe_msg=None, parser=parse_binance_trade, bbo_parser=parse_binance_bbo,
                taker_fee_bps=4.5, maker_fee_bps=2.0),
    VenueConfig(name="Binance Spot", role="follower",
                ws_url="wss://stream.binance.com:9443/stream?streams=btcusdt@trade/btcusdt@bookTicker",
                subscribe_msg=None, parser=parse_binance_trade, bbo_parser=parse_binance_bbo,
                taker_fee_bps=10.0, maker_fee_bps=6.0),
    VenueConfig(name="Bybit Spot", role="follower",
                ws_url="wss://stream.bybit.com/v5/public/spot",
                subscribe_msg={"op": "subscribe", "args": ["publicTrade.BTCUSDT"]},
                parser=parse_bybit_trade,
                bbo_subscribe_msg={"op": "subscribe", "args": ["orderbook.1.BTCUSDT"]},
                bbo_parser=parse_bybit_bbo,
                keepalive_type="ws_ping", keepalive_interval=20,
                taker_fee_bps=10.0, maker_fee_bps=6.0),
    VenueConfig(name="MEXC Perp", role="follower",
                ws_url="wss://contract.mexc.com/edge",
                subscribe_msg={"method": "sub.deal", "param": {"symbol": "BTC_USDT"}},
                parser=parse_mexc_trade,
                keepalive_type="json_ping", keepalive_msg={"method": "ping"}, keepalive_interval=15,
                taker_fee_bps=2.0, maker_fee_bps=0.0, contract_size=0.0001),
    VenueConfig(name="Bitget Perp", role="follower",
                ws_url="wss://ws.bitget.com/v2/ws/public",
                subscribe_msg={"op": "subscribe", "args": [{"instType": "USDT-FUTURES", "channel": "trade", "instId": "BTCUSDT"}]},
                parser=parse_bitget_trade,
                bbo_subscribe_msg={"op": "subscribe", "args": [{"instType": "USDT-FUTURES", "channel": "books1", "instId": "BTCUSDT"}]},
                bbo_parser=parse_bitget_bbo,
                keepalive_type="text_ping", keepalive_interval=30,
                taker_fee_bps=6.0, maker_fee_bps=2.0),
    VenueConfig(name="Gate Perp", role="follower",
                ws_url="wss://fx-ws.gateio.ws/v4/ws/usdt",
                subscribe_msg="DYNAMIC", subscribe_factory=make_gate_subscribe,
                parser=parse_gate_trade,
                keepalive_type="json_ping", keepalive_msg={"channel": "futures.ping"}, keepalive_interval=15,
                taker_fee_bps=5.0, maker_fee_bps=2.0, contract_size=0.0001),
    VenueConfig(name="Hyperliquid Perp", role="follower",
                ws_url="wss://api.hyperliquid.xyz/ws",
                subscribe_msg={"method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}},
                parser=parse_hyperliquid_trade,
                taker_fee_bps=3.5, maker_fee_bps=1.0),
    VenueConfig(name="Lighter Perp", role="follower",
                ws_url="wss://mainnet.zklighter.elliot.ai/stream",
                subscribe_msg="DYNAMIC", subscribe_factory=make_lighter_subscribe,
                parser=parse_lighter_trade, bbo_parser=parse_lighter_bbo,
                keepalive_type="ws_ping", keepalive_interval=60,
                taker_fee_bps=0.0, maker_fee_bps=0.0),
    VenueConfig(name="edgeX Perp", role="follower",
                ws_url="wss://quote.edgex.exchange/api/v1/public/ws",
                subscribe_msg={"type": "subscribe", "channel": "trades.10000001"},
                parser=parse_edgex_trade,
                bbo_subscribe_msg={"type": "subscribe", "channel": "bookTicker.all.1s"},
                bbo_parser=parse_edgex_bbo,
                keepalive_type="edgex_pong",
                taker_fee_bps=2.6, maker_fee_bps=1.0),
    VenueConfig(name="Aster Perp", role="follower",
                ws_url="wss://fstream.asterdex.com/ws/btcusdt@aggTrade/btcusdt@bookTicker",
                subscribe_msg=None, parser=parse_aster_trade, bbo_parser=parse_aster_bbo,
                taker_fee_bps=2.0, maker_fee_bps=0.5),
]

for _cfg in REGISTRY_CONFIGS:
    register_venue(_cfg)
