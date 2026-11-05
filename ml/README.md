# ml/

Multi-agent reinforcement learning platform (Phase 4).

| Path | Contents |
|---|---|
| `env/fleet_env.py` | Gymnasium multi-agent environment wrapping the warehouse task loop (CTDE) |
| `env/encoding.py` | Deterministic local-obs/global-state encoding shared by train + eval |
| `policies/base.py` | `FleetPolicy` Protocol (SYSTEM_PROMPT §3.3) |
| `policies/random.py` | Random policy (sanity check) |
| `policies/mappo/` | agent, network, real PPO trainer + `config.yaml` |
| `evaluation/rollout.py` | FleetEnv rollout evaluator for trained MAPPO checkpoints |
| `training/train.py` · `callbacks.py` | PPO training entrypoint + callbacks |
| `training/bc_pretrain.py` | BC + DAgger pretraining for the MAPPO actor |
| `checkpoints/` | PyTorch `.pt` checkpoints; `step_bc_v3.pt` is the current best policy, see README there |

**Status: COMPLETE (learned policy).** `ml/checkpoints/step_bc_v3.pt` was
bootstrapped with behavioral cloning + 3 DAgger rounds and evaluated on 30
seeds: **100.0% success, 92.9 ± 2.1 PoPW, 135.6 s mean completion** — above the
best classical baseline (Hungarian, 90.7 ± 3.8). MAPPO is a high-level
waypoint policy, so it is evaluated via
`experiments/scripts/evaluate_mappo.py`, not the TaskAllocator benchmark.
PPO fine-tuning was attempted and did not improve the BC checkpoint; raw
negative results are in `experiments/results/mappo_ppo_ft/`.
See `docs/ml.md`.
