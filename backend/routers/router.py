"""API router aggregation.

Status: COMPLETE (Phase 6).
"""

from fastapi import APIRouter

from backend.routers import evaluations, health, missions, payments, robots

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(robots.router)
api_router.include_router(missions.router)
api_router.include_router(evaluations.router)
api_router.include_router(payments.router)
