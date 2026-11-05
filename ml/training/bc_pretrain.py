#!/usr/bin/env python3
"""Behavioral-cloning + DAgger pretraining for the MAPPO actor.

The MAPPO actor emits a high-level target waypoint (normalized to [-1, 1] and
scaled to +/-20 m by FleetEnv). The expert is a reactive task-seeker:

    - assigned task, not picked up  -> point at the pickup
    - assigned task, picked up      -> point at the delivery
    - idle with pending tasks       -> point at the nearest pending pickup
    - otherwise                     -> stay put

Plain BC clones the expert on expert-visited states, which suffers from
compounding error once the policy deviates. DAgger fixes this by labelling the
states the *learned* policy actually visits with the expert action and
aggregating them back into the training set.

Usage:
    python ml/training/bc_pretrain.py \
        --episodes 40 --epochs 60 \
        --dagger-iterations 3 --dagger-episodes 10 \
        --output ml/checkpoints/step_bc_v2.pt
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.env.encoding import (  # noqa: E402
    flatten_obs,
    observation_dim,
    state_dim,
)
from ml.env.fleet_env import FleetEnv, FleetEnvConfig  # noqa: E402
from ml.policies.mappo.agent import MAPPOAgent  # noqa: E402

NDArray = npt.NDArray[np.float32]

ACTION_SCALE_M = 20.0

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def parse_seeds(value: str) -> list[int]:
    if "-" in value:
        start, end = value.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(part) for part in value.split(",")]


def expert_action(obs: dict[str, Any]) -> NDArray:
    """Expert waypoint target for one agent, normalized to [-1, 1]."""
    if int(obs["has_task"]):
        rel = obs["task_delivery"] if float(obs["task_phase"]) >= 0.5 else obs["task_pickup"]
    else:
        pending = obs["pending_tasks"]
        rel = (
            pending[0] if pending.shape[0] and np.any(pending[0]) else np.zeros(2, dtype=np.float32)
        )
    return np.clip(np.asarray(rel, dtype=np.float32) / ACTION_SCALE_M, -1.0, 1.0)


def rollout(
    env: FleetEnv,
    seed: int,
    policy: str,
    agent: MAPPOAgent | None = None,
) -> list[tuple[NDArray, NDArray]]:
    """Run one episode and return (flattened obs, expert action) pairs."""
    observations, _ = env.reset(seed=seed)
    samples: list[tuple[NDArray, NDArray]] = []
    done = False
    while not done:
        actions: dict[str, NDArray] = {}
        for agent_id, obs in observations.items():
            label = expert_action(obs)
            samples.append((flatten_obs(obs), label))
            if policy == "expert":
                actions[agent_id] = label
            else:
                assert agent is not None
                actions[agent_id] = agent.act(flatten_obs(obs), deterministic=True)
        observations, _, terminateds, truncateds, _ = env.step(actions)
        done = bool(terminateds.get("__all__", False) or truncateds.get("__all__", False))
    return samples


def train_actor(
    agent: MAPPOAgent,
    features: NDArray,
    labels: NDArray,
    epochs: int,
    batch_size: int,
    lr: float,
    seed: int,
    log_prefix: str = "",
) -> None:
    """Fit the actor's deterministic action (tanh(mean)) to expert labels."""
    optimizer = torch.optim.Adam(agent.actor.parameters(), lr=lr)
    rng = np.random.default_rng(seed)
    n = len(features)
    for epoch in range(epochs):
        permutation = rng.permutation(n)
        total_loss = 0.0
        for start in range(0, n, batch_size):
            index = permutation[start : start + batch_size]
            x = torch.as_tensor(features[index], dtype=torch.float32, device=agent.device)
            y = torch.as_tensor(labels[index], dtype=torch.float32, device=agent.device)
            mean, _ = agent.actor(x)
            loss = ((mean.tanh() - y) ** 2).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * len(index)
        if epoch % 10 == 0 or epoch == epochs - 1:
            logger.info("%sepoch %s: mse=%.5f", log_prefix, epoch, total_loss / n)


