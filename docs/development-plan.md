# Development Plan — Phases & Acceptance Criteria

> **Phase 0 deliverable** (BUILD.md §3). Status: COMPLETE (plan).
> Phases from PLAN.md §11; gate checklists from TESTING_PLAN.md §10.
> **Rule:** a phase is not complete until its gate checklist passes and its test suite passes.

---

## Phase Overview

| # | Deliverable | Acceptance Criterion | Status |
|---|---|---|---|
| 0 | Architecture docs + repo skeleton | Internally consistent design | **COMPLETE** |
| 1 | Simulation: 5 robots in warehouse | Robots navigate independently | **WIRING COMPLETE — live Gazebo run NOT RUN (containerized)** |
| 2 | Fleet coordination: baseline policies | 5 robots complete multi-task mission | **COMPLETE (headless)** |
| 3 | Benchmarking engine | Policies compared automatically | **COMPLETE — exp_001–003 + exp_006 scaling** |
| 4 | MARL (MAPPO) | Learned policy beats or matches best baseline | **COMPLETE — BC + DAgger actor: 92.9 ± 2.1 PoPW vs Hungarian 90.7** |
| 5 | Robustness: failures + comm loss | Fleet recovers from 1 robot failure | **COMPLETE (headless) — Gazebo injection STUB** |
| 6 | Validator service | Two validators reproduce same score ±0.5 | **COMPLETE (in-process) — Docker sandbox STUB** |
| 7 | PoPW prototype | Mission produces verifiable evaluation artifact | **COMPLETE — artifact re-derives from published components** |
| 8 | Konnex adapter | Core system integrates without modification | **COMPLETE (boundary) — live SDK calls STUB (researched, not integrated)** |
| 9 | Dashboard | Third party understands system from UI alone | **COMPLETE — live WS telemetry (10 Hz), 3D map, live PoPW score, real policy, energy chart, no mock data** |
| 10 | Final demo | `make demo` + `make benchmark` produce full results | **COMPLETE — demo.sh, real benchmark results (exp_001–003), e2e suite green** |

## Phase Gate Checklists (TESTING_PLAN.md §10)

### Phase 0 — Architecture
```
[✓] docs/architecture.md exists and describes all components
[✓] docs/mvp.md defines what MVP includes and excludes
[✓] Repository structure matches BUILD.md Section 1
[✓] All dependency versions pinned in requirements.txt
[✓] make lint passes (no code yet = zero errors)
```

### Phase 1 — Simulation
```
[✓] simulation/ is a buildable ROS 2 ament package (package.xml + CMakeLists.txt)
[✓] simulation/Dockerfile.gazebo — Humble + Gazebo Harmonic + ros_gz_bridge (make sim)
[✓] Warehouse world launch (ros_gz_sim, Harmonic) + multi-robot spawn launch (xacro URDF, deterministic seeded poses)
[✓] gz↔ROS bridge (odom/scan/imu/cmd_vel/tf per robot) — generated at launch + reference robot_bridge.yaml
[✓] fleet_agent go-to-goal node per robot (LiDAR obstacle stop + rotate recovery + modeled battery)
[✓] GazeboRobotAdapter (RobotAdapter protocol, transport-injected) + backend/ros ROSBridge (SIM_MODE=gazebo)
[✓] tests/simulation/ passes: 19 headless PASSED + 6 Gazebo-gated SKIPPED (honest NOT RUN here)
[✓] Asset validation + adapter + bridge unit tests (35 tests) — no Gazebo required
[ ] Gazebo launches without errors: make sim — ATTEMPTED 2026-11-02, BLOCKED by bandwidth:
    docker compose build gazebo pulls osrf/ros:humble-desktop + gz-harmonic (~4-6 GB).
    Measured ~0.3 MB/s on this host; the pull did not finish in-session (277 s for
    ~200 MB of a single 811 MB layer). Docker caches partial layers, so re-running
    `make sim` resumes. No image, container, or score was produced — nothing above
    is claimed to have run.
[ ] 5 robot models visible in Gazebo — NOT RUN
[ ] All 5 robots complete independent navigation to test goals — NOT RUN
[ ] LiDAR scans returning data (verify via ROS 2 topic echo) — NOT RUN
[ ] Battery model draining correctly during movement (Gazebo) — NOT RUN
```

