// Frontend contract types (AGENTS.md §1.2 types/). These mirror the backend
// payloads documented in docs/dashboard.md §3-4. No `any` — strict mode.

export interface Vector2D {
  x: number
  y: number
}

export type NavState = 'idle' | 'moving' | 'blocked' | 'charging' | 'failed'
export type CommState = 'online' | 'degraded' | 'offline'
export type MissionStatus = 'pending' | 'running' | 'complete' | 'failed' | 'timed_out'
export type TaskStatus =
  | 'pending'
  | 'assigned'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'timed_out'

export interface RobotState {
  id: string
  position: Vector2D
  orientation: number
  velocity: Vector2D
  battery_pct: number
  current_task_id: string | null
  nav_state: NavState
  in_collision: boolean
  comm_state: CommState
  timestamp: number
  distance_traveled: number
}

export interface MissionUpdate {
  mission_id: string
  status: MissionStatus
  policy: string
  completed_tasks: number
  total_tasks: number
  collision_count: number
  failure_count: number
  elapsed_seconds: number
  energy_consumed: number
  popw_score: number | null
}

export interface EnergySample {
  t: number
  energy: number
}

export interface TaskState {
  id: string
  pickup: Vector2D
  delivery: Vector2D
  priority: 'low' | 'medium' | 'high'
  status: TaskStatus
  assigned_robot_id: string | null
}

export interface RobotStateUpdateEvent {
  type: 'ROBOT_STATE_UPDATE'
  robot_id: string
  state: RobotState
  timestamp: number
}

export interface MissionUpdateEvent extends MissionUpdate {
  type: 'MISSION_UPDATE'
  timestamp: number
}

export interface TaskCompletedEvent {
  type: 'TASK_COMPLETED'
  task_id: string
  timestamp: number
}

export interface CollisionDetectedEvent {
  type: 'COLLISION_DETECTED'
  robot_id: string
  near_miss: boolean
  timestamp: number
}

export interface SimulatorOfflineEvent {
  type: 'SIMULATOR_OFFLINE'
  reason: string
  timestamp: number
}

export type FleetEvent =
  | RobotStateUpdateEvent
  | MissionUpdateEvent
  | TaskCompletedEvent
  | CollisionDetectedEvent
  | SimulatorOfflineEvent

export interface EvaluationResult {
  id: string
  policy_id: string
  status: string
  final_score: number | null
  artifact_hash: string
  artifact_url: string
}

export interface HealthStatus {
  status: string
}

export interface RobotFailureResponse {
  robot_id: string
  failure_type: string
  injected: boolean
}

// ─── Agentic payment layer (Arc + Circle USDC) ─────────────────────────────

export type PaymentServiceType = 'charging' | 'fueling' | 'maintenance' | 'inspection'

export interface ProviderQuote {
  provider_id: string
  name: string
  service: PaymentServiceType
  price_usdc: number
  distance_km: number
  rating: number
  address: string
  score: number
  selected: boolean
}

export interface AgentDecision {
  fleet_id: string
  vehicle_id: string
  service: PaymentServiceType
  amount_usdc: number
  rationale: string
  no_action: boolean
  selected_provider_id: string
  quotes: ProviderQuote[]
}

export interface PaymentTransaction {
  id: string
  intent_id: string
  fleet_id: string
  vehicle_id: string
  provider_id: string
  provider_name: string
  provider_address: string
  service: PaymentServiceType
  amount_usdc: number
  currency: string
  status: string
  settlement_status: string
  tx_hash: string
  receipt_id: string
  reason: string
  decision_rationale: string
  explorer_url: string
  is_mock: boolean
  created_at: number
  executed_at: number | null
  settled_at: number | null
}

export interface PaymentWallet {
  wallet_id: string
  currency: string
  balance_usdc: number
  daily_budget_usdc: number
  spent_today_usdc: number
  remaining_today_usdc: number
  max_tx_usdc: number
  is_mock: boolean
  /** Settlement network: "arc-mock" (simulation) or "arc-mainnet" / "arc-testnet". */
  network: string
}

export interface PaymentSummary {
  wallet: PaymentWallet
  autonomous_payments: number
  usdc_settled: number
  arc_transactions: number
  receipts: number
  rejected_intents: number
}

export interface PaymentDemoResult {
  decisions: AgentDecision[]
  transactions: PaymentTransaction[]
  summary: PaymentSummary
}

export interface PaymentAuthorizeResult {
  intent_id: string
  approved: boolean
  checks: Record<string, boolean>
  reasons: string[]
}

export interface PaymentEventInput {
  vehicle_id: string
  event_type: string
  battery_pct: number
  note?: string
}
