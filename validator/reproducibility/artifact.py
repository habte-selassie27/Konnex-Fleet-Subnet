"""EvaluationArtifact — serializable proof of a completed evaluation.

Status: COMPLETE (Phase 6/7).
Contract (BUILD.md §8, TESTING_PLAN.md §3.5):
- compute_hash() is deterministic: SHA-256 of canonical JSON (keys sorted,
  floats rounded to 6dp, artifact_hash excluded).
- Any field change changes the hash (tamper detection).
- to_json/from_json roundtrip preserves the artifact.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, cast


@dataclass
class EvaluationArtifact:
    """Immutable-by-convention proof of a validator evaluation."""

    policy_id: str
    policy_hash: str
    scenario_id: str
    seed: int
    env_version: str
    sim_version: str
    score_components: dict[str, float]
    final_score: float
    completion_time_s: float
    collision_count: int
    tasks_completed: int
    tasks_total: int
    energy_consumed: float
    timestamp: float
    artifact_hash: str = ""

    def seal(self) -> EvaluationArtifact:
        """Compute and attach the artifact hash. Returns self."""
        self.artifact_hash = self.compute_hash()
        return self

    def verify(self) -> bool:
        """Verify the artifact hash matches the recomputed hash.

        Returns False if the hash is empty or does not match.
        """
        if not self.artifact_hash:
            return False
        return self.artifact_hash == self.compute_hash()

    def compute_hash(self) -> str:
        """SHA-256 of canonical JSON (sorted keys, floats to 6dp)."""
        canonical = json.dumps(self._canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        """Serialize including the artifact hash."""
        payload = self._canonical()
        payload["artifact_hash"] = self.artifact_hash
        return json.dumps(payload, sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, text: str) -> EvaluationArtifact:
        """Deserialize a serialized artifact (including its stored hash)."""
        data = cast(dict[str, Any], json.loads(text))
        artifact = cls(
            policy_id=str(data["policy_id"]),
            policy_hash=str(data["policy_hash"]),
            scenario_id=str(data["scenario_id"]),
            seed=int(data["seed"]),
            env_version=str(data["env_version"]),
            sim_version=str(data["sim_version"]),
            score_components=cast(dict[str, float], data["score_components"]),
            final_score=float(data["final_score"]),
            completion_time_s=float(data["completion_time_s"]),
            collision_count=int(data["collision_count"]),
            tasks_completed=int(data["tasks_completed"]),
            tasks_total=int(data["tasks_total"]),
            energy_consumed=float(data["energy_consumed"]),
            timestamp=float(data["timestamp"]),
            artifact_hash=str(data.get("artifact_hash", "")),
        )
        return artifact

    def _canonical(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        for key, value in self.__dict__.items():
            if key == "artifact_hash":
                continue
            if isinstance(value, float):
                payload[key] = round(value, 6)
            elif isinstance(value, dict):
                payload[key] = {
                    k: round(v, 6) if isinstance(v, float) else v for k, v in value.items()
                }
            else:
                payload[key] = value
        return payload
