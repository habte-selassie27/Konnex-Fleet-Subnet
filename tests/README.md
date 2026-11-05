# tests/

Test pyramid (TESTING_PLAN.md §2): unit (80+) → simulation (5–10) → integration (15–25) → e2e (3–5).

| Suite | Path | Run with |
|---|---|---|
| Unit | `tests/unit/` | `make test-unit` (every commit) |
| Integration | `tests/integration/` | `make test-integration` (every PR) |
| Simulation | `tests/simulation/` | `pytest tests/simulation/ -m simulation` (needs Gazebo) |
| E2E | `tests/e2e/` | `pytest tests/e2e/ -m e2e` (needs `make demo`) |

**Status: STUB — test files are placeholders; tests are added per phase.**
A test that asserts on fabricated data or always passes is INVALID (TESTING_PLAN.md §12).

**Note (Phase 0):** with zero tests present, `make test` (pytest) exits with code 5
and `make test-frontend` (vitest) exits with code 1 ("no test files found").
This is expected until Phase 1+ adds tests — the Phase 0 gate is `make lint` only.
