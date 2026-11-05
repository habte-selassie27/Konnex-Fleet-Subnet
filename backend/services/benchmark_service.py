"""Benchmark result reader for the dashboard (Phase 3/9).

Reads the artifacts `make benchmark` writes under ``experiments/results/**/result.json``
— the same files ``experiments/scripts/generate_report.py`` summarizes. The API
never invents numbers: a missing or unreadable result file is reported as an empty
list (or a SKIPPED row), never as a fabricated score (AGENTS.md Law 1).

Status: COMPLETE (Phase 3 artifacts surfaced in Phase 9 dashboard).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import structlog

from backend.schemas import BenchmarkResult

logger = structlog.get_logger(__name__)

# Fields shared by every policy row in the multi-policy unified run.
_UNIFIED_BASE_FIELDS = ("scenario", "robot_count", "seed_range", "ran_at", "git_commit", "harness")

# Statuses backed by an actual execution (as opposed to SKIPPED/NOT_RUN/FAILED).
_MEASURED_STATUSES = frozenset({"COMPLETE", "UNSTABLE"})


class BenchmarkService:
    """Normalize the result.json variants into one comparable row list."""

    def __init__(self, results_dir: Path) -> None:
        self._results_dir = results_dir

    def list_benchmarks(self) -> list[BenchmarkResult]:
        """Return one comparable benchmark row per policy/fleet size.

        Several artifacts measure the same configuration: the unified FleetEnv
        run scores every policy on identical seeds, while older per-experiment
        runs (exp_001..003) and the MAPPO evaluation repeat those policies. The
        dashboard shows the apples-to-apples row (labeled harness) and drops the
        duplicate measurement, keeping the raw artifact name in ``source``.
        Policies that were never measured keep their SKIPPED/NOT_RUN row so the
        gap stays visible (Law 1).
        """
        collected: list[BenchmarkResult] = []
        if not self._results_dir.exists():
            logger.warning("benchmark_results_missing", path=str(self._results_dir))
            return collected
        for path in sorted(self._results_dir.rglob("result.json")):
            # End-to-end smoke runs are not benchmark experiments
            # (same exclusion as experiments/scripts/generate_report.py).
            if path.parent.name.startswith("exp_e2e"):
                continue
            for raw in self._load(path):
                row = self._to_result(raw, path)
                if row is not None:
                    collected.append(row)

        measured = [row for row in collected if row.status in _MEASURED_STATUSES]
        measured_policies = {row.policy for row in measured}
        rows = [
            row
            for row in collected
            if row.status in _MEASURED_STATUSES or row.policy not in measured_policies
        ]

        rows = _best_per_scale(rows)
        rows = _best_per_measurement(rows)

        rows.sort(
            key=lambda row: (
                row.mean_popw_score is None,
                -(row.mean_popw_score or 0.0),
                row.policy,
                row.experiment_id,
            )
        )
        return rows

    def _load(self, path: Path) -> list[dict[str, Any]]:
        """Read one result file, flattening the known JSON shapes."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("benchmark_result_unreadable", path=str(path), error=str(error))
            return []
        if not isinstance(payload, dict):
            return []

        result = cast(dict[str, Any], payload)

        # Shape 1: unified harness run — one file, one row per policy
        # (experiments/results/fleet_env_unified/result.json).
        policies = result.get("policies")
        if isinstance(policies, list):
            base = {field: result.get(field) for field in _UNIFIED_BASE_FIELDS}
            return [
                {**base, **cast(dict[str, Any], entry)}
                for entry in policies
                if isinstance(entry, dict)
            ]

        # Shape 2: ML evaluation — metrics live under "summary"
        # (experiments/results/mappo_eval/result.json).
        summary = result.get("summary")
        if isinstance(summary, dict):
            return [
                {
                    **cast(dict[str, Any], summary),
                    **{key: value for key, value in result.items() if key != "summary"},
                }
            ]

        # Shape 3: allocator/scaling runs — metrics at the top level.
        return [result]

    def _to_result(self, raw: dict[str, Any], path: Path) -> BenchmarkResult | None:
        """Validate and normalize one policy row."""
        policy = _text(raw.get("policy"))
        if policy is None:
            return None

        try:
            relative = path.parent.relative_to(self._results_dir)
        except ValueError:
            relative = path.parent
        group = relative.parts[0] if relative.parts else path.parent.name

        scenario = _text(raw.get("scenario_id")) or _text(raw.get("scenario")) or ""
        mean_score = _number(raw.get("mean_popw_score"))
        reported_status = _text(raw.get("status"))
        status = reported_status or ("COMPLETE" if mean_score is not None else "NOT_RUN")

        return BenchmarkResult(
            experiment_id=_text(raw.get("experiment_id")) or group or path.parent.name,
            policy=policy,
            scenario_id=scenario,
            harness=_text(raw.get("harness")) or "",
            robot_count=_integer(raw.get("robot_count")),
            n_runs=_integer(raw.get("n_runs")) or len(_seed_list(raw.get("seed_range"))),
            seed_range=_seed_list(raw.get("seed_range")),
            mean_popw_score=mean_score,
            std_popw_score=_number(raw.get("std_popw_score")),
            mean_success_rate=_number(raw.get("mean_success_rate")),
            std_success_rate=_number(raw.get("std_success_rate")),
            mean_collision_count=_number(raw.get("mean_collision_count")),
            std_collision_count=_number(raw.get("std_collision_count")),
            mean_completion_time_s=_number(raw.get("mean_completion_time_s")),
            std_completion_time_s=_number(raw.get("std_completion_time_s")),
            status=status,
            skip_reason=_text(raw.get("skip_reason")) or "",
            ran_at=_text(raw.get("ran_at")) or "",
            git_commit=_text(raw.get("git_commit")) or "",
            source=str(relative),
        )


def _preference(row: BenchmarkResult) -> tuple[bool, int, float]:
    """Prefer the run with a named harness, more runs, then a higher score."""
    return (bool(row.harness), row.n_runs or 0, row.mean_popw_score or 0.0)


def _best_per_scale(rows: list[BenchmarkResult]) -> list[BenchmarkResult]:
    """Keep the preferred row for each (policy, robot_count) pair."""
    best: dict[tuple[str, int | None], BenchmarkResult] = {}
    for row in rows:
        key = (row.policy, row.robot_count)
        current = best.get(key)
        if current is None or _preference(row) > _preference(current):
            best[key] = row
    return list(best.values())


def _best_per_measurement(rows: list[BenchmarkResult]) -> list[BenchmarkResult]:
    """Collapse identical measurements reported by two artifacts."""
    best: dict[tuple[str, int | None, float | None], BenchmarkResult] = {}
    for row in rows:
        score = None if row.mean_popw_score is None else round(row.mean_popw_score, 4)
        key = (row.policy, row.n_runs, score)
        current = best.get(key)
        if current is None or _preference(row) > _preference(current):
            best[key] = row
    return list(best.values())


def _text(value: Any) -> str | None:
    """Return a non-empty string or None."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number(value: Any) -> float | None:
    """Return a float for real numeric values (bools excluded), else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _integer(value: Any) -> int | None:
    """Return an int for real integer values, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _seed_list(value: Any) -> list[int]:
    """Return the seed range as a list of ints (empty when absent/malformed)."""
    if not isinstance(value, list):
        return []
    return [seed for seed in value if isinstance(seed, int) and not isinstance(seed, bool)]
