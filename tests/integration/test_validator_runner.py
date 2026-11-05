"""ValidatorRunner integration tests — Phase 6 gates.

Gates (Phase 6 task spec):
- same (policy_id, policy_hash, scenario_id, seed) -> |score1 - score2| <= 0.5
- crashed policy -> POLICY_CRASH, score 0.0, validator does not crash
- evaluation artifact is verifiable (canonical SHA-256)
- two independent validator instances agree within tolerance
Plus: TIMEOUT / RESOURCE_EXCEEDED / INVALID_ACTIONS -> score 0.0, and policy
hash verification rejects mismatches before execution.

Status: COMPLETE (Phase 6, in-process deterministic executor).
"""

import hashlib

import pytest

from fleet.task_allocator.base import TaskAllocator
from fleet.task_allocator.cost_optimizer import CostOptimizerAllocator
from fleet.task_allocator.hungarian import HungarianAllocator
from fleet.task_allocator.nearest import NearestTaskAllocator
from robotics.models.robot_state import RobotState
from robotics.models.task import Assignment, Task
from validator.reproducibility.artifact import EvaluationArtifact
from validator.runner import PolicyError, ValidationRequest, ValidatorRunner
from validator.sandbox.executor import (
    InProcessPolicyExecutor,
    PolicyEntry,
    PolicyExecutionError,
    ResourceExceededError,
)
from validator.sandbox.resource_limits import ResourceLimits

NEAREST_WEIGHTS = b"nearest-policy-weights-v1"
HUNGARIAN_WEIGHTS = b"hungarian-policy-weights-v1"
COST_WEIGHTS = b"cost-optimizer-policy-weights-v1"


def weights_hash(weights: bytes) -> str:
    """SHA-256 hex digest of policy weights."""
    return hashlib.sha256(weights).hexdigest()


def make_registry(extra: dict[str, PolicyEntry] | None = None) -> dict[str, PolicyEntry]:
    """Build the policy registry with the three baseline policies."""
    registry: dict[str, PolicyEntry] = {
        "nearest": PolicyEntry(weights=NEAREST_WEIGHTS, factory=NearestTaskAllocator),
        "hungarian": PolicyEntry(weights=HUNGARIAN_WEIGHTS, factory=HungarianAllocator),
        "cost_optimizer": PolicyEntry(weights=COST_WEIGHTS, factory=CostOptimizerAllocator),
    }
    if extra:
        registry.update(extra)
    return registry


def make_request(
    policy_id: str = "nearest",
    policy_hash: str | None = None,
    seed: int = 42,
    limits: ResourceLimits | None = None,
) -> ValidationRequest:
    """Build a validation request for the nearest policy by default."""
    return ValidationRequest(
        policy_id=policy_id,
        policy_hash=policy_hash or weights_hash(NEAREST_WEIGHTS),
        scenario_id="warehouse_v1_20tasks",
        seed=seed,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
        resource_limits=limits or ResourceLimits.default(),
    )


def make_runner(registry: dict[str, PolicyEntry] | None = None) -> ValidatorRunner:
    """Build a validator backed by a fresh in-process executor."""
    return ValidatorRunner(InProcessPolicyExecutor(registry or make_registry()))


class DoNothingPolicy:
    """A policy that never returns assignments (the mission times out)."""

    name = "do_nothing"

    def assign(self, _robots: list[RobotState], _tasks: list[Task]) -> list[Assignment]:
        return []


class ResourceHungryPolicy:
    """A policy that exceeds the sandbox resource limits while executing."""

    name = "resource_hungry"

    def assign(self, _robots: list[RobotState], _tasks: list[Task]) -> list[Assignment]:
        raise ResourceExceededError("memory limit exceeded")


class GhostAssignerPolicy:
    """A policy returning assignments for robots that do not exist."""

    name = "ghost"

    def assign(self, _robots: list[RobotState], _tasks: list[Task]) -> list[Assignment]:
        return [Assignment(robot_id="ghost_robot", task_id="task_0")]


class TestReproducibility:
    def test_same_policy_and_seed_produces_same_score(self) -> None:
        runner = make_runner()
        request = make_request()
        first = runner.validate(request)
        second = runner.validate(request)
        assert first.status == "COMPLETE"
        assert abs(first.score.final - second.score.final) <= 0.5
        # Substantive artifact fields are identical (hashes differ only by the
        # per-evaluation timestamp, which is by design).
        assert first.evaluation_artifact.final_score == second.evaluation_artifact.final_score
        assert first.completion_time_s == second.completion_time_s

    def test_two_validators_agree_within_tolerance(self) -> None:
        runner_a = make_runner(make_registry())
        runner_b = make_runner(make_registry())
        request = make_request()
        result_a = runner_a.validate(request)
        result_b = runner_b.validate(request)
        assert result_a.status == result_b.status == "COMPLETE"
        assert abs(result_a.score.final - result_b.score.final) <= 0.5

    def test_different_seed_yields_different_outcome(self) -> None:
        runner = make_runner()
        first = runner.validate(make_request(seed=42))
        second = runner.validate(make_request(seed=43))
        assert first.status == "COMPLETE"
        assert second.status == "COMPLETE"
        assert (first.completion_time_s, first.evaluation_artifact.final_score) != (
            second.completion_time_s,
            second.evaluation_artifact.final_score,
        )


