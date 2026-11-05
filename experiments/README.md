# experiments/

Benchmark experiments (Phase 3).

| Path | Contents |
|---|---|
| `configs/exp_001_nearest.yaml` … `exp_006_fleet_scaling.yaml` | Seeded, deterministic scenario configs |
| `scripts/run_experiment.py` | Runs one or all experiments, writes results + execution log |
| `scripts/generate_report.py` | Produces the comparison table |
| `results/` | **Real runs only** — populated by `make benchmark` |

**Integrity (TESTING_PLAN.md §7):** every result must pass `validate_benchmark_result` (≥5 runs, bounds, std dev, scenario version, 40-char git commit, artifact hash verification, execution log). No execution log = no result.

**Status: STUB — pending Phase 3.**
