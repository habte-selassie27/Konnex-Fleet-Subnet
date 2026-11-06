"""FleetPaymentBridge — live fleet telemetry drives real agent payments.

Watches the running mission's robot states and turns genuine operational
events into the same quote -> authorize -> execute flow the REST API exposes:

    robot FAILED (nav_state == failed)                 -> maintenance_required
    battery <= PAYMENT_LOW_BATTERY_THRESHOLD           -> charging_required

Each (robot, event-type) episode pays at most once. The arming state clears
when the condition resolves (battery recovers, robot returns to service) or
when a new mission starts, so one episode can never drain the daily budget
with duplicate payments.

The bridge never fabricates events: every payment it records is derived from
robot state the orchestrator actually reported during a real run (Law 1).
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time as _time
from pathlib import Path

import structlog

from backend.config import Settings
from backend.services.fleet_service import FleetAppState
from validator.scoring.engine import MissionResult, PoPWScoringEngine
from backend.services.payment_service import PaymentAppState
from payments.models import EventType, FleetEvent, PaymentRequest
from robotics.models.robot_state import NavState, RobotState

logger = structlog.get_logger(__name__)


class FleetPaymentBridge:
    """Polls fleet telemetry and executes policy-gated agent payments."""

    def __init__(
        self,
        fleet: FleetAppState,
        payments: PaymentAppState,
        settings: Settings,
    ) -> None:
        self._fleet = fleet
        self._payments = payments
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._armed: dict[str, EventType] = {}
        self._mission_id: str | None = None
        self._mission_recorded: bool = False
        self._scorer = PoPWScoringEngine()

    # ─── Lifecycle ───────────────────────────────────────────────────────

    @property
    def armed(self) -> dict[str, EventType]:
        """Robots with an open payment episode (robot id -> event type)."""
        return dict(self._armed)

    @property
    def running(self) -> bool:
        """True while the polling task is alive."""
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start the polling loop (no-op if already running)."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="fleet-payment-bridge")
        logger.info(
            "payment_bridge_started",
            interval_s=self._settings.payment_bridge_interval_s,
            low_battery_threshold=self._settings.payment_low_battery_threshold,
            fleet_id=self._settings.payment_fleet_id,
        )

    async def stop(self) -> None:
        """Stop the polling loop and wait for it to unwind."""
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("payment_bridge_stopped")

    # ─── Loop ────────────────────────────────────────────────────────────

    async def _run(self) -> None:
        interval = max(0.2, self._settings.payment_bridge_interval_s)
        while True:
            await asyncio.sleep(interval)
            try:
                await self.tick()
            except Exception as exc:  # noqa: BLE001 — one bad tick must not kill the bridge
                logger.error("payment_bridge_tick_failed", error=str(exc))

    async def tick(self) -> None:
        """One evaluation pass over the live fleet state."""
        state = self._fleet.orchestrator.get_fleet_state()
        if state.mission_id is None:
            return
        if state.mission_id != self._mission_id:
            # New mission: previous arming no longer applies.
            self._mission_id = state.mission_id
            self._armed.clear()
            self._mission_recorded = False

        for robot in state.robots:
            event_type = self._classify(robot)
            if event_type is None:
                if self._armed.pop(robot.id, None) is not None:
                    logger.info(
                        "payment_bridge_episode_closed",
                        robot_id=robot.id,
                        battery_pct=round(robot.battery_pct, 3),
                    )
                continue
            if self._armed.get(robot.id) == event_type:
                continue  # already paid for this episode
            self._armed[robot.id] = event_type
            await self._handle(robot, event_type)

        # Capture completed live mission as a real-metrics benchmark row.
        if (state.total_tasks and state.completed_tasks >= state.total_tasks
                and state.mission_status == "complete"
                and not self._mission_recorded):
            self._mission_recorded = True
            self._record_live_mission(state)

    def _record_live_mission(self, state) -> None:
        """Write a real-metrics benchmark row for a completed live mission."""
        try:
            mission = self._fleet.orchestrator.get_mission()
            policy = self._fleet.orchestrator.policy_name
            completed = state.completed_tasks
            total = state.total_tasks
            collisions = state.collision_count
            elapsed = state.elapsed_seconds
            time_limit = state.time_limit_s
            energy = getattr(mission, "energy_consumed", 0.0) if mission else 0.0
            failure_count = getattr(mission, "failure_count", 0) if mission else 0
            robot_count = len(state.robots)

            result = MissionResult(
                tasks_completed=completed,
                tasks_total=total,
                elapsed_s=elapsed,
                time_limit_s=time_limit,
                collision_count=collisions,
                energy_consumed=energy,
                energy_budget=robot_count * 100.0,
                failure_count=failure_count,
            )
            score = self._scorer.score(result).final

            # Per-robot contribution breakdown (real, from tracked mission state).
            per_robot = {}
            if mission is not None:
                for task in getattr(mission, "tasks", []) or []:
                    rid = getattr(task, "assigned_robot_id", None) or getattr(task, "assigned_robot", None)
                    if not rid:
                        continue
                    bucket = per_robot.setdefault(rid, {"robot_id": rid, "tasks_completed": 0, "tasks_assigned": 0})
                    bucket["tasks_assigned"] += 1
                    if getattr(task, "status", None) == "completed":
                        bucket["tasks_completed"] += 1
            # Merge live robot state (battery/position) for context.
            robot_state_by_id = {getattr(r, "id", None): r for r in (state.robots or [])}
            per_robot_list = []
            for rid, info in per_robot.items():
                rs = robot_state_by_id.get(rid)
                per_robot_list.append({
                    "robot_id": rid,
                    "tasks_completed": info["tasks_completed"],
                    "tasks_assigned": info["tasks_assigned"],
                    "battery_pct": getattr(rs, "battery_pct", None) if rs is not None else None,
                    "final_nav_state": getattr(getattr(rs, "nav_state", None), "value", None) if rs is not None else None,
                })

            try:
                git_commit = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
                ).decode().strip()
            except Exception:
                git_commit = "UNKNOWN"

            payload = {
                "experiment_id": f"live_{state.mission_id}",
                "policy": policy,
                "scenario_id": getattr(mission, "scenario_id", "") if mission else "",
                "robot_count": robot_count,
                "n_runs": 1,
                "mean_popw_score": score,
                "std_popw_score": 0.0,
                "mean_success_rate": (completed / total) if total else 0.0,
                "std_success_rate": 0.0,
                "mean_collision_count": float(collisions),
                "std_collision_count": 0.0,
                "mean_completion_time_s": elapsed,
                "std_completion_time_s": 0.0,
                "status": "COMPLETE",
                "harness": "live_mission",
                "per_robot": per_robot_list,
                "seed_range": [getattr(mission, "seed", 0) if mission else 0],
                "ran_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
                "git_commit": git_commit,
            }

            out_dir = Path("experiments/results/live_missions") / str(state.mission_id)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "result.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
            import structlog
            structlog.get_logger(__name__).info("live_mission_recorded", mission_id=state.mission_id, score=score)
        except Exception as exc:  # noqa: BLE001
            import structlog
            structlog.get_logger(__name__).warning("live_mission_record_failed", error=str(exc))

    # ─── Decision + payment ──────────────────────────────────────────────

    def _classify(self, robot: RobotState) -> EventType | None:
        """Map robot telemetry to the payment event it implies (None = no event)."""
        if robot.nav_state == NavState.FAILED:
            return EventType.MAINTENANCE_REQUIRED
        if robot.battery_pct <= self._settings.payment_low_battery_threshold:
            return EventType.CHARGING_REQUIRED
        return None

    async def _handle(self, robot: RobotState, event_type: EventType) -> None:
        """Quote -> policy-authorize -> execute one live payment."""
        note = (
            f"Live telemetry: {robot.id} nav_state={robot.nav_state.value}, "
            f"battery={robot.battery_pct:.0%}"
        )
        event = FleetEvent(
            vehicle_id=robot.id,
            event_type=event_type,
            battery_pct=robot.battery_pct,
            note=note,
        )
        decision = self._payments.core.quote(event)
        if decision.no_action or decision.selected is None:
            logger.info(
                "payment_bridge_no_action",
                robot_id=robot.id,
                event_type=event_type.value,
                rationale=decision.rationale,
            )
            return

        intent, policy = self._payments.core.authorize(
            PaymentRequest(
                fleet_id=self._settings.payment_fleet_id,
                vehicle_id=decision.vehicle_id,
                provider_id=decision.selected_provider_id,
                service=decision.service,
                amount_usdc=decision.amount_usdc,
                reason=(
                    f"{decision.service.value} required for {robot.id} "
                    f"(battery {robot.battery_pct:.0%}, nav_state={robot.nav_state.value})"
                ),
                max_allowed_usdc=self._settings.payment_max_tx_usdc,
                decision_rationale=decision.rationale,
            )
        )
        if not policy.approved:
            logger.warning(
                "payment_bridge_rejected",
                robot_id=robot.id,
                event_type=event_type.value,
                amount_usdc=decision.amount_usdc,
                reasons=policy.reasons,
            )
            return

        transaction = await self._payments.execute(intent.id)
        logger.info(
            "payment_bridge_paid",
            robot_id=robot.id,
            event_type=event_type.value,
            provider=transaction.provider_name,
            amount_usdc=transaction.amount_usdc,
            tx_hash=transaction.tx_hash,
            settlement=transaction.settlement_status,
            is_mock=transaction.is_mock,
        )
