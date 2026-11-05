"""Payments router — agentic payment API (Arc + Circle USDC).

Endpoints (docs/payments.md §API):
    POST /api/v1/payments/quote        agent observes a fleet event -> decision
    POST /api/v1/payments/authorize    policy-gate a payment request (no wallet)
    POST /api/v1/payments/execute      execute an authorized intent (USDC -> Arc)
    POST /api/v1/payments/demo         deterministic end-to-end demo scenario
    GET  /api/v1/payments/wallet       agent wallet + daily budget
    GET  /api/v1/payments/transactions agent transaction history
    GET  /api/v1/payments/{id}         single transaction

All mutating endpoints require the X-Fleet-API-Key header. In the default
mock mode every transaction is explicitly MOCK/DEMO (0xMOCK... hashes) —
nothing here claims to be on-chain (spec §12).
"""

from typing import cast

from fastapi import APIRouter, HTTPException, Request

from backend.schemas import (
    AgentDecisionResponse,
    PaymentAuthorizeRequest,
    PaymentAuthorizeResponse,
    PaymentDemoResponse,
    PaymentEventRequest,
    PaymentExecuteRequest,
    PaymentSummaryResponse,
    PaymentTransactionResponse,
    PaymentWalletResponse,
)
from backend.security import require_api_key
from backend.services.payment_service import PaymentAppState

router = APIRouter(prefix="/payments", tags=["payments"])


def _payments(request: Request) -> PaymentAppState:
    """Resolve the payment app state from request context."""
    return cast(PaymentAppState, request.app.state.payments)


@router.post("/quote", response_model=AgentDecisionResponse)
async def payment_quote(body: PaymentEventRequest, request: Request) -> AgentDecisionResponse:
    """The fleet agent evaluates providers for a fleet event."""
    require_api_key(request)
    try:
        return _payments(request).quote(
            vehicle_id=body.vehicle_id,
            event_type=body.event_type,
            battery_pct=body.battery_pct,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/authorize", response_model=PaymentAuthorizeResponse)
async def payment_authorize(
    body: PaymentAuthorizeRequest, request: Request
) -> PaymentAuthorizeResponse:
    """Policy-gate an agent-generated payment request (no wallet access)."""
    require_api_key(request)
    try:
        return _payments(request).authorize(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/execute", response_model=PaymentTransactionResponse)
async def payment_execute(
    body: PaymentExecuteRequest, request: Request
) -> PaymentTransactionResponse:
    """Execute an authorized intent: USDC transfer + Arc settlement."""
    require_api_key(request)
    try:
        return await _payments(request).execute(body.intent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/demo", response_model=PaymentDemoResponse)
async def payment_demo(request: Request) -> PaymentDemoResponse:
    """Run the deterministic end-to-end demo scenario (resets demo wallet)."""
    require_api_key(request)
    return await _payments(request).run_demo()


@router.get("/wallet", response_model=PaymentWalletResponse)
async def payment_wallet(request: Request) -> PaymentWalletResponse:
    """Agent wallet snapshot: balance, daily budget, spent, remaining."""
    return await _payments(request).wallet()


@router.get("/transactions", response_model=list[PaymentTransactionResponse])
async def payment_transactions(request: Request) -> list[PaymentTransactionResponse]:
    """Agent transaction history (newest first)."""
    return await _payments(request).list_transactions()


@router.get("/summary", response_model=PaymentSummaryResponse)
async def payment_summary(request: Request) -> PaymentSummaryResponse:
    """Aggregate agent-economy stats for the dashboard."""
    return await _payments(request).summary()


@router.get("/{transaction_id}", response_model=PaymentTransactionResponse)
async def payment_transaction(transaction_id: str, request: Request) -> PaymentTransactionResponse:
    """A single transaction by id."""
    transaction = await _payments(request).get_transaction(transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail=f"transaction {transaction_id} not found")
    return transaction
