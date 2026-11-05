# ML Platform — MAPPO for Fleet Coordination

> **Status: COMPLETE for the BC + DAgger MAPPO actor.** The environment,
> actor/critic, PPO trainer, behavioral-cloning/DAgger pretrainer, rollout
> evaluator, and training entrypoint are implemented. The current best
> checkpoint (`ml/checkpoints/step_bc_v3.pt`) completes 30/30 evaluation
> missions (20/20 tasks each) and scores **92.9 ± 2.1 PoPW**, above the best
> classical baseline (Hungarian, 90.7 ± 3.8). PPO fine-tuning from that
> checkpoint was attempted (30k, 20k, and 100k timesteps) and did not improve
> it; the BC + DAgger checkpoint remains published. The negative results and
> post-mortem are in `experiments/results/mappo_ppo_ft/`.

## Why MAPPO is not a TaskAllocator

MAPPO controls robots: it maps a local observation to a high-level waypoint
target in `FleetEnv`. The benchmark allocators (nearest, Hungarian, cost
optimizer) map `(robots, tasks) -> assignments`. These are different
interfaces, so MAPPO cannot be substituted into `POLICY_MAP` in
`experiments/scripts/run_experiment.py`.

The old `MAPPOTaskAllocator` tried to do this anyway with hard-coded
`obs_dim=256`, a 7-feature `_score_pair()` vector, and a silent
`except Exception: return nearest`. That is why `exp_004` rows were
byte-identical to `exp_001` nearest rows. The class is now a tombstone that
raises `MAPPOIsNotATaskAllocatorError`.

## Environment (`ml/env/fleet_env.py`)

Gymnasium multi-agent environment with one agent per robot. CTDE:
centralized training, decentralized execution.

- Observation per agent: position, velocity, orientation, battery, task
  pickup/delivery, task progress, task phase (`-1` idle / `0` to pickup /
  `1` to delivery), 36-bin LiDAR, 4 nearby robots, 3 pending tasks, fleet
  utilization, tasks remaining, time remaining. **70 dims.**
- Global state for the centralized critic: all agents' observations
  concatenated in sorted agent order. **350 dims for 5 agents.**
- Action: high-level target waypoint relative to the robot, normalized to
  `[-1, 1]` and scaled to ±20 m by the environment.
- Navigation: deterministic A* over a 0.5 m occupancy grid built from world
  walls and 15 shelf rectangles, with stop-and-turn heading control, a
  repulsive-potential stuck-recovery rotation, reciprocal robot-robot
  repulsion plus forward-cone yielding, and a 2.5 m docking assist that snaps
  the goal to the assigned pickup/delivery. This is low-level control; the
  learned policy chooses the waypoint.
- Task assignment: greedy nearest unassigned pickup per idle robot.
- Reward: pickup +5, delivery +10, collision −1, dense distance shaping,
  per-step time cost −0.01, mission-complete time bonus, terminal task bonus,
  small energy penalty. The per-step term must stay negative: a positive
  "alive" bonus pays ~+300 fleet reward for standing still over a 600 s
  episode, which outbids completing all 20 tasks and makes inaction the
  greedy optimum.
- Battery: a full charge lasts ~1200 s of movement.

## Training

```bash
# BC + DAgger pretraining (the current best checkpoint)
./.venv/bin/python ml/training/bc_pretrain.py \
  --episodes 20 --seeds 2000-2019 \
  --epochs 40 --dagger-iterations 3 \
  --dagger-episodes 5 --dagger-seeds 3000-3004 \
  --dagger-epochs 15 \
  --output ml/checkpoints/step_bc_v3.pt

# PPO fine-tuning from a pretrained checkpoint.
# --init-log-std is mandatory in practice: the default log_std = 0 means std
# = 1.0, i.e. ±20 m of waypoint noise, which destroys the BC policy.
./.venv/bin/python ml/training/train.py \
  --config ml/policies/mappo/config_finetune.yaml \
  --total-timesteps 100000 \
  --init-checkpoint ml/checkpoints/step_bc_v3.pt \
  --init-log-std -2.0 \
  --output-dir experiments/results/mappo_ppo_ft \
  --checkpoint-dir ml/checkpoints/ppo_ft
```

**Fine-tuning result so far: NOT IMPROVED.** Plain PPO from the BC checkpoint
regresses (60k total steps across two attempts: 1–7.5% success vs 100% for BC;
full numbers in `experiments/results/mappo_ppo_ft/README.md`). Reducing
exploration from std 1.0 to 0.135 recovers training reward but not evaluation
performance; the critic is under-fit. The published MAPPO policy is therefore
the BC + DAgger checkpoint.

`ml/training/bc_pretrain.py` labels expert rollouts (point at the assigned
pickup, then the delivery) and, in each DAgger round, labels the states the
learned policy actually visits before retraining. This fixes the compounding
error that plain BC suffers from.

`ml/training/train.py` collects per-agent transitions, computes GAE per agent,
feeds the **global state** to the centralized critic, applies the entropy and
value-loss coefficients, and saves checkpoints with shape metadata.

Checkpoints store `obs_dim`, `state_dim`, and `action_dim`.
`MAPPOAgent.from_checkpoint()` reads them and rejects mismatches; there is no
silent fallback.

## Evaluation

MAPPO is evaluated by rolling out complete warehouse episodes:

```bash
python experiments/scripts/evaluate_mappo.py \
  --checkpoint ml/checkpoints/step_bc_v3.pt \
  --seeds 1000-1029 \
  --output experiments/results/mappo_eval
```

The evaluator computes task success, completion time, collisions, energy, and
the same PoPW score used by the validator. It never calls an allocator.

### Real results (30 seeds, warehouse_v1, 5 robots, 20 tasks)

| Policy | Success | Time (s) | Collisions | PoPW | Status |
|---|---|---|---|---|---|
| MAPPO actor (BC + DAgger) | 100.0% ± 0.0% | 135.63 ± 14.20 | 1.1 | 92.9 ± 2.1 | COMPLETE |

The checkpoint is `ml/checkpoints/step_bc_v3.pt`; the raw run is
`experiments/results/mappo_eval/result.json`. The classical baselines use the
orchestrator benchmark and are listed in the top-level `README.md`.

## Checkpoints

`ml/checkpoints/step_bc_v3.pt` is the current best learned policy. Older
`step_*.pt` files are random-policy or superseded artifacts; see
`ml/checkpoints/README.md`. Do not report legacy checkpoints as benchmark
results.
