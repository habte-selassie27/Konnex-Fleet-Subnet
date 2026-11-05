"""Konnex adapter package.

Status: COMPLETE (Phase 8 stub — SDK not yet verified).
All adapter methods raise NotImplementedError until the Konnex SDK is reviewed.

Provider interface:
    - KonnexProvider: Protocol defining the PoPW lifecycle contract
    - MockKonnexProvider: Local mock with simulated KNX rewards
    - RealKonnexProvider: STUB for live network (blocked on SDK verification)
    - create_provider(): Factory to instantiate from config
"""

from protocol.konnex.adapter import KonnexAdapter, KonnexAdapterError
from protocol.konnex.factory import create_provider
from protocol.konnex.mock_provider import MockKonnexProvider
from protocol.konnex.models import MissionMetadata, SubmissionReceipt
from protocol.konnex.provider import KonnexProvider
from protocol.konnex.real_provider import RealKonnexProvider

__all__ = [
    "KonnexAdapter",
    "KonnexAdapterError",
    "KonnexProvider",
    "MockKonnexProvider",
    "MissionMetadata",
    "RealKonnexProvider",
    "SubmissionReceipt",
    "create_provider",
]
