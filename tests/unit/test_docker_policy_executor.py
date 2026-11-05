"""Tests for the Docker policy sandbox (Phase 6).

The transport is faked so the sandbox logic (hash gate, protocol, status
mapping, isolation flags) is covered without Docker. One test runs a real
container when Docker and KONNEX_POLICY_IMAGE are available, otherwise skips.
"""

import json
import os
import subprocess
import sys
import time
from typing import Any

import pytest

from simulation.scenarios.scenario_generator import ScenarioGenerator
from validator.runner import PolicyError, ValidationRequest, ValidatorRunner
from validator.sandbox.docker_executor import (
    ContainerCrashError,
    ContainerSpec,
    ContainerTimeoutError,
    DockerPolicyExecutor,
    DockerUnavailableError,
    SubprocessContainer,
    _assignments_from,
    _robot_payload,
    _task_payload,
    build_docker_run_argv,
)
from validator.sandbox.resource_limits import ResourceLimits

POLICY_HASH = "a" * 64


def make_request(limits: ResourceLimits | None = None) -> ValidationRequest:
    """Build a validation request for the fake policy image."""
    return ValidationRequest(
        policy_id="nearest",
        policy_hash=POLICY_HASH,
        scenario_id="warehouse_v1_20tasks",
        seed=42,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
        resource_limits=limits or ResourceLimits(timeout_s=1.0),
    )


class FakeContainer:
    """In-memory stand-in for a policy container."""

    def __init__(
        self,
        policy_hash: str = POLICY_HASH,
        assign_reply: dict[str, Any] | None = None,
        raise_on_assign: Exception | None = None,
        metadata_delay_s: float = 0.0,
        exit_code: int = 0,
    ) -> None:
        self._policy_hash = policy_hash
        self._assign_reply = assign_reply
        self._raise_on_assign = raise_on_assign
        self._metadata_delay_s = metadata_delay_s
        self._exit_code = exit_code
        self.messages: list[dict[str, Any]] = []
        self.closed = False

    def request(self, message: dict[str, Any]) -> dict[str, Any]:
        self.messages.append(message)
        op = message["op"]
        if op == "metadata":
            if self._metadata_delay_s:
                time.sleep(self._metadata_delay_s)
            return {"policy_hash": self._policy_hash}
        if op == "assign":
            if self._raise_on_assign is not None:
                raise self._raise_on_assign
            return self._assign_reply or {"assignments": []}
        if op == "shutdown":
            return {}
        raise AssertionError(f"unexpected op {op!r}")

    def close(self, force: bool = False) -> int:
        self.closed = True
        self.close_forced = force
        return self._exit_code


def make_executor(
    container: FakeContainer, limits: ResourceLimits | None = None
) -> DockerPolicyExecutor:
    """Executor wired to a fake container (no Docker required)."""
    return DockerPolicyExecutor(
        "fake/policy:latest",
        limits or ResourceLimits(timeout_s=1.0),
        container_factory=lambda _spec, _timeout: container,
    )


# ─── Isolation flags ──────────────────────────────────────────────────────


def test_run_argv_applies_isolation_and_limits() -> None:
    spec = ContainerSpec(
        image="fleet/policy:1",
        limits=ResourceLimits(cpu=1.5, memory_mb=2048),
        name="konnex-policy-test",
    )
    argv = build_docker_run_argv(spec)

    assert argv[:3] == ["docker", "run", "--rm"]
    assert argv[-1] == "fleet/policy:1"
    joined = " ".join(argv)
    assert "--network none" in joined
    assert "--read-only" in joined
    assert "--cap-drop ALL" in joined
    assert "--security-opt no-new-privileges" in joined
    assert "--cpus 1.5" in joined
    assert "--memory 2048m" in joined
    assert "--memory-swap 2048m" in joined


def test_network_is_opt_in_only() -> None:
    spec = ContainerSpec(
        image="fleet/policy:1",
        limits=ResourceLimits(network_enabled=True),
        name="c",
    )
    argv = build_docker_run_argv(spec)
    assert "none" not in argv
    assert "bridge" in argv


