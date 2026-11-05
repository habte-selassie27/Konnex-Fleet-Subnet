// WalletCard — agent wallet: USDC balance, daily budget progress, and
// agent-economy totals (autonomous payments, settled USDC, Arc txs).
import { Coins, Link2, Wallet, Zap } from 'lucide-react'
import type { PaymentSummary, PaymentWallet } from '../../types'

interface WalletCardProps {
  wallet: PaymentWallet
  summary: PaymentSummary | null
}

function formatUsdc(value: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function WalletCard({ wallet, summary }: WalletCardProps) {
  const spentPct =
    wallet.daily_budget_usdc > 0
      ? Math.min(100, (wallet.spent_today_usdc / wallet.daily_budget_usdc) * 100)
      : 0

  return (
    <section
      aria-label="Agent wallet"
      className="rounded-xl border border-slate-700/60 bg-slate-900 p-4"
    >
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
          <Wallet className="h-3.5 w-3.5" aria-hidden="true" />
          Agent Wallet
        </h2>
        {wallet.is_mock ? (
          <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-400">
            MOCK / DEMO
          </span>
        ) : (
          <span
            data-testid="wallet-live-badge"
            className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-400"
          >
            LIVE · {wallet.network}
          </span>
        )}
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="font-mono text-3xl font-semibold text-slate-100">
          {formatUsdc(wallet.balance_usdc)}
        </span>
        <span className="text-sm font-medium text-slate-400">{wallet.currency}</span>
      </div>
      <p className="mt-1 truncate font-mono text-[10px] text-slate-500">
        {wallet.wallet_id} · {wallet.network}
      </p>

      {/* Daily budget */}
      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="text-slate-500">Daily budget</span>
          <span className="font-mono text-slate-300">
            {formatUsdc(wallet.spent_today_usdc)} / {formatUsdc(wallet.daily_budget_usdc)}
          </span>
        </div>
        <div
          className="h-2 overflow-hidden rounded-full bg-slate-800"
          role="img"
          aria-label={`Daily budget ${Math.round(spentPct)}% spent`}
        >
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              spentPct > 80 ? 'bg-red-500' : spentPct > 50 ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${spentPct}%` }}
          />
        </div>
        <p className="mt-1 text-right font-mono text-xs text-slate-400">
          {formatUsdc(wallet.remaining_today_usdc)} remaining
        </p>
      </div>

      {/* Agent-economy totals */}
      <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-slate-800 pt-3">
        <div>
          <dt className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-slate-500">
            <Zap className="h-3 w-3" aria-hidden="true" />
            Payments
          </dt>
          <dd className="mt-0.5 font-mono text-lg font-semibold text-slate-100">
            {summary?.autonomous_payments ?? 0}
          </dd>
        </div>
        <div>
          <dt className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-slate-500">
            <Coins className="h-3 w-3" aria-hidden="true" />
            USDC settled
          </dt>
          <dd className="mt-0.5 font-mono text-lg font-semibold text-slate-100">
            {formatUsdc(summary?.usdc_settled ?? 0)}
          </dd>
        </div>
        <div>
          <dt className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-slate-500">
            <Link2 className="h-3 w-3" aria-hidden="true" />
            Arc txs
          </dt>
          <dd className="mt-0.5 font-mono text-lg font-semibold text-slate-100">
            {summary?.arc_transactions ?? 0}
          </dd>
        </div>
      </dl>
    </section>
  )
}
