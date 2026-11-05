# Benchmarking

> Status: COMPLETE (Phase 3) for the classical policies; MAPPO is evaluated on a
> separate path (see below). Fleet-scaling support (`scenario.robot_counts`)
> added in Phase 5.

## Experiments

`experiments/configs/exp_00X_*.yaml` — seeded, deterministic scenario configs:

| Config | Policy | Fleet size | Tasks | Seeds | Status |
|---|---|---|---|---|---|
| exp_001 | nearest | 5 | 20 | 30 (1000–1029) | COMPLETE |
| exp_002 | hungarian | 5 | 20 | 30 (1000–1029) | COMPLETE |
| exp_003 | cost_optimizer | 5 | 20 | 30 (1000–1029) | COMPLETE |
| exp_004 | mappo | 5 | 20 | 10 (1000–1009) | SKIPPED — see below |
| exp_005 | mappo + failure | 5 | 20 | 10 (1000–1009) | SKIPPED — see below |
| exp_006 | cost_optimizer | 5 / 10 / 20 | 40 | 5 (1000–1004) | COMPLETE |

Time limit: 600 s. `make benchmark` runs every config and prints the comparison
table; `make benchmark-single EXP=exp_006_fleet_scaling` runs one config.

## Fleet-scaling studies

A config may set `scenario.robot_counts: [5, 10, 20]` instead of a single
`scenario.robot_count`. The runner then executes the whole seed range once per
fleet size and writes:

```
experiments/results/exp_006/
├── robots_5/result.json
├── robots_10/result.json
├── robots_20/result.json
└── scaling_summary.json    # all three rows in one file
```

`result.json` rows carry a `robot_count` field; `generate_report.py` appends it
to the policy label so a scaled row is never confused with the baseline run.

## Why exp_004 / exp_005 are SKIPPED

MAPPO is a continuous velocity policy evaluated through `FleetEnv` rollouts, not
a `TaskAllocator`. Registering it in `POLICY_MAP` caused a silent nearest-task
fallback that produced mislabelled numbers (see
`experiments/results/exp_004/README.md`). MAPPO is therefore benchmarked with:

```bash
python experiments/scripts/evaluate_mappo.py \
  --checkpoint ml/checkpoints/step_bc_v3.pt --seeds 1000-1029
```

## Metric definitions

- **Collisions are edge-triggered.** `CollisionMonitor` emits one event when a
  robot pair enters the contact radius (< 0.5 m) and one more if a near miss
  escalates to contact — not one event per 10 Hz tick. A sustained 10 s contact
  therefore counts as 1, not ~100. Without this, a single deadlock inflated
  `collision_count` into the thousands and saturated the PoPW safety component.
- **PoPW** comes from `validator/scoring/engine.py`, the same engine the
  validator uses, so benchmark and evaluation scores are directly comparable.

## Integrity

What the runner enforces today:

- Deterministic scenarios: identical `(seed, robot_count, task_count)` produce
  an identical scenario, so any validator can reconstruct a run.
- One `execution.jsonl` row per seed; a previous log is archived with its run id
  rather than overwritten, so `result.json` always matches the rows on disk.
- Statistics are computed from the executed rows only, and `std > 15% of mean`
  marks a result `UNSTABLE` instead of hiding the variance.
- `git_commit` is recorded per result (`UNKNOWN` when the tree is not a git
  checkout, as in this workspace).

`validate_benchmark_result` (TESTING_PLAN.md §7) — which additionally checks
bounds, non-negative collisions, scenario-version match and artifact hashes —
remains a **specification, not implemented**. Do not claim results were
validated by it.
