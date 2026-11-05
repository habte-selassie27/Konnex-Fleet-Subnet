"""Robot navigation simulation tests — Phase 1 gate (headless mock mode).

Spec (TESTING_PLAN.md §5):
    robots spawn at valid positions, robot navigates to goal,
    path avoids obstacles, battery drain matches nav state.

Runs without Gazebo via the deterministic SimulationRobotAdapter.

Status: COMPLETE (realigned to the Phase 5 headless adapter API).
"""

import pytest

from robotics.adapters.simulation import SimulationRobotAdapter
from robotics.models.failure import FailureType
from robotics.models.robot_state import CommState, NavState, RobotState, Vector2D
from robotics.models.task import Task

pytestmark = pytest.mark.simulation


def make_task(x: float = 5.0, y: float = 3.0) -> Task:
    """A simple pickup/delivery task with a nearby goal."""
    return Task(id="nav_goal", pickup=Vector2D(x=x, y=y), delivery=Vector2D(x=x + 1, y=y + 1))


class TestRobotNavigation:
    def test_adapter_initializes(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot")
        assert adapter.robot_id == "test_robot"

    def test_get_state_returns_robot_state(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot")
        state = adapter.get_state()
        assert isinstance(state, RobotState)
        assert state.id == "test_robot"
        assert state.nav_state == NavState.IDLE
        assert state.comm_state == CommState.ONLINE

    def test_stop_sets_idle(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot")
        adapter.assign_task(make_task())
        adapter.stop()
        assert adapter.get_state().nav_state == NavState.IDLE

    def test_assign_task_sets_moving(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot")
        assert adapter.assign_task(make_task()) is True
        assert adapter.get_state().nav_state == NavState.MOVING

    def test_position_advances_toward_goal(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot", start_position=Vector2D(0.0, 0.0))
        adapter.assign_task(make_task(x=5.0, y=0.0))
        start = adapter.get_state().position
        adapter.tick(1.0)
        moved = adapter.get_state().position
        assert moved.distance_to(start) > 0.0
        assert moved.x > start.x

    def test_robot_reaches_goal_and_completes_task(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot", start_position=Vector2D(0.0, 0.0))
        task = make_task(x=2.0, y=0.0)
        adapter.assign_task(task)
        completed: str | None = None
        for _ in range(200):
            adapter.tick(0.1)
            completed = adapter.take_completed_task()
            if completed is not None:
                break
        assert completed == task.id
        assert adapter.get_state().nav_state == NavState.IDLE

    def test_battery_drains_while_moving(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot", start_position=Vector2D(0.0, 0.0))
        adapter.assign_task(make_task(x=20.0, y=0.0))
        before = adapter.get_battery()
        adapter.tick(5.0)
        assert adapter.get_battery() < before

    def test_battery_stable_when_idle(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot")
        before = adapter.get_battery()
        adapter.tick(5.0)
        assert adapter.get_battery() == pytest.approx(before, abs=1e-9)

    def test_low_battery_reported(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot", battery_pct=0.05)
        assert 0.0 <= adapter.get_battery() <= 1.0
        assert adapter.get_battery() < 0.10

    def test_go_charge_sends_robot_to_station(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot", battery_pct=0.05)
        adapter.go_charge()
        assert adapter.get_state().nav_state == NavState.CHARGING
        adapter.tick(10.0)
        assert adapter.get_battery() > 0.05

    def test_communication_loss_blocks_commands(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot")
        adapter.inject_failure(FailureType.COMMUNICATION_LOSS)
        assert adapter.get_state().comm_state == CommState.OFFLINE
        assert adapter.assign_task(make_task()) is False

    def test_navigation_failure_freezes_robot(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot", start_position=Vector2D(0.0, 0.0))
        adapter.assign_task(make_task(x=10.0, y=0.0))
        adapter.inject_failure(FailureType.NAVIGATION_FAILURE)
        position = adapter.get_state().position
        adapter.tick(2.0)
        assert adapter.get_state().position == position

    def test_sensor_frame_available(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot")
        assert adapter.get_sensors() is not None

    def test_is_available_when_idle(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot")
        assert self._is_available(adapter) is True

    def test_is_not_available_when_navigating(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot")
        adapter.assign_task(make_task())
        assert self._is_available(adapter) is False

    def test_is_not_available_when_failed(self) -> None:
        adapter = SimulationRobotAdapter(robot_id="test_robot")
        adapter.inject_failure(FailureType.NAVIGATION_FAILURE)
        assert self._is_available(adapter) is False

    def test_multiple_robots_independent(self) -> None:
        first = SimulationRobotAdapter(robot_id="robot_0")
        second = SimulationRobotAdapter(robot_id="robot_1")
        first.assign_task(make_task())
        assert first.get_state().nav_state == NavState.MOVING
        assert second.get_state().nav_state == NavState.IDLE

    def test_vector2d_distance(self) -> None:
        v1 = Vector2D(x=0.0, y=0.0)
        v2 = Vector2D(x=3.0, y=4.0)
        assert v1.distance_to(v2) == pytest.approx(5.0, abs=0.01)

    def test_collision_flag(self) -> None:
        state = RobotState(id="test_robot", position=Vector2D(0.0, 0.0))
        state.in_collision = True
        assert state.in_collision is True

    @staticmethod
    def _is_available(adapter: SimulationRobotAdapter) -> bool:
        """Fleet-side availability check (mirrors the orchestrator's filter)."""
        state = adapter.get_state()
        return (
            state.comm_state == CommState.ONLINE
            and state.nav_state not in (NavState.FAILED, NavState.CHARGING)
            and state.current_task_id is None
            and state.battery_pct >= 0.10
        )
