"""
signals/momentum_module.py - Momentum Signal Generator

Uses: RSI, MACD, EMA trend filter
Output: {signal: -1/0/+1, confidence: [0,1], source: "momentum"}
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from indicators import ema, macd, rsi  # from Role 1


class MomentumSignal:
    """
    Combines RSI, MACD histogram, and EMA trend into a single momentum signal.
    Deterministic, no randomness.
    """

    def __init__(self, rsi_period: int = 14, macd_fast: int = 12,
                 macd_slow: int = 26, macd_sig: int = 9,
                 ema_period: int = 50):
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_sig = macd_sig
        self.ema_period = ema_period

    def generate(self, prices: np.ndarray) -> dict:
        """
        Generate momentum signal from price data.
        Returns: {"signal": int, "confidence": float, "source": str}
        """
        if prices is None or len(prices) < self.macd_slow + self.macd_sig + 1:
            return {"signal": 0, "confidence": 0.0, "source": "momentum",
                    "reason": "INSUFFICIENT_DATA"}

        signal = 0.0  # floating point for weighting
        agreement_count = 0
        total_indicators = 0

        # ── RSI Component ──────────────────────────────────────────
        rsi_vals = rsi(prices, self.rsi_period)
        if len(rsi_vals) > 0:
            current_rsi = float(rsi_vals[-1])
            rsi_signal, rsi_conf = self._rsi_signal(current_rsi)
            signal += rsi_signal * rsi_conf
            agreement_count += 1 if rsi_signal != 0 else 0
            total_indicators += 1

        # ── MACD Component ─────────────────────────────────────────
        mline, sline, hist = macd(prices, self.macd_fast, self.macd_slow, self.macd_sig)
        if len(hist) > 0:
            current_hist = float(hist[-1])
            macd_signal, macd_conf = self._macd_signal(current_hist, hist)
            signal += macd_signal * macd_conf
            agreement_count += 1 if macd_signal != 0 else 0
            total_indicators += 1

        # ── EMA Trend Component ───────────────────────────────────
        if len(prices) > self.ema_period:
            e = ema(prices, self.ema_period)
            if len(e) > 1:
                slope = (e[-1] - e[-2]) / max(e[-2], 1e-9)
                ema_signal, ema_conf = self._ema_signal(slope)
                signal += ema_signal * ema_conf
                agreement_count += 1 if ema_signal != 0 else 0
                total_indicators += 1

        # ── Determine Final Signal ────────────────────────────────
        if total_indicators == 0:
            return {"signal": 0, "confidence": 0.0, "source": "momentum",
                    "reason": "NO_INDICATORS_COMPUTED"}

        avg_signal = signal / total_indicators

        if avg_signal > 0.15:
            final = 1
        elif avg_signal < -0.15:
            final = -1
        else:
            final = 0

        # Confidence: based on indicator agreement
        if total_indicators > 1:
            # Count how many agree with majority direction
            directions = []
            if "rsi_signal" in dir(self):
                d, c = self._last_rsi, self._last_rsi_conf
                directions.append((d, c))
            if "rsi_signal" not in dir(self):
                # recalculate agreement
                pass
            direction_signs = []
            if len(rsi_vals) > 0:
                direction_signs.append(np.sign(rsi_signal))
            if len(hist) > 0:
                direction_signs.append(np.sign(macd_signal))
            if len(prices) > self.ema_period:
                direction_signs.append(np.sign(ema_signal))

            non_zero = [d for d in direction_signs if d != 0]
            if len(non_zero) >= 2:
                majority = max(set(non_zero), key=non_zero.count)
                agree_pct = non_zero.count(majority) / len(non_zero)
                confidence = max(0.1, min(1.0, agree_pct * 0.7 + 0.15))
            else:
                confidence = 0.35
        else:
            confidence = 0.35

        return {
            "signal": final,
            "confidence": round(confidence, 4),
            "source": "momentum",
            "details": {
                "rsi": round(current_rsi, 2) if len(rsi_vals) > 0 else None,
                "macd_hist": round(current_hist, 6) if len(hist) > 0 else None,
            },
        }

    def _rsi_signal(self, rsi_val: float) -> tuple:
        """RSI: <30 oversold=BUY, >70 overbought=SELL, else neutral."""
        if rsi_val < 30:
            conf = (30 - rsi_val) / 30  # 0->1 as deeper oversold
            return (1, max(0.1, conf))
        elif rsi_val > 70:
            conf = (rsi_val - 70) / 30
            return (-1, max(0.1, conf))
        else:
            return (0, 0.2)

    def _macd_signal(self, hist_val: float, hist_arr: np.ndarray) -> tuple:
        """MACD histogram: positive=BUY, negative=SELL."""
        if hist_val > 0:
            strength = min(1.0, abs(hist_val) / (np.std(hist_arr) + 1e-9))
            return (1, max(0.1, strength * 0.6 + 0.2))
        elif hist_val < 0:
            strength = min(1.0, abs(hist_val) / (np.std(hist_arr) + 1e-9))
            return (-1, max(0.1, strength * 0.6 + 0.2))
        return (0, 0.2)

    def _ema_signal(self, slope: float) -> tuple:
        """EMA slope: positive=uptrend, negative=downtrend."""
        if abs(slope) < 0.002:
            return (0, 0.15)
        elif slope > 0:
            strength = min(1.0, abs(slope) / 0.05)
            return (1, max(0.15, strength * 0.5 + 0.2))
        else:
            strength = min(1.0, abs(slope) / 0.05)
            return (-1, max(0.15, strength * 0.5 + 0.2))
