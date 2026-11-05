"""ValidatorRunner — executes policies reproducibly and scores outcomes.

Status: COMPLETE (Phase 6).
Validation statuses (SYSTEM_PROMPT.md §4.3 / BUILD.md §8):
COMPLETE, POLICY_CRASH, TIMEOUT, RESOURCE_EXCEEDED, INVALID_ACTIONS, UNSTABLE.
Failed statuses receive score 0.0; the validator never crashes with a bad policy.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Protocol, cast

import httpx

from robotics.models.telemetry import (
    CollisionEvent,
    EnergyEntry,
    TaskOutcome,
    TrajectoryFrame,
)
from validator.reproducibility.artifact import EvaluationArtifact
from validator.sandbox.resource_limits import ResourceLimits
from validator.scoring.engine import MissionResult, PoPWScore, PoPWScoringEngine


class PolicyError(Exception):
    """Raised for unknown policies or policy hash mismatches."""


@dataclass(frozen=True)
class ValidationRequest:
    """Everything a validator needs to reproduce an evaluation."""

    policy_id: str
    policy_hash: str
    scenario_id: str
    seed: int
    env_version: str
    sim_version: str
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits.default)


@dataclass(frozen=True)
class PolicyExecutionResult:
    """Raw result of executing a policy against an environment."""

    status: str
    tasks_completed: int
    tasks_total: int
    completion_time_s: float
    time_limit_s: float
    collision_count: int
    energy_consumed: float
    robot_count: int
    failure_count: int = 0
    task_outcomes: list[TaskOutcome] = field(default_factory=list)
    trajectory: list[TrajectoryFrame] = field(default_factory=list)
    collision_log: list[CollisionEvent] = field(default_factory=list)
    energy_log: list[EnergyEntry] = field(default_factory=list)
    error_message: str | None = None


class PolicyExecutor(Protocol):
    """Interface every policy executor (headless or Docker) implements."""

    def execute(self, request: ValidationRequest) -> PolicyExecutionResult:
        """Execute a policy; may raise PolicyError for hash/identity problems."""
        ...


@dataclass
class ValidationResult:
    """A completed validation with score and verifiable artifact."""

    request: ValidationRequest
    status: str
    score: PoPWScore
    evaluation_artifact: EvaluationArtifact
    completion_time_s: float
    trajectory: list[TrajectoryFrame] | None = None
    task_outcomes: list[TaskOutcome] | None = None
    energy_log: list[EnergyEntry] | None = None
    collision_log: list[CollisionEvent] | None = None
    failure_count: int = 0
    error_message: str | None = None


class ValidatorRunner:
    """Runs a validation request through an executor and produces a score."""

    def __init__(
        self,
        executor: PolicyExecutor,
        scoring_engine: PoPWScoringEngine | None = None,
        env_version: str = "v1.0.0",
        sim_version: str = "gazebo_harmonic",
    ) -> None:
        self._executor = executor
        self._scoring = scoring_engine or PoPWScoringEngine()
        self._env_version = env_version
        self._sim_version = sim_version

    def validate(self, request: ValidationRequest) -> ValidationResult:
        """Execute and score a validation request.

        Raises PolicyError for unknown policies or hash mismatches (rejected
        before execution). A failing policy never crashes the validator.
        """
        execution = self._executor.execute(request)

        if execution.status != "COMPLETE":
            score = self._zero_score()
            artifact = self._build_artifact(request, execution, score)
            return ValidationResult(
                request=request,
                status=execution.status,
                score=score,
                evaluation_artifact=artifact,
                completion_time_s=execution.completion_time_s,
                trajectory=execution.trajectory,
                task_outcomes=execution.task_outcomes,
                energy_log=execution.energy_log,
                collision_log=execution.collision_log,
                failure_count=execution.failure_count,
                error_message=execution.error_message,
            )

        mission_result = MissionResult(
            tasks_completed=execution.tasks_completed,
            tasks_total=execution.tasks_total,
            elapsed_s=execution.completion_time_s,
            time_limit_s=execution.time_limit_s,
            collision_count=execution.collision_count,
            energy_consumed=execution.energy_consumed,
            energy_budget=execution.robot_count * 100.0,
            failure_count=execution.failure_count,
        )
        score = self._scoring.score(mission_result)
        artifact = self._build_artifact(request, execution, score)
        return ValidationResult(
            request=request,
            status=execution.status,
            score=score,
            evaluation_artifact=artifact,
            completion_time_s=execution.completion_time_s,
            trajectory=execution.trajectory,
            task_outcomes=execution.task_outcomes,
            energy_log=execution.energy_log,
            collision_log=execution.collision_log,
            failure_count=execution.failure_count,
        )

    def _zero_score(self) -> PoPWScore:
        weights = self._scoring.weights
        return PoPWScore(
            mission_success=0.0,
            safety=0.0,
            efficiency=0.0,
            energy=0.0,
            coordination=0.0,
            robustness=0.0,
            final=0.0,
            weights=weights,
        )

    def _build_artifact(
        self, request: ValidationRequest, execution: PolicyExecutionResult, score: PoPWScore
    ) -> EvaluationArtifact:
        artifact = EvaluationArtifact(
            policy_id=request.policy_id,
            policy_hash=request.policy_hash,
            scenario_id=request.scenario_id,
            seed=request.seed,
            env_version=request.env_version,
            sim_version=request.sim_version,
            score_components={
                "mission_success": score.mission_success,
                "safety": score.safety,
                "efficiency": score.efficiency,
                "energy": score.energy,
                "coordination": score.coordination,
                "robustness": score.robustness,
            },
            final_score=score.final,
            completion_time_s=execution.completion_time_s,
            collision_count=execution.collision_count,
            tasks_completed=execution.tasks_completed,
            tasks_total=execution.tasks_total,
            energy_consumed=execution.energy_consumed,
            timestamp=time.time(),
        )
        return artifact.seal()


async def post_evaluation_result(
    api_url: str, api_key: str, result: ValidationResult
) -> dict[str, object]:
    """POST a validation result to the backend evaluations API."""
    payload = {
        "policy_id": result.request.policy_id,
        "policy_hash": result.request.policy_hash,
        "scenario_id": result.request.scenario_id,
        "seed": result.request.seed,
        "env_version": result.request.env_version,
        "sim_version": result.request.sim_version,
        "status": result.status,
        "final_score": result.score.final,
        "artifact_hash": result.evaluation_artifact.artifact_hash,
        "artifact": json.loads(result.evaluation_artifact.to_json()),
    }
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.post(
            f"{api_url.rstrip('/')}/api/v1/evaluations/",
            json=payload,
            headers={"X-Fleet-API-Key": api_key},
        )
        response.raise_for_status()
        return cast(dict[str, object], response.json())
