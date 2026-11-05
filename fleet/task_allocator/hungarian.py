"""HungarianAllocator — optimal bipartite matching on the distance matrix.

Status: COMPLETE (Phase 5). Complexity O(R^3) (PLAN.md §7.2).
Cost matrix is never negative; empty fleet/task queue returns [].
"""

import numpy as np
from scipy.optimize import linear_sum_assignment

from robotics.models.robot_state import RobotState
from robotics.models.task import Assignment, Task


class HungarianAllocator:
    """Optimal robot-task assignment minimizing total pickup distance."""

    name = "hungarian"

    def assign(self, robots: list[RobotState], tasks: list[Task]) -> list[Assignment]:
        """Assign via linear_sum_assignment; handles rectangular matrices."""
        available = [
            r
            for r in robots
            if r.current_task_id is None and r.comm_state == "online" and r.nav_state != "failed"
        ]
        pending = tasks
        if not available or not pending:
            return []

        cost = np.zeros((len(available), len(pending)), dtype=float)
        for i, robot in enumerate(available):
            for j, task in enumerate(pending):
                cost[i, j] = robot.position.distance_to(task.pickup)

        row_ind, col_ind = linear_sum_assignment(cost)
        assignments: list[Assignment] = []
        for robot_idx, task_idx in zip(row_ind, col_ind, strict=True):
            assignments.append(
                Assignment(
                    robot_id=available[robot_idx].id,
                    task_id=pending[task_idx].id,
                    distance=float(cost[robot_idx, task_idx]),
                )
            )
        return assignments
