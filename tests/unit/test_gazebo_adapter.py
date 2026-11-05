"""Unit tests for GazeboRobotAdapter (Phase 1).

Uses a fake transport so the adapter logic (goal publishing, odometry
snapshots, task phases, failure injection) is exercised without rclpy /
Gazebo.
"""

from dataclasses import dataclass, field

import pytest

from robotics.adapters.gazebo import (
    GazeboRobotAdapter,
    OdometrySample,
    PoseGoal,
    ScanSample,
    TwistCommand,
)
from robotics.models.failure import FailureType
from robotics.models.robot_state import CommState, NavState, Vector2D
from robotics.models.task import Task


@dataclass
class FakeTransport:
    """Records commands and serves canned telemetry."""

    odometry: OdometrySample | None = None
    scan: ScanSample | None = None
    battery: float | None = 1.0
    connected: bool = True
    goals: list[PoseGoal] = field(default_factory=list)
    twists: list[TwistCommand] = field(default_factory=list)

    def is_connected(self) -> bool:
        return self.connected

    def publish_goal(self, goal: PoseGoal) -> None:
        self.goals.append(goal)

    def publish_velocity(self, twist: TwistCommand) -> None:
        self.twists.append(twist)

    def latest_odometry(self) -> OdometrySample | None:
        return self.odometry

    def latest_scan(self) -> ScanSample | None:
        return self.scan

    def latest_battery(self) -> float | None:
        return self.battery


def make_task(pickup: tuple[float, float], delivery: tuple[float, float]) -> Task:
    return Task(
        id="t1",
        pickup=Vector2D(*pickup),
        delivery=Vector2D(*delivery),
        created_at=0.0,
    )


class TestGazeboRobotAdapter:
    def test_initial_state_from_telemetry(self) -> None:
        transport = FakeTransport(
            odometry=OdometrySample(x=3.0, y=4.0, yaw=0.5, timestamp=0.0),
            battery=0.8,
        )
        adapter = GazeboRobotAdapter("robot_0", transport)
        state = adapter.get_state()
        assert state.id == "robot_0"
        assert state.position.x == 3.0
        assert state.position.y == 4.0
        assert state.battery_pct == pytest.approx(0.8)
        assert state.comm_state == CommState.ONLINE

    def test_no_telemetry_defaults(self) -> None:
        adapter = GazeboRobotAdapter("robot_0", FakeTransport())
        state = adapter.get_state()
        assert state.position == Vector2D(0.0, 0.0)
        assert state.battery_pct == pytest.approx(1.0)

    def test_assign_task_publishes_pickup_goal(self) -> None:
        transport = FakeTransport()
        adapter = GazeboRobotAdapter("robot_0", transport)
        assert adapter.assign_task(make_task((5.0, 0.0), (6.0, 1.0))) is True
        assert transport.goals == [PoseGoal(5.0, 0.0)]
        assert adapter.get_state().nav_state == NavState.MOVING

    def test_assign_task_rejected_when_busy_or_failed(self) -> None:
        transport = FakeTransport()
        adapter = GazeboRobotAdapter("robot_0", transport)
        task = make_task((5.0, 0.0), (6.0, 1.0))
        assert adapter.assign_task(task) is True
        assert adapter.assign_task(task) is False  # already has a task
        adapter.inject_failure(FailureType.COMMUNICATION_LOSS)
        adapter.clear_failure()
        adapter.stop()
        assert adapter.assign_task(task) is True  # idle again

    def test_assign_task_rejected_when_offline(self) -> None:
        transport = FakeTransport(connected=False)
        adapter = GazeboRobotAdapter("robot_0", transport)
        assert adapter.assign_task(make_task((5.0, 0.0), (6.0, 1.0))) is False

    def test_reaches_pickup_then_publishes_delivery_goal(self) -> None:
        transport = FakeTransport(odometry=OdometrySample(4.9, 0.0, 0.0, 0.0))
        adapter = GazeboRobotAdapter("robot_0", transport)
        adapter.assign_task(make_task((5.0, 0.0), (6.0, 1.0)))
        adapter.tick(1.0)  # now within 0.3 m of pickup
        assert transport.goals[-1] == PoseGoal(6.0, 1.0)

    def test_completes_task_at_delivery(self) -> None:
        transport = FakeTransport(odometry=OdometrySample(5.0, 0.0, 0.0, 0.0))
        adapter = GazeboRobotAdapter("robot_0", transport)
        adapter.assign_task(make_task((5.0, 0.0), (6.0, 1.0)))
        adapter.tick(1.0)  # at pickup -> switch to delivery, publish delivery goal
        assert transport.goals[-1] == PoseGoal(6.0, 1.0)
        transport.odometry = OdometrySample(6.0, 1.0, 0.0, 0.0)
        adapter.tick(1.0)  # at delivery -> complete
        assert adapter.take_completed_task() == "t1"
        assert adapter.get_state().nav_state == NavState.IDLE

    def test_scan_becomes_sensor_frame(self) -> None:
        transport = FakeTransport(scan=ScanSample(ranges=(1.0, 2.0, 3.0), timestamp=0.0))
        adapter = GazeboRobotAdapter("robot_0", transport)
        frame = adapter.get_sensors()
        assert frame is not None
        assert frame.lidar_ranges == [1.0, 2.0, 3.0]

    def test_no_scan_returns_none(self) -> None:
        adapter = GazeboRobotAdapter("robot_0", FakeTransport())
        assert adapter.get_sensors() is None

    def test_stop_publishes_zero_velocity_and_clears_task(self) -> None:
        transport = FakeTransport()
        adapter = GazeboRobotAdapter("robot_0", transport)
        adapter.assign_task(make_task((5.0, 0.0), (6.0, 1.0)))
        adapter.stop()
        assert transport.twists[-1] == TwistCommand(0.0, 0.0)
        assert adapter.get_state().nav_state == NavState.IDLE

    def test_communication_loss_marks_offline_and_blocks_commands(self) -> None:
        transport = FakeTransport()
        adapter = GazeboRobotAdapter("robot_0", transport)
        adapter.inject_failure(FailureType.COMMUNICATION_LOSS)
        assert adapter.get_state().comm_state == CommState.OFFLINE
        assert adapter.assign_task(make_task((5.0, 0.0), (6.0, 1.0))) is False
        adapter.clear_failure()
        assert adapter.get_state().comm_state == CommState.ONLINE

    def test_navigation_failure_marks_failed_state(self) -> None:
        transport = FakeTransport()
        adapter = GazeboRobotAdapter("robot_0", transport)
        adapter.inject_failure(FailureType.NAVIGATION_FAILURE)
        assert adapter.get_state().nav_state == NavState.FAILED

    def test_go_charge_publishes_charging_station_goal(self) -> None:
        transport = FakeTransport()
        adapter = GazeboRobotAdapter("robot_0", transport, charging_station=Vector2D(38.0, 28.0))
        adapter.assign_task(make_task((5.0, 0.0), (6.0, 1.0)))
        dropped = adapter.go_charge()
        assert dropped == "t1"
        assert transport.goals[-1] == PoseGoal(38.0, 28.0)
        assert adapter.get_state().nav_state == NavState.CHARGING

    def test_energy_consumed_from_battery_topic(self) -> None:
        transport = FakeTransport(battery=0.7)
        adapter = GazeboRobotAdapter("robot_0", transport)
        assert adapter.energy_consumed_units == pytest.approx(30.0)

    def test_energy_zero_without_battery_telemetry(self) -> None:
        adapter = GazeboRobotAdapter("robot_0", FakeTransport(battery=None))
        assert adapter.energy_consumed_units == 0.0
