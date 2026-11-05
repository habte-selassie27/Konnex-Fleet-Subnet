"""Evaluations API integration tests — Phase 6 gate (POST /api/v1/evaluations).

Covers: submission stores the evaluation + artifact, retrieval by id, artifact
download, API-key enforcement, and 404 handling.

Status: COMPLETE (Phase 6).
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
        database_url=f"sqlite+aiosqlite:///{tmp_path}/eval.db",
        artifact_dir=tmp_path / "artifacts",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def make_payload(**overrides: object) -> dict[str, object]:
    """A valid evaluation submission payload."""
    payload: dict[str, object] = {
        "policy_id": "nearest",
        "policy_hash": "policy-hash-abc",
        "scenario_id": "warehouse_v1_20tasks",
        "seed": 42,
        "env_version": "v1.0.0",
        "sim_version": "gazebo_harmonic",
        "status": "COMPLETE",
        "final_score": 92.4,
        "artifact_hash": "artifact-hash-xyz",
        "artifact": {
            "policy_id": "nearest",
            "policy_hash": "policy-hash-abc",
            "final_score": 92.4,
            "score_components": {"mission_success": 1.0, "safety": 0.9},
        },
    }
    payload.update(overrides)
    return payload


class TestEvaluationsAPI:
    def test_submit_evaluation(self, client: TestClient) -> None:
        response = client.post("/api/v1/evaluations", json=make_payload(), headers=HEADERS)
        assert response.status_code == 201
        body = response.json()
        assert body["id"]
        assert body["policy_id"] == "nearest"
        assert body["status"] == "COMPLETE"
        assert body["final_score"] == 92.4
        assert body["artifact_hash"] == "artifact-hash-xyz"
        assert body["artifact_url"].startswith("/api/v1/evaluations/")

    def test_get_evaluation(self, client: TestClient) -> None:
        created = client.post("/api/v1/evaluations", json=make_payload(), headers=HEADERS).json()
        response = client.get(f"/api/v1/evaluations/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]
        assert response.json()["final_score"] == 92.4

    def test_artifact_roundtrip(self, client: TestClient) -> None:
        created = client.post("/api/v1/evaluations", json=make_payload(), headers=HEADERS).json()
        response = client.get(created["artifact_url"])
        assert response.status_code == 200
        artifact = response.json()
        assert artifact["policy_id"] == "nearest"
        assert artifact["final_score"] == 92.4
        assert artifact["score_components"]["mission_success"] == 1.0

    def test_submit_requires_api_key(self, client: TestClient) -> None:
        response = client.post("/api/v1/evaluations", json=make_payload())
        assert response.status_code == 401

    def test_get_missing_evaluation_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/evaluations/does-not-exist")
        assert response.status_code == 404

    def test_missing_artifact_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/evaluations/does-not-exist/artifact")
        assert response.status_code == 404
