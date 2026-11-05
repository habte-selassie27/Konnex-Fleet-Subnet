"""RealCircleProvider tests — Circle Wallets REST + Arc JSON-RPC (mocked HTTP).

The provider performs real HTTP calls in production; here they are served by
httpx.MockTransport so the wire contract is asserted exactly — endpoints,
X-API-Key auth, documented request fields, Arc receipt semantics — without
credentials or network access. Nothing outside the transport is simulated.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.config import Settings
from backend.db.database import Database
from backend.services.payment_service import PaymentAppState
from payments.errors import PaymentProviderConfigError, PaymentProviderError
from payments.factory import create_payment_provider
from payments.models import SettlementStatus
from payments.real_provider import RealCircleProvider

CIRCLE_HOST = "api.circle.com"
VALID_ADDRESS = "0x" + "ab" * 20
API_KEY = "TEST123:key-id:secret"


class _FakeNetwork:
    """Serves canned Circle/Arc responses and records every request."""

    def __init__(
        self,
        *,
        balances: Any = None,
        transfer: Any = None,
        receipt: Any = None,
        balance_status: int = 200,
        transfer_status: int = 200,
        arc_error: Any = None,
    ) -> None:
        self.balances = balances
        self.transfer = transfer
        self.receipt = receipt
        self.balance_status = balance_status
        self.transfer_status = transfer_status
        self.arc_error = arc_error
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == CIRCLE_HOST:
            if request.url.path.endswith("/balances"):
                return httpx.Response(self.balance_status, json=self.balances)
            if request.url.path.endswith("/transfer"):
                return httpx.Response(self.transfer_status, json=self.transfer)
            if "entity/publicKey" in request.url.path:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "publicKey": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArJu+lA7PI8CYl40Veew1\nmUvDHbUVUcHa4RJz4SJJ9jVI0PoWXIaNLzadoZAUR9E8/WWgEjHQ4tuIKYB18kuq\nrjyzmuKIJzTj5CWhCPijvHQHicq2JgBbrot1Qy+kLArosBs2Lncd6uceSi96In5i\nX61mGGSUgyY9Olzg/sPzSaTie/ZIJVFL8SGyFDm6yR2lpoDTNKiF6zBvSfpfa0AV\nHSvwxdr2dVpgaFUUEaWgKBiDe0aoDv9JdcHylZU0MHUq7bRUjBNC9DMJzkSchLp3\nD++F1aAHL1ftJavjHzqO9YaN2otMmQlUVeBi0NJ3tskQ4r8wZ0CmbETgsku27Sze\njQIDAQAB\n-----END PUBLIC KEY-----"  # noqa: E501
                        }
                    },
                )
            if "/transactions/" in request.url.path:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "transaction": self.transfer.get("data", {})
                            if isinstance(self.transfer, dict)
                            else {}
                        }
                    },
                )
            return httpx.Response(404, json={"message": "not found"})
        body = json.loads(request.content.decode() or "{}")
        rpc_id = body.get("id", 1)
        if self.arc_error is not None:
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": rpc_id, "error": self.arc_error}
            )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": rpc_id, "result": self.receipt})

    def circle_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host == CIRCLE_HOST]

    def arc_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host != CIRCLE_HOST]


def _provider(network: _FakeNetwork, **overrides: Any) -> RealCircleProvider:
    kwargs: dict[str, Any] = {
        "wallet_id": "wallet-1",
        "circle_api_key": API_KEY,
        "entity_secret": "0" * 64,
        "token_id": "token-1",
        "arc_rpc_url": "https://rpc.testnet.arc.io",
        "arc_chain_id": "5042002",
        "settle_attempts": 2,
        "settle_poll_s": 0.0,
        "transport": httpx.MockTransport(network.handler),
    }
    kwargs.update(overrides)
    return RealCircleProvider(**kwargs)


class TestConfiguration:
    def test_missing_api_key_names_the_env_var(self) -> None:
        with pytest.raises(PaymentProviderConfigError) as exc:
            RealCircleProvider(
                wallet_id="w",
                circle_api_key="",
                entity_secret="0" * 64,
                arc_rpc_url="https://rpc",
                arc_chain_id="5042",
            )
        assert "CIRCLE_API_KEY" in str(exc.value)

    def test_missing_rpc_url_names_the_env_var(self) -> None:
        with pytest.raises(PaymentProviderConfigError) as exc:
            RealCircleProvider(
                wallet_id="w",
                circle_api_key=API_KEY,
                entity_secret="0" * 64,
                arc_rpc_url="",
                arc_chain_id="5042",
            )
        assert "ARC_RPC_URL" in str(exc.value)

    def test_missing_wallet_id_names_the_env_var(self) -> None:
        with pytest.raises(PaymentProviderConfigError) as exc:
            RealCircleProvider(
                wallet_id=" ",
                circle_api_key=API_KEY,
                entity_secret="0" * 64,
                arc_rpc_url="https://rpc",
                arc_chain_id="5042",
            )
        assert "PAYMENT_WALLET_ID" in str(exc.value)

    def test_network_label_follows_chain_id(self) -> None:
        assert _provider(_FakeNetwork(), arc_chain_id="5042").network == "arc-mainnet"
        assert _provider(_FakeNetwork(), arc_chain_id="5042002").network == "arc-testnet"
        assert _provider(_FakeNetwork(), arc_chain_id="999").network == "arc-chain-999"

    def test_provider_is_never_marked_mock(self) -> None:
        provider = _provider(_FakeNetwork())
        assert provider.is_mock is False
        provider.close()


class TestFactory:
    def test_real_mode_returns_live_provider(self) -> None:
        provider = create_payment_provider(
            "real",
            wallet_id="wallet-1",
            circle_api_key=API_KEY,
            circle_entity_secret="0" * 64,
            circle_token_id="token-1",
            arc_rpc_url="https://rpc.mainnet.arc.io",
            arc_chain_id="5042",
        )
        assert provider is not None
        assert provider.is_mock is False
        assert provider.network == "arc-mainnet"
        provider.close()  # type: ignore[attr-defined]

    def test_real_mode_missing_credentials_fails_at_startup(self) -> None:
        with pytest.raises(PaymentProviderConfigError) as exc:
            create_payment_provider(
                "real",
                wallet_id="wallet-1",
                circle_api_key="",
                arc_rpc_url="https://rpc.mainnet.arc.io",
                arc_chain_id="5042",
            )
        assert "CIRCLE_API_KEY" in str(exc.value)

    def test_mock_mode_is_still_mock(self) -> None:
        provider = create_payment_provider("mock")
        assert provider is not None
        assert provider.is_mock is True


class TestWalletBalance:
    def test_parses_usdc_entry_from_documented_shape(self) -> None:
        network = _FakeNetwork(
            balances={
                "data": {
                    "tokenBalances": [
                        {"token": {"id": "token-1", "symbol": "USDC"}, "amount": "825.00"}
                    ]
                }
            }
        )
        with _provider(network) as provider:
            assert provider.wallet_balance() == 825.0

    def test_wallet_without_usdc_returns_real_zero(self) -> None:
        network = _FakeNetwork(
            balances={
                "data": {
                    "tokenBalances": [
                        {"token": {"id": "token-2", "symbol": "EURC"}, "amount": "5.00"}
                    ]
                }
            }
        )
        with _provider(network) as provider:
            assert provider.wallet_balance() == 0.0

    def test_unexpected_payload_raises_instead_of_guessing(self) -> None:
        network = _FakeNetwork(balances={"data": "not-a-dict"})
        with _provider(network) as provider:
            with pytest.raises(PaymentProviderError):
                provider.wallet_balance()

    def test_rejected_api_key_raises_actionable_error(self) -> None:
        network = _FakeNetwork(balances={"data": {"tokenBalances": []}}, balance_status=401)
        with _provider(network) as provider:
            with pytest.raises(PaymentProviderError) as exc:
                provider.wallet_balance()
        assert "CIRCLE_API_KEY" in str(exc.value)


class TestTransfer:
    def test_posts_only_documented_fields_with_api_key_header(self) -> None:
        network = _FakeNetwork(
            transfer={
                "data": {
                    "id": "transfer-9",
                    "status": "INITIATED",
                    "txHash": "0xdeadbeef",
                }
            }
        )
        with _provider(network) as provider:
            result = provider.transfer(
                to_address=VALID_ADDRESS, amount_usdc=18.0, memo="FLEET-017|robot_1"
            )

        # The first Circle request is the entity public key fetch (needed for
        # signing); the transfer POST is the second Circle request.
        transfer_requests = [
            r for r in network.circle_requests() if r.url.path.endswith("/transfer")
        ]
        assert len(transfer_requests) >= 1
        request = transfer_requests[0]
        assert request.url.path == "/v1/w3s/developer/transactions/transfer"
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        body = json.loads(request.content.decode())
        assert body["walletId"] == "wallet-1"
        assert body["tokenId"] == "token-1"
        assert body["destinationAddress"] == VALID_ADDRESS
        assert body["amounts"] == ["18.000000"]
        assert body["feeLevel"] == "MEDIUM"
        assert "entitySecretCiphertext" in body
        assert "idempotencyKey" in body

        assert result.tx_hash == "0xdeadbeef"
        assert result.settlement_status is SettlementStatus.PENDING
        assert result.provider_payload["is_mock"] is False
        assert result.provider_payload["network"] == "arc-testnet"

    def test_rejects_non_positive_amount(self) -> None:
        with _provider(_FakeNetwork()) as provider:
            with pytest.raises(ValueError):
                provider.transfer(to_address=VALID_ADDRESS, amount_usdc=0.0, memo="")

    def test_rejects_malformed_destination(self) -> None:
        with _provider(_FakeNetwork()) as provider:
            with pytest.raises(ValueError):
                provider.transfer(to_address="0xnothex", amount_usdc=1.0, memo="")

    def test_http_error_becomes_payment_provider_error(self) -> None:
        network = _FakeNetwork(transfer={"message": "bad key"}, transfer_status=401)
        with _provider(network) as provider:
            with pytest.raises(PaymentProviderError) as exc:
                provider.transfer(to_address=VALID_ADDRESS, amount_usdc=1.0, memo="")
        assert "CIRCLE_API_KEY" in str(exc.value)

    def test_missing_transaction_hash_is_an_error_not_a_guess(self) -> None:
        network = _FakeNetwork(transfer={"data": {"id": "transfer-1", "status": "INITIATED"}})
        with _provider(network) as provider:
            with pytest.raises(PaymentProviderError):
                provider.transfer(to_address=VALID_ADDRESS, amount_usdc=1.0, memo="")


class TestSettlement:
    def test_receipt_status_one_is_settled(self) -> None:
        network = _FakeNetwork(receipt={"status": "0x1", "blockNumber": "0x2a"})
        with _provider(network) as provider:
            assert provider.settle("0xdead") is SettlementStatus.SETTLED

    def test_receipt_status_zero_is_failed(self) -> None:
        network = _FakeNetwork(receipt={"status": "0x0"})
        with _provider(network) as provider:
            assert provider.settle("0xdead") is SettlementStatus.FAILED

    def test_missing_receipt_stays_pending(self) -> None:
        network = _FakeNetwork(receipt=None)
        with _provider(network, settle_attempts=1) as provider:
            assert provider.settle("0xdead") is SettlementStatus.PENDING
        assert len(network.arc_requests()) == 1

    def test_settle_queries_arc_with_eth_get_transaction_receipt(self) -> None:
        network = _FakeNetwork(receipt={"status": "0x1"})
        with _provider(network) as provider:
            provider.settle("0xfeed")
        request = network.arc_requests()[0]
        body = json.loads(request.content.decode())
        assert body["method"] == "eth_getTransactionReceipt"
        assert body["params"] == ["0xfeed"]
        assert str(request.url) == "https://rpc.testnet.arc.io"

    def test_arc_rpc_error_becomes_payment_provider_error(self) -> None:
        network = _FakeNetwork(arc_error={"code": -32601, "message": "method not found"})
        with _provider(network) as provider:
            with pytest.raises(PaymentProviderError):
                provider.settle("0xdead")


class TestStatusAndExplorer:
    def test_transaction_status_reflects_receipt(self) -> None:
        network = _FakeNetwork(
            receipt={"status": "0x1", "blockNumber": "0x10", "from": "0x1", "to": "0x2"}
        )
        with _provider(network) as provider:
            status = provider.get_transaction_status("0xdead")
        assert status["status"] == "settled"
        assert status["is_mock"] is False
        assert status["network"] == "arc-testnet"

    def test_unknown_transaction_reports_not_found(self) -> None:
        network = _FakeNetwork(receipt=None)
        with _provider(network) as provider:
            status = provider.get_transaction_status("0xdead")
        assert status["status"] == "not_found"

    def test_explorer_url_derived_from_chain(self) -> None:
        with _provider(_FakeNetwork(), arc_chain_id="5042") as provider:
            assert provider.explorer_url("0xabc") == "https://explorer.arc.io/tx/0xabc"
        with _provider(_FakeNetwork()) as provider:
            assert provider.explorer_url("0xabc") == "https://explorer.testnet.arc.io/tx/0xabc"

    def test_unknown_chain_without_explorer_is_a_config_error(self) -> None:
        with _provider(_FakeNetwork(), arc_chain_id="999") as provider:
            with pytest.raises(PaymentProviderConfigError):
                provider.explorer_url("0xabc")


class TestBackendStartupValidation:
    def test_real_mode_without_destination_address_refuses_to_start(self, tmp_path: Path) -> None:
        async def scenario() -> None:
            db = Database(f"sqlite+aiosqlite:///{tmp_path}/real.db")
            await db.create_all()
            settings = Settings(
                database_url=f"sqlite+aiosqlite:///{tmp_path}/real.db",
                artifact_dir=tmp_path / "artifacts",
                payment_provider="real",
                payment_destination_address="",
                circle_api_key=API_KEY,
                arc_rpc_url="https://rpc.testnet.arc.io",
                arc_chain_id="5042002",
            )
            with pytest.raises(PaymentProviderConfigError) as exc:
                PaymentAppState(db, settings)
            assert "PAYMENT_DESTINATION_ADDRESS" in str(exc.value)
            await db.dispose()

        asyncio.run(scenario())
