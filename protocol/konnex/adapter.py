"""KonnexAdapter — adapter between the Fleet subnet and the Konnex network.

STATUS: STUB — SDK research complete (see docs/konnex.md), live calls NOT implemented.
All public methods raise NotImplementedError until a real Konnex SDK
integration has been exercised (SYSTEM_PROMPT.md §6.3: never invent API calls).

Verified research (2026-08-09, re-verified 2026-11-01, docs/konnex.md):
- Official docs: https://docs.konnex.world  (docs.konnex.network and
  gitbook.konnex.network DO NOT exist — DNS lookup failed).
- SDK: documented as `from konnex import KonnexClient` with
  `client.tasks.submit`, `client.miners.register`, `client.validators.verify`.
- Install is source-only from `konnex-world/konnex`, which currently returns
  `Repository not found`; `pip index versions konnex` finds no distribution.
- HTTP API prefix: `/api/v1` with documented POST endpoints under
  `/tasks`, `/miners/models`, `/validators/verify`. No reward-query or
  submission-status endpoint is documented.

Boundary contract (docs/protocol.md, TESTING_PLAN.md §14):
- Only these types may cross into this adapter:
      policy_id: str, policy_hash: str, MissionMetadata, EvaluationArtifact
- NEVER: RobotState, Gazebo world handles, ROS 2 nodes, raw trajectories.
- Zero imports from robotics/, simulation/, ml/ in this package.
"""

from __future__ import annotations

import structlog

from protocol.konnex.models import MissionMetadata
from validator.reproducibility.artifact import EvaluationArtifact

logger = structlog.get_logger(__name__)


class KonnexAdapterError(Exception):
    """Raised for invalid adapter input (and, post-verification, SDK failures)."""


def _require_non_empty(value: str, field_name: str) -> None:
    """Raise KonnexAdapterError if a required id/hash is empty or blank."""
    if not value or not value.strip():
        raise KonnexAdapterError(f"{field_name} must not be empty")


class KonnexAdapter:
    """STUB — raises NotImplementedError until the Konnex SDK is integrated.

    Constructor takes only connection configuration; no simulator types.
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        logger.info(
            "konnex_adapter_initialized",
            endpoint=endpoint,
            sdk_verified=False,
        )

    def submit_mission(self, metadata: MissionMetadata) -> str:
        """Submit a mission to Konnex. Returns mission_id."""
        _require_non_empty(metadata.mission_id, "mission_id")
        logger.info("konnex.submit_mission", mission_id=metadata.mission_id)
        raise NotImplementedError("# TODO: verify Konnex SDK submitMission()")

    def submit_policy(
        self,
        policy_id: str,
        policy_hash: str,
        metadata: MissionMetadata | None = None,
    ) -> str:
        """Register a policy. Returns registration_id."""
        _require_non_empty(policy_id, "policy_id")
        _require_non_empty(policy_hash, "policy_hash")
        logger.info(
            "konnex.submit_policy",
            policy_id=policy_id,
            policy_hash=policy_hash,
            has_metadata=metadata is not None,
        )
        raise NotImplementedError("# TODO: verify Konnex SDK submitPolicy()")

    def submit_evaluation(
        self,
        policy_id: str,
        eval_id: str,
        score: float,
        artifact_hash: str,
    ) -> str:
        """Submit an evaluation result. Returns submission_id."""
        _require_non_empty(policy_id, "policy_id")
        _require_non_empty(eval_id, "eval_id")
        _require_non_empty(artifact_hash, "artifact_hash")
        logger.info(
            "konnex.submit_evaluation",
            policy_id=policy_id,
            eval_id=eval_id,
            score=score,
            artifact_hash=artifact_hash,
        )
        raise NotImplementedError("# TODO: verify Konnex SDK submitEvaluation()")

    def publish_proof(self, artifact: EvaluationArtifact) -> str:
        """Publish an evaluation proof on-chain. Returns tx_hash.

        Accepts only the sealed EvaluationArtifact — never raw simulator state.
        """
        _require_non_empty(artifact.policy_id, "policy_id")
        _require_non_empty(artifact.artifact_hash, "artifact_hash")
        logger.info(
            "konnex.publish_proof",
            policy_id=artifact.policy_id,
            artifact_hash=artifact.artifact_hash,
        )
        raise NotImplementedError("# TODO: verify Konnex SDK publishProof()")

    def query_rewards(self, policy_id: str) -> float:
        """Query pending KNX rewards for a policy."""
        _require_non_empty(policy_id, "policy_id")
        logger.info("konnex.query_rewards", policy_id=policy_id)
        raise NotImplementedError("# TODO: verify Konnex SDK queryRewards()")

    def get_submission_status(self, submission_id: str) -> dict[str, object]:
        """Query submission status. Returns a JSON-shaped dict."""
        _require_non_empty(submission_id, "submission_id")
        logger.info("konnex.get_submission_status", submission_id=submission_id)
        raise NotImplementedError("# TODO: verify Konnex SDK getSubmissionStatus()")
