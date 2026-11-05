"""JobService unit tests — ARQ dispatch, config guards, and job status.

Status: COMPLETE. No Redis required: a fake pool records dispatches and a fake
arq-job object answers status queries.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from arq.jobs import JobStatus

from backend.services.job_service import (
    BENCHMARK_JOB,
    EVALUATION_JOB,
    InvalidEvaluationRequestError,
    JobQueueUnavailableError,
    JobService,
    UnknownBenchmarkConfigError,
)


class FakeJob:
    """Stands in for arq.jobs.Job returned by enqueue_job."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id


class FakePool:
    """Records enqueued jobs without touching Redis."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> FakeJob:
        self.calls.append((function, args, kwargs))
        return FakeJob(f"job-{len(self.calls)}")

    async def ping(self) -> bool:
        return True


class FakeArqJob:
    """Answers status/result_info like arq.jobs.Job."""

    def __init__(self, state: JobStatus, result: Any | None = None) -> None:
        self._state = state
        self._result = result

    async def status(self) -> JobStatus:
        return self._state

    async def result_info(self) -> Any | None:
        if self._state is not JobStatus.complete:
            return None
        return SimpleNamespace(result=self._result)


@pytest.fixture
def configs_dir(tmp_path: Path) -> Path:
    """A configs dir with one valid benchmark config."""
    directory = tmp_path / "configs"
    directory.mkdir()
    (directory / "exp_001_nearest.yaml").write_text("experiment: {}\n", encoding="utf-8")
    (directory / "notes.txt").write_text("not a config\n", encoding="utf-8")
    (tmp_path / "outside.yaml").write_text("experiment: {}\n", encoding="utf-8")
    return directory


def service_for(pool: FakePool, configs_dir: Path, job: Any = None) -> JobService:
    """Build a JobService with the fake pool and an optional fake job object."""
    return JobService(
        pool,
        redis_url="redis://127.0.0.1:1/0",
        configs_dir=configs_dir,
        job_factory=lambda _job_id, _pool: job,
    )


class TestEnqueue:
    def test_benchmark_dispatch(self, configs_dir: Path) -> None:
        pool = FakePool()
        job_id = asyncio.run(
            service_for(pool, configs_dir).enqueue_benchmark("exp_001_nearest.yaml")
        )

        assert job_id == "job-1"
        function, args, _kwargs = pool.calls[0]
        assert function == BENCHMARK_JOB
        assert args == ("exp_001_nearest.yaml",)

    def test_missing_config_is_rejected(self, configs_dir: Path) -> None:
        service = JobService(FakePool(), "redis://x", configs_dir)
        with pytest.raises(UnknownBenchmarkConfigError):
            asyncio.run(service.enqueue_benchmark("missing.yaml"))

    def test_path_traversal_is_rejected(self, configs_dir: Path) -> None:
        service = JobService(FakePool(), "redis://x", configs_dir)
        with pytest.raises(UnknownBenchmarkConfigError):
            asyncio.run(service.enqueue_benchmark("../outside.yaml"))

    def test_non_yaml_is_rejected(self, configs_dir: Path) -> None:
        service = JobService(FakePool(), "redis://x", configs_dir)
        with pytest.raises(UnknownBenchmarkConfigError):
            asyncio.run(service.enqueue_benchmark("notes.txt"))

    def test_evaluation_dispatch(self, configs_dir: Path) -> None:
        pool = FakePool()
        job_id = asyncio.run(
            service_for(pool, configs_dir).enqueue_evaluation("hungarian", [1000, 1001])
        )

        assert job_id == "job-1"
        function, args, _kwargs = pool.calls[0]
        assert function == EVALUATION_JOB
        assert args == ("hungarian", [1000, 1001])

    def test_unknown_policy_is_rejected(self, configs_dir: Path) -> None:
        service = JobService(FakePool(), "redis://x", configs_dir)
        with pytest.raises(InvalidEvaluationRequestError):
            asyncio.run(service.enqueue_evaluation("mappo", [42]))

    def test_empty_and_oversized_seed_lists_are_rejected(self, configs_dir: Path) -> None:
        service = JobService(FakePool(), "redis://x", configs_dir)
        with pytest.raises(InvalidEvaluationRequestError):
            asyncio.run(service.enqueue_evaluation("nearest", []))
        with pytest.raises(InvalidEvaluationRequestError):
            asyncio.run(service.enqueue_evaluation("nearest", list(range(51))))
        with pytest.raises(InvalidEvaluationRequestError):
            asyncio.run(service.enqueue_evaluation("nearest", [-1]))


class TestStatus:
    def test_complete_job_returns_result(self, configs_dir: Path) -> None:
        job = FakeArqJob(JobStatus.complete, {"policy": "nearest", "mean_final_score": 90.1})
        snapshot = asyncio.run(service_for(FakePool(), configs_dir, job).status("job-1"))

        assert snapshot is not None
        assert snapshot.status == "complete"
        assert snapshot.result == {"policy": "nearest", "mean_final_score": 90.1}

    def test_running_job_has_no_result(self, configs_dir: Path) -> None:
        job = FakeArqJob(JobStatus.in_progress)
        snapshot = asyncio.run(service_for(FakePool(), configs_dir, job).status("job-1"))

        assert snapshot is not None
        assert snapshot.status == "in_progress"
        assert snapshot.result is None

    def test_unknown_job_is_none(self, configs_dir: Path) -> None:
        job = FakeArqJob(JobStatus.not_found)
        snapshot = asyncio.run(service_for(FakePool(), configs_dir, job).status("nope"))

        assert snapshot is None


class TestUnavailable:
    def test_unreachable_redis_raises_unavailable(self, configs_dir: Path) -> None:
        # Port 1 is closed: the lazy connect must fail fast, not fabricate a job.
        service = JobService(None, "redis://127.0.0.1:1/0", configs_dir)
        with pytest.raises(JobQueueUnavailableError):
            asyncio.run(service.enqueue_benchmark("exp_001_nearest.yaml"))
        assert service.available is False
