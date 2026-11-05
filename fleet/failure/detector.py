"""FailureDetector — monitors robot health and emits FailureEvents.

Status: COMPLETE (Phase 5).
Thresholds (BUILD.md §5): battery warning 20%, battery critical 10%,
stuck 30 s, comm loss 10 s; navigation failure detection added per Phase 5 spec.
"""

from robotics.models.failure import FailureEvent, FailureSeverity, FailureType
from robotics.models.robot_state import NavState, RobotState


class FailureDetector:
    """Detects health failures from a stream of robot states."""

    BATTERY_WARNING_THRESHOLD = 0.20
    BATTERY_CRITICAL_THRESHOLD = 0.10
    STUCK_TIMEOUT_S = 30.0
    COMM_LOSS_TIMEOUT_S = 10.0
    NAV_STALL_TIMEOUT_S = 15.0

    def __init__(self) -> None:
        self._reported: set[tuple[str, FailureType]] = set()
        self._stuck_since: dict[str, float] = {}
        self._comm_loss_since: dict[str, float] = {}
        self._last_position: dict[str, tuple[float, float]] = {}

    def check(self, state: RobotState, history: list[RobotState]) -> list[FailureEvent]:
        """Return any new failure events for this robot.

        `history` contains prior states for this robot (oldest first) and is
        used for position-change detection.
        """
        events: list[FailureEvent] = []
        robot_id = state.id

        # Battery thresholds (deduped until the battery recovers).
        if state.battery_pct < self.BATTERY_CRITICAL_THRESHOLD:
            events.extend(self._emit_once(robot_id, FailureType.BATTERY_CRITICAL, state.timestamp))
        elif state.battery_pct < self.BATTERY_WARNING_THRESHOLD:
            events.extend(self._emit_once(robot_id, FailureType.BATTERY_WARNING, state.timestamp))
        else:
            self._reported.discard((robot_id, FailureType.BATTERY_WARNING))
            self._reported.discard((robot_id, FailureType.BATTERY_CRITICAL))

        # Communication loss (needs a sustained outage window).
        if state.comm_state != "online":
            since = self._comm_loss_since.setdefault(robot_id, state.timestamp)
            if state.timestamp - since >= self.COMM_LOSS_TIMEOUT_S:
                events.extend(
                    self._emit_once(robot_id, FailureType.COMMUNICATION_LOSS, state.timestamp)
                )
        else:
            self._comm_loss_since.pop(robot_id, None)
            self._reported.discard((robot_id, FailureType.COMMUNICATION_LOSS))

        # Navigation failure (explicit FAILED nav state).
        if state.nav_state == NavState.FAILED:
            events.extend(
                self._emit_once(robot_id, FailureType.NAVIGATION_FAILURE, state.timestamp)
            )

        # Stuck detection: MOVING without progress for STUCK_TIMEOUT_S.
        self._track_stuck(state, history, events)

        return events

    def reset(self) -> None:
        """Forget all previously reported failures (new mission)."""
        self._reported.clear()
        self._stuck_since.clear()
        self._comm_loss_since.clear()
        self._last_position.clear()

    def _emit_once(
        self, robot_id: str, failure_type: FailureType, timestamp: float
    ) -> list[FailureEvent]:
        key = (robot_id, failure_type)
        if key in self._reported:
            return []
        self._reported.add(key)
        severity = (
            FailureSeverity.CRITICAL
            if failure_type in (FailureType.BATTERY_CRITICAL, FailureType.NAVIGATION_FAILURE)
            else FailureSeverity.WARNING
        )
        return [
            FailureEvent(
                robot_id=robot_id, failure_type=failure_type, severity=severity, timestamp=timestamp
            )
        ]

    def _track_stuck(
        self, state: RobotState, history: list[RobotState], events: list[FailureEvent]
    ) -> None:
        robot_id = state.id
        if state.nav_state == NavState.MOVING:
            moved = self._has_moved(state, history)
            if not moved:
                since = self._stuck_since.setdefault(robot_id, state.timestamp)
                if state.timestamp - since >= self.STUCK_TIMEOUT_S:
                    events.extend(self._emit_once(robot_id, FailureType.STUCK, state.timestamp))
            else:
                self._stuck_since.pop(robot_id, None)
                self._reported.discard((robot_id, FailureType.STUCK))
        else:
            self._stuck_since.pop(robot_id, None)
            self._reported.discard((robot_id, FailureType.STUCK))

    @staticmethod
    def _has_moved(state: RobotState, history: list[RobotState]) -> bool:
        for previous in reversed(history):
            if previous.id != state.id:
                continue
            return state.position.distance_to(previous.position) > 0.01
        return True
