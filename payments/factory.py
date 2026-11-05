"""Payment provider factory — mirrors protocol/konnex/factory.py.

Reads the PAYMENT_PROVIDER environment variable and returns:
    - "disabled" -> None (payment layer off)
    - "mock"     -> MockCircleProvider (local USDC/Arc simulation, MOCK-labeled)
    - "real"     -> RealCircleProvider (Circle Wallets REST + Arc JSON-RPC)

Real mode validates its configuration at construction time and raises
PaymentProviderConfigError naming the missing env var — it never falls back
to mock data (Law 1: a real deployment must not silently show fake USDC).

Boundary contract: only payment-domain configuration crosses this boundary.
"""

from __future__ import annotations

import structlog

from payments.errors import PaymentProviderConfigError
from payments.mock_provider import MockCircleProvider
from payments.provider import CirclePaymentProvider

logger = structlog.get_logger(__name__)

# Valid provider modes
PROVIDER_MODES = ("disabled", "mock", "real")


def create_payment_provider(
    mode: str = "mock",
    *,
    wallet_id: str = "fleet-agent-wallet-001",
    initial_balance_usdc: float = 1000.0,
    circle_api_key: str = "",
    circle_entity_secret: str = "",
    circle_token_id: str = "",
    circle_entity_public_key: str = "",
    circle_wallet_set_id: str = "",  # noqa: ARG001 (reserved for wallet creation)
    arc_rpc_url: str = "",
    arc_chain_id: str = "",
    arc_explorer_url: str = "",
    arc_contract_address: str = "",  # noqa: ARG001 (reserved for the settlement contract)
) -> CirclePaymentProvider | None:
    """Create a CirclePaymentProvider based on the configured mode.

    Args:
        mode: One of "disabled", "mock", "real".
        wallet_id: Agent wallet identifier (Circle wallet id in real mode).
        initial_balance_usdc: Starting USDC balance (mock mode only).
        circle_api_key: Circle API key, `PREFIX:ID:SECRET` (real mode).
        circle_entity_secret: 32-byte hex entity secret (real mode).
        circle_token_id: Circle token id for USDC (real mode).
        circle_entity_public_key: Optional PEM override; fetched from Circle if empty.
        circle_wallet_set_id: Circle wallet set id (reserved for wallet ops).
        arc_rpc_url: Arc JSON-RPC endpoint (real mode).
        arc_chain_id: Arc chain id — 5042 mainnet / 5042002 testnet (real mode).
        arc_explorer_url: Explorer base URL (real mode; derived from chain id).
        arc_contract_address: Deployed FleetPayment contract (reserved).

    Returns:
        MockCircleProvider for "mock", RealCircleProvider for "real",
        None for "disabled".

    Raises:
        ValueError: If mode is not one of the valid modes.
        PaymentProviderConfigError: If real mode is missing configuration.
    """
    if mode not in PROVIDER_MODES:
        raise ValueError(
            f"Invalid PAYMENT_PROVIDER mode: {mode!r}. Must be one of: {', '.join(PROVIDER_MODES)}"
        )

    if mode == "disabled":
        logger.info("payment_provider_disabled")
        return None

    if mode == "mock":
        logger.info(
            "payment_provider_mock",
            wallet_id=wallet_id,
            message="Mock Circle/Arc provider active — no real USDC moves.",
        )
        return MockCircleProvider(
            wallet_id=wallet_id,
            initial_balance_usdc=initial_balance_usdc,
        )

    # mode == "real" — construct eagerly so misconfiguration fails at startup.
    from payments.real_provider import RealCircleProvider

    provider = RealCircleProvider(
        wallet_id=wallet_id,
        circle_api_key=circle_api_key,
        entity_secret=circle_entity_secret,
        token_id=circle_token_id,
        entity_public_key=circle_entity_public_key,
        arc_rpc_url=arc_rpc_url,
        arc_chain_id=arc_chain_id,
        arc_explorer_url=arc_explorer_url,
    )
    logger.info(
        "payment_provider_real",
        wallet_id=provider.wallet_id,
        network=provider.network,
        message="Real Circle/Arc provider active — transfers move real USDC.",
    )
    return provider


__all__ = ["PROVIDER_MODES", "PaymentProviderConfigError", "create_payment_provider"]
