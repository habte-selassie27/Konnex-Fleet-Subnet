"""Backend configuration — environment-driven (AGENTS.md §3.5)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All backend configuration; every value overridable via environment/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    version: str = "0.1.0"
    environment: str = "development"
    fleet_api_key: str = "dev-only-key"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "sqlite+aiosqlite:///./fleet_dev.db"
    artifact_dir: Path = Path("./data/artifacts")
    minio_endpoint: str = ""  # empty -> local artifact store
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "fleet-artifacts"
    minio_secure: bool = False
    robot_count: int = 5
    task_count: int = 20
    seed: int = 42
    policy: str = "nearest"
    # Simulation mode: "headless" (deterministic in-process sim, default) or
    # "gazebo" (start the optional ROS 2 bridge scaffolding beside the Gazebo
    # container; the fleet loop remains headless until GazeboRobotAdapter is
    # wired into FleetAppState — Phase 2 follow-up, docs/simulation.md §5).
    sim_mode: str = "headless"
    ros_domain_id: int = 42
    # Konnex integration mode: "disabled" (off), "mock" (local rewards), "real" (SDK — STUB)
    konnex_provider: str = "disabled"
    konnex_endpoint: str = ""
    konnex_api_key: str = ""
    # Agentic payment layer (Arc + Circle USDC) — see docs/payments.md
    # Provider mode: "mock" (default, in-process USDC/Arc simulation labeled
    # MOCK/DEMO) | "real" (Circle Wallets REST + Arc JSON-RPC — implemented,
    # requires credentials) | "disabled" (payment API refuses to start)
    payment_provider: str = "mock"
    payment_currency: str = "USDC"
    payment_fleet_id: str = "FLEET-017"
    payment_daily_budget_usdc: float = 500.0
    payment_max_tx_usdc: float = 250.0
    payment_wallet_id: str = "fleet-agent-wallet-001"
    payment_wallet_initial_balance_usdc: float = 1000.0
    # Real-mode settlement target on Arc (required for PAYMENT_PROVIDER=real).
    # The provider catalog addresses are deterministic placeholders, so a real
    # deployment must name the wallet that receives the USDC.
    payment_destination_address: str = ""
    # Live fleet -> payment bridge: turns real mission telemetry (low battery,
    # failed robot) into agent decisions + persisted transactions.
    payment_live_bridge: bool = True
    payment_low_battery_threshold: float = 0.20  # matches FailureDetector warning tier
    payment_bridge_interval_s: float = 2.0
    # Circle Wallets (required for PAYMENT_PROVIDER=real) — see docs/payments.md
    circle_api_key: str = ""
    circle_entity_secret: str = ""
    circle_token_id: str = ""
    circle_wallet_set_id: str = ""
    circle_wallet_config_id: str = ""
    # Arc settlement (required for PAYMENT_PROVIDER=real) — see docs/payments.md
    # Chain ids: 5042 (mainnet) / 5042002 (testnet); explorer derived if empty.
    arc_rpc_url: str = ""
    arc_chain_id: str = ""
    arc_contract_address: str = ""
    arc_explorer_url: str = ""
