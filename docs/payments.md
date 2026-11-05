# Agentic Payment Layer — FleetPay Agent (Arc + Circle USDC)

> **Track:** Ignyte Stablecoin Commerce Stack — *Best Agentic Economy Experience on Arc*
> **Status:** COMPLETE. Two settlement paths ship: `mock` (in-process USDC/Arc
> simulation, explicitly labeled MOCK/DEMO) and `real` (Circle Wallets REST +
> Arc JSON-RPC — implemented and unit-tested against mocked HTTP; live use
> requires credentials). Payments are additionally driven by live mission
> telemetry (§5).
> **One-liner:** An AI fleet agent that autonomously evaluates operational
> needs, selects optimal service providers, and settles authorized payments
> in USDC on Arc.

---

## 1. What this is

The existing **Autonomous Fleet Intelligence** project coordinates robot fleets
on warehouse missions. This layer makes the *fleet agent an economic actor*:

```
Fleet Event → AI Agent → Provider Evaluation → Payment Intent
→ Policy Engine → Circle Wallet → USDC → Arc → Settlement → Receipt
```

The AI does not just *recommend* an action — it participates in the economic
transaction: it observes a fleet event (e.g. "vehicle battery at 18%"),
evaluates competing service providers, picks one, and (through a
deterministic policy gate) authorizes a USDC payment that settles on Arc.

### Demo story

```
Human:  "Keep Fleet #17 operational under a $500 budget."

Fleet:  TRUCK-42 battery at 18% — charging required
Agent:  VoltCharge $18 · ApexGrid $14 · QuickJuice $21  →  VoltCharge
Policy: approved (currency, amount, budget, address, provider all pass)
Circle: -18 USDC from the agent wallet (MOCK)
Arc:    settled — 0xMOCK7c30f8f1… (MOCK explorer link)
Receipt: rcpt_… (is_mock=True)

VAN-27  maintenance → AutoServiceX $62      (settled)
TRUCK-12 fueling   → PetroDirect  $95      (settled)

TODAY:  Budget $500 · Spent $175 · Remaining $325 · 3 autonomous payments
```

---

## 2. Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│ PRESENTATION  React dashboard — "FleetPay Agent" panel                │
│   wallet · budget bar · agent decisions · provider comparison ·       │
│   tx history · 0xMOCK… hashes + MOCK explorer links                    │
├───────────────────────────────────────────────────────────────────────┤
│ API GATEWAY  FastAPI  POST /payments/{quote,authorize,execute,demo}   │
│               GET /payments/{wallet,transactions,summary,:id}          │
├───────────────────────────────────────────────────────────────────────┤
│ APPLICATION  backend/services/payment_service.py (PaymentAppState)    │
│              + SQLite persistence (backend/db/models.py PaymentRecord)│
├───────────────────────────────────────────────────────────────────────┤
│ DOMAIN CORE  payments/ (imports NOTHING from fleet/robotics/ml/)      │
│   payments/agent.py        FleetPaymentAgent — deterministic decisions│
│   payments/policy.py       PaymentPolicy — the payment gatekeeper     │
│   payments/service.py      PaymentService — quote/authorize/execute   │
│   payments/providers.py    deterministic provider catalog             │
│   payments/models.py       intents · transactions · receipts · wallet │
├──────────────────────────────┬────────────────────────────────────────┤
│ WALLET BOUNDARY              │ SETTLEMENT BOUNDARY                    │
│ payments/provider.py         │ payments/contracts/FleetPayment.sol    │
│  MockCircleProvider  (MOCK)  │  payProvider(address, amount,          │
│  RealCircleProvider  (live)  │    fleetId, vehicleId, serviceId)      │
└──────────────────────────────┴────────────────────────────────────────┘
```

### Layering rules

- `payments/` is a **pure domain module**: it imports nothing from `fleet/`,
  `robotics/`, `simulation/`, `ml/`, or `protocol/`. Fleet telemetry enters
  as plain `FleetEvent` dataclasses.
- The **only** wallet/chain boundary is `CirclePaymentProvider`
  (`payments/provider.py`). `MockCircleProvider` and (future)
  `RealCircleProvider` are the only implementations.
- The **AI never touches the wallet**. `PaymentService.execute()` is the only
  code path that calls the provider, and it only runs on intents the policy
  engine already approved (spec §6).

---

## 3. Security model (spec §6)

| Rule | Where enforced |
|---|---|
| LLM/agent never gets private keys | `PaymentPolicy` sits between agent output and any provider call |
| Max transaction amount | `PAYMENT_MAX_TX_USDC` (default 250) — check `max_tx_limit` |
| Daily / agent spending limit | `PAYMENT_DAILY_BUDGET_USDC` (default 500) — check `daily_budget` |
| Request-level cap | `max_allowed_usdc` on each intent — check `max_allowed` |
| Recipient/provider validation | provider must exist in catalog + address must match `^0x[0-9a-fA-F]{40}$` |
| Malformed requests rejected | currency must be USDC, amount > 0, reason required, service known |
| Wallet balance check | amount ≤ wallet balance before execution |

The policy is **deterministic** — no randomness, no LLM — and every check
result is returned so the dashboard can show exactly why a payment was
approved or rejected.

---

## 4. API

All endpoints under `/api/v1/payments`; mutating endpoints require
`X-Fleet-API-Key`.

| Method | Path | Description |
|---|---|---|
| POST | `/payments/quote` | Agent observes a fleet event → provider decision + rationale |
| POST | `/payments/authorize` | Policy-gate a payment request (no wallet access) |
| POST | `/payments/execute` | Execute an authorized intent (USDC → Arc) |
| POST | `/payments/demo` | Deterministic end-to-end demo (resets the demo wallet) |
| GET | `/payments/wallet` | Agent wallet: balance, daily budget, spent, remaining |
| GET | `/payments/transactions` | Transaction history (newest first) |
| GET | `/payments/summary` | Aggregate agent-economy stats |
| GET | `/payments/{id}` | Single transaction |

### Example: quote

```bash
curl -s -X POST http://localhost:8000/api/v1/payments/quote \
  -H "X-Fleet-API-Key: dev-only-key" -H "Content-Type: application/json" \
  -d '{"vehicle_id":"TRUCK-42","event_type":"charging_required","battery_pct":0.18}'
