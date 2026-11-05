# PoPW Scoring — Prototype Design

> Status: **COMPLETE** (Phase 7).
> Formula designed (PLAN.md §8, BUILD.md §9); implemented in `validator/scoring/engine.py`.
> NOT Konnex's official algorithm — adapt after Phase 8 SDK research.

## Prototype Score

| Component | Weight | Formula |
|---|---|---|
| Mission Success Rate | 40% | tasks completed / tasks assigned |
| Safety Score | 20% | 1.0 − (collisions / 10) |
| Efficiency Score | 15% | 1.0 − (time_taken / time_limit) |
| Energy Score | 10% | 1.0 − (energy_used / energy_budget) |
| Coordination Score | 10% | inter-robot cooperation metric |
| Robustness Score | 5% | performance under failure conditions |

- Range: 0.0–100.0 (`validator/scoring/engine.py`)
- Weights configurable via `protocol/powp/weights.yaml`
- Evaluation artifact: JSON + SHA-256 canonical hash (keys sorted, floats to 6dp) — `validator/reproducibility/artifact.py`
- Reproducibility contract: same `(policy_hash, scenario_id, seed, env_version)` ⇒ scores within ±0.5 (PLAN.md §9.3)

## Files

| File | Purpose |
|---|---|
| `validator/scoring/engine.py` | `PoPWScoringEngine`, `ScoringWeights`, `PoPWScore`, `MissionResult` |
| `validator/scoring/components.py` | `coordination_score()`, `robustness_score()` |
| `validator/reproducibility/artifact.py` | `EvaluationArtifact` with SHA-256 hashing, seal/verify/to_json/from_json |
| `protocol/powp/proof.py` | `ProofOfPhysicalWork` — on-chain proof data model |
| `protocol/powp/serializer.py` | Canonical JSON serialization for proofs |
| `protocol/powp/weights.yaml` | Configurable scoring weights |

## Evaluation Artifact

The `EvaluationArtifact` captures everything needed to independently verify an evaluation:

```json
{
  "policy_id": "nearest",
  "policy_hash": "abc123...",
  "scenario_id": "warehouse_v1_20tasks",
  "seed": 42,
  "env_version": "v1.0.0",
  "sim_version": "gazebo_harmonic",
  "score_components": {"mission_success": 0.9, "safety": 1.0, ...},
  "final_score": 94.2,
  "completion_time_s": 120.5,
  "collision_count": 0,
  "tasks_completed": 20,
  "tasks_total": 20,
  "energy_consumed": 210.25,
  "timestamp": 1700000000.0,
  "artifact_hash": "sha256:..."
}
```

**Tamper detection:** Any change to any field produces a different SHA-256 hash.

## ProofOfPhysicalWork

The `ProofOfPhysicalWork` links an evaluation to the Konnex network:

```json
{
  "mission_id": "...",
  "policy_id": "...",
  "policy_hash": "...",
  "scenario_id": "...",
  "seed": 42,
  "env_version": "v1.0.0",
  "score": 94.2,
  "artifact_hash": "...",
  "artifact_url": "s3://fleet-artifacts/...",
  "timestamp": 1700000000.0,
  "proof_hash": "sha256:..."
}
```

Adapt to the real Konnex SDK scoring rules after Phase 8 research.
