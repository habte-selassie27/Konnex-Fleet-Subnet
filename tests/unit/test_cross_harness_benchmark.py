"""Tests for the unified cross-harness benchmark plumbing.

Covers the two seams that remove the cross-harness caveat:
  * `AllocatorPolicy` translating FleetEnv views into allocator assignments,
  * `FleetOrchestrator` accepting an injected robot factory (Gazebo wiring).
"""

from __future__ import annotations

import numpy as np

from fleet.mission_manager import MissionConfig
from fleet.orchestrator import FleetOrchestrator
from fleet.task_allocator.hungarian import HungarianAllocator
from fleet.task_allocator.nearest import NearestTaskAllocator
from ml.env.assignment import PRIORITY_HIGH, RobotView, TaskView
from ml.env.fleet_env import FleetEnv, FleetEnvConfig
from ml.evaluation.allocator_policy import AllocatorPolicy, allocator_action_fn
from robotics.adapters.simulation import SimulationRobotAdapter
from robotics.models.robot_state import Vector2D


def _robots() -> list[RobotView]:
    return [
        RobotView(id="robot_0", x=0.0, y=0.0, battery_pct=1.0),
        RobotView(id="robot_1", x=10.0, y=0.0, battery_pct=1.0),
    ]


def _tasks() -> list[TaskView]:
    return [
        TaskView(id="near_robot_0", pickup_x=1.0, pickup_y=0.0, delivery_x=2.0, delivery_y=0.0),
        TaskView(
            id="near_robot_1",
            pickup_x=11.0,
            pickup_y=0.0,
            delivery_x=12.0,
            delivery_y=0.0,
            priority=PRIORITY_HIGH,
        ),
    ]


def test_nearest_allocator_assigns_closest_task() -> None:
    policy = AllocatorPolicy(NearestTaskAllocator())
    pairs = dict(policy.provider(_robots(), _tasks()))

    assert pairs["robot_0"] == "near_robot_0"
    assert pairs["robot_1"] == "near_robot_1"


def test_hungarian_allocator_minimises_total_distance() -> None:
    policy = AllocatorPolicy(HungarianAllocator())
    pairs = dict(policy.provider(_robots(), _tasks()))

    assert pairs["robot_0"] == "near_robot_0"
    assert pairs["robot_1"] == "near_robot_1"


def test_empty_inputs_produce_no_assignments() -> None:
    policy = AllocatorPolicy(NearestTaskAllocator())
    assert policy.provider([], _tasks()) == []
    assert policy.provider(_robots(), []) == []


def test_allocator_drives_waypoints_inside_fleet_env() -> None:
    """End-to-end: allocator assignment becomes a non-zero waypoint action."""
    env = FleetEnv(FleetEnvConfig(robot_count=2, task_count=4))
    policy = AllocatorPolicy(NearestTaskAllocator())
    env.set_assignment_provider(policy.provider)

    observations, _ = env.reset(seed=11)
    actions = allocator_action_fn()(env, observations)

    assert set(actions) == set(observations)
    for vector in actions.values():
        assert vector.shape == (2,)
        assert np.all(np.abs(vector) <= 1.0)
    assert any(np.any(vector) for vector in actions.values())


def test_orchestrator_uses_injected_robot_factory() -> None:
    built: list[str] = []

    def factory(robot_id: str, position: Vector2D, battery_pct: float) -> SimulationRobotAdapter:
        built.append(robot_id)
        return SimulationRobotAdapter(
            robot_id=robot_id, start_position=position, battery_pct=battery_pct
        )

    orchestrator = FleetOrchestrator(allocator=NearestTaskAllocator(), robot_factory=factory)
    mission = orchestrator.start_mission(42, MissionConfig(robot_count=3, task_count=5, seed=42))

    assert built == ["robot_0", "robot_1", "robot_2"]
    assert mission.robot_count == 3
    assert len(orchestrator.get_fleet_state().robots) == 3


def test_orchestrator_defaults_to_headless_adapter() -> None:
    orchestrator = FleetOrchestrator(allocator=NearestTaskAllocator())
    orchestrator.start_mission(42, MissionConfig(robot_count=2, task_count=3, seed=42))

    state = orchestrator.get_fleet_state()
    assert len(state.robots) == 2
