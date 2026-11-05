"""SensorFrame dataclass — LiDAR + odometry snapshot.

Status: COMPLETE (Phase 5 domain layer).
"""

from dataclasses import dataclass, field


@dataclass
class SensorFrame:
    """A single sensor observation snapshot."""

    lidar_ranges: list[float] = field(default_factory=list)
    imu_yaw: float = 0.0
    timestamp: float = 0.0
