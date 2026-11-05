"""Policies API integration tests — miner-facing policy registry.

Covers: server-side SHA-256 verification, declared-hash mismatch rejection,
idempotent resubmission, artifact roundtrip, listing, API-key enforcement,
and 404 handling.
"""

import base64
import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app

API_KEY = "dev-only-key"
HEADERS = {"X-Fleet-API-Key": API_KEY}
ARTIFACT = b"class Nearest:\n    pass\n"


def sha256_hex(payload: bytes) -> str:
    """Lowercase hex SHA-256 of the given bytes."""
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """A TestClient wired to a throwaway SQLite DB + policy artifact dir."""
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/policies.db",
        artifact_dir=tmp_path / "artifacts",
        policy_dir=tmp_path / "policies",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def make_payload(**overrides: object) -> dict[str, object]:
    """A valid policy submission payload (declared hash matches ARTIFACT)."""
    payload: dict[str, object] = {
        "name": "nearest",
        "version": "0.1.0",
        "author": "miner-1",
        "algorithm": "nearest",
        "policy_hash": sha256_hex(ARTIFACT),
        "artifact_base64": base64.b64encode(ARTIFACT).decode(),
    }
    payload.update(overrides)
    return payload


class TestPoliciesAPI:
    def test_submit_policy_verifies_hash(self, client: TestClient) -> None:
        response = client.post("/api/v1/policies/", json=make_payload(), headers=HEADERS)
        assert response.status_code == 201
        body = response.json()
        assert body["id"]
        assert body["name"] == "nearest"
        assert body["status"] == "VERIFIED"
        assert body["policy_hash"] == sha256_hex(ARTIFACT)
        assert body["size_bytes"] == len(ARTIFACT)
        assert body["duplicate"] is False
        assert body["artifact_url"].startswith("/api/v1/policies/")

    def test_submit_without_declared_hash_computes_it(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/policies/", json=make_payload(policy_hash=""), headers=HEADERS
        )
        assert response.status_code == 201
        assert response.json()["policy_hash"] == sha256_hex(ARTIFACT)

    def test_hash_mismatch_is_rejected_and_not_stored(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/policies/",
            json=make_payload(policy_hash="0" * 64),
            headers=HEADERS,
        )
        assert response.status_code == 422
        assert "does not match" in response.json()["detail"]
        assert client.get("/api/v1/policies/").json() == []

    def test_invalid_base64_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/policies/",
            json=make_payload(artifact_base64="not base64!!"),
            headers=HEADERS,
        )
        assert response.status_code == 422

    def test_resubmission_is_idempotent(self, client: TestClient) -> None:
        first = client.post("/api/v1/policies/", json=make_payload(), headers=HEADERS).json()
        second = client.post("/api/v1/policies/", json=make_payload(), headers=HEADERS).json()
        assert second["id"] == first["id"]
        assert second["duplicate"] is True
        assert len(client.get("/api/v1/policies/").json()) == 1

    def test_artifact_roundtrip_returns_submitted_bytes(self, client: TestClient) -> None:
        created = client.post("/api/v1/policies/", json=make_payload(), headers=HEADERS).json()
        response = client.get(created["artifact_url"])
        assert response.status_code == 200
        assert response.content == ARTIFACT
        assert sha256_hex(response.content) == created["policy_hash"]

    def test_get_policy(self, client: TestClient) -> None:
        created = client.post("/api/v1/policies/", json=make_payload(), headers=HEADERS).json()
        response = client.get(f"/api/v1/policies/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_submit_requires_api_key(self, client: TestClient) -> None:
        response = client.post("/api/v1/policies/", json=make_payload())
        assert response.status_code == 401

    def test_missing_policy_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/policies/does-not-exist").status_code == 404
        assert client.get("/api/v1/policies/does-not-exist/artifact").status_code == 404
