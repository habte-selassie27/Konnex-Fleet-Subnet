"""Tests for multi-validator disagreement handling.

A disputed validator set must never publish a score. Two failure modes are
covered: scores that diverge beyond tolerance, and too few validators producing
a usable result at all.
"""

from __future__ import annotations

import pytest

from validator.consensus import (
    CONSENSUS_TOLERANCE,
    ConsensusRequest,
    ConsensusValidator,
)
from validator.runner import PolicyExecutionResult, ValidatorRunner


class _FixedExecutor:
    """Executor returning a fixed mission outcome (no simulation)."""

    def __init__(self, tasks_completed: int, status: str = "COMPLETE") -> None:
        self._completed = tasks_completed
        self._status = status

    def execute(self, request: object) -> PolicyExecutionResult:
        del request
        return PolicyExecutionResult(
            status=self._status,
            tasks_completed=self._completed,
            tasks_total=20,
            completion_time_s=300.0,
            time_limit_s=600.0,
            collision_count=0,
            energy_consumed=10.0,
            robot_count=5,
            failure_count=0,
        )


def _request(seed: int = 42) -> ConsensusRequest:
    return ConsensusRequest(
        policy_id="probe",
        policy_hash="a" * 64,
        scenario_id="warehouse_v1_20tasks",
        seed=seed,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
    )


def _runner(completed: int, status: str = "COMPLETE") -> ValidatorRunner:
    return ValidatorRunner(_FixedExecutor(completed, status))


def test_divergent_scores_produce_a_dispute() -> None:
    consensus = ConsensusValidator([_runner(20), _runner(10)])
    result = consensus.validate(_request())

    assert result.agreed is False
    assert result.status == "DISPUTE"
    assert result.score_spread > CONSENSUS_TOLERANCE
    assert result.rejection_reason is not None
    assert "spread" in result.rejection_reason


def test_dispute_is_rejected_not_published() -> None:
    consensus = ConsensusValidator([_runner(20), _runner(10)])

    assert consensus.resolve(_request()) is None


def test_agreement_publishes_the_result() -> None:
    consensus = ConsensusValidator([_runner(20), _runner(20)])
    result = consensus.validate(_request())

    assert result.accepted is True
    assert result.rejection_reason is None
    assert consensus.resolve(_request()) is not None


def test_single_complete_validator_is_not_enough() -> None:
    consensus = ConsensusValidator([_runner(20), _runner(0, status="TIMEOUT")])
    result = consensus.validate(_request())

    assert result.agreed is False
    assert result.agreement_count == 1
    assert result.rejection_reason is not None
    assert "at least 2" in result.rejection_reason
    assert consensus.resolve(_request()) is None


def test_requires_two_validators() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        ConsensusValidator([_runner(20)])