# ─── Wire format ──────────────────────────────────────────────────────────


def test_payloads_omit_simulator_internals() -> None:
    scenario = ScenarioGenerator().generate(seed=7, robot_count=5, task_count=20)
    from robotics.adapters.simulation import SimulationRobotAdapter

    robot = SimulationRobotAdapter(
        robot_id="robot_0",
        start_position=scenario.robot_positions[0],
        battery_pct=0.9,
    ).get_state()

    robot_payload = _robot_payload(robot)
    task_payload = _task_payload(scenario.tasks[0])

    assert set(robot_payload) == {
        "id",
        "x",
        "y",
        "orientation",
        "battery_pct",
        "nav_state",
        "comm_state",
        "current_task_id",
    }
    assert set(task_payload) == {"id", "pickup", "delivery", "priority"}
    assert json.dumps(robot_payload)  # JSON-serializable


def test_assignments_parse_distance_and_reject_malformed() -> None:
    parsed = _assignments_from(
        {"assignments": [{"robot_id": "robot_0", "task_id": "task_001", "distance": 3.5}]}
    )
    assert parsed[0].robot_id == "robot_0"
    assert parsed[0].distance == 3.5

    with pytest.raises(ContainerCrashError):
        _assignments_from({})
    with pytest.raises(ContainerCrashError) as excinfo:
        _assignments_from({"assignments": [{"robot_id": 1, "task_id": "t"}]})
    assert excinfo.value.status == "INVALID_ACTIONS"


# ─── Hash gate ────────────────────────────────────────────────────────────


def test_hash_mismatch_is_rejected_before_mission() -> None:
    container = FakeContainer(policy_hash="b" * 64)
    with pytest.raises(PolicyError):
        make_executor(container).execute(make_request())
    assert container.closed is True
    assert [m["op"] for m in container.messages] == ["metadata"]


def test_missing_hash_is_a_policy_crash() -> None:
    container = FakeContainer(policy_hash="")
    result = make_executor(container).execute(make_request())
    assert result.status == "POLICY_CRASH"
    assert result.error_message is not None


def test_two_sandboxes_produce_identical_scores() -> None:
    """Reproducibility gate still holds when the policy runs in a container."""

    def run() -> float:
        container = FakeContainer(assign_reply={"assignments": []})
        request = make_request(limits=ResourceLimits(timeout_s=5.0))
        return ValidatorRunner(make_executor(container)).validate(request).score.final

    assert abs(run() - run()) <= 0.5


# ─── Status mapping ───────────────────────────────────────────────────────


def test_timeout_maps_to_zero_score() -> None:
    container = FakeContainer(metadata_delay_s=0.5)
    result = make_executor(container).execute(make_request(ResourceLimits(timeout_s=0.05)))
    assert result.status == "TIMEOUT"
    assert result.tasks_completed == 0


def test_protocol_violation_maps_to_policy_crash() -> None:
    container = FakeContainer(raise_on_assign=ContainerCrashError("garbage reply"))
    result = make_executor(container).execute(make_request())
    assert result.status == "POLICY_CRASH"


def test_oom_kill_maps_to_resource_exceeded() -> None:
    container = FakeContainer(assign_reply={"assignments": []}, exit_code=137)
    result = make_executor(container).execute(make_request())
    assert result.status == "RESOURCE_EXCEEDED"


def test_unknown_robot_assignment_maps_to_invalid_actions() -> None:
    container = FakeContainer(
        assign_reply={"assignments": [{"robot_id": "ghost", "task_id": "task_001"}]}
    )
    result = make_executor(container).execute(make_request())
    assert result.status == "INVALID_ACTIONS"


def test_sandbox_requires_an_image() -> None:
    with pytest.raises(ValueError):
        DockerPolicyExecutor("")


# ─── Real container (opt-in) ──────────────────────────────────────────────


def _policy_image() -> str | None:
    return os.environ.get("KONNEX_POLICY_IMAGE")


