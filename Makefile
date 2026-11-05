# Makefile — Konnex Fleet Intelligence Subnet
# All targets are defined upfront (BUILD.md §3 / AGENTS.md §9.1).
# Targets for future phases print STUB status until implemented — no fabricated behavior.

.PHONY: benchmark-unified mlflow-ingest mlflow-ui verify-consensus echo-policy-image verify-logs sim-backend
.PHONY: help setup demo sim sim-world sim-robots backend frontend build \
	benchmark benchmark-single test test-unit test-integration test-sim test-e2e \
	test-frontend lint lint-fix train-mappo train-mappo-quick evaluate-mappo \
	db-migrate db-reset \
	db-seed docs clean clean-results konnex-check konnex-demo konnex-docs \
	payment-demo payment-docs

# Prefer the project venv. On a fresh checkout, .venv may not exist yet; setup
# creates it. Never silently use a system Python that lacks the dependencies.
PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
PYTEST := $(PYTHON) -m pytest
SEEDS ?= 1000-1009
OUTPUT ?= experiments/results/mappo_eval
CHECKPOINT ?=

# ─── Setup ──────────────────────────────────────────────────────────────────

setup:
	@bash scripts/setup.sh

# ─── Demo (Law 3: must work with one command by Phase 10) ───────────────────

demo:
	@bash scripts/demo.sh

# ─── Simulation (Phase 1) ───────────────────────────────────────────────────
# Gazebo Harmonic + ROS 2 Humble run inside the `gazebo` container (see
# simulation/Dockerfile.gazebo). The container entrypoint launches the
# warehouse world + robots + gz<->ROS bridge; the targets below expose the
# same container in different modes.
# NOTE: the first `make sim` pulls/boots a multi-GB image and needs a
# display/EGL for rendering (headless: set DISPLAY= or run in the container).

sim:
	@docker compose up --build gazebo

sim-world:
	@docker compose run --rm --entrypoint bash gazebo -lc \
		"source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && ros2 launch simulation warehouse.launch.py"

sim-robots:
	@docker compose exec gazebo bash -lc \
		"source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && ros2 launch simulation multi_robot.launch.py"

sim-up:
	@docker compose up --build -d gazebo

sim-down:
	@docker compose down

sim-logs:
	@docker compose logs -f gazebo

sim-test:
	@echo "=== Gazebo-gated sim tests ==="
	@echo "BLOCKED on this host: no gz/ros2 binary on PATH (ROS 2 + Gazebo are containerized)."
	@echo "The sim tests in tests/simulation/ self-skip accordingly."
	@echo "See docs/simulation.md for exact repro steps to run them inside the container."
	@echo "Running the inert-mode unit tests instead:"
	@$(PYTEST) tests/unit/test_gazebo_adapter.py tests/unit/test_ros_bridge.py -v --tb=short

# ─── Services ───────────────────────────────────────────────────────────────

backend:
	@$(PYTHON) -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

frontend:
	@cd frontend && npm run dev

build:
	@docker-compose build

# ─── Benchmarking (Phase 3) ─────────────────────────────────────────────────

benchmark:
	@$(PYTHON) experiments/scripts/run_experiment.py --all --report

benchmark-single:
	@$(PYTHON) experiments/scripts/run_experiment.py \
		--config experiments/configs/$(EXP).yaml \
		--report

# ─── Testing ────────────────────────────────────────────────────────────────

test:
	@$(PYTEST) tests/unit tests/integration \
		-v \
		--tb=short \
		--strict-markers \
		--cov=. \
		--cov-report=term-missing

test-unit:
	@$(PYTEST) tests/unit -v --tb=short

test-integration:
	@$(PYTEST) tests/integration -v --tb=short

test-sim:
	@$(PYTEST) tests/simulation -v --tb=short -m simulation

test-e2e:
	@$(PYTEST) tests/e2e -v --tb=short -m e2e

test-frontend:
	@cd frontend && npm run test:unit

# ─── Linting ────────────────────────────────────────────────────────────────

lint:
	@echo "=== Python lint ==="
	@$(PYTHON) -m ruff check .
	@$(PYTHON) -m ruff format --check .
	@$(PYTHON) -m mypy . --ignore-missing-imports --explicit-package-bases
	@$(PYTHON) -m bandit -r . -ll -c pyproject.toml
	@echo "=== TypeScript lint ==="
	@cd frontend && npm run lint && npm run type-check
	@echo "All lint checks passed."

lint-fix:
	@$(PYTHON) -m ruff check . --fix
	@$(PYTHON) -m ruff format .
	@cd frontend && npm run lint:fix

# ─── ML Training (Phase 4) ──────────────────────────────────────────────────

train-mappo:
	@$(PYTHON) ml/training/train.py \
		--config ml/policies/mappo/config.yaml \
		--seed 42 \
		--total-timesteps 5000000

