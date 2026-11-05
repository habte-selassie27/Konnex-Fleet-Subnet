#!/bin/bash
# scripts/setup.sh — install all dependencies
# Status: COMPLETE (Phase 10).
# Creates a venv, installs pinned requirements + dev requirements, and
# installs frontend npm packages.
set -euo pipefail

cd "$(dirname "$0")/.."

bash scripts/check_environment.sh

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ ! -d .venv ]; then
  echo "Creating virtual environment .venv with $PYTHON_BIN ..."
  "$PYTHON_BIN" -m venv .venv
fi

echo "Installing Python dependencies ..."
./.venv/bin/pip install --upgrade pip

# The project is CPU-only (AGENTS.md: no GPU required). Install the small
# CPU-only PyTorch wheel first so pip does not pull the multi-GB CUDA wheel.
# `torch==2.13.0` in requirements.txt is satisfied by the local `+cpu` build.
if [ "$(uname -s)" = "Linux" ]; then
  ./.venv/bin/pip install \
    --index-url https://pypi.org/simple \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    "torch==2.13.0+cpu"
fi

./.venv/bin/pip install -r requirements-dev.txt

if [ -f frontend/package.json ]; then
  echo "Installing frontend dependencies ..."
  (cd frontend && npm install)
fi

echo ""
echo "Setup complete. Next steps:"
echo "  make lint          # verify the toolchain"
echo "  make test          # run unit + integration tests"
echo "  make demo          # launch the full-stack demo"
echo "  make benchmark     # run the benchmark suite"
