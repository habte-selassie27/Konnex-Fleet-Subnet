# Simulation → Real Hardware

> Status: STUB — design defined, implementation pending (post-MVP / Mainnet tier).

## Path

1. **Simulation (MVP)** — Gazebo Harmonic, deterministic seeded scenarios.
2. **Domain randomization** (nice-to-have) — vary physics/sensor parameters so policies generalize.
3. **Physical adapter** (`robotics/adapters/physical.py`, currently STUB) — implements the same `RobotAdapter` Protocol as `SimulationRobotAdapter`, so the orchestrator and policies are hardware-agnostic (SYSTEM_PROMPT.md §3.2).
4. **Robot pilot** — Spark/Launch grant stages (PLAN.md §4.3, §13).

## Design invariant

Because every robot interaction flows through the `RobotAdapter` Protocol, adding real hardware changes **zero** code above the robotics layer.
