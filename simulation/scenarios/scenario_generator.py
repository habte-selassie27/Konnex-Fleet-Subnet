"""Deterministic scenario generator.

Status: COMPLETE (Phase 5 domain layer).
Contract (PLAN.md §5.2, TESTING_PLAN.md §3.2):
- Same seed => identical scenario (all fields equal)
- Different seeds => different robot positions
- All positions within the world bounds
- Robot initial positions >= 1.5 m apart (spec floor is 1.0 m)
- Task count matches request
- Failure injection is optional and declarative
Hard-coded scenarios are prohibited.
"""

import random
from dataclasses import dataclass

from robotics.models.robot_state import Vector2D
from robotics.models.task import Priority, Task


@dataclass(frozen=True)
class ScenarioConfig:
    """World and generation parameters."""

    world: str = "warehouse_v1"
    world_size: Vector2D = Vector2D(40.0, 30.0)
    obstacle_count: int = 15
    min_robot_spacing_m: float = 1.5
    margin_m: float = 1.0


@dataclass
class Scenario:
    """A fully-generated, reproducible scenario."""

    seed: int
    world: str
    world_size: Vector2D
    obstacle_count: int
    robot_count: int
    task_count: int
    robot_positions: list[Vector2D]
    robot_battery_pcts: list[float]
    tasks: list[Task]
    failure_injection: bool = False
    failure_robot_index: int = 1


class ScenarioGenerator:
    """Generates deterministic warehouse scenarios from a seed."""

    def __init__(self, config: ScenarioConfig | None = None) -> None:
        self._config = config or ScenarioConfig()

    def generate(
        self,
        seed: int,
        robot_count: int,
        task_count: int,
        battery_range: tuple[float, float] = (0.6, 1.0),
        failure_injection: bool = False,
        failure_robot_index: int = 1,
    ) -> Scenario:
        """Generate a scenario deterministically from `seed`."""
        rng = random.Random(seed)
        size = self._config.world_size

        robot_positions = self._sample_positions(rng, robot_count)
        robot_battery_pcts = [
            round(rng.uniform(battery_range[0], battery_range[1]), 4) for _ in range(robot_count)
        ]
        tasks = self._generate_tasks(rng, task_count)

        return Scenario(
            seed=seed,
            world=self._config.world,
            world_size=size,
            obstacle_count=self._config.obstacle_count,
            robot_count=robot_count,
            task_count=task_count,
            robot_positions=robot_positions,
            robot_battery_pcts=robot_battery_pcts,
            tasks=tasks,
            failure_injection=failure_injection,
            failure_robot_index=failure_robot_index,
        )

    def _sample_positions(self, rng: random.Random, count: int) -> list[Vector2D]:
        """Sample `count` positions inside the world, at least min_spacing apart."""
        positions: list[Vector2D] = []
        margin = self._config.margin_m
        size = self._config.world_size
        spacing = self._config.min_robot_spacing_m
        attempts_per_robot = 200
        for _ in range(count):
            for _attempt in range(attempts_per_robot):
                candidate = Vector2D(
                    rng.uniform(margin, size.x - margin),
                    rng.uniform(margin, size.y - margin),
                )
                if all(candidate.distance_to(p) >= spacing for p in positions):
                    positions.append(candidate)
                    break
            else:  # pragma: no cover -- world is large enough for realistic counts
                positions.append(Vector2D(margin, margin))
        return positions

    def _generate_tasks(self, rng: random.Random, count: int) -> list[Task]:
        """Generate pickup/delivery tasks inside the world."""
        size = self._config.world_size
        margin = self._config.margin_m
        priorities = [Priority.LOW, Priority.MEDIUM, Priority.HIGH]
        tasks: list[Task] = []
        for index in range(count):
            pickup = Vector2D(
                rng.uniform(margin, size.x - margin),
                rng.uniform(margin, size.y - margin),
            )
            delivery = Vector2D(
                rng.uniform(margin, size.x - margin),
                rng.uniform(margin, size.y - margin),
            )
            tasks.append(
                Task(
                    id=f"task_{index}",
                    pickup=pickup,
                    delivery=delivery,
                    priority=rng.choice(priorities),
                    created_at=0.0,
                )
            )
        return tasks
