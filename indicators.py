"""
indicators.py - Technical indicator implementations (pure numpy).

Provides:
- EMA, SMA
- MACD
- ADX (Average Directional Index)
- RSI (shared reference)
- Bollinger Bands
- ATR (Average True Range)

No external TA library — all numpy. Deterministic, testable.
"""

import numpy as np
from typing import Tuple


# ── Moving Averages ─────────────────────────────────────────────────
def sma(data: np.ndarray, period: int) -> np.ndarray:
    kernel = np.ones(period) / period
    return np.convolve(data, kernel, mode="valid")


def ema(data: np.ndarray, period: int) -> np.ndarray:
    alpha = 2.0 / (period + 1)
    result = np.empty_like(data, dtype=float)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = data[i] * alpha + result[i - 1] * (1 - alpha)
    return result


# ── RSI ─────────────────────────────────────────────────────────────
def rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = ema(gains, period)
    avg_loss = ema(losses, period)

    rs = np.where(avg_loss == 0, 100.0, avg_gain / np.where(avg_loss == 0, 1, avg_loss))
    return 100.0 - (100.0 / (1.0 + rs))


# ── MACD ────────────────────────────────────────────────────────────
def macd(
    prices: np.ndarray, fast: int = 12, slow: int = 26, sig: int = 9
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    fast_line = ema(prices, fast)
    slow_line = ema(prices, slow)
    macd_line = fast_line - slow_line
    signal_line = ema(macd_line, sig)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ── ADX ─────────────────────────────────────────────────────────────
def adx(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Compute ADX (Average Directional Index).
    Returns array of ADX values. ADX > 25 = trending, ADX < 25 = ranging.
    """
    highs = prices
    lows = prices
    closes = prices

    if len(prices) < period + 1:
        return np.array([])

    tr1 = highs[1:] - lows[1:]
    tr2 = np.abs(highs[1:] - closes[:-1])
    tr3 = np.abs(lows[1:] - closes[:-1])
    true_range = np.maximum(np.maximum(tr1, tr2), tr3)

    plus_dm = np.where((highs[1:] - highs[:-1]) > (lows[:-1] - lows[1:]),
                       np.maximum(highs[1:] - highs[:-1], 0), 0)
    minus_dm = np.where((lows[:-1] - lows[1:]) > (highs[1:] - highs[:-1]),
                        np.maximum(lows[:-1] - lows[1:], 0), 0)

    atr = ema(true_range, period)
    plus_di = 100.0 * ema(plus_dm, period) / np.where(atr == 0, 1, atr)
    minus_di = 100.0 * ema(minus_dm, period) / np.where(atr == 0, 1, atr)

    dx = 100.0 * np.abs(plus_di - minus_di) / np.where(
        (plus_di + minus_di) == 0, 1, (plus_di + minus_di)
    )

    adx_values = ema(dx, period)
    return adx_values


# ── Bollinger Bands ─────────────────────────────────────────────────
def bollinger_bands(
    prices: np.ndarray, period: int = 20, std_mult: float = 2.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    sma_line = sma(prices, period)
    # Align lengths
    sma_aligned = np.full_like(prices, np.nan)
    offset = period - 1
    sma_aligned[offset:] = sma_line

    rolling_std = np.zeros_like(prices)
    for i in range(period - 1, len(prices)):
        rolling_std[i] = np.std(prices[i - period + 1:i + 1])

    upper = sma_aligned + std_mult * rolling_std
    lower = sma_aligned - std_mult * rolling_std
    return upper, sma_aligned, lower


# ── ATR ──────────────────────────────────────────────────────────────
def atr(prices: np.ndarray, period: int = 14) -> float:
    tr = np.abs(np.diff(prices))
    return float(np.mean(tr[-period:])) if len(tr) >= period else float(np.mean(tr))


# ── EMA Trend Filter ────────────────────────────────────────────────
def ema_slope(prices: np.ndarray, period: int = 50) -> float:
    e = ema(prices, period)
    if len(e) < 2:
        return 0.0
    return (e[-1] - e[-2]) / e[-2]
