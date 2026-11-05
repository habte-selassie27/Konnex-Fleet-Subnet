// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.20;

/// @title FleetPayment — minimal payment/settlement contract for the
///        Agentic Fleet Payment Layer (Ignyte Stablecoin Commerce Stack).
/// @notice Records USDC settlements between an autonomous fleet agent and
///         service providers, keyed by fleet/vehicle/service metadata so a
///         blockchain payment can be traced back to the fleet event that
///         caused it (spec §4).
/// @dev    Status: reference contract — NOT deployed. The real deployment
///         needs an Arc RPC, the USDC token address on that chain, and a
///         funded fleet-agent wallet. Steps: docs/payments.md §Contract.
///         The off-chain PaymentPolicy (payments/policy.py) is the primary
///         gatekeeper; this contract enforces the on-chain minimum
///         (authorized caller + nonzero amount + transfer success).
contract FleetPayment {
    /// @notice Circle USDC (ERC-20) token address.
    address public immutable usdc;

    /// @notice Authorized fleet-agent wallet that may call payProvider().
    address public immutable fleetAgent;

    /// @dev Emitted when a provider payment settles on-chain.
    event PaymentSettled(
        address indexed provider,
        uint256 indexed amount,
        bytes32 indexed fleetId,
        bytes32 vehicleId,
        bytes32 serviceId,
        uint256 timestamp
    );

    /// @param _usdc       USDC (ERC-20) token address on the deployment chain.
    /// @param _fleetAgent  Fleet agent wallet allowed to pay providers.
    constructor(address _usdc, address _fleetAgent) {
        require(_usdc != address(0), "FleetPayment: zero usdc");
        require(_fleetAgent != address(0), "FleetPayment: zero agent");
        usdc = _usdc;
        fleetAgent = _fleetAgent;
    }

    /// @notice Pay a provider `amount` USDC for `serviceId` on behalf of a fleet.
    /// @param provider   Recipient address (validated off-chain by the policy).
    /// @param amount     USDC amount (6 decimals).
    /// @param fleetId    Fleet identifier (e.g. keccak256("FLEET-017")).
    /// @param vehicleId  Vehicle identifier (e.g. keccak256("TRUCK-42")).
    /// @param serviceId  Service identifier (e.g. keccak256("charging")).
    function payProvider(
        address provider,
        uint256 amount,
        bytes32 fleetId,
        bytes32 vehicleId,
        bytes32 serviceId
    ) external {
        require(msg.sender == fleetAgent, "FleetPayment: not authorized agent");
        require(provider != address(0), "FleetPayment: zero provider");
        require(amount > 0, "FleetPayment: zero amount");
        require(
            IERC20(usdc).transferFrom(msg.sender, provider, amount),
            "FleetPayment: transfer failed"
        );
        emit PaymentSettled(provider, amount, fleetId, vehicleId, serviceId, block.timestamp);
    }
}

/// @dev Minimal ERC-20 interface — only the call the contract needs.
interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}
