"""signals/config.py - Signal Agent configuration.

Handles:
- Sentiment API settings
- Validation thresholds
- Pipeline tuning parameters
"""

import os


class SignalConfig:
    """Configuration for the Data/AI Signal Engine."""

    # --- Timeframes ---
    PRIMARY_TIMEFRAME: int = 240       # 4-hour bars (Kraken interval)
    SECONDARY_TIMEFRAME: int = 60      # 1-hour for confirmation

    # --- Sentiment API ---
    PRISM_API_URL: str = os.environ.get("PRISM_API_URL", "")
    PRISM_API_KEY: str = os.environ.get("PRISM_API_KEY", "")

    # --- Validation Thresholds ---
    MIN_DATA_POINTS: int = 30
    MAX_PRICE_JUMP: float = 0.50       # 50% single-candle jump = anomaly
    MAX_CONSECUTIVE_NANS: int = 5

    # --- Signal Thresholds ---
    SIGNAL_BUY_THRESHOLD: float = 0.15
    SIGNAL_SELL_THRESHOLD: float = -0.15
    MIN_CONFIDENCE: float = 0.1        # Below this -> HOLD

    # --- Momentum Tuning ---
    RSI_PERIOD: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    EMA_TREND: int = 50

    # --- Fusion Weights ---
    WEIGHT_MOMENTUM: float = 1.0
    WEIGHT_SENTIMENT: float = 1.0
    WEIGHT_REGIME: float = 0.5         # Contextual, not primary

    # --- Cache ---
    CACHE_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data"
    )
    CACHE_TTL_SECONDS: int = 3600      # 1 hour

    @staticmethod
    def validate() -> bool:
        """Check config sanity."""
        checks = [
            SignalConfig.MIN_DATA_POINTS > 0,
            SignalConfig.MAX_PRICE_JUMP > 0,
            0.0 <= SignalConfig.SIGNAL_BUY_THRESHOLD <= 1.0,
            0.0 <= SignalConfig.MIN_CONFIDENCE <= 1.0,
            SignalConfig.RSI_PERIOD > 0,
            SignalConfig.MACD_SLOW > SignalConfig.MACD_FAST,
            SignalConfig.WEIGHT_MOMENTUM > 0,
            SignalConfig.WEIGHT_SENTIMENT > 0,
            SignalConfig.WEIGHT_REGIME >= 0,
        ]
        return all(checks)

    @staticmethod
    def status() -> dict:
        """Return config status summary."""
        return {
            "timeframe_primary": f"{SignalConfig.PRIMARY_TIMEFRAME}min",
            "sentiment_api": "configured" if SignalConfig.PRISM_API_KEY else "not set",
            "min_data_points": SignalConfig.MIN_DATA_POINTS,
            "cache_dir": SignalConfig.CACHE_DIR,
        }
