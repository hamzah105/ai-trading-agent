"""quick_demo_test.py - Non-interactive smoke test of live demo pipeline."""
import sys, os, time, numpy as np
sys.path.insert(0, os.path.dirname(__file__))

from config import StrategyConfig
from strategy_math import decide
from execution.config import ExecutionConfig, ExecutionMode
from execution.executor import ExecutionEngine
from execution.logger import ExecutionLogger
from signals.pipeline import SignalPipeline

print("Loading all modules...")

cfg = StrategyConfig(risk=0.5, risk_mode="logistic")
exec_cfg = ExecutionConfig(mode=ExecutionMode.PAPER, initial_balance=10000.0)
log = ExecutionLogger(log_dir="execution/logs")
engine = ExecutionEngine(exec_cfg, log)
pipeline = SignalPipeline()

np.random.seed(42)
prices = np.cumsum(np.random.randn(200)) + 100

print(f"Prices: {len(prices)} candles, range: ${prices.min():.2f} - ${prices.max():.2f}")

window = prices[100:]
decision = decide(window, cfg=cfg)
d = decision.to_dict()
print(f"Decision: action={d['decision']['action']}, size={d['decision']['position_size']:.4f}")

result = engine.execute_order(d, float(prices[-1]))
print(f"Execution: {result['status']}")

sig = pipeline.process(prices)
print(f"Signals: fused={sig['fused']['signal']}, conf={sig['fused']['confidence']:.2f}")

print("\nAll modules loaded and tested OK.")
print("Ready for live demo - run: python live_demo_paper.py")
