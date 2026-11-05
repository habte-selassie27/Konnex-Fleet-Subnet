"""Collision avoidance — proactive velocity scaling to prevent collisions.

Status: COMPLETE.
Contract (AGENTS.md §4.7):
    Receives robot states + collision risk, returns velocity scaling factors.
    Does NOT command robots directly — the fleet orchestrator applies the scaling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Distance thresholds (meters)
CRITICAL_DISTANCE_M = 0.7  # Two robot radii touching
WARNING_DISTANCE_M = 1.2  # Safety margin — start slowing down
FULL_SPEED_DISTANCE_M = 2.0  # No reduction needed beyond this


@dataclass
class VelocityScale:
    """Per-robot velocity scaling factor (0.0 = full stop, 1.0 = full speed)."""

    robot_id: str
    scale: float  # [0.0, 1.0]


def compute_avoidance_scales(
    robot_positions: dict[str, tuple[float, float]],
    robot_ids: list[str],
) -> list[VelocityScale]:
    """Compute velocity scaling factors to avoid robot-robot collisions.

    For each robot, find the nearest other robot and scale velocity inversely
    with distance. Closer robots slow down more.

    Args:
        robot_positions: mapping of robot_id -> (x, y) world position.
        robot_ids: list of robot IDs to compute scales for.

    Returns:
        One VelocityScale per robot_id, with scale in [0.0, 1.0].
    """
    scales: list[VelocityScale] = []

    for rid in robot_ids:
        pos = robot_positions.get(rid)
        if pos is None:
            scales.append(VelocityScale(robot_id=rid, scale=1.0))
            continue

        min_dist = float("inf")
        for other_id in robot_ids:
            if other_id == rid:
                continue
            other_pos = robot_positions.get(other_id)
            if other_pos is None:
                continue
            dist = math.sqrt((pos[0] - other_pos[0]) ** 2 + (pos[1] - other_pos[1]) ** 2)
            min_dist = min(min_dist, dist)

        scale = _distance_to_scale(min_dist)
        scales.append(VelocityScale(robot_id=rid, scale=scale))

    return scales


def _distance_to_scale(distance: float) -> float:
    """Map distance to velocity scale [0.0, 1.0].

    - At CRITICAL_DISTANCE_M or less: scale = 0.0 (stop)
    - Between CRITICAL and WARNING: linear ramp from 0.0 to 1.0
    - At WARNING_DISTANCE_M or more: scale = 1.0 (full speed)
    """
    if distance <= CRITICAL_DISTANCE_M:
        return 0.0
    if distance >= WARNING_DISTANCE_M:
        return 1.0
    # Linear interpolation between critical and warning
    return (distance - CRITICAL_DISTANCE_M) / (WARNING_DISTANCE_M - CRITICAL_DISTANCE_M)
