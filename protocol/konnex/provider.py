"""KonnexProvider — protocol interface for Konnex network operations.

Defines the contract that any provider (mock, real, staging) must implement.
This is the primary extension point for adding real Konnex SDK integration.

Boundary contract (AGENTS.md §6.8):
    Only protocol-safe types cross this boundary:
    - str, int, float primitives
    - MissionMetadata, EvaluationArtifact (from protocol.konnex.models)
    - NEVER: RobotState, Gazebo handles, ROS 2 nodes, raw trajectories.

Status: COMPLETE (interface defined).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from protocol.konnex.models import MissionMetadata, SubmissionReceipt
from validator.reproducibility.artifact import EvaluationArtifact


@runtime_checkable
class KonnexProvider(Protocol):
    """Protocol that all Konnex network providers must satisfy.

    Three operations mirror the Konnex PoPW lifecycle:
        1. submit_mission  — register a fleet mission on the network
        2. submit_evaluation — report a validator's evaluation result
        3. publish_proof — anchor an evaluation artifact on-chain

    Plus two query operations:
        4. query_rewards — check pending KNX rewards for a policy
        5. get_submission_status — track a prior submission
    """

    def submit_mission(self, metadata: MissionMetadata) -> SubmissionReceipt:
        """Register a mission. Returns a receipt with submission_id."""
        ...

    def submit_evaluation(
        self,
        policy_id: str,
        eval_id: str,
        score: float,
        artifact_hash: str,
    ) -> SubmissionReceipt:
        """Report an evaluation result. Returns a receipt."""
        ...

    def publish_proof(self, artifact: EvaluationArtifact) -> SubmissionReceipt:
        """Anchor a sealed evaluation artifact on-chain. Returns a receipt.

        Accepts only sealed EvaluationArtifact — never raw simulator state.
        """
        ...

    def query_rewards(self, policy_id: str) -> float:
        """Query pending KNX rewards for a policy. Returns reward amount."""
        ...

    def get_submission_status(self, submission_id: str) -> dict[str, object]:
        """Query submission status. Returns a JSON-shaped dict."""
        ...
