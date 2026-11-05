"""Compatibility shim — the Docker sandbox lives in `docker_executor.py`.

Status: COMPLETE (Phase 6 sandbox). Historically this module held the STUB
contract; the working implementation (container launch, isolation flags, hash
verification, JSON-lines policy protocol, deadline enforcement) is in
`validator/sandbox/docker_executor.py`. Imports from here keep working.
"""

from validator.sandbox.docker_executor import (
    ContainerCrashError,
    ContainerSpec,
    ContainerTimeoutError,
    ContainerTransport,
    DockerPolicyExecutor,
    DockerUnavailableError,
    SubprocessContainer,
    build_docker_run_argv,
)

__all__ = [
    "ContainerCrashError",
    "ContainerSpec",
    "ContainerTimeoutError",
    "ContainerTransport",
    "DockerPolicyExecutor",
    "DockerUnavailableError",
    "SubprocessContainer",
    "build_docker_run_argv",
]
