"""Artifact integrity checks inside validator/anti_gaming/checks.py.

Status: COMPLETE (Phase 6) — ties the freshness timestamp to the sealed artifact hash
and cross-checks the request envelope against the artifact.

These live with the existing anti-gaming tests because they close the "captured artifact,
fresh timestamp" replay gap that freshness alone cannot.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from validator.anti_gaming.checks import (
    AntiGamingError,
    ArtifactIntegrityError,
    canonical_artifact_hash,
    check_submission,
    verify_artifact,
    verify_envelope_against_artifact,
)


def _fresh_artifact(
    *,
    policy_id: str = "nearest",
    policy_hash: str = "policy-hash-abc",
    scenario_id: str = "warehouse_v1_20tasks",
    seed: int = 42,
    env_version: str = "v1.0.0",
    sim_version: str = "gazebo_harmonic",
    mission_success: float = 1.0,
    efficiency: float = 0.8,
    final_score: float = 92.4,
    completion_time_s: float = 120.0,
    collision_count: int = 0,
    tasks_completed: int = 18,
    tasks_total: int = 20,
    energy_consumed: float = 42.0,
    timestamp: float | None = None,
) -> dict[str, Any]:
    if timestamp is None:
        timestamp = time.time()
    artifact: dict[str, Any] = {
        "policy_id": policy_id,
        "policy_hash": policy_hash,
        "scenario_id": scenario_id,
        "seed": seed,
        "env_version": env_version,
        "sim_version": sim_version,
        "score_components": {
            "mission_success": mission_success,
            "safety": 1.0,
            "efficiency": efficiency,
            "energy": 0.9,
            "coordination": 1.0,
            "robustness": 1.0,
        },
        "final_score": final_score,
        "completion_time_s": completion_time_s,
        "collision_count": collision_count,
        "tasks_completed": tasks_completed,
        "tasks_total": tasks_total,
        "energy_consumed": energy_consumed,
        "timestamp": timestamp,
    }
    return artifact


def _envelope_for(
    artifact: dict[str, Any], *, nonce: str = "abc", timestamp: float | None = None
) -> dict[str, Any]:
    return {
        "policy_id": artifact["policy_id"],
        "policy_hash": artifact["policy_hash"],
        "scenario_id": artifact["scenario_id"],
        "seed": artifact["seed"],
        "env_version": artifact["env_version"],
        "sim_version": artifact["sim_version"],
        "status": "COMPLETE",
        "final_score": artifact["final_score"],
        "artifact_hash": canonical_artifact_hash(artifact),
        "nonce": nonce,
        "timestamp": timestamp if timestamp is not None else artifact["timestamp"],
        "artifact": dict(artifact),
    }


def test_canonical_artifact_hash_roundtrips_the_sealed_artifact() -> None:
    artifact = _fresh_artifact()
    computed = canonical_artifact_hash(artifact)
    assert canonical_artifact_hash(artifact) == computed
    assert round(float(artifact["final_score"]), 6) == 92.4  # noqa: PLR2004


def test_verify_artifact_accepts_the_matching_hash() -> None:
    artifact = _fresh_artifact()
    verify_artifact(artifact, expected_hash=canonical_artifact_hash(artifact))


def test_verify_artifact_rejects_a_wrong_hash() -> None:
    artifact = _fresh_artifact()
    with pytest.raises(ArtifactIntegrityError, match="artifact hash mismatch"):
        verify_artifact(artifact, expected_hash="0" * 64)


def test_verify_artifact_rejects_an_empty_artifact() -> None:
    with pytest.raises(ArtifactIntegrityError, match="artifact payload is empty"):
        verify_artifact({}, expected_hash=canonical_artifact_hash(_fresh_artifact()))


def test_verify_artifact_rejects_a_missing_required_field() -> None:
    artifact = _fresh_artifact()
    del artifact["scenario_id"]
    with pytest.raises(ArtifactIntegrityError, match="artifact is missing required field"):
        verify_envelope_against_artifact(artifact, _envelope_for(_fresh_artifact()))


def test_verify_envelope_against_artifact_accepts_consistent_fields() -> None:
    artifact = _fresh_artifact()
    envelope = _envelope_for(artifact)
    verify_envelope_against_artifact(artifact, envelope)


def test_verify_envelope_rejects_a_timestamp_outside_the_sealed_artifact() -> None:
    artifact = _fresh_artifact()
    many_timestamp: float = float(artifact["timestamp"]) + 60.0
    envelope = _envelope_for(artifact, timestamp=many_timestamp)
    with pytest.raises(
        ArtifactIntegrityError,
        match="submission timestamp must equal the sealed artifact timestamp",
    ):
        verify_envelope_against_artifact(artifact, envelope)


def test_check_submission_still_enforces_freshness_and_form() -> None:
    with pytest.raises(AntiGamingError, match="maximum age"):
        check_submission("nonce-1234567890abcdef", time.time() - 901.0)

    with pytest.raises(AntiGamingError, match="in the future"):
        check_submission("nonce-1234567890abcdef", time.time() + 61.0)

    with pytest.raises(AntiGamingError, match="nonce must be"):
        check_submission("short", time.time())
