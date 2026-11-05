"""TaskAllocator Protocol — all allocators implement this interface.

Status: COMPLETE (Phase 5).
Contract (BUILD.md §5):
- `name` identifies the policy for benchmarking/artifacts.
- `assign` returns one Assignment per available robot.
- Must not modify input lists.
- Must handle tasks < robots and robots < tasks.
"""

from typing import Protocol

from robotics.models.robot_state import RobotState
from robotics.models.task import Assignment, Task


class TaskAllocator(Protocol):
    """Policy interface implemented by every allocator."""

    name: str

    def assign(self, robots: list[RobotState], tasks: list[Task]) -> list[Assignment]:
        """Assign available robots to pending tasks.

        Returns one Assignment per assignment made. Must not modify the input
        lists and must handle both tasks < robots and robots < tasks.
        """
        ...
