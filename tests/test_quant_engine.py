"""test_quant_engine.py -- Test suite for Quant Architect Agent v2.

Run:
  python tests/test_quant_engine.py
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import StrategyConfig
from signals_schema import (
    StrategySignal, DecisionOutput,
    SignalDirection, TradingAction,
)
from strategy_math import (
    compute_weights, signal_momentum_v2, signal_sentiment,
    signal_risk_v2, combine_signals, check_signal_conflict,
    compute_position_size, decide, market_regime, adapt_weights,
    confidence_model, hysteresis_decision, check_exits,
)
from indicators import ema, macd, adx, sma, atr

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

print("=== Config Tests ===")
cfg = StrategyConfig(risk=0.5)
check(cfg.risk == 0.5, "risk=0.5")
check(cfg.validate(), "config validates")

cfg_bad = StrategyConfig(risk=1.5)
check(cfg_bad.risk == 1.0, "risk clamped to max 1.0")

cfg_neg = StrategyConfig(risk=-0.3)
check(cfg_neg.risk == 0.0, "risk clamped to min 0.0")

check(cfg.stop_loss_pct > 0, "stop_loss_pct > 0")
check(cfg.take_profit_pct > cfg.stop_loss_pct, "TP > SL")
check(cfg.fee_pct > 0, "fee_pct > 0")
check(cfg.decision_threshold > 0, "decision_threshold > 0")

print("\n=== Indicator Tests ===")
np.random.seed(42)
prices = np.cumsum(np.random.randn(100)) + 100

e = ema(prices, 10)
check(len(e) == len(prices), f"EMA length matches: {len(e)}")

ml, sl, hist = macd(prices)
check(len(ml) == len(prices), f"MACD length: {len(ml)}")

adx_vals = adx(prices, 14)
check(len(adx_vals) > 0, f"ADX computed: {len(adx_vals)} values")

s = sma(prices, 10)
check(len(s) == 91, f"SMA length (valid): {len(s)}")

a = atr(prices, 14)
check(a > 0, f"ATR > 0: {a:.4f}")

print("\n=== Weight Tests ===")
w = compute_weights(StrategyConfig(risk=0.0))
total = sum(w.values())
check(abs(total - 1.0) < 1e-6, f"R=0: sum={total:.6f}")
check(min(w.values()) >= 0, f"R=0: all non-negative [{w['risk_manager']:.3f}]")

w = compute_weights(StrategyConfig(risk=1.0))
total = sum(w.values())
check(abs(total - 1.0) < 1e-6, f"R=1: sum={total:.6f}")
check(w["momentum"] > w["risk_manager"], "R=1: momentum > risk_manager")

w = compute_weights(StrategyConfig(risk=0.5, risk_mode="logistic"))
total = sum(w.values())
check(abs(total - 1.0) < 1e-6, f"R=0.5 logistic: sum={total:.6f}")

w2 = adapt_weights(w.copy(), "trending")
check(abs(sum(w2.values()) - 1.0) < 1e-6, "Adapted weights normalize")
check(w2["momentum"] > w["momentum"], "Trending boosts momentum")

print("\n=== Signal Tests ===")
# Oversold: create a realistic declining series (enough data for MACD)
oversold = np.linspace(100, 60, 80)
sig = signal_momentum_v2(oversold, cfg)
# Deep decline -> RSI should be very low -> LONG signal
check(sig.direction != SignalDirection.SHORT.value,
      f"Oversold not SHORT (dir={sig.direction}, conf={sig.confidence:.2f})")

# Overbought: realistic rising series
overbought = np.linspace(60, 140, 80)
sig = signal_momentum_v2(overbought, cfg)
check(sig.direction != SignalDirection.LONG.value or sig.confidence < 0.5,
      f"Overbought check (dir={sig.direction})")

# Short data -> HOLD (fail-safe)
sig = signal_momentum_v2(np.array([100.0, 101.0]), cfg)
check(sig.direction == SignalDirection.HOLD.value, "Short data -> HOLD")

# Sentiment
sig_s = signal_sentiment(np.array([0.8, 0.6, 0.9]))
check(sig_s.direction == SignalDirection.LONG.value, "Positive sentiment -> LONG")

sig_s2 = signal_sentiment(None)
check(sig_s2.direction == SignalDirection.HOLD.value, "No sentiment data -> HOLD")

sig_rm = signal_risk_v2(prices, volatility=80.0, drawdown=15.0, cfg=cfg)
check(sig_rm.direction == SignalDirection.SHORT.value, "High vol+drawdown -> SHORT")

print("\n=== Decision Engine Tests ===")
result = decide(prices, cfg=StrategyConfig(risk=0.7))
check(isinstance(result, DecisionOutput), "Returns DecisionOutput")
check(result.risk_level == 0.7, "risk_level=0.7")
check(isinstance(result.decision, dict), "decision is dict")
check("confidence" in result.metadata, "confidence in metadata")
check("regime" in result.metadata, "regime in metadata")

d = result.to_dict()
check("confidence" in d["metadata"], "confidence in JSON")
check("regime" in d["metadata"], "regime in JSON")
check("action" in d["decision"], "Has action key")
check("position_size" in d["decision"], "Has position_size")
check("momentum" in d["signals"], "Has momentum signal")

result_empty = decide(None, cfg=StrategyConfig())
check(result_empty.decision["action"] == TradingAction.HOLD, "Missing data -> HOLD")
check(result_empty.decision["position_size"] == 0.0, "Missing data -> zero position")
check(result_empty.metadata.get("reason") == "MISSING_DATA", "Missing data flagged")

print("\n=== Market Regime ===")
long_uptrend = np.linspace(100, 200, 200) + np.random.randn(200) * 2
reg = market_regime(long_uptrend, cfg)
check(reg in ("trending", "ranging", "transitional"), f"Regime returns valid value: '{reg}'")

print("\n=== Conflict Detection ===")
signals_conflict = {
    "a": StrategySignal("a", SignalDirection.LONG.value, 0.9),
    "b": StrategySignal("b", SignalDirection.SHORT.value, 0.9),
}
check(check_signal_conflict(signals_conflict, 0.6), "Conflict detected")

signals_agree = {
    "a": StrategySignal("a", SignalDirection.LONG.value, 0.8),
    "b": StrategySignal("b", SignalDirection.LONG.value, 0.7),
}
check(not check_signal_conflict(signals_agree, 0.6), "No conflict when aligned")

print("\n=== Position Sizing ===")
cfg_test = StrategyConfig(risk=0.5, max_position_pct=0.25)
sz = compute_position_size(0.8, cfg_test, conflict=False)
check(sz <= 0.25, f"Size capped at 25%: {sz:.4f}")

sz_conflict = compute_position_size(0.8, cfg_test, conflict=True)
check(sz_conflict < sz, f"Conflict reduces size: {sz_conflict:.4f} < {sz:.4f}")

print("\n=== Hysteresis ===")
check(hysteresis_decision(0.3, "hold", cfg_test) == "buy", "Strong pos -> buy")
check(hysteresis_decision(-0.3, "hold", cfg_test) == "sell", "Strong neg -> sell")

# Hysteresis: buy -> needs negative score to flip to sell
prev_buy = hysteresis_decision(0.1, "buy", cfg_test)
check(prev_buy in ("buy", "hold"), f"Buy hysteresis holds: {prev_buy}")

# Small score with no prev -> hold (within band)
no_trade = hysteresis_decision(0.01, "hold", cfg_test)
check(no_trade == "hold", f"Within band -> hold: {no_trade}")

print("\n=== Exit Logic ===")
ex = check_exits(98.0, 100.0, 100.0, 0.02, 0.04, 0.015)
check(ex == "stop_loss", f"Stop loss triggered: {ex}")

ex2 = check_exits(104.0, 100.0, 106.0, 0.02, 0.04, 0.015)
# Peak 106, price 104 -> dropped 1.9% from peak -> > 1.5% trailing
# But first check take_profit: (104-100)/100 = 4% = TP threshold
check(ex2 in ("take_profit", "trailing_stop"),
      f"Exit triggered (TP or trailing): {ex2}")

# Flat price, no exit
ex3 = check_exits(100.0, 100.0, 100.0, 0.02, 0.04, 0.015)
check(ex3 is None, f"No exit on flat price: {ex3}")

# No exit within thresholds
ex4 = check_exits(101.0, 100.0, 101.0, 0.02, 0.04, 0.015)
check(ex4 is None, f"No exit for small move: {ex4}")

print("\n=== Confidence Model ===")
conf = confidence_model(
    {"a": StrategySignal("a", 1, 0.8), "b": StrategySignal("b", 1, 0.7)},
    {"a": 0.5, "b": 0.5},
    "trending",
)
check(0.0 <= conf <= 1.0, f"Confidence in [0,1]: {conf:.3f}")

conf2 = confidence_model(
    {"a": StrategySignal("a", 1, 0.3), "b": StrategySignal("b", -1, 0.6)},
    {"a": 0.5, "b": 0.5},
    "ranging",
)
check(conf2 < conf, f"Conflict+ranging < agreement+trending: {conf2:.3f} < {conf:.3f}")

print("\n=== JSON Serialization ===")
result = decide(prices, cfg=StrategyConfig(risk=0.5))
j = result.to_dict()
check(j["risk_level"] == 0.5, "risk_level serialized")
check(0.0 <= j["weights"]["momentum"] <= 1.0, "weight in [0,1]")
check(j["decision"]["action"] in ("buy", "sell", "hold"), "action valid")
check(0.0 <= j["decision"]["position_size"] <= 1.0, "position in [0,1]")

print(f"\n{'='*50}")
print(f" RESULTS: {PASS} passed, {FAIL} failed")
print(f"{'='*50}")
sys.exit(0 if FAIL == 0 else 1)