```

Returns the three provider quotes (price / distance / rating / score), the
selected provider, and the agent's rationale.

### Example: authorize + execute

```bash
curl -s -X POST http://localhost:8000/api/v1/payments/authorize \
  -H "X-Fleet-API-Key: dev-only-key" -H "Content-Type: application/json" \
  -d '{"vehicle_id":"TRUCK-42","provider_id":"prov_charge_a","service":"charging",
       "amount_usdc":18.0,"reason":"battery below 20%","max_allowed_usdc":250.0}'
# → {"intent_id":"…","approved":true,"checks":{…},"reasons":[]}

curl -s -X POST http://localhost:8000/api/v1/payments/execute \
  -H "X-Fleet-API-Key: dev-only-key" -H "Content-Type: application/json" \
  -d '{"intent_id":"…"}'
# → {"status":"settled","tx_hash":"0xMOCK…","is_mock":true,"explorer_url":"…"}
```

---

## 5. Live fleet → payment bridge

`backend/services/fleet_payment_bridge.py` watches the running mission and
turns **real telemetry** into payments through the same quote → authorize →
execute path the REST API exposes:

| Trigger (observed in `RobotState`) | Event | Comes from |
|---|---|---|
| `nav_state == failed` | `maintenance_required` | injected/detected robot failure |
| `battery_pct <= PAYMENT_LOW_BATTERY_THRESHOLD` (0.20) | `charging_required` | same tier the failure detector calls low battery |

Guarantees:

- **One payment per episode.** Arming clears when the condition resolves
  (battery recovers, robot returns to service) or when a new mission starts,
  so a long mission cannot drain the budget with duplicate payments.
- **Policy-gated.** Every payment passes `PaymentPolicy` (daily budget,
  per-tx cap, balance); rejections are logged and counted, never forced.
- **Nothing fabricated.** Events derive only from state the orchestrator
  actually reported during a real run (AGENTS.md Law 1).
- **Resilient.** A failing tick is logged and retried; the bridge never takes
  the API down. Toggle with `PAYMENT_LIVE_BRIDGE=true|false`.

`scripts/demo.sh` schedules `navigation_failure` on `robot_2` at t+20s, so the
FleetPay panel shows a mission-driven payment a few seconds later — real
event, real agent decision, real persisted transaction (settlement stays MOCK
until credentials exist).

---

## 6. Configuration

Copy `.env.example` → `.env` (all defaults are demo-safe):

| Variable | Default | Meaning |
|---|---|---|
| `PAYMENT_PROVIDER` | `mock` | `mock` (MOCK/DEMO) · `real` (Circle+Arc — implemented, needs creds) · `disabled` |
| `PAYMENT_CURRENCY` | `USDC` | Settlement currency |
| `PAYMENT_FLEET_ID` | `FLEET-017` | Fleet identifier embedded in metadata |
| `PAYMENT_DAILY_BUDGET_USDC` | `500` | Daily spending limit enforced by policy |
| `PAYMENT_MAX_TX_USDC` | `250` | Per-transaction limit enforced by policy |
| `PAYMENT_WALLET_ID` | `fleet-agent-wallet-001` | Agent wallet identifier |
| `PAYMENT_WALLET_INITIAL_BALANCE_USDC` | `1000` | Mock wallet starting balance |
| `PAYMENT_DESTINATION_ADDRESS` | *(empty)* | Arc receiving wallet (0x + 40 hex) — **required for `real`** |
| `PAYMENT_LIVE_BRIDGE` | `true` | Live telemetry → payment bridge (§5) |
| `PAYMENT_LOW_BATTERY_THRESHOLD` | `0.20` | Battery level that raises `charging_required` |
| `PAYMENT_BRIDGE_INTERVAL_S` | `2.0` | Bridge poll interval in seconds |

### Circle configuration (`PAYMENT_PROVIDER=real`)

| Variable | Required for real mode | Purpose |
|---|---|---|
| `CIRCLE_API_KEY` | ✅ | Circle API key (`PREFIX:ID:SECRET`), sent as `X-API-Key` |
| `PAYMENT_WALLET_ID` | ✅ | Funded Circle wallet id the agent pays from |
| `CIRCLE_WALLET_SET_ID` | — | Reserved for wallet creation (not used by transfers) |
| `CIRCLE_WALLET_CONFIG_ID` | — | Reserved for wallet creation (not used by transfers) |

### Arc configuration (`PAYMENT_PROVIDER=real`)

| Variable | Required for real mode | Purpose |
|---|---|---|
| `ARC_RPC_URL` | ✅ | Arc JSON-RPC endpoint — `https://rpc.mainnet.arc.io` / `https://rpc.testnet.arc.io` |
| `ARC_CHAIN_ID` | ✅ | `5042` (mainnet) / `5042002` (testnet); sets the network label |
| `ARC_EXPLORER_URL` | — | Derived from the chain id when empty (`explorer.arc.io`) |
| `ARC_CONTRACT_ADDRESS` | — | Only for the optional `FleetPayment.sol` settlement contract |

