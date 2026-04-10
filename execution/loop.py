"""
execution/loop.py - Automation loop for the Execution Agent.

Polls for decisions, validates, executes, logs, and repeats.
Runs safely under all failure conditions.
"""

import sys
import os
import time
import json
import signal as sig
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from execution.config import ExecutionConfig, ExecutionMode
from execution.logger import ExecutionLogger
from execution.executor import ExecutionEngine
from data_feed import fetch_ohlcv_kraken, get_prices


class AgentLoop:
    """
    Main automation loop. Polls -> Validates -> Executes -> Logs -> Sleeps.
    """

    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.log = ExecutionLogger(
            log_dir=os.path.join(os.path.dirname(__file__), "logs")
        )
        self.engine = ExecutionEngine(config, self.log)
        self.running = True

        # Register signal handlers for graceful shutdown
        sig.signal(sig.SIGINT, self._handle_signal)
        sig.signal(sig.SIGTERM, self._handle_signal)

        self.log.info("Execution Agent loop initialized", {
            "mode": config.mode.value,
            "pair": config.pair,
            "poll_interval": config.poll_interval_seconds,
        })

    def _handle_signal(self, signum, frame):
        self.log.info("Shutdown signal received")
        self.running = False

    def run(self):
        """Main run loop — runs until stopped."""
        self.log.info("Execution Agent loop started")
        print(f"[EXEC] Mode={self.config.mode.value} | Pair={self.config.pair} | Poll={self.config.poll_interval_seconds}s")
        print(f"[EXEC] Press Ctrl+C to stop.\n")

        while self.running:
            try:
                self._iteration()
            except KeyboardInterrupt:
                self.log.info("KeyboardInterrupt — shutting down")
                self.running = False
            except Exception as e:
                self.log.error(f"Unexpected error in loop: {str(e)}")
                time.sleep(self.config.poll_interval_seconds)

        self._shutdown()

    def _iteration(self):
        """Single poll->execute cycle."""
        # Circuit breaker check
        if self.engine.circuit_broken:
            self.log.circuit_breaker("Circuit breaker active — skipping", "HALTED")
            time.sleep(self.config.poll_interval_seconds * 2)
            return

        # Fetch live price
        try:
            data = fetch_ohlcv_kraken(
                self.config.pair,
                interval=240,
                limit=100,
                use_cache=True,
            )
            if not data:
                self.log.error("Failed to fetch price data — defaulting to HOLD")
                time.sleep(self.config.poll_interval_seconds)
                return

            current_price = float(data["close"][-1])
            prices = data["close"]

        except Exception as e:
            self.log.error(f"Price fetch failed: {str(e)}")
            time.sleep(self.config.poll_interval_seconds)
            return

        # Run strategy engine for this price
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from config import StrategyConfig
            from strategy_math import decide

            strat_cfg = StrategyConfig(
                risk=0.5,
                risk_mode="logistic",
            )
            decision = decide(
                prices=prices,
                volatility=None,
                prev_action="hold",
                cfg=strat_cfg,
            )
            decision_dict = decision.to_dict()

        except Exception as e:
            self.log.error(f"Strategy engine failed: {str(e)}")
            time.sleep(self.config.poll_interval_seconds)
            return

        # Execute
        result = self.engine.execute_order(decision_dict, current_price)

        # Print summary
        action = decision_dict["decision"]["action"]
        status = result["status"]
        self.log.info(
            f"{status}: {action.upper()} @ ${current_price:,.2f}",
            {
                "position_size": decision_dict["decision"]["position_size"],
                "confidence": decision_dict.get("metadata", {}).get("confidence", 0),
                "regime": decision_dict.get("metadata", {}).get("regime", "unknown"),
            },
        )

        # State snapshot every 5 iterations
        state = self.engine.get_state()
        self.log.state_snapshot(state)

        time.sleep(self.config.poll_interval_seconds)

    def _shutdown(self):
        """Clean shutdown."""
        state = self.engine.get_state()
        self.log.state_snapshot(state)
        self.log.info("Execution Agent loop stopped", state)
        print(f"\n[EXEC] Shutting down. Final state: {json.dumps(state, indent=2)}")


if __name__ == "__main__":
    config = ExecutionConfig(
        mode=ExecutionMode.DRY_RUN,
        pair="BTC/USD",
        poll_interval_seconds=30,
    )
    loop = AgentLoop(config)
    loop.run()
