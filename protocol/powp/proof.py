"""ProofOfPhysicalWork — on-chain proof data model.

Spec (AGENTS.md §6.8, BUILD.md §9):
    Serializable proof that links an evaluation artifact to the Konnex network.
    Contains only protocol-safe fields: no RobotState, no Gazebo handles, no ROS2 nodes.

Status: COMPLETE (Phase 7).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProofOfPhysicalWork:
    """On-chain proof linking a PoPW evaluation to the Konnex network.

    All fields are protocol-safe primitives (str, int, float).
    No imports from robotics/, simulation/, or ml/ allowed.
    """

    mission_id: str
    policy_id: str
    policy_hash: str
    scenario_id: str
    seed: int
    env_version: str
    score: float
    artifact_hash: str
    artifact_url: str
    timestamp: float = field(default_factory=time.time)
    proof_hash: str = ""

    def seal(self) -> ProofOfPhysicalWork:
        """Compute and attach the proof hash. Returns self."""
        return ProofOfPhysicalWork(
            mission_id=self.mission_id,
            policy_id=self.policy_id,
            policy_hash=self.policy_hash,
            scenario_id=self.scenario_id,
            seed=self.seed,
            env_version=self.env_version,
            score=self.score,
            artifact_hash=self.artifact_hash,
            artifact_url=self.artifact_url,
            timestamp=self.timestamp,
            proof_hash=self._compute_hash(),
        )

    def _compute_hash(self) -> str:
        """SHA-256 of canonical JSON (sorted keys, floats to 6dp, proof_hash excluded)."""
        payload = {}
        for key, value in self.__dict__.items():
            if key == "proof_hash":
                continue
            if isinstance(value, float):
                payload[key] = round(value, 6)
            else:
                payload[key] = value
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify(self) -> bool:
        """Verify the proof hash matches the recomputed hash."""
        if not self.proof_hash:
            return False
        return self.proof_hash == self._compute_hash()

    def to_json(self) -> str:
        """Serialize to JSON including the proof hash."""
        payload = {}
        for key, value in self.__dict__.items():
            if isinstance(value, float):
                payload[key] = round(value, 6)
            else:
                payload[key] = value
        return json.dumps(payload, sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, text: str) -> ProofOfPhysicalWork:
        """Deserialize from JSON."""
        data = json.loads(text)
        return cls(
            mission_id=str(data["mission_id"]),
            policy_id=str(data["policy_id"]),
            policy_hash=str(data["policy_hash"]),
            scenario_id=str(data["scenario_id"]),
            seed=int(data["seed"]),
            env_version=str(data["env_version"]),
            score=float(data["score"]),
            artifact_hash=str(data["artifact_hash"]),
            artifact_url=str(data["artifact_url"]),
            timestamp=float(data["timestamp"]),
            proof_hash=str(data.get("proof_hash", "")),
        )
