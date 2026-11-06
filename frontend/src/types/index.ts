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
  /** ScoreRoot/commitments framing when the validator posted one. */
  popw_commitments?: ValidatorScoreCommitments | null
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
  /** Backend-generated id when the decision was persisted — demo quotes may omit it. */
  id?: string | null
  /** Unix seconds when the decision was recorded — demo quotes may omit it. */
  timestamp?: number | null
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

// ─── Robot payment roster (per-robot ledger for RobotPaymentHistory) ─────────

export interface RobotPaymentAccount {
  robot_id: string
  total_usdc: number
  payment_count: number
  settled_count: number
  pending_count: number
  failed_count: number
  decision_count: number
  transactions: PaymentTransaction[]
  decisions: AgentDecision[]
}

// ─── Benchmarks (backend/schemas.py BenchmarkResult → GET /experiments/) ─────

export interface BenchmarkResult {
  experiment_id: string
  policy: string
  scenario_id: string
  /** Harness label, e.g. "FleetEnv" — empty when no unified-harness run exists. */
  harness: string
  robot_count: number
  n_runs: number
  seed_range: [number, number]
  /** null for unmeasured rows (SKIPPED) — never invented by the dashboard. */
  mean_popw_score: number | null
  std_popw_score: number | null
  mean_success_rate: number | null
  std_success_rate: number | null
  mean_collision_count: number | null
  std_collision_count: number | null
  mean_completion_time_s: number | null
  std_completion_time_s: number | null
  /** COMPLETE | SKIPPED | … */
  status: string
  skip_reason: string
  ran_at: string
  git_commit: string
  source: string
}

// ─── Policies (POST/GET /policies — backend router is a STUB) ────────────────

export interface PolicyRecord {
  id: string
  name: string
  version: string
  author: string
  algorithm: string
  /** SHA-256 of the artifact bytes, recomputed server-side. */
  policy_hash: string
  /** SUBMITTED | VERIFIED | REJECTED */
  status: string
  size_bytes: number
  /** true when the same artifact hash was submitted before. */
  duplicate: boolean
  artifact_url: string
  created_at: string
}

export interface PolicySubmitPayload {
  name: string
  version: string
  author: string
  algorithm: string
  policy_hash: string
  artifact_base64: string
}

// ─── Konnex scoring (validator framing) ──────────────────────────────────────

/** Configured estimate: Konnex does not publish its per-subnet weight vector. */
export interface KonnexWeights {
  task_match: number
  efficiency: number
  evidence_quality: number
}

/**
 * Konnex-aligned work score for one evaluation:
 * gate(safety) × (w1·task_match + w2·efficiency + w3·evidence).
 * A safety violation zeroes the whole score (safety_gate = 0).
 */
export interface KonnexScore {
  safety_gate: number
  safety_violations: number
  task_match: number
  efficiency: number
  evidence_quality: number
  final: number
  weights: KonnexWeights
}

// ─── Reward split (GET /evaluations/reward-split) ────────────────────────────

export interface RewardSplitEntry {
  policy_id: string
  evaluation_id: string
  score: number
  competitive_share: number
  winner_takes_most_share: number
  is_top: boolean
}

export interface RewardSplit {
  /** Largest winner-takes-most share (fractions of a unit pool). */
  top_share: number
  note?: string
  entries: RewardSplitEntry[]
}

// ─── Validator context (GET /validators/evaluations/{id}/context — STUB) ─────

/** ScoreRoot/commitments framing posted with an evaluation (or from context). */
export interface ValidatorScoreCommitments {
  scoreroot_hash: string
  commitments_url: string
  posted_at_ms: number | null
}

export type ValidatorEvaluatorStatus = 'ready' | 'scoring' | 'timed_out' | 'slashed'
export type ValidatorServingMode = 'idle' | 'serving'

export interface ValidatorStakeSnapshot {
  knx_staked: number
  knx_at_risk_after_slash: number
  stablecoin_settlement_assurance: number
  status: ValidatorEvaluatorStatus
}

export interface ValidatorServingSnapshot {
  mode: ValidatorServingMode
  active_request_id: string | null
  requests_since_reset: number
  last_checkpoint_ms: number | null
}

/**
 * Raw backend context shape. STUB values are honest placeholders (empty
 * ScoreRoot, 0.0 KNX) — the Konnex adapter populates them when verified.
 */
export interface ValidatorContextSnapshot {
  scoreroot_hash: string
  scoreroot_url: string
  commitments_url: string
  knx_staked: number
  knx_at_risk_after_slash: number
  stablecoin_settlement_assurance: number
  evaluator_status: string
  serving_mode: string
  active_request_id: string | null
  requests_since_reset: number
  last_checkpoint_ms: number | null
  _note?: string
  _source: string
}

// ─── Konnex-aligned validator network (GET /validators/network) ──────────────

export type ValidatorRole = 'execution' | 'safety' | 'performance'
export type ValidatorVerdict = 'PASS' | 'FAIL' | 'PENDING' | 'INCONCLUSIVE'
export type ConsensusDecision =
  | 'ACCEPTED'
  | 'REJECTED'
  | 'DISPUTED'
  | 'INCONCLUSIVE'
  | 'PENDING'

export interface ValidatorCheck {
  name: string
  passed: boolean
  detail: string
}

export interface ValidatorAssessment {
  validator_id: string
  role: ValidatorRole
  verdict: ValidatorVerdict
  /** null until the mission evidence is final — never a fabricated 0. */
  score: number | null
  checks: ValidatorCheck[]
  reason: string
}

export interface ValidatorConsensus {
  decision: ConsensusDecision
  accept_votes: number
  reject_votes: number
  validator_count: number
  reason: string
}

export interface MissionVerification {
  mission_id: string
  scenario_id: string
  policy: string
  mission_status: MissionStatus
  tasks_completed: number
  task_count: number
  collision_count: number
  failure_count: number
  elapsed_s: number
  time_limit_s: number
  energy_consumed: number
  /** SHA-256 of the canonical evidence manifest. */
  evidence_hash: string
  assessments: ValidatorAssessment[]
  consensus: ValidatorConsensus
}

export interface ValidatorIdentity {
  id: string
  role: ValidatorRole
  operator: string
  capabilities: string[]
  implementation: string
  status: string
}

/** Fleet-subnet validators are local; the Konnex protocol bridge is STUB. */
export interface KonnexValidatorBridge {
  adapter_status: string
  docs_url: string
  note: string
}

export interface ValidatorNetwork {
  validators: ValidatorIdentity[]
  konnex: KonnexValidatorBridge
  verification: MissionVerification | null
}
