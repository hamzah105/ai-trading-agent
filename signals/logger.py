"""signals/logger.py - Structured JSON logging for the Signal Agent."""

import json
import os
import datetime
from threading import Lock


class SignalLogger:
    """Thread-safe JSON logger for signal pipeline output."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"signals_{ts}.log")
        self._lock = Lock()

    def log(self, output: dict):
        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(output, default=str) + "\n")

    def error(self, msg: str, context: dict = None):
        entry = {
            "_type": "ERROR",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "message": msg,
            "context": context or {},
        }
        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")

    def info(self, msg: str):
        entry = {
            "_type": "INFO",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "message": msg,
        }
        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
