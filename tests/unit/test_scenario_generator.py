"""Scenario generator unit tests (TESTING_PLAN.md §3.2, Phase 5).

Contract: same seed => identical scenario; positions in bounds with minimum
spacing; task count honored; battery range honored; no hard-coded scenarios.

Status: COMPLETE (Phase 5).
"""

from simulation.scenarios.scenario_generator import ScenarioGenerator


class TestScenarioGenerator:
    def test_same_seed_identical_scenario(self) -> None:
        generator = ScenarioGenerator()
        first = generator.generate(seed=42, robot_count=5, task_count=10)
        second = generator.generate(seed=42, robot_count=5, task_count=10)
        assert first.robot_positions == second.robot_positions
        assert first.robot_battery_pcts == second.robot_battery_pcts
        assert first.tasks == second.tasks

    def test_different_seeds_differ(self) -> None:
        generator = ScenarioGenerator()
        first = generator.generate(seed=42, robot_count=5, task_count=10)
        second = generator.generate(seed=99, robot_count=5, task_count=10)
        assert first.robot_positions != second.robot_positions

    def test_positions_within_bounds(self) -> None:
        scenario = ScenarioGenerator().generate(seed=1, robot_count=5, task_count=10)
        for position in scenario.robot_positions:
            assert 1.0 <= position.x <= 39.0
            assert 1.0 <= position.y <= 29.0

    def test_minimum_robot_spacing(self) -> None:
        positions = (
            ScenarioGenerator().generate(seed=1, robot_count=5, task_count=10).robot_positions
        )
        for index, position in enumerate(positions):
            for other in positions[index + 1 :]:
                assert position.distance_to(other) >= 1.5 - 1e-9

    def test_task_count_honored(self) -> None:
        scenario = ScenarioGenerator().generate(seed=3, robot_count=5, task_count=12)
        assert scenario.task_count == 12
        assert len(scenario.tasks) == 12
        assert all(task.id == f"task_{index}" for index, task in enumerate(scenario.tasks))

    def test_battery_range_honored(self) -> None:
        scenario = ScenarioGenerator().generate(
            seed=5, robot_count=5, task_count=10, battery_range=(0.3, 0.4)
        )
        assert all(0.3 <= pct <= 0.4 for pct in scenario.robot_battery_pcts)

    def test_failure_injection_flags(self) -> None:
        scenario = ScenarioGenerator().generate(
            seed=5,
            robot_count=5,
            task_count=10,
            failure_injection=True,
            failure_robot_index=2,
        )
        assert scenario.failure_injection is True
        assert scenario.failure_robot_index == 2

    def test_generator_instances_are_equivalent(self) -> None:
        first = ScenarioGenerator().generate(seed=42, robot_count=5, task_count=10)
        second = ScenarioGenerator().generate(seed=42, robot_count=5, task_count=10)
        assert first.robot_positions == second.robot_positions
        assert first.tasks == second.tasks
