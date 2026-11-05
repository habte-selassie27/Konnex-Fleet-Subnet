# TESTING_PLAN.md — Test Strategy & Validation
## Konnex Fleet Intelligence Subnet

> **Rule:** No phase is complete until its test suite passes.  
> **Rule:** No benchmark result is valid unless it was produced by running the actual experiment.  
> **Rule:** No component can be marked DONE with failing tests.

---

## 1. Testing Philosophy

This project operates on a **trust-but-verify** model. Because the subnet's entire value proposition rests on objective, reproducible evaluation of physical-world outcomes, the testing infrastructure is not optional overhead — it is the product.

A Konnex reviewer will ask: "How do I know these benchmark numbers are real?" The answer must be: "Run `make benchmark` and get the same numbers."

---

## 2. Test Pyramid

```
         ┌──────────────────┐
         │  End-to-End (E2E)│  ← 3–5 scenarios, slow, full stack
         ├──────────────────┤
         │   Integration    │  ← 15–25 tests, component pairs
         ├──────────────────┤
         │  Simulation      │  ← 5–10 tests, ROS + Gazebo
         ├──────────────────┤
         │    Unit Tests    │  ← 80+ tests, pure logic, fast
         └──────────────────┘
```

- **Unit tests** run on every commit (fast, <60s total)
- **Integration tests** run on every PR (medium, <5 minutes)
- **Simulation tests** run nightly or on-demand (<20 minutes)
- **E2E tests** run before any phase gate or grant submission (<45 minutes)

---

## 3. Unit Tests

### 3.1 Task allocators (`tests/unit/test_task_allocator.py`)

```python
class TestNearestAllocator:
    def test_single_robot_single_task(self): ...
    # Robot at (0,0), task at (5,0) → assigned

    def test_multiple_robots_choose_nearest(self): ...
    # Robot A at (1,0), Robot B at (10,0), task at (2,0) → Robot A

    def test_more_tasks_than_robots(self): ...
    # 3 robots, 10 tasks → 3 assignments, 7 tasks unassigned

    def test_more_robots_than_tasks(self): ...
    # 5 robots, 2 tasks → 2 assignments, 3 robots idle

    def test_all_robots_have_tasks(self): ...
    # Robots with active tasks are excluded from re-assignment

class TestHungarianAllocator:
    def test_optimal_assignment(self): ...
    # Verifies lower total distance than nearest-greedy on constructed example

    def test_empty_fleet(self): ...
    # 0 robots → returns empty list, no exception

    def test_empty_task_queue(self): ...
    # 5 robots, 0 tasks → returns empty list

    def test_cost_matrix_symmetry(self): ...
    # Cost matrix is never negative

class TestCostOptimizerAllocator:
    def test_prefers_high_battery_robot_all_else_equal(self): ...
    def test_penalizes_congested_path(self): ...
    def test_respects_task_priority(self): ...
    def test_custom_weights_applied(self): ...
    def test_normalized_components(self): ...
    # All cost components must be in [0, 1] before weighting
```

### 3.2 Scenario generator (`tests/unit/test_scenario_generator.py`)

```python
class TestScenarioGenerator:
    def test_seed_determinism(self):
        # Same seed → identical scenario (all fields equal)
        gen = ScenarioGenerator()
        s1 = gen.generate(seed=42, robot_count=5, task_count=20)
        s2 = gen.generate(seed=42, robot_count=5, task_count=20)
        assert s1 == s2

    def test_different_seeds_differ(self):
        gen = ScenarioGenerator()
        s1 = gen.generate(seed=1, robot_count=5, task_count=20)
        s2 = gen.generate(seed=2, robot_count=5, task_count=20)
        assert s1.robot_positions != s2.robot_positions

    def test_positions_within_world_bounds(self):
        # All positions must be within [0, 40] x [0, 30] for warehouse_v1

    def test_no_overlapping_robots(self):
        # Robot initial positions must be >= 1.0m apart

    def test_task_count_matches_request(self):

    def test_failure_injection_optional(self):
```

