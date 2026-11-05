"""Tests for the ReproducibilityVerifier (Phase 6)."""

import hashlib

from fleet.task_allocator.nearest import NearestTaskAllocator
from validator.reproducibility.verifier import ReproducibilityVerifier
from validator.runner import ValidationRequest, ValidatorRunner
from validator.sandbox.executor import InProcessPolicyExecutor, PolicyEntry
from validator.sandbox.resource_limits import ResourceLimits


def _hash(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _request() -> ValidationRequest:
    return ValidationRequest(
        policy_id="nearest",
        policy_hash=_hash(b"nearest"),
        scenario_id="warehouse_v1_20tasks",
        seed=42,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
        resource_limits=ResourceLimits.default(),
    )


def test_verifier_agrees_for_deterministic_run() -> None:
    registry = {
        "nearest": PolicyEntry(weights=b"nearest", factory=NearestTaskAllocator),
    }
    runner_a = ValidatorRunner(InProcessPolicyExecutor(registry))
    runner_b = ValidatorRunner(InProcessPolicyExecutor(registry))

    result = ReproducibilityVerifier([runner_a, runner_b]).verify(_request())

    assert result.agreed is True
    assert result.spread <= 0.5
    assert result.status == "REPRODUCIBLE"
    assert len(result.scores) == 2
