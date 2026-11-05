"""Robots API integration tests — Phase 5 failure-injection endpoint.

Covers POST /api/v1/robots/{id}/fail (the Phase 5 gate), plus robot listing,
per-robot state, API-key enforcement, and 404/422 handling.

Status: COMPLETE (Phase 5, headless fleet).
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app

API_KEY = "dev-only-key"
HEADERS = {"X-Fleet-API-Key": API_KEY}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """A TestClient wired to a throwaway SQLite DB + local artifact store."""
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/robots.db",
        artifact_dir=tmp_path / "artifacts",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


class TestRobotsAPI:
    def test_list_robots(self, client: TestClient) -> None:
        response = client.get("/api/v1/robots")
        assert response.status_code == 200
        robots = response.json()
        assert len(robots) == 5
        assert {robot["id"] for robot in robots} == {f"robot_{index}" for index in range(5)}

    def test_get_robot(self, client: TestClient) -> None:
        response = client.get("/api/v1/robots/robot_0")
        assert response.status_code == 200
        assert response.json()["id"] == "robot_0"

    def test_get_unknown_robot_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/robots/ghost")
        assert response.status_code == 404

    def test_fail_robot(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/robots/robot_0/fail",
            json={"failure_type": "communication_loss"},
            headers=HEADERS,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["injected"] is True
        assert body["robot_id"] == "robot_0"
        assert body["failure_type"] == "communication_loss"
        # The fleet continues; robot_0's comm state flips to offline.
        state = client.get("/api/v1/robots/robot_0").json()
        assert state["comm_state"] == "offline"

    def test_fail_robot_requires_api_key(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/robots/robot_0/fail", json={"failure_type": "communication_loss"}
        )
        assert response.status_code == 401

    def test_fail_unknown_robot_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/robots/ghost/fail",
            json={"failure_type": "communication_loss"},
            headers=HEADERS,
        )
        assert response.status_code == 404

    def test_fail_unknown_failure_type_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/robots/robot_0/fail",
            json={"failure_type": "explosion"},
            headers=HEADERS,
        )
        assert response.status_code == 422
