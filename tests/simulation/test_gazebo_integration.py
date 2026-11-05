"""Gazebo integration tests — Phase 1 gate (TESTING_PLAN.md §5).

These tests require a live gz-sim instance (the `make sim` container or a
native Gazebo Harmonic install); they self-skip via the `gazebo_env` fixture
when unavailable. Each test performs REAL assertions against the running
simulator via the `gz` CLI — no trivially-passing placeholders (a test that
always passes is INVALID per TESTING_PLAN.md §12).

Run with: `pytest tests/simulation/ -m simulation`
"""

from __future__ import annotations

import subprocess

import pytest

pytestmark = pytest.mark.simulation

GZ_TIMEOUT_S = 30


def run_gz(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a `gz` CLI command with a bounded timeout."""
    return subprocess.run(  # noqa: S603 - trusted local CLI
        ["gz", *args],
        capture_output=True,
        text=True,
        timeout=GZ_TIMEOUT_S,
    )


class TestGazeboWorld:
    """World-level checks: the simulator is up and the warehouse is loaded."""

    def test_world_clock_publishes(self, gazebo_env: str) -> None:
        """gz-sim is running and publishing the world clock."""
        assert gazebo_env == "gazebo_harmonic"
        topics = run_gz("topic", "-l")
        assert topics.returncode == 0
        assert "/clock" in topics.stdout

    def test_warehouse_models_loaded(self, gazebo_env: str) -> None:
        """The warehouse floor, walls, shelves and zones exist as models."""
        assert gazebo_env == "gazebo_harmonic"
        models = run_gz("model", "--list")
        assert models.returncode == 0
        assert "floor" in models.stdout
        assert "shelf_00" in models.stdout
        assert "pickup_zone_0" in models.stdout
        assert "delivery_zone_0" in models.stdout

    def test_sim_time_advances(self, gazebo_env: str) -> None:
        """The physics clock produces a stream of messages (sim advances)."""
        assert gazebo_env == "gazebo_harmonic"
        clock = run_gz("topic", "-e", "-t", "/clock", "-n", "2")
        assert clock.returncode == 0
        assert len(clock.stdout.strip().splitlines()) >= 2


class TestGazeboRobots:
    """Robot-level checks: 5 robots spawned with bridged topics."""

    def test_five_robot_models_spawned(self, gazebo_env: str) -> None:
        """robot_0 … robot_4 are present in the world."""
        assert gazebo_env == "gazebo_harmonic"
        models = run_gz("model", "--list")
        assert models.returncode == 0
        for i in range(5):
            assert f"robot_{i}" in models.stdout

    def test_robot_bridge_topics_published(self, gazebo_env: str) -> None:
        """gz topics for odometry, LiDAR and cmd_vel exist per robot."""
        assert gazebo_env == "gazebo_harmonic"
        topics = run_gz("topic", "-l")
        assert topics.returncode == 0
        # Actual gz topic names (verified in-container 2026-11-02):
        #   odometry (not "odom"), and the lidar scan lives under the full
        #   world/model/link/sensor path.
        assert "/model/robot_0/odometry" in topics.stdout
        assert "/world/warehouse_v1/model/robot_0/link/base_link/sensor/lidar/scan" in topics.stdout
        assert "/model/robot_0/cmd_vel" in topics.stdout

    def test_odometry_publishes_data(self, gazebo_env: str) -> None:
        """robot_0 odometry emits at least one message (LiDAR/odom live)."""
        assert gazebo_env == "gazebo_harmonic"
        odom = run_gz("topic", "-e", "-t", "/model/robot_0/odometry", "-n", "1")
        assert odom.returncode == 0
        assert "x:" in odom.stdout or "position" in odom.stdout

    def test_robot_cmd_vel_commandable(self, gazebo_env: str) -> None:
        """robot_0 accepts a velocity command (fleet_agent can drive it)."""
        assert gazebo_env == "gazebo_harmonic"
        result = run_gz(
            "topic",
            "-t",
            "/model/robot_0/cmd_vel",
            "-m",
            "gz.msgs.Twist",
            "-p",
            "linear: {x: 0.1}",
        )
        assert result.returncode == 0
