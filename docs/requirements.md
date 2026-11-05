# Requirements — Pinned Dependencies & Environment

> **Phase 0 deliverable** (BUILD.md §3). Status: COMPLETE.
> Every version below was **researched against PyPI / npm registry on 2026-08-08** before pinning (per AGENTS.md §0.2 and SYSTEM_PROMPT.md §6.1). No versions from memory.
> All Python pins are **resolved as a set** (`pip install --dry-run -r requirements-dev.txt` passes) and are the **maximum version installable on Python 3.10** (the project minimum, and the CI Python). Where the latest release required Python ≥3.11/3.12, we pinned the newest 3.10-compatible release and noted it.

---

## 1. Environment Requirements

| Tool | Required | Verified minimum (SYSTEM_PROMPT.md §2.1) |
|---|---|---|
| Python | 3.10+ | 3.10+ |
| ROS 2 | Humble (LTS to 2027) | containerized via `simulation/Dockerfile.gazebo` (Phase 1) |
| Gazebo | Harmonic (2023+) | containerized via `simulation/Dockerfile.gazebo` (Phase 1) |
| Node.js | 20+ | 20+ |
| Docker | 20+ / Compose v3.9 | 20+ |

Dev machine (2026-08-08): Python 3.11.5 · Node 22.12.0 · npm 11.6.2 · Docker 29.7.2 · ROS 2 **not installed** (containerized) · Gazebo **not installed** (containerized).

**Simulation image (Phase 1):** `osrf/ros:humble-desktop` (Ubuntu 22.04) +
`gazebo-harmonic` (OSRF stable repo) + `ros-humble-ros-gzharmonic`
(ros_gz_bridge / ros_gz_sim) + xacro / rsp / jsp. The `simulation` ament
package is colcon-built inside the image; the exact versions are pinned by
what apt resolves for Jammy at build time (no fabricated pins).

## 2. Python Dependencies (`requirements.txt`)

Researched latest stable (PyPI, 2026-08-08):

| Package | Pinned | Spec minimum | Notes |
|---|---|---|---|
| fastapi | 0.141.1 | 0.110+ | |
| uvicorn[standard] | 0.52.1 | — | ASGI server |
| pydantic | 2.13.4 | 2.6+ | v2 |
| pydantic-settings | 2.15.0 | — | env-driven config |
| sqlmodel | 0.0.39 | — | SQLAlchemy managed transitively |
| alembic | 1.19.0 | — | migrations |
| aiosqlite | 0.22.1 | — | SQLite dev driver |
| python-multipart | 0.0.32 | — | form parsing |
| httpx | 0.28.1 | — | async test client / API |
| structlog | 26.1.0 | 24.1+ | JSON logging |
| redis | 5.3.1 | — | client for Redis 7 server; arq 0.28.0 requires `redis[hiredis]<6` |
| arq | 0.28.0 | — | async task queue (requires `redis[hiredis]<6`) |
| boto3 | 1.43.67 | — | MinIO/S3 |
| numpy | 1.26.4 | — | mlflow 2.11.0 requires `numpy<2` (see note below) |
| scipy | 1.15.3 | — | Hungarian `linear_sum_assignment`; max for Py3.10 |
| pandas | 2.3.3 | — | report tables; max for Py3.10 (3.x needs ≥3.11) |
| pyarrow | 15.0.2 | — | Parquet storage; mlflow 2.11.0 requires `pyarrow<16` |
| PyYAML | 6.0.3 | — | scenario/config YAML |
| torch | 2.13.0 | 2.2+ | CPU-only build (`2.13.0+cpu`) is installed by `scripts/setup.sh` on Linux; no GPU required |
| gymnasium | 1.3.0 | 0.29+ | |
| stable-baselines3 | 2.9.0 | 2.3+ | |
| mlflow | **2.11.0** | 2.11+ | Pinned to match `ghcr.io/mlflow/mlflow:v2.11.0` (AGENTS.md §3.6); latest is 3.15.1 — upgrade **both** server image and client together when moving to 3.x |

> **CPU-only PyTorch:** the default PyPI `torch==2.13.0` wheel bundles CUDA and is multiple GB. `make setup` installs `torch==2.13.0+cpu` from the PyTorch CPU index first; the pinned `torch==2.13.0` requirement is satisfied by that local build. This project runs on CPU only (AGENTS.md §0.1).

> **Constraint cascade (mlflow 2.11.0):** requires `numpy<2` and `pyarrow<16` → `numpy==1.26.4`, `pyarrow==15.0.2`. The whole set is verified with `pip install --dry-run -r requirements-dev.txt` (resolves cleanly on Python 3.10–3.11).

