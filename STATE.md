# STATE.md — Verified State of konnex-fleet-subnet

Last updated: 2026-11-02

## How to read

- **VERIFIED** — implemented, tested, and observed running.
- **STUB** — interface defined, implementation pending or raises NotImplementedError.
- **BLOCKED** — cannot run in this environment; blocker documented.
- **PARTIAL** — works for the happy path; gaps listed.

## Verified done

| Component | Evidence |
|---|---|
| Lint (ruff, mypy, bandit, eslint, tsc) | `make lint` → all passed, 0 errors |
| Unit + integration tests | `make test` → 407 passed, 1 skipped |
| Frontend unit tests | `npm run test:unit` → 16 passed |
| Classical benchmark (nearest/hungarian/cost_optimizer) | `make benchmark` → exp_001/002/003 COMPLETE, 30 seeds each |
| MAPPO actor (BC+DAgger) | `experiments/results/mappo_eval/result.json` → 100% success, 92.9±2.1 PoPW, 30 seeds |
| MAPPO vs Hungarian significance | Welch t=2.883, p=0.003 (one-sided), Cohen's d=0.74 |
| Fleet scaling study (exp_006) | `experiments/results/exp_006/scaling_summary.json` + `scaling_plot.png` |
| Robustness (Phase 5) | `tests/integration/test_fleet_orchestration.py` → all pass; `experiments/results/robustness_table.md` |
| Two-validator reproducibility | `make verify-repro` → PASS, spread 0.0000 ≤ 0.5, 4 seeds × 3 policies |
| Unified cross-harness benchmark | `make benchmark-unified` → 5 policies × 30 seeds in FleetEnv; MAPPO 92.9, expert 92.8, hungarian 92.2, nearest 90.8, cost_optimizer 90.1 (`experiments/results/fleet_env_unified/`) |
| Multi-validator consensus (real container) | `make verify-consensus` with `KONNEX_POLICY_IMAGE=konnex-echo-policy` → 3/3 seeds CONSENSUS, max spread 0.0000 (`experiments/results/validator_consensus/consensus.json`) |
| Benchmark log integrity | `make verify-logs` → PASS, 13 artifacts, run-partitioned, no duplicate seeds |
| MLflow evidence (file-backed) | `make mlflow-ingest` → 15 runs in `mlruns/` (experiment `konnex-fleet-benchmarks`) |
| Gazebo → fleet loop wiring | `GazeboRobotAdapter` injected via `RobotFactory`; `sim_backend` reports the live adapter; `docker compose --profile simulation up gazebo backend-sim`. Live run NOT RUN on this host (no `gz`/`rclpy` outside the container) |
| Payment tests never spend real USDC | `tests/conftest.py` pins `PAYMENT_PROVIDER=mock`; `.env` may hold real Circle credentials |
| PoPW scoring engine | `tests/unit/test_scoring_engine.py` → pass |
| Evaluation artifacts (SHA-256) | `tests/unit/test_evaluation_artifact.py` → pass |
| Docker policy sandbox | `tests/unit/test_docker_policy_executor.py` → pass (transport faked; real Docker path not exercised here) |
| Konnex provider (mock) | `tests/integration/test_konnex_adapter.py` → pass; mock provider complete |
| Agentic payments (mock) | `tests/integration/test_payments_api.py` → pass; `make payment-demo` works |
| Demo launch | `make demo` → boots backend + dashboard + mission (verified previously) |

## Stub / partial

| Component | Status | Notes |
|---|---|---|
| MAPPO PPO fine-tuning | Negative result | `experiments/results/mappo_ppo_ft/` — collapsed to 1–10% success; BC checkpoint retained |
| Konnex real provider | STUB | SDK not publicly accessible (see docs/konnex.md) |
| Gazebo live execution | VERIFIED (in-container) | `docker build -f simulation/Dockerfile.gazebo -t fleet-sim-test simulation/` then `docker run --rm -v "\$PWD:/ws/repo" fleet-sim-test` → 26 passed, 0 skipped. Host runs still self-skip (no `gz` on PATH) by design. |
| Docker policy sandbox (real container) | VERIFIED | Built `konnex-echo-policy` image (policy_server.py implementing the container protocol). `KONNEX_POLICY_IMAGE=konnex-echo-policy .venv/bin/python -m pytest tests/unit/test_docker_policy_executor.py::test_real_container_end_to_end` → PASSED. Isolation flags + timeout + crash mapping also covered by faked-transport tests. |
| Physical robot adapter | STUB | Out of scope (Mainnet tier) |
| Multi-validator consensus (on-chain) | STUB | Out of scope |
| On-chain commitment / marketplace / KNX rewards | STUB | Out of scope |

## Blocked (needs Joshua)

1. **Demo video** — record per `DEMO_SCRIPT.md`, upload, paste URL into README + KONNEX_APPLICATION.md.
2. **Team info** — fill `[Team Name]` / backgrounds in KONNEX_APPLICATION.md.
3. **Konnex SDK access** — repo `github.com/konnex-world/konnex` not publicly accessible; real provider blocked.
4. **(Optional) Gazebo on host** — sim tests now run in-container (26/26 pass); host `gz` not needed for grant demo.

## Grant-tier (Spark) checklist

- [x] `make demo` runs end-to-end in under 3 minutes
- [x] `make benchmark` produces a comparison table with real numbers
- [x] At least 3 policies with statistically meaningful differences
- [x] Validator reproduces any result from (policy_hash + seed) — spread 0.0
- [x] Dashboard shows live robot state during demo
- [x] All results in `experiments/results/` are from actual runs
- [ ] README contains a demo video link — needs Joshua
- [ ] `KONNEX_APPLICATION.md` complete — needs team info + video link

## Risks and caveats for grant reviewers

- MAPPO is evaluated via FleetEnv rollouts, not the TaskAllocator benchmark, because it outputs continuous velocities rather than task assignments. The methodology difference is documented in README and KONNEX_APPLICATION.md.
- The 30-seed MAPPO result uses a BC+DAgger actor; PPO fine-tuning did not improve it (negative result documented).
- Gazebo live execution VERIFIED in-container: `docker build -f simulation/Dockerfile.gazebo -t fleet-sim-test simulation/` then `docker run --rm -v "\$PWD:/ws/repo" fleet-sim-test` → 26 passed, 0 skipped. The gz↔ROS bridge publishes `/model/robot_0/odometry`, `/robot_0/scan`, `/robot_0/cmd_vel` per robot. Host runs still skip (no `gz` on PATH) by design.
- Konnex integration: TWO-TIER. Spark: HTTP-based RealKonnexProvider (3 documented endpoints) + mock. Launch: BittensorKonnexProvider skeleton (protocol/konnex/bittensor_provider.py) + FleetMissionSynapse (protocol/konnex/synapse.py) using konnex-chain-sdk (bittensor fork). Live chain ops remain STUBs (need testnet funds + registered hotkey). 24 contract tests pass.
- All benchmark numbers are from real runs; no fabricated data.
