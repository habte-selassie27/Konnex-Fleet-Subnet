"""MockKonnectProvider — local mock implementing the KonnexProvider protocol.

Simulates the full PoPW lifecycle without any network calls:
- Missions are tracked in-memory
- Evaluations accumulate and compute simulated KNX rewards
- Proof publication records artifacts with deterministic tx hashes
- Rewards scale with evaluation score (higher score = more KNX)

Use this for:
- Local development and testing
- Demo mode (make konnex-demo)
- CI/CD pipeline validation
- Any environment where real Konnex SDK is not available

Boundary contract (AGENTS.md §6.8):
    Only protocol-safe types cross this boundary.
    Zero imports from robotics/, simulation/, ml/, fleet/.

Status: COMPLETE.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import structlog

from protocol.konnex.models import MissionMetadata, SubmissionReceipt
from validator.reproducibility.artifact import EvaluationArtifact

logger = structlog.get_logger(__name__)


# ─── Simulated reward parameters ─────────────────────────────────────────────

# KNX per point of PoPW score (0–100 scale)
KNX_PER_SCORE_POINT: float = 0.1

# Base reward for any successful evaluation submission
BASE_EVAL_REWARD_KNX: float = 5.0

# Bonus multiplier for high scores (> 80)
HIGH_SCORE_BONUS_MULTIPLIER: float = 1.5

# Maximum KNX reward per single evaluation
MAX_REWARD_PER_EVAL: float = 20.0


@dataclass
class _MissionRecord:
    """In-memory record of a submitted mission."""

    mission_id: str
    policy_id: str
    scenario_id: str
    seed: int
    submitted_at: float
    submission_id: str


@dataclass
class _EvalRecord:
    """In-memory record of a submitted evaluation."""

    eval_id: str
    policy_id: str
    score: float
    artifact_hash: str
    submitted_at: float
    submission_id: str
    reward_knx: float


@dataclass
class _ProofRecord:
    """In-memory record of a published proof."""

    artifact_hash: str
    policy_id: str
    tx_hash: str
    published_at: float
    submission_id: str


class MockKonnexProvider:
    """Local mock implementing the KonnexProvider protocol.

    All state is in-memory. No persistence. No network calls.
    Suitable for development, testing, and demo mode.
    """

    def __init__(self) -> None:
        self._missions: dict[str, _MissionRecord] = {}
        self._evals: dict[str, _EvalRecord] = {}
        self._proofs: dict[str, _ProofRecord] = {}
        self._rewards: dict[str, float] = {}  # policy_id -> accumulated KNX
        self._submission_counter: int = 0
        logger.info("mock_konnex_provider_initialized")

    def submit_mission(self, metadata: MissionMetadata) -> SubmissionReceipt:
        """Register a mission locally. Returns a receipt."""
        self._submission_counter += 1
        submission_id = f"mock_sub_{self._submission_counter:06d}"

        record = _MissionRecord(
            mission_id=metadata.mission_id,
            policy_id=metadata.policy_id,
            scenario_id=metadata.scenario_id,
            seed=metadata.seed,
            submitted_at=time.time(),
            submission_id=submission_id,
        )
        self._missions[metadata.mission_id] = record

        logger.info(
            "mock_mission_submitted",
            mission_id=metadata.mission_id,
            submission_id=submission_id,
        )

        return SubmissionReceipt(
            submission_id=submission_id,
            status="accepted",
            tx_hash=_mock_tx_hash(submission_id),
        )

    def submit_evaluation(
        self,
        policy_id: str,
        eval_id: str,
        score: float,
        artifact_hash: str,
    ) -> SubmissionReceipt:
        """Report an evaluation result locally. Computes and credits reward."""
        self._submission_counter += 1
        submission_id = f"mock_sub_{self._submission_counter:06d}"

        reward = _compute_reward(score)
        self._rewards[policy_id] = self._rewards.get(policy_id, 0.0) + reward

        record = _EvalRecord(
            eval_id=eval_id,
            policy_id=policy_id,
            score=score,
            artifact_hash=artifact_hash,
            submitted_at=time.time(),
            submission_id=submission_id,
            reward_knx=reward,
        )
        self._evals[eval_id] = record

        logger.info(
            "mock_evaluation_submitted",
            policy_id=policy_id,
            eval_id=eval_id,
            score=score,
            reward_knx=reward,
        )

        return SubmissionReceipt(
            submission_id=submission_id,
            status="accepted",
            tx_hash=_mock_tx_hash(submission_id),
        )

    def publish_proof(self, artifact: EvaluationArtifact) -> SubmissionReceipt:
        """Anchor a sealed evaluation artifact locally."""
        self._submission_counter += 1
        submission_id = f"mock_sub_{self._submission_counter:06d}"

        record = _ProofRecord(
            artifact_hash=artifact.artifact_hash,
            policy_id=artifact.policy_id,
            tx_hash=_mock_tx_hash(submission_id),
            published_at=time.time(),
            submission_id=submission_id,
        )
        self._proofs[artifact.artifact_hash] = record

        logger.info(
            "mock_proof_published",
            policy_id=artifact.policy_id,
            artifact_hash=artifact.artifact_hash,
            tx_hash=record.tx_hash,
        )

        return SubmissionReceipt(
            submission_id=submission_id,
            status="confirmed",
            tx_hash=record.tx_hash,
        )

    def query_rewards(self, policy_id: str) -> float:
        """Query accumulated KNX rewards for a policy."""
        reward = self._rewards.get(policy_id, 0.0)
        logger.info("mock_rewards_queried", policy_id=policy_id, reward=reward)
        return reward

    def get_submission_status(self, submission_id: str) -> dict[str, object]:
        """Look up a prior submission by ID."""
        # Check missions
        for mission_record in self._missions.values():
            if mission_record.submission_id == submission_id:
                return {
                    "submission_id": submission_id,
                    "type": "mission",
                    "status": "confirmed",
                    "mission_id": mission_record.mission_id,
                }

        # Check evaluations
        for eval_record in self._evals.values():
            if eval_record.submission_id == submission_id:
                return {
                    "submission_id": submission_id,
                    "type": "evaluation",
                    "status": "confirmed",
                    "eval_id": eval_record.eval_id,
                    "score": eval_record.score,
                    "reward_knx": eval_record.reward_knx,
                }

        # Check proofs
        for proof_record in self._proofs.values():
            if proof_record.submission_id == submission_id:
                return {
                    "submission_id": submission_id,
                    "type": "proof",
                    "status": "confirmed",
                    "tx_hash": proof_record.tx_hash,
                }

        return {
            "submission_id": submission_id,
            "type": "unknown",
            "status": "not_found",
        }

    # ─── Introspection (not part of protocol, useful for demos/tests) ────────

    def get_policy_rewards(self) -> dict[str, float]:
        """Return a copy of all accumulated policy rewards."""
        return dict(self._rewards)

    def get_mission_count(self) -> int:
        return len(self._missions)

    def get_eval_count(self) -> int:
        return len(self._evals)

    def get_proof_count(self) -> int:
        return len(self._proofs)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _compute_reward(score: float) -> float:
    """Compute simulated KNX reward from a PoPW score (0–100)."""
    base = BASE_EVAL_REWARD_KNX + score * KNX_PER_SCORE_POINT
    if score > 80.0:
        base *= HIGH_SCORE_BONUS_MULTIPLIER
    return round(min(base, MAX_REWARD_PER_EVAL), 4)


def _mock_tx_hash(submission_id: str) -> str:
    """Deterministic mock tx hash from submission_id."""
    return "0x" + hashlib.sha256(submission_id.encode()).hexdigest()[:16]
