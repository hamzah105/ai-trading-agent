"""
live_demo_paper.py v2 - Interactive Paper Trading Demo (Kraken Hackathon)

Showcases Roles 1-3 (Strategy -> Execution -> Signals) with fixes:
- Momentum filter: no longs when mom < 0 + high confidence
- Adaptive stop-loss (volatility-scaled)
- Cooldown after losses (3 + losses * 2 steps)
- Transitional regime = 50% position reduction
- Circuit breaker + manual reset
"""

import sys, os, time, numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from config import StrategyConfig
from strategy_math import decide
from execution.config import ExecutionConfig, ExecutionMode
from execution.executor import ExecutionEngine
from execution.logger import ExecutionLogger
from signals.pipeline import SignalPipeline

# ── Terminal Colors ─────────────────────────────────────────────
class C:
    R, G, Y, B, Cc, W = "\033[91m", "\033[92m", "\033[93m", "\033[94m", "\033[96m", "\033[97m"
    DIM, BOLD = "\033[2m", "\033[1m"
    RST = "\033[0m"
    BG_R, BG_G, BG_Y = "\033[97;41m", "\033[97;42m", "\033[97;43m"
    BG_RB = "\033[97;101m"

def badge(a):
    if a == "buy":   return f"{C.BG_G} BUY "
    if a == "sell":  return f"{C.BG_R} SELL"
    return           f"{C.BG_Y} HOLD"

# ── Data Generation ─────────────────────────────────────────────
def gen_prices(n=200, seed=None):
    """Bull -> Plateau -> Crash -> Recovery -> Chop (NON-deterministic)"""
    if seed is not None:
        np.random.seed(seed)
    else:
        np.random.seed()  # true randomness

    p = []
    for frac, start_mul, end_mul, vol in [
        (0.30, 100, 170, 2),
        (0.20, None, None, 4),
        (0.10, -1, 0.70, 2),
        (0.25, None, 1.30, 3),
        (0.15, None, None, 1.5),
    ]:
        ln = max(1, int(n * frac))
        s = p[-1] if p else start_mul

        if start_mul == -1:
            e = s * end_mul
        elif end_mul is not None and start_mul is None:
            e = s * end_mul
        else:
            e = end_mul if end_mul else s

        noise = np.random.randn(ln) * vol * np.random.uniform(0.8, 1.3)
        arr = np.linspace(s, e, ln) + noise

        p.extend(arr.tolist())

    return np.array(p[:n])

def gen_shock_prices(n=200, seed=None):
    """Dynamic crash simulation (non-deterministic)"""
    p = gen_prices(n, seed)

    crash_idx = int(len(p) * np.random.uniform(0.35, 0.5))
    crash_strength = np.random.uniform(0.10, 0.25)

    spike = np.zeros(min(8, len(p) - crash_idx))
    spike[0] = -p[crash_idx] * crash_strength

    p[crash_idx:crash_idx + len(spike)] += spike[:len(p) - crash_idx]

    # Recovery randomness
    for j in range(crash_idx + 5, min(crash_idx + 20, len(p))):
        p[j] = p[j - 1] + np.random.randn() * 2.5

    return p

# ── Dashboard ───────────────────────────────────────────────────
chart = []
def print_dashboard(step, price, action, size, mtm, pnl, dd, mom, conf, regime, alerts):
    pnl_c = C.G if pnl >= 0 else C.R
    sign = "+" if pnl >= 0 else ""
    chart.append(price)
    bar = ""
    if len(chart) > 20:
        recent = chart[-60:]
        mn, mx = min(recent), max(recent)
        rng = mx - mn if mx > mn else 1
        for x in recent:
            pos = int((x - mn) / max(rng, 1e-9) * 3)
            bar += ["_", "-", "=", "#"][min(pos, 3)]

    print(f"  {C.DIM}S{step:>3d}{C.RST} | ${price:>9,.2f} | {badge(action)} | "
          f"size:{size:.4f} | {pnl_c}{sign}${pnl:>8,.2f} | DD:{dd:.1f}% | "
          f"mom:{mom} conf:{conf:.2f} regime:{regime}")
    if bar:
        print(f"  {C.DIM}{bar}{C.RST}")
    for a in alerts:
        print(f"  {C.BG_RB} {a:^70} {C.RST}")

def print_summary(start, end, trades, safety, losses, events):
    pct = (end - start) / start * 100
    clr = C.G if pct >= 0 else C.R
    print(f"\n  {C.BOLD}{C.Cc}")
    print("  " + "="*50)
    print("  DEMO COMPLETE")
    print("  " + "="*50)
    print(f"  Start:      ${start:>10,.2f}")
    print(f"  End:        ${end:>10,.2f}")
    print(f"  Return:     {clr}{pct:>+10.2f}%{C.RST}")
    print(f"  Trades:     {losses:>10d}")
    print(f"  Safety:     {events:>10d}")
    print(f"  Consec Losses (max): {trades:>2d}")
    print(f"  Final PnL:  ${end - start:>+8,.2f}")
    print(f"\n  {C.DIM}PAPER MODE • No real funds{C.RST}\n")

