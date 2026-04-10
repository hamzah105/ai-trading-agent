# TrustlessAI Trader

> An autonomous AI trading agent with verifiable on-chain identity, risk-aware execution, and transparent trust signals.

## Short Description

QuantAgent is an autonomous AI trading system that combines mathematical strategy, multi-signal fusion, and ERC-8004 verifiable identity. Every trade decision is validated, logged, and cryptographically verifiable — making it the safest, most transparent AI agent in crypto.

## Full Description

QuantAgent is a modular, risk-aware AI trading system built for the Kraken Hackathon.

Architecture:
 Layer 1 (Data/Signals): Multi-source signal pipeline with momentum (RSI+MACD+EMA), sentiment (PRISM API), and market regime detection. All inputs validated and sanitized.

 Layer 2 (Strategy Engine): Risk-parameterized decision engine accepting R  [0,1]. Adaptive position sizing based on volatility and market regime. Momentum filter blocks longs in downtrends. Hysteresis prevents flip-flopping.

 Layer 3 (Execution Agent): Three-mode execution (DRY/PAPER/LIVE) with 8-point pre-trade validation, circuit breaker after 3 losses, daily loss cap at 5%, and adaptive stop-loss. Every action logged and verifiable.

 Layer 4 (Identity & Trust): ERC-8004 agent identity with reputation scoring, cryptographic trade proofs, and transparent risk artifacts.

Safety: Paper trading only. Max 25% position size. Circuit breaker at 3 consecutive losses.

135 tests passing. All modules are modular and plug-and-play.

## Technologies

Python, AI/ML, Trading, Crypto, Kraken API, ERC-8004, Signal Processing, Risk Management

## Categories

Finance, AI/ML, Trading

## Agent Identity (ERC-8004)

```
{
  "agent_id": "0efa914733bc0f65",
  "name": "QuantAgent",
  "version": "2.0.0",
  "owner_address": "0xHamzah",
  "registered_at": 1775158094.4948344,
  "reputation_score": 0.5,
  "total_validations": 0,
  "successful_trades": 0,
  "failed_trades": 0,
  "risk_score": 0.3,
  "metadata": {
    "chain": "mock_erc8004",
    "hackathon": "kraken_2026",
    "type": "ai_trading_agent"
  }
}
```

## Trust Artifacts

```
{
  "agent_id": "0efa914733bc0f65",
  "total_artifacts": 8,
  "artifact_types": {
    "REPUTATION_UPDATE": 2,
    "RISK_VALIDATION": 2,
    "SIGNAL_GENERATED": 2,
    "TRADE_EXECUTION": 2
  },
  "verifiable": true,
  "storage": "D:\\Hamzah\\.openclaw\\projects\\quant-architect-agent\\data\\trust_artifacts"
}
```

## Metrics

- Tests: 135 passing
- Roles: 3 (Strategy + Execution + Signals)
- Safety mechanisms: 8
- Mode: Paper trading only (no real funds)

## Repository

https://github.com/hamzah/quant-architect-agent

## Demo

```bash
python live_demo_paper.py
```
