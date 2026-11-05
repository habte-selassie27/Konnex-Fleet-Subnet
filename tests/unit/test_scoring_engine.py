"""PoPW scoring engine unit tests (TESTING_PLAN.md §3.4, Phase 6).

Contract: every component normalized to [0, 1]; final score in [0, 100];
weights sum to 1.0; a perfect mission scores 100.

Status: COMPLETE (Phase 6).
"""

from validator.scoring.engine import MissionResult, PoPWScoringEngine, ScoringWeights


def make_result(
    completed: int = 10,
    total: int = 10,
    elapsed_s: float = 0.0,
    time_limit_s: float = 600.0,
    collisions: int = 0,
    energy: float = 0.0,
    energy_budget: float = 500.0,
    failures: int = 0,
) -> MissionResult:
    """Build a MissionResult with sensible defaults for a full-score mission."""
    return MissionResult(
        tasks_completed=completed,
        tasks_total=total,
        elapsed_s=elapsed_s,
        time_limit_s=time_limit_s,
        collision_count=collisions,
        energy_consumed=energy,
        energy_budget=energy_budget,
        failure_count=failures,
    )


class TestPoPWScoringEngine:
    def test_perfect_mission_scores_100(self) -> None:
        score = PoPWScoringEngine().score(make_result())
        assert score.final == 100.0
        assert score.mission_success == 1.0
        assert score.safety == 1.0

    def test_partial_completion_reduces_success(self) -> None:
        score = PoPWScoringEngine().score(make_result(completed=5, total=10))
        assert score.mission_success == 0.5

    def test_collisions_reduce_safety_and_coordination(self) -> None:
        score = PoPWScoringEngine().score(make_result(collisions=5))
        assert score.safety == 0.5
        assert score.coordination == 0.5

    def test_elapsed_time_reduces_efficiency(self) -> None:
        score = PoPWScoringEngine().score(make_result(elapsed_s=300.0, time_limit_s=600.0))
        assert score.efficiency == 0.5

    def test_energy_over_budget_floor_at_zero(self) -> None:
        score = PoPWScoringEngine().score(make_result(energy=600.0, energy_budget=500.0))
        assert score.energy == 0.0

    def test_robustness_penalized_under_failures(self) -> None:
        score = PoPWScoringEngine().score(make_result(completed=8, total=10, failures=3))
        assert score.robustness == 0.8  # robustness = mission_success under failure

    def test_components_normalized_under_degradation(self) -> None:
        score = PoPWScoringEngine().score(
            make_result(
                completed=4,
                total=10,
                elapsed_s=580.0,
                collisions=9,
                energy=490.0,
                failures=2,
            )
        )
        for component in (
            score.mission_success,
            score.safety,
            score.efficiency,
            score.energy,
            score.coordination,
            score.robustness,
        ):
            assert 0.0 <= component <= 1.0
        assert 0.0 <= score.final <= 100.0

    def test_weights_sum_to_one(self) -> None:
        weights = ScoringWeights()
        total = (
            weights.mission_success
            + weights.safety
            + weights.efficiency
            + weights.energy
            + weights.coordination
            + weights.robustness
        )
        assert total == 1.0

    def test_zero_tasks_zero_mission_success(self) -> None:
        score = PoPWScoringEngine().score(make_result(completed=0, total=0))
        assert score.mission_success == 0.0
