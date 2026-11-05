"""Jobs API integration tests — queued benchmarks/evaluations.

Status: COMPLETE. The queue itself is faked (no Redis in CI); the real ARQ
round-trip is exercised by running the worker against docker-compose's redis.
"""

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from arq.jobs import JobStatus
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.services.job_service import JobService

API_KEY = "dev-only-key"
HEADERS = {"X-Fleet-API-Key": API_KEY}


class FakeJob:
    """arq job handle returned by the fake pool."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id


class FakePool:
    """Records enqueues; no network."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, function: str, *args: Any, **_kwargs: Any) -> FakeJob:
        self.calls.append((function, args))
        return FakeJob("job-abc")

    async def ping(self) -> bool:
        return True


class FakeArqJob:
    """Reports a completed job with a fixed result."""

    async def status(self) -> JobStatus:
        return JobStatus.complete

    async def result_info(self) -> Any:
        return SimpleNamespace(result={"experiment_id": "exp_001", "status": "COMPLETE"})


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """TestClient with the real DB and a faked ARQ pool."""
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/jobs.db",
        artifact_dir=tmp_path / "artifacts",
        policy_dir=tmp_path / "policies",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        test_client.app.state.jobs = JobService(  # type: ignore[attr-defined]
            FakePool(),
            settings.redis_url,
            settings.benchmark_configs_dir,
            job_factory=lambda _job_id, _pool: FakeArqJob(),
        )
        yield test_client


class TestJobsAPI:
    def test_enqueue_benchmark(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/jobs/benchmark",
            json={"config": "exp_001_nearest.yaml"},
            headers=HEADERS,
        )
        assert response.status_code == 202
        body = response.json()
        assert body["job_id"] == "job-abc"
        assert body["status"] == "queued"

    def test_enqueue_evaluation(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/jobs/evaluation",
            json={"policy": "hungarian", "seeds": [1000, 1001]},
            headers=HEADERS,
        )
        assert response.status_code == 202
        assert response.json()["job_id"] == "job-abc"

    def test_get_completed_job_returns_worker_result(self, client: TestClient) -> None:
        response = client.get("/api/v1/jobs/job-abc")
        assert response.status_code == 200
        assert response.json()["status"] == "complete"
        assert response.json()["result"]["experiment_id"] == "exp_001"

    def test_unknown_config_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/jobs/benchmark",
            json={"config": "does-not-exist.yaml"},
            headers=HEADERS,
        )
        assert response.status_code == 404

    def test_invalid_policy_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/jobs/evaluation",
            json={"policy": "mappo", "seeds": [42]},
            headers=HEADERS,
        )
        assert response.status_code == 422

    def test_enqueue_requires_api_key(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/jobs/benchmark",
            json={"config": "exp_001_nearest.yaml"},
        )
        assert response.status_code == 401

    def test_unreachable_queue_is_503_not_a_fake_job(self, client: TestClient) -> None:
        client.app.state.jobs = JobService(  # type: ignore[attr-defined]
            None,
            "redis://127.0.0.1:1/0",
            client.app.state.settings.benchmark_configs_dir,  # type: ignore[attr-defined]
        )
        response = client.post(
            "/api/v1/jobs/benchmark",
            json={"config": "exp_001_nearest.yaml"},
            headers=HEADERS,
        )
        assert response.status_code == 503
        assert "not reachable" in response.json()["detail"]
