"""Cost function unit tests — Phase 2 gate.

Spec (TESTING_PLAN.md §3.1):
    Tests specific to the cost optimizer's cost function components:
    distance, battery, priority, congestion, collision_risk.

Status: COMPLETE (realigned to the Phase 5 cost() signature).
"""

from __future__ import annotations

import pytest

from fleet.task_allocator.cost_optimizer import CostOptimizerAllocator, CostWeights
from robotics.models.robot_state import CommState, NavState, RobotState, Vector2D
from robotics.models.task import Priority, Task


def _robot(x: float, y: float, battery: float = 1.0, robot_id: str = "r0") -> RobotState:
    """A minimal robot state with a position and battery level."""
    return RobotState(
        id=robot_id,
        position=Vector2D(x=x, y=y),
        battery_pct=battery,
        nav_state=NavState.IDLE,
        comm_state=CommState.ONLINE,
    )


def _task(px: float, py: float, priority: Priority = Priority.MEDIUM) -> Task:
    """A minimal pickup/delivery task with a nearby delivery point."""
    return Task(
        id="t0",
        pickup=Vector2D(x=px, y=py),
        delivery=Vector2D(x=px + 5, y=py + 5),
        priority=priority,
    )


class TestCostFunction:
    def test_distance_affects_cost(self) -> None:
        allocator = CostOptimizerAllocator()
        task = _task(5.0, 0.0)
        r_near = _robot(4.0, 0.0)
        r_far = _robot(10.0, 0.0)
        cost_near = allocator.cost(r_near, task, [r_near])
        cost_far = allocator.cost(r_far, task, [r_far])
        assert cost_near < cost_far

    def test_battery_affects_cost(self) -> None:
        allocator = CostOptimizerAllocator()
        task = _task(5.0, 0.0)
        r_low = _robot(0.0, 0.0, battery=0.1)
        r_high = _robot(0.0, 0.0, battery=0.9)
        cost_low = allocator.cost(r_low, task, [r_low])
        cost_high = allocator.cost(r_high, task, [r_high])
        assert cost_low > cost_high

    def test_priority_affects_cost(self) -> None:
        allocator = CostOptimizerAllocator()
        robot = _robot(0.0, 0.0)
        urgent = _task(5.0, 0.0, priority=Priority.HIGH)
        low = _task(5.0, 0.0, priority=Priority.LOW)
        cost_urgent = allocator.cost(robot, urgent, [robot])
        cost_low = allocator.cost(robot, low, [robot])
        assert cost_urgent < cost_low  # high priority costs less

    def test_congestion_increases_cost(self) -> None:
        allocator = CostOptimizerAllocator()
        task = _task(5.0, 0.0)
        robot = _robot(0.0, 0.0)
        nearby = [
            _robot(0.5, 0.5, robot_id="n0"),
            _robot(1.0, 0.0, robot_id="n1"),
            _robot(0.0, 1.0, robot_id="n2"),
        ]
        cost_empty = allocator.cost(robot, task, [robot])
        cost_congested = allocator.cost(robot, task, [robot, *nearby])
        assert cost_congested > cost_empty

    def test_cost_increases_with_distance(self) -> None:
        allocator = CostOptimizerAllocator()
        task = _task(20.0, 0.0)
        r_close = _robot(19.0, 0.0)
        r_far = _robot(0.0, 0.0)
        cost_close = allocator.cost(r_close, task, [r_close])
        cost_far = allocator.cost(r_far, task, [r_far])
        assert cost_close < cost_far

    def test_default_weights_sum_to_one(self) -> None:
        weights = CostWeights()
        total = (
            weights.distance
            + weights.battery
            + weights.priority
            + weights.congestion
            + weights.collision_risk
        )
        assert total == pytest.approx(1.0)

    def test_cost_components_are_finite(self) -> None:
        allocator = CostOptimizerAllocator()
        robot = _robot(3.0, 4.0, battery=0.7)
        task = _task(10.0, 8.0, priority=Priority.HIGH)
        cost = allocator.cost(robot, task, [robot])
        assert cost == cost  # NaN check
        assert abs(cost) != float("inf")  # Inf check
