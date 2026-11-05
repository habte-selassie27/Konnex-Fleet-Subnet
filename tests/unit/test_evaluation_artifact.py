"""EvaluationArtifact canonical-hash unit tests (TESTING_PLAN.md §3.5, Phase 6).

Contract: SHA-256 over canonical JSON (sorted keys, floats rounded to 6dp,
artifact_hash field excluded); tampering changes the hash; JSON roundtrip
preserves the artifact.

Status: COMPLETE (Phase 6).
"""

from validator.reproducibility.artifact import EvaluationArtifact


def make_artifact(final_score: float = 88.5) -> EvaluationArtifact:
    """Build a representative evaluation artifact."""
    return EvaluationArtifact(
        policy_id="nearest",
        policy_hash="policy-hash-abc",
        scenario_id="warehouse_v1_20tasks",
        seed=42,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
        score_components={"mission_success": 0.9, "safety": 0.8},
        final_score=final_score,
        completion_time_s=120.5,
        collision_count=2,
        tasks_completed=18,
        tasks_total=20,
        energy_consumed=210.25,
        timestamp=1_700_000_000.0,
    )


class TestEvaluationArtifact:
    def test_hash_deterministic(self) -> None:
        assert make_artifact().compute_hash() == make_artifact().compute_hash()

    def test_seal_attaches_hash(self) -> None:
        artifact = make_artifact().seal()
        assert artifact.artifact_hash == artifact.compute_hash()
        assert artifact.artifact_hash  # non-empty hex digest

    def test_seal_idempotent(self) -> None:
        artifact = make_artifact().seal()
        assert artifact.seal().artifact_hash == artifact.artifact_hash

    def test_hash_changes_on_tamper(self) -> None:
        assert make_artifact(88.5).compute_hash() != make_artifact(90.0).compute_hash()

    def test_hash_excludes_artifact_hash_field(self) -> None:
        sealed = make_artifact().seal()
        assert sealed.compute_hash() == sealed.artifact_hash

    def test_json_roundtrip_preserves_artifact(self) -> None:
        sealed = make_artifact().seal()
        loaded = EvaluationArtifact.from_json(sealed.to_json())
        assert loaded.final_score == sealed.final_score
        assert loaded.policy_id == sealed.policy_id
        assert loaded.artifact_hash == sealed.artifact_hash
        assert loaded.compute_hash() == sealed.artifact_hash

    def test_tamper_detected_after_roundtrip(self) -> None:
        sealed = make_artifact().seal()
        loaded = EvaluationArtifact.from_json(sealed.to_json())
        loaded.final_score = 0.0
        assert loaded.compute_hash() != sealed.artifact_hash

    def test_floats_rounded_to_six_decimal_places(self) -> None:
        artifact = make_artifact()
        artifact.final_score = 88.123456789
        canonical = artifact.to_json()
        assert '"final_score": 88.123457' in canonical

    def test_verify_passes_for_valid_artifact(self) -> None:
        """TESTING_PLAN.md §13 — verify() returns True for unmodified sealed artifact."""
        sealed = make_artifact().seal()
        assert sealed.verify() is True

    def test_verify_fails_for_tampered_artifact(self) -> None:
        """TESTING_PLAN.md §13 — verify() returns False after any field mutation."""
        sealed = make_artifact().seal()
        loaded = EvaluationArtifact.from_json(sealed.to_json())
        loaded.final_score = 0.0
        # The hash won't match because final_score changed
        assert loaded.verify() is False
