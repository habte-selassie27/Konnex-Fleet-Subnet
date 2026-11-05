"""MockCircleProvider — in-process simulation of the Circle Wallets + Arc flow.

MOCK / DEMO ONLY. This provider:
    - keeps an in-memory USDC balance for the agent wallet
    - produces deterministic MOCK transaction hashes (0xMOCK...)
    - simulates Arc settlement (pending -> settled)
    - exposes a mock block-explorer URL
It makes NO network calls and no real USDC moves. RealCircleProvider replaces
it when Circle/Arc credentials are available (see docs/payments.md).

Every artifact it produces carries is_mock=True / a 0xMOCK... hash so nothing
here can be mistaken for a real on-chain transaction (spec §12: never fake
blockchain functionality).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import structlog

from payments.models import (
    PaymentStatus,
    ProviderTransfer,
    SettlementStatus,
)

logger = structlog.get_logger(__name__)

MOCK_NETWORK = "arc-mock"
MOCK_EXPLORER_BASE = "https://mock-explorer.arc.local/tx"

# Prefix that makes mock hashes unmistakable: 0xMOCK + 60 hex chars.
_MOCK_HASH_PREFIX = "MOCK"


@dataclass
class _MockTransaction:
    """In-memory record of a mock USDC transfer."""

    tx_hash: str
    to_address: str
    amount_usdc: float
    memo: str
    status: PaymentStatus
    settlement_status: SettlementStatus
    created_at: float
    settled_at: float | None = None


class MockCircleProvider:
    """Implements CirclePaymentProvider in memory. is_mock=True everywhere."""

    is_mock = True
    network = MOCK_NETWORK

    def __init__(self, wallet_id: str, initial_balance_usdc: float = 1000.0) -> None:
        self.wallet_id = wallet_id
        self._balance = round(initial_balance_usdc, 2)
        self._transactions: dict[str, _MockTransaction] = {}
        self._counter = 0
        logger.info(
            "mock_circle_provider_initialized",
            wallet_id=wallet_id,
            balance_usdc=self._balance,
            mock=True,
        )

    # ─── Protocol implementation ─────────────────────────────────────────

    def wallet_balance(self) -> float:
        """Current (simulated) USDC balance."""
        return round(self._balance, 2)

    def transfer(
        self,
        *,
        to_address: str,
        amount_usdc: float,
        memo: str,
    ) -> ProviderTransfer:
        """Execute a mock USDC transfer. Deducts the simulated balance."""
        if amount_usdc <= 0:
            raise ValueError("amount_usdc must be > 0")
        if amount_usdc > self._balance:
            raise ValueError(f"insufficient wallet balance: {amount_usdc} > {self._balance} USDC")
        self._counter += 1
        tx_hash = self._mock_hash(to_address, amount_usdc, memo)
        self._balance = round(self._balance - amount_usdc, 2)
        self._transactions[tx_hash] = _MockTransaction(
            tx_hash=tx_hash,
            to_address=to_address,
            amount_usdc=round(amount_usdc, 2),
            memo=memo,
            status=PaymentStatus.EXECUTED,
            settlement_status=SettlementStatus.PENDING,
            created_at=time.time(),
        )
        logger.info(
            "mock_transfer_executed",
            tx_hash=tx_hash,
            amount_usdc=amount_usdc,
            to_address=to_address,
            mock=True,
        )
        return ProviderTransfer(
            tx_hash=tx_hash,
            status=PaymentStatus.EXECUTED,
            settlement_status=SettlementStatus.PENDING,
            provider_payload={
                "network": MOCK_NETWORK,
                "wallet_id": self.wallet_id,
                "mock": True,
            },
        )

    def settle(self, tx_hash: str) -> SettlementStatus:
        """Simulate Arc confirmation of a pending transfer."""
        record = self._transactions.get(tx_hash)
        if record is None:
            raise KeyError(f"unknown mock tx {tx_hash}")
        record.status = PaymentStatus.SETTLED
        record.settlement_status = SettlementStatus.SETTLED
        record.settled_at = time.time()
        logger.info("mock_settlement_confirmed", tx_hash=tx_hash, mock=True)
        return record.settlement_status

    def get_transaction_status(self, tx_hash: str) -> dict[str, object]:
        """Query a mock transfer's status."""
        record = self._transactions.get(tx_hash)
        if record is None:
            return {"tx_hash": tx_hash, "status": "not_found", "mock": True}
        return {
            "tx_hash": record.tx_hash,
            "status": record.status.value,
            "settlement_status": record.settlement_status.value,
            "amount_usdc": record.amount_usdc,
            "to_address": record.to_address,
            "mock": True,
        }

    def explorer_url(self, tx_hash: str) -> str:
        """Mock block-explorer URL (clearly not a real explorer)."""
        return f"{MOCK_EXPLORER_BASE}/{tx_hash}"

    # ─── Internals ───────────────────────────────────────────────────────

    def _mock_hash(self, to_address: str, amount_usdc: float, memo: str) -> str:
        """Deterministic, unmistakably-mock transaction hash."""
        digest = hashlib.sha256(
            f"{self._counter}|{to_address}|{amount_usdc}|{memo}".encode()
        ).hexdigest()
        return f"0x{_MOCK_HASH_PREFIX}{digest[4:60]}"
