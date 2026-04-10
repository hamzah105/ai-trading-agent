"""
backtest_v2.py - Paper trading simulation with costs, exits, and full metrics.

Upgrades from v1:
- Fees + slippage on every trade
- Stop-loss, take-profit, trailing stop
- Full metrics: Sharpe, Max Drawdown, Win Rate, Profit Factor, Calmar
- Equity curve + trade log

Usage:
  python backtest_v2.py --risk 0.5 --mode logistic
  python backtest_v2.py --risk 0.8 --stop-loss 0.03 --take-profit 0.06
"""

import argparse
import json
import os
import numpy as np

from config import StrategyConfig
from strategy_math import decide, check_exits
from signals_schema import TradingAction
from data_feed import fetch_ohlcv_kraken, get_prices

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def generate_mock_prices_v2(n: int = 500, start: float = 100.0) -> np.ndarray:
    """Generate realistic prices: trend + regime shifts + noise."""
    np.random.seed(42)
    prices = [start]
    for i in range(1, n):
        regime = np.random.choice(["bull", "bear", "range"], p=[0.35, 0.25, 0.40])
        if regime == "bull":
            mu, sigma = 0.0015, 0.015
        elif regime == "bear":
            mu, sigma = -0.001, 0.02
        else:
            mu, sigma = 0.0, 0.008
        ret = np.random.normal(mu, sigma)
        prices.append(prices[-1] * (1 + ret))
    return np.array(prices)


