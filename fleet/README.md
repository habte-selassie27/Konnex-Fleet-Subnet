# fleet/

Central coordinator for the robot fleet (Phase 2).

| Path | Contents (planned) |
|---|---|
| `orchestrator.py` | `FleetOrchestrator` — assigns tasks, monitors, recovers failures; never controls actuators or implements ML |
| `mission_manager.py` | Mission lifecycle (PENDING → RUNNING → COMPLETE/FAILED/TIMED_OUT) |
| `task_allocator/base.py` | `TaskAllocator` Protocol (`name` + `assign`) |
| `task_allocator/nearest.py` | Greedy nearest-task (O(R×T)) |
| `task_allocator/hungarian.py` | scipy `linear_sum_assignment` (O(R³)) |
| `task_allocator/cost_optimizer.py` | Weighted multi-factor cost (distance, battery, priority, congestion, collision risk) |
| `collision/monitor.py` · `avoidance.py` | Cross-robot collision detection + avoidance |
| `failure/detector.py` | Low battery (15%), stuck (30 s), comm loss (10 s) |
| `communication/model.py` | Latency + packet-loss simulation (Phase 5) |

**Status: STUB — placeholders pending Phase 2.**