### Phase 2 — Fleet Coordination
```
[✓] All 3 baseline allocators implemented
[✓] tests/unit/test_task_allocator.py: 100% pass
[✓] tests/integration/test_fleet_orchestration.py: 100% pass
[✓] 5 robots complete a 20-task mission (headless orchestrator; Gazebo observation NOT RUN)
[✓] Robot failure triggers task reassignment (test_tasks_reassigned_to_remaining_robots)
[ ] make lint passes — 6 pre-existing ruff errors outside this work
```

### Phase 3 — Benchmarking
```
[✓] Scenario generator produces deterministic scenarios
[✓] tests/unit/test_scenario_generator.py: 100% pass
[✓] exp_001 (nearest), exp_002 (hungarian), exp_003 (cost_optimizer) all run to completion
[✓] exp_006 fleet scaling (5 / 10 / 20 robots) runs per robot count
[ ] Results saved in experiments/results/ with valid artifact hashes
    — benchmark rows carry no evaluation artifact (only validator evaluations do)
[✓] make benchmark produces comparison table
[✓] Results provide execution logs for all 3 experiments
```

### Phase 4 — MARL
```
[✓] Random policy runs 1000 steps without crash
[✓] Trained policy produces non-zero task completion in evaluation
[✓] exp_004 result saved (SKIPPED with an explicit reason — see below)
[✓] MLflow callback implemented (degrades to local logging without a server)
[ ] MAPPO trains for at least 500K timesteps without error — training runs are
    short (20K–100K); no 500K-step run has been executed
[ ] MLflow server running for tracking — NOT RUN
```
**Honest status:** the published MAPPO policy is the BC + DAgger actor
(`ml/checkpoints/step_bc_v3.pt`): 100% mission success, 92.9 ± 2.1 PoPW over 30
seeds via `experiments/scripts/evaluate_mappo.py`. Plain PPO fine-tuning from
that checkpoint **regressed** in both attempts (1–7.5% success); see
`experiments/results/mappo_ppo_ft/README.md`. `exp_004`/`exp_005` stay `SKIPPED`
in the TaskAllocator benchmark because MAPPO emits waypoints, not assignments.
The earlier 5,000,039-timestep run rolled out a random actor and its results are
invalidated.

### Phase 5 — Robustness
```
[✓] Failure injection API: POST /robots/{id}/fail (tests/integration/test_robots_api.py)
[✓] FailureDetector: battery 20%/10%, stuck 30s, comm loss 10s, nav failure
[✓] Communication degradation model (latency + packet loss)
[✓] Orchestrator health monitor (5 Hz) + recover_tasks_from_robot + reassignment
[✓] Fleet recovery time measured and reported (MissionOutcome.recovery_time_s)
[✓] tests/integration/test_fleet_orchestration.py: 100% pass (partial failure, NO_ROBOTS halt)
[ ] exp_005 (MAPPO with failure) result saved (Phase 4/5 experiments, not yet run)
```

### Phase 6 — Validator
```
[✓] Reproducibility: same seed → |score1 - score2| <= 0.5 (two instances)
[✓] Crashed policy → POLICY_CRASH, score 0.0, validators do not crash
[✓] TIMEOUT / RESOURCE_EXCEEDED / INVALID_ACTIONS → score 0.0
[✓] Policy hash verified before execution (sha256 of weights)
[✓] EvaluationArtifact: canonical SHA-256 + tamper detection
[✓] POST /api/v1/evaluations stores record + artifact
[✓] tests/integration/test_validator_runner.py: 100% pass
[✓] Policy containerization (Docker) — validator/sandbox/docker_executor.py: --network none, --read-only, cap-drop, cgroup caps, deadline, container-reported hash gate, OOM/timeout/protocol status mapping
[✓] tests/unit/test_docker_policy_executor.py: 19 pass, 1 opt-in skip (real container needs KONNEX_POLICY_IMAGE)
```

### Phase 7 — PoPW
```
[✓] PoPWScore produces valid scores for all 4 policies
[✓] Score components sum correctly with weights (incl. artifact re-derivation test)
[✓] Evaluation artifact hash is verifiable
[✓] tests/unit/test_scoring_engine.py: 100% pass
[✓] tests/unit/test_evaluation_artifact.py: 100% pass
```