Missing required values fail **at startup** with a `PaymentProviderConfigError`
naming the env var — real mode never falls back to mock data.

---

## 7. Mock vs real (honesty contract — spec §12)

| Capability | Mock (default) | Real (`payments/real_provider.py`) |
|---|---|---|
| Wallet balance | In-memory USDC balance | `GET /v1/wallets/{id}/balances` with `X-API-Key` |
| Transfer | Simulated; deducts balance | `POST /v1/wallets/{id}/transfers` → `data.transactionHash` |
| Tx hash | `0xMOCK…` (unmistakable) | Real hash returned by Circle |
| Settlement | Instant mock confirmation | `eth_getTransactionReceipt` on Arc → settled (`0x1`) / failed (`0x0`) / pending |
| Explorer | `https://mock-explorer.arc.local/tx/…` | `https://explorer.arc.io/tx/…` (chain-derived) |
| Receipt / label | `is_mock=True`, `arc-mock` | `is_mock=False`, `arc-mainnet` / `arc-testnet` |

**Nothing in the demo claims to be on-chain.** Every artifact carries an
`is_mock` flag, `0xMOCK…` hashes, and a MOCK badge in the UI; the wallet card
switches to a `LIVE · <network>` badge only when `is_mock=False`.

**Honesty note on the real path:** the Circle/Arc implementation is exercised
by `tests/unit/test_real_provider.py` against `httpx.MockTransport` (exact
endpoints, headers, and documented fields). It has **never** been run against
live Circle — no credentials exist in this repo — so no live-transfer result
is claimed anywhere (Law 1).

---

## 7. Contract — `payments/contracts/FleetPayment.sol`

Minimal settlement contract (per spec §4):

