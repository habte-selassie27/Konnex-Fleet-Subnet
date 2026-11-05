"""CostOptimizerAllocator — weighted multi-factor cost minimization.

Status: COMPLETE (Phase 5).
CostWeights (PLAN.md §7.3): distance 0.4, battery 0.2, priority 0.2,
congestion 0.1, collision_risk 0.1. All components normalized to [0, 1]
before weighting. Lower cost is better.
"""

from dataclasses import dataclass

from robotics.models.robot_state import RobotState
from robotics.models.task import Assignment, Task

_MAX_WORLD_DISTANCE = 50.0
_CONGESTION_RADIUS_M = 3.0


def _normalize(values: list[float]) -> list[float]:
    """Normalize a list of floats to [0, 1] range.

    Handles empty lists and constant lists (all same value).
    """
    if not values:
        return []
    min_val = min(values)
    max_val = max(values)
    spread = max_val - min_val
    if spread == 0:
        return [0.5] * len(values)
    return [(v - min_val) / spread for v in values]


@dataclass(frozen=True)
class CostWeights:
    """Normalized component weights; must sum to 1.0."""

    distance: float = 0.4
    battery: float = 0.2
    priority: float = 0.2
    congestion: float = 0.1
    collision_risk: float = 0.1


class CostOptimizerAllocator:
    """Assigns tasks minimizing a weighted multi-factor cost."""

    name = "cost_optimizer"

    def __init__(self, weights: CostWeights | None = None) -> None:
        self._weights = weights or CostWeights()

    def assign(self, robots: list[RobotState], tasks: list[Task]) -> list[Assignment]:
        """For each task (priority order), pick the robot with minimal cost."""
        available = [
            r
            for r in robots
            if r.current_task_id is None and r.comm_state == "online" and r.nav_state != "failed"
        ]
        pending = sorted(tasks, key=lambda t: (self._priority_rank(t), t.id))
        assignments: list[Assignment] = []
        used: set[str] = set()
        for task in pending:
            best: RobotState | None = None
            best_cost = float("inf")
            for robot in available:
                if robot.id in used:
                    continue
                cost = self.cost(robot, task, available)
                if cost < best_cost:
                    best_cost = cost
                    best = robot
            if best is None:
                break
            used.add(best.id)
            assignments.append(Assignment(robot_id=best.id, task_id=task.id, distance=best_cost))
        return assignments

    def cost(self, robot: RobotState, task: Task, fleet: list[RobotState]) -> float:
        """Weighted normalized cost; lower is better."""
        distance = min(1.0, robot.position.distance_to(task.pickup) / _MAX_WORLD_DISTANCE)
        battery = 1.0 - robot.battery_pct
        priority = self._priority_rank(task) / 2.0  # high -> 0.0 (best), low -> 1.0
        congestion = self._congestion(robot, fleet)
        collision_risk = 1.0 if robot.nav_state.value == "blocked" else 0.0
        w = self._weights
        return (
            w.distance * distance
            + w.battery * battery
            + w.priority * priority
            + w.congestion * congestion
            + w.collision_risk * collision_risk
        )

    @staticmethod
    def _priority_rank(task: Task) -> int:
        if task.priority.value == "high":
            return 0
        if task.priority.value == "medium":
            return 1
        return 2

    @staticmethod
    def _congestion(robot: RobotState, fleet: list[RobotState]) -> float:
        neighbors = sum(
            1
            for other in fleet
            if other.id != robot.id
            and other.position.distance_to(robot.position) < _CONGESTION_RADIUS_M
        )
        return min(1.0, neighbors / max(1, len(fleet)))
