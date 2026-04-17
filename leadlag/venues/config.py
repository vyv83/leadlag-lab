from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class VenueConfig:
    name: str
    role: str  # 'leader' | 'follower'
    ws_url: str
    subscribe_msg: Any = None
    subscribe_factory: Optional[Callable] = None
    parser: Optional[Callable] = None
    bbo_subscribe_msg: Any = None
    bbo_parser: Optional[Callable] = None
    keepalive_type: Optional[str] = None  # text_ping|json_ping|ws_ping|edgex_pong
    keepalive_msg: Any = None
    keepalive_interval: int = 0
    taker_fee_bps: float = 0.0
    maker_fee_bps: float = 0.0
    contract_size: float = 1.0  # reference only; qty already normalized in parsers
    enabled: bool = True

    @property
    def bbo_available(self) -> bool:
        return self.bbo_parser is not None


REGISTRY: dict[str, VenueConfig] = {}


def register_venue(cfg: VenueConfig) -> None:
    REGISTRY[cfg.name] = cfg


LEADERS = ("OKX Perp", "Bybit Perp")

FEES = {
    "OKX Perp": 5.0,
    "Bybit Perp": 5.5,
    "Binance Perp": 4.5,
    "Binance Spot": 10.0,
    "Bybit Spot": 10.0,
    "MEXC Perp": 2.0,
    "Bitget Perp": 6.0,
    "Gate Perp": 5.0,
    "Hyperliquid Perp": 3.5,
    "Lighter Perp": 0.0,
    "edgeX Perp": 2.6,
    "Aster Perp": 2.0,
}

BBO_UNAVAILABLE_VENUES = {"MEXC Perp", "Gate Perp", "Hyperliquid Perp"}


def FOLLOWERS() -> list[str]:
    return [n for n, v in REGISTRY.items() if v.role == "follower"]
