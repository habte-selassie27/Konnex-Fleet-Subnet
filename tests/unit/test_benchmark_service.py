"""Benchmark service tests — the dashboard must read real artifacts only.

Covers the three result.json shapes (unified harness, nested summary, flat),
the duplicate/superseded-row selection rule, and honest empty output.

Status: COMPLETE (Phase 9 dashboard surface).
"""

import json
from pathlib import Path

from backend.services.benchmark_service import BenchmarkService


def write_result(root: Path, relative: str, payload: dict[str, object]) -> None:
    """Write one result.json under a results root."""
    path = root / relative / "result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def policy_row(policy: str, score: float, **overrides: object) -> dict[str, object]:
    """A measured policy entry for the unified-harness shape."""
    row: dict[str, object] = {
        "policy": policy,
        "n_runs": 30,
        "mean_popw_score": score,
        "std_popw_score": 2.0,
        "mean_success_rate": 1.0,
        "std_success_rate": 0.0,
        "mean_collision_count": 1.0,
        "std_collision_count": 0.5,
        "status": "COMPLETE",
    }
    row.update(overrides)
    return row


def test_unified_harness_rows_carry_context_and_sort_by_score(tmp_path: Path) -> None:
    write_result(
        tmp_path,
        "fleet_env_unified",
        {
            "harness": "FleetEnv",
            "scenario": "warehouse_v1_20tasks",
            "robot_count": 5,
            "seed_range": [1000, 1001],
            "policies": [policy_row("nearest", 90.0), policy_row("mappo", 93.0)],
        },
    )

    rows = BenchmarkService(tmp_path).list_benchmarks()

    assert [row.policy for row in rows] == ["mappo", "nearest"]
    assert rows[0].harness == "FleetEnv"
    assert rows[0].scenario_id == "warehouse_v1_20tasks"
    assert rows[0].robot_count == 5
    assert rows[0].seed_range == [1000, 1001]
    assert rows[0].mean_popw_score == 93.0


def test_nested_summary_is_flattened(tmp_path: Path) -> None:
    write_result(
        tmp_path,
        "mappo_eval",
        {
            "policy": "mappo",
            "scenario_id": "warehouse_v1_20tasks",
            "seed_range": [1000, 1001],
            "summary": {"n_runs": 2, "mean_popw_score": 92.5, "mean_success_rate": 1.0},
        },
    )

    rows = BenchmarkService(tmp_path).list_benchmarks()

    assert len(rows) == 1
    assert rows[0].experiment_id == "mappo_eval"
    assert rows[0].mean_popw_score == 92.5
    assert rows[0].status == "COMPLETE"


def test_unmeasured_policy_keeps_skip_reason(tmp_path: Path) -> None:
    write_result(
        tmp_path,
        "exp_004",
        {
            "experiment_id": "exp_004",
            "policy": "mappo",
            "n_runs": 10,
            "status": "SKIPPED",
            "skip_reason": "continuous policy, not a TaskAllocator",
        },
    )

    rows = BenchmarkService(tmp_path).list_benchmarks()

    # MAPPO was never measured here, so its gap stays visible rather than hidden.
    assert len(rows) == 1
    assert rows[0].policy == "mappo"
    assert rows[0].mean_popw_score is None
    assert "not a TaskAllocator" in rows[0].skip_reason


def test_measured_policy_drops_the_skipped_config_row(tmp_path: Path) -> None:
    write_result(
        tmp_path,
        "exp_004",
        {"experiment_id": "exp_004", "policy": "mappo", "n_runs": 10, "status": "SKIPPED"},
    )
    write_result(
        tmp_path,
        "fleet_env_unified",
        {
            "harness": "FleetEnv",
            "robot_count": 5,
            "policies": [policy_row("mappo", 92.9)],
        },
    )

    rows = BenchmarkService(tmp_path).list_benchmarks()

    assert len(rows) == 1
    assert rows[0].status == "COMPLETE"
    assert rows[0].mean_popw_score == 92.9


def test_prefers_labeled_harness_over_duplicate_measurement(tmp_path: Path) -> None:
    write_result(
        tmp_path,
        "fleet_env_unified",
        {
            "harness": "FleetEnv",
            "scenario": "warehouse_v1_20tasks",
            "robot_count": 5,
            "policies": [policy_row("nearest", 90.75)],
        },
    )
    write_result(
        tmp_path,
        "exp_001",
        {
            "experiment_id": "exp_001",
            "policy": "nearest",
            "robot_count": 5,
            "n_runs": 30,
            "status": "COMPLETE",
            "mean_popw_score": 85.8,
        },
    )
    write_result(
        tmp_path,
        "mappo_eval",
        {
            "policy": "mappo",
            "n_runs": 30,
            "summary": {"mean_popw_score": 92.928, "mean_success_rate": 1.0},
        },
    )
    write_result(
        tmp_path,
        "fleet_env_unified_mappo",
        {"policies": [policy_row("mappo", 92.928)]},
    )

    rows = BenchmarkService(tmp_path).list_benchmarks()

    assert [(row.policy, row.mean_popw_score) for row in rows] == [
        ("mappo", 92.928),
        ("nearest", 90.75),
    ]
    assert rows[1].harness == "FleetEnv"


def test_excludes_e2e_smoke_runs_and_missing_dir(tmp_path: Path) -> None:
    write_result(
        tmp_path,
        "exp_e2e_001",
        {"experiment_id": "exp_e2e_001", "policy": "nearest", "mean_popw_score": 82.0},
    )

    assert BenchmarkService(tmp_path).list_benchmarks() == []
    assert BenchmarkService(tmp_path / "does-not-exist").list_benchmarks() == []


def test_ignores_unreadable_and_policyless_files(tmp_path: Path) -> None:
    broken = tmp_path / "broken" / "result.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{not json", encoding="utf-8")
    write_result(tmp_path, "no_policy", {"experiment_id": "no_policy", "mean_popw_score": 99.0})

    assert BenchmarkService(tmp_path).list_benchmarks() == []