def backtest(prices: np.ndarray, cfg: StrategyConfig) -> dict:
    """
    Run paper-trading simulation with costs, exits, and full metrics.
    """
    if len(prices) < 60:
        return {"error": "Insufficient data (need >= 60 candles)"}

    balance = 10000.0
    position = 0.0
    entry_price = 0.0
    peak_price = 0.0
    prev_action = "hold"
    trades = []
    equity_curve = [balance]

    for i in range(50, len(prices)):
        window = prices[:i+1]
        price = prices[i]
        vol = np.std(np.diff(window) / window[:-1]) * 100

        result = decide(window, volatility=vol, prev_action=prev_action, cfg=cfg)

        action_str = result.decision["action"].value
        size = result.decision["position_size"]

        # Check exits on open position
        if position > 0:
            exit_reason = check_exits(price, entry_price, peak_price,
                                       cfg.stop_loss_pct, cfg.take_profit_pct,
                                       cfg.trailing_stop_pct)
            if exit_reason:
                # Close position
                cost = position * price * (cfg.fee_pct + cfg.slippage_pct)
                revenue = position * price - cost
                balance += revenue
                pnl = revenue - (position * entry_price)
                trades.append({
                    "type": "exit", "reason": exit_reason,
                    "entry": round(entry_price, 2), "exit": round(price, 2),
                    "pnl": round(pnl, 2), "balance": round(balance, 2),
                })
                position = 0.0
                entry_price = 0.0
                peak_price = 0.0
                prev_action = "sell"
                equity_curve.append(balance)
                continue

        # Entry logic
        if action_str == "buy" and size > 0 and position == 0:
            invest = balance * size
            cost = invest * (cfg.fee_pct + cfg.slippage_pct)
            entry_price = price * (1 + cfg.slippage_pct)
            position = invest / entry_price
            balance -= invest + cost
            peak_price = price
            prev_action = "buy"
            trades.append({
                "type": "entry", "price": round(entry_price, 2),
                "size": round(size, 4), "balance": round(balance, 2),
                "regime": result.metadata.get("regime", "unknown"),
                "score": result.metadata.get("score", 0),
            })

        # Update peak for trailing stop
        if position > 0:
            peak_price = max(peak_price, price)

        # Mark-to-market
        mtm = balance + position * price
        equity_curve.append(mtm)

    # Force close open position at end
    if position > 0:
        cost = position * prices[-1] * (cfg.fee_pct + cfg.slippage_pct)
        revenue = position * prices[-1] - cost
        balance += revenue
        pnl = revenue - (position * entry_price)
        trades.append({
            "type": "exit", "reason": "end_of_period",
            "entry": round(entry_price, 2), "exit": round(prices[-1], 2),
            "pnl": round(pnl, 2), "balance": round(balance, 2),
        })

    # Metrics
    equity = np.array(equity_curve)
    returns = np.diff(equity) / equity[:-1]
    returns = returns[np.isfinite(returns)]

    total_return = (equity[-1] - 10000.0) / 10000.0
    peak = np.maximum.accumulate(equity)
    drawdowns = (equity - peak) / np.where(peak > 0, peak, 1)
    max_dd = float(np.min(drawdowns))

    win_trades = [t for t in trades if t.get("pnl", 0) > 0 and t["type"] == "exit"]
    loss_trades = [t for t in trades if t.get("pnl", 0) <= 0 and t["type"] == "exit" and "pnl" in t]
    wins = [t["pnl"] for t in win_trades]
    losses = [abs(t["pnl"]) for t in loss_trades if "pnl" in t]
    win_rate = len(win_trades) / (len(win_trades) + len(loss_trades)) if (win_trades or loss_trades) else 0
    profit_factor = sum(wins) / sum(losses) if sum(losses) > 0 else (float("inf") if wins else 0)

    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
    calmar = total_return / abs(max_dd) if max_dd != 0 else 0

    return {
        "risk": cfg.risk,
        "mode": cfg.risk_mode,
        "start_balance": 10000.0,
        "end_balance": round(float(balance), 2),
        "total_return_pct": round(total_return * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "sharpe_ratio": round(float(sharpe), 3),
        "calmar_ratio": round(float(calmar), 3),
        "win_rate_pct": round(win_rate * 100, 1),
        "profit_factor": round(float(profit_factor), 3),
        "total_trades": len([t for t in trades if t["type"] in ("entry", "exit")]),
        "trades": trades[:100],
        "fee_pct": cfg.fee_pct,
        "slippage_pct": cfg.slippage_pct,
        "stop_loss_pct": cfg.stop_loss_pct,
        "take_profit_pct": cfg.take_profit_pct,
        "trailing_stop_pct": cfg.trailing_stop_pct,
        "equity_curve": equity.tolist(),
        "paper_trading": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Quant Agent Backtest v2")
    parser.add_argument("--risk", type=float, default=0.5)
    parser.add_argument("--mode", choices=["linear", "logistic"], default="logistic")
    parser.add_argument("--stop-loss", type=float, default=0.02)
    parser.add_argument("--take-profit", type=float, default=0.04)
    parser.add_argument("--trailing", type=float, default=0.015)
    parser.add_argument("--fee", type=float, default=0.0026)
    parser.add_argument("--source", choices=["mock", "kraken"], default="mock")
    parser.add_argument("--pair", default="BTC/USD")
    args = parser.parse_args()

    cfg = StrategyConfig(
        risk=args.risk,
        risk_mode=args.mode,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        trailing_stop_pct=args.trailing,
        fee_pct=args.fee,
    )

    if args.source == "kraken":
        print(f"Fetching {args.pair} from Kraken...")
        data = fetch_ohlcv_kraken(args.pair, interval=240, limit=500)
        if not data:
            print("Failed to fetch from Kraken, falling back to mock data")
            prices = generate_mock_prices_v2(500)
        else:
            prices = get_prices(data)
            print(f"Got {len(prices)} candles. Latest: ${prices[-1]:,.2f}")
    else:
        prices = generate_mock_prices_v2(500)

    if len(prices) < 60:
        print("ERROR: Not enough data")
        return

    print(f"\n=== Backtest: Risk={cfg.risk}, Mode={cfg.risk_mode}, Stops={cfg.stop_loss_pct}/{cfg.take_profit_pct} ===\n")

    result = backtest(prices, cfg)

    print(f"Start Balance:   ${result['start_balance']:>10,.2f}")
    print(f"End Balance:     ${result['end_balance']:>10,.2f}")
    print(f"Total Return:    {result['total_return_pct']:>+10.2f}%")
    print(f"Max Drawdown:    {result['max_drawdown_pct']:>10.2f}%")
    print(f"Sharpe Ratio:    {result['sharpe_ratio']:>10.3f}")
    print(f"Calmar Ratio:    {result['calmar_ratio']:>10.3f}")
    print(f"Win Rate:        {result['win_rate_pct']:>10.1f}%")
    print(f"Profit Factor:   {result['profit_factor']:>10.3f}")
    print(f"Total Trades:    {result['total_trades']:>10d}")
    print(f"\nFees: {cfg.fee_pct*100:.2f}% | Slippage: {cfg.slippage_pct*100:.2f}%")
    print("[PAPER TRADING ONLY]\n")

    os.makedirs(DATA_DIR, exist_ok=True)
    out = os.path.join(DATA_DIR, f"backtest_v2_R{cfg.risk}_{cfg.risk_mode}.json")
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Results -> {out}")


if __name__ == "__main__":
    main()
