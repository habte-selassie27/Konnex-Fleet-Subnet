"""PaymentService — orchestrates the agentic payment flow.

Flow (docs/payments.md):
    FleetEvent -> AgentDecision (provider evaluation)
    -> PaymentIntent (structured request)
    -> PaymentPolicy (deterministic gatekeeper)
    -> CirclePaymentProvider (USDC transfer — mock in demo mode)
    -> Arc settlement (mock confirmation)
    -> PaymentReceipt

The service owns the transaction ledger and the wallet snapshot. It never
calls a wallet on raw AI output — every payment passes the policy engine
first (spec §6). Backend persistence is handled by the wrapper in
backend/services/payment_service.py.

Status: COMPLETE — mock flow (MOCK/DEMO labeled) and real Circle/Arc
settlement (payments/real_provider.py; requires credentials, docs/payments.md).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace

import structlog

from payments.agent import FleetPaymentAgent
from payments.errors import PaymentProviderConfigError
from payments.models import (
    AgentDecision,
    EventType,
    FleetEvent,
    PaymentIntent,
    PaymentReceipt,
    PaymentRequest,
    PaymentStatus,
    Provider,
    SettlementStatus,
    TransactionRecord,
    WalletSnapshot,
)
from payments.policy import PaymentPolicy, PolicyDecision, PolicyLimits
from payments.provider import CirclePaymentProvider
from payments.providers import ProviderRegistry

logger = structlog.get_logger(__name__)

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

# Settlement outcome -> persisted transaction status.
_STATUS_FOR_SETTLEMENT: dict[SettlementStatus, PaymentStatus] = {
    SettlementStatus.SETTLED: PaymentStatus.SETTLED,
    SettlementStatus.FAILED: PaymentStatus.FAILED,
    SettlementStatus.PENDING: PaymentStatus.EXECUTED,
    SettlementStatus.NONE: PaymentStatus.EXECUTED,
}


def _coerce_block_number(value: object) -> int | None:
    """Parse a block number from Circle (int) or Arc JSON-RPC (`0x2a`)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 16) if value.startswith("0x") else int(value)
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
class EconomySummary:
    """Aggregate agent-economy stats (dashboard-ready)."""

    wallet: WalletSnapshot
    autonomous_payments: int
    usdc_settled: float
    arc_transactions: int
    receipts: int
    rejected_intents: int


@dataclass(frozen=True)
class DemoRun:
    """Result of the deterministic end-to-end demo scenario."""

    decisions: list[AgentDecision]
    transactions: list[TransactionRecord]
    summary: EconomySummary


@dataclass(frozen=True)
class PaymentServiceConfig:
    """Payment layer configuration (mirrors backend settings)."""

    fleet_id: str = "FLEET-017"
    currency: str = "USDC"
    daily_budget_usdc: float = 500.0
    max_tx_usdc: float = 250.0
    wallet_id: str = "fleet-agent-wallet-001"
    initial_balance_usdc: float = 1000.0
    # Real-mode settlement target. The catalog addresses are deterministic
    # placeholders, so PAYMENT_PROVIDER=real requires an operator-supplied
    # address that actually holds/ receives USDC on Arc. Empty in mock mode
    # (which pays the catalog address, as before).
    destination_address: str = ""
    # Optional per-provider destinations (provider_id -> 0x address). Falls
    # back to destination_address, then the catalog address in mock mode only.
    destination_addresses: dict[str, str] = field(default_factory=dict)


