"""Payments API integration tests — agentic payment layer (Arc + Circle USDC).

Covers quote / authorize / execute / demo / wallet / transactions endpoints,
API-key enforcement, mock-labeled transaction data, and DB persistence.

Status: COMPLETE (mock provider — all hashes are 0xMOCK... demo hashes).
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app

API_KEY = "dev-only-key"
HEADERS = {"X-Fleet-API-Key": API_KEY}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """A TestClient wired to a throwaway SQLite DB + local artifact store."""
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/payments.db",
        artifact_dir=tmp_path / "artifacts",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


QUOTE_BODY = {
    "vehicle_id": "TRUCK-42",
    "event_type": "charging_required",
    "battery_pct": 0.18,
    "note": "Battery below 20% threshold",
}


class TestPaymentQuote:
    def test_quote_requires_api_key(self, client: TestClient) -> None:
        response = client.post("/api/v1/payments/quote", json=QUOTE_BODY)
        assert response.status_code == 401

    def test_quote_returns_decision_with_three_quotes(self, client: TestClient) -> None:
        response = client.post("/api/v1/payments/quote", json=QUOTE_BODY, headers=HEADERS)
        assert response.status_code == 200
        body = response.json()
        assert body["vehicle_id"] == "TRUCK-42"
        assert body["service"] == "charging"
        assert body["no_action"] is False
        assert len(body["quotes"]) == 3
        selected = [quote for quote in body["quotes"] if quote["selected"]]
        assert len(selected) == 1
        assert selected[0]["provider_id"] == "prov_charge_a"
        assert selected[0]["price_usdc"] == 18.0

    def test_quote_unknown_event_type_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/payments/quote",
            json={**QUOTE_BODY, "event_type": "explosion"},
            headers=HEADERS,
        )
        assert response.status_code == 422

    def test_quote_no_action_above_threshold(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/payments/quote",
            json={**QUOTE_BODY, "battery_pct": 0.80},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["no_action"] is True


class TestPaymentAuthorize:
    def test_authorize_requires_api_key(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/payments/authorize",
            json={
                "vehicle_id": "TRUCK-42",
                "provider_id": "prov_charge_a",
                "service": "charging",
                "amount_usdc": 18.0,
                "reason": "low battery",
            },
        )
        assert response.status_code == 401

    def test_authorize_approves_valid_request(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/payments/authorize",
            json={
                "vehicle_id": "TRUCK-42",
                "provider_id": "prov_charge_a",
                "service": "charging",
                "amount_usdc": 18.0,
                "reason": "low battery",
                "max_allowed_usdc": 250.0,
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["approved"] is True
        assert body["checks"]["provider_address"] is True
        assert body["intent_id"]

    def test_authorize_rejects_over_budget(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/payments/authorize",
            json={
                "vehicle_id": "TRUCK-42",
                "provider_id": "prov_charge_a",
                "service": "charging",
                "amount_usdc": 600.0,
                "reason": "over budget",
                "max_allowed_usdc": 250.0,
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["approved"] is False
        assert body["checks"]["max_tx_limit"] is False
        assert body["reasons"]

    def test_authorize_defaults_max_allowed_when_omitted(self, client: TestClient) -> None:
        """Omitting max_allowed_usdc must not reject the request — it defaults
        to the configured max-tx limit."""
        response = client.post(
            "/api/v1/payments/authorize",
            json={
                "vehicle_id": "TRUCK-42",
                "provider_id": "prov_charge_a",
                "service": "charging",
                "amount_usdc": 18.0,
                "reason": "low battery",
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["approved"] is True

    def test_authorize_unknown_service_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/payments/authorize",
            json={
                "vehicle_id": "TRUCK-42",
                "provider_id": "prov_charge_a",
                "service": "teleport",
                "amount_usdc": 18.0,
                "reason": "low battery",
            },
            headers=HEADERS,
        )
        assert response.status_code == 422


class TestPaymentExecute:
    def test_execute_requires_api_key(self, client: TestClient) -> None:
        response = client.post("/api/v1/payments/execute", json={"intent_id": "any"})
        assert response.status_code == 401

    def test_execute_unknown_intent_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/payments/execute", json={"intent_id": "ghost"}, headers=HEADERS
        )
        assert response.status_code == 404

    def test_full_flow_and_persistence(self, client: TestClient) -> None:
        quote = client.post("/api/v1/payments/quote", json=QUOTE_BODY, headers=HEADERS).json()
        selected = next(quote_item for quote_item in quote["quotes"] if quote_item["selected"])

        authorize = client.post(
            "/api/v1/payments/authorize",
            json={
                "vehicle_id": quote["vehicle_id"],
                "provider_id": selected["provider_id"],
                "service": selected["service"],
                "amount_usdc": selected["price_usdc"],
                "reason": "battery below 20%",
                "max_allowed_usdc": 250.0,
                "decision_rationale": quote["rationale"],
            },
            headers=HEADERS,
        ).json()
        assert authorize["approved"] is True

        execute = client.post(
            "/api/v1/payments/execute",
            json={"intent_id": authorize["intent_id"]},
            headers=HEADERS,
        )
        assert execute.status_code == 200
        tx = execute.json()
        assert tx["status"] == "settled"
        assert tx["settlement_status"] == "settled"
        assert tx["tx_hash"].startswith("0xMOCK")
        assert tx["is_mock"] is True
        assert tx["provider_name"] == "VoltCharge"
        assert tx["explorer_url"].startswith("https://mock-explorer.arc.local/")

        # Persisted and fetchable by id.
        fetched = client.get(f"/api/v1/payments/{tx['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == tx["id"]

        # Wallet reflects the spend; history lists the transaction.
        wallet = client.get("/api/v1/payments/wallet").json()
        assert wallet["spent_today_usdc"] == 18.0
        assert wallet["is_mock"] is True
        history = client.get("/api/v1/payments/transactions").json()
        assert len(history) == 1
        assert history[0]["tx_hash"] == tx["tx_hash"]

    def test_execute_rejected_intent_422(self, client: TestClient) -> None:
        authorize = client.post(
            "/api/v1/payments/authorize",
            json={
                "vehicle_id": "TRUCK-42",
                "provider_id": "prov_charge_a",
                "service": "charging",
                "amount_usdc": 600.0,
                "reason": "over budget",
                "max_allowed_usdc": 250.0,
            },
            headers=HEADERS,
        ).json()
        assert authorize["approved"] is False
        response = client.post(
            "/api/v1/payments/execute",
            json={"intent_id": authorize["intent_id"]},
            headers=HEADERS,
        )
        assert response.status_code == 422


class TestPaymentDemoAndWallet:
    def test_demo_endpoint_full_story(self, client: TestClient) -> None:
        response = client.post("/api/v1/payments/demo", headers=HEADERS)
        assert response.status_code == 200
        body = response.json()
        assert len(body["decisions"]) == 3
        assert len(body["transactions"]) == 3
        assert body["summary"]["usdc_settled"] == 175.0
        assert body["summary"]["autonomous_payments"] == 3
        assert body["summary"]["arc_transactions"] == 3

    def test_demo_wallet_state(self, client: TestClient) -> None:
        client.post("/api/v1/payments/demo", headers=HEADERS)
        wallet = client.get("/api/v1/payments/wallet").json()
        assert wallet["balance_usdc"] == 825.0
        assert wallet["spent_today_usdc"] == 175.0
        assert wallet["remaining_today_usdc"] == 325.0
        assert wallet["daily_budget_usdc"] == 500.0
        assert wallet["is_mock"] is True

    def test_demo_requires_api_key(self, client: TestClient) -> None:
        response = client.post("/api/v1/payments/demo")
        assert response.status_code == 401

    def test_summary_endpoint(self, client: TestClient) -> None:
        summary = client.get("/api/v1/payments/summary").json()
        assert summary["autonomous_payments"] == 0
        assert summary["usdc_settled"] == 0.0
        assert summary["wallet"]["balance_usdc"] == 1000.0

    def test_unknown_transaction_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/payments/ghost")
        assert response.status_code == 404


class TestLiveBridgeAndNetwork:
    """The live fleet->payment bridge and settlement-network transparency."""

    def test_bridge_runs_with_the_app(self, client: TestClient) -> None:
        bridge = cast(Any, client.app).state.payment_bridge
        assert bridge.running is True
        assert bridge.armed == {}

    def test_wallet_reports_the_settlement_network(self, client: TestClient) -> None:
        wallet = client.get("/api/v1/payments/wallet").json()
        assert wallet["network"] == "arc-mock"
        assert wallet["is_mock"] is True

    def test_transactions_survive_a_restart(self, tmp_path: Path) -> None:
        """The database, not process memory, is the source of truth."""
        database_url = f"sqlite+aiosqlite:///{tmp_path}/restart.db"
        settings = Settings(
            database_url=database_url,
            artifact_dir=tmp_path / "artifacts",
            payment_live_bridge=False,
        )
        with TestClient(create_app(settings)) as first:
            first.post("/api/v1/payments/demo", headers=HEADERS)
            assert len(first.get("/api/v1/payments/transactions").json()) == 3

        with TestClient(create_app(settings)) as second:
            history = second.get("/api/v1/payments/transactions").json()
            assert len(history) == 3
            wallet = second.get("/api/v1/payments/wallet").json()
            assert wallet["spent_today_usdc"] == 175.0
