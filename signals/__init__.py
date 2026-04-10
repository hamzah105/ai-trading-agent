"""
signals package - Data/AI Signal Engineer (Role 3)

Pluggable signal modules that feed the Strategy Agent (Role 1).

Usage:
    from signals import SignalPipeline
    pipeline = SignalPipeline()
    output = pipeline.process(prices, sentiment_scores=np.array([...]))

    # Handoff to Strategy Agent:
    from strategy_math import decide
    signals = output["fused"]
"""

from signals.pipeline import SignalPipeline
from signals.momentum_module import MomentumSignal
from signals.sentiment_module import SentimentSignal
from signals.validator import DataValidator
from signals.config import SignalConfig
