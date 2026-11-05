"""Collision avoidance tests — Phase 2.

Verifies velocity scaling logic for robot-robot collision avoidance.
"""

from __future__ import annotations

from fleet.collision.avoidance import (
    CRITICAL_DISTANCE_M,
    WARNING_DISTANCE_M,
    VelocityScale,
    _distance_to_scale,
    compute_avoidance_scales,
)


class TestDistanceToScale:
    def test_critical_distance_gives_zero_scale(self) -> None:
        assert _distance_to_scale(CRITICAL_DISTANCE_M) == 0.0
        assert _distance_to_scale(0.1) == 0.0

    def test_warning_distance_gives_full_scale(self) -> None:
        assert _distance_to_scale(WARNING_DISTANCE_M) == 1.0
        assert _distance_to_scale(5.0) == 1.0

    def test_intermediate_distance_gives_proportional_scale(self) -> None:
        mid = (CRITICAL_DISTANCE_M + WARNING_DISTANCE_M) / 2
        scale = _distance_to_scale(mid)
        assert 0.4 < scale < 0.6  # should be ~0.5

    def test_scale_monotonic_increasing(self) -> None:
        prev = 0.0
        for d in [0.5, 0.8, 1.0, 1.2, 2.0, 5.0]:
            s = _distance_to_scale(d)
            assert s >= prev
            prev = s


class TestComputeAvoidanceScales:
    def test_single_robot_gets_full_speed(self) -> None:
        scales = compute_avoidance_scales(
            robot_positions={"r0": (5.0, 5.0)},
            robot_ids=["r0"],
        )
        assert len(scales) == 1
        assert scales[0].scale == 1.0

    def test_distant_robots_get_full_speed(self) -> None:
        scales = compute_avoidance_scales(
            robot_positions={"r0": (0.0, 0.0), "r1": (10.0, 10.0)},
            robot_ids=["r0", "r1"],
        )
        assert all(s.scale == 1.0 for s in scales)

    def test_close_robots_slow_down(self) -> None:
        scales = compute_avoidance_scales(
            robot_positions={"r0": (0.0, 0.0), "r1": (1.0, 0.0)},
            robot_ids=["r0", "r1"],
        )
        for s in scales:
            assert 0.0 < s.scale < 1.0

    def test_touching_robots_stop(self) -> None:
        scales = compute_avoidance_scales(
            robot_positions={"r0": (0.0, 0.0), "r1": (0.5, 0.0)},
            robot_ids=["r0", "r1"],
        )
        assert all(s.scale == 0.0 for s in scales)

    def test_missing_position_gets_full_speed(self) -> None:
        scales = compute_avoidance_scales(
            robot_positions={"r0": (5.0, 5.0)},
            robot_ids=["r0", "r1"],
        )
        by_id = {s.robot_id: s for s in scales}
        assert by_id["r0"].scale == 1.0
        assert by_id["r1"].scale == 1.0

    def test_returns_one_scale_per_robot(self) -> None:
        scales = compute_avoidance_scales(
            robot_positions={"r0": (0, 0), "r1": (1, 0), "r2": (2, 0)},
            robot_ids=["r0", "r1", "r2"],
        )
        assert len(scales) == 3
        assert {s.robot_id for s in scales} == {"r0", "r1", "r2"}
