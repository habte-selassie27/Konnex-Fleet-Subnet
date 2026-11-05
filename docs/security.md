# Security Design

> Status: STUB — design defined (PLAN.md §10 anti-gaming table), implementation pending per phase.

## Anti-Gaming Measures (MVP)

| Threat | Mitigation |
|---|---|
| Reward hacking via scenario exploitation | Randomized scenarios + fixed seed per evaluation |
| Fake trajectories | Validator executes policy directly; no self-reported telemetry |
| Replay attacks | Evaluation timestamps + nonce |
| Sandbox escape | Container CPU/memory limits + network isolation (Phase 6) |
| Policy tampering | SHA-256 hash verification before execution (Phase 6) |
| Validator collusion | Multiple validator requirement (post-MVP) |

## Ops

- Secrets via `.env` only; `X-Fleet-API-Key` auth (JWT post-MVP).
- `bandit -r . -ll` in `make lint` and CI.
- Deterministic object-storage paths `{policy_hash}/{artifact_type}/{filename}` for dedup (AGENTS.md §5.8).
