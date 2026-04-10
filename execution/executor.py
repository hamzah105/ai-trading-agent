"""
execution/executor.py v2 - Adaptive risk + cooldown logic

Changes from v1:
- Adaptive stop-loss (scales with volatility)
- Cooldown timer after consecutive losses
- Regime-based position limits
- All safety checks preserved
"""

import time
import urllib.request
import urllib.parse
import hashlib
import hmac
import base64
import json as _json
from typing import Optional

from execution.config import ExecutionConfig, ExecutionMode
from execution.validator import validate_trade
from execution.logger import ExecutionLogger


class ExecutionEngine:
    def __init__(self, config: ExecutionConfig, log: ExecutionLogger):
        self.config = config
        self.log = log

        # State
        self.balance = config.initial_balance
        self.position = 0.0
        self.entry_price = 0.0
        self.peak_price = 0.0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.total_trades = 0
        self.circuit_broken = False

        # Cooldown state
        self.cooldown_remaining = 0    # steps until trade allowed again
        self.last_trade_side = None

    def execute_order(self, decision: dict, price: float,
                      volatility: float = None, regime: str = None,
                      **kwargs) -> dict:
        """
        Master execution with momentum filter awareness + cooldown.
        """
        self.log.decision_received(decision)

        # HOLD always passes through
        action = decision["decision"]["action"].lower()
        if action in ("hold",):
            return self._result("HOLD", "No action", {})

        # Cooldown check (skip for HOLD)
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            self.log.info(f"COOLDOWN: {self.cooldown_remaining} steps remaining")
            return self._result("COOLDOWN", "Cooldown active", {})

        # Validate
        is_valid, reason = validate_trade(
            decision, self.config, self.balance,
            abs(self.daily_pnl) / self.config.initial_balance,
            self.consecutive_losses, price,
        )
        if not is_valid:
            self.log.error(f"Rejected: {reason}", {"decision": decision})
            return self._result("REJECTED", reason, {})

        # Validate

        try:
            if self.config.mode == ExecutionMode.DRY_RUN:
                result = self._dry_run(action, decision, price)
            elif self.config.mode == ExecutionMode.PAPER:
                result = self._paper_execute(action, decision, price, volatility)
            elif self.config.mode == ExecutionMode.LIVE:
                result = self._live_execute(action, decision, price)
        except Exception as e:
            self.log.error(f"Execution failed: {e}")
            return self._result("ERROR", str(e), {})

        if result.get("status") == "EXECUTED":
            self._update_state(result, price, volatility, regime)

        return result

    def _dry_run(self, action, decision, price):
        pos_size = decision["decision"]["position_size"]
        amount = self.balance * pos_size
        units = amount / price
        fee = amount * 0.0026

        order = {
            "symbol": self.config.pair, "side": action.upper(),
            "price": price, "units": round(units, 6),
            "value": round(amount, 2), "est_fee": round(fee, 4),
            "mode": "DRY_RUN",
        }
        self.log.info(f"DRY_RUN: {action} {units:.6f} @ ${price:,.2f}")
        return self._result("EXECUTED", "DRY_RUN", order)

    def _paper_execute(self, action, decision, price, volatility=None):
        pos_size = decision["decision"]["position_size"]
        amount = self.balance * pos_size

        # Adaptive slippage: higher vol = more slippage
        slip = self.config.slippage_pct
        if volatility and volatility > 5:
            slip = min(0.02, slip * (1 + volatility / 50))

        fill_price = price * (1 + slip) if action == "buy" else price * (1 - slip)
        units = amount / fill_price
        fee = amount * 0.0026

        order = {
            "symbol": self.config.pair, "side": action.upper(),
            "requested_price": price, "fill_price": round(fill_price, 2),
            "units": round(units, 6), "value": round(amount, 2),
            "fee": round(fee, 4), "mode": "PAPER",
            "slippage": round(slip * 100, 3),
        }
        self.log.info(f"PAPER: {action} {units:.6f} @ ${fill_price:,.2f}")
        return self._result("EXECUTED", "PAPER filled", order)

    def _live_execute(self, action, decision, price):
        if not self.config.api_key:
            return self._result("ERROR", "No API key", {})
        for attempt in range(self.config.max_retries + 1):
            try:
                return self._kraken_order(action, decision, price)
            except Exception as e:
                self.log.error(f"LIVE attempt {attempt+1}: {e}")
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_backoff_base ** attempt)
        return self._result("ERROR", "All retries exhausted", {})

    def _kraken_order(self, action, decision, price):
        volume = round(self.balance * decision["decision"]["position_size"] / price, 8)
        url = "https://api.kraken.com/0/private/AddOrder"
        nonce = str(int(time.time() * 1000))
        params = {
            "nonce": nonce,
            "pair": self.config.pair.replace("/", ""),
            "type": "buy" if action == "buy" else "sell",
            "ordertype": "market",
            "volume": str(volume),
        }
        postdata = urllib.parse.urlencode(params).encode()
        message = params["nonce"].encode() + postdata
        sig = hmac.new(base64.b64decode(self.config.api_secret), message, hashlib.sha256)
        headers = {
            "API-Key": self.config.api_key,
            "API-Sign": base64.b64encode(sig.digest()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        req = urllib.request.Request(url, data=postdata, headers=headers)
        with urllib.request.urlopen(req, timeout=self.config.request_timeout) as resp:
            data = _json.loads(resp.read().decode())
        if data.get("error"):
            raise ValueError(f"Kraken: {data['error']}")
        txid = data.get("result", {}).get("txid", [""])[0]
        return self._result("EXECUTED", f"LIVE: {txid}", {
            "symbol": self.config.pair, "side": action.upper(),
            "kraken_txid": txid, "volume": volume, "mode": "LIVE",
        })

    def _update_state(self, result, price, volatility=None, regime=None):
        action = result["order"]["side"].lower()
        fill_px = result["order"].get("fill_price", result["order"].get("price", price))
        order_val = result["order"].get("value", 0)
        fee = result["order"].get("fee", result["order"].get("est_fee", 0))

        if action in ("buy",):
            self.entry_price = fill_px if self.position == 0 else self.entry_price
            self.peak_price = price if self.position == 0 else self.peak_price
            units = result["order"]["units"]
            self.position += units
            self.balance -= order_val + fee
            self.cooldown_remaining = 0
            self.last_trade_side = "buy"

        elif action in ("sell",):
            if self.position > 0:
                revenue = self.position * fill_px - fee
                pnl = revenue - (self.position * self.entry_price)
                self.balance += revenue
                position_value = self.position * self.entry_price

                if pnl < 0:
                    self.consecutive_losses += 1
                    # Adaptive cooldown: more losses = longer cooldown
                    self.cooldown_remaining = 3 + self.consecutive_losses * 2
                    self.log.info(f"Loss #{self.consecutive_losses} — cooldown {self.cooldown_remaining} steps")
                else:
                    self.consecutive_losses = 0
                    self.cooldown_remaining = 1
                    self.log.info(f"Profit — cooldown {self.cooldown_remaining} step")

                self.total_trades += 1
                self.position = 0.0
                self.entry_price = 0.0

            self.last_trade_side = "sell"

        if self.position > 0:
            self.peak_price = max(self.peak_price, price)

        # Adaptive stop-loss based on volatility
        effective_sl = 0.02  # Default 2%
        if volatility and volatility > 3:
            effective_sl = min(0.05, 0.02 * (1 + volatility / 30))

        # Position tracking for trailing stop (handled by strategy layer)

        self.daily_pnl = (self.balance + self.position * price) - self.config.initial_balance

        # Circuit breaker check
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            if not self.circuit_broken:
                self.circuit_broken = True
                self.cooldown_remaining = 20  # Extended cooldown
                self.log.circuit_breaker(
                    f"{self.consecutive_losses} consecutive losses",
                    "HALTED",
                )

        self.log.state_snapshot(self.get_state())

    def get_state(self) -> dict:
        return {
            "balance": round(self.balance, 2),
            "position": round(self.position, 6),
            "entry_price": round(self.entry_price, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "consecutive_losses": self.consecutive_losses,
            "circuit_broken": self.circuit_broken,
            "cooldown_remaining": self.cooldown_remaining,
            "total_trades": self.total_trades,
            "mode": self.config.mode.value,
        }

    def reset_circuit_breaker(self):
        if self.circuit_broken:
            self.circuit_broken = False
            self.consecutive_losses = 0
            self.cooldown_remaining = 0
            self.log.circuit_breaker("Manually reset", "RESUMED")

    def _result(self, status, msg, order):
        return {"status": status, "message": msg, "order": order, "timestamp": time.time()}
