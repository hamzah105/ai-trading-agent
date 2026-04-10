"""
config.py - Strategy configuration and risk parameter management.

Handles:
- Risk parameter (R) validation: R in [0, 1]
- Strategy weight curve selection (linear / logistic)
- Output schema contract enforcement
- All tunable parameters for the Quant Architect Agent
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class StrategyConfig:
    """Configuration for the Quant/Strategy Architect Agent."""

    # --- Risk Parameter ---
    risk: float = 0.5
    risk_mode: Literal["linear", "logistic"] = "logistic"

    # --- Base Weights ---
    base_momentum: float = 0.5
    base_sentiment: float = 0.3
    base_risk_manager: float = 1.0

    # --- Indicator Periods ---
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    ema_trend_period: int = 50
    adx_period: int = 14
    adx_threshold: float = 25.0
    bb_period: int = 20
    bb_std: float = 2.0

    # --- Position Sizing ---
    max_position_pct: float = 0.25
    min_confidence: float = 0.15
    conflict_threshold: float = 0.6

    # --- Decision Stability ---
    decision_threshold: float = 0.15
    hysteresis_band: float = 0.05

    # --- Exit Logic ---
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    trailing_stop_pct: float = 0.015

    # --- Costs ---
    fee_pct: float = 0.0026     # ~0.26% Kraken typical
    slippage_pct: float = 0.001 # 0.1%

    # --- Regime Control ---
    regime_weight_factor: float = 0.3  # influence of regime on weights

    # --- Confidence Model Tuning ---
    confidence_volatility_penalty: float = 0.2
    confidence_agreement_boost: float = 0.3

    # --- Risk Limits (Backtest Safety) ---
    max_drawdown_limit: float = 0.2

    # --- Safety ---
    paper_trading: bool = True
    require_approval_live: bool = True

    # --- Paths ---
    data_dir: str = "data"
    log_dir: str = "logs"

    def __post_init__(self):
        # Clamp risk safely
        self.risk = max(0.0, min(1.0, float(self.risk)))

    def validate(self) -> bool:
        """Validate configuration values."""
        checks = [
            # Risk
            0.0 <= self.risk <= 1.0,

            # Weights
            self.base_momentum >= 0,
            self.base_sentiment >= 0,
            self.base_risk_manager >= 0,

            # Position sizing
            0.0 <= self.min_confidence <= 1.0,
            0.0 <= self.max_position_pct < 1.0,

            # Decision stability
            0.0 <= self.decision_threshold < 1.0,
            0.0 <= self.hysteresis_band < 0.5,

            # Costs
            0.0 <= self.fee_pct < 0.01,
            0.0 <= self.slippage_pct < 0.01,

            # Indicators
            self.rsi_period > 0,
            self.macd_fast > 0,
            self.macd_slow > self.macd_fast,
            self.macd_signal > 0,
            self.ema_trend_period > 0,
            self.adx_period > 0,
            self.adx_threshold > 0,
            self.bb_period > 0,
            self.bb_std > 0,

            # Exit logic
            self.stop_loss_pct > 0,
            self.take_profit_pct > 0,
            self.trailing_stop_pct > 0,

            # Regime + confidence
            0.0 <= self.regime_weight_factor <= 1.0,
            0.0 <= self.confidence_volatility_penalty <= 1.0,
            0.0 <= self.confidence_agreement_boost <= 1.0,

            # Risk safety
            0.0 < self.max_drawdown_limit < 1.0,
        ]

        return all(checks)