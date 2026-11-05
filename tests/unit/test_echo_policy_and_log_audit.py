"""Tests for the committed echo policy and the benchmark-log auditor."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_benchmark_logs import audit
from validator.examples.echo_policy.policy_server import assign
from validator.examples.echo_policy.weights import echo_policy_hash


def _robot(robot_id: str, x: float) -> dict[str, object]:
    return {"id": robot_id, "x": x, "y": 0.0}


def _task(task_id: str, x: float) -> dict[str, object]:
    return {"id": task_id, "pickup": [x, 0.0], "delivery": [x + 1.0, 0.0]}


def test_echo_policy_assigns_nearest_pickup() -> None:
    robots = [_robot("robot_0", 0.0), _robot("robot_1", 10.0)]
    tasks = [_task("far", 9.0), _task("near", 1.0)]

    assignments = {item["robot_id"]: item["task_id"] for item in assign(robots, tasks)}

    assert assignments["robot_0"] == "near"
    assert assignments["robot_1"] == "far"


def test_echo_policy_is_deterministic() -> None:
    robots = [_robot("robot_0", 0.0), _robot("robot_1", 5.0)]
    tasks = [_task("a", 1.0), _task("b", 4.0)]

    assert assign(robots, tasks) == assign(robots, tasks)


def test_echo_policy_never_reuses_a_task() -> None:
    robots = [_robot("robot_0", 0.0), _robot("robot_1", 0.1)]
    tasks = [_task("only", 1.0)]

    assignments = assign(robots, tasks)

    assert len(assignments) == 1
    assert assignments[0]["task_id"] == "only"


def test_echo_policy_hash_is_a_sha256_digest() -> None:
    digest = echo_policy_hash()

    assert len(digest) == 64
    assert all(char in "0123456789abcdef" for char in digest)
    assert digest == echo_policy_hash()


# ── Benchmark log auditor ──────────────────────────────────────────────────


def _write_run(
    root: Path,
    rows: int,
    *,
    seeds: list[int] | None = None,
    commit: str = "abc123",
    n_runs: int | None = None,
) -> None:
    seed_list = seeds if seeds is not None else list(range(1000, 1000 + rows))
    declared_runs = n_runs if n_runs is not None else len(seed_list)
    scores = [80.0] * len(seed_list)
    run_dir = root / "exp_test"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "result.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp_test",
                "policy": "nearest",
                "n_runs": declared_runs,
                "mean_popw_score": sum(scores) / len(scores),
                "status": "COMPLETE",
                "run_id": "exp_test_r5_20260101T000000Z",
                "git_commit": commit,
            }
        )
    )
    with (run_dir / "execution.jsonl").open("w") as handle:
        for seed in seed_list:
            handle.write(
                json.dumps(
                    {
                        "seed": seed,
                        "popw_score": 80.0,
                        "run_id": "exp_test_r5_20260101T000000Z",
                    }
                )
                + "\n"
            )


def test_clean_logs_pass_audit(tmp_path: Path) -> None:
    _write_run(tmp_path, rows=3)
    assert audit(tmp_path) == []


def test_duplicate_seeds_are_reported(tmp_path: Path) -> None:
    _write_run(tmp_path, rows=3, seeds=[1000, 1000, 1001])
    problems = audit(tmp_path)

    assert any("duplicate seeds" in problem for problem in problems)


def test_row_count_mismatch_is_reported(tmp_path: Path) -> None:
    _write_run(tmp_path, rows=2, seeds=[1000, 1001], n_runs=3)
    problems = audit(tmp_path)

    assert any("rows" in problem for problem in problems)


def test_unknown_git_commit_is_reported(tmp_path: Path) -> None:
    _write_run(tmp_path, rows=2, commit="UNKNOWN")
    problems = audit(tmp_path)

    assert any("git_commit" in problem for problem in problems)