### 3.3 Battery model

```python
class TestBatteryModel:
    def test_drains_during_movement(self):
    def test_drains_slower_when_idle(self):
    def test_never_goes_below_zero(self):
    def test_low_battery_threshold_fires_event(self):
    def test_battery_affects_cost_function(self):
```

### 3.4 PoPW scoring engine

```python
class TestPoPWScoringEngine:
    def test_perfect_mission_scores_100(self):
        # All tasks complete, 0 collisions, on time, full energy → 100.0

    def test_zero_tasks_complete_scores_low(self):
        # 0/20 tasks → score < 20.0 (weighted by mission_success = 0.40)

    def test_collision_reduces_safety_component(self):

    def test_score_bounded_zero_to_100(self):
        # Fuzz test: random results should never produce score outside [0, 100]

    def test_custom_weights_applied_correctly(self):
        # Hand-compute expected score for simple case

    def test_component_scores_between_0_and_1(self):

    def test_partial_task_completion(self):
        # 15/20 tasks → mission_success = 0.75

    def test_energy_efficiency_penalized(self):
        # 200% energy consumed → energy component = 0.0

    def test_reproducibility_same_input(self):
        # Same MissionResult → same PoPWScore on every call
```

### 3.5 Evaluation artifact

```python
class TestEvaluationArtifact:
    def test_hash_is_deterministic(self):
        artifact = create_test_artifact()
        h1 = artifact.compute_hash()
        h2 = artifact.compute_hash()
        assert h1 == h2

    def test_different_score_different_hash(self):
        a1 = create_test_artifact(final_score=95.0)
        a2 = create_test_artifact(final_score=95.1)
        assert a1.compute_hash() != a2.compute_hash()

    def test_hash_changes_on_any_field_change(self):
        # Parametrized: mutate each field, verify hash changes

    def test_serialization_roundtrip(self):
        artifact = create_test_artifact()
        json_str = artifact.to_json()
        restored = EvaluationArtifact.from_json(json_str)
        assert restored == artifact

    def test_tamper_detection(self):
        artifact = create_test_artifact()
        original_hash = artifact.artifact_hash
        artifact.final_score = 99.9  # tamper
        assert artifact.compute_hash() != original_hash
```

### 3.6 Collision detection

```python
class TestCollisionMonitor:
    def test_detects_robot_robot_collision(self):
        # Two robots at same position → collision event

    def test_no_false_positive_when_far(self):
        # Robots 2m apart → no collision

    def test_detects_robot_obstacle_collision(self):

    def test_near_miss_detection(self):
        # Robots within safety margin but not colliding → near-miss event

    def test_collision_clears_on_separation(self):
```

---

## 4. Integration Tests

### 4.1 Fleet orchestration

```python
class TestFleetOrchestration:
    def test_mission_assigned_to_all_robots(self, mock_fleet: FleetFixture):
        # 5 robots, 10 tasks → all robots receive initial assignments

    def test_task_reassigned_on_robot_failure(self, mock_fleet):
        # Complete 3 tasks → fail robot_2 → robot_2's task reassigned

    def test_mission_completes_with_partial_failure(self, mock_fleet):
        # 1 robot failure mid-mission → mission still reaches completion

    def test_no_task_assigned_twice(self, mock_fleet):
        # Run full mission → no task_id appears in more than one completion event

    def test_orchestrator_handles_all_robots_low_battery(self, mock_fleet):
        # All robots at 5% battery → orchestrator reports BATTERY_CRITICAL, halts

    def test_deadlock_prevention(self, mock_fleet):
        # Scenario where naive allocation causes deadlock → cost optimizer resolves it
```

### 4.2 Mission lifecycle

```python
class TestMissionLifecycle:
    def test_mission_created_with_valid_schema(self):
    def test_mission_transitions_through_states(self):
        # PENDING → RUNNING → COMPLETE (or FAILED)

    def test_mission_generates_tasks_from_scenario(self):

    def test_mission_records_all_events(self):
        # All MissionCreated, TaskAssigned, TaskCompleted events logged

    def test_mission_timeout_triggers_evaluation(self):
        # time_limit reached → mission marked TIMED_OUT, evaluation still runs
```