# ── Main ────────────────────────────────────────────────────────
def main():
    risk = float(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].replace(".","").replace("-","").isdigit() else 0.5
    risk = max(0.0, min(1.0, risk))

    print(f"\n  {C.BOLD}{C.Cc}")
    print("  QUANT ARCHITECT DEMO v2 (paper, R={:.2f})".format(risk))
    print("  Momentum Filter | Adaptive Stops | Cooldown | Regime Filter")
    print(f"  {C.RST}")

    if not os.environ.get("DEMO_NO_WAIT"):
        input(f"  {C.Y}Press Enter to start...{C.RST}")

    strat_cfg = StrategyConfig(risk=risk, risk_mode="logistic")
    exec_cfg = ExecutionConfig(mode=ExecutionMode.PAPER, initial_balance=10000.0)
    log = ExecutionLogger(log_dir=os.path.join(os.path.dirname(__file__), "demo_logs"))
    engine = ExecutionEngine(exec_cfg, log)
    pipeline = SignalPipeline()

    seed_env = os.environ.get("DEMO_SEED")
    seed = int(seed_env) if seed_env and seed_env.isdigit() else None

    prices = gen_shock_prices(200, seed)
    prev_action = "hold"
    max_consec = 0
    safety_events = 0
    mtm = 10000.0
    pos = 0.0
    entry_px = 0.0
    peak_bal = 10000.0
    trades = 0

    look = max(60, strat_cfg.macd_slow + strat_cfg.macd_signal + 5)
    step = 0

    for i in range(look, len(prices)):
        step += 1
        price = float(prices[i])
        window = prices[:i+1]
        vol = float(np.std(np.diff(window) / window[:-1]) * 100)

        # Signal Pipeline
        sig = pipeline.process(window)
        mom_dir = sig["momentum"]["signal"]
        conf = sig["fused"]["confidence"]
        regime = sig.get("regime", {}).get("type", "?")

        # Strategy + Execution
        dd = (mtm - peak_bal) / peak_bal * 100 if peak_bal > 0 else 0
        dec = decide(window, volatility=vol, drawdown=dd, prev_action=prev_action, cfg=strat_cfg)
        d = dec.to_dict()
        action = d["decision"]["action"]
        size = d["decision"]["position_size"]

        alerts = []

        # Stress test injection notice
        if step == 40:
            alerts.append("STRESS TEST: Sharp crash zone — monitoring risk controls")
            safety_events += 1

        result = engine.execute_order(d, price, volatility=vol, regime=regime)

        # Track engine state
        state = engine.get_state()
        if engine.circuit_broken and prev_action != "circuit":
            alerts.append("CIRCUIT BREAKER: Trading halted")
            safety_events += 1
        if result["status"] == "COOLDOWN":
            alerts.append(f"COOLDOWN: {engine.cooldown_remaining} steps remaining")

        # Simulate position state
        if result.get("status") == "EXECUTED":
            o = result["order"]
            side = o["side"].lower()
            fill_px = o.get("fill_price", o.get("price", price))
            val = o.get("value", 0)
            fee = o.get("fee", o.get("est_fee", 0))

            if side == "buy" and pos == 0:
                entry_px = fill_px
                units = o["units"]
                pos = units
                mtm -= val + fee
                peak_bal = max(peak_bal, mtm)
                prev_action = "buy"
                trades += 1
                alerts.append(f"LONG @ ${fill_px:,.2f}")

            elif side == "sell" and pos > 0:
                revenue = pos * fill_px - fee
                pnl = revenue - (pos * entry_px)
                mtm += revenue
                if pnl < 0:
                    alerts.append(f"STOP @ ${fill_px:,.2f} | ${pnl:,.2f}")
                    safety_events += 1
                else:
                    alerts.append(f"PROFIT @ ${fill_px:,.2f} | ${pnl:,.2f}")
                pos = 0; entry_px = 0; prev_action = "sell"; trades += 1

        # Mark-to-market
        mtm_with_pos = (mtm + pos * price) if pos > 0 else mtm
        peak_bal = max(peak_bal, mtm_with_pos)
        daily_pnl = mtm_with_pos - 10000.0

        max_consec = max(max_consec, engine.consecutive_losses)

        # Drawdown calc
        dd = (mtm_with_pos - peak_bal) / peak_bal * 100 if peak_bal > 0 else 0

        # Dashboard render (every step, with slight delay for demo)
        print_dashboard(step, price, action, size, mtm_with_pos,
                        daily_pnl, dd, mom_dir, conf, regime, alerts)

        # Manual circuit breaker reset every 10 steps
        if engine.circuit_broken and step % 10 == 0:
            engine.reset_circuit_breaker()
            prev_action = "hold"
            alerts.append("Circuit breaker RESET — resuming")

        if not os.environ.get("DEMO_FAST"):
            time.sleep(0.05)
        prev_action = "hold" if result.get("status") in ("HOLD", "COOLDOWN", "REJECTED") else prev_action

    # Force close
    if pos > 0:
        mtm += pos * price * 0.998
        trades += 1

    print_summary(10000.0, mtm, trades, max_consec, safety_events, engine.total_trades)

if __name__ == "__main__":
    main()
