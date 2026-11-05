#!/usr/bin/env python3
"""experiments/scripts/generate_report.py — Generate benchmark comparison report.

Reads all result.json files from experiments/results/ and produces:
1. A formatted ASCII table for terminal output
2. A Markdown table for README / KONNEX_APPLICATION.md

Usage:
    python experiments/scripts/generate_report.py
    python experiments/scripts/generate_report.py --markdown
    python experiments/scripts/generate_report.py --output report.md

Status: COMPLETE (Phase 3).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"


def load_results() -> list[dict[str, float | str | None]]:
    """Load all result.json files from experiments/results/.

    MAPPO evaluation results use a nested ``summary`` object (see
    ``evaluate_mappo.py``); flatten it so one report table can compare every
    policy.
    """
    results: list[dict[str, float | str | None]] = []
    for result_path in sorted(RESULTS_DIR.rglob("result.json")):
        # End-to-end smoke runs are not benchmark experiments.
        if result_path.parent.name.startswith("exp_e2e"):
            continue
        with result_path.open() as f:
            result = json.load(f)
        summary = result.get("summary")
        if isinstance(summary, dict):
            normalized: dict[str, float | str | None] = {**summary}
            for key, value in result.items():
                if key != "summary":
                    normalized[key] = value
            normalized.setdefault("status", "COMPLETE")
            results.append(normalized)
        else:
            results.append(result)
    return results


def _num(r: dict[str, float | str | None], key: str) -> float | None:
    """Safely extract a numeric value from a result dict."""
    val = r.get(key)
    return val if isinstance(val, (int, float)) else None


def fmt(value: object, spec: str = ".1f") -> str:
    """Format a numeric value, returning '—' for None."""
    if value is None or not isinstance(value, (int, float)):
        return "—"
    return f"{value:{spec}}"


def policy_label(r: dict[str, float | str | None]) -> str:
    """Policy name, suffixed with experiment id and fleet size when present."""
    policy = str(r.get("policy", "unknown"))
    parts: list[str] = []
    experiment_id = r.get("experiment_id")
    if isinstance(experiment_id, str) and experiment_id:
        parts.append(experiment_id)
    robot_count = r.get("robot_count")
    if isinstance(robot_count, int):
        parts.append(f"{robot_count} robots")
    return f"{policy} ({', '.join(parts)})" if parts else policy


def generate_ascii_table(results: list[dict[str, float | str | None]]) -> str:
    """Generate a formatted ASCII benchmark table."""
    sep = "-" * 105
    header = (
        f"{'Policy':<22} {'Success':<18} {'Time(s)':<18} "
        f"{'Collisions':<18} {'PoPW Score':<18} {'Status':<10}"
    )
    rows = [header, sep]

    for r in results:
        policy = policy_label(r)
        status = str(r.get("status", "UNKNOWN"))

        if status in ("NOT_RUN", "SKIPPED"):
            row = f"{policy:<22} {status:<18} {status:<18} {status:<18} {status:<18} {status:<10}"
        else:
            sr = fmt(_num(r, "mean_success_rate"), ".1%")
            sr_std = fmt(_num(r, "std_success_rate"), ".1%")
            t = fmt(_num(r, "mean_completion_time_s"), ".1f")
            t_std = fmt(_num(r, "std_completion_time_s"), ".1f")
            c = fmt(_num(r, "mean_collision_count"), ".1f")
            c_std = fmt(_num(r, "std_collision_count"), ".1f")
            p = fmt(_num(r, "mean_popw_score"), ".1f")
            p_std = fmt(_num(r, "std_popw_score"), ".1f")
            row = (
                f"{policy:<22} {sr}±{sr_std:<10} {t}±{t_std:<10} "
                f"{c}±{c_std:<10} {p}±{p_std:<18} {status:<10}"
            )
        rows.append(row)

    return "\n".join(rows)


def generate_markdown_table(results: list[dict[str, float | str | None]]) -> str:
    """Generate a Markdown benchmark table for docs."""
    lines = [
        "| Policy | Success Rate | Time (s) | Collisions | PoPW Score | Status |",
        "|--------|-------------|----------|-----------|-----------|--------|",
    ]

    for r in results:
        policy = policy_label(r)
        status = str(r.get("status", "UNKNOWN"))

        if status in ("NOT_RUN", "SKIPPED"):
            lines.append(f"| {policy} | {status} | {status} | {status} | {status} | {status} |")
        else:
            sr = fmt(_num(r, "mean_success_rate"), ".1%")
            sr_std = fmt(_num(r, "std_success_rate"), ".1%")
            t = fmt(_num(r, "mean_completion_time_s"), ".1f")
            t_std = fmt(_num(r, "std_completion_time_s"), ".1f")
            c = fmt(_num(r, "mean_collision_count"), ".1f")
            c_std = fmt(_num(r, "std_collision_count"), ".1f")
            p = fmt(_num(r, "mean_popw_score"), ".1f")
            p_std = fmt(_num(r, "std_popw_score"), ".1f")
            lines.append(
                f"| {policy} | {sr} ± {sr_std} | {t} ± {t_std} | "
                f"{c} ± {c_std} | {p} ± {p_std} | {status} |"
            )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate benchmark report from experiment results"
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Output Markdown table instead of ASCII",
    )
    parser.add_argument("--output", type=str, help="Write report to file instead of stdout")
    args = parser.parse_args()

    results = load_results()
    if not results:
        print(
            "No experiment results found in experiments/results/",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.markdown:
        report = generate_markdown_table(results)
    else:
        header = f"\nKONNEX FLEET BENCHMARK REPORT\nResults from {len(results)} experiment(s)\n\n"
        report = header + generate_ascii_table(results) + "\n"

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