### 4.3 Validator runner

```python
class TestValidatorRunner:
    def test_same_policy_and_seed_produces_same_score(self):
        """Reproducibility test — this is the most important integration test."""
        request = ValidationRequest(
            policy_id="nearest",
            policy_hash=...,
            scenario_id="warehouse_v1_20tasks",
            seed=42,
            env_version="v1.0.0",
            sim_version="gazebo_harmonic",
            resource_limits=ResourceLimits.default(),
        )
        result1 = await runner.validate(request)
        result2 = await runner.validate(request)
        assert abs(result1.score.final - result2.score.final) <= 0.5

    def test_crashed_policy_returns_zero_score(self):
        # Policy that raises exception → POLICY_CRASH status, score 0.0

    def test_policy_hash_mismatch_rejected(self):
        # Corrupt weights → PolicyError raised

    def test_timeout_policy_returns_timeout_status(self):

    def test_evaluation_artifact_verifiable(self):
        result = await runner.validate(valid_request)
        assert result.evaluation_artifact.compute_hash() == result.evaluation_artifact.artifact_hash

    def test_two_validators_agree_within_tolerance(self):
        """Run same validation on two validator instances, compare scores."""
        r1 = await validator_1.validate(request)
        r2 = await validator_2.validate(request)
        assert abs(r1.score.final - r2.score.final) <= 0.5
```

### 4.4 Backend API

```python
class TestMissionsAPI:
    def test_create_mission_returns_201(self, client):
    def test_get_mission_returns_404_if_not_found(self, client):
    def test_create_mission_validates_schema(self, client):
        # Missing required fields → 422 Unprocessable Entity
    def test_unauthenticated_request_returns_401(self, client):
    def test_mission_status_updates_reflect_in_api(self, client):

class TestPoliciesAPI:
    def test_submit_policy_returns_policy_id(self, client):
    def test_policy_hash_verified_on_submission(self, client):
    def test_list_policies_returns_all_submitted(self, client):

class TestEvaluationsAPI:
    def test_start_evaluation_returns_evaluation_id(self, client):
    def test_evaluation_result_contains_score(self, client):
    def test_evaluation_artifact_downloadable(self, client):
```

---

## 5. Simulation Tests

> These tests require a running Gazebo instance. Run with: `pytest tests/simulation/ -m simulation`

```python
# tests/simulation/test_robot_navigation.py

@pytest.mark.simulation
class TestRobotNavigation:
    def test_single_robot_reaches_goal(self, gazebo_env):
        """Robot spawned at (0, 0). Goal at (5, 5). Reaches within 0.3m in 30s."""

    def test_five_robots_navigate_independently(self, gazebo_env):
        """5 robots, independent goals, all reach within 60s, zero collisions."""

    def test_robot_stops_before_obstacle(self, gazebo_env):
        """Robot stops or replans, does NOT pass through obstacle."""

    def test_lidar_returns_nonzero_readings(self, gazebo_env):

    def test_battery_drains_during_movement(self, gazebo_env):
        """Battery at start > battery after 10s of movement."""

    def test_robot_failure_injection(self, gazebo_env):
        """COMM_LOSS injection causes robot to stop accepting commands."""
```

---

## 6. End-to-End Tests

> Run with: `pytest tests/e2e/ -m e2e` (requires full Docker stack: `make demo`)

