// ValidatorPanel — Konnex validator operations UI (validating docs standup).
//
// Two views, same component:
//  1. Empty state when VITE_EVALUATION_ID is not set.
//  2. Evaluation detail when an evaluation ID is available.
//
// The evaluation fetch uses the typed API client (services/api.ts) and
// handles loading / error / empty / data per AGENTS.md §1.6.
import { useEffect, useState } from 'react'
import {
  FileCode2,
  Shield,
  CheckCircle,
  AlertCircle,
  Clock,
} from 'lucide-react'
import { api } from '../../services/api'
import type {
  EvaluationResult,
  ValidatorScoreCommitments,
  ValidatorStakeSnapshot,
  ValidatorServingSnapshot,
} from '../../types'
import { LoadingSpinner } from '../shared/LoadingSpinner'

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'empty' }
  | {
      kind: 'data'
      evaluation: EvaluationResult
      commitments: ValidatorScoreCommitments | null
      stake: ValidatorStakeSnapshot | null
      serving: ValidatorServingSnapshot | null
    }

// NOTE: the backend has no "list evaluations" endpoint yet, so this panel
// reads a single known evaluation id from the env (or stays empty). It proves
// the full fetch→render path without inventing data (AGENTS.md §1.6).
export function ValidatorPanel() {
  const evaluationId = import.meta.env.VITE_EVALUATION_ID
  const [state, setState] = useState<LoadState>({
    kind: evaluationId ? 'loading' : 'empty',
  })

  useEffect(() => {
    if (!evaluationId) return
    let cancelled = false

    const load = async () => {
      let evaluation: EvaluationResult | null = null
      let commitments: ValidatorScoreCommitments | null = null
      let stake: ValidatorStakeSnapshot | null = null
      let serving: ValidatorServingSnapshot | null = null

      try {
        evaluation = await api.getEvaluation(evaluationId)

        if (evaluation.popw_commitments) {
          commitments = evaluation.popw_commitments
        } else {
          try {
            const ctx = await api.getValidatorContext(evaluationId)
            commitments = {
              scoreroot_hash: ctx.scoreroot_hash,
              commitments_url: ctx.commitments_url,
              posted_at_ms: ctx.last_checkpoint_ms ?? null,
            }
            stake = {
              knx_staked: ctx.knx_staked,
              knx_at_risk_after_slash: ctx.knx_at_risk_after_slash,
              stablecoin_settlement_assurance:
                ctx.stablecoin_settlement_assurance,
              status: ctx.evaluator_status as 'ready' | 'scoring' | 'timed_out' | 'slashed',
            }
            serving = {
              mode: ctx.serving_mode as 'idle' | 'serving',
              active_request_id: ctx.active_request_id,
              requests_since_reset: ctx.requests_since_reset,
              last_checkpoint_ms: ctx.last_checkpoint_ms,
            }
          } catch {
            // Validator context is optional for the demo.
          }
        }

        if (!cancelled) {
          setState({ kind: 'data', evaluation, commitments, stake, serving })
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            kind: 'error',
            message: error instanceof Error ? error.message : 'Request failed',
          })
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [evaluationId])

  const stakeStatusIcon = (status: string) => {
    if (status === 'ready') {
      return (
        <CheckCircle className="h-3.5 w-3.5 shrink-0 text-emerald-400" aria-hidden="true" />
      )
    }
    if (status === 'scoring') {
      return (
        <Clock className="h-3.5 w-3.5 shrink-0 text-cyan-400" aria-hidden="true" />
      )
    }
    return (
      <AlertCircle className="h-3.5 w-3.5 shrink-0 text-red-400" aria-hidden="true" />
    )
  }

  const postedAt = (ts: number | null) =>
    ts ? new Date(ts).toISOString() : '—'

  return (
    <section
      aria-label="Konnex validator operations"
      className="rounded-xl border border-line/60 bg-panel p-4"
    >
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
        <Shield className="h-3.5 w-3.5" aria-hidden="true" />
        Validator
      </h2>

      {state.kind === 'loading' && (
        <LoadingSpinner label="Loading validator context…" />
      )}

      {state.kind === 'error' && (
        <p className="mt-3 text-xs text-red-400" role="alert">
          Evaluation unavailable: {state.message}
        </p>
      )}

      {state.kind === 'empty' && (
        <p className="mt-3 text-xs text-subtle">
          No evaluation yet. Set{' '}
          <code className="font-mono text-muted">VITE_EVALUATION_ID</code> to display one.
        </p>
      )}

      {state.kind === 'data' && (
        <>
          {/* Evaluation result */}
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

            {state.commitments && (
              <>
                <div className="flex justify-between">
                  <dt className="text-subtle">ScoreRoot</dt>
                  <dd className="font-mono text-fg break-all">
                    {state.commitments.scoreroot_hash}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-subtle">Posted at</dt>
                  <dd className="font-mono text-muted">{postedAt(state.commitments.posted_at_ms)}</dd>
                </div>
                <div className="flex items-center gap-1.5 pt-1 text-subtle">
                  <FileCode2 className="h-3.5 w-3.5" aria-hidden="true" />
                  <a
                    href={state.commitments.commitments_url}
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

          {/* Konnex validator framing */}
          {(state.stake || state.serving) && (
            <div className="mt-4 border-t border-line/60 pt-3">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted">
                Validator operations
              </p>

              <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                {state.stake && (
                  <dl className="space-y-1">
                    <div className="flex justify-between">
                      <dt className="text-subtle">KNX staked</dt>
                      <dd className="font-mono text-fg">
                        {state.stake.knx_staked.toFixed(4)} KNX
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-subtle">At risk after slash</dt>
                      <dd className="font-mono text-muted">
                        {state.stake.knx_at_risk_after_slash.toFixed(4)} KNX
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-subtle">Settlement assurance</dt>
                      <dd className="font-mono text-fg">
                        {state.stake.stablecoin_settlement_assurance.toFixed(2)} USDC
                      </dd>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-subtle">Status</span>
                      {stakeStatusIcon(state.stake.status)}
                      <span className="font-mono text-muted capitalize">
                        {state.stake.status}
                      </span>
                    </div>
                  </dl>
                )}

                {state.serving && (
                  <dl className="space-y-1">
                    <div className="flex justify-between">
                      <dt className="text-subtle">Serving</dt>
                      <dd className="font-mono text-fg">{state.serving.mode}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-subtle">Active request</dt>
                      <dd className="font-mono text-muted break-all">
                        {state.serving.active_request_id ?? '—'}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-subtle">Requests served</dt>
                      <dd className="font-mono text-muted">
                        {state.serving.requests_since_reset}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-subtle">Last checkpoint</dt>
                      <dd className="font-mono text-muted">{postedAt(state.serving.last_checkpoint_ms)}</dd>
                    </div>
                  </dl>
                )}
              </div>

              <p className="mt-3 text-[10px] leading-relaxed text-subtle">
                Validators do not operate the robots. They independently score
                miner outputs against the task instruction and PoPW policy, post
                ScoreRoots / commitments, and meet staking requirements. Malicious
                or negligent validation is economically discouraged via slashing
                and isolation.
              </p>
            </div>
          )}
        </>
      )}
    </section>
  )
}
