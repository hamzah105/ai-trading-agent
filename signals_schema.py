"""signals_schema.py - Standardized signal definitions and output contract.

This module defines:
- The SignalType enum for strategy outputs
- TradingAction enum for final decisions
- DecisionOutput dataclass (the STRICT contract all agents must emit)
- Validation to ensure downstream agents can parse consistently
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SignalDirection(Enum):
    SHORT = -1
    HOLD = 0
    LONG = 1


class TradingAction(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class StrategySignal:
    """Output of a single strategy component."""
    name: str
    direction: SignalDirection        # -1, 0, +1
    confidence: float                  # [0, 1]

    def __post_init__(self):
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        if isinstance(self.direction, SignalDirection):
            self.direction = self.direction.value  # normalize to int


@dataclass
class DecisionOutput:
    """STRICT CONTRACT — this is what downstream Execution agents expect."""
    risk_level: float
    weights: dict[str, float]
    signals: dict[str, StrategySignal]
    decision: dict                     # {"action": TradingAction, "position_size": float}
    metadata: Optional[dict] = None    # extra info (timestamps, warnings)

    def to_dict(self) -> dict:
        """Serialize to plain dict for JSON / API handoff."""
        return {
            "risk_level": round(self.risk_level, 4),
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "signals": {
                k: {"direction": int(v.direction) if hasattr(v.direction, "value") else v.direction,
                    "confidence": round(v.confidence, 4)}
                for k, v in self.signals.items()
            },
            "decision": {
                "action": self.decision["action"].value
                if isinstance(self.decision["action"], TradingAction)
                else self.decision["action"],
                "position_size": round(self.decision["position_size"], 4),
            },
            "metadata": self.metadata or {},
        }
