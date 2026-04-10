"""
signals/sentiment_module.py - Sentiment Signal Generator

Supports:
- PRISM API (primary: external API with API key via env)
- Manual scores (for testing / mock data)
- External signal files (raw JSON/text scores)

Output: {signal: -1/0/+1, confidence: [0,1], source: "sentiment"}
"""

import os
import json
import urllib.request
import urllib.error
import numpy as np
from typing import Optional


class SentimentSignal:
    """
    Generates sentiment signals from PRISM API or manual scores.
    Falls back to HOLD on any API failure.
    """

    # --- Config (from env) ---
    PRISM_API_URL = os.environ.get("PRISM_API_URL", "")
    PRISM_API_KEY = os.environ.get("PRISM_API_KEY", "")

    def __init__(self):
        self.cached_scores = []
        self.last_signal = {"signal": 0, "confidence": 0.0}

    def generate(self, price_data: Optional[np.ndarray] = None,
                 manual_scores: Optional[np.ndarray] = None,
                 use_prism: bool = True) -> dict:
        """
        Generate sentiment signal.
        Priority: PRISM API > Manual scores > Previous state.
        """
        # Try PRISM API first
        if use_prism and self.PRISM_API_KEY and self.PRISM_API_URL:
            try:
                scores = self._fetch_prism()
                if scores is not None and len(scores) > 0:
                    return self._compute_signal(scores)
            except Exception:
                pass  # Fall through

        # Use manual scores if provided
        if manual_scores is not None and len(manual_scores) > 0:
            return self._compute_signal(manual_scores)

        # No data available
        return {"signal": 0, "confidence": 0.0, "source": "sentiment",
                "reason": "NO_SENTIMENT_DATA"}

    def _fetch_prism(self) -> Optional[np.ndarray]:
        """Fetch sentiment scores from PRISM API."""
        if not self.PRISM_API_URL:
            return None

        req = urllib.request.Request(
            self.PRISM_API_URL,
            headers={
                "Authorization": f"Bearer {self.PRISM_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "Signal-Agent/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        # Expected format: {"scores": [float, ...]} or similar
        scores = data.get("scores", data.get("data", []))
        return np.array(scores, dtype=float) if scores else None

    def _compute_signal(self, scores: np.ndarray) -> dict:
        """
        Convert sentiment scores to signal + confidence.
        Scores should be in any numeric range, normalized internally.
        """
        # Clean: remove NaN/inf
        scores = scores[np.isfinite(scores)]
        if len(scores) == 0:
            return {"signal": 0, "confidence": 0.0, "source": "sentiment",
                    "reason": "EMPTY_SCORES"}

        avg = float(np.mean(scores))
        std = float(np.std(scores))

        # Normalize to [-1, +1] range using tanh
        normalized = np.tanh(avg)
        vol_penalty = min(1.0, std / 2.0)  # High volatility -> lower confidence

        if normalized > 0.15:
            signal = 1
            confidence = max(0.1, min(0.95, abs(normalized) - vol_penalty))
        elif normalized < -0.15:
            signal = -1
            confidence = max(0.1, min(0.95, abs(normalized) - vol_penalty))
        else:
            signal = 0
            confidence = max(0.1, 1.0 - abs(normalized) - vol_penalty)

        result = {
            "signal": signal,
            "confidence": round(confidence, 4),
            "source": "sentiment",
            "details": {
                "avg_score": round(avg, 6),
                "normalized": round(normalized, 4),
                "vol_penalty": round(vol_penalty, 4),
                "n_scores": len(scores),
            },
        }

        self.last_signal = result
        return result
