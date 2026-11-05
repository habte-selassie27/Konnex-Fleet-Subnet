// AgentDecisionCard — the agent's economic decision: the fleet event that
// triggered it, the provider comparison, and the rationale. A MOCK/DEMO badge
// keeps the demo honest (spec §12: never present simulated data as real).
import { BrainCircuit, CheckCircle2 } from 'lucide-react'
import type { AgentDecision } from '../../types'

interface AgentDecisionCardProps {
  decision: AgentDecision
}

export function AgentDecisionCard({ decision }: AgentDecisionCardProps) {
  if (decision.no_action) {
    return (
      <div className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
          <BrainCircuit className="h-3.5 w-3.5" aria-hidden="true" />
          Agent Decision
        </div>
        <p className="mt-3 text-sm text-slate-300">
          <span className="font-mono font-semibold text-slate-100">{decision.vehicle_id}</span>{' '}
          — no action: {decision.rationale}
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
          <BrainCircuit className="h-3.5 w-3.5" aria-hidden="true" />
          Agent Decision
        </h3>
        <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-400">
          MOCK / DEMO
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
        <span className="font-mono font-semibold text-slate-100">{decision.vehicle_id}</span>
        <span className="capitalize text-slate-400">{decision.service}</span>
        <span className="font-mono text-base font-semibold text-emerald-400">
          ${decision.amount_usdc.toFixed(2)}
        </span>
        <span className="text-xs text-slate-500">USDC</span>
      </div>

      {/* Provider comparison */}
      <table className="mt-3 w-full text-left text-xs">
        <thead>
          <tr className="border-b border-slate-700/60 text-slate-500">
            <th scope="col" className="pb-1.5 pr-2 font-medium">Provider</th>
            <th scope="col" className="pb-1.5 pr-2 text-right font-medium">Price</th>
            <th scope="col" className="pb-1.5 pr-2 text-right font-medium">Dist</th>
            <th scope="col" className="pb-1.5 pr-2 text-right font-medium">Rating</th>
            <th scope="col" className="pb-1.5 text-right font-medium">Score</th>
          </tr>
        </thead>
        <tbody>
          {decision.quotes.map((quote) => (
            <tr
              key={quote.provider_id}
              className={`border-b border-slate-800/60 ${
                quote.selected ? 'bg-sky-500/10 text-slate-100' : 'text-slate-400'
              }`}
            >
              <td className="py-1.5 pr-2">
                <span className="flex items-center gap-1.5">
                  {quote.name}
                  {quote.selected && (
                    <CheckCircle2 className="h-3.5 w-3.5 text-sky-400" aria-label="Selected" />
                  )}
                </span>
              </td>
              <td className="py-1.5 pr-2 text-right font-mono">
                ${quote.price_usdc.toFixed(2)}
              </td>
              <td className="py-1.5 pr-2 text-right font-mono">{quote.distance_km.toFixed(1)} km</td>
              <td className="py-1.5 pr-2 text-right font-mono">{quote.rating.toFixed(1)}</td>
              <td className={`py-1.5 text-right font-mono ${quote.selected ? 'text-sky-300' : ''}`}>
                {quote.score.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="mt-3 border-t border-slate-800 pt-2 text-xs leading-relaxed text-slate-400">
        {decision.rationale}
      </p>
    </div>
  )
}
