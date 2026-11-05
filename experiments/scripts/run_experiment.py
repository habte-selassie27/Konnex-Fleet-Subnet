#!/usr/bin/env python3
"""Experiment runner for benchmarking fleet policies.

Usage:
    python experiments/scripts/run_experiment.py --all --report
    python experiments/scripts/run_experiment.py --config <path> --report
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fleet.task_allocator.base import TaskAllocator
from fleet.task_allocator.cost_optimizer import CostOptimizerAllocator
from fleet.task_allocator.hungarian import HungarianAllocator
from fleet.task_allocator.nearest import NearestTaskAllocator

RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"
CONFIGS_DIR = PROJECT_ROOT / "experiments" / "configs"

# MAPPO is intentionally NOT in this map. The trained network is a continuous
# velocity policy (FleetEnv action space), not a TaskAllocator: it does not
# produce robot -> task assignments. Treating it as one previously caused the
# silent nearest-task fallback and mislabeled exp_004/exp_005 results. MAPPO
# is evaluated separately via ml/evaluation/rollout.py once a real checkpoint
# exists.
POLICY_MAP: dict[str, type[TaskAllocator]] = {
    "nearest": NearestTaskAllocator,
    "hungarian": HungarianAllocator,
    "cost_optimizer": CostOptimizerAllocator,
}

SKIP_REASONS: dict[str, str] = {
    "mappo": (
        "MAPPO is a continuous velocity policy evaluated through FleetEnv, "
        "not a TaskAllocator. Use ml/evaluation/rollout.py with a real "
        "checkpoint; exp_004/exp_005 are NOT RUN."
    ),
}


@dataclass
class SingleRunResult:
    seed: int
    policy: str
    tasks_completed: int
    tasks_total: int
    success_rate: float
    completion_time_s: float
    collision_count: int
    energy_consumed: float
    popw_score: float
    run_id: str = ""
    git_commit: str = ""


@dataclass
class ExperimentResult:
    experiment_id: str
    policy: str
    scenario_id: str
    seed_range: list[int]
    n_runs: int
    robot_count: int | None = None
    mean_success_rate: float | None = None
    std_success_rate: float | None = None
    mean_completion_time_s: float | None = None
    std_completion_time_s: float | None = None
    mean_collision_count: float | None = None
    std_collision_count: float | None = None
    mean_popw_score: float | None = None
    std_popw_score: float | None = None
    status: str = "NOT_RUN"
    skip_reason: str = ""
    run_id: str = ""
    git_commit: str = ""
    execution_log_path: str = ""
    ran_at: str = ""


def _execute_single_run(
    policy_name: str,
    seed: int,
    robot_count: int,
    task_count: int,
    time_limit_s: float,
    failure_injection: bool,
) -> SingleRunResult:
    """Run one deterministic mission through the real FleetOrchestrator.

    Uses the same execution path as the validator's in-process executor
    (robots, collisions, energy are simulated, never fabricated — AGENTS.md
    Law 1) and the same PoPWScoringEngine used for evaluation artifacts, so
    benchmark scores are directly comparable to validator scores.
    """
    from fleet.mission_manager import MissionConfig
    from fleet.orchestrator import FailurePlan, FleetOrchestrator
    from robotics.models.failure import FailureType
    from validator.scoring.engine import MissionResult, PoPWScoringEngine

    config = MissionConfig(
        robot_count=robot_count,
        task_count=task_count,
        seed=seed,
        time_limit_s=time_limit_s,
        scenario_id=f"warehouse_v1_{task_count}tasks",
    )
    failure_plan: FailurePlan | None = None
    if failure_injection:
        failure_plan = FailurePlan(
            robot_id=f"robot_{robot_count - 1}",
            failure_type=FailureType.COMMUNICATION_LOSS,
            after_elapsed_s=5.0,
        )
    orchestrator = FleetOrchestrator(allocator=POLICY_MAP[policy_name]())
    outcome = orchestrator.run_mission(seed, config, failure_plan=failure_plan)

    score = PoPWScoringEngine().score(
        MissionResult(
            tasks_completed=outcome.tasks_completed,
            tasks_total=outcome.tasks_total,
            elapsed_s=outcome.elapsed_s,
            time_limit_s=config.time_limit_s,
            collision_count=outcome.collision_count,
            energy_consumed=outcome.energy_consumed,
            energy_budget=config.robot_count * 100.0,
            failure_count=outcome.failure_count,
        )
    )
    return SingleRunResult(
        seed=seed,
        policy=policy_name,
        tasks_completed=outcome.tasks_completed,
        tasks_total=outcome.tasks_total,
        success_rate=(
            outcome.tasks_completed / outcome.tasks_total if outcome.tasks_total > 0 else 0.0
        ),
        completion_time_s=outcome.elapsed_s,
        collision_count=outcome.collision_count,
        energy_consumed=outcome.energy_consumed,
        popw_score=score.final,
    )


def _fmt(val: float | None, fmt_str: str) -> str:
    return format(val, fmt_str) if val is not None else "—"


def run_experiment(config_path: Path) -> ExperimentResult:
    """Run one experiment config and return its first/single result.

    Configs with a `scenario.robot_counts` list produce one result per robot
    count; callers that need all of them should use `run_experiment_set`.
    """
    return run_experiment_set(config_path)[0]


def run_experiment_set(config_path: Path) -> list[ExperimentResult]:
    """Run an experiment config, returning one result per fleet size.

    `scenario.robot_counts` (fleet-scaling studies) yields a result per count,
    each written to `experiments/results/{exp_id}/robots_{n}/result.json`, plus
    a `scaling_summary.json`. A plain `scenario.robot_count` yields one result
    at `experiments/results/{exp_id}/result.json`.
    """
    with config_path.open() as f:
        config = yaml.safe_load(f)

    exp_cfg = config["experiment"]
    scenario_cfg = config["scenario"]
    exp_id = exp_cfg["id"]

    robot_counts = scenario_cfg.get("robot_counts")
    if robot_counts:
        results = [
            _run_for_robot_count(
                config,
                robot_count=int(count),
                results_dir=RESULTS_DIR / exp_id / f"robots_{int(count)}",
            )
            for count in robot_counts
        ]
        _save_scaling_summary(exp_id, results)
        return results

    return [
        _run_for_robot_count(
            config,
            robot_count=scenario_cfg.get("robot_count"),
            results_dir=RESULTS_DIR / exp_id,
        )
    ]


def _run_for_robot_count(
    config: dict[str, Any], robot_count: int | None, results_dir: Path
) -> ExperimentResult:
    """Execute one config at a single fleet size."""
    exp_cfg = config["experiment"]
    scenario_cfg = config["scenario"]
    exec_cfg = config.get("execution", {})

    exp_id = exp_cfg["id"]
    policy_name = exp_cfg["policy"]
    seed_range = scenario_cfg.get("seed_range", [0, 0])
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    suffix = f"_r{robot_count}" if robot_count is not None else ""
    run_id = f"{exp_id}{suffix}_{timestamp}"

    result = ExperimentResult(
        experiment_id=exp_id,
        policy=policy_name,
        scenario_id=scenario_cfg["world"],
        seed_range=seed_range,
        n_runs=seed_range[1] - seed_range[0] + 1,
        robot_count=robot_count,
        run_id=run_id,
        git_commit=_get_git_commit(),
        ran_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )

    if policy_name not in POLICY_MAP:
        point = f" for policy {policy_name!r}" if policy_name else ""
        result.status = "SKIPPED"
        result.skip_reason = SKIP_REASONS.get(policy_name, f"policy not registered{point}")
        _save_result(result, results_dir)
        return result

    if robot_count is None:
        result.status = "SKIPPED"
        result.skip_reason = (
            "scenario.robot_count (or scenario.robot_counts) is required for orchestrator runs"
        )
        _save_result(result, results_dir)
        return result

    results_dir.mkdir(parents=True, exist_ok=True)
    log_path = results_dir / "execution.jsonl"

    # Logs are per-run, never append-only. A previous run is archived with its
    # run id so result.json always corresponds to exactly the rows in the
    # current execution log.
    if log_path.exists():
        log_path.rename(results_dir / f"execution.{run_id}.jsonl")

    raw_results: list[SingleRunResult] = []
    for seed in range(seed_range[0], seed_range[1] + 1):
        run = _execute_single_run(
            policy_name=policy_name,
            seed=seed,
            robot_count=robot_count,
            task_count=scenario_cfg["task_count"],
            time_limit_s=exec_cfg.get("time_limit_s", 600),
            failure_injection=scenario_cfg.get("failure_injection", False),
        )
        run.run_id = run_id
        run.git_commit = result.git_commit
        raw_results.append(run)
        with log_path.open("a") as f:
            f.write(json.dumps(asdict(run)) + "\n")

    import statistics

    scores = [r.popw_score for r in raw_results]
    times = [r.completion_time_s for r in raw_results]
    rates = [r.success_rate for r in raw_results]
    colls = [r.collision_count for r in raw_results]

    result.mean_success_rate = statistics.mean(rates)
    result.std_success_rate = statistics.stdev(rates) if len(rates) > 1 else 0.0
    result.mean_completion_time_s = statistics.mean(times)
    result.std_completion_time_s = statistics.stdev(times) if len(times) > 1 else 0.0
    result.mean_collision_count = statistics.mean(colls)
    result.std_collision_count = statistics.stdev(colls) if len(colls) > 1 else 0.0
    result.mean_popw_score = statistics.mean(scores)
    result.std_popw_score = statistics.stdev(scores) if len(scores) > 1 else 0.0
    result.execution_log_path = str(log_path)

    if result.std_popw_score and result.mean_popw_score:
        threshold = 0.15 * result.mean_popw_score
        result.status = "UNSTABLE" if result.std_popw_score > threshold else "COMPLETE"
    else:
        result.status = "COMPLETE"

    _save_result(result, results_dir)
    return result


def _save_result(result: ExperimentResult, results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    with (results_dir / "result.json").open("w") as f:
        json.dump(asdict(result), f, indent=2)


def _save_scaling_summary(exp_id: str, results: list[ExperimentResult]) -> None:
    """Write the cross-size scaling table (one row per robot count)."""
    summary = {
        "experiment_id": exp_id,
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scaling": [asdict(result) for result in results],
    }
    path = RESULTS_DIR / exp_id / "scaling_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(summary, f, indent=2)


def generate_benchmark_table(results: list[ExperimentResult]) -> str:
    sep = "-" * 100
    cols = ("Policy", "Success", "Time(s)", "Collisions", "PoPW", "Status")
    header = f"{cols[0]:<20} {cols[1]:<18} {cols[2]:<18} {cols[3]:<18} {cols[4]:<18} {cols[5]:<10}"
    rows = [header, sep]

    for r in results:
        policy = r.policy if r.robot_count is None else f"{r.policy} ({r.robot_count} robots)"
        if r.status in ("NOT_RUN", "SKIPPED"):
            s = r.status
            row = f"{policy:<20} {s:<18} {s:<18} {s:<18} {s:<18} {s:<10}"
        else:
            s = _fmt(r.mean_success_rate, ".1%")
            sr = _fmt(r.std_success_rate, ".1%")
            t = _fmt(r.mean_completion_time_s, ".2f")
            tr = _fmt(r.std_completion_time_s, ".2f")
            c = _fmt(r.mean_collision_count, ".1f")
            cr = _fmt(r.std_collision_count, ".1f")
            p = _fmt(r.mean_popw_score, ".1f")
            pr = _fmt(r.std_popw_score, ".1f")
            score_col = f"{p}±{pr}"
            row = (
                f"{policy:<20} {s}±{sr:<10} {t}±{tr:<10} "
                f"{c}±{cr:<10} {score_col:<18} {r.status:<10}"
            )
        rows.append(row)

    return "\n".join(rows)


def _get_git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=PROJECT_ROOT,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "UNKNOWN"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fleet benchmark runner")
    parser.add_argument("--config", type=str, help="Experiment config YAML path")
    parser.add_argument("--all", action="store_true", help="Run all configs")
    parser.add_argument("--report", action="store_true", help="Print table")
    args = parser.parse_args()

    if not args.config and not args.all:
        parser.print_help()
        sys.exit(1)

    if args.all:
        config_files = sorted(CONFIGS_DIR.glob("exp_00*.yaml"))
    else:
        assert args.config is not None
        config_files = [Path(args.config)]

    results: list[ExperimentResult] = []
    for cp in config_files:
        print(f"Running: {cp.name}")
        for r in run_experiment_set(cp):
            results.append(r)
            label = f"  [{r.robot_count} robots] " if r.robot_count else "  "
            print(f"{label}{r.status}", end="")
            if r.status == "SKIPPED" and r.skip_reason:
                print(f" — {r.skip_reason}")
            elif r.mean_popw_score is not None:
                print(f" — PoPW: {r.mean_popw_score:.1f}±{r.std_popw_score:.1f}")
            else:
                print()

    if args.report:
        print("\n" + generate_benchmark_table(results) + "\n")


if __name__ == "__main__":
    main()
