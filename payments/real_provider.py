"""RealCircleProvider — Circle Developer-Controlled Wallets + Arc settlement.

Every endpoint, header, and field below was verified against Circle's current
documentation/OpenAPI (2026-11) before implementation:

  * Entity public key      GET  /v1/w3s/config/entity/publicKey
  * Wallet                 GET  /v1/w3s/wallets/{id}
  * Wallet balances        GET  /v1/w3s/wallets/{id}/balances
  * Create transfer        POST /v1/w3s/developer/transactions/transfer
  * Transaction status     GET  /v1/w3s/transactions/{id}
  * Auth                   `Authorization: Bearer <CIRCLE_API_KEY>`

The entity secret is a 32-byte hex key that never leaves the process. For every
request that needs it, a fresh RSA-OAEP (SHA-256 / MGF1-SHA-256) ciphertext is
produced with Circle's entity public key (Circle rejects reused ciphertexts).

Settlement is verified on Arc through `eth_getTransactionReceipt`:

    mainnet: chain id 5042,    https://rpc.mainnet.arc.io
    testnet: chain id 5042002, https://rpc.testnet.arc.io

Circle transfers are asynchronous: the create response only carries an id and
state. This provider polls `GET /v1/w3s/transactions/{id}` for the Arc tx hash
and then checks the Arc receipt. A payment that has not reached a terminal
state is returned as EXECUTED/PENDING instead of being guessed (Law 1).

Status: COMPLETE (implemented and unit-tested against mocked HTTP).
Live use requires CIRCLE_API_KEY, CIRCLE_ENTITY_SECRET, CIRCLE_TOKEN_ID, a
funded Circle wallet id, and an Arc RPC URL. No credentials ship with this
repository, so no live USDC transfer is claimed anywhere.
"""

from __future__ import annotations

import base64
import time
import uuid
from typing import Any

import httpx
import structlog

from payments.errors import PaymentProviderConfigError, PaymentProviderError
from payments.models import PaymentStatus, ProviderTransfer, SettlementStatus

logger = structlog.get_logger(__name__)

CIRCLE_API_BASE = "https://api.circle.com"
CIRCLE_W3S_PREFIX = "/v1/w3s"
FEE_LEVEL = "MEDIUM"
USDC_DECIMALS = 6

ARC_CHAIN_IDS = {
    "5042": "arc-mainnet",
    "5042002": "arc-testnet",
}
ARC_EXPLORERS = {
    "5042": "https://explorer.arc.io",
    "5042002": "https://explorer.testnet.arc.io",
}

# Circle transaction states (OpenAPI TransactionState enum).
TERMINAL_STATES = frozenset({"COMPLETE", "FAILED", "DENIED", "CANCELLED"})
FAILED_STATES = frozenset({"FAILED", "DENIED", "CANCELLED"})

_ADDRESS_PREFIX = "0x"


def _require(value: str, env_name: str) -> str:
    """Return a non-empty config value or raise a config error naming the env var."""
    cleaned = value.strip()
    if not cleaned:
        raise PaymentProviderConfigError(
            f"{env_name} is required for PAYMENT_PROVIDER=real. "
            f"See docs/payments.md §Configuration."
        )
    return cleaned


def _hex_to_int(value: object) -> int | None:
    """Parse an Ethereum JSON-RPC quantity (`0x2a`) or an int."""
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