@pytest.mark.skipif(not _policy_image(), reason="KONNEX_POLICY_IMAGE not set")
def test_real_container_end_to_end() -> None:
    """Run a real policy image; requires KONNEX_POLICY_IMAGE and Docker."""
    if not DockerPolicyExecutor.is_available():
        pytest.skip("docker daemon unavailable")

    image = _policy_image()
    assert image is not None
    spec = ContainerSpec(
        image=image, limits=ResourceLimits(timeout_s=30.0), name="konnex-policy-e2e"
    )
    transport = SubprocessContainer(spec, timeout_s=30.0)
    try:
        metadata = transport.request({"op": "metadata"})
    finally:
        transport.close()
    assert isinstance(metadata.get("policy_hash"), str)


def test_subprocess_container_reports_startup_failure_as_crash() -> None:
    """A start-up failure must surface as a crash, not an exception.

    An unparseable image reference makes `docker run` exit immediately, so this
    exercises the EOF path without waiting on a registry pull.
    """
    if not DockerPolicyExecutor.is_available():
        pytest.skip("docker daemon unavailable")

    spec = ContainerSpec(
        image="not a valid image reference!!",
        limits=ResourceLimits(timeout_s=10.0),
        name="konnex-policy-invalid",
    )
    transport = SubprocessContainer(spec, timeout_s=5.0)
    try:
        with pytest.raises(ContainerCrashError):
            transport.request({"op": "metadata"})
    finally:
        transport.close(force=True)


ECHO_POLICY = """
import json, sys
for line in sys.stdin:
    message = json.loads(line)
    if message["op"] == "metadata":
        reply = {"policy_hash": "a" * 64}
    elif message["op"] == "assign":
        reply = {"assignments": []}
    else:
        reply = {}
    sys.stdout.write(json.dumps(reply) + "\\n")
    sys.stdout.flush()
"""


def _spec() -> ContainerSpec:
    return ContainerSpec(
        image="fleet/policy:1",
        limits=ResourceLimits(timeout_s=2.0),
        name="konnex-policy-pipes",
    )


def test_transport_round_trips_over_real_pipes() -> None:
    transport = SubprocessContainer(
        _spec(), timeout_s=10.0, argv=[sys.executable, "-c", ECHO_POLICY]
    )
    try:
        assert transport.request({"op": "metadata"}) == {"policy_hash": "a" * 64}
        assert transport.request({"op": "assign", "robots": [], "tasks": []}) == {"assignments": []}
    finally:
        assert transport.close() == 0


def test_transport_times_out_on_silent_container() -> None:
    transport = SubprocessContainer(
        _spec(), timeout_s=0.3, argv=[sys.executable, "-c", "import time; time.sleep(30)"]
    )
    try:
        with pytest.raises(ContainerTimeoutError):
            transport.request({"op": "metadata"})
    finally:
        transport.close(force=True)


def test_transport_reports_immediate_exit_as_crash() -> None:
    transport = SubprocessContainer(_spec(), timeout_s=5.0, argv=[sys.executable, "-c", "pass"])
    try:
        with pytest.raises(ContainerCrashError) as excinfo:
            transport.request({"op": "metadata"})
        assert "exit code 0" in str(excinfo.value)
    finally:
        transport.close(force=True)


def test_transport_rejects_non_json_output() -> None:
    transport = SubprocessContainer(
        _spec(),
        timeout_s=5.0,
        argv=[sys.executable, "-c", "print('not json', flush=True); input()"],
    )
    try:
        with pytest.raises(ContainerCrashError):
            transport.request({"op": "metadata"})
    finally:
        transport.close(force=True)


def test_is_available_reports_false_for_missing_binary() -> None:
    assert DockerPolicyExecutor.is_available("konnex-not-a-binary") is False


def test_unavailable_docker_raises_instead_of_silently_degrading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing daemon must be an error, never a silent zero-score pass."""
    monkeypatch.setattr(
        DockerPolicyExecutor, "is_available", staticmethod(lambda _bin="docker": False)
    )
    executor = DockerPolicyExecutor("fleet/policy:1")
    with pytest.raises(DockerUnavailableError):
        executor.execute(make_request())
