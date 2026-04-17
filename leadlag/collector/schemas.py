import pyarrow as pa

TICK_SCHEMA = pa.schema([
    ("ts_ms", pa.int64()),
    ("ts_exchange_ms", pa.int64()),
    ("price", pa.float64()),
    ("qty", pa.float64()),
    ("side", pa.string()),
    ("venue", pa.string()),
])

BBO_SCHEMA = pa.schema([
    ("ts_ms", pa.int64()),
    ("bid_price", pa.float64()),
    ("bid_qty", pa.float64()),
    ("ask_price", pa.float64()),
    ("ask_qty", pa.float64()),
    ("venue", pa.string()),
])
