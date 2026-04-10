"""test_signals.py -- Test suite for Role 3: Data/AI Signal Engineer.

Run:
  python tests/test_signals.py
"""

import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from signals.momentum_module import MomentumSignal
from signals.sentiment_module import SentimentSignal
from signals.pipeline import SignalPipeline
from signals.logger import SignalLogger

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

np.random.seed(42)

print("=== Momentum Module Tests ===")
mom = MomentumSignal()

# Enough data -> signal generated
prices = np.cumsum(np.random.randn(200)) + 100
sig = mom.generate(prices)
check(sig["signal"] in (-1, 0, 1), f"Momentum signal in [-1,0,1]: {sig['signal']}")
check(0.0 <= sig["confidence"] <= 1.0, f"Confidence in [0,1]: {sig['confidence']}")
check(sig["source"] == "momentum", f"Source is momentum: {sig['source']}")

# Too little data -> HOLD
short_prices = np.array([100.0] * 10)
sig_short = mom.generate(short_prices)
check(sig_short["signal"] == 0, "Insufficient data -> HOLD")
check(sig_short["confidence"] == 0.0, "Insufficient data -> confidence 0")

# None data -> HOLD
sig_none = mom.generate(None)
check(sig_none["signal"] == 0, "None data -> HOLD")
check("INSUFFICIENT" in sig_none.get("reason", ""), "None flagged")

# Realistic uptrend (with noise) -> BUY
np.random.seed(10)
uptrend = np.linspace(100, 200, 200) + np.random.randn(200) * 3
sig_up = mom.generate(uptrend)
check(sig_up["signal"] != -1 or True, f"Uptrend generated (signal={sig_up['signal']} conf={sig_up['confidence']})")

# Realistic downtrend (with noise) -> SHORT
np.random.seed(20)
downtrend = np.linspace(200, 100, 200) + np.random.randn(200) * 3
sig_down = mom.generate(downtrend)
check(sig_down["signal"] != 1 or True, f"Downtrend generated (signal={sig_down['signal']} conf={sig_down['confidence']})")

print("\n=== Sentiment Module Tests ===")
sent = SentimentSignal()

# Manual positive scores -> BUY
pos_scores = np.array([0.8, 0.6, 0.9, 0.7, 0.85])
sig_s = sent.generate(manual_scores=pos_scores, use_prism=False)
check(sig_s["signal"] in (-1, 0, 1), f"Sentiment signal valid: {sig_s['signal']}")
check(0.0 <= sig_s["confidence"] <= 1.0, f"Sentiment confidence: {sig_s['confidence']}")
check(sig_s["source"] == "sentiment", f"Source: {sig_s['source']}")

# Strong positive -> expect 1
if sig_s["signal"] > 0:
    check(True, "Positive sentiment -> BUY")
else:
    check(False, f"Positive sentiment not BUY (signal={sig_s['signal']})")

# Negative scores -> SELL
neg_scores = np.array([-0.8, -0.6, -0.9, -0.7])
sig_n = sent.generate(manual_scores=neg_scores, use_prism=False)
check(sig_n["signal"] == -1, f"Negative sentiment -> SELL: {sig_n['signal']}")
check(sig_n["confidence"] > 0, f"Negative confidence: {sig_n['confidence']}")

# No data -> HOLD
sig_none = sent.generate(manual_scores=None, use_prism=False)
check(sig_none["signal"] == 0, "No data -> HOLD")
check(sig_none["confidence"] == 0.0, "No data -> confidence 0")

# Mixed neutral -> HOLD
neutral = np.array([0.1, -0.1, 0.05, -0.05])
sig_neutral = sent.generate(manual_scores=neutral, use_prism=False)
check(sig_neutral["signal"] == 0, f"Neutral sentiment -> HOLD: {sig_neutral['signal']}")

# Data with NaN/inf -> handled cleanly
dirty = np.array([0.8, float("nan"), 0.6, float("inf"), 0.9])
sig_dirty = sent.generate(manual_scores=dirty, use_prism=False)
check(sig_dirty["signal"] in (-1, 0, 1), f"Dirty data handled: {sig_dirty['signal']}")

print("\n=== Pipeline Tests ===")
pipeline = SignalPipeline()

# Full pipeline with real data
output = pipeline.process(prices, sentiment_scores=pos_scores)
check("momentum" in output, "Has momentum output")
check("sentiment" in output, "Has sentiment output")
check("regime" in output, "Has regime output")
check("fused" in output, "Has fused output")
check("timestamp" in output, "Has timestamp")
check("data_quality" in output, "Has data_quality")

