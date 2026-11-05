// Typed REST client (AGENTS.md §1.6: all fetch calls live here, never in
// components). Base URL resolved from VITE_API_URL or the dev proxy.
import type {
  AgentDecision,
  EvaluationResult,
  HealthStatus,
  PaymentAuthorizeResult,
  PaymentDemoResult,
  PaymentEventInput,
  PaymentSummary,
  PaymentTransaction,
  PaymentWallet,
  RobotFailureResponse,
  RobotState,
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
}
