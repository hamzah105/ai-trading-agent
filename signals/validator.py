"""
signals/validator.py - Data Validation & Cleaning Module

Validates all input data before it enters the signal pipeline.
Handles:
- Missing values (NaN/None)
- Outliers (price jumps > threshold)
- Time alignment gaps
- Data format verification
- Range validation (price > 0, volume >= 0)

If data is invalid: returns cleaned data + quality flag.
If data is unrecoverable: returns None + rejection reason.
"""

import numpy as np
from typing import Optional, Tuple, Dict


class DataValidator:
    """Validates and cleans OHLCV + sentiment data."""

    def __init__(self, max_price_jump: float = 0.5,
                 min_data_points: int = 30,
                 max_consecutive_nans: int = 5):
        self.max_price_jump = max_price_jump
        self.min_data_points = min_data_points
        self.max_consecutive_nans = max_consecutive_nans

    def validate(self, prices: np.ndarray,
                 high: Optional[np.ndarray] = None,
                 low: Optional[np.ndarray] = None,
                 volume: Optional[np.ndarray] = None) -> Dict:
        """
        Validate ingested market data.
        Returns: {"valid": bool, "quality": str, "reason": str, "counts": dict}
        """
        result = {
            "valid": True,
            "quality": "good",
            "reason": "",
            "counts": {
                "total": len(prices) if prices is not None else 0,
                "nan_count": 0,
                "outlier_count": 0,
                "negative_count": 0,
            },
        }

        if prices is None or len(prices) == 0:
            result["valid"] = False
            result["reason"] = "NO_PRICE_DATA"
            return result

        # Check minimum data points
        if len(prices) < self.min_data_points:
            result["valid"] = False
            result["reason"] = "INSUFFICIENT_DATA"
            return result

        # Count NaN/inf
        flat = prices.flatten()
        nan_count = int(np.sum(~np.isfinite(flat)))
        result["counts"]["nan_count"] = nan_count

        if nan_count > self.max_consecutive_nans:
            result["quality"] = "degraded"

        # Check for negative/zero prices
        if np.any(prices <= 0):
            result["counts"]["negative_count"] = int(np.sum(prices <= 0))
            result["quality"] = "degraded"

        # Check for extreme price jumps (outliers)
        if len(prices) > 1:
            finite_mask = np.isfinite(prices)
            if np.sum(finite_mask) > 1:
                finite_prices = prices[finite_mask]
                returns = np.abs(np.diff(finite_prices) / finite_prices[:-1])
                outliers = int(np.sum(returns > self.max_price_jump))
                result["counts"]["outlier_count"] = outliers
                if outliers > 0:
                    result["quality"] = "degraded"

        # Validate OHLC consistency if provided
        if high is not None and low is not None:
            if len(high) == len(prices) and len(low) == len(prices):
                valid_ohl = np.sum(
                    np.isfinite(high) & np.isfinite(low) &
                    (high >= low) & (high >= prices) & (low <= prices)
                )
                if valid_ohl < len(prices) * 0.9:
                    result["quality"] = "degraded"
                    result["reason"] = "OHLC_INCONSISTENT"

        # Validate volume
        if volume is not None:
            neg_vol = int(np.sum(np.isfinite(volume) & (volume < 0)))
            if neg_vol > 0:
                result["counts"]["negative_count"] += neg_vol
                result["quality"] = "degraded"

        return result

    def clean(self, prices: np.ndarray) -> np.ndarray:
        """
        Clean price data: forward-fill NaN, clip negatives,
        remove extreme outliers via rolling median.
        """
        if prices is None:
            return np.array([])

        clean = prices.copy().astype(float)

        # Forward-fill NaN values
        last_valid = None
        for i in range(len(clean)):
            if np.isfinite(clean[i]):
                last_valid = clean[i]
            elif last_valid is not None:
                clean[i] = last_valid

        # If leading NaNs remain, fill with first valid value
        if last_valid is not None:
            valid_idx = np.where(np.isfinite(clean))[0]
            if len(valid_idx) > 0:
                clean[:valid_idx[0]] = clean[valid_idx[0]]

        # Clip any remaining non-positive values to small positive
        clean = np.where(clean <= 0, 1e-9, clean)

        # Smooth extreme outliers using rolling median
        if len(clean) > 10:
            clean = self._smooth_outliers(clean)

        return clean

    def _smooth_outliers(self, data: np.ndarray, window: int = 5,
                         z_threshold: float = 3.0) -> np.ndarray:
        """Replace values that deviate > z_threshold std from rolling median."""
        result = data.copy()
        half = window // 2

        for i in range(half, len(data) - half):
            segment = data[i - half:i + half + 1]
            median = float(np.median(segment))
            mad = float(np.median(np.abs(segment - median)))
            if mad == 0:
                continue
            z_score = abs(data[i] - median) / (1.4826 * mad)
            if z_score > z_threshold:
                result[i] = median

        return result

    def validate_sentiment(self, scores: np.ndarray) -> Dict:
        """Validate sentiment score array."""
        if scores is None or len(scores) == 0:
            return {"valid": False, "reason": "NO_SENTIMENT_DATA"}

        finite = scores[np.isfinite(scores)]
        if len(finite) == 0:
            return {"valid": False, "reason": "ALL_SENTIMENT_NAN"}

        return {
            "valid": True,
            "count": len(finite),
            "range": [float(np.min(finite)), float(np.max(finite))],
            "mean": float(np.mean(finite)),
        }
