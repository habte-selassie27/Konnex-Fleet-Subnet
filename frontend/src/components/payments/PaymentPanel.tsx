// PaymentPanel — "FleetPay Agent" agentic economy panel (Arc + Circle USDC).
// Shows the full story: agent wallet, agent decisions with provider
// comparison, and payment history. One button runs the deterministic
// end-to-end demo (event -> decision -> policy -> USDC -> Arc -> receipt).
// Everything in the default mock mode is explicitly labeled MOCK/DEMO.
import { useEffect } from 'react'
import { CircleDollarSign, Loader2, PlayCircle } from 'lucide-react'
import { usePaymentStore } from '../../store/paymentStore'
import { AgentDecisionCard } from './AgentDecisionCard'
import { TransactionList } from './TransactionList'
import { WalletCard } from './WalletCard'

export function PaymentPanel() {
  const wallet = usePaymentStore((s) => s.wallet)
  const summary = usePaymentStore((s) => s.summary)
  const transactions = usePaymentStore((s) => s.transactions)
  const lastDemo = usePaymentStore((s) => s.lastDemo)
  const latestDecision = usePaymentStore((s) => s.latestDecision)
  const loading = usePaymentStore((s) => s.loading)
  const error = usePaymentStore((s) => s.error)
  const refresh = usePaymentStore((s) => s.refresh)
  const runDemo = usePaymentStore((s) => s.runDemo)
  const clearError = usePaymentStore((s) => s.clearError)

  useEffect(() => {
    void refresh()
  }, [refresh])

  const decisions = lastDemo?.decisions.length
    ? lastDemo.decisions
    : latestDecision
      ? [latestDecision]
      : []

  return (
    <section
      aria-label="Agent economy — FleetPay"
      className="rounded-xl border border-violet-700/40 bg-slate-900/80 p-4"
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <CircleDollarSign className="h-4 w-4 text-violet-400" aria-hidden="true" />
            FleetPay Agent — Agentic Economy
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Fleet events → AI decisions → policy-gated USDC payments settled on Arc
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-amber-500/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-amber-400">
            MOCK / DEMO
          </span>
          <span className="rounded-full bg-violet-500/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-violet-400">
            Arc
          </span>
          <span className="rounded-full bg-sky-500/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-sky-400">
            Circle USDC
          </span>
          <button
            type="button"
            onClick={() => void runDemo()}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Run end-to-end demo scenario"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <PlayCircle className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {loading ? 'Running…' : 'Run demo'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-3 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
          <button
            type="button"
            onClick={clearError}
            className="ml-2 font-semibold underline hover:text-red-200"
            aria-label="Dismiss error"
          >
            dismiss
          </button>
        </div>
      )}

      {/* Content */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1">
          {wallet ? (
            <WalletCard wallet={wallet} summary={summary} />
          ) : (
            <div className="rounded-xl border border-slate-700/60 bg-slate-900 p-4 text-center text-xs text-slate-500">
              {loading ? 'Loading wallet…' : 'No wallet data yet'}
            </div>
          )}
        </div>

        <div className="space-y-4 lg:col-span-2">
          <div>
            <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Agent decisions
            </h3>
            {decisions.length === 0 ? (
              <div className="rounded-xl border border-slate-700/60 bg-slate-900 p-4 text-center text-xs text-slate-500">
                No agent decisions yet — run the demo to see the agent evaluate providers.
              </div>
            ) : (
              <div className="space-y-3">
                {decisions.map((decision) => (
                  <AgentDecisionCard key={`${decision.vehicle_id}-${decision.service}`} decision={decision} />
                ))}
              </div>
            )}
          </div>

          <TransactionList transactions={transactions} />
        </div>
      </div>
    </section>
  )
}