```solidity
function payProvider(
    address provider, uint256 amount,
    bytes32 fleetId, bytes32 vehicleId, bytes32 serviceId
) external;   // only the authorized fleetAgent wallet
```

It emits `PaymentSettled(provider, amount, fleetId, vehicleId, serviceId, ts)`
so an on-chain payment can be traced back to the fleet event. Deployment steps
(compile with solc/hardhat, deploy with USDC + agent wallet, `approve` the
contract, set `ARC_CONTRACT_ADDRESS`) are in `payments/contracts/README.md`.

**Status: NOT DEPLOYED** — requires an Arc RPC + USDC token + funded wallet.

---

## 9. Local development

```bash
make setup            # install dependencies
make payment-demo     # terminal demo of the full agentic payment loop
make demo             # full stack: backend :8000 + dashboard :3014
# open http://localhost:3014 → "FleetPay Agent" panel → click "Run demo"
```

The demo panel shows: agent wallet (balance / daily budget / spent /
remaining), the three agent decisions with the provider comparison tables and
rationale, and the payment history with `0xMOCK…` hashes and MOCK explorer
links. The **Run demo** button triggers the deterministic end-to-end scenario
(`POST /api/v1/payments/demo`) and refreshes the wallet + history.

> **Note:** reads are database-backed. Wallet spend, history, and summary come
> from the SQLite `payments` table, so a backend restart shows the same data
> (covered by `test_transactions_survive_a_restart`). The mock wallet balance
> itself is in-process and resets with the backend, and `POST /payments/demo`
> is an explicit reset: it clears the persisted ledger and re-tells the same
> 3-event / $175 story.

```bash
python -m pytest tests/unit/test_payment_policy.py tests/unit/test_payment_agent.py \
  tests/unit/test_payment_flow.py tests/unit/test_real_provider.py \
  tests/unit/test_payment_bridge.py tests/integration/test_payments_api.py -q
```

---

## 10. Going real (checklist)

1. Get Circle API credentials and a funded wallet id; fund it with USDC on
   Arc (testnet faucet: https://faucet.circle.com).
2. Set `CIRCLE_API_KEY`, `PAYMENT_WALLET_ID`, `ARC_RPC_URL`,
   `ARC_CHAIN_ID`, `PAYMENT_DESTINATION_ADDRESS`; then
   `PAYMENT_PROVIDER=real`.
3. Run a small testnet transfer first (Arc testnet chain id `5042002`),
   verify the receipt on `explorer.testnet.arc.io`, then switch to mainnet.
4. Optionally deploy `FleetPayment.sol` (see contract README) for attributed
   settlement and set `ARC_CONTRACT_ADDRESS`.
5. Replace the deterministic `ProviderRegistry` with a live marketplace API
   (same `Provider` shape).
6. Badges flip automatically: the UI renders `LIVE · <network>` once
   `is_mock=False` — no UI edits needed.

---

## 11. Circle Product Feedback (challenge requirement)

This section is the integration feedback requested by the Ignyte Stablecoin
Commerce Stack challenge. It reflects **planned/architecture-level
integration** — no Circle API calls were made because credentials were not
available in this environment (allowed by the challenge for gated products).

1. **Developer experience / docs:** The Circle Wallets (Programmable Wallets)
   API and Arc settlement flow should ship with an official Python SDK and a
   worked end-to-end agentic-payments sample (wallet creation → allowance →
   USDC transfer → settlement status polling). We implemented the documented
   REST contract directly with httpx (`payments/real_provider.py`); an official
   Python SDK would still be preferable to hand-rolled HTTP.
2. **Agentic primitives:** A first-class "agent wallet" concept (per-agent
   balance + spend limits + webhook events) would remove the need to hand-roll
   the policy/limits layer. `POST /v1/wallets/{id}/transfers` with
   configurable daily caps and per-recipient allowlists would be ideal.
3. **Settlement observability:** A simple `GET /v1/transfers/{id}` with
   stable status enums (`pending` → `settled`) and an explorer link in the
   response would have saved us from building a mock settlement-state machine.
4. **Testnet friction:** Clear Arc testnet faucet instructions (USDC + native
   gas) for EVM toolchains would shorten the credential→live-transaction path
   materially.
5. **What we love:** The WaaS model (API-managed keys, no raw private keys on
   the developer side) aligns perfectly with our security model — the policy
   layer can authorize transfers without ever holding a key.
