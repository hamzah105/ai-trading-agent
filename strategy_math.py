"""
strategy_math.py - Core mathematical model (v3: Adaptive Risk + Momentum Filter)

v3 fixes:
- Momentum filter: block long trades if Mom < 0 and confidence high
- Regime-aware execution (transitional = 50% reduction, ranging = 40% reduction)
- Adaptive position sizing (volatility + regime scaling)
- Regime added: "transitional" for flat EMA slope + moderate ADX
- Confidence model includes regime penalty
"""

import math
import numpy as np
from typing import Dict, Optional, Tuple

from config import StrategyConfig
from signals_schema import (
    StrategySignal,
    DecisionOutput,
    SignalDirection,
    TradingAction,
)
from indicators import ema, macd, adx, rsi as rsi_func, atr


# ======================================================================
#  1. WEIGHT FUNCTIONS
# ======================================================================
def _logistic(x, k=6.0, midpoint=0.5):
    return 1.0 / (1.0 + math.exp(-k * (x - midpoint)))


def compute_weights(cfg):
    R = cfg.risk
    if cfg.risk_mode == "logistic":
        raw_m = _logistic(R, k=8.0, midpoint=0.4)
        raw_s = _logistic(R, k=6.0, midpoint=0.6)
        raw_r = 1.0 - _logistic(R, k=6.0, midpoint=0.5)
    else:
        raw_m = 0.5 + 0.5 * R
        raw_s = 0.3 + 0.7 * R
        raw_r = 1.0 - R
    raw_m = max(0.0, raw_m); raw_s = max(0.0, raw_s); raw_r = max(0.0, raw_r)
    total = raw_m + raw_s + raw_r
    if total == 0:
        return {"momentum": 0.3333, "sentiment": 0.3333, "risk_manager": 0.3334}
    return {"momentum": raw_m/total, "sentiment": raw_s/total, "risk_manager": raw_r/total}


# ======================================================================
#  2. REGIME DETECTION (v3 adds transitional)
# ======================================================================
def market_regime(prices, cfg):
    if len(prices) < cfg.ema_trend_period + 1:
        return "ranging"
    adx_vals = adx(prices, cfg.adx_period)
    ema_s = ema(prices, min(cfg.ema_trend_period, len(prices) - 1))
    if len(adx_vals) == 0 or len(ema_s) < 2:
        return "ranging"
    current_adx = float(adx_vals[-1])
    ema_slope = (ema_s[-1] - ema_s[-2]) / max(abs(ema_s[-2]), 1e-9)
    if current_adx > cfg.adx_threshold and abs(ema_slope) > 0.005:
        return "trending"
    # Transitional: moderate ADX, low slope
    if current_adx > 15 and abs(ema_slope) < 0.01:
        # Flat EMA with moderate ADX = transitional/chop
        return "transitional"
    return "ranging"


def adapt_weights(weights, regime):
    if regime == "trending":
        weights["momentum"] *= 1.2; weights["risk_manager"] *= 0.8
    elif regime == "ranging":
        weights["momentum"] *= 0.6; weights["risk_manager"] *= 1.4
    elif regime == "transitional":
        weights["momentum"] *= 0.4; weights["risk_manager"] *= 1.6; weights["sentiment"] *= 0.6
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


