# Konnex Adapter — SDK Research & Integration Status

> Phase 8 deliverable (TESTING_PLAN.md §14). Status: **STUB — SDK surface re-verified 2026-11-01; live integration still blocked.**
> Research dates: 2026-08-09 (initial) and 2026-11-01 (re-verification). Every claim below was checked against primary sources.

## 0. Re-verification 2026-11-01 (supersedes the blockers listed in §1 where they conflict)

| # | Check | Result |
|---|---|---|
| 1 | `https://docs.konnex.world/sdk/sdk.md` | **200 OK** — SDK overview is live |
| 2 | `https://docs.konnex.world/sdk/python.md` | **200 OK** — documents `from konnex import KonnexClient` |
| 3 | `https://docs.konnex.world/sdk/http.md` | **200 OK** — three endpoints, listed below |
| 4 | `https://docs.konnex.world/llms.txt` | **200 OK** — full docs index |
| 5 | `git ls-remote https://github.com/konnex-world/konnex` | **`Repository not found`** — the documented source-install path cannot be followed |
| 6 | `pip index versions konnex` | **No matching distribution found** — no published package |

**Documented Python SDK surface** (`docs.konnex.world/sdk/python`):

```python
from konnex import KonnexClient
client = KonnexClient()

job_id = client.tasks.submit(subnet="sn.roboarm.sim", prompt="...",
                             reward_usd1=12.5, stake_usd1=5, deadline_s=120)
client.miners.register(subnet="sn.roboarm.sim", wasm_path="./out/policy.wasm",
                       kpi={"success": ">=0.98", "time_s": "<=120"}, stake_usd1=10)
score = client.validators.verify(job_id=job_id, bundle_path="./powp.zip")
```

(Note the documented kwarg spelling `reward_usd1` / `stake_usd1`; the HTTP API
uses `rewardStable` / `stakeStable` for the same fields. Treat both as
unconfirmed until the client source is inspectable.)

**Documented HTTP surface** (`docs.konnex.world/sdk/http`, JSON over HTTPS, `/api/v1`):

| Endpoint | Body fields |
|---|---|
| `POST /api/v1/tasks` | `subnet`, `prompt`, `rewardStable`, `stakeStable`, `deadline` |
| `POST /api/v1/miners/models` | `subnet`, `modelUri`, `kpi`, `stakeStable` |
| `POST /api/v1/validators/verify` | `jobId`, `bundleUri` |

**Still undocumented — therefore still STUB:**

- No endpoint or SDK method for querying KNX rewards (`query_rewards`).
- No endpoint or SDK method for submission status (`get_submission_status`).
- No documented authentication scheme (base URL and auth are "deployment-specific"),
  and no testnet API key is available to this repository.

The Python SDK client remains source-unavailable (monorepo 404), but the
documented HTTP surface IS implemented in `protocol/konnex/real_provider.py`
(`RealKonnexProvider`): `submit_mission` → POST /api/v1/tasks,
`submit_evaluation`/`publish_proof` → POST /api/v1/validators/verify. The two
methods without a documented endpoint (`query_rewards`, `get_submission_status`)
remain STUBs. Status: PARTIAL — HTTP-based, SDK client still source-only.

## 5. Additional repos inspected (2026-11-02)

The following repos were provided for SDK research:

| Repo | What it actually is | Relevance to this adapter |
|---|---|---|
| `konnex-world/konnex-chain-sdk` | A fork of **bittensor** (Substrate L1 client). Provides `bittensor as bt`, subnets, metagraph, axons. | NOT the Konnex Python REST client (`from konnex import KonnexClient`). Subnets use `import bittensor as bt`, not the documented HTTP SDK. No `/api/v1` endpoints here. |
| `konnex-world/knx-subnet-drone-navigation` | A bittensor **subnet** (miner/validator neurons). Uses `bittensor as bt`. | Reference for how a Konnex subnet is structured (miner.py, validator.py, protocol.py). Does not contain a REST client. |
| `konnex-world/konnex-chain-subtensor` | Substrate node (chain). | Infrastructure; not needed for this adapter. |
| `konnex-world/knx-openclaw` | Not inspected (likely tooling). | Unknown. |

Conclusion: the documented `KonnexClient` (HTTP REST, `from konnex import KonnexClient`)
is NOT in any of these repos. It lives in the private monorepo `konnex-world/konnex`
(sdk/python-client), which returns 404. The HTTP API docs are the only verified
surface, and `RealKonnexProvider` is implemented against those. Full integration
requires SDK access.

---

---

## 1. Verified Findings