```python
# tests/e2e/test_full_mission.py

@pytest.mark.e2e
class TestFullMission:
    def test_warehouse_mission_completes(self, full_stack):
        """
        E2E: POST /missions with 5 robots, 20 tasks, seed=42, nearest policy.
        Expected: mission COMPLETE within 120s.
        Expected: task_completion_rate > 0.7
        Expected: valid evaluation artifact hash.
        """

    def test_benchmark_produces_comparable_results(self, full_stack):
        """
        nearest + hungarian on same scenario (seed=100).
        Expected: hungarian score >= nearest score.
        Expected: both scores in [0, 100].
        """

    def test_validator_reproduces_result(self, full_stack):
        """
        nearest twice (same seed): |score1 - score2| <= 0.5,
        artifact hashes identical.
        """

    def test_robot_failure_handled_gracefully(self, full_stack):
        """
        Inject robot_2 failure via API after 20s.
        Mission continues, tasks reassigned, task_completion_rate > 0.5.
        """

    def test_dashboard_shows_live_state(self, full_stack):
        """
        GET /robots during mission: 5 entries with distinct positions,
        at least 1 robot with current_task != null.
        """
```

---

## 7. Benchmark Validation Rules

Before any benchmark result is written to `experiments/results/`:

```python
def validate_benchmark_result(result: ExperimentResult) -> None:
    """Raises BenchmarkIntegrityError if any check fails."""
    # 1. Run count
    assert result.n_runs >= 5, "Minimum 5 runs required for statistical reporting"
    # 2. Success rate bounds
    assert 0.0 <= result.mean_success_rate <= 1.0
    # 3. Standard deviation reported
    assert result.std_success_rate is not None, "Must report std dev"
    # 4. Collision count is non-negative
    assert result.mean_collisions >= 0
    # 5. Completion time is positive
    assert result.mean_completion_time_s > 0
    # 6. Scenario version matches
    assert result.scenario_version == CURRENT_SCENARIO_VERSION
    # 7. Git commit recorded
    assert result.git_commit is not None and len(result.git_commit) == 40
    # 8. Artifact hashes verified
    for artifact in result.evaluation_artifacts:
        assert artifact.compute_hash() == artifact.artifact_hash, \
            f"Artifact {artifact.policy_id} hash mismatch — possible data corruption"
    # 9. Policy ran (not mock)
    assert result.policy_execution_log is not None, \
        "No execution log — result may be fabricated"
```

---

## 8. Linting & Type Checking

All of these must pass before any commit is accepted by CI:

```bash
# Python
ruff check .                          # Zero errors
ruff format --check .                 # Zero formatting issues
mypy . --ignore-missing-imports       # Zero type errors
bandit -r . -ll                       # No high-severity security issues

# TypeScript
cd frontend && npm run lint           # ESLint zero errors
cd frontend && npm run type-check     # tsc --noEmit zero errors

# Docker
docker-compose config                 # Valid Compose config
```

### ruff configuration

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py310"
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "DTZ", "T20", "ARG", "PTH", "ERA"]
ignore = ["ERA001"]  # Allow commented-out code during development (remove before Phase gate)

[tool.mypy]
strict = true
ignore_missing_imports = true
```

---

## 9. CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.10" }
      - run: pip install ruff mypy bandit
      - run: ruff check .
      - run: mypy . --ignore-missing-imports
      - run: bandit -r . -ll
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm ci && npm run lint && npm run type-check

  unit-tests:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.10" }
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/unit/ -v --cov=. --cov-report=xml --tb=short
      - uses: codecov/codecov-action@v4

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: fleet_test
          POSTGRES_USER: fleet
          POSTGRES_PASSWORD: fleet
        options: --health-cmd pg_isready
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.10" }
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/integration/ -v --tb=short
        env:
          DATABASE_URL: postgresql://fleet:fleet@localhost/fleet_test

  build:
    runs-on: ubuntu-latest
    needs: integration-tests
    steps:
      - uses: actions/checkout@v4
      - run: docker-compose build
      - run: docker-compose config
```

---

## 10. Phase Gate Checklist

Use this checklist before declaring any phase complete and moving to the next.

### Phase 0 — Architecture

```
[ ] docs/architecture.md exists and describes all components
[ ] docs/mvp.md defines what MVP includes and excludes
[ ] Repository structure matches BUILD.md Section 1
[ ] All dependency versions pinned in requirements.txt
[ ] make lint passes (no code yet = zero errors)
```

### Phase 1 — Simulation

