"""Konnex-aligned work measurement tests (validator/scoring/konnex.py).

Contract: safety is a hard gate (any violation -> 0), the weighted components
are normalized to [0, 1], weights default to our 0.50/0.30/0.20 estimate, and
reward splits never invent reward for zero-score work.

Status: COMPLETE (estimate model; not Konnex's official formula).
"""

from pathlib import Path

import pytest
import yaml

from validator.scoring.engine import MissionResult, PoPWScoringEngine
from validator.scoring.konnex import (
    KonnexWeights,
    competitive_split,
    reference_efficiency,
    winner_takes_most,
    work_score,
)


class TestKonnexWorkScore:
    def test_perfect_work_scores_one(self) -> None:
        score = work_score(task_match=1.0, efficiency=1.0, evidence_quality=1.0)
        assert score.safety_gate == 1
        assert score.final == 1.0
        assert score.weights == KonnexWeights()

    def test_default_weights_sum_to_one(self) -> None:
        weights = KonnexWeights()
        assert weights.task_match + weights.efficiency + weights.evidence_quality == 1.0
        assert weights.from_yaml().normalized() == weights

    def test_safety_violation_gates_the_whole_score(self) -> None:
        score = work_score(
            task_match=1.0,
            efficiency=1.0,
            evidence_quality=1.0,
            safety_violations=1,
        )
        assert score.safety_gate == 0
        assert score.final == 0.0
        assert score.safety_violations == 1

    def test_weighted_sum_matches_the_documented_formula(self) -> None:
        weights = KonnexWeights(task_match=0.5, efficiency=0.3, evidence_quality=0.2)
        score = work_score(
            task_match=0.8,
            efficiency=0.5,
            evidence_quality=0.5,
            weights=weights,
        )
        assert score.final == pytest.approx(0.5 * 0.8 + 0.3 * 0.5 + 0.2 * 0.5)

    def test_weights_are_normalized(self) -> None:
        weights = KonnexWeights(task_match=2.0, efficiency=1.0, evidence_quality=1.0).normalized()
        assert weights.task_match + weights.efficiency + weights.evidence_quality == pytest.approx(
            1.0
        )
        assert weights.task_match == pytest.approx(0.5)

    def test_components_are_clamped(self) -> None:
        score = work_score(task_match=2.0, efficiency=-1.0, evidence_quality=5.0)
        assert score.task_match == 1.0
        assert score.efficiency == 0.0
        assert score.evidence_quality == 1.0

    def test_from_yaml_reads_the_konnex_block(self, tmp_path: Path) -> None:
        path = tmp_path / "weights.yaml"
        path.write_text(
            yaml.safe_dump(
                {"konnex": {"task_match": 0.4, "efficiency": 0.4, "evidence_quality": 0.2}}
            )
        )
        weights = KonnexWeights.from_yaml(path)
        assert (weights.task_match, weights.efficiency, weights.evidence_quality) == (
            0.4,
            0.4,
            0.2,
        )

    def test_from_yaml_missing_file_falls_back(self, tmp_path: Path) -> None:
        assert KonnexWeights.from_yaml(tmp_path / "absent.yaml") == KonnexWeights()


class TestReferenceEfficiency:
    def test_halves_time_and_energy_ratios(self) -> None:
        assert reference_efficiency(t_ref=100, t_actual=200, e_ref=10, e_actual=10) == 0.75

    def test_ratios_are_capped_at_one(self) -> None:
        assert reference_efficiency(t_ref=200, t_actual=10, e_ref=50, e_actual=10) == 1.0

    def test_non_positive_measurements_contribute_zero(self) -> None:
        assert reference_efficiency(t_ref=100, t_actual=0, e_ref=10, e_actual=0) == 0.0


class TestRewardSplits:
    def test_competitive_split_is_proportional_and_conserves_reward(self) -> None:
        rewards = competitive_split([90.0, 10.0], task_reward=100.0)
        assert rewards == [90.0, 10.0]
        assert sum(rewards) == 100.0

    def test_competitive_split_pays_nothing_for_zero_work(self) -> None:
        assert competitive_split([0.0, 0.0], task_reward=100.0) == [0.0, 0.0]
        assert competitive_split([-5.0], task_reward=10.0) == [0.0]

    def test_competitive_split_rejects_negative_reward(self) -> None:
        with pytest.raises(ValueError):
            competitive_split([1.0], task_reward=-1.0)

    def test_winner_takes_most_pays_the_top_score(self) -> None:
        rewards = winner_takes_most([90.0, 10.0], task_reward=100.0, top_share=0.75)
        assert rewards[0] == pytest.approx(75.0)
        assert rewards[1] == pytest.approx(25.0)

    def test_winner_takes_most_leaves_unattributable_reward_unallocated(self) -> None:
        rewards = winner_takes_most([90.0, 0.0], task_reward=100.0, top_share=0.75)
        assert rewards == [pytest.approx(75.0), 0.0]

    def test_winner_takes_most_requires_a_valid_share(self) -> None:
        with pytest.raises(ValueError):
            winner_takes_most([1.0], task_reward=1.0, top_share=0.0)


class TestEngineKonnexScore:
    def test_engine_exposes_the_gated_score(self) -> None:
        score = PoPWScoringEngine().score(
            MissionResult(
                tasks_completed=10,
                tasks_total=10,
                elapsed_s=0.0,
                time_limit_s=600.0,
                collision_count=0,
                energy_consumed=0.0,
                energy_budget=500.0,
            )
        )
        assert score.konnex is not None
        assert score.konnex.safety_gate == 1
        assert score.konnex.final == 1.0

    def test_engine_gates_the_estimate_on_collisions(self) -> None:
        score = PoPWScoringEngine().score(
            MissionResult(
                tasks_completed=10,
                tasks_total=10,
                elapsed_s=0.0,
                time_limit_s=600.0,
                collision_count=1,
                energy_consumed=0.0,
                energy_budget=500.0,
            )
        )
        assert score.konnex is not None
        assert score.konnex.safety_gate == 0
        assert score.konnex.final == 0.0
        # The six-component prototype score is unchanged by the estimate.
        assert score.final == 97.0
