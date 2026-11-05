"""CollisionMonitor — cross-robot collision and near-miss detection.

Status: COMPLETE (Phase 5).
Tests (TESTING_PLAN.md §3.6): robot-robot collision, no false positive when far,
near-miss detection, collision clears on separation.

Detection is edge-triggered: a pair emits an event when it enters the
near-miss/collision zone and when a near miss escalates to a collision — not
once per simulation tick. The 10 Hz mission loop would otherwise report a
single sustained contact as hundreds of "collisions", which corrupts both the
mission collision_count and the PoPW safety component.
"""

from robotics.models.robot_state import RobotState
from robotics.models.telemetry import CollisionEvent


class CollisionMonitor:
    """Detects robot-robot collisions and near misses from a fleet snapshot."""

    COLLISION_DISTANCE_M = 0.5
    NEAR_MISS_DISTANCE_M = 1.0

    def __init__(self) -> None:
        # pair (sorted robot ids) -> True when the pair is currently touching.
        self._active_pairs: dict[tuple[str, str], bool] = {}

    def detect(self, robots: list[RobotState]) -> list[CollisionEvent]:
        """Emit an event when a pair enters a contact state; evaluate each pair once."""
        events: list[CollisionEvent] = []
        current_pairs: dict[tuple[str, str], bool] = {}

        for i, left in enumerate(robots):
            for right in robots[i + 1 :]:
                distance = left.position.distance_to(right.position)
                if distance >= self.NEAR_MISS_DISTANCE_M:
                    continue
                is_collision = distance < self.COLLISION_DISTANCE_M
                pair = (left.id, right.id)
                current_pairs[pair] = is_collision

                previous = self._active_pairs.get(pair)
                if previous is True:
                    # Already touching — the contact was already reported.
                    continue
                if previous is False and not is_collision:
                    # Already reported as a near miss.
                    continue
                # New near miss, new collision, or near-miss escalated to contact.
                events.append(
                    CollisionEvent(
                        robot_id=left.id,
                        other_id=right.id,
                        position=left.position,
                        timestamp=left.timestamp,
                        near_miss=not is_collision,
                    )
                )

        self._active_pairs = current_pairs
        return events

    def reset(self) -> None:
        """Forget active contacts (new mission)."""
        self._active_pairs.clear()
