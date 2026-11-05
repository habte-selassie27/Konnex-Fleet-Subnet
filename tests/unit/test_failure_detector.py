"""FailureDetector unit tests (TESTING_PLAN.md §3.7, Phase 5).

Thresholds: battery warning < 20%, battery critical < 10%, stuck 30 s,
comm loss 10 s, navigation failure on explicit FAILED nav state.

Status: COMPLETE (Phase 5).
"""

from fleet.failure.detector import FailureDetector
from robotics.models.failure import FailureSeverity, FailureType
from robotics.models.robot_state import CommState, NavState, RobotState, Vector2D


def make_state(
    robot_id: str = "r1",
    x: float = 0.0,
    y: float = 0.0,
    battery_pct: float = 1.0,
    nav_state: NavState = NavState.IDLE,
    comm_state: CommState = CommState.ONLINE,
    timestamp: float = 0.0,
) -> RobotState:
    """Build a RobotState with only the fields relevant to detection."""
    return RobotState(
        id=robot_id,
        position=Vector2D(x=x, y=y),
        battery_pct=battery_pct,
        nav_state=nav_state,
        comm_state=comm_state,
        timestamp=timestamp,
    )


class TestBatteryFailures:
    def test_battery_warning_at_15_percent(self) -> None:
        events = FailureDetector().check(make_state(battery_pct=0.15), [])
        assert len(events) == 1
        assert events[0].failure_type == FailureType.BATTERY_WARNING
        assert events[0].severity == FailureSeverity.WARNING

    def test_battery_critical_at_5_percent(self) -> None:
        events = FailureDetector().check(make_state(battery_pct=0.05), [])
        assert len(events) == 1
        assert events[0].failure_type == FailureType.BATTERY_CRITICAL
        assert events[0].severity == FailureSeverity.CRITICAL

    def test_no_event_when_healthy(self) -> None:
        assert FailureDetector().check(make_state(battery_pct=0.9), []) == []

    def test_warning_not_reported_until_recovery(self) -> None:
        detector = FailureDetector()
        low = make_state(battery_pct=0.15)
        assert len(detector.check(low, [])) == 1
        assert detector.check(low, []) == []  # deduplicated
        detector.check(make_state(battery_pct=0.9), [])  # recovered above threshold
        assert len(detector.check(make_state(battery_pct=0.15), [])) == 1  # re-emitted


class TestCommAndNavFailures:
    def test_communication_loss_after_sustained_outage(self) -> None:
        detector = FailureDetector()
        first = make_state(comm_state=CommState.DEGRADED, timestamp=0.0)
        assert detector.check(first, []) == []
        second = make_state(comm_state=CommState.DEGRADED, timestamp=11.0)
        events = detector.check(second, [first])
        assert [event.failure_type for event in events] == [FailureType.COMMUNICATION_LOSS]

    def test_communication_recovers(self) -> None:
        detector = FailureDetector()
        detector.check(make_state(comm_state=CommState.DEGRADED, timestamp=0.0), [])
        detector.check(make_state(comm_state=CommState.DEGRADED, timestamp=11.0), [])
        assert detector.check(make_state(comm_state=CommState.ONLINE, timestamp=12.0), []) == []

    def test_navigation_failure_reported_once(self) -> None:
        detector = FailureDetector()
        state = make_state(nav_state=NavState.FAILED, timestamp=1.0)
        events = detector.check(state, [])
        assert [event.failure_type for event in events] == [FailureType.NAVIGATION_FAILURE]
        assert detector.check(state, []) == []


class TestStuckDetection:
    def test_stuck_detected_after_30s_without_progress(self) -> None:
        detector = FailureDetector()
        t0 = make_state(nav_state=NavState.MOVING, timestamp=0.0)
        t31 = make_state(nav_state=NavState.MOVING, timestamp=31.0)
        t61 = make_state(nav_state=NavState.MOVING, timestamp=61.0)
        detector.check(t0, [])
        detector.check(t31, [t0])
        events = detector.check(t61, [t0, t31])
        assert [event.failure_type for event in events] == [FailureType.STUCK]

    def test_moving_robot_is_not_stuck(self) -> None:
        detector = FailureDetector()
        detector.check(make_state(nav_state=NavState.MOVING, timestamp=0.0), [])
        moved = make_state(nav_state=NavState.MOVING, x=5.0, timestamp=11.0)
        history = [make_state(nav_state=NavState.MOVING, timestamp=0.0)]
        assert detector.check(moved, history) == []


class TestReset:
    def test_reset_forgets_reported_state(self) -> None:
        detector = FailureDetector()
        detector.check(make_state(battery_pct=0.05), [])
        detector.reset()
        assert len(detector.check(make_state(battery_pct=0.05), [])) == 1