```
[✓] simulation/ is a buildable ROS 2 ament package (package.xml + CMakeLists.txt)
[✓] simulation/Dockerfile.gazebo — Humble + Gazebo Harmonic + ros_gz_bridge (make sim)
[✓] Warehouse world launch (ros_gz_sim, Harmonic) + multi-robot spawn launch (xacro URDF, deterministic seeded poses)
[✓] gz↔ROS bridge (odom/scan/imu/cmd_vel/tf per robot) — generated at launch + reference robot_bridge.yaml
[✓] fleet_agent go-to-goal node per robot (LiDAR obstacle stop + rotate recovery + modeled battery)
[✓] GazeboRobotAdapter (RobotAdapter protocol, transport-injected) + backend/ros ROSBridge (SIM_MODE=gazebo)
[✓] tests/simulation/ passes: pytest tests/simulation/ -m simulation (19 headless PASSED + 6 Gazebo-gated SKIPPED)
[✓] Asset/adapter/bridge unit tests pass without Gazebo (35 tests)
[ ] Gazebo launches without errors: make sim — NOT RUN on this machine (ROS 2/Gazebo containerized)
[ ] 5 robot models visible in Gazebo — NOT RUN
[ ] All 5 robots complete independent navigation to test goals — NOT RUN
[ ] LiDAR scans returning data (verify via ROS 2 topic echo) — NOT RUN
[ ] Battery model draining correctly during movement (Gazebo) — NOT RUN
```

### Phase 2 — Fleet Coordination

```
[ ] All 3 baseline allocators implemented
[ ] tests/unit/test_task_allocator.py: 100% pass
[ ] tests/integration/test_fleet_orchestration.py: 100% pass
[ ] 5 robots complete a 20-task mission (run manually, observe in Gazebo)
[ ] Robot failure triggers task reassignment (verify in logs)
[ ] make lint passes
```

### Phase 3 — Benchmarking

```
[ ] Scenario generator produces deterministic scenarios
[ ] tests/unit/test_scenario_generator.py: 100% pass
[ ] exp_001 (nearest), exp_002 (hungarian), exp_003 (cost_optimizer) all run to completion
[ ] Results saved in experiments/results/ with valid artifact hashes
[ ] make benchmark produces comparison table
[ ] Results provide execution logs for all 3 experiments
```

### Phase 4 — MARL

```
[ ] FleetEnv passes Gymnasium check_env() without warnings
[ ] Random policy runs 1000 steps without crash
[ ] MAPPO trains for at least 500K timesteps without error
[ ] Trained policy produces non-zero task completion in evaluation
[ ] exp_004 result saved (even if WORSE than baselines — report honestly)
[ ] MLflow experiment tracked
```

### Phase 5 — Robustness

```
[ ] Robot failure injection works via API
[ ] tests/integration/ test_robot_failure_handled_gracefully passes
[ ] exp_005 (MAPPO with failure) result saved
[ ] Communication degradation model working
[ ] Fleet recovery time measured and reported
```

### Phase 6 — Validator

```
[ ] Reproducibility test passes: same seed → |score1 - score2| <= 0.5
[ ] Crashed policy → POLICY_CRASH status, validators do not crash
[ ] Hash tamper detection working
[ ] tests/integration/test_validator_runner.py: 100% pass
[ ] Policy containerization working with resource limits
```

### Phase 7 — PoPW

```
[ ] PoPWScore produces valid scores for all 4 policies
[ ] Score components sum correctly with weights
[ ] Evaluation artifact hash is verifiable
[ ] tests/unit/test_scoring_engine.py: 100% pass
[ ] tests/unit/test_evaluation_artifact.py: 100% pass
```

### Phase 8 — Konnex Adapter

```
[ ] Konnex SDK documentation reviewed (link: <add URL>)
[ ] SDK version confirmed
[ ] KonnexAdapter stub replaced with real implementation (or documented stub with reason)
[ ] Robotics core has zero imports from protocol/konnex/
[ ] Adapter integration test written (even if mocked)
```

### Phase 9 — Dashboard

