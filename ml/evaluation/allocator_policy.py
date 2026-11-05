"""Score classical TaskAllocators inside FleetEnv (unified cross-harness run).

Background
----------
The MAPPO policy emits continuous waypoints, while `nearest` / `hungarian` /
`cost_optimizer` are `TaskAllocator` implementations that decide *which task a
robot should chase*. Comparing them used to require two simulators (the
orchestrator for allocators, FleetEnv for the learned policy), so every
"MAPPO beats Hungarian" claim carried a cross-harness caveat.

This module removes the caveat. It plugs an allocator into FleetEnv through
the environment's assignment-provider seam (`FleetEnv.set_assignment_provider`)
and drives the robots with the same waypoint controller the expert and MAPPO
use. Every policy is therefore scored by one simulator, one controller, one
PoPW engine and one seed set.

Layer rule: this module imports `fleet` (allocators) and `robotics` (domain
models), which is allowed for an evaluation harness. It is never imported by
`ml/env`, so the environment itself keeps zero coupling to the fleet layer.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

from fleet.task_allocator.base import TaskAllocator
from ml.env.assignment import PRIORITY_HIGH, PRIORITY_LOW, RobotView, TaskView
from ml.env.fleet_env import FleetEnv
from robotics.models.robot_state import NavState, RobotState, Vector2D
from robotics.models.task import Priority, Task, TaskStatus

NDArray = npt.NDArray[np.float32]

_PRIORITY_BY_RANK: dict[int, Priority] = {
    PRIORITY_HIGH: Priority.HIGH,
    PRIORITY_LOW: Priority.LOW,
}
_DEFAULT_PRIORITY = Priority.MEDIUM


def _to_domain_robot(view: RobotView) -> RobotState:
    """Adapt an environment RobotView to the shared RobotState contract."""
    return RobotState(
        id=view.id,
        position=Vector2D(view.x, view.y),
        battery_pct=view.battery_pct,
        nav_state=NavState.IDLE,
    )


def _to_domain_task(view: TaskView) -> Task:
    """Adapt an environment TaskView to the shared Task contract."""
    return Task(
        id=view.id,
        pickup=Vector2D(view.pickup_x, view.pickup_y),
        delivery=Vector2D(view.delivery_x, view.delivery_y),
        priority=_PRIORITY_BY_RANK.get(view.priority, _DEFAULT_PRIORITY),
        status=TaskStatus.PENDING,
    )


class AllocatorPolicy:
    """TaskAllocator adapted to FleetEnv's assignment-provider contract.

    The allocator chooses assignments; the environment's own waypoint/task
    controller does the driving. That is the same split the orchestrator uses,
    so results are comparable with the classical benchmark and with MAPPO.
    """

    def __init__(self, allocator: TaskAllocator) -> None:
        self._allocator = allocator

    @property
    def name(self) -> str:
        """Allocator name (used as the benchmark policy label)."""
        return self._allocator.name

    def provider(
        self, robots: Sequence[RobotView], tasks: Sequence[TaskView]
    ) -> list[tuple[str, str]]:
        """Return (robot_id, task_id) pairs for the environment tick."""
        if not robots or not tasks:
            return []
        assignments = self._allocator.assign(
            [_to_domain_robot(robot) for robot in robots],
            [_to_domain_task(task) for task in tasks],
        )
        return [(assignment.robot_id, assignment.task_id) for assignment in assignments]

    def __call__(
        self, robots: Sequence[RobotView], tasks: Sequence[TaskView]
    ) -> list[tuple[str, str]]:
        return self.provider(robots, tasks)


def allocator_action_fn() -> Callable[[FleetEnv, dict[str, Any]], dict[str, NDArray]]:
    """Action function that follows the robot's assigned task waypoint.

    The allocator has already picked the task via the assignment provider, so
    the action is simply the vector toward that task's current target — the
    identical convention used by the expert baseline and learned by MAPPO.
    """

    def act(env: FleetEnv, observations: dict[str, Any]) -> dict[str, NDArray]:
        return {agent_id: env.target_vector(agent_id) for agent_id in observations}

    return act


def mappo_action_fn(agent: Any) -> Callable[[FleetEnv, dict[str, Any]], dict[str, NDArray]]:
    """Action function backed by a trained MAPPO actor (flattened observations)."""
    from ml.env.encoding import flatten_obs

    def act(env: FleetEnv, observations: dict[str, Any]) -> dict[str, NDArray]:
        del env
        return {
            agent_id: agent.act(flatten_obs(obs), deterministic=True)
            for agent_id, obs in observations.items()
        }

    return act


def expert_action_fn() -> Callable[[FleetEnv, dict[str, Any]], dict[str, NDArray]]:
    """Action function for the heuristic expert baseline (greedy task-seeker)."""
    from ml.training.bc_pretrain import expert_action

    def act(env: FleetEnv, observations: dict[str, Any]) -> dict[str, NDArray]:
        del env
        return {agent_id: expert_action(obs) for agent_id, obs in observations.items()}

    return act


def zero_action(agent_count: int) -> dict[str, NDArray]:
    """Neutral action dict (used by tests)."""
    return {f"robot_{i}": np.zeros(2, dtype=np.float32) for i in range(agent_count)}
