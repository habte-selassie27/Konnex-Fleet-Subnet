"""KonnexAdapter integration tests (TESTING_PLAN.md §14, Phase 8).

Covers:
- adapter loads and exposes the required method set
- all live methods raise NotImplementedError until the SDK is verified
- input validation raises KonnexAdapterError for empty ids/hashes
- every call is logged via structlog
- robotics/ (and sim-side packages) have zero imports from protocol/konnex/
- the adapter boundary accepts only protocol-safe types
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, get_args, get_origin

import pytest
from structlog.testing import capture_logs

from protocol.konnex.adapter import KonnexAdapter, KonnexAdapterError
from protocol.konnex.models import MissionMetadata
from validator.reproducibility.artifact import EvaluationArtifact

REPO_ROOT = Path(__file__).resolve().parents[2]

# Method names the adapter must expose (TESTING_PLAN.md §14).
REQUIRED_METHODS = [
    "submit_mission",
    "submit_policy",
    "submit_evaluation",
    "publish_proof",
    "query_rewards",
    "get_submission_status",
]

# Only these type names may appear in KonnexAdapter signatures.
# "object" is allowed (dict[str, object] for get_submission_status) — it is
# a fully opaque type and leaks no simulator internals.
ALLOWED_SIGNATURE_TYPES = {
    "str",
    "float",
    "dict",
    "object",
    "MissionMetadata",
    "EvaluationArtifact",
    "NoneType",
    "UnionType",
}


def make_metadata() -> MissionMetadata:
    return MissionMetadata(
        mission_id="mission_1",
        policy_id="policy_a",
        scenario_id="warehouse_v1",
        seed=42,
        robot_count=5,
        task_count=10,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
    )


def make_artifact() -> EvaluationArtifact:
    artifact = EvaluationArtifact(
        policy_id="policy_a",
        policy_hash="a" * 64,
        scenario_id="warehouse_v1",
        seed=42,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
        score_components={"mission_success": 0.9},
        final_score=88.5,
        completion_time_s=120.0,
        collision_count=0,
        tasks_completed=10,
        tasks_total=10,
        energy_consumed=50.0,
        timestamp=1_700_000_000.0,
    )
    return artifact.seal()


class TestKonnexAdapterLoads:
    def test_adapter_loads(self) -> None:
        with capture_logs():
            adapter = KonnexAdapter()
        for name in REQUIRED_METHODS:
            assert callable(getattr(adapter, name)), f"missing method {name}"

    def test_error_type_defined(self) -> None:
        assert issubclass(KonnexAdapterError, Exception)

    def test_models_importable(self) -> None:
        assert MissionMetadata.__name__ == "MissionMetadata"


class TestKonnexAdapterNotImplemented:
    """Until the SDK is verified, every live method must raise NotImplementedError."""

    @pytest.mark.parametrize(
        ("method", "args"),
        [
            ("submit_mission", (make_metadata(),)),
            ("submit_policy", ("policy_a", "a" * 64)),
            ("submit_evaluation", ("policy_a", "eval_1", 88.5, "b" * 64)),
            ("publish_proof", (make_artifact(),)),
            ("query_rewards", ("policy_a",)),
            ("get_submission_status", ("submission_1",)),
        ],
    )
    def test_methods_raise_not_implemented(self, method: str, args: tuple[Any, ...]) -> None:
        adapter = KonnexAdapter()
        with pytest.raises(NotImplementedError) as exc_info:
            getattr(adapter, method)(*args)
        assert "TODO: verify Konnex SDK" in str(exc_info.value)


class TestKonnexAdapterValidation:
    def test_rejects_empty_policy_id(self) -> None:
        adapter = KonnexAdapter()
        with pytest.raises(KonnexAdapterError):
            adapter.submit_policy("", "a" * 64)
        with pytest.raises(KonnexAdapterError):
            adapter.submit_policy("   ", "a" * 64)

    def test_rejects_empty_policy_hash(self) -> None:
        adapter = KonnexAdapter()
        with pytest.raises(KonnexAdapterError):
            adapter.submit_policy("policy_a", "")

    def test_rejects_empty_mission_id(self) -> None:
        adapter = KonnexAdapter()
        empty = MissionMetadata(
            mission_id="",
            policy_id="policy_a",
            scenario_id="warehouse_v1",
            seed=42,
            robot_count=5,
            task_count=10,
            env_version="v1.0.0",
            sim_version="gazebo_harmonic",
        )
        with pytest.raises(KonnexAdapterError):
            adapter.submit_mission(empty)

    def test_rejects_empty_eval_id_and_hash(self) -> None:
        adapter = KonnexAdapter()
        with pytest.raises(KonnexAdapterError):
            adapter.submit_evaluation("policy_a", "", 88.5, "b" * 64)
        with pytest.raises(KonnexAdapterError):
            adapter.submit_evaluation("policy_a", "eval_1", 88.5, "")

    def test_rejects_empty_submission_id(self) -> None:
        adapter = KonnexAdapter()
        with pytest.raises(KonnexAdapterError):
            adapter.get_submission_status("")

    def test_validation_precedes_not_implemented(self) -> None:
        """Empty input must raise KonnexAdapterError, not NotImplementedError."""
        adapter = KonnexAdapter()
        with pytest.raises(KonnexAdapterError):
            adapter.query_rewards("")


class TestKonnexAdapterLogging:
    def test_adapter_logs_calls(self) -> None:
        adapter = KonnexAdapter()
        with capture_logs() as captured:
            with pytest.raises(NotImplementedError):
                adapter.submit_policy("policy_a", "a" * 64)
        assert any(
            entry.get("event") == "konnex.submit_policy" and entry.get("policy_id") == "policy_a"
            for entry in captured
        )

    def test_constructor_logs_initialization(self) -> None:
        with capture_logs() as captured:
            KonnexAdapter(endpoint="https://example.invalid")
        assert any(entry.get("event") == "konnex_adapter_initialized" for entry in captured)


class TestBoundaryEnforced:
    """The adapter must only ever receive protocol-safe types."""

    def test_robotics_core_zero_konnex_imports(self) -> None:
        """Grep test: no sim-side package may import protocol.konnex (AGENTS.md §3.2).

        Two patterns, so neither `import protocol.konnex` nor the dot-less
        `from protocol import konnex` form can slip through.
        """
        dotted = re.compile(r"^\s*(from|import)\s+protocol\s*\.\s*konnex\b")
        dotless = re.compile(r"^\s*from\s+protocol\s+import\s+.*\bkonnex\b")
        sim_side = ["robotics", "simulation", "ml", "fleet"]
        offenders: list[str] = []
        for package in sim_side:
            for path in sorted((REPO_ROOT / package).rglob("*.py")):
                for lineno, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    if dotted.search(line) or dotless.search(line):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
        assert not offenders, (
            "Zero imports from protocol.konnex required in "
            f"{', '.join(sim_side)}:\n" + "\n".join(offenders)
        )

    def test_protocol_konnex_has_no_simulator_imports(self) -> None:
        """The adapter must not import robotics/simulation/ml/fleet types."""
        pattern = re.compile(r"^\s*(from|import)\s+(robotics|simulation|ml|fleet|rclpy|gazebo)\b")
        konnex_dir = REPO_ROOT / "protocol" / "konnex"
        offenders: list[str] = []
        for path in sorted(konnex_dir.rglob("*.py")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
        assert not offenders, "protocol/konnex must not import simulator packages:\n" + "\n".join(
            offenders
        )

    def test_adapter_boundary_enforced(self) -> None:
        """Only protocol-safe types may appear in KonnexAdapter signatures.

        Two checks: (1) every parameter of every public method must be
        annotated, so an untyped parameter cannot smuggle a simulator type
        past enforcement; (2) every resolved annotation must be in the
        protocol-safe whitelist.
        """
        import inspect
        import typing

        for name in dir(KonnexAdapter):
            if name.startswith("_"):
                continue
            member = getattr(KonnexAdapter, name)
            if not callable(member) or isinstance(member, type):
                continue
            params = inspect.signature(member).parameters
            unannotated = [
                p for p in params if p != "self" and params[p].annotation is inspect.Parameter.empty
            ]
            assert not unannotated, (
                f"{name} has unannotated parameters {unannotated} — annotate them so "
                "the boundary check can verify type safety"
            )
            used: set[str] = set()
            hints = typing.get_type_hints(member)
            for annotation in hints.values():
                used.update(_collect_type_names(annotation))
            leaked = used - ALLOWED_SIGNATURE_TYPES
            assert not leaked, (
                f"Boundary violated in {name} — non-protocol types in signatures: {sorted(leaked)}"
            )


def _collect_type_names(annotation: Any) -> set[str]:
    """Recursively collect type names from an annotation (unwrapping Optional)."""
    origin = get_origin(annotation)
    if origin is not None:
        names: set[str] = {getattr(origin, "__name__", str(origin))}
        for arg in get_args(annotation):
            names.update(_collect_type_names(arg))
        return names
    return {getattr(annotation, "__name__", str(annotation))}
