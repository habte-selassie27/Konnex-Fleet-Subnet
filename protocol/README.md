# protocol/

Blockchain/protocol boundary layer.

| Path | Contents |
|---|---|
| `powp/proof.py` · `powp/serializer.py` | PoPW proof dataclass + canonical JSON serialization (Phase 7) |
| `konnex/adapter.py` | `KonnexAdapter` — **STUB**, all methods raise `NotImplementedError` with `# TODO: verify Konnex SDK <method>()` (Phase 8; SDK researched in `docs/konnex.md`) |
| `konnex/models.py` | `MissionMetadata` — protocol-safe mission metadata (Phase 8) |

**Boundary rules (SYSTEM_PROMPT.md §3.4):** only `policy_id`, `policy_hash`, `EvaluationArtifact`, `MissionMetadata` cross into `KonnexAdapter`. Robotics core never imports from here.

**Status: STUB — Konnex SDK researched (2026-08-09, docs.konnex.world) but not integrated. Boundary enforced by tests/integration/test_konnex_adapter.py.**
