# Quant / Strategy Architect Agent — Kraken Hackathon

> Full AI trading system: Signal → Strategy → Execution pipeline.
> Three roles, one repo. Modular, secure, deterministic.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA LAYER (Role 3)                      │
│                                                              │
│  [OHLCV from Kraken API] ──► Validator ──► Cleaner           │
│                                                              │
│       ┌───────────┐  ┌──────────┐  ┌────────┐               │
│       │ Momentum  │  │Sentiment │  │ Regime │  (pluggable)   │
│       └─────┬─────┘  └────┬─────┘  └───┬────┘               │
│             └──────┬──────┘──────┬─────┘                      │
│                    ▼              ▼                           │
│              ┌─────────┐  ┌────────────┐                      │
│              │  Fusion  │  │ confidence │                      │
│              └─────┬───┘  └────────────┘                      │
│                    │  Fused Signal Output                       │
├────────────────────┼───────────────────────────────────────────┤
│              STRATEGY LAYER (Role 1)                           │
│                                                              │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐       │
│  │ Weight Func │  │ Signal Gen │  │ Decision Engine  │       │
│  │  f(R) → w   │  │ RSI/MACD/  │  │ Score → Action   │       │
│  │             │  │Sentiment   │  │ + Position Size  │       │
│  └──────┬──────┘  └────────────┘  └────────┬─────────┘       │
│         └───────────────────────────────────┘                  │
│                    │  Decision Output (JSON contract)           │
├────────────────────┼───────────────────────────────────────────┤
│              EXECUTION LAYER (Role 2)                          │
│                                                              │
│  ┌──────────┐  ┌───────────┐  ┌─────────┐  ┌──────────────┐  │
│  │Validator │→ │ Executor  │→ │  State  │  │ Circuit      │  │
│  │ 8 checks │  │DRY/P/LIVE │  │ Tracker │  │  Breaker     │  │
│  └──────────┘  └───────────┘  └─────────┘  └──────────────┘  │
│                                                              │
│  Structured JSON Logging (signals, orders, errors, PnL)      │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
pip install numpy pandas python-dotenv
```

### Role 1 — Quant Strategy Engine

```python
from config import StrategyConfig
from strategy_math import decide

cfg = StrategyConfig(risk=0.7, risk_mode="logistic")
decision = decide(prices, cfg=cfg)
print(decision.to_dict())
```

### Role 2 — Execution Agent

```python
from execution.config import ExecutionConfig, ExecutionMode
from execution.executor import ExecutionEngine
from execution.logger import ExecutionLogger

config = ExecutionConfig(mode=ExecutionMode.DRY_RUN)
log = ExecutionLogger()
engine = ExecutionEngine(config, log)
result = engine.execute_order(decision.to_dict(), price=50000.0)
```

### Role 3 — Data / Signal Pipeline

```python
from signals import SignalPipeline

