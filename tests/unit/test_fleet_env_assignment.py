"""Tests for FleetEnv's external assignment-provider seam (unified benchmark).

The seam is what lets classical allocators be scored in the same simulator as
MAPPO. It must be opt-in (training dynamics unchanged), deterministic, and
fail loudly on invalid assignments rather than silently falling back.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest

from ml.env.assignment import RobotView, TaskView
from ml.env.fleet_env import FleetEnv, FleetEnvConfig


def _env(robots: int = 3, tasks: int = 6) -> FleetEnv:
    return FleetEnv(FleetEnvConfig(robot_count=robots, task_count=tasks))


def test_provider_is_called_with_idle_robots_and_pending_tasks() -> None:
    env = _env()
    calls: list[tuple[int, int]] = []

    def provider(robots: Sequence[RobotView], tasks: Sequence[TaskView]) -> list[tuple[str, str]]:
        calls.append((len(robots), len(tasks)))
        return [(robots[0].id, tasks[0].id)]

    env.set_assignment_provider(provider)
    env.reset(seed=7)

    assert calls, "provider must run during reset so robots have a target"
    robots, tasks = calls[0]
    assert robots == 3
    assert tasks == 6
    # robot_0 owns the first pending task, so it has a waypoint target.
    assert np.any(env.target_vector("robot_0"))


def test_provider_sees_domain_free_views() -> None:
    env = _env()
    captured: dict[str, object] = {}

    def provider(robots: Sequence[RobotView], tasks: Sequence[TaskView]) -> list[tuple[str, str]]:
        captured["robot"] = robots[0]
        captured["task"] = tasks[0]
        return []

    env.set_assignment_provider(provider)
    env.reset(seed=7)

    robot = captured["robot"]
    task = captured["task"]
    assert isinstance(robot, RobotView)
    assert isinstance(task, TaskView)
    assert 0.0 <= robot.battery_pct <= 1.0
    assert task.priority in (0, 1, 2)


def test_unknown_robot_from_provider_raises() -> None:
    env = _env()
    env.set_assignment_provider(lambda _robots, tasks: [("robot_99", tasks[0].id)])

    with pytest.raises(ValueError, match="unknown robot"):
        env.reset(seed=7)


def test_unknown_task_from_provider_raises() -> None:
    env = _env()
    env.set_assignment_provider(lambda robots, _tasks: [(robots[0].id, "task_missing")])

    with pytest.raises(ValueError, match="unknown task"):
        env.reset(seed=7)


def test_without_provider_greedy_assignment_still_drives_robots() -> None:
    env = _env()
    env.reset(seed=7)
    # The internal greedy rule assigns on the first step, not at reset.
    assert not np.any(env.target_vector("robot_0"))

    actions = {agent: np.zeros(2, dtype=np.float32) for agent in env.agent_ids}
    env.step(actions)
    assert np.any(env.target_vector("robot_0"))


def test_clearing_provider_restores_headless_behaviour() -> None:
    env = _env()
    env.set_assignment_provider(lambda robots, tasks: [(robots[0].id, tasks[0].id)])
    env.reset(seed=7)
    assert env.assignment_provider is not None

    env.set_assignment_provider(None)
    assert env.assignment_provider is None
