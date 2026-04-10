"""
execution/config.py - Execution Agent configuration.

Separate from strategy_math config. Controls:
- Execution mode (DRY_RUN / PAPER / LIVE)
- Safety limits (daily loss, circuit breaker, position caps)
- Retry/backoff parameters
- API key paths (env-based)
"""

from dataclasses import dataclass
from enum import Enum
import os


class ExecutionMode(Enum):
    DRY_RUN = "dry_run"     # Simulate only, full logging
    PAPER = "paper"         # Sandbox/kraken demo
    LIVE = "live"           # REAL trading — disabled by default


@dataclass
class ExecutionConfig:
    """Execution layer configuration."""

    # --- Mode ---
    mode: ExecutionMode = ExecutionMode.DRY_RUN

    # --- Kraken API (loaded from env) ---
    api_key: str = ""
    api_secret: str = ""

    # --- Costs ---
    fee_pct: float = 0.0026
    slippage_pct: float = 0.001

    # --- Pair ---
    pair: str = "BTC/USD"

    # --- Safety Limits ---
    max_position_size: float = 0.25          # Max 25% of portfolio per trade
    max_daily_loss_pct: float = 0.05         # Halt after 5% daily loss
    max_consecutive_losses: int = 3          # Circuit breaker threshold

    # --- Retry ---
    max_retries: int = 3
    retry_backoff_base: float = 2.0          # Exponential: 2s, 4s, 8s
    request_timeout: float = 15.0

    # --- Polling ---
    poll_interval_seconds: float = 30.0      # How often to check for decisions

    # --- State ---
    initial_balance: float = 10000.0         # Starting portfolio for PnL

    def __post_init__(self):
        # Load API keys from env
        if not self.api_key:
            self.api_key = os.environ.get("KRAKEN_API_KEY", "")
        if not self.api_secret:
            self.api_secret = os.environ.get("KRAKEN_API_SECRET", "")

        # Safety: LIVE mode requires explicit env flag
        mode_env = os.environ.get("EXECUTION_MODE", "dry_run").lower()
        if mode_env == "live":
            if not self.api_key or not self.api_secret:
                print("[WARN] LIVE mode requested but no API keys found. Falling to DRY_RUN.")
                self.mode = ExecutionMode.DRY_RUN
            else:
                self.mode = ExecutionMode.LIVE
        elif mode_env == "paper":
            self.mode = ExecutionMode.PAPER
        else:
            self.mode = ExecutionMode.DRY_RUN

    def validate(self) -> bool:
        checks = [
            0.0 < self.max_position_size <= 1.0,
            0.0 < self.max_daily_loss_pct < 1.0,
            self.max_consecutive_losses > 0,
            self.max_retries >= 0,
            self.request_timeout > 0,
            self.poll_interval_seconds > 0,
        ]
        if self.mode == ExecutionMode.LIVE:
            checks.append(bool(self.api_key and self.api_secret))
        return all(checks)
