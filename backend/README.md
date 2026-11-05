# backend/

FastAPI backend — the central nervous system of the subnet (Phase 2).

| Path | Contents (planned) |
|---|---|
| `main.py` | FastAPI app factory (AGENTS.md §2.3) |
| `routers/` | `missions`, `policies`, `evaluations`, `robots`, `metrics` (+ health) |
| `services/` | `mission_service`, `policy_service`, `evaluation_service` |
| `events/` | In-process async event bus + typed event dataclasses (AGENTS.md §3.4) |
| `db/` | SQLModel engine + models |

**API (AGENTS.md §2.8):** Base URL `http://localhost:8000/api/v1`, auth `X-Fleet-API-Key`, WebSocket `/ws/fleet`. All responses carry a `request_id`.

**Rules (AGENTS.md §2.9):** no sync DB calls in async handlers; config via env only; Pydantic v2 validation; ROS 2 imports only in `backend/ros/` (skeleton defers this directory to Phase 2+ — see AGENTS.md §2.2).

**Status: STUB — placeholders pending Phase 2.**
