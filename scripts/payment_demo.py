#!/usr/bin/env python3
"""FleetPay Agent demo — full agentic payment loop in the terminal.

Run with: make payment-demo   (or: python scripts/payment_demo.py)

Story (docs/payments.md §Demo):
    Human: "Keep Fleet #17 operational under a $500 budget."
    Fleet event -> agent observes -> evaluates 3 providers -> decides
    -> PaymentIntent -> PaymentPolicy approves -> USDC transfer (mock Circle)
    -> Arc settlement (mock) -> receipt -> daily budget updated

MOCK / DEMO ONLY: no real USDC moves, no real on-chain transactions. Every
transaction hash is a 0xMOCK... hash and every receipt is flagged is_mock.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from payments.factory import create_payment_provider  # noqa: E402
from payments.service import PaymentService, PaymentServiceConfig  # noqa: E402

HEADER = "=" * 78
SUB = "-" * 78


def main() -> int:
    provider = create_payment_provider("mock")
    assert provider is not None, "mock provider must always be available"
    service = PaymentService(PaymentServiceConfig(), provider)

    print(HEADER)
    print("  FleetPay Agent — Autonomous Fleet Intelligence & USDC Payments on Arc")
    print("  MOCK / DEMO MODE — no real USDC moves, no on-chain transactions")
    print(HEADER)
    print()
    print('  Human: "Keep Fleet #17 operational under a $500 budget."')
    print()

    result = service.run_demo_scenario(reset=True)

    for decision in result.decisions:
        print(SUB)
        print(f"  EVENT  Fleet #17  {decision.vehicle_id}  needs {decision.service.value}")
        if decision.no_action:
            print(f"  AGENT  no action: {decision.rationale}")
            continue
        print()
        print("  AGENT  evaluating providers (price / distance / rating / score):")
        for quote in decision.quotes:
            marker = "->" if quote.provider.provider_id == decision.selected_provider_id else "  "
            print(
                f"    {marker} {quote.provider.name:<18} "
                f"${quote.provider.price_usdc:>7.2f}  "
                f"{quote.provider.distance_km:>4.1f} km  "
                f"{quote.provider.rating:>4.1f}  score {quote.score:>6.2f}"
            )
        print()
        print(
            f"  AGENT  selected {decision.selected_provider_id} at ${decision.amount_usdc:.2f} USDC"
        )
        print(f"         {decision.rationale}")

    print(SUB)
    print("  POLICY  deterministic gatekeeper — budget, max-tx, address checks")
    print()

    for record in result.transactions:
        print("  PAYMENT  ------------------------------------------------")
        print(f"    vehicle     {record.vehicle_id}")
        print(f"    provider    {record.provider_name} ({record.provider_id})")
        print(f"    service     {record.service.value}")
        print(f"    amount      ${record.amount_usdc:.2f} USDC")
        print(f"    wallet      {record.fleet_id} agent wallet (mock Circle)")
        print(f"    arc tx      {record.tx_hash}")
        print(f"    status      {record.status.value} / {record.settlement_status.value}")
        print(f"    receipt     {record.receipt_id}  (is_mock={record.is_mock})")
        print(f"    explorer    {record.explorer_url}")

    wallet = result.summary.wallet
    print(SUB)
    print("  TODAY'S AGENT ECONOMY")
    print(f"    Budget             ${wallet.daily_budget_usdc:.2f}")
    print(f"    Spent              ${wallet.spent_today_usdc:.2f}")
    print(f"    Remaining          ${wallet.remaining_today_usdc:.2f}")
    print(f"    Autonomous payments  {result.summary.autonomous_payments}")
    print(f"    USDC settled        ${result.summary.usdc_settled:.2f}")
    print(f"    Arc transactions     {result.summary.arc_transactions}")
    print(f"    Receipts            {result.summary.receipts}")
    print(HEADER)
    print("  Next: run `make demo` and open the dashboard -> FleetPay Agent panel")
    print("  for the same story with a live UI (MOCK-labeled transaction hashes).")
    print(HEADER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
