# validator/

The trust anchor of the subnet (Phase 6).

| Path | Contents (planned) |
|---|---|
| `runner.py` | `ValidatorRunner.validate(request) -> ValidationResult` — statuses: COMPLETE / POLICY_CRASH / TIMEOUT / RESOURCE_EXCEEDED / INVALID_ACTIONS / UNSTABLE |
| `scoring/engine.py` | `PoPWScoringEngine` — prototype weighted score (BUILD.md §9) |
| `scoring/components.py` | Individual score components |
| `sandbox/docker_executor.py` | `DockerPolicyExecutor` — isolated container, hash gate, JSON-lines protocol, deadline/OOM status mapping |
| `sandbox/executor.py` | `InProcessPolicyExecutor` + shared `run_headless_mission` mission loop |
| `sandbox/resource_limits.py` | Sandbox CPU/memory/network/timeout limits |
| `reproducibility/artifact.py` · `verifier.py` | `EvaluationArtifact` + SHA-256 verification (±0.5 reproducibility) |
| `anti_gaming/checks.py` | Hash verification, nonce/timestamps, invalid-action rejection |

**Constraints (AGENTS.md §3.2):** validator must never modify robot state; must not import fleet orchestrator internals — it uses the policy interface only.

**Status: COMPLETE (Phase 6).** Both executors implemented; `make lint` and the
unit + integration suites pass. See `docs/validator.md` for the sandbox
contract and how to evaluate a containerized policy.
