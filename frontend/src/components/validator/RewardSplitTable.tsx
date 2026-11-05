// RewardSplitTable — projected reward shares for the evaluated policies.
// Reads GET /evaluations/reward-split, which uses each policy's latest recorded
// evaluation. Shares are fractions of a unit pool; no token amount is invented.
import { useEffect, useState } from 'react'
import { Coins } from 'lucide-react'
import { api } from '../../services/api'
import type { RewardSplit } from '../../types'

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'empty' }
  | { kind: 'data'; split: RewardSplit }

interface RewardSplitTableProps {
  /** The policy currently shown, highlighted in the split. */
  policyId: string
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function RewardSplitTable({ policyId }: RewardSplitTableProps) {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    api
      .getRewardSplit()
      .then((split) => {
        if (cancelled) return
        setState(split.entries.length > 0 ? { kind: 'data', split } : { kind: 'empty' })
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: 'error',
            message: error instanceof Error ? error.message : 'Request failed',
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="mt-4 border-t border-line/60 pt-3" aria-label="Projected reward split">
      <h3 className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted">
        <Coins className="h-3 w-3" aria-hidden="true" />
        Reward split · estimate
      </h3>

      {state.kind === 'loading' && <p className="mt-2 text-xs text-subtle">Loading split…</p>}

      {state.kind === 'error' && (
        <p className="mt-2 text-xs text-red-400" role="alert">
          Reward split unavailable: {state.message}
        </p>
      )}

      {state.kind === 'empty' && (
        <p className="mt-2 text-xs text-subtle">No scored evaluations yet.</p>
      )}

      {state.kind === 'data' && (
        <>
          <table className="mt-2 w-full text-left text-xs">
            <thead>
              <tr className="text-[10px] uppercase tracking-wide text-subtle">
                <th scope="col" className="pb-1 font-medium">
                  Policy
                </th>
                <th scope="col" className="pb-1 text-right font-medium">
                  Score
                </th>
                <th scope="col" className="pb-1 text-right font-medium" title="Score_i / Σ Score_j">
                  Competitive
                </th>
                <th
                  scope="col"
                  className="pb-1 text-right font-medium"
                  title={`Top policy takes ${Math.round(state.split.top_share * 100)}%`}
                >
                  Winner
                </th>
              </tr>
            </thead>
            <tbody>
              {state.split.entries.map((entry) => {
                const isCurrent = entry.policy_id === policyId
                return (
                  <tr
                    key={entry.evaluation_id}
                    className={
                      isCurrent
                        ? 'border-t border-line/50 text-fg'
                        : 'border-t border-line/50 text-muted'
                    }
                  >
                    <th scope="row" className="py-1 pr-2 text-left font-mono font-normal">
                      {entry.policy_id}
                      {entry.is_top && (
                        <span className="ml-1 rounded bg-sky-500/10 px-1 text-[9px] font-semibold uppercase text-sky-400">
                          top
                        </span>
                      )}
                      {isCurrent && (
                        <span className="ml-1 text-[9px] uppercase tracking-wide text-subtle">
                          current
                        </span>
                      )}
                    </th>
                    <td className="py-1 text-right font-mono">{percent(entry.score)}</td>
                    <td className="py-1 text-right font-mono">
                      {percent(entry.competitive_share)}
                    </td>
                    <td className="py-1 text-right font-mono">
                      {percent(entry.winner_takes_most_share)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <p className="mt-2 text-[10px] leading-relaxed text-subtle">
            {state.split.note ||
              'Projected shares of a unit reward pool from each policy’s latest recorded evaluation.'}
          </p>
        </>
      )}
    </div>
  )
}
