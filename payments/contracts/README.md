# FleetPayment Contract — Deployment Notes

Status: **NOT DEPLOYED** — reference contract for the demo. The agentic
payment flow runs against the mock provider; this contract documents the
real on-chain settlement step (docs/payments.md §Contract).

## What it does

- Only the authorized `fleetAgent` wallet can call `payProvider(...)`.
- Transfers `amount` USDC (6 decimals) from the agent wallet to the provider.
- Emits `PaymentSettled(provider, amount, fleetId, vehicleId, serviceId, ts)`
  so the blockchain payment is traceable back to the fleet event.

## Compile

Requires solc 0.8.20+ or a Hardhat/Foundry toolchain:

```bash
solc --optimize --bin --abi payments/contracts/FleetPayment.sol -o build/
# or
npx hardhat compile   # with hardhat.config pointing at this contract
```

## Deploy (real Arc chain)

1. Get an Arc RPC URL + chain id (env: `ARC_RPC_URL`, `ARC_CHAIN_ID`).
2. Deploy USDC (or use the existing USDC token address on that chain).
3. Deploy with the USDC address + the fleet-agent wallet address:

```js
const FleetPayment = await ethers.getContractFactory("FleetPayment");
const contract = await FleetPayment.deploy(usdcAddress, agentWalletAddress);
await contract.deployed();
```

4. The agent wallet must `approve(contract.address, amount)` the USDC
   token before the first `payProvider` call (ERC-20 allowance).
5. Set `ARC_CONTRACT_ADDRESS` in the backend environment.

## Metadata encoding

`fleetId` / `vehicleId` / `serviceId` are `bytes32` — encode strings with
`ethers.utils.id("FLEET-017")` (keccak256). The off-chain receipt keeps the
plaintext ids so the UI can render them.
