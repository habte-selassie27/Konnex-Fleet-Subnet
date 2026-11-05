#!/usr/bin/env python3
"""Generate the exp_006 fleet-scaling plot and table.

Reads experiments/results/exp_006/scaling_summary.json and writes:
  - experiments/results/exp_006/scaling_plot.png (success, PoPW, runtime vs robots)
  - experiments/results/exp_006/scaling_table.md

Usage:
    python scripts/plot_scaling.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = PROJECT_ROOT / "experiments" / "results" / "exp_006"


def main() -> None:
    summary = json.loads((RESULTS / "scaling_summary.json").read_text())
    rows = summary["scaling"]
    robots = [r["robot_count"] for r in rows]
    success = [r["mean_success_rate"] * 100 for r in rows]
    popw = [r["mean_popw_score"] for r in rows]
    runtime = [r["mean_completion_time_s"] for r in rows]

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes[0].plot(robots, success, "o-", color="#0EA5E9")
    axes[0].set_title("Success rate (%)")
    axes[0].set_xlabel("Robots")
    axes[0].set_ylim(0, 105)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(robots, popw, "o-", color="#10B981")
    axes[1].set_title("PoPW score")
    axes[1].set_xlabel("Robots")
    axes[1].set_ylim(0, 100)
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(robots, runtime, "o-", color="#F59E0B")
    axes[2].set_title("Completion time (s)")
    axes[2].set_xlabel("Robots")
    axes[2].grid(True, alpha=0.3)

    fig.suptitle("Fleet scaling — cost_optimizer, 40 tasks, 5 seeds")
    fig.tight_layout()
    out = RESULTS / "scaling_plot.png"
    fig.savefig(out, dpi=120)
    print(f"Plot saved to {out}")

    lines = [
        "| Robots | Success Rate | Time (s) | Collisions | PoPW Score |",
        "|--------|-------------|----------|-----------|-----------|",
    ]
    for r in rows:
        sr = f"{r['mean_success_rate'] * 100:.1f}% ± {r['std_success_rate'] * 100:.1f}%"
        tm = f"{r['mean_completion_time_s']:.1f} ± {r['std_completion_time_s']:.1f}"
        cl = f"{r['mean_collision_count']:.1f} ± {r['std_collision_count']:.1f}"
        pw = f"{r['mean_popw_score']:.1f} ± {r['std_popw_score']:.1f}"
        lines.append(f"| {r['robot_count']} | {sr} | {tm} | {cl} | {pw} |")
    (RESULTS / "scaling_table.md").write_text("\n".join(lines) + "\n")
    print(f"Table saved to {RESULTS / 'scaling_table.md'}")


if __name__ == "__main__":
    main()
