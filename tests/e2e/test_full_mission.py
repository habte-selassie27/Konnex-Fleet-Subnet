"""Full-mission end-to-end tests — Phase 10 gate (TESTING_PLAN.md §6).

Run with: pytest tests/e2e/ -m e2e   (boots the real backend stack via the
`full_stack` fixture; no Docker/Gazebo required — the headless simulator is
the same execution path the live demo uses).
"""

from __future__ import annotations

import asyncio
import hashlib
import json

import httpx
import pytest

from tests.e2e.conftest import API_KEY, AUTH, wait_for

pytestmark = pytest.mark.e2e


@pytest.fixture
def http(full_stack: str) -> httpx.Client:
    """HTTP client against the live stack; follows trailing-slash redirects."""
    with httpx.Client(base_url=full_stack, follow_redirects=True, timeout=15.0) as client:
        yield client


def mission_status(http: httpx.Client, mission_id: str) -> dict[str, object]:
    """Fetch a mission's current state from the live backend."""
    response = http.get(f"/api/v1/missions/{mission_id}")
    response.raise_for_status()
    return response.json()


def wait_for_mission_end(
    http: httpx.Client, mission_id: str, timeout_s: float = 300.0
) -> dict[str, object]:
    """Block until the mission leaves running, then return its final state."""
    wait_for(
        lambda: mission_status(http, mission_id)["status"] not in {"pending", "running"},
        timeout_s=timeout_s,
    )
    return mission_status(http, mission_id)


def _read_ws_events(url: str, count: int, timeout_s: float = 20.0) -> list[dict[str, object]]:
    """Collect `count` JSON events from a WebSocket endpoint."""

    async def _run() -> list[dict[str, object]]:
        import websockets

        events: list[dict[str, object]] = []
        async with websockets.connect(url) as ws:
            for _ in range(count):
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
                events.append(json.loads(raw))
        return events

    return asyncio.run(_run())


