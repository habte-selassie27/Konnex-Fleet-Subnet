"""E2E fixtures — the real backend stack, booted over HTTP.

Status: COMPLETE (Phase 10).
`make demo` runs the same backend (headless simulator + WS broadcaster +
REST) natively; these tests exercise it end-to-end over real HTTP/WebSocket.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path("/tmp/fleet_e2e_test.db")
API_KEY = "dev-only-key"
AUTH = {"X-Fleet-API-Key": API_KEY}
BASE_URL = ""  # set dynamically by full_stack fixture


def _free_port() -> int:
    """Reserve a free loopback port for the e2e backend (no port conflicts)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for(
    condition: Callable[[], bool], timeout_s: float = 60.0, interval_s: float = 1.0
) -> None:
    """Poll a zero-arg callable until it returns truthy or the timeout hits."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(interval_s)
    raise AssertionError(f"condition not met within {timeout_s}s")


@pytest.fixture(scope="session")
def full_stack() -> Iterator[str]:
    """Boot the real backend (uvicorn) for the duration of the e2e session."""
    DB_PATH.unlink(missing_ok=True)
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{DB_PATH}",
        "FLEET_API_KEY": API_KEY,
        "ROBOT_COUNT": "5",
        "TASK_COUNT": "20",
        "SEED": "42",
        "POLICY": "nearest",
    }
    log_path = Path("/tmp/fleet_e2e_backend.log")
    log_path.unlink(missing_ok=True)
    log_file = log_path.open("w")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for(lambda: _healthy(base_url), timeout_s=30.0, interval_s=0.5)
        import tests.e2e.conftest as _mod

        _mod.BASE_URL = base_url
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()
        DB_PATH.unlink(missing_ok=True)


def _healthy(base_url: str) -> bool:
    try:
        response = httpx.get(f"{base_url}/api/v1/health", timeout=2)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def mission_status(mission_id: str, base_url: str = "") -> dict[str, object]:
    """Fetch a mission's current state from the live backend."""
    url = base_url or BASE_URL
    response = httpx.get(f"{url}/api/v1/missions/{mission_id}", timeout=5)
    response.raise_for_status()
    return response.json()


def wait_for_mission_end(
    mission_id: str, timeout_s: float = 300.0, base_url: str = ""
) -> dict[str, object]:
    """Block until the mission leaves running, then return its final state."""
    url = base_url or BASE_URL

    def _check() -> bool:
        try:
            return mission_status(mission_id, url)["status"] not in {"pending", "running"}
        except Exception:
            return False

    wait_for(_check, timeout_s=timeout_s)
    return mission_status(mission_id, url)
