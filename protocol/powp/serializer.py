"""PoPW proof serialization — canonical JSON for hashing and transmission.

Spec (AGENTS.md §6.8):
    The serializer ensures deterministic JSON output: sorted keys, no whitespace,
    floats rounded to 6 decimal places. This guarantees that two independent
    serializations of the same proof produce identical bytes.

Status: COMPLETE (Phase 7).
"""

from __future__ import annotations

import json
from typing import Any

from protocol.powp.proof import ProofOfPhysicalWork


def serialize_proof(proof: ProofOfPhysicalWork) -> str:
    """Canonical JSON serialization of a ProofOfPhysicalWork.

    - Keys sorted alphabetically
    - No whitespace (separators=(",", ":"))
    - Floats rounded to 6 decimal places
    - proof_hash excluded from the payload (it covers the rest)
    """
    payload: dict[str, Any] = {}
    for key, value in proof.__dict__.items():
        if key == "proof_hash":
            continue
        if isinstance(value, float):
            payload[key] = round(value, 6)
        else:
            payload[key] = value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def canonical_proof(proof: ProofOfPhysicalWork) -> str:
    """Alias for serialize_proof — the canonical form used for hashing."""
    return serialize_proof(proof)
