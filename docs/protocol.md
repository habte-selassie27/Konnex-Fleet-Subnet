# Protocol Layer — Konnex Adapter & PoPW Boundary

> Status: **COMPLETE (boundary) — SDK researched but not integrated.** Adapter methods raise `NotImplementedError`; research findings in `docs/konnex.md`.

## Konnex Adapter Boundary

Only these types may cross into `KonnexAdapter` (AGENTS.md §3.2, TESTING_PLAN.md §14):

| Safe types (allowed) | Blocked types (never cross) |
|---|---|
| `policy_id: str` | `RobotState` |
| `policy_hash: str` (SHA-256) | Gazebo world handles |
| `MissionMetadata` (protocol/konnex/models.py) | ROS 2 node references |
| `EvaluationArtifact` (validator/reproducibility/artifact.py) | Raw trajectory arrays |
| `score: float`, `dict[str, object]` (status payloads) | Any type from `robotics/`, `simulation/`, `ml/`, `fleet/` |

**Robotics core has zero imports from `protocol/konnex/`** — enforced by grep test in CI (`tests/integration/test_konnex_adapter.py`).

## SDK Status

- **RESEARCHED (2026-08-09), NOT INTEGRATED.** All adapter methods raise `NotImplementedError` with `# TODO: verify Konnex SDK`.
- Verified findings (full detail in `docs/konnex.md`):
  - `docs.konnex.network` / `gitbook.konnex.network` **do not exist**. Official docs: **`https://docs.konnex.world/`**.
  - SDK: Python client in `konnex-world/konnex` monorepo (`pip install -e ./sdk/python-client`, `from konnex import KonnexClient`); **no PyPI/npm release found**.
  - HTTP API prefix `/api/v1/`; endpoints include `POST /api/v1/tasks`, `POST /api/v1/miners/models`, `POST /api/v1/validators/verify`.
- No Konnex API calls may be invented (AGENTS.md §0.5, SYSTEM_PROMPT.md §6.3).

## Files

| File | Purpose | Status |
|---|---|---|
| `protocol/konnex/adapter.py` | `KonnexAdapter` — boundary to Konnex network | STUB (NotImplementedError, SDK researched) |
| `protocol/konnex/models.py` | `MissionMetadata` | COMPLETE (Phase 8) |
| `protocol/powp/proof.py` | `ProofOfPhysicalWork` — on-chain proof data model | COMPLETE |
| `protocol/powp/serializer.py` | Canonical JSON serialization for proofs | COMPLETE |
| `protocol/powp/weights.yaml` | Configurable scoring weights | COMPLETE |
| `docs/powp.md` | PoPW scoring design documentation | COMPLETE |

## Data Flow

```
Mission completes
    ↓
PoPWScoringEngine.score(MissionResult) → PoPWScore
    ↓
EvaluationArtifact(...) → seal() → verify()
    ↓
ProofOfPhysicalWork.from_artifact(...) → seal()
    ↓
KonnexAdapter.publish_proof(artifact: EvaluationArtifact)  ← STUB
```
