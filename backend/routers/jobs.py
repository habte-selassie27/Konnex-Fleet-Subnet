"""Jobs router — queue benchmarks/evaluations on the ARQ worker.

Status: COMPLETE — the worker in backend/workers/arq_worker.py runs these
functions. With Redis unreachable the endpoints answer 503; they never report a
queued job that does not exist.
"""

from typing import cast

from fastapi import APIRouter, HTTPException, Request, status

from backend.schemas import BenchmarkJobRequest, EvaluationJobRequest, JobResponse
from backend.security import require_api_key
from backend.services.job_service import (
    InvalidEvaluationRequestError,
    JobQueueUnavailableError,
    JobService,
    UnknownBenchmarkConfigError,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _jobs(request: Request) -> JobService:
    """Resolve the job service from request context."""
    return cast(JobService, request.app.state.jobs)


@router.post(
    "/benchmark",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobResponse,
    summary="Queue a benchmark config on the ARQ worker",
)
async def enqueue_benchmark(body: BenchmarkJobRequest, request: Request) -> JobResponse:
    """Queue experiments/configs/<config>; results land in experiments/results."""
    require_api_key(request)
    try:
        job_id = await _jobs(request).enqueue_benchmark(body.config)
    except UnknownBenchmarkConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except JobQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job_id=job_id, status="queued")


@router.post(
    "/evaluation",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobResponse,
    summary="Queue a built-in policy evaluation on the ARQ worker",
)
async def enqueue_evaluation(body: EvaluationJobRequest, request: Request) -> JobResponse:
    """Queue evaluation; the worker persists EvaluationRecord rows + artifacts."""
    require_api_key(request)
    try:
        job_id = await _jobs(request).enqueue_evaluation(body.policy, body.seeds)
    except InvalidEvaluationRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except JobQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job_id=job_id, status="queued")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, request: Request) -> JobResponse:
    """Current job state; includes the worker's return value once complete."""
    try:
        snapshot = await _jobs(request).status(job_id)
    except JobQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return JobResponse(
        job_id=snapshot.job_id,
        status=snapshot.status,
        result=snapshot.result,
    )
