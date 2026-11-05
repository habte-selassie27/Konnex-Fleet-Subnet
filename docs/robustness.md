# Robustness — Failure Modes & Recovery Strategy

> **Phase 5 deliverable.** Status: COMPLETE for the headless simulation
> (`SimulationRobotAdapter`). Gazebo failure-injection wiring remains STUB
> until Phase 1 simulation integration. No fabricated failure data — every
> number below comes from the deterministic in-process simulation.

## Goal

The fleet survives partial failures without mission failure:
- 1 robot failing mid-execution ⇒ mission still completes, success_rate > 0.5
- Tasks of a failed robot are reassigned to the remaining robots
- All robots failing ⇒ the mission halts gracefully with reason `NO_ROBOTS`
- Collision rate stays acceptable during failure recovery
- Fleet recovery time (failure → task reassigned) is measured and reported

## Failure Taxonomy

| FailureType | Severity | Detection trigger | Orchestrator action |
|---|---|---|---|
| `SHUTDOWN` | critical | injected (or adapter reports) | robot stops; tasks recovered |
| `COMMUNICATION_LOSS` | warning | comm state ≠ online for ≥ 10 s | robot stops accepting commands; fleet continues |
| `BATTERY_WARNING` | warning | battery < 20% | logged; robot keeps working |
| `BATTERY_CRITICAL` | critical | battery < 10% | robot navigates to charging station |
| `STUCK` | warning | MOVING without progress for ≥ 30 s | robot stops; tasks recovered |
| `NAVIGATION_FAILURE` | critical | explicit FAILED nav state | orchestrator reroutes its tasks |

## Thresholds (`fleet/failure/detector.py`)

| Metric | Threshold |
|---|---|
| Battery warning | < 20% |
| Battery critical | < 10% |
| Stuck | 30 s without position change while MOVING |
| Comm loss | 10 s sustained outage window |
| Navigation failure | immediate (explicit `nav_state == FAILED`) |

Events are deduplicated until the underlying condition recovers, so the
orchestrator reacts to each failure exactly once.

## Health Monitoring & Recovery Flow

The orchestrator polls robot health at **5 Hz**
(`OrchestratorConfig.health_poll_interval_s = 0.2`).

```
robot tick ──► health poll (5 Hz)
                 │
                 ▼
          FailureDetector.check(state, history)
                 │  FailureEvent
                 ▼
          _handle_failure_event
            ├─ BATTERY_CRITICAL → robot.go_charge()
            └─ other failures   → robot.stop()
                 │
                 ▼
          MissionManager.recover_tasks_from_robot(robot_id)
            └─ unassign + mark PENDING
                 │
                 ▼
          _assign_pending → current policy reassigns recovered tasks
                 │
                 └─ recovery time = t(reassigned) − t(failure)
```

Recovery time is recorded in `MissionOutcome.recovery_time_s` (None when no
recovery occurred).

## Halting Semantics

- `_operational_count()` counts robots that are online and not
  FAILED/CHARGING.
- When the operational count reaches 0 while tasks remain, the mission is
  halted with reason `NO_ROBOTS` (status `FAILED`).

## Failure Injection

- **API (Phase 5 gate):** `POST /api/v1/robots/{id}/fail`
  with body `{"failure_type": "...", "duration_s": null}` (see below).
- **Headless simulation:** `SimulationRobotAdapter.inject_failure` supports
  `SHUTDOWN`, `COMMUNICATION_LOSS`, `NAVIGATION_FAILURE` with optional
  duration; `BATTERY_CRITICAL` is driven by the battery model + detector.
- **Gazebo (STUB):** shutdown, comm loss, sensor degradation and nav-freeze
  plugins are specified in `simulation/` but wired in Phase 1.

## Communication Degradation Model

`fleet/communication/model.py` simulates a lossy command channel:

- `CommConfig(base_latency_ms, jitter_ms, packet_loss_rate)`
- `transmit()` returns latency in ms when delivered, `None` when dropped
- `CommStats` tracks sent/delivered/lost + mean latency + delivery rate

## API Reference — Failure Injection

```
POST /api/v1/robots/{robot_id}/fail
X-Fleet-API-Key: <key>

{ "failure_type": "communication_loss", "duration_s": null }

200 { "robot_id": "robot_0", "failure_type": "communication_loss", "injected": true }
401 missing/invalid API key
404 unknown robot
422 unknown failure_type
```

Valid `failure_type` values: `shutdown`, `communication_loss`,
`battery_warning`, `battery_critical`, `stuck`, `navigation_failure`.

## Tests (Phase 5 gates)

- `tests/unit/test_failure_detector.py` — thresholds + dedup + recovery
- `tests/unit/test_communication_model.py` — latency bounds + packet loss
- `tests/unit/test_collision_monitor.py` — edge-triggered contact events (one
  event per contact episode, escalation from near miss to contact, reset)
- `tests/integration/test_fleet_orchestration.py`
  - `test_orchestrator_handles_all_robots_low_battery` — NO_ROBOTS halt
  - `test_mission_completes_with_partial_failure` — success_rate > 0.5
  - `test_tasks_reassigned_to_remaining_robots` — recovery measured
  - `test_collision_rate_acceptable_during_recovery`
  - `test_fleet_halts_when_all_robots_fail`
  - `test_battery_critical_sends_robot_to_charger`
- `tests/integration/test_robots_api.py` — failure-injection endpoint
