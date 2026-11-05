"""Collision monitor unit tests (TESTING_PLAN.md §3.6).

Status: COMPLETE (Phase 5).
"""

from fleet.collision.monitor import CollisionMonitor
from robotics.models.robot_state import RobotState, Vector2D


def robot(robot_id: str, x: float, y: float, t: float = 0.0) -> RobotState:
    return RobotState(id=robot_id, position=Vector2D(x=x, y=y), timestamp=t)


class TestCollisionMonitor:
    def test_detects_robot_robot_collision(self) -> None:
        events = CollisionMonitor().detect([robot("a", 0, 0), robot("b", 0.2, 0)])
        assert any(not event.near_miss for event in events)

    def test_no_false_positive_when_far(self) -> None:
        events = CollisionMonitor().detect([robot("a", 0, 0), robot("b", 2.0, 0)])
        assert events == []

    def test_detects_robot_obstacle_near_miss(self) -> None:
        events = CollisionMonitor().detect([robot("a", 0, 0), robot("b", 0.8, 0)])
        assert events
        assert all(event.near_miss for event in events)

    def test_collision_clears_on_separation(self) -> None:
        monitor = CollisionMonitor()
        assert monitor.detect([robot("a", 0, 0), robot("b", 0.2, 0)])
        assert monitor.detect([robot("a", 0, 0), robot("b", 2.0, 0)]) == []

    def test_pair_counted_once(self) -> None:
        events = CollisionMonitor().detect([robot("a", 0, 0), robot("b", 0.2, 0)])
        assert len(events) == 1

    def test_sustained_contact_reported_once(self) -> None:
        # A 10 s contact at 10 Hz must count as one collision, not 100.
        monitor = CollisionMonitor()
        monitor.detect([robot("a", 0, 0), robot("b", 0.2, 0)])
        events = [
            event
            for tick in range(1, 100)
            for event in monitor.detect([robot("a", 0, 0, t=tick * 0.1), robot("b", 0.2, 0)])
        ]
        assert events == []

    def test_separate_and_recontact_reports_again(self) -> None:
        monitor = CollisionMonitor()
        assert monitor.detect([robot("a", 0, 0), robot("b", 0.2, 0)])
        assert monitor.detect([robot("a", 0, 0, t=1.0), robot("b", 3.0, 0)]) == []
        again = monitor.detect([robot("a", 0, 0, t=2.0), robot("b", 0.2, 0)])
        assert len(again) == 1
        assert again[0].near_miss is False

    def test_near_miss_escalation_reports_collision(self) -> None:
        monitor = CollisionMonitor()
        near = monitor.detect([robot("a", 0, 0), robot("b", 0.8, 0)])
        assert len(near) == 1 and near[0].near_miss is True
        # Same pair keeps closing — no repeat near-miss, then one collision event.
        assert monitor.detect([robot("a", 0, 0, t=0.1), robot("b", 0.7, 0)]) == []
        contact = monitor.detect([robot("a", 0, 0, t=0.2), robot("b", 0.2, 0)])
        assert len(contact) == 1
        assert contact[0].near_miss is False

    def test_reset_forgets_active_contacts(self) -> None:
        monitor = CollisionMonitor()
        assert monitor.detect([robot("a", 0, 0), robot("b", 0.2, 0)])
        monitor.reset()
        assert len(monitor.detect([robot("a", 0, 0), robot("b", 0.2, 0)])) == 1