```
[✓] Dashboard shows live robot positions during active mission
[✓] Dashboard shows task completion progress
[✓] Dashboard streams the PoPW score live — the broadcaster computes the provisional score from live mission state using the same PoPWScoringEngine as the validator (converges to the final score at mission end)
[✓] Dashboard shows "Simulator offline" when Gazebo not running
[✓] No hard-coded or mock data in production dashboard
[✓] Frontend lint + type-check passing
```

### Phase 10 — Final Demo

```
[✓] make demo runs full demo without manual steps (scripts/demo.sh: backend + dashboard + predefined 5/20/42 mission)
[✓] make benchmark runs all experiments and produces report (exp_001–003 real runs; exp_004–006 SKIPPED honestly)
[✓] All benchmark results are from actual runs (execution logs verified in experiments/results/)
[✓] KONNEX_APPLICATION.md written with real (not projected) metrics
[ ] README contains demo video link (record via make demo)
[✓] tests/e2e/ passes: pytest tests/e2e/ -m e2e (5/5 scenarios against the real backend)
[✓] make test passes completely (unit + integration)
[✓] Repository is clean (no debug code, no fabricated data)
```

---

## 11. Test Fixture Conventions

```python
# tests/conftest.py

@pytest.fixture
def mock_robot_state() -> RobotState:
    return RobotState(
        id="robot_0",
        position=Vector2D(x=0.0, y=0.0),
        orientation=0.0,
        velocity=Vector2D(x=0.0, y=0.0),
        battery_pct=1.0,
        nav_state=NavState.IDLE,
    )

@pytest.fixture
def mock_fleet(mock_robot_state) -> list[RobotState]:
    return [
        replace(mock_robot_state, id=f"robot_{i}", position=Vector2D(i * 2.0, 0.0))
        for i in range(5)
    ]

@pytest.fixture
def simple_mission() -> Mission:
    return ScenarioGenerator().generate(seed=42, robot_count=5, task_count=10)

@pytest.fixture
def scoring_engine() -> PoPWScoringEngine:
    return PoPWScoringEngine()
```

---

## 12. What Disqualifies a Test

A test is invalid and must NOT be committed if:

```python
# INVALID — asserts on fabricated data
def test_mappo_beats_baseline():
    score = 95.0  # just made this up
    assert score > 88.7

# INVALID — always passes regardless of implementation
def test_allocator_assigns_tasks():
    assert True

# INVALID — depends on external network in unit test
def test_konnex_submission():
    adapter = KonnexAdapter(live_endpoint="https://mainnet.konnex...")
    result = adapter.submit_mission(...)  # real network call in unit test
    assert result is not None

# INVALID — asserts on implementation detail, not behavior
def test_hungarian_uses_scipy():
    import scipy
    assert "scipy" in sys.modules
```

---

*This testing plan is a binding contract. Agents must not skip tests, must not fabricate results, and must update this file if test requirements change.*
---

## 13. Phase 7 — PoPW Prototype

**Goal:** Every mission produces a verifiable evaluation artifact with PoPW-inspired score.

### Unit Tests — Scoring Engine (`tests/unit/test_scoring_engine.py`)

- [ ] test_perfect_mission_scores_100
- [ ] test_zero_tasks_complete_scores_low
- [ ] test_collision_reduces_safety_component
- [ ] test_score_bounded_zero_to_100 (fuzz)
- [ ] test_custom_weights_applied
- [ ] test_component_scores_between_0_and_1
- [ ] test_partial_task_completion
- [ ] test_energy_efficiency_penalized
- [ ] test_reproducibility_same_input

### Unit Tests — Artifact (`tests/unit/test_evaluation_artifact.py`)

- [ ] test_hash_is_deterministic
- [ ] test_different_score_different_hash
- [ ] test_hash_changes_on_any_field_change
- [ ] test_serialization_roundtrip
- [ ] test_tamper_detection
- [ ] test_verify_passes_for_valid_artifact
- [ ] test_verify_fails_for_tampered_artifact

### Acceptance