pipeline = SignalPipeline()
output = pipeline.process(prices, sentiment_scores=scores)
print(output["fused"])  # {"signal": 1, "confidence": 0.68, ...}
```

## Directory Structure

```
quant-architect-agent/
├── config.py               ← Strategy config (editable by user)
├── strategy_math.py        ← Role 1: weights, signals, decisions
├── signals_schema.py       ← Strict JSON output contract
├── indicators.py           ← Technical indicators (RSI, MACD, ADX, etc.)
├── data_feed.py            ← Kraken OHLCV fetcher (public API)
├── backtest.py             ← Paper trading with fees, exits, metrics
├── requirements.txt        ← numpy, pandas, python-dotenv
│
├── signals/                ← Role 3: Data / AI Signal Engineer
│   ├── momentum_module.py  ← RSI + MACD + EMA momentum
│   ├── sentiment_module.py ← PRISM API / manual sentiment
│   ├── validator.py        ← Data validation & cleaning
│   ├── pipeline.py         ← Full signal pipeline orchestration
│   ├── config.py           ← Signal tuning parameters
│   └── logger.py           ← Structured JSON logging
│
├── execution/              ← Role 2: Execution Agent
│   ├── config.py           ← Execution mode, safety limits
│   ├── validator.py        ← Pre-trade validation (8 checks)
│   ├── executor.py         ← Core execution (DRY_RUN/PAPER/LIVE)
│   ├── logger.py           ← Structured JSON logging
│   └── loop.py             ← Automation polling loop
│
├── tests/
│   ├── test_quant_engine.py   ← Role 1 tests (58)
│   ├── test_execution.py      ← Role 2 tests (32)
│   ├── test_signals.py        ← Role 3 tests (45)
│   ├── run_backtests.py       ← Risk/mode matrix
│   └── run_demo.py            ← Engine decisions by R value
│
├── data/                   ← Cached OHLCV + backtest results
└── logs/                   ← Runtime logs
```

## Role 1 — Quant Strategy Engine

**Purpose:** Mathematical trading logic. Accepts risk parameter R ∈ [0,1] and produces deterministic trading decisions.

### Features
- Risk-weighted strategy combination (Momentum + Sentiment + Risk Manager)
- Linear and logistic weight scaling
- Hysteresis (prevents flip-flopping)
- Conflict detection (70% position reduction on disagreement)
- Fail-safe: missing data → HOLD

### Tests
```bash
python tests/test_quant_engine.py   # 58/58 passing
```

## Role 2 — Execution Agent

**Purpose:** Safely execute strategy decisions through validation, state tracking, and order routing.

### Execution Modes
| Mode | Behavior |
|------|----------|
| `DRY_RUN` | Simulate only, full logging (default) |
| `PAPER` | Sandbox with realistic fills + slippage |
| `LIVE` | Real Kraken API — requires env vars (disabled by default) |

### Safety
- Max position size: 25%
- Daily loss limit: 5%
- Circuit breaker: 3 consecutive losses → halt
- Retry with exponential backoff on failures
- Manual reset required after circuit breaker trip

### Tests
```bash
python tests/test_execution.py   # 32/32 passing
```

## Role 3 — Data / AI Signal Engineer

**Purpose:** Collect, process, and generate high-quality trading signals.

### Pipeline Stages
1. **Ingest** — OHLCV + Sentiment data
2. **Validate** — NaN, outliers, range checks, OHLC consistency
3. **Clean** — Forward-fill, outlier smoothing
4. **Generate** — Momentum (RSI+MACD+EMA), Sentiment (PRISM/manual), Regime
5. **Fuse** — Weighted combination with agreement bonus
6. **Output** — Strict JSON contract for Strategy Agent

### Signal Contract
```json
{
  "signal": -1,
  "confidence": 0.75,
  "source": "momentum",
  "details": {}
}
```

### Tests
```bash
python tests/test_signals.py   # 45/45 passing
```

## Handoff Between Roles

```
Role 3 (Signal) → Role 1 (Strategy) → Role 2 (Execution)

Signal Pipeline Output:
  {"fused": {"signal": 1, "confidence": 0.68}, ...}
    │
    ▼
Strategy Engine:
  {"decision": {"action": "buy", "position_size": 0.0821}}
    │
    ▼
Execution Agent:
  {"status": "EXECUTED", "order": {...}}
```

## Security

- No hardcoded API keys — use env vars (`PRISM_API_KEY`, `KRAKEN_API_KEY`, etc.)
- Paper trading enforced by default
- LIVE mode requires explicit `EXECUTION_MODE=live` env + valid keys
- All logs are JSON-structured, timestamped, non-sensitive
- Least-privilege design: each role only does its job

## Running Tests

```bash
# All roles
python tests/test_quant_engine.py
python tests/test_execution.py
python tests/test_signals.py

# Backtest matrix
python tests/run_backtests.py
python tests/run_demo.py
```

## Notes for Team Handoff

- **Risk/Execution agents** can plug into `DecisionOutput.decision`
- **Sentiment agents** feed scores into `signal_sentiment()`
- **Live data** swap `generate_mock_prices()` with real OHLCV via `data_feed.py`
- **Add a new signal:** drop into `signals/`, register in `pipeline.py`, done
