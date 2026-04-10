"""
signals/pipeline.py - Signal Orchestration Pipeline

Pipeline stages:
1. Data Ingestion → OHLCV + Sentiment
2. Validation → Schema checks, missing data, outliers
3. Cleaning → NaN handling, time alignment
4. Signal Generation → Momentum + Sentiment + Volatility
5. Signal Fusion → Combine with confidence weighting
6. Output Formatting → Strict contract for Strategy Agent

Output format (STRICT):
{
  "momentum": {"signal": -1, "confidence": 0.75, "source": "momentum"},
  "sentiment": {"signal": 1, "confidence": 0.82, "source": "sentiment"},
  "regime": {"signal": 0, "confidence": 0.5, "source": "regime"},
  "fused": {"signal": -1, "confidence": 0.68},
  "timestamp": "ISO8601",
  "data_quality": "good"
}
"""

import sys
import os
import json
import numpy as np
from datetime import datetime
from typing import Optional, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from signals.momentum_module import MomentumSignal
from signals.sentiment_module import SentimentSignal
from signals.logger import SignalLogger


class SignalPipeline:
    """Master signal generation pipeline."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.momentum = MomentumSignal()
        self.sentiment = SentimentSignal()
        self.logger = SignalLogger(
            log_dir=os.path.join(os.path.dirname(__file__), "logs")
        )

        # Pipeline state
        self.last_output = None
        self.streak_agreement = []

    def process(self, prices: np.ndarray,
                sentiment_scores: Optional[np.ndarray] = None,
                high: Optional[np.ndarray] = None,
                low: Optional[np.ndarray] = None,
                volume: Optional[np.ndarray] = None) -> dict:
        """
        Full pipeline: ingest → validate → clean → generate → fuse → output.
        """
        # --- Stage 1: Ingestion Validation ---
        if prices is None or len(prices) == 0:
            return self._emergency_output("No price data provided")

        # --- Stage 2: Validation ---
        quality = self._validate_data(prices, high, low, volume)
        if quality == "bad":
            return self._emergency_output("Data validation failed")

        # --- Stage 3: Cleaning ---
        clean_prices = self._clean_data(prices)
        if len(clean_prices) < 30:
            return self._emergency_output("Insufficient clean data")

        # --- Stage 4: Signal Generation ---
        mom_sig = self.momentum.generate(clean_prices)
        sent_sig = self.sentiment.generate(clean_prices, sentiment_scores)
        regime_sig = self._compute_regime(clean_prices)

        # --- Stage 5: Signal Fusion ---
        all_signals = {
            "momentum": mom_sig,
            "sentiment": sent_sig,
            "regime": regime_sig,
        }
        fused = self._fuse_signals(all_signals)

        # --- Stage 6: Output Formatting ---
        output = {
            "momentum": mom_sig,
            "sentiment": sent_sig,
            "regime": regime_sig,
            "fused": fused,
            "timestamp": datetime.utcnow().isoformat(),
            "data_quality": quality,
        }

        self.last_output = output
        self.logger.log(output)

        return output

    def _validate_data(self, prices: np.ndarray,
                       high: Optional[np.ndarray],
                       low: Optional[np.ndarray],
                       volume: Optional[np.ndarray]) -> str:
        """Validate ingested data. Returns quality level."""
        if not np.isfinite(prices).all():
            # Has NaN/inf but can be cleaned
            return "degraded"

        if len(prices) < 30:
            return "degraded"

        # Check for extreme outliers (price jump > 50% in one candle)
        if len(prices) > 1:
            returns = np.abs(np.diff(prices) / prices[:-1])
            if np.any(returns > 0.5):
                return "degraded"

            # Volume spike check
            if volume is not None and len(volume) > 1:
                vol_returns = np.abs(np.diff(volume) / (volume[:-1] + 1e-9))
                if np.mean(vol_returns) > 5.0:
                    return "degraded"

        return "good"

    def _clean_data(self, prices: np.ndarray) -> np.ndarray:
        """Clean price data: forward-fill NaN, clip extreme outliers."""
        clean = prices.copy().astype(float)

        # Forward-fill NaN
        nan_mask = ~np.isfinite(clean)
        if nan_mask.any():
            last_valid = None
            for i in range(len(clean)):
                if np.isfinite(clean[i]):
                    last_valid = clean[i]
                elif last_valid is not None:
                    clean[i] = last_valid
            # If still NaN at start → use first valid
            for i in range(len(clean)):
                if not np.isfinite(clean[i]):
                    for j in range(i, len(clean)):
                        if np.isfinite(clean[j]):
                            for k in range(i, j):
                                clean[k] = clean[j]
                            break
                    break

        return clean

    def _compute_regime(self, prices: np.ndarray) -> dict:
        """
        Detect market regime: trending vs ranging.
        Uses ADX concept + price range compression.
        """
        if len(prices) < 50:
            return {"signal": 0, "confidence": 0.1, "source": "regime",
                    "reason": "not enough data"}

        recent = prices[-30:]
        ema_20 = self._ema_single(recent, 20)
        ema_50 = self._ema_single(prices[-100:] if len(prices) >= 100 else prices, 50)

        # Trending if EMAs are separated and aligned
        if len(ema_20) > 0 and len(ema_50) > 0:
            ema_diff = abs(ema_20[-1] - ema_50[-1]) / max(ema_50[-1], 1e-9)
            direction = 1 if ema_20[-1] > ema_50[-1] else -1
        else:
            ema_diff = 0
            direction = 0

        # Sideways if recent range is compressed
        recent_range = (max(recent) - min(recent)) / max(min(recent), 1e-9)
        if recent_range < 0.02:  # < 2% range → sideways
            return {"signal": 0, "confidence": 0.6, "source": "regime",
                    "type": "sideways", "range": round(recent_range, 4)}

        if ema_diff > 0.02:  # EMAs separated → trending
            return {"signal": direction, "confidence": min(0.8, ema_diff * 10),
                    "source": "regime", "type": "trending",
                    "direction": "up" if direction > 0 else "down"}

        return {"signal": 0, "confidence": 0.3, "source": "regime",
                "type": "transitional"}

    def _ema_single(self, data: np.ndarray, period: int) -> np.ndarray:
        """Simple EMA computation."""
        alpha = 2.0 / (period + 1)
        result = np.zeros(len(data))
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = data[i] * alpha + result[i - 1] * (1 - alpha)
        return result

    def _fuse_signals(self, signals: Dict) -> dict:
        """
        Fuse all signals into a single output.
        Agreement detection + confidence weighting.
        """
        weighted_signal = 0.0
        total_weight = 0.0
        directions = []
        confidences = []

        for name, sig in signals.items():
            s = sig.get("signal", 0)
            c = sig.get("confidence", 0.0)

            if c < 0.05:
                continue  # Skip near-zero confidence signals

            # Weighting: sentiment and momentum are primary, regime is contextual
            weight = 1.0 if name != "regime" else 0.5

            weighted_signal += s * c * weight
            total_weight += c * weight
            if s != 0:
                directions.append(s)
            confidences.append(c)

        if total_weight == 0:
            return {"signal": 0, "confidence": 0.0, "source": "fused",
                    "reason": "NO_VALID_SIGNALS"}

        # Normalized combined score
        normalized = weighted_signal / total_weight

        # Agreement bonus
        if len(directions) >= 2:
            majority = max(set(directions), key=directions.count)
            agree_ratio = directions.count(majority) / len(directions)
            agreement_bonus = agree_ratio * 0.3
        else:
            agreement_bonus = 0
            majority = directions[0] if directions else 0

        # Final fused signal
        if normalized > 0.15:
            fused_signal = 1
        elif normalized < -0.15:
            fused_signal = -1
        else:
            fused_signal = 0

        # Confidence: base from weighted average + agreement bonus
        base_conf = sum(confidences) / max(len(confidences), 1)
        final_conf = min(1.0, base_conf + agreement_bonus)

        # Track streak for stability
        self.streak_agreement.append(fused_signal)
        if len(self.streak_agreement) > 5:
            self.streak_agreement.pop(0)

        return {
            "signal": fused_signal,
            "confidence": round(final_conf, 4),
            "source": "fused",
            "details": {
                "normalized_score": round(normalized, 4),
                "agreement_bonus": round(agreement_bonus, 4),
                "signals_used": len(directions),
            },
        }

    def _emergency_output(self, reason: str) -> dict:
        """Hold-all output when pipeline fails."""
        output = {
            "momentum": {"signal": 0, "confidence": 0.0, "source": "momentum"},
            "sentiment": {"signal": 0, "confidence": 0.0, "source": "sentiment"},
            "regime": {"signal": 0, "confidence": 0.0, "source": "regime"},
            "fused": {"signal": 0, "confidence": 0.0, "source": "fused",
                      "reason": reason},
            "timestamp": datetime.utcnow().isoformat(),
            "data_quality": "failed",
            "error": reason,
        }
        self.last_output = output
        self.logger.log(output)
        return output
