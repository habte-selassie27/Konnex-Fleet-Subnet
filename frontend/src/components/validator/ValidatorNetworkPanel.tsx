// ValidatorNetworkPanel — Konnex-aligned multi-validator verification.
//
// One panel replaces the two duplicate "VALIDATOR" cards: three role-separated
// validators (execution / safety / performance) independently assess the same
// live mission evidence, then a consensus layer decides. Data comes from
// GET /validators/network — real mission telemetry, never mock verdicts
// (AGENTS.md Law 1). The Konnex protocol adapter is STUB and labelled so.
import { useEffect, useState } from 'react'
import { ExternalLink, ShieldCheck } from 'lucide-react'

import { api } from '../../services/api'
import { useFleetStore } from '../../store/fleetStore'
import type { ConsensusDecision, ValidatorNetwork, ValidatorRole } from '../../types'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ValidatorRoleRow } from './ValidatorRoleRow'

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'data'; data: ValidatorNetwork }

const ROLES: ValidatorRole[] = ['execution', 'safety', 'performance']

const DECISION_STYLES: Record<ConsensusDecision, string> = {
  ACCEPTED: 'bg-emerald-500/15 text-emerald-500',
  REJECTED: 'bg-red-500/15 text-red-500',
  DISPUTED: 'bg-amber-500/15 text-amber-500',
  INCONCLUSIVE: 'bg-amber-500/15 text-amber-500',
  PENDING: 'bg-sky-500/15 text-sky-500',
}

function shortHash(hash: string): string {
  return hash.length > 16 ? `${hash.slice(0, 16)}…` : hash
}

export function ValidatorNetworkPanel() {
  const missionId = useFleetStore((s) => s.mission?.mission_id)
  const missionStatus = useFleetStore((s) => s.mission?.status)
  const [state, setState] = useState<LoadState>({ kind: 'loading' })

  // Refetch when the live mission changes or reaches a terminal status: the
  // verdict is only final once execution ends.
  useEffect(() => {
    let cancelled = false
    setState({ kind: 'loading' })
    api
      .getValidatorNetwork()
      .then((data) => {
        if (!cancelled) setState({ kind: 'data', data })
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
  }, [missionId, missionStatus])

  const verification = state.kind === 'data' ? state.data.verification : null
  const assessments = new Map(
    (verification?.assessments ?? []).map((assessment) => [assessment.role, assessment]),
  )

  return (
    <section
      aria-label="Konnex validator network"
      className="flex flex-col rounded-xl border border-line/60 bg-panel p-4 transition-colors duration-200 lg:col-span-2"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
          Konnex validator network
        </h2>
        {verification ? (
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${DECISION_STYLES[verification.consensus.decision]}`}
          >
            {verification.consensus.decision}
          </span>
        ) : (
          <span className="rounded-full bg-elevated px-2.5 py-0.5 text-xs font-medium text-muted">
            No mission
          </span>
        )}
      </div>

      {state.kind === 'loading' && <LoadingSpinner label="Verifying mission evidence…" />}

      {state.kind === 'error' && (
        <p className="mt-3 text-xs text-red-400" role="alert">
          Validator network unavailable: {state.message}
        </p>
      )}

      {state.kind === 'data' && (
        <>
          {verification ? (
            <>
              <p className="mt-2 font-mono text-[10px] text-subtle">
                #{verification.mission_id.slice(0, 8)} · {verification.policy} ·{' '}
                {verification.tasks_completed}/{verification.task_count} tasks ·{' '}
                {verification.collision_count} collisions · evidence{' '}
                <span title={verification.evidence_hash}>
                  {shortHash(verification.evidence_hash)}
                </span>
              </p>

              <div className="mt-2.5 grid grid-cols-1 gap-2 md:grid-cols-3">
                {ROLES.map((role) => (
                  <ValidatorRoleRow
                    key={role}
                    role={role}
                    assessment={assessments.get(role)}
                  />
                ))}
              </div>

              <div className="mt-3 border-t border-line/60 pt-2.5">
                <p className="text-[11px] leading-snug text-muted">
                  <span className="font-semibold text-fg">Consensus:</span>{' '}
                  {verification.consensus.reason}
                  <span className="font-mono text-subtle">
                    {' '}
                    ({verification.consensus.accept_votes} accept /{' '}
                    {verification.consensus.reject_votes} reject of{' '}
                    {verification.consensus.validator_count})
                  </span>
                </p>
              </div>
            </>
          ) : (
            <div className="mt-2.5 grid grid-cols-1 gap-2 md:grid-cols-3">
              {ROLES.map((role) => (
                <ValidatorRoleRow key={role} role={role} />
              ))}
            </div>
          )}

          <div className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line/60 pt-2.5 text-[10px] text-subtle">
            <span className="font-semibold uppercase tracking-wide">
              Konnex bridge: {state.data.konnex.adapter_status}
            </span>
            <span aria-hidden="true">·</span>
            <span>{state.data.konnex.note}</span>
            <a
              href={state.data.konnex.docs_url}
              target="_blank"
              rel="noreferrer"
              aria-label="Open Konnex validator documentation"
              className="ml-auto flex items-center gap-0.5 underline decoration-slate-600 underline-offset-2 hover:text-muted"
            >
              docs <ExternalLink className="h-2.5 w-2.5" aria-hidden="true" />
            </a>
          </div>
        </>
      )}
    </section>
  )
}