### Phase 8 — Konnex Adapter
```
[✓] Konnex SDK documentation reviewed — https://docs.konnex.world/ (docs.konnex.network does NOT exist; see docs/konnex.md)
[✓] SDK existence confirmed — Python client in konnex-world/konnex monorepo; NO PyPI/npm release (version N/A, source install)
[✓] KonnexAdapter stub kept with documented reason (SDK not integrated; NotImplementedError + # TODO: verify Konnex SDK)
[✓] Robotics core has zero imports from protocol/konnex/ (grep test in tests/integration/test_konnex_adapter.py)
[✓] Adapter integration test written — tests/integration/test_konnex_adapter.py (loads, NotImplemented, validation, logging, boundary, zero-import)
[✓] KonnexProvider Protocol interface — protocol/konnex/provider.py (submit_mission, submit_evaluation, publish_proof, query_rewards, get_submission_status); protocol-safe boundary only (AGENTS.md §6.8)
[✓] MockKonnexProvider — protocol/konnex/mock_provider.py (in-memory PoPW lifecycle, simulated KNX rewards with high-score bonus + cap)
[✓] RealKonnexProvider stub — protocol/konnex/real_provider.py (all methods NotImplementedError; SDK blockers documented in docs/konnex.md)
[✓] Provider factory — protocol/konnex/factory.py + KONNEX_PROVIDER env (disabled/mock/real) wired into backend/config.py
[✓] make konnex-demo target + scripts/konnex_demo.py — full mock PoPW lifecycle demo runs end-to-end (mission → evaluation → proof → rewards)
[✓] Provider lifecycle tests — tests/unit/test_konnex_provider.py (18 tests: factory modes, lifecycle, reward math, submission status, protocol conformance, demo smoke test)
```

### Phase 9 — Dashboard
```
[✓] Dashboard shows live robot positions during active mission (WS /ws/fleet, 10 Hz)
[✓] Dashboard shows task completion progress (mission panel + metrics)
[✓] Dashboard streams the PoPW score LIVE — broadcaster computes the provisional score from live mission state via the same PoPWScoringEngine the validator uses (converges to the final score at mission end)
[✓] Dashboard shows the real policy name in the header (from MISSION_UPDATE.policy, e.g. nearest/hungarian/cost_optimizer)
[✓] Energy consumption chart (Recharts, 1 sample/s, "No data yet" when empty)
[✓] Dashboard shows "Simulator offline" when backend/Gazebo not running (OfflineIndicator)
[✓] No hard-coded or mock data in production dashboard (verified in browser: live positions only)
[✓] Frontend lint + type-check passing (npm run lint / type-check / test:unit all green)
```

### Phase 10 — Final Demo
```
[✓] make demo runs full demo without manual steps (scripts/demo.sh: backend + dashboard + predefined 5/20/42 mission)
[✓] make benchmark runs all experiments and produces report (exp_001–003 and exp_006 COMPLETE; exp_004–005 SKIPPED honestly, MAPPO evaluated separately)
[✓] All benchmark results are from actual runs (execution logs in experiments/results/exp_00X/execution.jsonl, real orchestrator + PoPWScoringEngine)
[✓] KONNEX_APPLICATION.md written with real (not projected) metrics
[ ] README contains demo video link (record via make demo)
[✓] tests/e2e/ passes: pytest tests/e2e/ -m e2e (5/5 scenarios against the real backend)
[✓] make test passes completely (unit + integration)
[✓] Repository clean: no debug code, no fabricated data (see git status before commit)
```

## Test Pyramid Target (TESTING_PLAN.md §2)

- Unit: 80+ tests (every commit)
- Integration: 15–25 tests (every PR)
- Simulation: 5–10 tests (nightly/on-demand)
- E2E: 3–5 scenarios (phase gates / grant submission)

## Benchmark Validation (TESTING_PLAN.md §7)

`validate_benchmark_result` is a **specification, not implemented**. The runner
today enforces: one execution-log row per seed (archived, never overwritten),
statistics computed only from executed rows, `UNSTABLE` when std > 15% of mean,
and a recorded `git_commit` (`UNKNOWN` in non-git checkouts). Bounds checks,
artifact-hash verification and scenario-version matching remain TODO — do not
claim results were validated by that function.
