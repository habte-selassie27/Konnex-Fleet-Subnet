#!/bin/bash
# scripts/check_environment.sh — Konnex Fleet Subnet environment check (BUILD.md §3)
set -euo pipefail

echo "=== Konnex Fleet Subnet — Environment Check ==="

check() { command -v "$1" &>/dev/null && echo "✓ $1" || echo "✗ $1 NOT FOUND"; }

check ros2
check gz          # Gazebo Harmonic
check python3
check pip
check docker
if command -v docker-compose &>/dev/null; then
  echo "✓ docker-compose"
elif docker compose version &>/dev/null 2>&1; then
  echo "✓ docker compose (v2 plugin)"
else
  echo "✗ docker compose NOT FOUND"
fi
check node
check npm

python3 -c "import torch; print(f'✓ PyTorch {torch.__version__}')" 2>/dev/null || echo "✗ PyTorch not installed"
python3 -c "import rclpy; print('✓ rclpy')" 2>/dev/null || echo "✗ rclpy not installed"