def demo_events() -> list[FleetEvent]:
    """The canonical demo story (deterministic — docs/payments.md §Demo).

    Three fleet events drive three autonomous payments:
        TRUCK-42  charging   (battery 18%)  -> VoltCharge   $18.00
        VAN-27    maintenance (scheduled)   -> AutoServiceX $62.00
        TRUCK-12  fueling    (low fuel)     -> PetroDirect  $95.00
    Total: $175.00 against a $500 daily budget.
    """
    return [
        FleetEvent(
            vehicle_id="TRUCK-42",
            event_type=EventType.CHARGING_REQUIRED,
            battery_pct=0.18,
            note="Battery below 20% threshold",
        ),
        FleetEvent(
            vehicle_id="VAN-27",
            event_type=EventType.MAINTENANCE_REQUIRED,
            battery_pct=0.62,
            note="Scheduled 50k km maintenance",
        ),
        FleetEvent(
            vehicle_id="TRUCK-12",
            event_type=EventType.FUELING_REQUIRED,
            battery_pct=1.0,
            note="Fuel below 25%",
        ),
    ]


class PaymentService:
    """Owns the agent, policy, provider, ledger, and wallet snapshot."""

    def __init__(
        self,
        config: PaymentServiceConfig | None = None,
        provider: CirclePaymentProvider | None = None,
        agent: FleetPaymentAgent | None = None,
        policy: PaymentPolicy | None = None,
    ) -> None:
        self._config = config or PaymentServiceConfig()
        self._registry = ProviderRegistry()
        self._agent = agent or FleetPaymentAgent(self._config.fleet_id)
        self._policy = policy or PaymentPolicy(
            PolicyLimits(
                daily_budget_usdc=self._config.daily_budget_usdc,
                max_tx_usdc=self._config.max_tx_usdc,
            )
        )
        self._provider = provider  # MockCircleProvider by default (factory)
        self._intents: dict[str, PaymentIntent] = {}
        self._transactions: dict[str, TransactionRecord] = {}
        self._receipts: dict[str, PaymentReceipt] = {}

    # ─── Accessors ───────────────────────────────────────────────────────

    @property
    def config(self) -> PaymentServiceConfig:
        """The active service configuration."""
        return self._config

    @property
    def registry(self) -> ProviderRegistry:
        """The deterministic provider catalog."""
        return self._registry

    @property
    def policy(self) -> PaymentPolicy:
        """The deterministic payment policy engine."""
        return self._policy

    @property
    def provider(self) -> CirclePaymentProvider | None:
        """The active wallet/settlement provider (None when disabled)."""
        return self._provider

    @property
    def is_mock(self) -> bool:
        """True only when the active provider is the in-process simulator."""
        return bool(getattr(self._provider, "is_mock", True))

    # ─── Flow ────────────────────────────────────────────────────────────

    def quote(self, event: FleetEvent) -> AgentDecision:
        """Agent observes a fleet event and returns a provider decision."""
        return self._agent.decide(event)

    def authorize(self, request: PaymentRequest) -> tuple[PaymentIntent, PolicyDecision]:
        """Policy-gate an agent payment request.

        Returns the stored PaymentIntent (AUTHORIZED or REJECTED) plus the
        PolicyDecision with per-check results. No wallet access happens here.
        """
        provider = self._registry.get(request.provider_id)
        wallet = self.wallet()
        effective_provider = (
            replace(provider, address=self._destination_for(provider))
            if provider is not None
            else None
        )
        decision = self._policy.validate(request, wallet, provider=effective_provider)
        intent = PaymentIntent(
            fleet_id=request.fleet_id or self._config.fleet_id,
            vehicle_id=request.vehicle_id,
            provider_id=request.provider_id,
            service=request.service,
            amount_usdc=round(request.amount_usdc, 2),
            currency=request.currency.upper(),
            reason=request.reason,
            max_allowed_usdc=round(request.max_allowed_usdc, 2) or self._config.max_tx_usdc,
            decision_rationale=request.decision_rationale,
            status=PaymentStatus.AUTHORIZED if decision.approved else PaymentStatus.REJECTED,
        )
        self._intents[intent.id] = intent
        logger.info(
            "payment_authorize",
            intent_id=intent.id,
            approved=decision.approved,
            amount_usdc=intent.amount_usdc,
            provider_id=intent.provider_id,
        )
        return intent, decision

    def execute(self, intent_id: str) -> TransactionRecord:
        """Execute an authorized intent: USDC transfer + Arc settlement.

        Returns a TransactionRecord whose status reflects what the provider
        actually reported:
            settled -> receipt created, intent settled
            pending -> submitted, receipt created once settlement confirms
            failed  -> on-chain failure recorded (no receipt)

        Raises KeyError for unknown intents and ValueError for non-authorized
        ones. Settlement failure is data, not an exception — it is persisted so
        the dashboard shows the failed payment instead of losing it.
        """
        intent = self._intents.get(intent_id)
        if intent is None:
            raise KeyError(f"intent {intent_id} not found")
        if intent.status != PaymentStatus.AUTHORIZED:
            raise ValueError(f"intent {intent_id} is {intent.status.value}, expected authorized")
        provider = self._registry.get(intent.provider_id)
        if provider is None:
            raise ValueError(f"provider {intent.provider_id} not found")
        if self._provider is None:
            raise RuntimeError("payment provider is disabled")

        # TOCTOU guard: re-validate against the CURRENT wallet at execution
        # time. The balance/budget may have changed since authorization (e.g.
        # other intents executed in between), so the policy runs again before
        # any USDC moves. The effective provider carries the real destination
        # address (not the catalog placeholder) so the address check is real.
        destination = self._destination_for(provider)
        effective_provider = replace(provider, address=destination)
        wallet = self.wallet()
        recheck = self._policy.validate(
            PaymentRequest(
                fleet_id=intent.fleet_id,
                vehicle_id=intent.vehicle_id,
                provider_id=intent.provider_id,
                service=intent.service,
                amount_usdc=intent.amount_usdc,
                currency=intent.currency,
                reason=intent.reason,
                max_allowed_usdc=intent.max_allowed_usdc,
            ),
            wallet,
            provider=effective_provider,
        )
        if not recheck.approved:
            raise ValueError(
                "payment no longer authorized at execution time: " + "; ".join(recheck.reasons)
            )

        memo = f"{intent.fleet_id}|{intent.vehicle_id}|{intent.provider_id}|{intent.service.value}"
        transfer = self._provider.transfer(
            to_address=destination,
            amount_usdc=intent.amount_usdc,
            memo=memo,
        )

        # Real Circle transfers are asynchronous and Circle does not return a
        # hash until the transaction reaches SENT/COMPLETE. A submitted
        # payment must never be lost because a follow-up poll failed, so
        # settlement errors are recorded on the transaction as data.
        settlement_error = ""
        status_info: dict[str, object] = {}
        settlement = transfer.settlement_status
        if transfer.tx_hash:
            try:
                settlement = self._provider.settle(transfer.tx_hash)
            except Exception as exc:  # noqa: BLE001 — record the submitted payment
                settlement_error = str(exc)
                logger.error(
                    "payment_settlement_check_failed",
                    tx_hash=transfer.tx_hash,
                    error=settlement_error,
                )
            try:
                status_info = self._provider.get_transaction_status(transfer.tx_hash)
            except Exception as exc:  # noqa: BLE001 — status is supplementary
                status_info = {}
                logger.warning(
                    "payment_status_check_failed",
                    tx_hash=transfer.tx_hash,
                    error=str(exc),
                )

        now = time.time()
        is_mock = bool(getattr(self._provider, "is_mock", False))
        if transfer.status == PaymentStatus.FAILED:
            status = PaymentStatus.FAILED
            settlement = SettlementStatus.FAILED
        else:
            status = _STATUS_FOR_SETTLEMENT.get(settlement, PaymentStatus.EXECUTED)
        explorer_url = ""
        if transfer.tx_hash:
            try:
                explorer_url = self._provider.explorer_url(transfer.tx_hash)
            except PaymentProviderConfigError as exc:
                logger.error(
                    "payment_explorer_unavailable", tx_hash=transfer.tx_hash, error=str(exc)
                )
        payload = transfer.provider_payload
        block_number = _coerce_block_number(
            status_info.get("block_number", payload.get("block_height"))
        )
        record = TransactionRecord(
            intent_id=intent.id,
            fleet_id=intent.fleet_id,
            vehicle_id=intent.vehicle_id,
            provider_id=intent.provider_id,
            provider_name=provider.name,
            provider_address=destination,
            service=intent.service,
            amount_usdc=intent.amount_usdc,
            currency=intent.currency,
            status=status,
            settlement_status=settlement,
            tx_hash=transfer.tx_hash,
            reason=intent.reason,
            decision_rationale=intent.decision_rationale,
            explorer_url=explorer_url,
            is_mock=is_mock,
            provider_transaction_id=str(payload.get("circle_transaction_id") or ""),
            provider_status=str(payload.get("circle_state") or ""),
            error_reason=(
                str(payload.get("error_reason") or "")
                or settlement_error
                or str(status_info.get("error_reason") or "")
            ),
            block_number=block_number,
            chain_id=str(payload.get("chain_id") or getattr(self._provider, "chain_id", "")),
            created_at=intent.created_at,
            executed_at=now,
            settled_at=now if settlement == SettlementStatus.SETTLED else None,
        )
        self._transactions[record.id] = record
        intent.status = status

        if settlement == SettlementStatus.SETTLED:
            receipt = self._create_receipt(record, now)
            logger.info(
                "payment_settled",
                tx_hash=record.tx_hash,
                amount_usdc=record.amount_usdc,
                provider_id=record.provider_id,
                vehicle_id=record.vehicle_id,
                network=receipt.network,
                mock=is_mock,
            )
        elif settlement == SettlementStatus.FAILED:
            logger.error(
                "payment_settlement_failed",
                tx_hash=record.tx_hash,
                amount_usdc=record.amount_usdc,
                provider_id=record.provider_id,
                mock=is_mock,
            )
        else:
            logger.warning(
                "payment_settlement_pending",
                tx_hash=record.tx_hash,
                amount_usdc=record.amount_usdc,
                mock=is_mock,
            )
        return record

    def reconcile(self, transaction_id: str) -> TransactionRecord | None:
        """Refresh one in-memory transaction from the provider.

        Returns None when the transaction is not in the process ledger; the
        backend uses `reconcile_record` for records loaded from the database
        after a restart.
        """
        record = self._transactions.get(transaction_id)
        if record is None:
            return None
        return self.reconcile_record(record)

    def reconcile_record(self, record: TransactionRecord) -> TransactionRecord:
        """Poll the provider and apply any reconciliation data to `record`.

        Real Circle transfers are asynchronous: a transaction can be accepted
        before Circle exposes its Arc hash. This method is the explicit,
        user-triggered path that closes that gap. It only records what Circle
        and Arc actually report — an unknown state stays PENDING (Law 1).
        """
        if self._provider is None:
            return record

        refresh = getattr(self._provider, "refresh_transaction", None)
        if record.provider_transaction_id and callable(refresh):
            info = refresh(record.provider_transaction_id)
            record.provider_status = str(info.get("state") or record.provider_status)
            new_hash = str(info.get("tx_hash") or "")
            if new_hash and not record.tx_hash:
                record.tx_hash = new_hash
            block_number = _coerce_block_number(info.get("block_number"))
            if block_number is not None:
                record.block_number = block_number
            error_reason = str(info.get("error_reason") or "")
            if error_reason:
                record.error_reason = error_reason
            if info.get("failed"):
                record.status = PaymentStatus.FAILED
                record.settlement_status = SettlementStatus.FAILED
                logger.error(
                    "payment_reconcile_failed",
                    transaction_id=record.id,
                    provider_transaction_id=record.provider_transaction_id,
                    provider_status=record.provider_status,
                    error_reason=record.error_reason,
                )
                return record

        if not record.tx_hash:
            return record

        now = time.time()
        try:
            settlement = self._provider.settle(record.tx_hash)
        except Exception as exc:  # noqa: BLE001 — keep the submitted payment
            record.error_reason = record.error_reason or str(exc)
            logger.error(
                "payment_reconcile_settlement_failed",
                transaction_id=record.id,
                tx_hash=record.tx_hash,
                error=str(exc),
            )
            return record

        record.settlement_status = settlement
        record.status = _STATUS_FOR_SETTLEMENT.get(settlement, PaymentStatus.EXECUTED)
        if record.status == PaymentStatus.SETTLED:
            if record.settled_at is None:
                record.settled_at = now
            self._create_receipt(record, now)
        elif record.status == PaymentStatus.FAILED:
            record.error_reason = record.error_reason or "Arc transaction reverted"
        try:
            status_info = self._provider.get_transaction_status(record.tx_hash)
        except Exception as exc:  # noqa: BLE001 — status is supplementary
            logger.warning(
                "payment_reconcile_status_failed",
                tx_hash=record.tx_hash,
                error=str(exc),
            )
            status_info = {}
        block_number = _coerce_block_number(status_info.get("block_number"))
        if block_number is not None:
            record.block_number = block_number
        if not record.explorer_url:
            try:
                record.explorer_url = self._provider.explorer_url(record.tx_hash)
            except PaymentProviderConfigError:
                pass
        logger.info(
            "payment_reconciled",
            transaction_id=record.id,
            tx_hash=record.tx_hash,
            status=record.status.value,
            settlement=record.settlement_status.value,
        )
        return record

    # ─── Ledger / wallet ─────────────────────────────────────────────────

    def get_transaction(self, transaction_id: str) -> TransactionRecord | None:
        """Look up a transaction by id."""
        return self._transactions.get(transaction_id)

    def list_transactions(self, limit: int = 100) -> list[TransactionRecord]:
        """All transactions, newest first."""
        records = sorted(
            self._transactions.values(), key=lambda record: record.created_at, reverse=True
        )
        return records[:limit]

    def _create_receipt(self, record: TransactionRecord, now: float) -> PaymentReceipt:
        """Build and store a verifiable receipt for a settled transaction."""
        import uuid

        receipt = PaymentReceipt(
            receipt_id=str(uuid.uuid4()),
            transaction_id=record.id,
            tx_hash=record.tx_hash,
            fleet_id=record.fleet_id,
            vehicle_id=record.vehicle_id,
            provider_id=record.provider_id,
            service=record.service,
            amount_usdc=record.amount_usdc,
            currency=record.currency,
            network=str(getattr(self._provider, "network", "arc-mock")),
            explorer_url=record.explorer_url,
            settled_at=now,
            is_mock=record.is_mock,
        )
        self._receipts[record.id] = receipt
        return receipt

    def get_receipt(self, transaction_id: str) -> PaymentReceipt | None:
        """The receipt for a settled transaction."""
        return self._receipts.get(transaction_id)

    def wallet(self) -> WalletSnapshot:
        """Current agent wallet snapshot (balance + limits + today's spend)."""
        spent = round(
            sum(
                record.amount_usdc
                for record in self._transactions.values()
                if record.status in (PaymentStatus.EXECUTED, PaymentStatus.SETTLED)
            ),
            2,
        )
        balance = (
            round(self._provider.wallet_balance(), 2)
            if self._provider is not None
            else self._config.initial_balance_usdc
        )
        return WalletSnapshot(
            wallet_id=self._config.wallet_id,
            currency=self._config.currency,
            balance_usdc=balance,
            daily_budget_usdc=self._config.daily_budget_usdc,
            spent_today_usdc=spent,
            remaining_today_usdc=round(max(0.0, self._config.daily_budget_usdc - spent), 2),
            max_tx_usdc=self._config.max_tx_usdc,
            is_mock=bool(getattr(self._provider, "is_mock", True)),
            network=(
                str(getattr(self._provider, "network", "arc-mock"))
                if self._provider is not None
                else "disabled"
            ),
            wallet_address=str(getattr(self._provider, "wallet_address", "")),
        )

    def summary(self) -> EconomySummary:
        """Aggregate agent-economy stats for the dashboard."""
        wallet = self.wallet()
        return EconomySummary(
            wallet=wallet,
            autonomous_payments=len(self._transactions),
            usdc_settled=round(
                sum(
                    record.amount_usdc
                    for record in self._transactions.values()
                    if record.settlement_status == SettlementStatus.SETTLED
                ),
                2,
            ),
            arc_transactions=len(self._transactions),
            receipts=len(self._receipts),
            rejected_intents=sum(
                1 for intent in self._intents.values() if intent.status == PaymentStatus.REJECTED
            ),
        )

    # ─── Demo scenario ───────────────────────────────────────────────────

    def run_demo_scenario(self, *, reset: bool = True) -> DemoRun:
        """Run the deterministic end-to-end demo story.

        With `reset=True` (default) the in-memory mock wallet and ledger are
        re-created first, so each demo run is a clean story: 3 fleet events,
        3 agent decisions, 3 policy approvals, 3 settled USDC payments
        ($175.00 total against the $500 daily budget).

        A live (real USDC) service refuses to run this scenario: resetting a
        real provider would silently replace it with a mock and misrepresent
        live money (Law 1).
        """
        if reset:
            self._reset_for_demo()
        decisions: list[AgentDecision] = []
        records: list[TransactionRecord] = []
        for event in demo_events():
            decision = self.quote(event)
            decisions.append(decision)
            if decision.no_action or decision.selected is None:
                continue
            request = PaymentRequest(
                fleet_id=self._config.fleet_id,
                vehicle_id=decision.vehicle_id,
                provider_id=decision.selected_provider_id,
                service=decision.service,
                amount_usdc=decision.amount_usdc,
                reason=(f"{decision.service.value} required (battery {event.battery_pct:.0%})"),
                max_allowed_usdc=self._config.max_tx_usdc,
                decision_rationale=decision.rationale,
            )
            intent, policy_decision = self.authorize(request)
            if policy_decision.approved:
                records.append(self.execute(intent.id))
        return DemoRun(
            decisions=decisions,
            transactions=records,
            summary=self.summary(),
        )

    # ─── Internals ───────────────────────────────────────────────────────

    def _reset_for_demo(self) -> None:
        """Reset the in-memory mock provider/ledger so a demo starts clean."""
        from payments.factory import create_payment_provider

        if self._provider is not None and not getattr(self._provider, "is_mock", True):
            raise RuntimeError(
                "the deterministic demo scenario is mock-only and cannot reset a live USDC provider"
            )
        self._provider = create_payment_provider(
            "mock",
            wallet_id=self._config.wallet_id,
            initial_balance_usdc=self._config.initial_balance_usdc,
        )
        self._intents.clear()
        self._transactions.clear()
        self._receipts.clear()
        logger.info("payment_demo_reset", wallet_id=self._config.wallet_id)

    def _destination_for(self, provider: Provider) -> str:
        """Resolve the real/effective destination for a provider.

        Real mode must never pay a deterministic catalog placeholder: it uses
        a provider-specific mapping, then the global destination. Mock mode
        keeps the catalog address so the existing demo is unchanged.
        """
        destination = (
            self._config.destination_addresses.get(provider.provider_id)
            or self._config.destination_address
        )
        if destination:
            if not _ADDRESS_RE.match(destination):
                raise ValueError(f"invalid destination address for {provider.provider_id}")
            return destination
        if not self.is_mock:
            raise PaymentProviderConfigError(
                f"PAYMENT_PROVIDER=real has no destination for provider "
                f"{provider.provider_id!r}; set PAYMENT_DESTINATION_ADDRESSES or "
                f"PAYMENT_DESTINATION_ADDRESS"
            )
        return provider.address