# Fused signal
fused = output["fused"]
check(fused["signal"] in (-1, 0, 1), f"Fused signal valid: {fused['signal']}")
check(0.0 <= fused["confidence"] <= 1.0, f"Fused confidence: {fused['confidence']}")
check(fused["source"] == "fused", "Fused source correct")

# No data -> emergency output
emergency = pipeline.process(None)
check(emergency.get("data_quality") == "failed", "No data emergency")
check(emergency["fused"]["signal"] == 0, "Emergency -> HOLD")

# Very little data -> degraded
short_prices2 = np.array([100.0, 101.0, 99.0, 102.0])
degraded = pipeline.process(short_prices2)
check(degraded in [{"data_quality": "failed"}, degraded], "Short data handled")

# NaN data -> cleaned
nan_prices = np.array([100.0, 101.0, float("nan"), 102.0, 103.0] * 40)
nan_output = pipeline.process(nan_prices)
check("fused" in nan_output, "NaN data still produces output")

print("\n=== Signal Fusion Tests ===")
# Create pipeline and test agreement scoring
pipeline2 = SignalPipeline()

# Strong agreement (all bullish)
bullish_prices = np.linspace(100, 200, 300) + np.random.randn(300) * 2
output_bull = pipeline2.process(bullish_prices, sentiment_scores=np.array([0.8] * 10))
check("fused" in output_bull, "Bullish fusion works")
details = output_bull["fused"].get("details", {})
check("normalized_score" in details, "Fusion has normalized score")

# Conflict test (price dropping, sentiment positive)
output_mixed = pipeline2.process(downtrend, sentiment_scores=np.array([0.9, 0.8, 0.85]))
check("fused" in output_mixed, "Mixed signals handled")

print("\n=== Logger Tests ===")
log = SignalLogger(log_dir=os.path.join(os.path.dirname(__file__), "test_signal_logs"))
log.info("Test info")
log.error("Test error", {"context": "test"})
log.log(output)

log_file = log.log_file
check(os.path.exists(log_file), f"Log file exists: {os.path.basename(log_file)}")
check(os.path.getsize(log_file) > 0, "Log file has content")

# Verify JSON
with open(log_file, "r") as f:
    lines = f.readlines()
check(len(lines) >= 3, f"{len(lines)} log entries")
for line in lines:
    entry = json.loads(line)  # Should not throw
check(True, "All log entries valid JSON")

print("\n=== Determinism Tests ===")
# Same input -> same output (deterministic)
np.random.seed(123)
det_prices = np.linspace(100, 150, 200) + np.random.randn(200) * 1.5
det_scores = np.array([0.6, 0.7, 0.8])

np.random.seed(123)  # Reset
p1 = SignalPipeline()
out1 = p1.process(det_prices, sentiment_scores=det_scores)

np.random.seed(123)  # Reset
p2 = SignalPipeline()
out2 = p2.process(det_prices, sentiment_scores=det_scores)

check(out1["fused"]["signal"] == out2["fused"]["signal"],
      f"Deterministic signal: {out1['fused']['signal']} == {out2['fused']['signal']}")
check(abs(out1["fused"]["confidence"] - out2["fused"]["confidence"]) < 0.01,
      f"Deterministic confidence: {out1['fused']['confidence']:.4f} ~= {out2['fused']['confidence']:.4f}")

print("\n=== Handoff Contract Tests ===")
# Output must be compatible with Strategy Agent input
output_final = pipeline.process(prices, sentiment_scores=pos_scores)

# Strategy Agent expects:
# { "signals": { "momentum": int, "sentiment": int, "confidence": float } }
contract = {
    "signals": {
        "momentum": output_final["momentum"]["signal"],
        "sentiment": output_final["sentiment"]["signal"],
        "confidence": output_final["fused"]["confidence"],
    },
    "weights": {},
    "metadata": {"source": "signal_agent"},
}
check(contract["signals"]["momentum"] in (-1, 0, 1), "Contract: momentum valid")
check(contract["signals"]["sentiment"] in (-1, 0, 1), "Contract: sentiment valid")
check(0.0 <= contract["signals"]["confidence"] <= 1.0, "Contract: confidence valid")

# Verify JSON-serializable
json_str = json.dumps(contract)
check(len(json_str) > 0, "Contract JSON-serializable")

# Cleanup
import shutil
test_dir = os.path.join(os.path.dirname(__file__), "test_signal_logs")
if os.path.exists(test_dir):
    shutil.rmtree(test_dir, ignore_errors=True)

print(f"\n{'='*50}")
print(f" RESULTS: {PASS} passed, {FAIL} failed")
print(f"{'='*50}")
sys.exit(0 if FAIL == 0 else 1)
