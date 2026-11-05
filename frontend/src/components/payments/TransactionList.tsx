// TransactionList — agent payment history: vehicle, provider, USDC amount,
// settlement status, and the (mock) Arc transaction hash + explorer link.
// Mock transactions are explicitly labeled so no 0xMOCK... hash is ever
// mistaken for a real on-chain transaction (spec §12).
import { ExternalLink, History } from 'lucide-react'
import type { PaymentTransaction } from '../../types'

interface TransactionListProps {
  transactions: PaymentTransaction[]
}

function shortHash(hash: string): string {
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

export function TransactionList({ transactions }: TransactionListProps) {
  return (
    <section aria-label="Payment history" className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
        <History className="h-3.5 w-3.5" aria-hidden="true" />
        Payment History
      </h2>

      {transactions.length === 0 ? (
        <p className="mt-4 text-center text-xs text-slate-500">
          No autonomous payments yet — the FleetPay agent pays when live fleet
          telemetry reports a low battery or a failed robot. You can also run
          the end-to-end demo scenario.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {transactions.map((transaction) => (
            <li
              key={transaction.id}
              className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-sm font-semibold text-slate-100">
                    {transaction.vehicle_id}
                  </span>
                  <span className="text-xs text-slate-400">{transaction.provider_name}</span>
                  <span className="text-[10px] uppercase tracking-wide text-slate-500">
                    {transaction.service}
                  </span>
                </div>
                <span className="font-mono text-sm font-semibold text-emerald-400">
                  ${transaction.amount_usdc.toFixed(2)}
                </span>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]">
                <span className="inline-flex items-center gap-1.5">
                  <span className="text-slate-500">Status</span>
                  <span className="font-medium capitalize text-sky-300">{transaction.status}</span>
                  <span className="font-medium capitalize text-emerald-400">
                    {transaction.settlement_status}
                  </span>
                </span>
                <span className="inline-flex items-center gap-1.5 font-mono text-slate-400">
                  <span className="text-slate-500">Arc</span>
                  {shortHash(transaction.tx_hash)}
                  <a
                    href={transaction.explorer_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-0.5 text-sky-400 hover:text-sky-300"
                    aria-label={`Open ${transaction.tx_hash} in explorer`}
                  >
                    <ExternalLink className="h-3 w-3" aria-hidden="true" />
                  </a>
                </span>
                {transaction.is_mock && (
                  <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-400">
                    Mock
                  </span>
                )}
                <span className="text-slate-500">{formatTime(transaction.settled_at)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
