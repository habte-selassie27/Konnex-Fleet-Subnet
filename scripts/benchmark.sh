#!/bin/bash
# Benchmark runner — Phase 3
# Usage: ./scripts/benchmark.sh

set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Konnex Fleet Benchmark ==="
echo "Running all experiments..."
echo ""

python experiments/scripts/run_experiment.py --all --report

echo ""
echo "Results saved to experiments/results/"