train-mappo-quick:
	@$(PYTHON) ml/training/train.py \
		--config ml/policies/mappo/config.yaml \
		--seed 42 \
		--total-timesteps 100000

evaluate-mappo:
	@test -n "$(CHECKPOINT)" || (echo "Usage: make evaluate-mappo CHECKPOINT=ml/checkpoints/step_N.pt"; exit 1)
	@$(PYTHON) experiments/scripts/evaluate_mappo.py \
		--checkpoint "$(CHECKPOINT)" \
		--seeds "$(SEEDS)" \
		--output "$(OUTPUT)"

# ─── Database ───────────────────────────────────────────────────────────────

db-migrate:
	@$(PYTHON) -m alembic upgrade head

db-reset:
	@$(PYTHON) -m alembic downgrade base
	@$(PYTHON) -m alembic upgrade head

db-seed:
	@$(PYTHON) backend/db/seed.py

# ─── Documentation ──────────────────────────────────────────────────────────

docs:
	@echo "Documentation index:"
	@ls -la docs/

# ─── Cleanup ────────────────────────────────────────────────────────────────

clean:
	@docker-compose down -v
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete
	@cd frontend && rm -rf dist node_modules 2>/dev/null || true
	@echo "Clean complete."

clean-results:
	@echo "WARNING: This deletes all benchmark results."
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	@find experiments/results -name "*.json" -delete
	@find experiments/results -name "*.jsonl" -delete
	@echo "Results cleared."

# ─── Reproducibility verification (Phase 6) ─────────────────────────────────

verify-repro:
	@$(PYTHON) scripts/verify_reproducibility.py

# Real-container consensus: two independent validators must agree within ±0.5.
# Requires the committed echo policy image (see validator/examples/echo_policy).
verify-consensus:
	@$(PYTHON) scripts/verify_consensus.py

echo-policy-image:
	@docker build -t konnex-echo-policy validator/examples/echo_policy

# Benchmark log integrity: row counts, run ids, duplicate seeds, git metadata.
verify-logs:
	@$(PYTHON) scripts/verify_benchmark_logs.py

# Unified cross-harness benchmark: every policy scored inside FleetEnv.
benchmark-unified:
	@$(PYTHON) experiments/scripts/benchmark_fleet_env.py --seeds $(SEEDS)

# File-backed MLflow evidence (no server needed).
mlflow-ingest:
	@$(PYTHON) -m ml.tracking.ingest

mlflow-ui:
	@$(PYTHON) -m mlflow ui --backend-store-uri ./mlruns

# Backend + Gazebo with live ROS 2 telemetry (simulation profile).
sim-backend:
	@docker compose --profile simulation up -d gazebo backend-sim
	@echo "Gazebo-backed backend: http://localhost:8001/docs"

# ─── Konnex Integration (STUB — SDK not yet verified) ───────────────────────

konnex-check:
	@echo "=== Checking Konnex Adapter Status ==="
	@$(PYTHON) -c "from protocol.konnex.adapter import KonnexAdapter; print('Adapter loaded. Status: STUB — SDK not yet verified.')"

konnex-demo:
	@$(PYTHON) scripts/konnex_demo.py

konnex-docs:
	@echo "Visit Konnex docs to verify SDK before implementing adapter:"
	@echo "https://docs.konnex.world (verified 2026-08-09)"
	@echo "SDK source: https://github.com/konnex-world/konnex (monorepo, sdk/python-client)"
	@echo "Full blockers: see docs/konnex.md"

# ─── Agentic Payments (Arc + Circle USDC) ───────────────────────────────────
# FleetPay Agent — mock provider by default (PAYMENT_PROVIDER=mock in .env).
# Real Circle Wallets + Arc integration is STUB until credentials exist
# (docs/payments.md). Every hash shown is a 0xMOCK... demo hash.

payment-demo:
	@$(PYTHON) scripts/payment_demo.py

payment-docs:
	@echo "Agentic payment layer documentation:"
	@echo "  docs/payments.md  — architecture, setup, Arc/Circle config, contract deploy"

# ─── Help ───────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Konnex Fleet Intelligence Subnet — Make Targets"
	@echo "================================================"
	@echo ""
	@echo "  make setup          Install all dependencies"
	@echo "  make demo           Launch full demo stack"
	@echo "  make benchmark      Run complete benchmark suite"
	@echo "  make test           Run unit + integration tests"
	@echo "  make lint           Run all linters"
	@echo "  make train-mappo    Train MAPPO policy"
	@echo "  make evaluate-mappo CHECKPOINT=...  Evaluate a trained MAPPO checkpoint"
	@echo "  make clean          Clean build artifacts"
	@echo "  make konnex-check   Check Konnex adapter status"
	@echo "  make konnex-demo    Run full Konnex lifecycle demo (mock)"
	@echo "  make payment-demo   Run FleetPay agentic payment demo (mock USDC/Arc)"
	@echo ""