## 3. Dev Dependencies (`requirements-dev.txt`)

| Package | Pinned | Spec minimum |
|---|---|---|
| pytest | 9.1.1 | 8.1+ |
| pytest-cov | 7.1.0 | — |
| pytest-asyncio | 1.4.0 | — |
| ruff | 0.16.2 | 0.3+ |
| black | 26.5.1 | 24.1+ |
| mypy | 2.3.0 | 1.9+ |
| bandit | 1.9.4 | — |

## 4. Frontend Dependencies (`frontend/package.json`)

Researched latest vs spec-pinned. **The binding spec (AGENTS.md §1.1 / BUILD.md §2.1) pins the React 18 + Vite 5 + TS 5 + Tailwind 3 stack**, so we pin to that generation rather than latest majors (React 19, Vite 8, TS 7, Tailwind 4) — latest majors violate the documented stack and break the documented peer set (R3F v9 requires React 19).

| Package | Pinned | Researched latest | Why pinned here |
|---|---|---|---|
| react / react-dom | ^18.3.1 | 19.2.8 | Spec: React 18 |
| @types/react(-dom) | ^18.3.x | 19.2.18 | match React 18 |
| vite | ^5.4.11 | 8.2.1 | Spec: Vite 5+ |
| @vitejs/plugin-react | ^4.3.4 | 6.0.5 | v6 needs Vite 6+ |
| typescript | ~5.6.3 | 7.0.2 | Spec: TS 5+ |
| tailwindcss | ^3.4.17 | 4.3.3 | Spec: Tailwind 3+ (uses `tailwind.config.ts`) |
| postcss / autoprefixer | ^8.4.49 / ^10.4.20 | 8.5.26 / 10.5.4 | Tailwind 3 build chain |
| three | ^0.170.0 | 0.185.1 | pairs with R3F v8 |
| @react-three/fiber | ^8.17.10 | 9.7.0 | v9 requires React 19 |
| @react-three/drei | ^9.122.0 | 10.7.8 | pairs with fiber v8 |
| recharts | ^2.15.1 | 3.10.1 | 2.x guaranteed React 18 compat |
| zustand | ^5.0.14 | 5.0.14 | peer react ≥18 |
| @tanstack/react-query | ^5.101.4 | 5.101.4 | peer react ≥18 |
| lucide-react | ^1.30.0 | 1.30.0 | icons |
| vitest | ^2.1.9 | 4.1.10 | v4 requires Vite 6/7 |
| jsdom | ^25.0.1 | 30.0.1 | vitest v2 pairing |
| @testing-library/react | ^16.3.2 | 16.3.2 | peer react ^18/^19 |
| @testing-library/jest-dom | ^6.6.3 | — | |
| eslint | ^8.57.1 | 10.8.1 | Spec structure uses `.eslintrc.json` (legacy config) |
| @typescript-eslint/{parser,eslint-plugin} | ^8.18.0 | — | supports eslint 8.57 |
| eslint-plugin-react-hooks / -refresh | ^4.6.2 / ^0.4.14 | — | Vite template |
| prettier | ^3.3.3 | 3.9.6 | |

## 5. Infrastructure Images (docker-compose.yml)

postgres:16-alpine · redis:7-alpine · minio/minio:RELEASE.2024-03-10T02-53-48Z · ghcr.io/mlflow/mlflow:v2.11.0 · prom/prometheus:v2.51.0 · grafana/grafana:10.4.0

## 6. Explicitly Avoided (BUILD.md §2.2)

Isaac Sim · Kubernetes · Kafka · Ray/RLlib · Custom SLAM (AMCL suffices)

## 7. Konnex SDK

**RESEARCHED (2026-08-09), NOT INTEGRATED — no Konnex dependency installed.** See `docs/konnex.md` for the full verified report.

| Item | Finding |
|---|---|
| Official docs | `https://docs.konnex.world/` — `docs.konnex.network` / `gitbook.konnex.network` **do not exist** |
| SDK | Python client inside `konnex-world/konnex` monorepo: `pip install -e ./sdk/python-client`, `from konnex import KonnexClient` |
| PyPI / npm | No public package found |
| HTTP API | Prefix `/api/v1/` (`/tasks`, `/miners/models`, `/validators/verify`) |
| In-repo status | `protocol/konnex/adapter.py` is a STUB with `# TODO: verify Konnex SDK` — no SDK calls exist anywhere |
