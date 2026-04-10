# Data / AI Signal Engineer (Role 3)

High-quality, deterministic signal generation pipeline for the Kraken Hackathon trading system.

## Architecture

```
[OHLCV Data] ──┐
               ▼
         ┌──────────────┐
         │   Validator  │ ← NaN, outliers, range checks
         └──────┬───────┘
                ▼
         ┌──────────────┐
         │    Cleaner   │ ← Forward-fill, smooth outliers
         └──────┬───────┘
                ▼
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌───────┐ ┌─────────┐ ┌────────┐
│Momentum│ │Sentiment│ │ Regime │  (pluggable modules)
└───┬───┘ └────┬────┘ └───┬────┘
    └──────────┼──────────┘
               ▼
         ┌──────────────┐
         │    Fusion    │ ← Agreement detection + confidence
         └──────┬───────┘
                ▼
         ┌──────────────┐
         │   Strategy   │ → Role 1 (Decision Engine)
         └──────────────┘
```

## Modules

| File | Purpose |
|------|---------|
| `momentum_module.py` | RSI + MACD + EMA trend → momentum signal |
| `sentiment_module.py` | PRISM API / manual scores → sentiment signal |
| `validator.py` | Data validation, NaN handling, outlier detection |
| `pipeline.py` | Full orchestration: ingest → validate → generate → fuse |
| `config.py` | Signal thresholds, API settings, tuning params |
| `logger.py` | Structured JSON logging |

## Signal Format

Each module outputs:
```json
{
  "signal": -1,
  "confidence": 0.75,
  "source": "momentum",
  "details": {}
}
```

Pipeline fused output:
```json
{
  "fused": {"signal": 1, "confidence": 0.68, "source": "fused", "details": {}},
  "momentum": {"signal": 1, "confidence": 0.80, "source": "momentum", "details": {}},
  "sentiment": {"signal": 0, "confidence": 0.30, "source": "sentiment", "details": {}},
  "regime": {"signal": 1, "confidence": 0.60, "source": "regime", "details": {}},
  "timestamp": "2026-04-02T22:40:00.000000",
  "data_quality": "good"
}
```

## Handoff to Strategy Agent

```python
from signals import SignalPipeline
from strategy_math import decide
import numpy as np

pipeline = SignalPipeline()
output = pipeline.process(prices, sentiment_scores=scores)

# Strategy Agent input
decision = decide(
    prices=prices,
    sentiment_scores=scores,
    cfg=strategy_config,
)
```

## Setup

No extra dependencies needed — uses shared `indicators.py` from Role 1.

```python
# Optional: set sentiment API keys
export PRISM_API_URL="https://api.prism.example/scores"
export PRISM_API_KEY="sk-..."
```

## Tests

```bash
python tests/test_signals.py
```

45 tests: momentum, sentiment, pipeline, fusion, validation, determinism, handoff contract.
