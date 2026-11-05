"""Assignment-provider contract for FleetEnv (harness-only task allocation).

Why this exists
---------------
FleetEnv assigns tasks to robots internally with a greedy nearest-pickup rule.
That is fine for training, but it makes the environment unable to compare
*allocation strategies*: whichever policy you run, the env still hands out
tasks the same way. To benchmark nearest / hungarian / cost_optimizer inside
the same simulator as the learned policy, the env needs a seam that lets the
*harness* decide assignments.

The seam is deliberately simulator-agnostic and free of `fleet`/`robotics`
imports so `ml/` keeps no dependency on the orchestration layer:

    provider(robots, tasks) -> [(robot_id, task_id), ...]

`RobotView` / `TaskView` are read-only snapshots of the environment's internal
state. They carry no observers in agent observations, so installing a provider
cannot leak global state into a trained policy: the provider is a benchmark
tool, not part of the agent's observation space.

Status: COMPLETE (unified cross-harness benchmark).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

# Task priority as an integer rank, matching FleetEnv's internal encoding
# (0 = high, 1 = medium, 2 = low). Kept as an int so this module has no
# dependency on any domain enum.
PRIORITY_HIGH = 0
PRIORITY_MEDIUM = 1
PRIORITY_LOW = 2


@dataclass(frozen=True)
class RobotView:
    """Environment robot snapshot exposed to a benchmark allocator."""

    id: str  # noqa: A003 -- `id` mandated by the shared domain models
    x: float
    y: float
    battery_pct: float
    busy: bool = False


@dataclass(frozen=True)
class TaskView:
    """Environment task snapshot exposed to a benchmark allocator."""

    id: str  # noqa: A003 -- `id` mandated by the shared domain models
    pickup_x: float
    pickup_y: float
    delivery_x: float
    delivery_y: float
    priority: int = PRIORITY_MEDIUM


AssignmentProvider = Callable[[Sequence[RobotView], Sequence[TaskView]], Sequence[tuple[str, str]]]
"""Maps idle robots + pending tasks to (robot_id, task_id) pairs.

Implementations must be deterministic: the same views must always produce the
same assignments, otherwise two benchmark runs of one policy diverge for
reasons unrelated to the policy.
"""
