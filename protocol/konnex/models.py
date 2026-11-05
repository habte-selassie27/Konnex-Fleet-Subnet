"""Konnex-side data models — protocol-safe types only.

Boundary (docs/protocol.md, TESTING_PLAN.md §14):
Only these types may cross into `KonnexAdapter`:
    - `MissionMetadata`, `PolicyRegistration`, `EvaluationSubmission`
    - Primitives: `str`, `int`, `float`
This file must NEVER reference RobotState, Gazebo world handles, ROS 2 nodes,
or raw trajectories.

Status: COMPLETE (Phase 8) — types defined; live SDK calls remain STUB.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MissionMetadata:
    """Protocol-safe metadata describing a fleet mission."""

    mission_id: str
    policy_id: str
    scenario_id: str
    seed: int
    robot_count: int
    task_count: int
    env_version: str
    sim_version: str = ""
    submitted_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class PolicyRegistration:
    """Minimal policy data for on-chain registration."""

    policy_id: str
    policy_hash: str
    algorithm: str
    author: str


@dataclass(frozen=True)
class EvaluationSubmission:
    """Evaluation result for on-chain submission."""

    policy_id: str
    evaluation_id: str
    score: float
    artifact_hash: str


@dataclass(frozen=True)
class SubmissionReceipt:
    """Receipt returned by the Konnex network after a successful submission."""

    submission_id: str
    status: str
    tx_hash: str = ""
