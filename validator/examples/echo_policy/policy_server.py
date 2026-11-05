"""Deterministic echo policy container (validator sandbox test fixture).

Implements the newline-delimited JSON protocol documented in
`validator/sandbox/docker_executor.py`:

    -> {"op": "metadata"}
    <- {"policy_hash": "<sha256 hex>", "name": "echo-policy"}

    -> {"op": "assign", "robots": [...], "tasks": [...]}
    <- {"assignments": [{"robot_id": "robot_0", "task_id": "task_003"}]}

    -> {"op": "shutdown"}

Policy: greedy nearest pickup — deliberately the simplest deterministic
strategy, so two independent validators must produce byte-identical scores and
any divergence is a validator/infra bug, not policy noise.

No network, no filesystem writes, no sockets: stdin/stdout only, matching the
hardened `docker run` flags (--network none, --read-only).
"""

from __future__ import annotations

import json
import math
import sys
from typing import Any

try:  # container layout (flat COPY) vs. repo package layout (tests)
    from weights import echo_policy_hash
except ImportError:  # pragma: no cover - exercised by the in-repo import path
    from validator.examples.echo_policy.weights import echo_policy_hash


def assign(robots: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Greedy nearest-pickup assignment; each robot claims one unused task."""
    pending = list(tasks)
    assignments: list[dict[str, str]] = []

    for robot in robots:
        if not pending:
            break
        rx, ry = float(robot["x"]), float(robot["y"])
        best = min(
            pending,
            key=lambda task: math.dist(
                (rx, ry), (float(task["pickup"][0]), float(task["pickup"][1]))
            ),
        )
        pending.remove(best)
        assignments.append({"robot_id": str(robot["id"]), "task_id": str(best["id"])})

    return assignments


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        message = json.loads(line)
        op = message.get("op")

        if op == "metadata":
            reply = {"policy_hash": echo_policy_hash(), "name": "echo-policy"}
        elif op == "assign":
            reply = {"assignments": assign(message.get("robots", []), message.get("tasks", []))}
        elif op == "shutdown":
            break
        else:
            reply = {"error": f"unknown op {op!r}"}

        sys.stdout.write(json.dumps(reply, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