class TestFullMission:
    def test_warehouse_mission_completes(self, http: httpx.Client) -> None:
        """POST /missions (5 robots, 8 tasks, seed 42) -> COMPLETE, >70% done."""
        created = http.post(
            "/api/v1/missions/",
            json={"robot_count": 5, "task_count": 8, "seed": 42, "policy": "nearest"},
            headers=AUTH,
        )
        assert created.status_code == 201
        mission_id = created.json()["id"]

        final = wait_for_mission_end(http, mission_id, timeout_s=300.0)
        assert final["status"] == "complete"
        assert final["completed_tasks"] / final["task_count"] > 0.7
        assert 0.0 <= float(final["popw_score"]) <= 100.0

    def test_benchmark_produces_comparable_results(self) -> None:
        """Two real policies produce comparable, reproducible scores + logs."""
        from pathlib import Path

        import yaml

        from experiments.scripts.run_experiment import run_experiment

        configs: list[dict[str, object]] = [
            {
                "experiment": {"id": "exp_e2e_001", "name": "e2e nearest", "policy": "nearest"},
                "scenario": {
                    "world": "warehouse_v1",
                    "robot_count": 5,
                    "task_count": 10,
                    "seed_range": [2000, 2001],
                    "failure_injection": False,
                },
                "execution": {"time_limit_s": 600},
            },
            {
                "experiment": {
                    "id": "exp_e2e_002",
                    "name": "e2e hungarian",
                    "policy": "hungarian",
                },
                "scenario": {
                    "world": "warehouse_v1",
                    "robot_count": 5,
                    "task_count": 10,
                    "seed_range": [2000, 2001],
                    "failure_injection": False,
                },
                "execution": {"time_limit_s": 600},
            },
        ]
        for config in configs:
            exp_id = str(config["experiment"]["id"])
            # Fresh e2e results dir each run (the runner appends to jsonl).
            results_dir = Path("experiments/results") / exp_id
            if results_dir.exists():
                import shutil

                shutil.rmtree(results_dir)
            tmp = Path("/tmp") / f"{exp_id}.yaml"
            tmp.write_text(yaml.safe_dump(config))
            result = run_experiment(tmp)
            # UNSTABLE is an honest status: executed with high variance
            # (std > 15% of mean) across the 2-seed sample.
            assert result.status in {"COMPLETE", "UNSTABLE"}
            assert 0.0 <= (result.mean_popw_score or 0.0) <= 100.0
            log_path = Path(result.execution_log_path)
            assert log_path.exists()
            assert sum(1 for _ in log_path.open()) == 2  # one line per seed

    def test_validator_reproduces_result(self, http: httpx.Client) -> None:
        """Same (policy, hash, seed) -> scores agree; artifact POSTs to backend."""
        from fleet.task_allocator.nearest import NearestTaskAllocator
        from validator.runner import ValidationRequest, ValidatorRunner, post_evaluation_result
        from validator.sandbox.executor import InProcessPolicyExecutor, PolicyEntry

        weights = b"nearest-policy-weights-v1"
        registry = {"nearest": PolicyEntry(weights=weights, factory=NearestTaskAllocator)}
        runner = ValidatorRunner(InProcessPolicyExecutor(registry))
        request = ValidationRequest(
            policy_id="nearest",
            policy_hash=hashlib.sha256(weights).hexdigest(),
            scenario_id="warehouse_v1_20tasks",
            seed=42,
            env_version="v1.0.0",
            sim_version="gazebo_harmonic",
        )
        first = runner.validate(request)
        second = runner.validate(request)
        assert first.status == second.status == "COMPLETE"
        assert abs(first.score.final - second.score.final) <= 0.5
        assert first.evaluation_artifact.final_score == second.evaluation_artifact.final_score
        assert first.evaluation_artifact.verify()

        # Full-stack round trip: validator -> backend API -> retrievable.
        posted = asyncio.run(post_evaluation_result(str(http.base_url), API_KEY, first))
        evaluation_id = posted["id"]
        fetched = http.get(f"/api/v1/evaluations/{evaluation_id}")
        assert fetched.status_code == 200
        assert abs(fetched.json()["final_score"] - first.score.final) <= 1e-6

    def test_robot_failure_handled_gracefully(self, http: httpx.Client) -> None:
        """A mid-mission failure does not kill the mission; tasks are recovered."""
        created = http.post(
            "/api/v1/missions/",
            json={
                "robot_count": 5,
                "task_count": 10,
                "seed": 7,
                "policy": "nearest",
                "time_limit_s": 600,
            },
            headers=AUTH,
        ).json()
        mission_id = created["id"]

        # Let assignment begin (a robot actually holds a task), then knock out
        # robot_0 for 30 simulated seconds so its task must be recovered.
        def _any_robot_holds_task() -> bool:
            robots = http.get("/api/v1/robots").json()
            return any(r["current_task_id"] for r in robots)

        wait_for(_any_robot_holds_task, timeout_s=30.0, interval_s=1.0)
        failure = http.post(
            "/api/v1/robots/robot_0/fail",
            json={"failure_type": "communication_loss", "duration_s": 30},
            headers=AUTH,
        )
        assert failure.status_code == 200
        assert failure.json()["injected"] is True

        final = wait_for_mission_end(http, mission_id, timeout_s=300.0)
        assert final["status"] == "complete"
        assert final["completed_tasks"] / final["task_count"] > 0.5

    def test_dashboard_shows_live_state(self, http: httpx.Client) -> None:
        """REST + WS expose 5 live robots with distinct positions and tasks."""
        # Start a fresh mission so robots are actively assigned tasks.
        started = http.post(
            "/api/v1/missions/",
            json={"robot_count": 5, "task_count": 20, "seed": 11, "policy": "nearest"},
            headers=AUTH,
        )
        assert started.status_code == 201

        robots = http.get("/api/v1/robots").json()
        assert len(robots) == 5
        positions = {(r["position"]["x"], r["position"]["y"]) for r in robots}
        assert len(positions) == 5

        events = _read_ws_events(
            f"{http.base_url}/ws/fleet?api_key={API_KEY}".replace("http", "ws"), 8
        )
        types = {event["type"] for event in events}
        assert "ROBOT_STATE_UPDATE" in types
        assert "MISSION_UPDATE" in types

        def _some_robot_has_task() -> bool:
            current = http.get("/api/v1/robots").json()
            return any(r["current_task_id"] for r in current)

        wait_for(_some_robot_has_task, timeout_s=60.0, interval_s=1.0)
