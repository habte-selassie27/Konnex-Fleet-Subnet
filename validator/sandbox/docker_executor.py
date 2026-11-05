"""DockerPolicyExecutor — containerized policy execution (production sandbox).

Status: COMPLETE (Phase 6 sandbox). Executes a submitted policy inside an
isolated container, verifies its weights hash before the mission starts, and
drives the *same* deterministic mission loop as the in-process executor
(`validator/sandbox/executor.py::run_headless_mission`), so a sandboxed
evaluation and a headless one are directly comparable.

Isolation applied to every container (AGENTS.md §5.2 anti-gaming table):
    --network none            no outbound calls, no data exfiltration
    --read-only + /tmp tmpfs  policy cannot persist state between runs
    --cap-drop ALL, no-new-privileges
    --cpus / --memory         4G + 2 CPU by default, OOM-killed at the limit
    wall-clock deadline       exceeded -> TIMEOUT, container killed

Container protocol (newline-delimited JSON on stdin/stdout, no sockets):

    -> {"op": "metadata"}
    <- {"policy_hash": "<sha256 hex>", "name": "<optional>"}

    -> {"op": "assign", "robots": [...], "tasks": [...]}
    <- {"assignments": [{"robot_id": "robot_0", "task_id": "task_003"}]}

    -> {"op": "shutdown"}                      (optional; stdin close is enough)

A container that exits, writes malformed JSON, or dies from the memory limit is
mapped to POLICY_CRASH / INVALID_ACTIONS / RESOURCE_EXCEEDED and scored 0.0 —
the validator never crashes because of a bad policy (BUILD.md §8).

The submitter supplies the image; see `docs/validation.md` for the contract.
"""

from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from robotics.models.robot_state import RobotState
from robotics.models.task import Assignment, Task
from simulation.scenarios.scenario_generator import ScenarioGenerator
from validator.runner import PolicyError, PolicyExecutionResult, ValidationRequest
from validator.sandbox.executor import (
    InvalidPolicyActionsError,
    run_headless_mission,
)
from validator.sandbox.resource_limits import ResourceLimits

logger = structlog.get_logger(__name__)

_ROBOT_COUNT = 5
_TASK_COUNT = 20
_MAX_MESSAGE_BYTES = 1 << 20  # 1 MiB — a policy must not stream unbounded output


class DockerUnavailableError(RuntimeError):
    """Docker is not installed or the daemon is unreachable."""


class ContainerTimeoutError(RuntimeError):
    """The policy container did not answer within the deadline."""


class ContainerCrashError(RuntimeError):
    """The policy container failed, exited, or broke the wire protocol."""

    def __init__(self, message: str, status: str = "POLICY_CRASH") -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class ContainerSpec:
    """Everything needed to launch one isolated policy container."""

    image: str
    limits: ResourceLimits
    name: str


