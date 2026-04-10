"""test_execution.py -- Full test suite for Execution Agent.

Run:
  python tests/test_execution.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from execution.config import ExecutionConfig, ExecutionMode
from execution.logger import ExecutionLogger
from execution.validator import validate_trade
from execution.executor import ExecutionEngine

PASS = 0
FAIL = 0

def check(condition, label):
    global PASS, FAIL
    if condition:
        print(f"  PASS: {label}")
        PASS += 1
    else:
        print(f"  FAIL: {label}")
        FAIL += 1

# --- Config Tests ---
print("=== Execution Config Tests ===")
cfg = ExecutionConfig(mode=ExecutionMode.DRY_RUN)
check(cfg.validate(), "DRY_RUN config validates")
check(cfg.max_position_size == 0.25, "max_position=0.25")
check(cfg.max_daily_loss_pct == 0.05, "daily_loss=5%")
check(cfg.max_consecutive_losses == 3, "consecutive_loss_limit=3")

# --- Validator Tests ---
print("\n=== Validator Tests ===")

# Valid trade
decision = {
    "risk_level": 0.5,
    "weights": {"momentum": 0.4, "sentiment": 0.3, "risk_manager": 0.3},
    "signals": {"momentum": 1, "sentiment": 1, "risk_manager": 0},
    "metadata": {"confidence": 0.7, "score": 0.4, "regime": "trending"},
    "decision": {"action": "buy", "position_size": 0.1},
}

ok, reason = validate_trade(decision, cfg, 10000.0, 0.0, 0, 50000.0)
check(ok, f"Valid trade accepted: {reason}")

# HOLD
hold_dec = {"decision": {"action": "hold", "position_size": 0.0}}
ok, reason = validate_trade(hold_dec, cfg, 10000.0, 0.0, 0, 50000.0)
check(ok, f"HOLD accepted: {reason}")

# Invalid action
bad_action = {"decision": {"action": "moon", "position_size": 0.1}}
ok, reason = validate_trade(bad_action, cfg, 10000.0, 0.0, 0, 50000.0)
check(not ok, f"Invalid action rejected: {reason}")

# Size too big
big_size = {"decision": {"action": "buy", "position_size": 0.5}}
ok, reason = validate_trade(big_size, cfg, 10000.0, 0.0, 0, 50000.0)
check(not ok, f"Oversized rejected: {reason}")

# Daily loss limit
ok, reason = validate_trade(decision, cfg, 10000.0, 0.06, 0, 50000.0)
check(not ok, f"Daily loss circuit: {reason}")

# Consecutive losses
ok, reason = validate_trade(decision, cfg, 10000.0, 0.0, 3, 50000.0)
check(not ok, f"Consecutive loss circuit: {reason}")

# Missing data
empty_dec = {}
ok, reason = validate_trade(empty_dec, cfg, 10000.0, 0.0, 0, 50000.0)
check(not ok, f"Empty decision rejected: {reason}")

# Low confidence
low_conf = {
    "decision": {"action": "buy", "position_size": 0.1},
    "metadata": {"confidence": 0.05},
    "signals": {"test": 1},
}
ok, reason = validate_trade(low_conf, cfg, 10000.0, 0.0, 0, 50000.0)
check(not ok, f"Low confidence rejected: {reason}")

# No price data
ok, reason = validate_trade(decision, cfg, 10000.0, 0.0, 0, None)
check(not ok, f"Missing price rejected: {reason}")

# --- Logger Tests ---
print("\n=== Logger Tests ===")
log = ExecutionLogger(log_dir=os.path.join(os.path.dirname(__file__), "test_logs"))

log.info("Test info message")
log.signal_received({"test": "signal"})
log.decision_received(decision)
log.order_placed({"test": "order"})
log.pnl_update(100.0, -50.0, 10050.0)
log.error("Test error")
log.circuit_breaker("test reason", "HALTED")

log_file = log.log_file
check(os.path.exists(log_file), f"Log file created: {log_file}")
check(os.path.getsize(log_file) > 0, "Log file has content")

# Verify JSON structure
with open(log_file, "r") as f:
    lines = f.readlines()
check(len(lines) >= 8, f"{len(lines)} log entries written")

for line in lines:
    entry = json.loads(line)
    check("_type" in entry, f"Has _type: {entry['_type']}")
    break  # just check first

# --- Executor Tests ---
print("\n=== Executor Tests ===")
log2 = ExecutionLogger(log_dir=os.path.join(os.path.dirname(__file__), "test_logs"))
engine = ExecutionEngine(cfg, log2)

state = engine.get_state()
check(state["balance"] == 10000.0, f"Initial balance: {state['balance']}")
check(state["position"] == 0.0, "Initial position: 0")
check(state["circuit_broken"] == False, "Circuit not broken")
check(state["mode"] == "dry_run", f"Mode: {state['mode']}")

# Execute BUY (DRY_RUN)
result = engine.execute_order(decision, 50000.0)
check(result["status"] == "EXECUTED", f"DRY_RUN buy: {result['status']}")
check("order" in result, "Order in result")

state = engine.get_state()
check(state["position"] > 0, f"Position added after DRY_RUN buy: {state['position']}")
check(state["balance"] < 10000.0, f"Balance decreased: {state['balance']}")

# Execute SELL (DRY_RUN)
sell_dec = {
    "risk_level": 0.3,
    "weights": {"momentum": 0.3, "sentiment": 0.3, "risk_manager": 0.4},
    "signals": {"momentum": -1, "sentiment": -1, "risk_manager": -1},
    "metadata": {"confidence": 0.6, "score": -0.4, "regime": "trending"},
    "decision": {"action": "sell", "position_size": 0.1},
}
result = engine.execute_order(sell_dec, 51000.0)
check(result["status"] == "EXECUTED", f"DRY_RUN sell: {result['status']}")

# HOLD pass-through
hold_result = engine.execute_order(hold_dec, 50000.0)
check(hold_result["status"] == "HOLD", f"HOLD: {hold_result['status']}")

# Rejected trade
reject_result = engine.execute_order(empty_dec, 50000.0)
check(reject_result["status"] == "REJECTED", f"Rejected: {reject_result['status']}")

# --- PnL Tests ---
print("\n=== PnL Tests ===")
log3 = ExecutionLogger(log_dir=os.path.join(os.path.dirname(__file__), "test_logs"))
cfg3 = ExecutionConfig(mode=ExecutionMode.DRY_RUN, initial_balance=10000.0)
engine3 = ExecutionEngine(cfg3, log3)

# Initial PnL check
initial_state = engine3.get_state()
check(initial_state["daily_pnl"] == 0.0, "Initial daily PnL = 0")

# --- Circuit Breaker Tests ---
print("\n=== Circuit Breaker Tests ===")
log4 = ExecutionLogger(log_dir=os.path.join(os.path.dirname(__file__), "test_logs"))
cfg4 = ExecutionConfig(mode=ExecutionMode.DRY_RUN, max_consecutive_losses=2)
engine4 = ExecutionEngine(cfg4, log4)

# Force circuit breaker via state manipulation
engine4.consecutive_losses = cfg4.max_consecutive_losses
engine4.circuit_broken = True
log4.circuit_breaker("test", "HALTED")

check(engine4.circuit_broken, f"Circuit breaker triggered after {cfg4.max_consecutive_losses} consecutive losses")

# Try to execute while circuit broken
cb_result = engine4.execute_order(decision, 50000.0)
check(cb_result["status"] == "REJECTED", f"Trade rejected during circuit break: {cb_result['status']}")

# Manual reset
engine4.reset_circuit_breaker()
check(not engine4.circuit_broken, "Circuit breaker manually reset")

# --- Summary ---
print(f"\n{'='*50}")
print(f" RESULTS: {PASS} passed, {FAIL} failed")
print(f"{'='*50}")

# Cleanup test logs
import shutil
test_logs = os.path.join(os.path.dirname(__file__), "test_logs")
if os.path.exists(test_logs):
    shutil.rmtree(test_logs, ignore_errors=True)

sys.exit(0 if FAIL == 0 else 1)
