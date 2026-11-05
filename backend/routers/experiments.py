"""Experiments router — GET /experiments/benchmarks.

Serves the measured benchmark rows produced by ``make benchmark`` so the
dashboard can render real numbers instead of a placeholder (AGENTS.md Law 1).

Status: COMPLETE (Phase 3 artifacts, Phase 9 dashboard surface).
"""

from typing import cast

from fastapi import APIRouter, Request

from backend.schemas import BenchmarkResult
from backend.services.benchmark_service import BenchmarkService

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _benchmarks(request: Request) -> BenchmarkService:
    """Resolve the benchmark service from request context."""
    return cast(BenchmarkService, request.app.state.benchmarks)


@router.get("/", response_model=list[BenchmarkResult])
async def list_benchmarks(request: Request) -> list[BenchmarkResult]:
    """List measured benchmark rows, highest PoPW score first."""
    return _benchmarks(request).list_benchmarks()


@router.get("/benchmarks", response_model=list[BenchmarkResult])
async def list_benchmark_rows(request: Request) -> list[BenchmarkResult]:
    """Alias used by the dashboard client."""
    return _benchmarks(request).list_benchmarks()