- [ ] PoPWScore valid for all 4 policies (nearest, hungarian, cost, mappo)
- [ ] Weights sum to 1.0, components in [0, 1]
- [ ] Artifact hash verifiable by re-computation
- [ ] All scoring + artifact tests pass
- [ ] `docs/powp.md` written
- [ ] `make lint` passes

---

## 14. Phase 8 — Konnex Adapter

**Goal:** Adapter cleanly integrated; robotics core has zero blockchain imports.

### Implementation

- [ ] Fetch Konnex developer docs / Gitbook
- [ ] Verify SDK package name + version on npm/pip
- [ ] Confirm available API endpoints
- [ ] Document verified endpoints in `docs/konnex.md`
- [ ] Implement `KonnexAdapter` class with methods:
  - [ ] `submit_policy(policy_id, policy_hash, metadata) → str`
  - [ ] `submit_evaluation(policy_id, eval_id, score, artifact_hash) → str`
  - [ ] `publish_proof(artifact) → str`
  - [ ] `query_rewards(policy_id) → float`
  - [ ] `get_submission_status(submission_id) → dict`
- [ ] Each method returns UNVERIFIED stub until docs confirmed
- [ ] Adapter lives in `protocol/konnex/adapter.py`
- [ ] Zero imports from `robotics/`, `simulation/`, `ml/` into `protocol/konnex/`
- [ ] Adapter accepts only: policy_id, policy_hash, EvaluationArtifact, MissionMetadata
- [ ] Adapter never receives: RobotState, Gazebo handles, ROS2 nodes, trajectories
- [ ] Implement `KonnexAdapterError` exception class
- [ ] Adapter logs every call with structlog

### Integration Tests (`tests/integration/test_konnex_adapter.py`)

- [ ] test_adapter_loads
- [ ] test_adapter_methods_raise_not_implemented (until verified)
- [ ] test_adapter_rejects_empty_policy_id
- [ ] test_adapter_logs_calls
- [ ] test_robotics_core_zero_konnex_imports (grep test)
- [ ] test_adapter_boundary_enforced (only safe types cross)

### Acceptance

- [ ] Konnex docs reviewed, link recorded
- [ ] SDK version confirmed
- [ ] `protocol/konnex/adapter.py` implemented (stub or verified)
- [ ] `robotics/` has zero imports from `protocol/konnex/`
- [ ] Adapter integration test written
- [ ] `docs/konnex.md` written
- [ ] `make lint` passes
- [ ] `make test` passes

---

## 15. Phase 9 — Dashboard

**Goal:** Third party understands the system from the UI without reading source code.

### Frontend Scaffold

- [✓] React 18 + TypeScript 5 + Vite 5 + TailwindCSS 3
- [✓] `frontend/tsconfig.json` — strict: true, zero any
- [✓] `frontend/vite.config.ts` — proxy /api + /ws to 127.0.0.1:8000
- [✓] `frontend/tailwind.config.ts` — dark mode, custom palette

### Core Components

- [✓] `src/services/api.ts` — typed fetch client, no raw fetch in components
- [✓] `src/hooks/useFleetSocket.ts` — WebSocket, reconnection, event dispatch
- [✓] `src/store/fleetStore.ts` — Zustand: live robot states, online/offline
- [✓] `src/components/fleet/WarehouseMap.tsx` — Three.js 3D warehouse
- [✓] `src/components/fleet/RobotCard.tsx` — sidebar per-robot status
- [✓] `src/components/fleet/FleetSummary.tsx` — aggregate fleet stats
- [✓] `src/components/metrics/MetricsDashboard.tsx` — score gauge + stats
- [✓] `src/components/metrics/ScoreGauge.tsx` — PoPW score animation
- [✓] `src/components/mission/MissionPanel.tsx` — active mission + progress
- [✓] `src/components/validator/EvaluationCard.tsx` — eval result display
- [✓] `src/components/benchmark/BenchmarkTable.tsx` — policy comparison (honest empty state)
- [✓] `src/components/shared/OfflineIndicator.tsx` — "Simulator offline"

### Live Data Rules

