"""tests/simulation fixtures (Phase 1).

`gazebo_env` skips (never fails) when a live Gazebo (gz-sim) server is not
reachable — on this machine ROS 2 / Gazebo are containerized, so the
Gazebo-gated tests report as skipped (honest NOT RUN) until `make sim` runs
on a Gazebo-capable machine with the gz tools available.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

GZ_TIMEOUT_S = 30


def run_gz(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a `gz` CLI command with a bounded timeout."""
    return subprocess.run(  # noqa: S603 - trusted local CLI
        ["gz", *args],
        capture_output=True,
        text=True,
        timeout=GZ_TIMEOUT_S,
    )


@pytest.fixture(scope="session")
def gazebo_env() -> str:
    """Return a live-gazebo marker once a gz-sim server is reachable.

    Skips when the `gz` CLI is missing or no server responds to `gz topic -l`.
    """
    if shutil.which("gz") is None:
        pytest.skip(
            "Gazebo (gz) CLI not found — Phase 1 Gazebo-gated tests NOT RUN on "
            "this machine (ROS 2/Gazebo are containerized). Run `make sim` on a "
            "Gazebo-capable machine to execute them."
        )
    probe = run_gz("topic", "-l")
    if probe.returncode != 0 or "/clock" not in probe.stdout:
        pytest.skip(
            "no live gz-sim server reachable (`gz topic -l` returned no /clock) "
            "— run `make sim` first."
        )
    return "gazebo_harmonic"
