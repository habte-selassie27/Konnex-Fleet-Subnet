// Zustand store for the Agentic Payment Layer (Arc + Circle USDC demo).
// State is REST-driven (the backend is the source of truth): wallet snapshot,
// transaction history, the latest agent decision, and the last demo run.
// Components never call the API directly — they go through this store.
import { create } from 'zustand'
import { api } from '../services/api'
import type {
  AgentDecision,
  PaymentDemoResult,
  PaymentSummary,
  PaymentTransaction,
  PaymentWallet,
} from '../types'

interface PaymentState {
  wallet: PaymentWallet | null
  transactions: PaymentTransaction[]
  summary: PaymentSummary | null
  latestDecision: AgentDecision | null
  lastDemo: PaymentDemoResult | null
  loading: boolean
  error: string | null
  /** Load wallet + transactions + summary in parallel. */
  refresh: () => Promise<void>
  /** Run the deterministic end-to-end demo scenario, then refresh. */
  runDemo: () => Promise<PaymentDemoResult | null>
  clearError: () => void
}

export const usePaymentStore = create<PaymentState>((set) => ({
  wallet: null,
  transactions: [],
  summary: null,
  latestDecision: null,
  lastDemo: null,
  loading: false,
  error: null,

  refresh: async () => {
    set({ loading: true, error: null })
    try {
      const [wallet, transactions, summary] = await Promise.all([
        api.getPaymentWallet(),
        api.getPaymentTransactions(),
        api.getPaymentSummary(),
      ])
      set({ wallet, transactions, summary, loading: false })
    } catch (error) {
      set({
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to load payment state',
      })
    }
  },

  runDemo: async () => {
    set({ loading: true, error: null })
    try {
      const demo = await api.paymentDemo()
      const [wallet, transactions, summary] = await Promise.all([
        api.getPaymentWallet(),
        api.getPaymentTransactions(),
        api.getPaymentSummary(),
      ])
      set({
        wallet,
        transactions,
        summary,
        lastDemo: demo,
        latestDecision: demo.decisions[demo.decisions.length - 1] ?? null,
        loading: false,
      })
      return demo
    } catch (error) {
      set({
        loading: false,
        error: error instanceof Error ? error.message : 'Demo failed',
      })
      return null
    }
  },

  clearError: () => set({ error: null }),
}))