- [✓] WebSocket events: ROBOT_STATE_UPDATE, MISSION_UPDATE, TASK_COMPLETED, COLLISION_DETECTED, SIMULATOR_OFFLINE
- [✓] Robot positions update ≤ 100ms via WS (10 Hz broadcaster)
- [✓] All charts show real data — "No data yet" if empty, never zeros
- [✓] Score gauge animates only when score actually changes
- [✓] No mock/static data anywhere in production

### Accessibility

- [✓] All interactive elements have aria-label
- [✓] Color never sole indicator of state (always icon + text — StatusBadge)
- [✓] Keyboard navigation works (focus-visible rings, natural tab order)

### Quality

- [✓] ErrorBoundary wraps every major panel
- [✓] `npm run lint` — zero errors
- [✓] `npm run type-check` — zero errors
- [✓] `npm run test:unit` — passes (7 tests: ScoreGauge, OfflineIndicator, fleetStore)
- [✓] `docs/dashboard.md` written
- [✓] Backend WS contract tested: tests/integration/test_websocket_fleet.py (4 tests)
- [✓] Browser-verified: LIVE badge, 3D map with moving robots, live metrics (no mock data)

---

## 16. Phase 10 — Final Demo

**Goal:** `make demo` + `make benchmark` produce a complete, honest, reproducible result set.

### Demo (`make demo`)

- [✓] `make demo` launches the stack: backend (headless sim) + frontend + predefined mission (validator runs via `make benchmark`; Gazebo/Docker STUB)
- [✓] Predefined mission runs: 5 robots, 20 tasks, seed=42
- [✓] At least 1 policy (nearest) completes successfully
- [✓] Dashboard shows live robot positions during active mission
- [✓] Dashboard shows task completion progress
- [✓] Dashboard shows PoPW score live during the mission (converges to final at mission end)
- [ ] Demo completes in under 3 minutes (mean 204 s ≈ 3.4 min for nearest/20 tasks — see exp_001)
- [✓] `make demo` requires zero manual steps

### Benchmark (`make benchmark`)

- [✓] `make benchmark` runs exp_001 (nearest), exp_002 (hungarian), exp_003 (cost_optimizer)
- [✓] Results saved in `experiments/results/exp_XXX/result.json` (execution logs in execution.jsonl)
- [✓] Comparison table printed to stdout
- [✓] All results are from actual runs (execution logs present)
- [✓] No fabricated numbers anywhere (real orchestrator + PoPWScoringEngine; collisions/energy simulated, never randint)
- [✓] Each result includes: git_commit (UNKNOWN — repo not under git), scenario_id, seed_range, status, mean±std

### KONNEX_APPLICATION.md

- [✓] Project name + one-line pitch
- [✓] Problem statement
- [✓] Solution description
- [✓] Why Konnex mapping
- [✓] Current prototype (what actually works)
- [✓] Benchmark table (real numbers only)
- [✓] Architecture section (references docs/architecture.md)
- [ ] Team section (honest) — fill with real names
- [✓] Roadmap (prototype → testnet → physical pilot → mainnet)
- [✓] Grant request

### README.md

- [✓] Problem + solution + architecture
- [✓] Quickstart (make setup → make demo)
- [ ] Demo video link (record via make demo)
- [✓] Benchmark methodology
- [✓] Konnex integration status
- [✓] Roadmap

### Final Checks

- [✓] `make test` — zero failures (unit + integration)
- [✓] `make lint` — zero errors (ruff + mypy + eslint + typecheck)
- [✓] `tests/e2e/` passes: `pytest tests/e2e/ -m e2e` (5/5)
- [ ] `tests/simulation/` Gazebo-gated tests execute live (needs Gazebo — SKIPPED on this machine; 19 headless sim tests + 35 Phase 1 unit tests pass everywhere)
- [✓] Repository clean: no debug code, no fabricated data
- [✓] All docs/ files updated
- [ ] No uncommitted changes (clean git status) — repo is not under git on this machine
- [ ] `make demo` video recorded and linked in README
