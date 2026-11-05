# MVP — Scope Definition

> **Phase 0 deliverable** (BUILD.md §3). Status: COMPLETE.
> Source of truth: PLAN.md §4 and §13.

The Spark-grant milestone ($25K) is a **working prototype**: five simulated robots completing warehouse delivery missions under competing policies, with reproducible validator-scored outcomes.

## 1. In Scope — Must Have (Spark demo)

- [ ] Warehouse simulation in Gazebo with 5 autonomous mobile robots
- [ ] Package pickup/delivery mission structure with randomized scenarios
- [ ] Three classical baseline policies: nearest-task, Hungarian, cost-optimizer
- [ ] Fleet orchestrator: task allocation, collision avoidance, failure detection
- [ ] Automated benchmark runner comparing all policies
- [ ] Validator service: reproducible policy execution + scoring
- [ ] PoPW-inspired score engine (clearly labeled as prototype)
- [ ] Fleet monitoring dashboard (React + Vite)
- [ ] `make demo` and `make benchmark` single-command entrypoints
- [ ] Docker Compose deployment
- [ ] CI with lint + unit + integration tests

## 2. Out of Scope (MVP)

- Real robot hardware (physical adapter is a STUB until Phase 8+)
- Actual Konnex token issuance (adapter only)
- More than 5 robots in the MVP benchmark
- Custom simulator (Gazebo is sufficient)

## 3. Mission Design (PLAN.md §5)

```yaml
mission:
  id: uuid
  scenario_id: string
  seed: integer
  environment:
    world: warehouse_v1        # 40m x 30m, 15 shelf obstacles
  robots: { count: 5, initial_positions: randomized, battery_levels: [60%–100%] }
  tasks:
    count: 20–30
    pickup_locations: randomized
    delivery_locations: randomized
    priorities: [LOW, MEDIUM, HIGH]
  constraints: { time_limit: 600s, max_collisions: 0 (target), energy_budget: per-robot }
  failure_injection: { robot_failures: 0–1, communication_loss: optional }
```

**Hard rule:** every scenario is generated deterministically from a seed. Hard-coded scenarios are prohibited (PLAN.md §5.2).

## 4. PoPW Score (prototype, PLAN.md §8)

| Component | Weight | Formula |
|---|---|---|
| Mission Success Rate | 40% | tasks completed / tasks assigned |
| Safety Score | 20% | 1.0 − (collisions / max_possible) |
| Efficiency Score | 15% | 1.0 − (time_taken / time_limit) |
| Energy Score | 10% | 1.0 − (energy_used / energy_budget) |
| Coordination Score | 10% | inter-robot cooperation metric |
| Robustness Score | 5% | performance under failure conditions |

Range 0.0–100.0. **This is a prototype, not Konnex's official algorithm** — adapt to the real SDK after Phase 8 research.

## 5. Success Criteria for Spark Submission (PLAN.md §13)

- [ ] `make demo` runs end-to-end in under 3 minutes
- [ ] `make benchmark` produces a comparison table with real numbers
- [ ] At least 3 policies with statistically meaningful differences
- [ ] Validator reproduces any result from (policy_hash + seed)
- [ ] Dashboard shows live robot state during demo
- [ ] All results in `experiments/results/` are from actual runs
- [ ] README contains a demo video link
- [ ] `KONNEX_APPLICATION.md` is complete and accurate
