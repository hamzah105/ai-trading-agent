"""
execution/logger.py - Structured JSON logging for the Execution Agent.

Logs:
- Signals received
- Decisions received
- Orders placed
- Execution results
- Errors
- PnL updates
- Circuit breaker events

All logs are timestamped, non-sensitive, and exportable.
"""

import json
import os
import datetime
from threading import Lock


class ExecutionLogger:
    """Thread-safe JSON logger for the Execution Agent."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"execution_{timestamp}.log")

        self._lock = Lock()

        # Write header
        self._write({
            "_type": "SESSION_START",
            "timestamp": self._ts(),
        })

    def _ts(self) -> str:
        return datetime.datetime.now().isoformat()

    def _write(self, entry: dict):
        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")

    def signal_received(self, signal: dict):
        self._write({"_type": "SIGNAL", "timestamp": self._ts(), "data": signal})

    def decision_received(self, decision: dict):
        self._write({"_type": "DECISION", "timestamp": self._ts(), "data": decision})

    def order_placed(self, order: dict):
        self._write({"_type": "ORDER", "timestamp": self._ts(), "data": order})

    def order_result(self, order_id: str, result: dict):
        self._write({"_type": "ORDER_RESULT", "timestamp": self._ts(),
                     "order_id": order_id, "result": result})

    def pnl_update(self, realized: float, unrealized: float, balance: float):
        self._write({"_type": "PNL", "timestamp": self._ts(),
                     "realized": round(realized, 4),
                     "unrealized": round(unrealized, 4),
                     "balance": round(balance, 4)})

    def error(self, error: str, context: dict = None):
        self._write({"_type": "ERROR", "timestamp": self._ts(),
                     "error": str(error), "context": context or {}})

    def circuit_breaker(self, reason: str, state: str):
        self._write({"_type": "CIRCUIT_BREAKER", "timestamp": self._ts(),
                     "reason": reason, "state": state})

    def state_snapshot(self, state: dict):
        self._write({"_type": "STATE_SNAPSHOT", "timestamp": self._ts(),
                     "data": state})

    def info(self, msg: str, context: dict = None):
        self._write({"_type": "INFO", "timestamp": self._ts(),
                     "msg": msg, "context": context or {}})
