"""run_demo.py -- Backtest with trended data to show the engine in action."""
import sys, os, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

np.random.seed(42)

from config import StrategyConfig
from strategy_math import decide
from backtest import backtest
import numpy as np

def generate_mock_prices(n=200):
    return np.cumsum(np.random.randn(n)) + 100

# ── Demo 1: Show engine decisions at different R values ──
print("=== Engine Decisions by Risk Level ===")
print(f"{'R':<4} {'Mode':<8} | {'W_mom':>5} {'W_sent':>6} {'W_risk':>6} | {'Score':>6} | {'Action':<5} {'Size':>5}")
print("-" * 70)

prices = np.cumsum(np.random.randn(100)) + 100

for r in [0.0, 0.3, 0.5, 0.7, 1.0]:
    for m in ["linear", "logistic"]:
        cfg = StrategyConfig(risk=r, risk_mode=m)
        result = decide(prices[:50], cfg=cfg)
        w = result.weights
        s = result.decision["position_size"]
        a = result.decision["action"]
        print(f"R={r:.1f}  {m:8s} | {w['momentum']:.3f}  {w['sentiment']:.3f}  {w['risk_manager']:.3f} | {result.metadata['score']:+6.3f} | {a:<5} {s:.4f}")

# ── Demo 2: Trended backtest (synthetic bull + bear) ──
print(f"\n=== Backtest with Trended Data ===")
np.random.seed(42)

up = np.linspace(100, 150, 100) + np.random.randn(100) * 2  # Strong uptrend
down = np.linspace(150, 120, 100) + np.random.randn(100) * 2  # Downtrend
trended = np.concatenate([up, down])

print(f"{'R':<4} {'Mode':<8} | {'Return':>8} | {'Drawdown':>8} | {'Win%':>5} | {'Trades':>6}")
print("-" * 60)

for r in [0.2, 0.5, 0.8]:
    for m in ["linear", "logistic"]:
        cfg = StrategyConfig(risk=r, risk_mode=m)
        res = backtest(trended, cfg)
        print(f"R={r:.1f}  {m:8s} | {res['total_return_pct']:+7.2f}% | {res['max_drawdown_pct']:7.2f}% | {res['win_rate_pct']:4.1f}% | {res['total_trades']:6d}")

print("-" * 60)
print("[PAPER TRADING ONLY]")
