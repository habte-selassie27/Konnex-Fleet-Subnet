"""FastAPI application entrypoint.

Status: COMPLETE (Phase 9) — app factory, lifespan (DB tables + fleet loop +
WebSocket broadcaster), CORS, REST routers under /api/v1 and WS /ws/fleet.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.ws.fleet import FleetBroadcaster
from backend.api.ws.fleet import router as fleet_ws_router
from backend.config import Settings
from backend.db.database import Database
from backend.routers.router import api_router
from backend.services.evaluation_service import EvaluationService
from backend.services.fleet_payment_bridge import FleetPaymentBridge
from backend.services.fleet_service import FleetAppState
from backend.services.payment_service import PaymentAppState
from backend.services.storage_service import ArtifactStore


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Startup: tables + fleet loop + WS broadcaster; shutdown: stop all."""
        await app.state.db.create_all()
        # Optional ROS 2 bridge (SIM_MODE=gazebo). Started BEFORE the fleet so
        # FleetAppState can build GazeboRobotAdapter robots over live topics
        # (Phase 2 wiring). When rclpy is absent the bridge reports not-running
        # and the fleet stays on the deterministic headless adapter.
        app.state.ros_bridge = None
        if config.sim_mode == "gazebo":
            from backend.ros.bridge import ROSBridge

            bridge = ROSBridge(domain_id=config.ros_domain_id)
            if bridge.start():
                app.state.ros_bridge = bridge
                app.state.fleet.attach_bridge(bridge)
        await app.state.fleet.start()
        app.state.broadcaster = FleetBroadcaster(app.state.fleet, config)
        app.state.broadcaster.start()
        # Live fleet -> payment bridge: turns real mission telemetry into
        # policy-gated agent payments (PAYMENT_LIVE_BRIDGE=false to disable).
        app.state.payment_bridge = FleetPaymentBridge(app.state.fleet, app.state.payments, config)
        if config.payment_live_bridge:
            await app.state.payment_bridge.start()
        yield
        await app.state.payment_bridge.stop()
        if app.state.ros_bridge is not None:
            app.state.ros_bridge.stop()
        await app.state.broadcaster.stop()
        await app.state.fleet.stop()
        await app.state.db.dispose()

    app = FastAPI(
        title="Konnex Fleet Intelligence API",
        version=config.version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db = Database(config.database_url)
    store = ArtifactStore(config.artifact_dir)
    app.state.settings = config
    app.state.db = db
    app.state.evaluations = EvaluationService(db, store)
    app.state.fleet = FleetAppState(config)
    app.state.payments = PaymentAppState(db, config)

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(fleet_ws_router, prefix="/ws")
    return app


app = create_app()
