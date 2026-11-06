// One role validator's independent assessment: verdict, score, checks, reason.
// Colour is never the only signal — every state also carries an icon and text
// (AGENTS.md §1.6 accessibility).
import { CheckCircle2, CircleHelp, Clock, XCircle } from 'lucide-react'

import type { ValidatorAssessment, ValidatorRole, ValidatorVerdict } from '../../types'

const ROLE_LABELS: Record<ValidatorRole, { label: string; scope: string }> = {
  execution: { label: 'Execution', scope: 'mission completion' },
  safety: { label: 'Safety', scope: 'collisions & telemetry' },
  performance: { label: 'Performance', scope: 'time & energy' },
}

const VERDICT_STYLES: Record<
  ValidatorVerdict | 'AWAITING',
  { className: string; label: string; Icon: typeof CheckCircle2 }
> = {
  PASS: { className: 'bg-emerald-500/15 text-emerald-500', label: 'Pass', Icon: CheckCircle2 },
  FAIL: { className: 'bg-red-500/15 text-red-500', label: 'Fail', Icon: XCircle },
  PENDING: { className: 'bg-sky-500/15 text-sky-500', label: 'Pending', Icon: Clock },
  INCONCLUSIVE: {
    className: 'bg-amber-500/15 text-amber-500',
    label: 'Inconclusive',
    Icon: CircleHelp,
  },
  AWAITING: { className: 'bg-elevated text-muted', label: 'Awaiting evidence', Icon: Clock },
}

interface ValidatorRoleRowProps {
  role: ValidatorRole
  assessment?: ValidatorAssessment
}

export function ValidatorRoleRow({ role, assessment }: ValidatorRoleRowProps) {
  const meta = ROLE_LABELS[role]
  const verdict = VERDICT_STYLES[assessment?.verdict ?? 'AWAITING']
  const VerdictIcon = verdict.Icon
  // While a verdict is pending/inconclusive a failed check is not a failure
  // yet — show a clock instead of a cross so the row does not imply one.
  const checksAreProvisional =
    assessment?.verdict === 'PENDING' || assessment?.verdict === 'INCONCLUSIVE'

  return (
    <div className="rounded-lg border border-line/50 bg-surface/40 p-2.5">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-fg">{meta.label} validator</p>
          <p className="text-[10px] uppercase tracking-wide text-subtle">{meta.scope}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className="font-mono text-xs text-fg"
            aria-label={
              assessment?.score == null ? 'No score yet' : `${meta.label} score ${assessment.score}`
            }
          >
            {assessment?.score == null ? '—' : assessment.score.toFixed(1)}
          </span>
          <span
            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${verdict.className}`}
          >
            <VerdictIcon className="h-3 w-3" aria-hidden="true" />
            {verdict.label}
          </span>
        </div>
      </div>

      <p className="mt-1.5 text-[11px] leading-snug text-muted">
        {assessment?.reason ?? 'The validator receives the mission evidence once it exists.'}
      </p>

      {assessment && assessment.checks.length > 0 && (
        <ul className="mt-1.5 space-y-0.5">
          {assessment.checks.map((check) => (
            <li key={check.name} className="flex items-start gap-1 text-[10px] text-subtle">
              {check.passed ? (
                <CheckCircle2 className="mt-px h-2.5 w-2.5 shrink-0 text-emerald-500" aria-hidden="true" />
              ) : checksAreProvisional ? (
                <Clock className="mt-px h-2.5 w-2.5 shrink-0 text-subtle" aria-hidden="true" />
              ) : (
                <XCircle className="mt-px h-2.5 w-2.5 shrink-0 text-amber-500" aria-hidden="true" />
              )}
              <span className="font-mono">{check.name}</span>
              <span aria-hidden="true">·</span>
              <span>{check.detail}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
