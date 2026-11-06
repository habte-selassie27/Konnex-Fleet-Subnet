"""API router aggregation.

Status: COMPLETE (Phase 6).
"""

from fastapi import APIRouter

from backend.routers import (
    evaluations,
    experiments,
    health,
    missions,
    payments,
    robots,
    validators,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(robots.router)
api_router.include_router(missions.router)
api_router.include_router(evaluations.router)
api_router.include_router(payments.router)
api_router.include_router(experiments.router)
api_router.include_router(validators.router)
