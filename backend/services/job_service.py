"""JobService — ARQ queue dispatch for benchmark and evaluation workloads.

Status: COMPLETE (async worker path).
The pool is connected lazily: importing/starting the API never blocks on Redis.
When Redis is unreachable, callers get JobQueueUnavailableError and the API
answers 503 instead of pretending a job was queued (Law 1).
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job, JobStatus

logger = structlog.get_logger(__name__)

BENCHMARK_JOB = "run_benchmark_job"
EVALUATION_JOB = "run_evaluation_job"

SUPPORTED_EVALUATION_POLICIES = frozenset({"nearest", "hungarian", "cost_optimizer"})
MAX_EVALUATION_SEEDS = 50
REDIS_CONNECT_TIMEOUT_S = 1.5


class JobQueueUnavailableError(Exception):
    """Raised when Redis/ARQ cannot accept or answer a job request."""


class UnknownBenchmarkConfigError(Exception):
    """Raised when the requested benchmark config does not exist."""


class InvalidEvaluationRequestError(Exception):
    """Raised when the policy or seed list is not a valid evaluation request."""


class EnqueuePool(Protocol):
    """Minimal ARQ pool surface used for dispatching jobs."""

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> Any:
        """Enqueue a job; returns an object with a job_id."""

    async def ping(self) -> Any:
        """Round-trip Redis to prove the connection is usable."""


class JobLike(Protocol):
    """Minimal ARQ job surface used for status/results."""

    async def status(self) -> JobStatus:
        """Current job state."""

    async def result_info(self) -> Any | None:
        """Completed result, or None while the job is still running."""


@dataclass(frozen=True)
class JobSnapshot:
    """A queued or completed job as exposed by the API."""

    job_id: str
    status: str
    result: Any | None = None


def resolve_benchmark_config(configs_dir: Path, name: str) -> Path:
    """Resolve a config filename under configs_dir, rejecting path traversal."""
    root = configs_dir.resolve()
    candidate = (root / name).resolve()
    if candidate.parent != root or not candidate.is_file():
        raise UnknownBenchmarkConfigError(f"benchmark config not found: {name}")
    if candidate.suffix not in {".yaml", ".yml"}:
        raise UnknownBenchmarkConfigError(f"benchmark config must be YAML: {name}")
    return candidate


class JobService:
    """Dispatches work to the ARQ worker and reads job state back."""

    def __init__(
        self,
        pool: EnqueuePool | None,
        redis_url: str,
        configs_dir: Path,
        job_factory: Any | None = None,
    ) -> None:
        self._pool = pool
        self._redis_url = redis_url
        self._configs_dir = configs_dir
        self._job_factory = job_factory or (lambda job_id, pool: Job(job_id, pool))

    @property
    def available(self) -> bool:
        """True once a pool has been connected."""
        return self._pool is not None

    async def enqueue_benchmark(self, config: str) -> str:
        """Queue a benchmark config from experiments/configs and return its job id."""
        resolve_benchmark_config(self._configs_dir, config)
        pool = await self._pool_or_raise()
        job = await pool.enqueue_job(BENCHMARK_JOB, config)
        if job is None:
            raise JobQueueUnavailableError("worker refused the benchmark job")
        logger.info("benchmark_job_enqueued", job_id=job.job_id, config=config)
        return str(job.job_id)

    async def enqueue_evaluation(self, policy: str, seeds: list[int]) -> str:
        """Queue an evaluation of a built-in policy across the given seeds."""
        if policy not in SUPPORTED_EVALUATION_POLICIES:
            raise InvalidEvaluationRequestError(
                f"unsupported policy {policy!r}; "
                f"choose one of {sorted(SUPPORTED_EVALUATION_POLICIES)}"
            )
        if not seeds:
            raise InvalidEvaluationRequestError("seeds must contain at least one seed")
        if len(seeds) > MAX_EVALUATION_SEEDS:
            raise InvalidEvaluationRequestError(
                f"at most {MAX_EVALUATION_SEEDS} seeds per job, got {len(seeds)}"
            )
        if any(seed < 0 for seed in seeds):
            raise InvalidEvaluationRequestError("seeds must be non-negative integers")

        pool = await self._pool_or_raise()
        job = await pool.enqueue_job(EVALUATION_JOB, policy, list(seeds))
        if job is None:
            raise JobQueueUnavailableError("worker refused the evaluation job")
        logger.info("evaluation_job_enqueued", job_id=job.job_id, policy=policy, seeds=seeds)
        return str(job.job_id)

    async def status(self, job_id: str) -> JobSnapshot | None:
        """Return a job's state and result, or None when it is unknown."""
        pool = await self._pool_or_raise()
        job = self._job_factory(job_id, pool)
        state = await job.status()
        if state is JobStatus.not_found:
            return None
        result = None
        if state is JobStatus.complete:
            info = await job.result_info()
            result = info.result if info is not None else None
        return JobSnapshot(job_id=job_id, status=state.value, result=result)

    async def close(self) -> None:
        """Close the Redis pool (shutdown path)."""
        if self._pool is None:
            return
        closer = getattr(self._pool, "aclose", None) or getattr(self._pool, "close", None)
        if closer is not None:
            await closer()
        self._pool = None

    async def _pool_or_raise(self) -> EnqueuePool:
        """Connect on first use; raise a clear error when Redis is unreachable."""
        if self._pool is not None:
            return self._pool
        try:
            pool = cast(
                EnqueuePool,
                await asyncio.wait_for(
                    create_pool(RedisSettings.from_dsn(self._redis_url)),
                    timeout=REDIS_CONNECT_TIMEOUT_S,
                ),
            )
            await asyncio.wait_for(pool.ping(), timeout=REDIS_CONNECT_TIMEOUT_S)
        except Exception as exc:  # connection refused, DNS, timeout, auth
            logger.warning("job_queue_unavailable", redis_url=self._redis_url, error=str(exc))
            raise JobQueueUnavailableError(
                f"Redis is not reachable at {self._redis_url}: {exc}"
            ) from exc
        self._pool = pool
        logger.info("job_queue_connected", redis_url=self._redis_url)
        return pool
