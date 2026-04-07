#!/usr/bin/env python3
"""
🤖 AI Trading Agent — Main Entry Point

This script initializes the trading agent, connects to the exchange,
and starts the real-time analysis and trading loop.
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from dotenv import load_dotenv
from src.utils.config import load_config
from src.trading_agent import TradingAgent

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("ai_trading_agent")

def main():
    """Main entry point."""
    # Load environment variables
    env_path = project_root / ".env"
    if not env_path.exists():
        log.error("Missing .env file. Please copy .env.example to .env and configure your settings.")
        sys.exit(1)

    load_dotenv(dotenv_path=env_path)

    # Load configuration
    config = load_config()

    # Safety check: paper mode warning
    if config.get("trading_mode", "paper") != "paper":
        log.warning("⚠️  LIVE TRADING MODE ENABLED — proceed with extreme caution!")
    else:
        log.info("🧪 Running in PAPER (simulation) mode — no real money at risk.")

    # Initialize agent
    agent = TradingAgent(config)

    # Start trading loop
    try:
        log.info("🚀 Starting AI Trading Agent...")
        agent.run()
    except KeyboardInterrupt:
        log.info("🛑 Shutting down gracefully...")
        agent.shutdown()
    except Exception as e:
        log.exception(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
