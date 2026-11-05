// EvaluationCard — latest evaluation result (AGENTS.md §1.2 validator/).
// Reads via the typed API client; handles loading / error / empty / data.
import { useEffect, useState } from 'react'
import { BadgeCheck, FileCode2 } from 'lucide-react'
import { api } from '../../services/api'
import type { EvaluationResult } from '../../types'
import { LoadingSpinner } from '../shared/LoadingSpinner'

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'empty' }
  | { kind: 'data'; evaluation: EvaluationResult }

// NOTE: the backend has no "list evaluations" endpoint yet, so this panel
// reads a single known evaluation id from the env (or stays empty). It proves
// the full fetch→render path without inventing data (AGENTS.md §1.6).
export function EvaluationCard() {
  const evaluationId = import.meta.env.VITE_EVALUATION_ID
  const [state, setState] = useState<LoadState>({ kind: evaluationId ? 'loading' : 'empty' })

  useEffect(() => {
    if (!evaluationId) return
    let cancelled = false
    api
      .getEvaluation(evaluationId)
      .then((evaluation) => {
        if (!cancelled) setState({ kind: 'data', evaluation })
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({ kind: 'error', message: error instanceof Error ? error.message : 'Request failed' })
        }
      })
    return () => {
      cancelled = true
    }
  }, [evaluationId])

  return (
    <section aria-label="Latest evaluation" className="rounded-xl border border-line/60 bg-panel p-4">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
        <BadgeCheck className="h-3.5 w-3.5" aria-hidden="true" />
        Validator
      </h2>

      {state.kind === 'loading' && <LoadingSpinner label="Loading evaluation…" />}

      {state.kind === 'error' && (
        <p className="mt-3 text-xs text-red-400" role="alert">
          Evaluation unavailable: {state.message}
        </p>
      )}

      {state.kind === 'empty' && (
        <p className="mt-3 text-xs text-subtle">
          No evaluation yet. Set <code className="font-mono text-muted">VITE_EVALUATION_ID</code> to display one.
        </p>
      )}

      {state.kind === 'data' && (
        <dl className="mt-3 space-y-2 text-xs">
          <div className="flex justify-between">
            <dt className="text-subtle">Policy</dt>
            <dd className="font-mono text-fg">{state.evaluation.policy_id}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-subtle">Score</dt>
            <dd className="font-mono font-semibold text-emerald-400">
              {state.evaluation.final_score?.toFixed(2) ?? '—'}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-subtle">Status</dt>
            <dd className="font-mono text-muted">{state.evaluation.status}</dd>
          </div>

          {state.evaluation.popw_commitments && (
            <>
              <div className="flex justify-between">
                <dt className="text-subtle">ScoreRoot</dt>
                <dd className="font-mono text-fg break-all">{state.evaluation.popw_commitments.scoreroot_hash}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-subtle">Posted</dt>
                <dd className="font-mono text-muted">
                  {state.evaluation.popw_commitments.posted_at_ms
                    ? new Date(state.evaluation.popw_commitments.posted_at_ms).toISOString()
                    : '—'}
                </dd>
              </div>
              <div className="flex items-center gap-1.5 pt-1 text-subtle">
                <FileCode2 className="h-3.5 w-3.5" aria-hidden="true" />
                <a
                  href={state.evaluation.popw_commitments.commitments_url}
                  target="_blank"
                  rel="noreferrer"
                  aria-label="Open Konnex commitments explorer"
                  className="underline decoration-slate-600 underline-offset-2 hover:text-muted"
                >
                  commitments
                </a>
              </div>
            </>
          )}

          <div className="flex items-center gap-1.5 pt-1 text-subtle">
            <FileCode2 className="h-3.5 w-3.5" aria-hidden="true" />
            <a
              href={state.evaluation.artifact_url}
              target="_blank"
              rel="noreferrer"
              aria-label="Open evaluation artifact"
              className="underline decoration-slate-600 underline-offset-2 hover:text-muted"
            >
              artifact
            </a>
          </div>
        </dl>
      )}
    </section>
  )
}
