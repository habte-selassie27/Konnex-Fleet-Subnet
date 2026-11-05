"""CirclePaymentProvider protocol — the Arc/Circle integration boundary.

Implementations:
    - MockCircleProvider: in-process simulation, explicitly MOCK/DEMO.
    - RealCircleProvider: Circle Wallets REST + Arc JSON-RPC (implemented;
      requires CIRCLE_API_KEY, a funded wallet id and ARC_RPC_URL).

Only payment-domain types cross this boundary — never fleet/robot types.
The PaymentService talks to wallets/chain exclusively through this protocol.

All provider methods are blocking (they perform I/O); the backend facade
invokes them through `asyncio.to_thread`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from payments.models import ProviderTransfer, SettlementStatus


@runtime_checkable
class CirclePaymentProvider(Protocol):
    """Wallet + settlement provider used by the PaymentService."""

    is_mock: bool
    network: str
    wallet_id: str

    def wallet_balance(self) -> float:
        """Current USDC balance of the agent wallet."""
        ...

    def transfer(
        self,
        *,
        to_address: str,
        amount_usdc: float,
        memo: str,
    ) -> ProviderTransfer:
        """Execute a USDC transfer. Returns the provider transaction payload."""
        ...

    def settle(self, tx_hash: str) -> SettlementStatus:
        """Confirm settlement of a transfer on (mock) Arc."""
        ...

    def get_transaction_status(self, tx_hash: str) -> dict[str, object]:
        """Query the status of a transfer by its provider tx hash."""
        ...

    def explorer_url(self, tx_hash: str) -> str:
        """Block-explorer URL for a transaction (mock explorer in demo mode)."""
        ...