def main() -> None:
    parser = argparse.ArgumentParser(description="BC + DAgger pretraining for MAPPO")
    parser.add_argument("--episodes", type=int, default=40, help="expert episodes for BC")
    parser.add_argument("--seeds", type=str, default="2000-2039", help="expert seed range")
    parser.add_argument("--epochs", type=int, default=60, help="BC epochs")
    parser.add_argument("--dagger-iterations", type=int, default=3)
    parser.add_argument("--dagger-episodes", type=int, default=10)
    parser.add_argument("--dagger-seeds", type=str, default="3000-3009")
    parser.add_argument("--dagger-epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--robot-count", type=int, default=5)
    parser.add_argument("--task-count", type=int, default=20)
    parser.add_argument("--time-limit", type=float, default=600.0)
    parser.add_argument("--output", type=str, default="ml/checkpoints/step_bc_v2.pt")
    args = parser.parse_args()

    config = FleetEnvConfig(
        robot_count=args.robot_count,
        task_count=args.task_count,
        seed=args.seed,
        time_limit_s=args.time_limit,
    )
    env = FleetEnv(config)
    agent = MAPPOAgent(
        obs_dim=observation_dim(env.observation_space),
        state_dim=state_dim(env.observation_space, env.n_agents),
        action_dim=2,
        lr=args.lr,
    )

    # ── Phase 1: expert demonstrations ────────────────────────────────────
    features: list[NDArray] = []
    labels: list[NDArray] = []
    expert_seeds = parse_seeds(args.seeds)[: args.episodes]
    for episode, seed in enumerate(expert_seeds):
        samples = rollout(env, seed, policy="expert")
        features.extend(sample[0] for sample in samples)
        labels.extend(sample[1] for sample in samples)
        logger.info(
            "expert episode %s/%s: %s samples",
            episode + 1,
            len(expert_seeds),
            len(samples),
        )

    x = np.asarray(features, dtype=np.float32)
    y = np.asarray(labels, dtype=np.float32)
    logger.info("BC dataset: %s samples, obs_dim=%s", x.shape[0], x.shape[1])
    train_actor(agent, x, y, args.epochs, args.batch_size, args.lr, args.seed, "bc ")
    agent.save(args.output)
    logger.info("saved %s", args.output)

    # ── Phase 2: DAgger — label policy-visited states with the expert ─────
    dagger_seeds = parse_seeds(args.dagger_seeds)
    for iteration in range(args.dagger_iterations):
        new_features: list[NDArray] = []
        new_labels: list[NDArray] = []
        for seed in dagger_seeds[: args.dagger_episodes]:
            samples = rollout(env, seed, policy="policy", agent=agent)
            new_features.extend(sample[0] for sample in samples)
            new_labels.extend(sample[1] for sample in samples)
        x = np.concatenate([x, np.asarray(new_features, dtype=np.float32)], axis=0)
        y = np.concatenate([y, np.asarray(new_labels, dtype=np.float32)], axis=0)
        logger.info(
            "dagger %s: +%s samples (total %s)",
            iteration + 1,
            len(new_features),
            x.shape[0],
        )
        train_actor(
            agent,
            x,
            y,
            args.dagger_epochs,
            args.batch_size,
            args.lr,
            args.seed + iteration + 1,
            f"dagger{iteration + 1} ",
        )
        agent.save(args.output)
        logger.info("saved %s", args.output)

    # ── Phase 3: report real validation performance ───────────────────────
    from ml.evaluation.rollout import evaluate_checkpoint, summarize

    results = evaluate_checkpoint(args.output, list(range(1000, 1010)), config=config)
    summary = summarize(results)
    logger.info(
        "validation: success=%.1f%% popw=%.1f time=%.1fs",
        summary["mean_success_rate"] * 100.0,
        summary["mean_popw_score"],
        summary["mean_completion_time_s"],
    )


if __name__ == "__main__":
    main()
