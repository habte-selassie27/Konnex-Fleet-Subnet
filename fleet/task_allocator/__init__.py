"""Task allocators (nearest, hungarian, cost_optimizer).

Status: COMPLETE (Phase 5). Baseline policies per PLAN.md §7.2.
"""

from fleet.task_allocator.base import TaskAllocator
from fleet.task_allocator.cost_optimizer import CostOptimizerAllocator, CostWeights
from fleet.task_allocator.hungarian import HungarianAllocator
from fleet.task_allocator.nearest import NearestTaskAllocator

__all__ = [
    "CostOptimizerAllocator",
    "CostWeights",
    "HungarianAllocator",
    "NearestTaskAllocator",
    "TaskAllocator",
    "allocator_by_name",
]


def allocator_by_name(name: str) -> TaskAllocator:
    """Return the allocator registered for `name`, or raise ValueError."""
    if name == "nearest":
        return NearestTaskAllocator()
    if name == "hungarian":
        return HungarianAllocator()
    if name == "cost_optimizer":
        return CostOptimizerAllocator()
    raise ValueError(f"unknown allocator: {name!r}")
