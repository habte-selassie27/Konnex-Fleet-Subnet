# Validator — Architecture, API & Sandbox

> **Phase 6 deliverable.** Status: COMPLETE for both executors — the
> deterministic in-process executor (`InProcessPolicyExecutor`) and the
> containerized sandbox (`DockerPolicyExecutor`). No fabricated scores — every
> number comes from executed deterministic missions.

## Goal

Two independent validator instances reproduce the same score within **±0.5**
for the same `(policy_hash, scenario_id, seed, env_version)`.

## Architecture

```
                 ValidationRequest
        (policy_id, policy_hash, scenario_id, seed,
         env_version, sim_version, resource_limits)
                        │
                        ▼
                 ValidatorRunner
                        │
          ┌─────────────┴──────────────┐
          ▼                           ▼
  Policy hash check             PolicyExecutor
  sha256(weights) ==        ┌──────────────────┐
  submitted_hash            │ InProcess        │   Docker sandbox
  else PolicyError          │ deterministic    │   CPU 2 · mem 4G ·
          │                │ seeded mission    │   network=none · read-only
          ▼                └────────┬─────────┘
  MissionResult                     │
        │                           │ PolicyExecutionResult
        ▼                           ▼
  PoPWScoringEngine ──► PoPWScore ──► EvaluationArtifact (sealed, SHA-256)
        │
        ▼
  POST /api/v1/evaluations  ──► DB record + artifact store
```

The validator never imports fleet orchestrator internals — it drives the
mission through the `TaskAllocator` policy interface and the
`RobotAdapter` contract (AGENTS.md §3.2).

## Validation Statuses

| Status | Meaning | Score |
|---|---|---|
| `COMPLETE` | policy finished the mission | scored normally |
| `POLICY_CRASH` | policy raised during construction/execution | 0.0 |
| `TIMEOUT` | mission exceeded 2× time limit | 0.0 |
| `RESOURCE_EXCEEDED` | policy violated sandbox limits | 0.0 |
| `INVALID_ACTIONS` | policy referenced unknown robots/tasks | 0.0 |

A failing policy never crashes the validator.

## Policy Hash Verification

Before any execution: `sha256(policy_weights) == submitted_hash`.
Mismatch or unknown policy ⇒ `PolicyError` raised (rejected, not scored).

## EvaluationArtifact

```
policy_id, policy_hash, scenario_id, seed,
env_version, sim_version,
score_components, final_score,
completion_time_s, collision_count,
tasks_completed, tasks_total, energy_consumed,
timestamp, artifact_hash
```

- `artifact_hash` = SHA-256 of canonical JSON: **keys sorted**, **floats
  rounded to 6 decimal places**, `artifact_hash` field excluded.
- Tampering with any field changes the hash (verified by
  `test_evaluation_artifact_verifiable`).
- `to_json()` / `from_json()` roundtrip preserves the artifact.

## Sandbox Spec (`ResourceLimits`)

| Setting | Value |
|---|---|
| CPU | 2 |
| Memory | 4 GB |
| Network | disabled |
| Filesystem | read-only |
| Timeout | configurable (`timeout_s`, default 600 s) |

Both executors honor the same limits and run the **same** mission loop
(`run_headless_mission` in `validator/sandbox/executor.py`), so a sandboxed
evaluation and a headless one are directly comparable.

## Docker sandbox (`validator/sandbox/docker_executor.py`)

The container is launched with every isolation flag applied:

| Flag | Effect |
|---|---|
| `--network none` | no outbound calls / exfiltration (opt-in `network_enabled` to override) |
| `--read-only` + `--tmpfs /tmp:size=64m` | policy cannot persist state between runs |
| `--cap-drop ALL`, `--security-opt no-new-privileges` | no privilege escalation |
| `--cpus` / `--memory` / `--memory-swap` | cgroup limits; exit 137 ⇒ `RESOURCE_EXCEEDED` |
| wall-clock deadline (`timeout_s`) | exceeded ⇒ container killed, status `TIMEOUT` |

### Container protocol

Newline-delimited JSON over stdin/stdout — no sockets, so the policy cannot
reach the network even to be driven:

```
-> {"op": "metadata"}
<- {"policy_hash": "<sha256 hex>", "name": "<optional>"}

-> {"op": "assign", "robots": [...], "tasks": [...]}
<- {"assignments": [{"robot_id": "robot_0", "task_id": "task_003"}]}

-> {"op": "shutdown"}        (optional; closing stdin is enough)
```

Robot payload: `id, x, y, orientation, battery_pct, nav_state, comm_state,
current_task_id`. Task payload: `id, pickup, delivery, priority`. Nothing else
from the simulator crosses the boundary.

### Rejections

The container must report the SHA-256 of its own weights on `metadata`; a
mismatch raises `PolicyError` **before the mission starts**, exactly like the
in-process registry check. Protocol garbage, start-up failure, and premature
exit become `POLICY_CRASH`; assignments naming unknown robots/tasks become
`INVALID_ACTIONS`.

```python
from validator.sandbox.docker_executor import DockerPolicyExecutor

runner = ValidatorRunner(DockerPolicyExecutor("ghcr.io/team/policy:1.2.0"))
result = runner.validate(request)          # raises PolicyError on hash mismatch
```

`DockerPolicyExecutor.is_available()` reports whether Docker is reachable; a
missing daemon raises `DockerUnavailableError` rather than silently producing a
zero score. Tests cover the transport over real pipes and the isolation flags;
the opt-in end-to-end container test runs when `KONNEX_POLICY_IMAGE` is set.

## API

```
POST /api/v1/evaluations          # validator → backend (X-Fleet-API-Key)
GET  /api/v1/evaluations/{id}     # evaluation summary
GET  /api/v1/evaluations/{id}/artifact   # stored artifact JSON
```

Submission persists the evaluation record in the DB and the artifact JSON in
the artifact store at `{policy_hash}/{evaluation_id}.json` (MinIO/S3 STUB).

## Reproducibility Gates (tests/integration/test_validator_runner.py)

- `test_same_policy_and_seed_produces_same_score` — |Δscore| ≤ 0.5
- `test_two_validators_agree_within_tolerance` — independent instances agree
- `test_crashed_policy_returns_zero_score` — POLICY_CRASH, no validator crash
- `test_evaluation_artifact_verifiable` — canonical hash + tamper detection
- Plus TIMEOUT / RESOURCE_EXCEEDED / INVALID_ACTIONS → 0.0, hash mismatch
  rejection, unknown-policy rejection.
