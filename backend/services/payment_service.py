"""PaymentAppState — backend facade over the agentic payment domain layer.

Wraps payments.service.PaymentService with SQLite persistence and
serialization to API schemas. The database is the source of truth for reads
(wallet spend, history, summary), so the dashboard shows the same numbers
after a restart as it did live. Provider I/O (real Circle/Arc) runs through
`asyncio.to_thread` so the event loop never blocks on the network.

Status: COMPLETE — mock provider (MOCK/DEMO labeled) and real Circle/Arc
settlement (PAYMENT_PROVIDER=real, docs/payments.md).
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, cast

import structlog
from sqlalchemy import delete, desc, func, select

from backend.config import Settings
from backend.db.database import Database
from backend.db.models import PaymentRecord
from backend.schemas import (
    AgentDecisionResponse,
    PaymentAuthorizeRequest,
    PaymentAuthorizeResponse,
    PaymentDemoResponse,
    PaymentSummaryResponse,
    PaymentTransactionResponse,
    PaymentWalletResponse,
    ProviderQuoteResponse,
)
from payments.errors import PaymentProviderConfigError
from payments.factory import create_payment_provider
from payments.models import (
    AgentDecision,
    EventType,
    FleetEvent,
    PaymentRequest,
    PaymentStatus,
    ServiceType,
    SettlementStatus,
    TransactionRecord,
)
from payments.service import PaymentService, PaymentServiceConfig

logger = structlog.get_logger(__name__)

_EVENT_TYPES = {event.value: event for event in EventType}
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_DEMO_LEDGER_LIMIT = 10_000


def _enum_or(enum_cls: type, raw: str, fallback: object) -> object:
    """Parse a persisted enum value, falling back instead of crashing reads."""
    try:
        return enum_cls(raw)
    except (ValueError, KeyError):
        return fallback


def _record_from_db(row: PaymentRecord) -> TransactionRecord:
    """Map a persisted PaymentRecord back to the domain transaction type."""

    def _ts(value: datetime | None) -> float | None:
        return value.timestamp() if value is not None else None

    return TransactionRecord(
        id=row.id,
        intent_id=row.intent_id,
        fleet_id=row.fleet_id,
        vehicle_id=row.vehicle_id,
        provider_id=row.provider_id,
        provider_name=row.provider_name,
        provider_address=row.provider_address,
        service=_enum_or(ServiceType, row.service, ServiceType.CHARGING),  # type: ignore[arg-type]
        amount_usdc=row.amount_usdc,
        currency=row.currency,
        status=_enum_or(PaymentStatus, row.status, PaymentStatus.EXECUTED),  # type: ignore[arg-type]
        settlement_status=_enum_or(  # type: ignore[arg-type]
            SettlementStatus, row.settlement_status, SettlementStatus.PENDING
        ),
        tx_hash=row.tx_hash,
        receipt_id=row.receipt_id,
        reason=row.reason,
        decision_rationale=row.decision_rationale,
        explorer_url=row.explorer_url,
        is_mock=row.is_mock,
        created_at=row.created_at.timestamp(),
        executed_at=_ts(row.executed_at),
        settled_at=_ts(row.settled_at),
    )


class PaymentAppState:
    """Application-level agentic payment singleton."""

    def __init__(self, db: Database, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        provider = create_payment_provider(
            settings.payment_provider,
            wallet_id=settings.payment_wallet_id,
            initial_balance_usdc=settings.payment_wallet_initial_balance_usdc,
            circle_api_key=settings.circle_api_key,
            circle_entity_secret=settings.circle_entity_secret,
            circle_token_id=settings.circle_token_id,
            circle_wallet_set_id=settings.circle_wallet_set_id,
            arc_rpc_url=settings.arc_rpc_url,
            arc_chain_id=settings.arc_chain_id,
            arc_explorer_url=settings.arc_explorer_url,
            arc_contract_address=settings.arc_contract_address,
        )
        if provider is None:
            raise ValueError(
                "PAYMENT_PROVIDER=disabled is not supported at startup — set it to "
                "'mock' (default) or 'real'."
            )
        if settings.payment_provider == "real":
            # Real USDC must not be sent to a deterministic catalog placeholder.
            if not _ADDRESS_RE.match(settings.payment_destination_address or ""):
                raise PaymentProviderConfigError(
                    "PAYMENT_PROVIDER=real requires PAYMENT_DESTINATION_ADDRESS "
                    "(0x + 40 hex) — the Arc wallet that receives settlements. "
                    "See docs/payments.md §Configuration."
                )
        config = PaymentServiceConfig(
            fleet_id=settings.payment_fleet_id,
            currency=settings.payment_currency,
            daily_budget_usdc=settings.payment_daily_budget_usdc,
            max_tx_usdc=settings.payment_max_tx_usdc,
            wallet_id=settings.payment_wallet_id,
            initial_balance_usdc=settings.payment_wallet_initial_balance_usdc,
            destination_address=settings.payment_destination_address,
        )
        self._core = PaymentService(config=config, provider=provider)
        logger.info(
            "payment_app_state_initialized",
            mode=settings.payment_provider,
            wallet_id=settings.payment_wallet_id,
            network=getattr(provider, "network", "unknown"),
            daily_budget_usdc=settings.payment_daily_budget_usdc,
            live_bridge=settings.payment_live_bridge,
        )

    @property
    def core(self) -> PaymentService:
        """The underlying domain PaymentService."""
        return self._core

    # ─── Quote / authorize / execute ─────────────────────────────────────

    def quote(
        self,
        *,
        vehicle_id: str,
        event_type: str,
        battery_pct: float,
        note: str,
    ) -> AgentDecisionResponse:
        """Agent observes a fleet event and returns a provider decision."""
        event_type_enum = self._require_event_type(event_type)
        decision = self._core.quote(
            FleetEvent(
                vehicle_id=vehicle_id,
                event_type=event_type_enum,
                battery_pct=battery_pct,
                note=note,
            )
        )
        return self._serialize_decision(decision)

    def authorize(self, body: PaymentAuthorizeRequest) -> PaymentAuthorizeResponse:
        """Policy-gate a payment request. No wallet access here."""
        request = PaymentRequest(
            fleet_id=body.fleet_id,
            vehicle_id=body.vehicle_id,
            provider_id=body.provider_id,
            service=ServiceType(body.service),
            amount_usdc=body.amount_usdc,
            currency=body.currency,
            reason=body.reason,
            # Unset max_allowed defaults to the configured max-tx limit so an
            # omitted field is not rejected by the policy (rejections come
            # from real violations, not from a missing optional field).
            max_allowed_usdc=body.max_allowed_usdc or self._settings.payment_max_tx_usdc,
            decision_rationale=body.decision_rationale,
        )
        intent, decision = self._core.authorize(request)
        return PaymentAuthorizeResponse(
            intent_id=intent.id,
            approved=decision.approved,
            checks=decision.checks,
            reasons=decision.reasons,
        )

    async def execute(self, intent_id: str) -> PaymentTransactionResponse:
        """Execute an authorized intent (off-loop) and persist the outcome."""
        record = await asyncio.to_thread(self._core.execute, intent_id)
        await self._persist(record)
        return self._serialize_transaction(record)

    # ─── Reads (database is the source of truth) ─────────────────────────

    async def get_transaction(self, transaction_id: str) -> PaymentTransactionResponse | None:
        """Look up a transaction by id (persisted first, then in-memory)."""
        row = await self._get_record(transaction_id)
        if row is not None:
            return self._serialize_transaction(_record_from_db(row))
        record = self._core.get_transaction(transaction_id)
        if record is None:
            return None
        return self._serialize_transaction(record)

    async def list_transactions(self, limit: int = 100) -> list[PaymentTransactionResponse]:
        """Agent transaction history from the database, newest first."""
        rows = await self._fetch_records(limit=limit)
        if rows is not None:
            return [self._serialize_transaction(_record_from_db(row)) for row in rows]
        # DB unavailable — fall back to the in-process ledger rather than 500.
        return [
            self._serialize_transaction(record)
            for record in self._core.list_transactions(limit=limit)
        ]

    async def wallet(self) -> PaymentWalletResponse:
        """Agent wallet snapshot (real balance via provider, spend via DB)."""
        snapshot = await asyncio.to_thread(self._core.wallet)
        spent = await self._spent_today_usdc()
        if spent is None:
            spent = snapshot.spent_today_usdc
        daily = self._settings.payment_daily_budget_usdc
        return PaymentWalletResponse(
            wallet_id=snapshot.wallet_id,
            currency=snapshot.currency,
            balance_usdc=snapshot.balance_usdc,
            daily_budget_usdc=daily,
            spent_today_usdc=spent,
            remaining_today_usdc=round(max(0.0, daily - spent), 2),
            max_tx_usdc=snapshot.max_tx_usdc,
            is_mock=snapshot.is_mock,
            network=snapshot.network,
        )

    async def summary(self) -> PaymentSummaryResponse:
        """Aggregate agent-economy stats computed from persisted payments."""
        wallet = await self.wallet()
        rows = await self._fetch_records(limit=_DEMO_LEDGER_LIMIT)
        if rows is None:
            core = self._core.summary()
            return PaymentSummaryResponse(
                wallet=wallet,
                autonomous_payments=core.autonomous_payments,
                usdc_settled=core.usdc_settled,
                arc_transactions=core.arc_transactions,
                receipts=core.receipts,
                rejected_intents=core.rejected_intents,
            )
        return PaymentSummaryResponse(
            wallet=wallet,
            autonomous_payments=len(rows),
            usdc_settled=round(
                sum(
                    row.amount_usdc
                    for row in rows
                    if row.settlement_status == SettlementStatus.SETTLED.value
                ),
                2,
            ),
            arc_transactions=len(rows),
            receipts=sum(1 for row in rows if row.receipt_id),
            rejected_intents=self._core.summary().rejected_intents,
        )

    async def run_demo(self) -> PaymentDemoResponse:
        """Run the deterministic demo story.

        POST /payments/demo is an explicit reset: it clears the persisted
        ledger (documented in docs/payments.md §API) so every run tells the
        same clean 3-event / $175 story, then persists the new transactions.
        """
        await self._clear_payments()
        result = await asyncio.to_thread(self._core.run_demo_scenario, reset=True)
        for record in result.transactions:
            await self._persist(record)
        return PaymentDemoResponse(
            decisions=[self._serialize_decision(d) for d in result.decisions],
            transactions=[self._serialize_transaction(t) for t in result.transactions],
            summary=await self.summary(),
        )

    # ─── Persistence helpers ─────────────────────────────────────────────

    async def _persist(self, record: TransactionRecord) -> None:
        """Write an executed transaction to the payments table."""
        db_record = PaymentRecord(
            id=record.id,
            intent_id=record.intent_id,
            fleet_id=record.fleet_id,
            vehicle_id=record.vehicle_id,
            provider_id=record.provider_id,
            provider_name=record.provider_name,
            provider_address=record.provider_address,
            service=record.service.value,
            amount_usdc=record.amount_usdc,
            currency=record.currency,
            status=record.status.value,
            settlement_status=record.settlement_status.value,
            tx_hash=record.tx_hash,
            receipt_id=record.receipt_id,
            reason=record.reason,
            decision_rationale=record.decision_rationale,
            explorer_url=record.explorer_url,
            is_mock=record.is_mock,
            created_at=datetime.fromtimestamp(record.created_at, tz=timezone.utc),
            executed_at=(
                datetime.fromtimestamp(record.executed_at, tz=timezone.utc)
                if record.executed_at is not None
                else None
            ),
            settled_at=(
                datetime.fromtimestamp(record.settled_at, tz=timezone.utc)
                if record.settled_at is not None
                else None
            ),
        )
        async with self._db.session() as session:
            session.add(db_record)
            await session.commit()

    async def _fetch_records(self, limit: int) -> list[PaymentRecord] | None:
        """Persisted transactions newest-first, or None when the DB is unusable."""
        try:
            async with self._db.session() as session:
                result = await session.execute(
                    select(PaymentRecord)
                    .order_by(desc(cast(Any, PaymentRecord.created_at)))
                    .limit(limit)
                )
                return list(result.scalars().all())
        except Exception as exc:  # noqa: BLE001 — reads must not take the API down
            logger.error("payment_db_read_failed", operation="fetch_records", error=str(exc))
            return None

    async def _get_record(self, transaction_id: str) -> PaymentRecord | None:
        """One persisted transaction by id, or None."""
        try:
            async with self._db.session() as result_session:
                result = await result_session.execute(
                    select(PaymentRecord).where(PaymentRecord.id == transaction_id)  # type: ignore[arg-type]
                )
                return result.scalars().first()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "payment_db_read_failed",
                operation="get_record",
                transaction_id=transaction_id,
                error=str(exc),
            )
            return None

    async def _spent_today_usdc(self) -> float | None:
        """Sum of persisted transaction amounts, or None when unavailable."""
        try:
            async with self._db.session() as session:
                result = await session.execute(
                    select(func.coalesce(func.sum(PaymentRecord.amount_usdc), 0.0))
                )
                total = result.scalar_one()
            return round(float(total), 2)
        except Exception as exc:  # noqa: BLE001
            logger.error("payment_db_read_failed", operation="spent_total", error=str(exc))
            return None

    async def _clear_payments(self) -> None:
        """Delete every persisted payment (demo-reset semantics)."""
        async with self._db.session() as session:
            await session.execute(delete(PaymentRecord))
            await session.commit()

    # ─── Serializers ─────────────────────────────────────────────────────

    @classmethod
    def _serialize_decision(cls, decision: AgentDecision) -> AgentDecisionResponse:
        return AgentDecisionResponse(
            fleet_id=decision.fleet_id,
            vehicle_id=decision.vehicle_id,
            service=decision.service.value,
            amount_usdc=decision.amount_usdc,
            rationale=decision.rationale,
            no_action=decision.no_action,
            selected_provider_id=decision.selected_provider_id,
            quotes=[
                ProviderQuoteResponse(
                    provider_id=quote.provider.provider_id,
                    name=quote.provider.name,
                    service=quote.provider.service.value,
                    price_usdc=quote.provider.price_usdc,
                    distance_km=quote.provider.distance_km,
                    rating=quote.provider.rating,
                    address=quote.provider.address,
                    score=quote.score,
                    selected=quote.provider.provider_id == decision.selected_provider_id,
                )
                for quote in decision.quotes
            ],
        )

    @staticmethod
    def _serialize_transaction(record: TransactionRecord) -> PaymentTransactionResponse:
        return PaymentTransactionResponse(
            id=record.id,
            intent_id=record.intent_id,
            fleet_id=record.fleet_id,
            vehicle_id=record.vehicle_id,
            provider_id=record.provider_id,
            provider_name=record.provider_name,
            provider_address=record.provider_address,
            service=record.service.value,
            amount_usdc=record.amount_usdc,
            currency=record.currency,
            status=record.status.value,
            settlement_status=record.settlement_status.value,
            tx_hash=record.tx_hash,
            receipt_id=record.receipt_id,
            reason=record.reason,
            decision_rationale=record.decision_rationale,
            explorer_url=record.explorer_url,
            is_mock=record.is_mock,
            created_at=record.created_at,
            executed_at=record.executed_at,
            settled_at=record.settled_at,
        )

    @staticmethod
    def _require_event_type(raw: str) -> EventType:
        """Map a raw event_type string to an EventType, else raise ValueError."""
        try:
            return _EVENT_TYPES[raw]
        except KeyError:
            raise ValueError(
                f"unknown event_type {raw!r} — expected one of: {', '.join(sorted(_EVENT_TYPES))}"
            ) from None
