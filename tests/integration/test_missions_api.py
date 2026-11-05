"""Missions API integration tests (Phase 10 demo + e2e contract).

Verifies POST /missions configures and starts a live mission (with the
requested policy honored at runtime) and GET /missions/{id} reports its state
including a live provisional PoPW score.
"""

from __future__ import annotations

from starlette.testclient import TestClient

from backend.main import create_app

API_KEY = "dev-only-key"
AUTH = {"X-Fleet-API-Key": API_KEY}


def _make_client() -> TestClient:
    return TestClient(create_app())


class TestMissionsAPI:
    def test_create_mission_returns_201_with_requested_config(self) -> None:
        with _make_client() as client:
            response = client.post(
                "/api/v1/missions",
                json={
                    "robot_count": 5,
                    "task_count": 20,
                    "seed": 42,
                    "policy": "hungarian",
                    "time_limit_s": 600.0,
                },
                headers=AUTH,
            )
            assert response.status_code == 201
            body = response.json()
            assert body["policy"] == "hungarian"
            assert body["robot_count"] == 5
            assert body["task_count"] == 20
            assert body["status"] in {"pending", "running"}
            assert 0.0 <= body["popw_score"] <= 100.0

    def test_get_mission_returns_live_state(self) -> None:
        with _make_client() as client:
            created = client.post(
                "/api/v1/missions",
                json={"robot_count": 5, "task_count": 20, "seed": 42, "policy": "nearest"},
                headers=AUTH,
            ).json()
            fetched = client.get(f"/api/v1/missions/{created['id']}", headers=AUTH)
            assert fetched.status_code == 200
            body = fetched.json()
            assert body["id"] == created["id"]
            assert body["task_count"] == 20
            assert body["completed_tasks"] >= 0

    def test_get_unknown_mission_returns_404(self) -> None:
        with _make_client() as client:
            response = client.get("/api/v1/missions/does-not-exist", headers=AUTH)
            assert response.status_code == 404

    def test_create_mission_requires_api_key(self) -> None:
        with _make_client() as client:
            response = client.post(
                "/api/v1/missions",
                json={"robot_count": 5, "task_count": 20},
            )
            assert response.status_code == 401

    def test_create_mission_validates_schema(self) -> None:
        with _make_client() as client:
            response = client.post(
                "/api/v1/missions",
                json={"robot_count": 0, "task_count": -1},
                headers=AUTH,
            )
            assert response.status_code == 422

    def test_unknown_policy_returns_422_and_keeps_fleet_alive(self) -> None:
        """An invalid policy must not kill the running mission loop."""
        with _make_client() as client:
            original = client.post(
                "/api/v1/missions",
                json={"robot_count": 5, "task_count": 20, "policy": "nearest"},
                headers=AUTH,
            ).json()
            response = client.post(
                "/api/v1/missions",
                json={"robot_count": 5, "task_count": 20, "policy": "does_not_exist"},
                headers=AUTH,
            )
            assert response.status_code == 422
            # The previously running mission is untouched.
            current = client.get(f"/api/v1/missions/{original['id']}", headers=AUTH)
            assert current.status_code == 200
            assert current.json()["id"] == original["id"]

    def test_new_mission_replaces_policy_at_runtime(self) -> None:
        """POST with a different policy is honored by the running orchestrator."""
        with _make_client() as client:
            client.post(
                "/api/v1/missions",
                json={"robot_count": 5, "task_count": 20, "policy": "cost_optimizer"},
                headers=AUTH,
            )
            from typing import cast

            from fastapi import FastAPI

            from backend.services.fleet_service import FleetAppState, live_popw_score

            fleet = cast(FastAPI, client.app).state.fleet
            assert isinstance(fleet, FleetAppState)
            assert fleet.orchestrator.policy_name == "cost_optimizer"
            assert fleet.mission is not None
            assert 0.0 <= live_popw_score(fleet.mission) <= 100.0
