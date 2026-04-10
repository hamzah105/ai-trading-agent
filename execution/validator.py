"""
execution/validator.py - Pre-execution trade validation pipeline.

Validates every decision before it reaches the executor.
Rejects invalid, unsafe, or ambiguous trades.
"""

from typing import Tuple

from execution.config import ExecutionConfig


def validate_trade(
    decision: dict,
    config: ExecutionConfig,
    current_balance: float,
    daily_loss_pct: float,
    consecutive_losses: int,
    price_data: float,  # current market price
) -> Tuple[bool, str]:
    """
    Validate a trade decision against all safety rules.
    Returns: (is_valid, reason)
    """

    # --- 1. Structure check ---
    if not decision or "decision" not in decision:
        return False, "INVALID_STRUCTURE: missing 'decision' key"

    dec = decision.get("decision", {})
    action = dec.get("action", "").lower()
    position_size = dec.get("position_size", 0.0)

    # --- 2. Action validation ---
    if action not in ("buy", "sell", "hold"):
        return False, f"INVALID_ACTION: '{action}' not in [buy, sell, hold]"

    if action == "hold":
        return True, "HOLD: Safe"

    # --- 3. Position size validation ---
    if not isinstance(position_size, (int, float)):
        return False, "INVALID_SIZE: position_size is not numeric"

    if position_size <= 0:
        return False, f"INVALID_SIZE: position_size={position_size} <= 0"

    if position_size > config.max_position_size:
        return False, (
            f"SIZE_LIMIT: requested={position_size:.4f}, "
            f"max={config.max_position_size:.4f}"
        )

    # --- 4. Balance check ---
    trade_amount = current_balance * position_size
    if trade_amount > current_balance * 0.95:
        return False, (
            f"INSUFFICIENT_BALANCE: need {trade_amount:.2f}, "
            f"have {current_balance:.2f}"
        )

    # --- 5. Daily loss circuit ---
    if daily_loss_pct >= config.max_daily_loss_pct:
        return False, (
            f"DAILY_LOSS_LIMIT: daily_loss={daily_loss_pct:.2%}, "
            f"limit={config.max_daily_loss_pct:.2%}"
        )

    # --- 6. Consecutive loss circuit ---
    if consecutive_losses >= config.max_consecutive_losses:
        return False, (
            f"CIRCUIT_BREAKER: {consecutive_losses} consecutive losses, "
            f"limit={config.max_consecutive_losses}"
        )

    # --- 7. Price data check ---
    if price_data is None or price_data <= 0:
        return False, "INVALID_PRICE: no valid market price"

    # --- 8. Signal sanity check ---
    signals = decision.get("signals", {})
    if not signals:
        return False, "MISSING_SIGNALS: empty signals block"

    confidence = decision.get("metadata", {}).get("confidence", 0.0)
    if confidence < 0.1:
        return False, f"LOW_CONFIDENCE: {confidence:.3f} < 0.1"

    return True, "VALID"
