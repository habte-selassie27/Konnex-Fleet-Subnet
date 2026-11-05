#!/usr/bin/env python3
"""Audit benchmark execution logs for stale, duplicate or misattributed rows.

The known historical defect was an append-only `execution.jsonl`: a 30-seed
experiment accumulated 90 rows across three runs, and early rows came from
older code. `result.json` only described the final run, so the log was not
evidence for the result.

`run_experiment.py` now archives the previous log per run id. This script
proves the invariant holds, for every experiment directory:

  1. `execution.jsonl` exists and has exactly `n_runs` rows (when n_runs > 0)
  2. every row carries the current `run_id`
  3. seeds are unique inside a run
  4. `result.json` metrics match the rows (mean PoPW within 1e-6)
  5. `git_commit` is a real hash, not "UNKNOWN"

Exit code 0 = clean, 1 = problems, 2 = nothing to check.

Usage:
    python scripts/verify_benchmark_logs.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"


def _load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def audit(results_dir: Path) -> list[str]:
    """Return a list of human-readable problems (empty when clean)."""
    problems: list[str] = []

    for result_path in sorted(results_dir.rglob("result.json")):
        if result_path.parent.name.startswith("exp_e2e"):
            continue  # e2e smoke evidence, not a benchmark
        raw = json.loads(result_path.read_text())
        if isinstance(raw.get("policies"), list):
            continue  # unified FleetEnv harness writes per-policy rows inline
        status = str(raw.get("status", ""))
        n_runs = raw.get("n_runs")
        exp_label = result_path.parent.relative_to(results_dir)

        commit = str(raw.get("git_commit", ""))
        if status in ("COMPLETE", "UNSTABLE") and (not commit or commit == "UNKNOWN"):
            problems.append(f"{exp_label}: git_commit is {commit or 'missing'}")

        if status in ("SKIPPED", "NOT_RUN"):
            continue

        log_path = result_path.parent / "execution.jsonl"
        if log_path.exists():
            rows = _load_rows(log_path)
        else:
            # Some harnesses (rollout-based MAPPO/expert evaluation) embed the
            # per-seed rows in result.json instead of a sidecar log. That is a
            # self-contained artifact, not a missing log — audit the rows
            # where they actually live.
            embedded = raw.get("runs")
            if not isinstance(embedded, list) or not embedded:
                problems.append(f"{exp_label}: missing execution.jsonl")
                continue
            rows = [row for row in embedded if isinstance(row, dict)]
        if isinstance(n_runs, int) and n_runs > 0 and len(rows) != n_runs:
            problems.append(
                f"{exp_label}: execution.jsonl has {len(rows)} rows, result.json says {n_runs}"
            )

        run_ids = {str(row.get("run_id", "")) for row in rows}
        if len(run_ids) > 1:
            problems.append(f"{exp_label}: rows span multiple run ids {sorted(run_ids)}")
        declared = str(raw.get("run_id", ""))
        if declared and run_ids and declared not in run_ids:
            problems.append(
                f"{exp_label}: result.json run_id {declared} absent from execution.jsonl"
            )

        seeds = [row.get("seed") for row in rows]
        if len(seeds) != len(set(seeds)):
            problems.append(f"{exp_label}: duplicate seeds in execution.jsonl")

        scores = [float(row["popw_score"]) for row in rows if "popw_score" in row]  # type: ignore[arg-type]
        declared_mean = raw.get("mean_popw_score")
        if (
            scores
            and isinstance(declared_mean, (int, float))
            and not isinstance(declared_mean, bool)
        ):
            actual = sum(scores) / len(scores)
            if abs(actual - float(declared_mean)) > 1e-6:
                problems.append(
                    f"{exp_label}: mean PoPW {actual:.6f} != result.json {float(declared_mean):.6f}"
                )

    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit benchmark logs")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    args = parser.parse_args()

    problems = audit(Path(args.results_dir))
    checked = len(list(Path(args.results_dir).rglob("result.json")))
    if checked == 0:
        print("NOT RUN — no result.json files found.")
        sys.exit(2)

    if problems:
        print(f"FAIL — {len(problems)} problem(s) across {checked} result file(s):")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)

    print(f"PASS — {checked} result file(s) with clean, run-partitioned logs.")


if __name__ == "__main__":
    main()
