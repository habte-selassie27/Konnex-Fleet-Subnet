"""Deprecated MAPPO task allocator — intentionally unusable.

History: this class hard-coded ``obs_dim=256`` and fed a 7-feature vector to
the actor. Both were wrong (the environment observation is 69 dims), the
exceptions were swallowed, and every "MAPPO" benchmark silently fell back to
``NearestTaskAllocator``. That made exp_004/exp_005 look like MAPPO results
when they were nearest-task results.

The real MAPPO policy is a continuous velocity controller, not a task
allocator. Evaluate it with ``ml/evaluation/rollout.py``. This tombstone stays
so any old import fails loudly instead of producing misleading numbers.
"""

from __future__ import annotations


class MAPPOIsNotATaskAllocatorError(RuntimeError):
    """Raised when code tries to use the MAPPO velocity policy as an allocator."""


class MAPPOTaskAllocator:
    """Removed — see module docstring. Kept only to fail with a clear message."""

    name = "mappo"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise MAPPOIsNotATaskAllocatorError(
            "MAPPOTaskAllocator was removed: MAPPO outputs continuous "
            "[linear_vel, angular_vel] actions, not robot->task assignments. "
            "It cannot be benchmarked against nearest/hungarian/cost_optimizer "
            "in the TaskAllocator harness. Use ml/evaluation/rollout.py with a "
            "trained checkpoint; exp_004/exp_005 are NOT RUN."
        )
