"""Failure types — robot-level failure vocabulary shared across layers.

Status: COMPLETE (Phase 5 domain layer).
Defined in the robotics layer so that adapters, the fleet failure detector,
and the validator all speak the same vocabulary without cross-layer imports.
"""

from dataclasses import dataclass
from enum import Enum


class FailureType(str, Enum):
    """Kinds of failures that can be injected or detected."""

    SHUTDOWN = "shutdown"
    COMMUNICATION_LOSS = "communication_loss"
    BATTERY_WARNING = "battery_warning"
    BATTERY_CRITICAL = "battery_critical"
    STUCK = "stuck"
    NAVIGATION_FAILURE = "navigation_failure"


class FailureSeverity(str, Enum):
    """Severity tier of a failure."""

    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class FailureEvent:
    """A detected or injected failure."""

    robot_id: str
    failure_type: FailureType
    severity: FailureSeverity
    timestamp: float
    message: str = ""
