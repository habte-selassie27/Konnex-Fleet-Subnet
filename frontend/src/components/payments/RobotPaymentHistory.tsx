// RobotPaymentHistory — the agent-economy ledger split by robot. Every robot
// on the live fleet roster gets a card, including robots with no payments
// yet, so "which robot spent what, and why" is answerable at a glance.
import { Bot, ExternalLink, History } from 'lucide-react'
import type { AgentDecision, PaymentTransaction, RobotPaymentAccount } from '../../types'

function formatUsdc(value: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function shortHash(hash: string): string {
  if (!hash) return '—'
  if (hash.length <= 16) return hash
  return `${hash.slice(0, 10)}…${hash.slice(-6)}`
}

function formatTime(unixSeconds: number | null): string {
  if (unixSeconds === null) return '—'
  return new Date(unixSeconds * 1000).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function statusClass(status: string): string {
  if (status === 'settled') return 'text-emerald-400'
  if (status === 'failed') return 'text-red-400'
  return 'text-amber-400'
}

function RobotPaymentRow({ transaction }: { transaction: PaymentTransaction }) {
  return (
    <li className="flex items-center justify-between gap-2 border-b border-line/50 py-1 last:border-b-0">
      <span className="min-w-0">
        <span className="block truncate text-[11px] text-fg">
          {transaction.provider_name || transaction.provider_id}
        </span>
        <span className="block truncate text-[10px] uppercase tracking-wide text-subtle">
          {transaction.service} · <span className={statusClass(transaction.settlement_status)}>
            {transaction.settlement_status}
          </span>{' '}
          · {formatTime(transaction.settled_at ?? transaction.executed_at)}
        </span>
      </span>
      <span className="flex shrink-0 items-center gap-1.5">
        <span className="font-mono text-[11px] text-emerald-400">
          ${formatUsdc(transaction.amount_usdc)}
        </span>
        {transaction.tx_hash && (
          <a
            href={transaction.explorer_url || undefined}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-0.5 font-mono text-[10px] text-sky-400 hover:text-sky-300"
            aria-label={`Open ${transaction.tx_hash} in explorer`}
            title={transaction.tx_hash}
          >
            {shortHash(transaction.tx_hash)}
            <ExternalLink className="h-2.5 w-2.5" aria-hidden="true" />
          </a>
        )}
      </span>
    </li>
  )
}

function lastDecisionText(decision: AgentDecision | undefined): string {
  if (!decision) return ''
  const action = decision.no_action
    ? 'no action'
    : `paid ${formatUsdc(decision.amount_usdc)} USDC`
  return `${decision.service} → ${action}`
}

function RobotPaymentCard({ account }: { account: RobotPaymentAccount }) {
  const latestDecision = account.decisions[0]
  return (
    <article
      aria-label={`Payment history for ${account.robot_id}`}
      className="rounded-xl border border-line/60 bg-panel p-3"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="flex items-center gap-1.5 font-mono text-xs font-semibold text-fg">
          <Bot className="h-3.5 w-3.5 text-sky-400" aria-hidden="true" />
          {account.robot_id}
        </h3>
        <span className="font-mono text-sm font-semibold text-emerald-400">
          ${formatUsdc(account.total_usdc)}
        </span>
      </div>

      <p className="mt-1 text-[10px] uppercase tracking-wide text-subtle">
        {account.payment_count} payment{account.payment_count === 1 ? '' : 's'} ·{' '}
        {account.settled_count} settled
        {account.pending_count > 0 && ` · ${account.pending_count} pending`}
        {account.failed_count > 0 && ` · ${account.failed_count} failed`} ·{' '}
        {account.decision_count} decision{account.decision_count === 1 ? '' : 's'}
      </p>

      {account.transactions.length === 0 ? (
        <p className="mt-3 text-[11px] leading-relaxed text-subtle">
          No payments yet — the agent pays only when this robot reports a low battery or a
          failure.
        </p>
      ) : (
        <ul className="mt-2">
          {account.transactions.slice(0, 3).map((transaction) => (
            <RobotPaymentRow key={transaction.id} transaction={transaction} />
          ))}
        </ul>
      )}

      {latestDecision && (
        <p
          className="mt-2 line-clamp-2 border-t border-line/50 pt-2 text-[10px] leading-relaxed text-muted"
          title={latestDecision.rationale}
        >
          {lastDecisionText(latestDecision)} — {latestDecision.rationale}
        </p>
      )}
    </article>
  )
}

interface RobotPaymentHistoryProps {
  accounts: RobotPaymentAccount[]
}

export function RobotPaymentHistory({ accounts }: RobotPaymentHistoryProps) {
  return (
    <section aria-label="Payment history by robot" className="mt-4">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
        <History className="h-3.5 w-3.5" aria-hidden="true" />
        Payment History by Robot
      </h2>
      {accounts.length === 0 ? (
        <p className="mt-3 text-xs text-subtle">No fleet roster available yet.</p>
      ) : (
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {accounts.map((account) => (
            <RobotPaymentCard key={account.robot_id} account={account} />
          ))}
        </div>
      )}
    </section>
  )
}
