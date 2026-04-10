"""
data_feed.py - Kraken public OHLCV data fetcher (no API key needed).

Provides:
- fetch_ohlcv_kraken(pair, interval, limit) via Kraken REST API
- Returns numpy arrays: (timestamp, open, high, low, close, volume)
- Fallback to cached/synthetic data on network errors

Public endpoint -- no authentication required.
"""

import json
import os
import urllib.request
import urllib.error
import numpy as np
from datetime import datetime

KRAKEN_API = "https://api.kraken.com/0/public/OHLC"

# Common pair mappings
PAIRS = {
    "BTC/USD": "XXBTZUSD",
    "ETH/USD": "XETHZUSD",
    "SOL/USD": "SOLUSD",
    "BTC/EUR": "XXBTZEUR",
    "ETH/EUR": "XETHZEUR",
}

# Valid Kraken intervals (minutes)
VALID_INTERVALS = [1, 5, 15, 30, 60, 240, 1440, 10080, 21600]

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")


def _pair_key(pair: str) -> str:
    return PAIRS.get(pair, pair.replace("/", ""))


def fetch_ohlcv_kraken(
    pair: str = "BTC/USD",
    interval: int = 240,  # 4-hour
    limit: int = 200,
    use_cache: bool = True,
) -> dict:
    """
    Fetch OHLCV from Kraken public API.
    Returns dict with numpy arrays: close, open, high, low, volume, timestamps.
    Falls back to cached data if network fails.
    """
    if interval not in VALID_INTERVALS:
        interval = 240

    pair_key = _pair_key(pair)
    url = f"{KRAKEN_API}?pair={pair_key}&interval={interval}"

    # Try cache first
    cache_file = os.path.join(CACHE_DIR, f"ohlcv_{pair_key}_{interval}.json")
    if use_cache and os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cached = json.load(f)
            data = cached.get("data", [])
            if len(data) >= limit:
                return _parse_kraken_data(data, pair=pair)
        except Exception:
            pass

    # Fetch from API
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Quant-Agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode())
    except Exception as e:
        print(f"[data_feed] Kraken fetch failed: {e}")
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                cached = json.load(f)
            return _parse_kraken_data(cached.get("data", []), pair=pair)
        return {}

    # Parse response
    result_key = None
    for k in raw.get("result", {}):
        if k != "last":
            result_key = k
            break

    if not result_key or result_key not in raw["result"]:
        print("[data_feed] Invalid Kraken response")
        return {}

    data = raw["result"][result_key]

    # Save cache
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(cache_file, "w") as f:
            json.dump({"pair": pair, "interval": interval, "data": data}, f)
    except Exception:
        pass

    return _parse_kraken_data(data, pair=pair)


def _parse_kraken_data(data: list, pair: str = "") -> dict:
    """Convert Kraken OHLCV list to numpy arrays."""
    if not data:
        return {}

    arr = np.array(data, dtype=float)
    # Kraken: [time, open, high, low, close, vwap, volume, count]
    return {
        "timestamps": arr[:, 0],
        "open": arr[:, 1],
        "high": arr[:, 2],
        "low": arr[:, 3],
        "close": arr[:, 4],
        "vwap": arr[:, 5],
        "volume": arr[:, 6],
        "count": arr[:, 7],
        "pair": pair,
    }


def get_prices(data: dict) -> np.ndarray:
    """Extract close prices from OHLCV dict. Returns empty array on failure."""
    return data.get("close", np.array([]))


if __name__ == "__main__":
    print("Fetching BTC/USD 4h OHLCV from Kraken...")
    result = fetch_ohlcv_kraken("BTC/USD", interval=240, limit=100)
    if result:
        prices = get_prices(result)
        print(f"Got {len(prices)} candles")
        print(f"Latest: ${prices[-1]:,.2f}")
        print(f"Range:  ${prices.min():,.2f} - ${prices.max():,.2f}")
    else:
        print("No data returned (check network)")