class ContainerTransport(Protocol):
    """JSON-lines request/response channel to a running policy container."""

    def request(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send one message and return the matching reply."""
        ...

    def close(self, force: bool = False) -> int | None:
        """Stop the container; returns its exit code when known."""
        ...


def build_docker_run_argv(spec: ContainerSpec, docker_bin: str = "docker") -> list[str]:
    """Build the hardened `docker run` command for a policy container."""
    limits = spec.limits
    argv = [
        docker_bin,
        "run",
        "--rm",
        "--interactive",
        "--name",
        spec.name,
        "--read-only",
        "--tmpfs",
        # In-container mount point, not a host temp directory (B108 false positive).
        "/tmp:rw,size=64m",  # nosec B108
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--cpus",
        str(limits.cpu),
        "--memory",
        f"{limits.memory_mb}m",
        "--memory-swap",
        f"{limits.memory_mb}m",
    ]
    if limits.network_enabled:  # pragma: no cover - opt-in, off by default
        argv += ["--network", "bridge"]
    else:
        argv += ["--network", "none"]
    argv.append(spec.image)
    return argv


class SubprocessContainer:
    """`docker run -i` transport speaking JSON lines over stdin/stdout."""

    def __init__(
        self,
        spec: ContainerSpec,
        timeout_s: float,
        docker_bin: str = "docker",
        argv: list[str] | None = None,
    ) -> None:
        self._deadline = time.monotonic() + max(0.0, timeout_s)
        self._buffer = b""
        self._proc = subprocess.Popen(  # noqa: S603 - argv is fully constructed above
            argv if argv is not None else build_docker_run_argv(spec, docker_bin),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if self._proc.stdin is None or self._proc.stdout is None:  # pragma: no cover
            raise DockerUnavailableError("failed to open container pipes")

    # ─── Transport protocol ───────────────────────────────────────────────

    def request(self, message: dict[str, Any]) -> dict[str, Any]:
        """Write one message and read the matching reply."""
        self._send(message)
        return self._receive()

    def close(self, force: bool = False) -> int | None:
        """Close stdin, then reap the container (killing it on timeout)."""
        proc = self._proc
        if proc.stdin is not None and not proc.stdin.closed:
            if not force:
                try:
                    self._send({"op": "shutdown"})
                except (ContainerCrashError, ContainerTimeoutError, OSError):
                    pass  # container may already be gone; that is fine
            try:
                proc.stdin.close()
            except OSError:  # pragma: no cover - pipe already broken
                pass
        try:
            return proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            return proc.wait(timeout=10.0)

    def stderr_text(self) -> str:
        """Drain the container's stderr (diagnostics for crash reports)."""
        proc = self._proc
        if proc.stderr is None:  # pragma: no cover
            return ""
        try:
            proc.stderr.close()
        except OSError:  # pragma: no cover
            return ""
        return ""

    # ─── Internals ────────────────────────────────────────────────────────

    def _remaining(self) -> float:
        return self._deadline - time.monotonic()

    def _send(self, message: dict[str, Any]) -> None:
        if self._remaining() <= 0:
            raise ContainerTimeoutError("policy container deadline exceeded before request")
        payload = json.dumps(message, separators=(",", ":")).encode() + b"\n"
        assert self._proc.stdin is not None
        try:
            self._proc.stdin.write(payload)
            self._proc.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:
            raise ContainerCrashError(self._exit_message("policy container exited")) from exc

    def _receive(self) -> dict[str, Any]:
        stdout = self._proc.stdout
        assert stdout is not None
        fd = stdout.fileno()

        while b"\n" not in self._buffer:
            remaining = self._remaining()
            if remaining <= 0:
                raise ContainerTimeoutError("policy container deadline exceeded while waiting")
            ready, _, _ = select.select([fd], [], [], min(remaining, 0.1))
            if not ready:
                continue
            chunk = os.read(fd, 65536)
            if not chunk:
                raise ContainerCrashError(self._exit_message("policy container exited"))
            self._buffer += chunk
            if len(self._buffer) > _MAX_MESSAGE_BYTES:
                raise ContainerCrashError("policy container sent an oversized message")

        line, self._buffer = self._buffer.split(b"\n", 1)
        try:
            reply = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContainerCrashError(
                f"policy container sent invalid JSON: {line[:100]!r}"
            ) from exc
        if not isinstance(reply, dict):
            raise ContainerCrashError("policy container reply is not a JSON object")
        return reply

    def _exit_message(self, prefix: str) -> str:
        code = self._proc.poll()
        return f"{prefix} (exit code {code})" if code is not None else prefix


class DockerPolicyExecutor:
    """Runs a policy in an isolated container and returns a mission result."""

    def __init__(
        self,
        image: str,
        limits: ResourceLimits | None = None,
        *,
        docker_bin: str = "docker",
        container_factory: Callable[[ContainerSpec, float], ContainerTransport] | None = None,
    ) -> None:
        if not image:
            raise ValueError("DockerPolicyExecutor requires a policy image")
        self._image = image
        self._limits = limits or ResourceLimits.default()
        self._docker_bin = docker_bin
        self._uses_real_docker = container_factory is None
        self._factory = container_factory or (
            lambda spec, timeout: SubprocessContainer(spec, timeout, docker_bin)
        )

    @property
    def limits(self) -> ResourceLimits:
        """Sandbox resource limits."""
        return self._limits

    @staticmethod
    def is_available(docker_bin: str = "docker") -> bool:
        """True when Docker is installed and its daemon answers."""
        if shutil.which(docker_bin) is None:
            return False
        try:
            probe = subprocess.run(  # noqa: S603 - fixed argv
                [docker_bin, "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return probe.returncode == 0

    def execute(self, request: ValidationRequest) -> PolicyExecutionResult:
        """Run the policy container; raises PolicyError for hash mismatches."""
        if self._uses_real_docker and not self.is_available(self._docker_bin):
            raise DockerUnavailableError(
                f"docker ({self._docker_bin}) is not installed or the daemon is unreachable"
            )

        limits = request.resource_limits or self._limits
        spec = ContainerSpec(
            image=self._image,
            limits=limits,
            name=f"konnex-policy-{uuid.uuid4().hex[:12]}",
        )
        logger.info("policy_container_starting", image=self._image, container=spec.name)

        transport = self._factory(spec, limits.timeout_s)
        exit_code: int | None = None
        try:
            result = self._execute_container(transport, request)
            exit_code = transport.close()
        except Exception:
            transport.close(force=True)
            raise

        if exit_code == 137:
            # OOM-killed by the kernel/cgroup, even if answers looked fine.
            return _failed_result("RESOURCE_EXCEEDED", request, "container exceeded memory limit")
        return result

    # ─── Internals ────────────────────────────────────────────────────────

    def _execute_container(
        self, transport: ContainerTransport, request: ValidationRequest
    ) -> PolicyExecutionResult:
        try:
            self._verify_policy_hash(transport, request)

            scenario = ScenarioGenerator().generate(
                seed=request.seed,
                robot_count=_ROBOT_COUNT,
                task_count=_TASK_COUNT,
            )

            def assign(robots: list[RobotState], tasks: list[Task]) -> list[Assignment]:
                reply = transport.request(
                    {
                        "op": "assign",
                        "robots": [_robot_payload(robot) for robot in robots],
                        "tasks": [_task_payload(task) for task in tasks],
                    }
                )
                return _assignments_from(reply)

            mission = run_headless_mission(assign, scenario, request)
        except ContainerTimeoutError as exc:
            logger.warning("policy_container_timeout", error=str(exc))
            return _failed_result("TIMEOUT", request, str(exc))
        except ContainerCrashError as exc:
            logger.warning("policy_container_crash", status=exc.status, error=str(exc))
            return _failed_result(exc.status, request, str(exc))
        except InvalidPolicyActionsError as exc:
            return _failed_result("INVALID_ACTIONS", request, str(exc))

        if mission.status == "COMPLETE":
            logger.info(
                "policy_container_complete",
                tasks_completed=mission.tasks_completed,
                completion_time_s=round(mission.completion_time_s, 2),
            )
        return mission

    @staticmethod
    def _verify_policy_hash(transport: ContainerTransport, request: ValidationRequest) -> None:
        """Reject a container whose weights do not match the submitted hash."""
        try:
            metadata = transport.request({"op": "metadata"})
        except ContainerTimeoutError as exc:
            raise ContainerCrashError(
                f"policy container did not answer metadata request: {exc}",
            ) from exc
        reported = metadata.get("policy_hash")
        if not isinstance(reported, str) or not reported:
            raise ContainerCrashError("policy container did not report a policy_hash")
        if reported != request.policy_hash:
            raise PolicyError(
                f"policy hash mismatch in sandbox: container reports {reported}, "
                f"submission is {request.policy_hash}"
            )


# ─── Wire format helpers ──────────────────────────────────────────────────


def _robot_payload(robot: RobotState) -> dict[str, Any]:
    """Serialize the fields a policy is allowed to observe about a robot."""
    return {
        "id": robot.id,
        "x": robot.position.x,
        "y": robot.position.y,
        "orientation": robot.orientation,
        "battery_pct": robot.battery_pct,
        "nav_state": robot.nav_state.value,
        "comm_state": robot.comm_state.value,
        "current_task_id": robot.current_task_id,
    }


def _task_payload(task: Task) -> dict[str, Any]:
    """Serialize the fields a policy is allowed to observe about a task."""
    return {
        "id": task.id,
        "pickup": [task.pickup.x, task.pickup.y],
        "delivery": [task.delivery.x, task.delivery.y],
        "priority": task.priority.value,
    }


def _assignments_from(reply: dict[str, Any]) -> list[Assignment]:
    """Parse a container's assignment reply, rejecting malformed content."""
    raw = reply.get("assignments")
    if raw is None:
        raise ContainerCrashError("policy container reply has no 'assignments' field")
    if not isinstance(raw, list):
        raise ContainerCrashError("policy container 'assignments' is not a list")

    assignments: list[Assignment] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ContainerCrashError(
                "policy container assignment is not an object", "INVALID_ACTIONS"
            )
        robot_id = item.get("robot_id")
        task_id = item.get("task_id")
        if not isinstance(robot_id, str) or not isinstance(task_id, str):
            raise ContainerCrashError(
                "policy container assignment lacks string robot_id/task_id",
                "INVALID_ACTIONS",
            )
        distance = item.get("distance", 0.0)
        assignments.append(
            Assignment(
                robot_id=robot_id,
                task_id=task_id,
                distance=float(distance) if isinstance(distance, (int, float)) else 0.0,
            )
        )
    return assignments


def _failed_result(status: str, request: ValidationRequest, message: str) -> PolicyExecutionResult:
    """Zero-work result for a policy the sandbox rejected."""
    return PolicyExecutionResult(
        status=status,
        tasks_completed=0,
        tasks_total=_TASK_COUNT,
        completion_time_s=0.0,
        time_limit_s=request.resource_limits.timeout_s,
        collision_count=0,
        energy_consumed=0.0,
        robot_count=_ROBOT_COUNT,
        failure_count=0,
        error_message=message,
    )