class RealCircleProvider:
    """CirclePaymentProvider backed by Circle's Wallets API + Arc JSON-RPC.

    Blocking I/O: every method performs HTTP requests. The backend facade
    calls these through `asyncio.to_thread` so the event loop never blocks.
    """

    is_mock = False

    def __init__(
        self,
        *,
        wallet_id: str,
        circle_api_key: str,
        entity_secret: str = "",
        token_id: str = "",
        arc_rpc_url: str,
        arc_chain_id: str,
        arc_explorer_url: str = "",
        network: str = "",
        circle_api_base: str = CIRCLE_API_BASE,
        entity_public_key: str = "",
        timeout_s: float = 20.0,
        poll_attempts: int = 6,
        poll_interval_s: float = 2.0,
        settle_attempts: int = 5,
        settle_poll_s: float = 0.5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.wallet_id = _require(wallet_id, "PAYMENT_WALLET_ID")
        self._api_key = _require(circle_api_key, "CIRCLE_API_KEY")
        self._token_id = token_id.strip()  # resolved from wallet balances if empty
        self._entity_secret = self._validated_entity_secret(entity_secret)
        self._arc_rpc_url = _require(arc_rpc_url, "ARC_RPC_URL")
        self._arc_chain_id = _require(arc_chain_id, "ARC_CHAIN_ID")
        self._explorer_base = (
            arc_explorer_url.strip() or ARC_EXPLORERS.get(self._arc_chain_id, "")
        ).rstrip("/")
        self.network = network.strip() or ARC_CHAIN_IDS.get(
            self._arc_chain_id, f"arc-chain-{self._arc_chain_id}"
        )
        self._public_key_override = entity_public_key.strip()
        self._entity_public_key = ""
        self._wallet_address = ""
        self._wallet_blockchain = ""
        self._poll_attempts = max(0, poll_attempts)
        self._poll_interval_s = max(0.0, poll_interval_s)
        self._settle_attempts = max(1, settle_attempts)
        self._settle_poll_s = max(0.0, settle_poll_s)

        # Circle client carries the bearer token; the Arc client must not.
        self._circle = httpx.Client(
            base_url=circle_api_base.rstrip("/"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout_s,
            transport=transport,
        )
        self._arc = httpx.Client(timeout=timeout_s, transport=transport)
        logger.info(
            "real_circle_provider_initialized",
            wallet_id=self.wallet_id,
            token_id=self._token_id,
            network=self.network,
            arc_chain_id=self._arc_chain_id,
            arc_rpc_url=self._arc_rpc_url,
        )

    # ─── CirclePaymentProvider protocol ──────────────────────────────────

    @property
    def wallet_address(self) -> str:
        """Cached on-chain address of the Circle wallet (empty until health check)."""
        return self._wallet_address

    def health_check(self) -> dict[str, Any]:
        """Fail-fast startup check: wallet exists, is readable, and holds USDC.

        Returns the observed wallet facts (never fabricated). Raises
        PaymentProviderError when Circle rejects the credentials or the wallet
        is not accessible, so PAYMENT_PROVIDER=real cannot start half-wired.
        """
        self._fetch_wallet()
        balance = self.wallet_balance()
        info = {
            "wallet_id": self.wallet_id,
            "wallet_address": self._wallet_address,
            "blockchain": self._wallet_blockchain,
            "balance_usdc": balance,
            "network": self.network,
            "is_mock": False,
        }
        logger.info("real_circle_wallet_verified", **info)
        return info

    def wallet_balance(self) -> float:
        """USDC balance of the Circle wallet (decimal token units)."""
        response = self._circle.get(
            f"{CIRCLE_W3S_PREFIX}/wallets/{self.wallet_id}/balances",
            params={"pageSize": 50},
        )
        self._raise_for_http(response, "wallet balance")
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        balances = data.get("tokenBalances") if isinstance(data, dict) else None
        if not isinstance(balances, list):
            raise PaymentProviderError(f"unexpected Circle balances payload: {payload!r}")

        by_token_id: float | None = None
        by_symbol: float | None = None
        for entry in balances:
            if not isinstance(entry, dict):
                continue
            token = entry.get("token")
            if not isinstance(token, dict):
                continue
            try:
                amount = float(entry.get("amount", 0.0))
            except (TypeError, ValueError) as exc:
                raise PaymentProviderError(
                    f"non-numeric balance in Circle response: {entry!r}"
                ) from exc
            if str(token.get("id") or "") == self._token_id:
                by_token_id = amount
            if str(token.get("symbol") or "").upper() == "USDC" and by_symbol is None:
                by_symbol = amount

        # Prefer the exact configured token; fall back to a USDC entry on the
        # wallet's single blockchain. No USDC entry is a real zero balance.
        value = by_token_id if by_token_id is not None else by_symbol
        return round(value, USDC_DECIMALS) if value is not None else 0.0

    def transfer(
        self,
        *,
        to_address: str,
        amount_usdc: float,
        memo: str,
    ) -> ProviderTransfer:
        """Submit a USDC transfer from the Circle wallet and follow its status."""
        if amount_usdc <= 0:
            raise ValueError("amount_usdc must be > 0")
        if not to_address.startswith(_ADDRESS_PREFIX) or len(to_address) != 42:
            raise ValueError(f"invalid destination address {to_address!r}")

        self._token_id = self._resolve_token_id()
        transfer_id, initial_state = self._submit_transfer(to_address, amount_usdc)
        info = self._wait_for_hash(transfer_id, initial_state)
        state = str(info.get("state") or initial_state)
        tx_hash = str(info.get("txHash") or "")
        error_reason = str(info.get("errorReason") or info.get("errorDetails") or "")
        if not tx_hash and state not in FAILED_STATES:
            raise PaymentProviderError(
                f"Circle transfer {transfer_id} did not produce a transaction hash "
                f"(state={state}); refusing to guess."
            )
        failed = state in FAILED_STATES
        block_height = _hex_to_int(info.get("blockHeight"))

        logger.info(
            "circle_transfer_submitted",
            transfer_id=transfer_id,
            state=state,
            tx_hash=tx_hash or None,
            amount_usdc=amount_usdc,
            destination=to_address,
            failed=failed,
        )
        payload: dict[str, object] = {
            "network": self.network,
            "chain_id": self._arc_chain_id,
            "wallet_id": self.wallet_id,
            "wallet_address": self._wallet_address,
            "destination_address": to_address,
            "circle_transaction_id": transfer_id,
            "circle_state": state,
            "error_reason": error_reason,
            "block_height": block_height,
            "memo": memo,  # local only — Arc memo contract is a documented follow-up
            "is_mock": False,
        }
        return ProviderTransfer(
            tx_hash=tx_hash,
            status=PaymentStatus.FAILED if failed else PaymentStatus.EXECUTED,
            settlement_status=SettlementStatus.FAILED if failed else SettlementStatus.PENDING,
            provider_payload=payload,
        )

    def settle(self, tx_hash: str) -> SettlementStatus:
        """Poll Arc for the receipt; Arc finalizes in under a second.

        Returns SETTLED (status 0x1), FAILED (status 0x0) or PENDING when the
        receipt has not appeared within the configured attempt budget.
        """
        if not tx_hash:
            return SettlementStatus.PENDING
        for attempt in range(self._settle_attempts):
            receipt = self._receipt(tx_hash)
            if isinstance(receipt, dict):
                status = receipt.get("status")
                if status in ("0x1", 1, "0x01"):
                    logger.info("arc_settlement_confirmed", tx_hash=tx_hash, attempt=attempt)
                    return SettlementStatus.SETTLED
                if status in ("0x0", 0, "0x00"):
                    logger.error("arc_settlement_reverted", tx_hash=tx_hash, attempt=attempt)
                    return SettlementStatus.FAILED
            if attempt < self._settle_attempts - 1 and self._settle_poll_s > 0:
                time.sleep(self._settle_poll_s)
        logger.warning(
            "arc_settlement_pending",
            tx_hash=tx_hash,
            attempts=self._settle_attempts,
        )
        return SettlementStatus.PENDING

    def get_transaction_status(self, tx_hash: str) -> dict[str, Any]:
        """Receipt-derived status for a transfer (Arc JSON-RPC)."""
        if not tx_hash:
            return {
                "tx_hash": "",
                "status": "not_submitted",
                "network": self.network,
                "is_mock": False,
            }
        receipt = self._receipt(tx_hash)
        if not isinstance(receipt, dict):
            return {
                "tx_hash": tx_hash,
                "status": "not_found",
                "network": self.network,
                "is_mock": False,
            }
        status_code = receipt.get("status")
        if status_code in ("0x1", 1, "0x01"):
            status = "settled"
        elif status_code in ("0x0", 0, "0x00"):
            status = "failed"
        else:
            status = "pending"
        return {
            "tx_hash": tx_hash,
            "status": status,
            "block_number": _hex_to_int(receipt.get("blockNumber")),
            "from_address": receipt.get("from"),
            "to_address": receipt.get("to"),
            "gas_used": receipt.get("gasUsed"),
            "network": self.network,
            "is_mock": False,
        }

    def refresh_transaction(self, provider_transaction_id: str) -> dict[str, Any]:
        """Poll the Circle transaction and report its latest reconciliation data.

        Used by POST /payments/{id}/refresh to resolve asynchronous transfers
        whose Arc hash was not available when they were first executed.
        """
        info = self._get_circle_transaction(provider_transaction_id)
        state = str(info.get("state") or "")
        return {
            "provider_transaction_id": provider_transaction_id,
            "state": state,
            "tx_hash": str(info.get("txHash") or ""),
            "block_number": _hex_to_int(info.get("blockHeight")),
            "error_reason": str(info.get("errorReason") or info.get("errorDetails") or ""),
            "terminal": state in TERMINAL_STATES,
            "failed": state in FAILED_STATES,
            "network": self.network,
            "is_mock": False,
        }

    def explorer_url(self, tx_hash: str) -> str:
        """Block-explorer URL for a real Arc transaction."""
        if not self._explorer_base:
            raise PaymentProviderConfigError(
                "ARC_EXPLORER_URL is not configured for this chain "
                f"(chain id {self._arc_chain_id})."
            )
        return f"{self._explorer_base}/tx/{tx_hash}"

    # ─── Lifecycle ───────────────────────────────────────────────────────

    def close(self) -> None:
        """Release the underlying HTTP clients."""
        self._circle.close()
        self._arc.close()

    def __enter__(self) -> RealCircleProvider:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ─── Circle internals ────────────────────────────────────────────────

    @staticmethod
    def _validated_entity_secret(entity_secret: str) -> str:
        cleaned = _require(entity_secret, "CIRCLE_ENTITY_SECRET")
        if len(cleaned) != 64:
            raise PaymentProviderConfigError(
                "CIRCLE_ENTITY_SECRET must be a 64-character hex string (32 bytes)."
            )
        try:
            bytes.fromhex(cleaned)
        except ValueError as exc:
            raise PaymentProviderConfigError(
                "CIRCLE_ENTITY_SECRET must be a 64-character hex string (32 bytes)."
            ) from exc
        return cleaned

    def _fetch_wallet(self) -> dict[str, Any]:
        """GET the wallet and cache its address/blockchain."""
        response = self._circle.get(f"{CIRCLE_W3S_PREFIX}/wallets/{self.wallet_id}")
        self._raise_for_http(response, "wallet lookup")
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        wallet = data.get("wallet") if isinstance(data, dict) else None
        if not isinstance(wallet, dict):
            raise PaymentProviderError(f"unexpected Circle wallet payload: {payload!r}")
        address = wallet.get("address")
        if not isinstance(address, str) or not address.startswith(_ADDRESS_PREFIX):
            raise PaymentProviderError(
                f"Circle wallet {self.wallet_id} has no usable address: {payload!r}"
            )
        self._wallet_address = address
        self._wallet_blockchain = str(wallet.get("blockchain") or "")
        return wallet

    def _resolve_token_id(self) -> str:
        """Resolve the USDC token id from the wallet's balances if not configured."""
        if self._token_id:
            return self._token_id
        try:
            balances = self._circle.get(
                f"{CIRCLE_W3S_PREFIX}/wallets/{self.wallet_id}/balances",
                params={"pageSize": 50},
            )
            self._raise_for_http(balances, "wallet balance")
            payload = balances.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            entries = data.get("tokenBalances") if isinstance(data, dict) else None
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    token = entry.get("token")
                    if not isinstance(token, dict):
                        continue
                    if str(token.get("symbol") or "").upper() == "USDC":
                        tid = str(token.get("id") or "")
                        if tid:
                            self._token_id = tid
                            return tid
        except Exception:
            pass
        raise PaymentProviderConfigError(
            "CIRCLE_TOKEN_ID could not be resolved from wallet balances. "
            "Fund the wallet with USDC via https://faucet.circle.com, or set "
            "CIRCLE_TOKEN_ID explicitly."
        )

    def _entity_secret_ciphertext(self) -> str:
        """Encrypt the entity secret with Circle's RSA public key (fresh each call)."""
        public_key = self._public_key_override or self._entity_public_key
        if not public_key:
            response = self._circle.get(f"{CIRCLE_W3S_PREFIX}/config/entity/publicKey")
            self._raise_for_http(response, "entity public key")
            payload = response.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            key = data.get("publicKey") if isinstance(data, dict) else None
            if not isinstance(key, str) or "BEGIN PUBLIC KEY" not in key:
                raise PaymentProviderError(
                    f"unexpected Circle entity public key payload: {payload!r}"
                )
            public_key = key
            self._entity_public_key = key

        try:
            from Crypto.Cipher import PKCS1_OAEP
            from Crypto.Hash import SHA256
            from Crypto.PublicKey import RSA
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise PaymentProviderConfigError(
                "pycryptodome is required for PAYMENT_PROVIDER=real "
                "(pip install pycryptodome==3.23.0)."
            ) from exc

        cipher = PKCS1_OAEP.new(key=RSA.importKey(public_key), hashAlgo=SHA256)
        encrypted = cipher.encrypt(bytes.fromhex(self._entity_secret))
        return base64.b64encode(encrypted).decode()

    def _submit_transfer(self, to_address: str, amount_usdc: float) -> tuple[str, str]:
        """POST the transfer and return (Circle transaction id, initial state)."""
        body = {
            "idempotencyKey": str(uuid.uuid4()),
            "walletId": self.wallet_id,
            "tokenId": self._token_id,
            "destinationAddress": to_address,
            "amounts": [f"{amount_usdc:.{USDC_DECIMALS}f}"],
            "feeLevel": FEE_LEVEL,
            "entitySecretCiphertext": self._entity_secret_ciphertext(),
        }
        response = self._circle.post(
            f"{CIRCLE_W3S_PREFIX}/developer/transactions/transfer", json=body
        )
        self._raise_for_http(response, "USDC transfer")
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise PaymentProviderError(f"unexpected Circle transfer payload: {payload!r}")
        transfer_id = data.get("id")
        if not isinstance(transfer_id, str) or not transfer_id:
            raise PaymentProviderError(
                f"Circle transfer accepted but returned no transaction id: {payload!r}"
            )
        return transfer_id, str(data.get("state") or "INITIATED")

    def _wait_for_hash(self, transfer_id: str, initial_state: str) -> dict[str, Any]:
        """Poll until Circle reports a tx hash or a terminal state."""
        info = self._get_circle_transaction(transfer_id)
        state = str(info.get("state") or initial_state)
        for attempt in range(self._poll_attempts):
            if info.get("txHash") or state in TERMINAL_STATES:
                break
            if self._poll_interval_s > 0:
                time.sleep(self._poll_interval_s)
            info = self._get_circle_transaction(transfer_id)
            state = str(info.get("state") or state)
            logger.debug(
                "circle_transfer_poll",
                transfer_id=transfer_id,
                state=state,
                attempt=attempt + 1,
            )
        return info

    def _get_circle_transaction(self, transfer_id: str) -> dict[str, Any]:
        """GET /v1/w3s/transactions/{id} -> the transaction object."""
        response = self._circle.get(f"{CIRCLE_W3S_PREFIX}/transactions/{transfer_id}")
        self._raise_for_http(response, "transaction status")
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        transaction = data.get("transaction") if isinstance(data, dict) else None
        if not isinstance(transaction, dict):
            raise PaymentProviderError(f"unexpected Circle transaction payload: {payload!r}")
        return transaction

    # ─── Arc internals ───────────────────────────────────────────────────

    def _receipt(self, tx_hash: str) -> dict[str, Any] | None:
        """eth_getTransactionReceipt, or None while the tx is still unknown."""
        result = self._rpc("eth_getTransactionReceipt", [tx_hash])
        if result is None:
            return None
        if not isinstance(result, dict):
            raise PaymentProviderError(f"unexpected receipt payload: {result!r}")
        return result

    def _rpc(self, method: str, params: list[Any]) -> Any:
        """One JSON-RPC call against Arc."""
        try:
            response = self._arc.post(
                self._arc_rpc_url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            )
        except httpx.HTTPError as exc:
            raise PaymentProviderError(f"Arc RPC {method} failed: {exc}") from exc
        if response.status_code >= 400:
            raise PaymentProviderError(
                f"Arc RPC {method} returned HTTP {response.status_code}: {response.text[:200]}"
            )
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise PaymentProviderError(f"Arc RPC {method} error: {payload['error']}")
        return payload.get("result") if isinstance(payload, dict) else None

    @staticmethod
    def _raise_for_http(response: httpx.Response, action: str) -> None:
        """Raise PaymentProviderError with an actionable message on HTTP failure."""
        if response.status_code < 400:
            return
        body = response.text[:300]
        if response.status_code in (401, 403):
            raise PaymentProviderError(
                f"Circle rejected the API key during {action} "
                f"(HTTP {response.status_code}) — check CIRCLE_API_KEY."
            )
        raise PaymentProviderError(f"Circle {action} failed (HTTP {response.status_code}): {body}")
