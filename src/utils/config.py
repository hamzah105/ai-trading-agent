"""
Configuration loader and validator.
"""

import os
from pathlib import Path
from typing import Dict, Any
import json

def load_config() -> Dict[str, Any]:
    """Load configuration from .env + optional config file."""
    base_dir = Path(__file__).parent.parent.parent

    # Load .env via python-dotenv
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=base_dir / ".env")

    # Default configuration
    config = {
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "trading_mode": os.getenv("TRADING_MODE", "paper"),
        "symbol": os.getenv("SYMBOL", "BTC/USD"),
        "timeframe": os.getenv("TIMEFRAME", "1h"),
        "capital": float(os.getenv("CAPITAL", 10000)),
        "max_position_size": float(os.getenv("MAX_POSITION_SIZE", 0.1)),
        "stop_loss": float(os.getenv("STOP_LOSS", 0.02)),
        "take_profit": float(os.getenv("TAKE_PROFIT", 0.04)),
        "database_url": os.getenv("DATABASE_URL", "sqlite:///trading.db"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }

    # Load additional config from file if present
    config_file = base_dir / "config.json"
    if config_file.exists():
        with open(config_file) as f:
            file_cfg = json.load(f)
            config.update(file_cfg)

    # Validate
    if not config["openrouter_api_key"]:
        raise ValueError("OPENROUTER_API_KEY is not set in .env")

    return config
