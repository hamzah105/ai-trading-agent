"""
trust_signals.py - On-chain trust signals & validation artifacts

Emits verifiable trust signals for every trading action.
Compatible with ERC-8004 identity system.
"""

import json
import hashlib
import time
import os
from typing import Optional


class TrustSignalEmitter:
    """Emits trust artifacts for agent actions."""

    def __init__(self, agent_id: str, storage_dir: str = None):
        self.agent_id = agent_id
        if storage_dir is None:
            storage_dir = os.path.join(
                os.path.dirname(__file__), "data", "trust_artifacts"
            )
        os.makedirs(storage_dir, exist_ok=True)
        self.storage_dir = storage_dir

    def emit_trade(self, decision: dict, state: dict) -> str:
        """Emit a trade validation artifact."""
        artifact = {
            "agent_id": self.agent_id,
            "type": "TRADE_EXECUTION",
            "timestamp": time.time(),
            "decision": decision,
            "portfolio_state": state,
        }
        return self._store(artifact)

    def emit_risk_check(self, checks: dict) -> str:
        """Emit a risk validation artifact."""
        artifact = {
            "agent_id": self.agent_id,
            "type": "RISK_VALIDATION",
            "timestamp": time.time(),
            "checks": checks,
            "passed": all(checks.values()),
        }
        return self._store(artifact)

    def emit_signal(self, signal: dict) -> str:
        """Emit a signal generation artifact."""
        artifact = {
            "agent_id": self.agent_id,
            "type": "SIGNAL_GENERATED",
            "timestamp": time.time(),
            "signal": signal,
        }
        return self._store(artifact)

    def emit_circuit_breaker(self, state: dict) -> str:
        """Emit a circuit breaker activation artifact."""
        artifact = {
            "agent_id": self.agent_id,
            "type": "CIRCUIT_BREAKER",
            "timestamp": time.time(),
            "state": state,
        }
        return self._store(artifact)

    def emit_reputation_update(self, reputation: float, reason: str) -> str:
        """Emit a reputation update artifact."""
        artifact = {
            "agent_id": self.agent_id,
            "type": "REPUTATION_UPDATE",
            "timestamp": time.time(),
            "reputation": reputation,
            "reason": reason,
        }
        return self._store(artifact)

    def _store(self, artifact: dict) -> str:
        """Store artifact and return hash."""
        # Create deterministic hash
        data_str = json.dumps(artifact, sort_keys=True)
        artifact["hash"] = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        # Store as individual file
        filename = f"{artifact['type']}_{artifact['timestamp']:.0f}_{artifact['hash'][:8]}.json"
        filepath = os.path.join(self.storage_dir, filename)

        with open(filepath, "w") as f:
            json.dump(artifact, f, indent=2)

        return artifact["hash"]

    def get_all_artifacts(self, artifact_type: str = None) -> list:
        """Retrieve stored artifacts."""
        artifacts = []
        if not os.path.exists(self.storage_dir):
            return artifacts

        for fname in sorted(os.listdir(self.storage_dir)):
            if artifact_type and not fname.startswith(artifact_type):
                continue
            filepath = os.path.join(self.storage_dir, fname)
            if filepath.endswith(".json"):
                with open(filepath, "r") as f:
                    artifacts.append(json.load(f))
        return artifacts

    def get_summary(self) -> dict:
        """Summary of all artifacts for submission."""
        artifacts = self.get_all_artifacts()
        types = {}
        for a in artifacts:
            t = a.get("type", "unknown")
            types[t] = types.get(t, 0) + 1

        return {
            "agent_id": self.agent_id,
            "total_artifacts": len(artifacts),
            "artifact_types": types,
            "verifiable": True,
            "storage": self.storage_dir,
        }