class TestFailedPolicies:
    def _crash_factory(self) -> TaskAllocator:
        raise PolicyExecutionError("simulated crash during policy construction")

    def test_crashed_policy_returns_zero_score(self) -> None:
        registry = make_registry(
            {"crashy": PolicyEntry(weights=b"crashy", factory=self._crash_factory)}
        )
        result = make_runner(registry).validate(
            make_request(policy_id="crashy", policy_hash=weights_hash(b"crashy"))
        )
        assert result.status == "POLICY_CRASH"
        assert result.score.final == 0.0
        assert result.error_message is not None

    def test_timeout_policy_returns_zero_score(self) -> None:
        registry = make_registry(
            {"do_nothing": PolicyEntry(weights=b"do_nothing", factory=DoNothingPolicy)}
        )
        request = make_request(
            policy_id="do_nothing",
            policy_hash=weights_hash(b"do_nothing"),
            limits=ResourceLimits(timeout_s=5.0),
        )
        result = make_runner(registry).validate(request)
        assert result.status == "TIMEOUT"
        assert result.score.final == 0.0

    def test_resource_exceeded_policy_returns_zero_score(self) -> None:
        registry = make_registry(
            {"hungry": PolicyEntry(weights=b"hungry", factory=ResourceHungryPolicy)}
        )
        result = make_runner(registry).validate(
            make_request(policy_id="hungry", policy_hash=weights_hash(b"hungry"))
        )
        assert result.status == "RESOURCE_EXCEEDED"
        assert result.score.final == 0.0

    def test_invalid_actions_policy_returns_zero_score(self) -> None:
        registry = make_registry(
            {"ghost": PolicyEntry(weights=b"ghost", factory=GhostAssignerPolicy)}
        )
        result = make_runner(registry).validate(
            make_request(policy_id="ghost", policy_hash=weights_hash(b"ghost"))
        )
        assert result.status == "INVALID_ACTIONS"
        assert result.score.final == 0.0


class TestArtifactVerification:
    def test_evaluation_artifact_verifiable(self) -> None:
        result = make_runner().validate(make_request())
        artifact = result.evaluation_artifact
        assert artifact.artifact_hash == artifact.compute_hash()
        loaded = EvaluationArtifact.from_json(artifact.to_json())
        assert loaded.artifact_hash == artifact.artifact_hash
        assert loaded.compute_hash() == artifact.artifact_hash
        loaded.final_score = 0.0  # tamper
        assert loaded.compute_hash() != artifact.artifact_hash


class TestArtifactMatchesScoringEngine:
    """The published artifact must be exactly what the scoring engine produced.

    Phase 7 gate: an artifact that cannot be re-derived from its own components
    and the published weights is not a proof of anything.
    """

    COMPONENTS = (
        "mission_success",
        "safety",
        "efficiency",
        "energy",
        "coordination",
        "robustness",
    )

    def test_components_match_engine_output(self) -> None:
        result = make_runner().validate(make_request())
        artifact = result.evaluation_artifact
        assert set(artifact.score_components) == set(self.COMPONENTS)
        for name in self.COMPONENTS:
            assert artifact.score_components[name] == getattr(result.score, name)
        assert artifact.final_score == result.score.final

    def test_final_score_re_derives_from_published_components(self) -> None:
        result = make_runner().validate(make_request())
        artifact = result.evaluation_artifact
        weights = result.score.weights
        recomputed = 100.0 * sum(
            getattr(weights, name) * artifact.score_components[name] for name in self.COMPONENTS
        )
        assert abs(recomputed - artifact.final_score) <= 0.01

    def test_artifact_is_reproducible_across_independent_validators(self) -> None:
        request = make_request()
        first = make_runner().validate(request).evaluation_artifact
        second = make_runner().validate(request).evaluation_artifact
        # Timestamps differ by design (replay protection); every scored field
        # and the derived identity fields must be identical.
        for name in (
            "policy_id",
            "policy_hash",
            "scenario_id",
            "seed",
            "env_version",
            "sim_version",
            "score_components",
            "final_score",
            "completion_time_s",
            "collision_count",
            "tasks_completed",
            "tasks_total",
            "energy_consumed",
        ):
            assert getattr(first, name) == getattr(second, name), name
        assert first.verify() and second.verify()


class TestHashVerification:
    def test_hash_mismatch_rejected_before_execution(self) -> None:
        with pytest.raises(PolicyError):
            make_runner().validate(make_request(policy_hash="deadbeef" * 4))

    def test_unknown_policy_rejected(self) -> None:
        with pytest.raises(PolicyError):
            make_runner().validate(
                make_request(policy_id="missing", policy_hash=weights_hash(b"missing"))
            )
