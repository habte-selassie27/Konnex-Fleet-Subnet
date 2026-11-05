"""ResourceLimits for sandboxed policy execution.

Status: COMPLETE (Phase 6).
Applied to the Docker sandbox (STUB) and honored by the in-process executor.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceLimits:
    """Container resource and isolation limits."""

    cpu: float = 2.0
    memory_mb: int = 4096
    network_enabled: bool = False
    read_only_fs: bool = True
    timeout_s: float = 600.0

    @classmethod
    def default(cls) -> ResourceLimits:
        """Default sandbox limits (CPU 2, mem 4G, no network, read-only fs)."""
        return cls()
