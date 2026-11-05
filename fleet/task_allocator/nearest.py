"""NearestTaskAllocator — greedy: assign task to closest available robot.

Status: COMPLETE (Phase 5). Complexity O(R x T) (PLAN.md §7.2).
"""

from robotics.models.robot_state import RobotState
from robotics.models.task import Assignment, Task


class NearestTaskAllocator:
    """Greedy nearest-task assignment, highest priority first."""

    name = "nearest"

    def assign(self, robots: list[RobotState], tasks: list[Task]) -> list[Assignment]:
        """Assign each pending task to the closest available robot (capacity 1)."""
        available = [
            r
            for r in robots
            if r.current_task_id is None and r.comm_state == "online" and r.nav_state != "failed"
        ]
        pending = sorted(
            tasks,
            key=lambda t: (self._priority_rank(t), t.id),
        )
        assignments: list[Assignment] = []
        used: set[str] = set()
        for task in pending:
            best: RobotState | None = None
            best_distance = float("inf")
            for robot in available:
                if robot.id in used:
                    continue
                distance = robot.position.distance_to(task.pickup)
                if distance < best_distance:
                    best_distance = distance
                    best = robot
            if best is None:
                break
            used.add(best.id)
            assignments.append(
                Assignment(robot_id=best.id, task_id=task.id, distance=best_distance)
            )
        return assignments

    @staticmethod
    def _priority_rank(task: Task) -> int:
        if task.priority.value == "high":
            return 0
        if task.priority.value == "medium":
            return 1
        return 2
