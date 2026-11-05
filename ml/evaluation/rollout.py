"""MAPPO policy evaluation via FleetEnv rollouts.

MAPPO emits a high-level target waypoint (normalized to [-1, 1], scaled to
±20 m by the environment), so it is evaluated by running complete warehouse
episodes — not by the TaskAllocator benchmark. This module produces the same
mission metrics the PoPW engine consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ml.env.encoding import flatten_obs, observation_dim, state_dim
from ml.env.fleet_env import FleetEnv, FleetEnvConfig
from ml.policies.mappo.agent import MAPPOAgent
from validator.scoring.engine import MissionResult, PoPWScoringEngine


@dataclass(frozen=True)
class MAPPORolloutResult:
    """One deterministic MAPPO episode."""

    seed: int
    tasks_completed: int
    tasks_total: int
    success_rate: float
    elapsed_s: float
    collision_count: int
    energy_consumed: float
    popw_score: float
    mission_complete: bool
    episode_steps: int


def evaluate_checkpoint(
    checkpoint_path: str | Path,
    seeds: list[int],
    config: FleetEnvConfig | None = None,
    deterministic: bool = True,
) -> list[MAPPORolloutResult]:
    """Run one episode per seed with the trained MAPPO actor."""
    env_config = config or FleetEnvConfig()
    env = FleetEnv(env_config)
    agent = MAPPOAgent.from_checkpoint(str(checkpoint_path))

    expected_obs = observation_dim(env.observation_space)
    expected_state = state_dim(env.observation_space, env.n_agents)
    expected_action = int(env.action_space.shape[0]) if env.action_space.shape else 2
    if (agent.obs_dim, agent.state_dim, agent.action_dim) != (
        expected_obs,
        expected_state,
        expected_action,
    ):
        raise ValueError(
            "Checkpoint dimensions do not match FleetEnv: "
            f"checkpoint=({agent.obs_dim},{agent.state_dim},{agent.action_dim}) "
            f"env=({expected_obs},{expected_state},{expected_action})"
        )

    scorer = PoPWScoringEngine()
    results: list[MAPPORolloutResult] = []

    for seed in seeds:
        observations, _ = env.reset(seed=seed)
        done = False
        info: dict[str, float | int | bool] = {}
        while not done:
            actions = {
                agent_id: agent.act(flatten_obs(obs), deterministic=deterministic)
                for agent_id, obs in observations.items()
            }
            observations, _, terminateds, truncateds, info = env.step(actions)
            done = bool(terminateds.get("__all__", False) or truncateds.get("__all__", False))

        metrics: dict[str, float | int | bool] = info.get("__all__", {})  # type: ignore[assignment]
        tasks_completed = int(metrics.get("tasks_completed", 0))
        tasks_total = int(metrics.get("tasks_total", env.tasks_total()))
        elapsed_s = float(metrics.get("elapsed_s", 0.0))
        collision_count = int(metrics.get("collision_count", 0))
        energy_consumed = float(metrics.get("energy_consumed", env.energy_consumed()))
        mission_complete = bool(metrics.get("mission_complete", env.mission_complete))
        episode_steps = int(metrics.get("episode_steps", 0))

        score = scorer.score(
            MissionResult(
                tasks_completed=tasks_completed,
                tasks_total=tasks_total,
                elapsed_s=elapsed_s,
                time_limit_s=env_config.time_limit_s,
                collision_count=collision_count,
                energy_consumed=energy_consumed,
                energy_budget=env_config.robot_count * 100.0,
            )
        )
        results.append(
            MAPPORolloutResult(
                seed=seed,
                tasks_completed=tasks_completed,
                tasks_total=tasks_total,
                success_rate=tasks_completed / tasks_total if tasks_total else 0.0,
                elapsed_s=elapsed_s,
                collision_count=collision_count,
                energy_consumed=energy_consumed,
                popw_score=score.final,
                mission_complete=mission_complete,
                episode_steps=episode_steps,
            )
        )

    return results


def summarize(results: list[MAPPORolloutResult]) -> dict[str, float]:
    """Aggregate rollout results with population-safe standard deviations."""
    if not results:
        return {}
    scores = np.array([r.popw_score for r in results], dtype=np.float64)
    rates = np.array([r.success_rate for r in results], dtype=np.float64)
    times = np.array([r.elapsed_s for r in results], dtype=np.float64)
    collisions = np.array([r.collision_count for r in results], dtype=np.float64)
    return {
        "n_runs": float(len(results)),
        "mean_success_rate": float(rates.mean()),
        "std_success_rate": float(rates.std(ddof=1)) if len(results) > 1 else 0.0,
        "mean_completion_time_s": float(times.mean()),
        "std_completion_time_s": float(times.std(ddof=1)) if len(results) > 1 else 0.0,
        "mean_collision_count": float(collisions.mean()),
        "mean_popw_score": float(scores.mean()),
        "std_popw_score": float(scores.std(ddof=1)) if len(results) > 1 else 0.0,
        "completion_rate": float(np.mean([r.mission_complete for r in results])),
    }