| # | Question | Finding | Verified via |
|---|---|---|---|
| 1 | Does `docs.konnex.network` exist? | **NO** — DNS/site lookup fails | Direct check |
| 2 | Does `gitbook.konnex.network` exist? | **NO** — DNS/site lookup fails | Direct check |
| 3 | What is the official docs URL? | **`https://docs.konnex.world/`** | docs redirects + whitepaper assets |
| 4 | Is there a Python SDK on PyPI? | **NO** public package under `konnex` / `konnex-network` | PyPI search |
| 5 | Is there an npm package? | **NOT VERIFIED** — none found in official docs | Docs search |
| 6 | How is the SDK installed? | From source, inside the Konnex monorepo:<br>`git clone https://github.com/konnex-world/konnex.git`<br>`cd konnex && pip install -e ./sdk/python-client ./sdk/cli ./tools` | Official docs |
| 7 | Python import | `from konnex import KonnexClient` | Official docs |
| 8 | HTTP API base path | JSON over HTTPS, prefix **`/api/v1/`** | docs.konnex.world/sdk/http |
| 9 | Known endpoints | `POST /api/v1/tasks` · `POST /api/v1/miners/models` · `POST /api/v1/validators/verify` | docs.konnex.world/sdk/http |
| 10 | On-chain / RPC | Testnet RPC `wss://testnet-rpc1.konnex.world:39944`; hotkey registration via Bittensor CLI | Docs |
| 11 | GitHub org | **`konnex-world`** — `konnex` (monorepo), `knx-subnet-drone-navigation` | GitHub |

**Net result:** an official Konnex SDK *exists* (Python client, source-install only, no published PyPI/npm release), but this repository has **not** integrated it. Per SYSTEM_PROMPT.md §6.3, no Konnex API calls may be invented, so `KonnexAdapter` remains a STUB that raises `NotImplementedError` with `# TODO: verify Konnex SDK <method>()`.

---

## 2. Adapter Boundary Contract

`protocol/konnex/adapter.py` accepts **only** these types (TESTING_PLAN.md §14, AGENTS.md §3.2):

| Allowed in | Never allowed in |
|---|---|
| `policy_id: str` | `RobotState` |
| `policy_hash: str` (SHA-256) | Gazebo world handles |
| `submission_id / eval_id: str` | ROS 2 node references |
| `score: float`, `dict[str, object]` (status payloads) | Raw trajectory arrays (summarize → hash) |
| `MissionMetadata` (protocol/konnex/models.py) | Any type from `robotics/`, `simulation/`, `ml/`, `fleet/` |
| `EvaluationArtifact` (validator/reproducibility/artifact.py) | — |

Enforcement:
- Signature-boundary test introspects every public method's annotations (`test_adapter_boundary_enforced`).
- Grep test asserts `robotics/`, `simulation/`, `ml/`, `fleet/` contain **zero** imports of `protocol.konnex`.
- Reverse grep test asserts `protocol/konnex/` imports **no** simulator packages (`robotics`, `simulation`, `ml`, `fleet`, `rclpy`, `gazebo`).

---

## 3. Adapter API (STUB surface, TESTING_PLAN.md §14)

| Method | Signature | Returns |
|---|---|---|
| `submit_mission` | `(metadata: MissionMetadata)` | `mission_id: str` |
| `submit_policy` | `(policy_id: str, policy_hash: str, metadata: MissionMetadata \| None)` | `registration_id: str` |
| `submit_evaluation` | `(policy_id: str, eval_id: str, score: float, artifact_hash: str)` | `submission_id: str` |
| `publish_proof` | `(artifact: EvaluationArtifact)` | `tx_hash: str` |
| `query_rewards` | `(policy_id: str)` | `rewards: float` |
| `get_submission_status` | `(submission_id: str)` | `dict[str, object]` |

All methods:
1. Validate inputs (empty/blank ids → `KonnexAdapterError`).
2. Log the call via **structlog**.
3. Raise `NotImplementedError("# TODO: verify Konnex SDK <method>()")`.

`KonnexAdapterError` is the single exception type for adapter-level failures.

---

## 4. Integration Plan (when the SDK becomes available)

1. Obtain a working source of the client — the documented `konnex-world/konnex`
   GitHub URL answered **404** on 2026-11-01, and no PyPI/npm package exists.
2. Verify the import surface (`from konnex import KonnexClient`) and its real method names against `docs.konnex.world`.
3. Map each stub method to the confirmed SDK call + HTTP endpoint. Current
   best-effort mapping from the documented surface:
   `submit_mission` → `client.tasks.submit` / `POST /api/v1/tasks`;
   `submit_policy` → `client.miners.register` / `POST /api/v1/miners/models`;
   `publish_proof` / `submit_evaluation` → `client.validators.verify` /
   `POST /api/v1/validators/verify` (bundle URI); `query_rewards` and
   `get_submission_status` have **no documented counterpart** and stay STUB
   until one appears.
4. Add `konnex` to `requirements.txt` (source install, exact commit pinned) — or vendor a published package once one exists.
5. Replace the `NotImplementedError` bodies with real calls; keep the boundary + logging intact.
6. Add a live integration test gated by an env flag (e.g. `KONNEX_LIVE_TEST=1`) so CI stays hermetic; the mocked/STUB tests remain the default gate.
7. Update `docs/protocol.md`, `docs/requirements.md` §7, and this file's Status line.

---

*The adapter is a deliberate STUB, not a shortcut: Law 1 (never fabricate) and SYSTEM_PROMPT.md §6.3 (never invent API calls) bind this phase.*
