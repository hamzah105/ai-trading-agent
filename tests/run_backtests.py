"""run_backtests.py -- Run backtests across risk levels and print results."""
import sys, os, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import StrategyConfig
from backtest import backtest
import numpy as np

def generate_mock_prices(n=200):
    return np.cumsum(np.random.randn(n)) + 100

print("=== Backtest Matrix ===")
print(f"{'R=':<4} {'Mode':<8} | {'Return':>8} | {'Drawdown':>8} | {'Win%':>5} | {'Trades':>6}")
print("-" * 60)

np.random.seed(42)
prices = generate_mock_prices(200)

for r in [0.2, 0.5, 0.8]:
    for m in ["linear", "logistic"]:
        cfg = StrategyConfig(risk=r, risk_mode=m)
        res = backtest(prices, cfg)
        print(f"R={r}   {m:8s} | {res['total_return_pct']:+7.2f}% | {res['max_drawdown_pct']:7.2f}% | {res['win_rate_pct']:4.1f}% | {res['total_trades']:6d}")

print("-" * 60)
print("[PAPER TRADING ONLY]")
