"""Konnex provider factory — instantiates the correct provider from config.

Reads the KONNEX_PROVIDER environment variable and returns:
    - "disabled" → None (Konnex integration off)
    - "mock"     → MockKonnexProvider (local simulated rewards)
    - "real"     → RealKonnexProvider (STUB — raises NotImplementedError)

Boundary contract (AGENTS.md §6.8):
    Only protocol-safe types cross this boundary.
    Zero imports from robotics/, simulation/, ml/, fleet/.

Status: COMPLETE.
"""

from __future__ import annotations

import structlog

from protocol.konnex.mock_provider import MockKonnexProvider

logger = structlog.get_logger(__name__)

# Valid provider modes
PROVIDER_MODES = ("disabled", "mock", "real", "bittensor")


def create_provider(
    mode: str = "disabled",
    endpoint: str = "",
    api_key: str = "",
) -> MockKonnexProvider | None:
    """Create a KonnexProvider based on the configured mode.

    Args:
        mode: One of "disabled", "mock", "real".
        endpoint: Konnex network URL (only used by "real" mode).
        api_key: Konnex API key (only used by "real" mode).

    Returns:
        MockKonnexProvider for "mock" mode, None for "disabled" mode.
        "real" mode returns the HTTP-based provider (partial).
        "bittensor" mode returns the on-chain provider (Launch tier, STUBs for live ops).

    Raises:
        ValueError: If mode is not one of the valid modes.
    """
    if mode not in PROVIDER_MODES:
        raise ValueError(
            f"Invalid KONNEX_PROVIDER mode: {mode!r}. Must be one of: {', '.join(PROVIDER_MODES)}"
        )

    if mode == "disabled":
        logger.info("konnex_provider_disabled")
        return None

    if mode == "mock":
        logger.info("konnex_provider_mock")
        return MockKonnexProvider()

    if mode == "real":
        from protocol.konnex.real_provider import RealKonnexProvider

        logger.warning(
            "konnex_provider_real",
            message="HTTP-based Konnex provider (partial). Undocumented methods raise.",
        )
        return RealKonnexProvider(endpoint=endpoint, api_key=api_key)  # type: ignore[return-value]

    # mode == "bittensor" (Launch tier)
    from protocol.konnex.bittensor_provider import BittensorKonnexProvider

    logger.warning(
        "konnex_provider_bittensor",
        message="Bittensor-based Konnex provider (Launch tier).",
    )
    return BittensorKonnexProvider(  # type: ignore[return-value]
        network=endpoint or "testnet",
    )
