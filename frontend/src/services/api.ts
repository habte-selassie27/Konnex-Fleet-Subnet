// Typed REST client (AGENTS.md §1.6: all fetch calls live here, never in
// components). Base URL resolved from VITE_API_URL or the dev proxy.
import type {
  AgentDecision,
  BenchmarkResult,
  EvaluationResult,
  HealthStatus,
  PaymentAuthorizeResult,
  PaymentDemoResult,
  PaymentEventInput,
  PaymentSummary,
  PaymentTransaction,
  PaymentWallet,
  PolicyRecord,
  PolicySubmitPayload,
  RewardSplit,
  RobotFailureResponse,
  RobotState,
  ValidatorContextSnapshot,
  ValidatorNetwork,
} from '../types'

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'
// Same key source as the WebSocket hook (useFleetSocket) — the backend's
// mutating endpoints require the X-Fleet-API-Key header.
const API_KEY = import.meta.env.VITE_WS_API_KEY ?? 'dev-only-key'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      'X-Fleet-API-Key': API_KEY,
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${response.statusText} (${path})`)
  }
  return (await response.json()) as T
}

export const api = {
  /** Live snapshot of all robot states. Trailing slash avoids the 307 redirect. */
  getRobots(): Promise<RobotState[]> {
    return request<RobotState[]>('/robots/')
  },

  /** Fetch a single evaluation result. */
  getEvaluation(evaluationId: string): Promise<EvaluationResult> {
    return request<EvaluationResult>(`/evaluations/${evaluationId}`)
  },

  /** List all evaluations. */
  listEvaluations(): Promise<EvaluationResult[]> {
    return request<EvaluationResult[]>('/evaluations/')
  },

  /** Inject a failure into a robot (Phase 5 API). */
  failRobot(robotId: string, failureType: string): Promise<RobotFailureResponse> {
    return request<RobotFailureResponse>(`/robots/${robotId}/fail`, {
      method: 'POST',
      body: JSON.stringify({ failure_type: failureType }),
    })
  },

  /** List genuinely registered, executable allocator policies. */
  getPolicies(): Promise<Array<{ id: string; name: string; algorithm: string; available: boolean }>> {
    return request<Array<{ id: string; name: string; algorithm: string; available: boolean }>>(
      '/missions/policies'
    )
  },

  /** Start a backend mission (auto-capture produces a benchmark row). */
  createMission(payload: {
    robot_count: number
    task_count: number
    seed: number
    policy: string
    time_limit_s?: number
  }): Promise<{ id: string }> {
    return request<{ id: string }>('/missions/', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  /** Liveness probe. */
  getHealth(): Promise<HealthStatus> {
    return request<HealthStatus>('/health')
  },

  // ─── Agentic payments (Arc + Circle USDC) ───────────────────────────

  /** Agent observes a fleet event and returns a provider decision. */
  paymentQuote(event: PaymentEventInput): Promise<AgentDecision> {
    return request<AgentDecision>('/payments/quote', {
      method: 'POST',
      body: JSON.stringify(event),
    })
  },

  /** Policy-gate an agent payment request. */
  paymentAuthorize(payload: {
    vehicle_id: string
    provider_id: string
    service: string
    amount_usdc: number
    currency?: string
    reason: string
    max_allowed_usdc?: number
    decision_rationale?: string
    fleet_id?: string
  }): Promise<PaymentAuthorizeResult> {
    return request<PaymentAuthorizeResult>('/payments/authorize', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  /** Execute an authorized intent: USDC transfer + Arc settlement. */
  paymentExecute(intentId: string): Promise<PaymentTransaction> {
    return request<PaymentTransaction>('/payments/execute', {
      method: 'POST',
      body: JSON.stringify({ intent_id: intentId }),
    })
  },

  /** Run the deterministic end-to-end demo scenario. */
  paymentDemo(): Promise<PaymentDemoResult> {
    return request<PaymentDemoResult>('/payments/demo', { method: 'POST' })
  },

  /** Agent wallet snapshot. */
  getPaymentWallet(): Promise<PaymentWallet> {
    return request<PaymentWallet>('/payments/wallet')
  },

  /** Agent transaction history (newest first). */
  getPaymentTransactions(): Promise<PaymentTransaction[]> {
    return request<PaymentTransaction[]>('/payments/transactions')
  },

  /** Aggregate agent-economy stats. */
  getPaymentSummary(): Promise<PaymentSummary> {
    return request<PaymentSummary>('/payments/summary')
  },

  // ─── Benchmarks / policies / validator context ───────────────────────

  /**
   * Measured benchmark rows from GET /experiments/benchmarks — only the runs
   * `make benchmark` actually produced (frontend never fabricates rows).
   */
  listBenchmarks(): Promise<BenchmarkResult[]> {
    return request<BenchmarkResult[]>('/experiments/benchmarks')
  },

  /**
   * Submitted policies. The backend router is a STUB (Phase 2) — callers must
   * surface the error honestly (PolicyRegistry shows "Policies unavailable").
   */
  listPolicies(): Promise<PolicyRecord[]> {
    return request<PolicyRecord[]>('/policies/')
  },

  /** Submit a policy artifact; the backend re-computes the SHA-256 hash. */
  submitPolicy(payload: PolicySubmitPayload): Promise<PolicyRecord> {
    return request<PolicyRecord>('/policies/', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  /**
   * Projected reward shares per policy. No backend route yet — the error is
   * surfaced as "Reward split unavailable" rather than a fabricated split.
   */
  getRewardSplit(): Promise<RewardSplit> {
    return request<RewardSplit>('/evaluations/reward-split')
  },

  /**
   * Fleet-subnet validator network: registry plus the current mission's
   * independent role assessments and consensus (real evidence only).
   */
  getValidatorNetwork(): Promise<ValidatorNetwork> {
    return request<ValidatorNetwork>('/validators/network')
  },

  /** Validator framing for one evaluation (STUB values until adapter wired). */
  getValidatorContext(evaluationId: string): Promise<ValidatorContextSnapshot> {
    return request<ValidatorContextSnapshot>(
      `/validators/evaluations/${evaluationId}/context`,
    )
  },
}
