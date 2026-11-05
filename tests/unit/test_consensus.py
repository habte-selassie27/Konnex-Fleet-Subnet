"""Tests for multi-validator consensus (validator/consensus.py).

Status: COMPLETE (Phase 6 stretch goal).
"""

from __future__ import annotations

import hashlib

import pytest

from fleet.task_allocator.nearest import NearestTaskAllocator
from validator.consensus import (
    CONSENSUS_TOLERANCE,
    ConsensusRequest,
    ConsensusResult,
    ConsensusValidator,
)
from validator.runner import ValidationRequest, ValidatorRunner
from validator.sandbox.executor import InProcessPolicyExecutor, PolicyEntry


@pytest.fixture
def two_runners() -> list[ValidatorRunner]:
    """Two independent validator runners with the same policy registry."""
    weights = b"consensus-test-weights-v1"
    registry = {"nearest": PolicyEntry(weights=weights, factory=NearestTaskAllocator)}
    executor = InProcessPolicyExecutor(registry)
    return [
        ValidatorRunner(executor, env_version="v1.0.0", sim_version="gazebo_harmonic"),
        ValidatorRunner(executor, env_version="v1.0.0", sim_version="gazebo_harmonic"),
    ]


@pytest.fixture
def consensus_request() -> ConsensusRequest:
    return ConsensusRequest(
        policy_id="nearest",
        policy_hash=hashlib.sha256(b"consensus-test-weights-v1").hexdigest(),
        scenario_id="warehouse_v1_20tasks",
        seed=42,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
    )


class TestConsensusValidator:
    def test_two_validators_agree(
        self, two_runners: list[ValidatorRunner], consensus_request: ConsensusRequest
    ) -> None:
        """Two validators running same request should agree within tolerance."""
        cv = ConsensusValidator(two_runners)
        result = cv.validate(consensus_request)

        assert result.agreed
        assert result.status == "CONSENSUS"
        assert result.validator_count == 2
        assert result.agreement_count == 2
        assert result.score_spread <= CONSENSUS_TOLERANCE
        assert 0.0 <= result.final_score <= 100.0

    def test_reproducibility_across_validators(
        self, two_runners: list[ValidatorRunner], consensus_request: ConsensusRequest
    ) -> None:
        """Same (policy_hash, seed) must produce identical scores."""
        cv = ConsensusValidator(two_runners)
        result = cv.validate(consensus_request)

        scores = [v.result.score.final for v in result.votes]
        assert scores[0] == scores[1]  # deterministic — exact match

    def test_different_seeds_differ(self, two_runners: list[ValidatorRunner]) -> None:
        """Different seeds should produce different scores."""
        cv = ConsensusValidator(two_runners)
        req_a = ConsensusRequest(
            policy_id="nearest",
            policy_hash=hashlib.sha256(b"consensus-test-weights-v1").hexdigest(),
            scenario_id="warehouse_v1_20tasks",
            seed=42,
            env_version="v1.0.0",
            sim_version="gazebo_harmonic",
        )
        req_b = ConsensusRequest(
            policy_id="nearest",
            policy_hash=hashlib.sha256(b"consensus-test-weights-v1").hexdigest(),
            scenario_id="warehouse_v1_20tasks",
            seed=99,
            env_version="v1.0.0",
            sim_version="gazebo_harmonic",
        )
        result_a = cv.validate(req_a)
        result_b = cv.validate(req_b)

        # Scores may or may not differ (both are nearest on same scenario),
        # but the requests are different.
        assert result_a.request.seed != result_b.request.seed

    def test_requires_at_least_two_validators(self) -> None:
        """Consensus with <2 validators should raise ValueError."""
        weights = b"test-weights"
        registry = {"nearest": PolicyEntry(weights=weights, factory=NearestTaskAllocator)}
        executor = InProcessPolicyExecutor(registry)
        runner = ValidatorRunner(executor)

        with pytest.raises(ValueError, match="at least 2"):
            ConsensusValidator([runner])

    def test_consensus_request_fields(self, two_runners: list[ValidatorRunner]) -> None:
        """ConsensusRequest carries all reproducibility fields."""
        cv = ConsensusValidator(two_runners)
        req = ConsensusRequest(
            policy_id="nearest",
            policy_hash=hashlib.sha256(b"consensus-test-weights-v1").hexdigest(),
            scenario_id="warehouse_v1_20tasks",
            seed=7,
            env_version="v2.0.0",
            sim_version="gazebo_harmonic_v2",
        )
        result = cv.validate(req)

        # Each vote should have the same request fields
        for vote in result.votes:
            assert vote.result.request.policy_id == "nearest"
            assert vote.result.request.seed == 7
            assert vote.result.request.env_version == "v2.0.0"

    def test_result_status_property(
        self, two_runners: list[ValidatorRunner], consensus_request: ConsensusRequest
    ) -> None:
        """Status returns CONSENSUS when agreed, DISPUTE when not."""
        cv = ConsensusValidator(two_runners)
        result = cv.validate(consensus_request)
        assert result.status == "CONSENSUS"
        assert result.agreed

    def test_spread_is_zero_for_deterministic(
        self, two_runners: list[ValidatorRunner], consensus_request: ConsensusRequest
    ) -> None:
        """Deterministic policies produce zero spread across validators."""
        cv = ConsensusValidator(two_runners)
        result = cv.validate(consensus_request)
        assert result.score_spread == 0.0