# ======================================================================
#  3. SIGNALS
# ======================================================================
def signal_momentum_v2(prices, cfg):
    min_len = cfg.macd_slow + cfg.macd_signal + 1
    if len(prices) < min_len:
        return StrategySignal("momentum", SignalDirection.HOLD.value, 0.0)

    rsi_vals = rsi_func(prices, cfg.rsi_period)
    current_rsi = float(rsi_vals[-1]) if len(rsi_vals) > 0 else 50.0

    if current_rsi < 30:
        rsi_dir = 1; rsi_conf = max(0.2, (30 - current_rsi) / 30)
    elif current_rsi > 70:
        rsi_dir = -1; rsi_conf = max(0.2, (current_rsi - 70) / 30)
    else:
        rsi_dir = 0; rsi_conf = max(0.1, 1.0 - abs(current_rsi - 50) / 30)

    mline, sline, hist = macd(prices, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
    current_hist = float(hist[-1]) if len(hist) > 0 else 0.0
    macd_dir = 1 if current_hist > 0 else (-1 if current_hist < 0 else 0)
    macd_conf = min(1.0, max(0.1, abs(current_hist) / (np.std(hist) + 1e-9)))

    # EMA trend confirmation
    trend_ok = True
    if len(prices) > cfg.ema_trend_period:
        ema_s = ema(prices, min(cfg.ema_trend_period, len(prices) - 1))
        if len(ema_s) > 1:
            slope = (ema_s[-1] - ema_s[-2]) / max(abs(ema_s[-2]), 1e-9)
            if macd_dir == 1 and slope < -0.01:
                trend_ok = False
            if macd_dir == -1 and slope > 0.01:
                trend_ok = False

    combined = 0.4 * rsi_dir + 0.4 * macd_dir + (0.2 if trend_ok else -0.2)
    if combined > 0.25:
        direction = SignalDirection.LONG; conf = min(1.0, abs(combined) + 0.15)
    elif combined < -0.25:
        direction = SignalDirection.SHORT; conf = min(1.0, abs(combined) + 0.15)
    else:
        direction = SignalDirection.HOLD; conf = max(0.05, 1.0 - abs(combined))

    return StrategySignal("momentum", direction.value, conf)


def signal_sentiment(scores=None, **kwargs):
    if scores is None or len(scores) == 0:
        return StrategySignal("sentiment", SignalDirection.HOLD.value, 0.0)
    avg = float(np.mean(scores[np.isfinite(scores)]))
    if avg > 0.2:
        return StrategySignal("sentiment", SignalDirection.LONG.value, abs(avg))
    elif avg < -0.2:
        return StrategySignal("sentiment", SignalDirection.SHORT.value, abs(avg))
    return StrategySignal("sentiment", SignalDirection.HOLD.value, 1.0 - abs(avg))


def signal_risk_v2(prices, volatility=None, drawdown=None, cfg=None):
    if cfg is None:
        cfg = StrategyConfig()
    danger = 0.0
    if volatility is not None:
        danger += min(1.0, volatility / 100.0) * 0.5
    if drawdown is not None:
        danger += min(1.0, abs(drawdown) / 20.0) * 0.5
    if danger > 0.5:
        return StrategySignal("risk_manager", SignalDirection.SHORT.value, danger)
    elif danger > 0.2:
        return StrategySignal("risk_manager", SignalDirection.HOLD.value, danger)
    return StrategySignal("risk_manager", SignalDirection.LONG.value, 1.0 - danger)


# ======================================================================
#  4. CONFIDENCE MODEL (v3: regime penalty)
# ======================================================================
def confidence_model(signals, weights, regime):
    wc = sum(weights.get(n, 0) * s.confidence for n, s in signals.items())
    dirs = [s.direction for s in signals.values() if s.direction != 0]
    if dirs:
        agree = dirs.count(max(set(dirs), key=dirs.count)) / len(dirs)
    else:
        agree = 0.5
    rf = 1.0 if regime == "trending" else (0.5 if regime == "transitional" else 0.75)
    return max(0.0, min(1.0, wc * (0.5 + 0.5 * agree) * rf))


# ======================================================================
#  5. COMBINE / CONFLICT / HYSTERESIS / SIZING / DECIDE
# ======================================================================
def combine_signals(signals, weights, cfg):
    return float(np.clip(sum(weights.get(n,0)*s.direction*s.confidence for n,s in signals.items()), -1, 1))


def check_signal_conflict(signals, threshold):
    high = [s for s in signals.values() if s.confidence > 0.5]
    dirs = set(s.direction for s in high)
    return 1 in dirs and -1 in dirs


def hysteresis_decision(score, prev_action, cfg):
    hb = cfg.hysteresis_band; t = cfg.decision_threshold
    if abs(score) < t: return "hold"
    if prev_action == "buy": return "sell" if score < -hb else "buy"
    if prev_action == "sell": return "buy" if score > hb else "sell"
    return "buy" if score > 0 else "sell"


def compute_position_size(score, cfg, conflict, volatility=None, regime=None):
    base = abs(score) * cfg.risk
    if conflict: base *= 0.3
    # Volatility scaling: high vol = smaller position
    if volatility and volatility > 0:
        base *= min(1.0, 5.0 / max(volatility, 1.0))
    # Regime scaling
    if regime == "transitional":
        base *= 0.4
    elif regime == "ranging":
        base *= 0.6
    return round(min(max(0.0, base), cfg.max_position_pct), 4)


def check_exits(current_price, entry_price, peak_price,
                stop_loss, take_profit, trailing_stop):
    """Stop-loss / take-profit / trailing stop check."""
    pnl_pct = (current_price - entry_price) / max(entry_price, 1e-9)
    if pnl_pct <= -stop_loss: return "stop_loss"
    if pnl_pct >= take_profit: return "take_profit"
    if current_price < peak_price * (1 - trailing_stop): return "trailing_stop"
    return None


def decide(prices, sentiment_scores=None, volatility=None,
           drawdown=None, prev_action="hold", cfg=None):
    if cfg is None: cfg = StrategyConfig()
    if prices is None or len(prices) == 0:
        return DecisionOutput(
            risk_level=cfg.risk,
            weights={"momentum": 0, "sentiment": 0, "risk_manager": 1},
            signals={"momentum": StrategySignal("momentum", 0, 0),
                     "sentiment": StrategySignal("sentiment", 0, 0),
                     "risk_manager": StrategySignal("risk_manager", 0, 1)},
            decision={"action": TradingAction.HOLD, "position_size": 0},
            metadata={"reason": "MISSING_DATA", "paper_trading": True})

    regime = market_regime(prices, cfg)
    weights = compute_weights(cfg)
    weights = adapt_weights(weights, regime)

    sig_m = signal_momentum_v2(prices, cfg)
    sig_s = signal_sentiment(sentiment_scores)
    sig_r = signal_risk_v2(prices, volatility, drawdown, cfg)
    signals = {"momentum": sig_m, "sentiment": sig_s, "risk_manager": sig_r}

    conf = confidence_model(signals, weights, regime)
    conflict = check_signal_conflict(signals, cfg.conflict_threshold)
    score = combine_signals(signals, weights, cfg)

    # ── v3: MOMENTUM FILTER ──────────────────────────────────
    # Block long entries when momentum says SHORT with high confidence
    if prev_action == "hold" and sig_m.direction < 0 and sig_m.confidence > 0.5:
        score *= 0.3  # Severely reduce score — force HOLD

    # ── v3: REGIME FILTER ────────────────────────────────────
    if regime == "transitional":
        score *= 0.5

    # ── Hysteresis decision ──────────────────────────────────
    raw = hysteresis_decision(score, prev_action, cfg)

    # ── Confidence + final action ────────────────────────────
    if conf < cfg.min_confidence:
        action = TradingAction.HOLD; position = 0.0
    elif raw == "buy":
        # Double-check: don't buy into a strong downtrend
        if sig_m.direction < 0 and sig_m.confidence > 0.7 and regime == "ranging":
            action = TradingAction.HOLD; position = 0.0
        else:
            action = TradingAction.BUY
            position = compute_position_size(score, cfg, conflict, volatility, regime)
    elif raw == "sell":
        action = TradingAction.SELL
        position = compute_position_size(score, cfg, conflict, volatility, regime)
    else:
        action = TradingAction.HOLD; position = 0.0

    return DecisionOutput(
        risk_level=cfg.risk, weights=weights, signals=signals,
        decision={"action": action, "position_size": position},
        metadata={"conflict": conflict, "score": round(score, 4),
                  "confidence": round(conf, 4), "regime": regime,
                  "paper_trading": cfg.paper_trading})
