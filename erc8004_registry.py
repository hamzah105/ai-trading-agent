"""
erc8004_registry.py - Mock ERC-8004 Agent Identity & Reputation Registry

Simulates on-chain identity registration for the AI Trading Agent.
In production, this would interact with an actual ERC-8004 smart contract.

Provides:
- Agent identity minting
- Reputation scoring
- Validation artifact recording
- On-chain trust signal emission
"""

import json
import hashlib
import time
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentIdentity:
    """ERC-8004 compatible agent identity."""
    agent_id: str                    # Unique identifier (keccak256 hash)
    name: str                        # Human-readable name
    version: str                     # Agent version
    owner_address: str               # "Wallet" address (mock)
    registered_at: float             # Timestamp
    reputation_score: float
    total_validations: int
    successful_trades: int
    failed_trades: int
    risk_score: float                # 0 (safe) to 1 (risky)
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "owner_address": self.owner_address,
            "registered_at": self.registered_at,
            "reputation_score": round(self.reputation_score, 4),
            "total_validations": self.total_validations,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "risk_score": round(self.risk_score, 4),
            "metadata": self.metadata,
        }


class ERC8004Registry:
    """
    Mock ERC-8004 registry for hackathon demo.
    In production: replace with actual contract interaction.
    """

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            storage_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data", "erc8004_registry.json"
            )
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        self.identities = {}
        self.validations = []
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r") as f:
                data = json.load(f)
            self.identities = data.get("identities", {})
            self.validations = data.get("validations", [])

    def _save(self):
        with open(self.storage_path, "w") as f:
            json.dump({
                "identities": self.identities,
                "validations": self.validations,
            }, f, indent=2)

    def mint_identity(self, name: str, version: str,
                      owner: str = "0xHamza") -> AgentIdentity:
        """Register a new agent identity on the mock chain."""
        timestamp = time.time()
        agent_id = hashlib.sha256(
            f"{name}:{version}:{owner}:{timestamp}".encode()
        ).hexdigest()[:16]

        identity = AgentIdentity(
            agent_id=agent_id,
            name=name,
            version=version,
            owner_address=owner,
            registered_at=timestamp,
            reputation_score=0.5,  # Starting neutral
            total_validations=0,
            successful_trades=0,
            failed_trades=0,
            risk_score=0.3,  # Starting safe
            metadata={
                "chain": "mock_erc8004",
                "hackathon": "kraken_2026",
                "type": "ai_trading_agent",
            }
        )

        self.identities[agent_id] = identity.to_dict()
        self._emit_event("IDENTITY_MINTED", {
            "agent_id": agent_id,
            "name": name,
            "tx_hash": agent_id,
        })
        self._save()
        return identity

    def update_reputation(self, agent_id: str, performance: dict):
        """Update reputation based on trading performance."""
        if agent_id not in self.identities:
            return None

        identity = self.identities[agent_id]
        identity["total_validations"] += 1

        pnl = performance.get("pnl", 0)
        drawdown = performance.get("drawdown", 0)
        sharpe = performance.get("sharpe", 0)

        # Reputation formula: weighted blend
        pnl_score = max(-1, min(1, pnl / 100)) * 0.4
        dd_score = max(-1, min(0, drawdown / 10)) * 0.3
        sharpe_score = max(-1, min(1, sharpe / 2)) * 0.3

        new_rep = identity["reputation_score"] + (pnl_score + dd_score + sharpe_score) * 0.05
        identity["reputation_score"] = max(0.0, min(1.0, round(new_rep, 4)))

        # Risk score: lower is safer
        if drawdown > 5:
            identity["risk_score"] = min(1.0, identity["risk_score"] + 0.1)
        else:
            identity["risk_score"] = max(0.0, identity["risk_score"] - 0.02)

        if pnl > 0:
            identity["successful_trades"] += 1
        else:
            identity["failed_trades"] += 1

        self._emit_event("REPUTATION_UPDATED", {
            "agent_id": agent_id,
            "new_reputation": identity["reputation_score"],
            "new_risk": identity["risk_score"],
        })
        self._save()
        return identity

    def record_validation(self, agent_id: str, artifact_type: str,
                          data: dict) -> str:
        """Record a validation artifact (trade proof, risk check, etc.)."""
        validation = {
            "agent_id": agent_id,
            "type": artifact_type,
            "timestamp": time.time(),
            "data": data,
            "hash": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12],
        }
        self.validations.append(validation)
        self._emit_event("VALIDATION_RECORDED", {
            "agent_id": agent_id,
            "type": artifact_type,
            "hash": validation["hash"],
        })
        self._save()
        return validation["hash"]

    def get_leaderboard(self) -> list:
        """Return sorted leaderboard by reputation score."""
        agents = list(self.identities.values())
        return sorted(agents, key=lambda x: x["reputation_score"], reverse=True)

    def _emit_event(self, event_type: str, data: dict):
        """Emit a mock on-chain event."""
        event = {
            "event": event_type,
            "data": data,
            "timestamp": time.time(),
        }
        # Append to event log
        log_path = self.storage_path.replace(".json", "_events.json")
        events = []
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                events = json.load(f)
        events.append(event)
        with open(log_path, "w") as f:
            json.dump(events, f, indent=2)

    def get_trust_report(self, agent_id: str) -> dict:
        """Generate a trust report for submission."""
        if agent_id not in self.identities:
            return {"error": "Agent not found"}

        identity = self.identities[agent_id]
        agent_validations = [v for v in self.validations if v["agent_id"] == agent_id]

        return {
            "identity": identity,
            "total_validations": len(agent_validations),
            "reputation_score": identity["reputation_score"],
            "risk_assessment": "LOW" if identity["risk_score"] < 0.3 else (
                "MEDIUM" if identity["risk_score"] < 0.7 else "HIGH"
            ),
            "verifiable": True,
            "chain": "mock_erc8004",
            "validations": agent_validations[-20:],  # Last 20
        }
