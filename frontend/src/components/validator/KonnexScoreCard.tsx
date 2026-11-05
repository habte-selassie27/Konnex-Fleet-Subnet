// KonnexScoreCard — the Konnex-aligned work score for one evaluation.
// Formula: gate(safety) × (w1·task_match + w2·efficiency + w3·evidence).
// Konnex does not publish its weight vector, so the card labels the result an
// estimate rather than presenting it as the official Konnex score.
import { ShieldAlert, ShieldCheck } from 'lucide-react'
import type { KonnexScore } from '../../types'

interface KonnexScoreCardProps {
  konnex: KonnexScore | null | undefined
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function ScoreRow({
  label,
  value,
  weight,
}: {
  label: string
  value: number
  weight: number
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-subtle">
        {label} <span className="text-[10px] text-subtle/70">w={Math.round(weight * 100)}%</span>
      </dt>
      <dd className="font-mono text-fg">{percent(value)}</dd>
    </div>
  )
}

export function KonnexScoreCard({ konnex }: KonnexScoreCardProps) {
  if (!konnex) {
    return (
      <div className="mt-4 border-t border-line/60 pt-3" aria-label="Konnex work score">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted">
          Konnex work score
        </p>
        <p className="mt-2 text-xs text-subtle">No Konnex score recorded for this evaluation.</p>
      </div>
    )
  }

  const gated = konnex.safety_gate === 0
  const GateIcon = gated ? ShieldAlert : ShieldCheck

  return (
    <div className="mt-4 border-t border-line/60 pt-3" aria-label="Konnex work score">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted">
          Konnex work score
        </p>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
            gated
              ? 'bg-red-500/10 text-red-400'
              : 'bg-emerald-500/10 text-emerald-400'
          }`}
        >
          <GateIcon className="h-3 w-3" aria-hidden="true" />
          {gated ? 'Gated' : 'Safe'}
        </span>
      </div>

      <div className="mt-1 flex items-baseline gap-2">
        <span
          className={`font-mono text-2xl font-semibold ${
            gated ? 'text-red-400' : 'text-emerald-400'
          }`}
        >
          {percent(konnex.final)}
        </span>
        <span className="text-[10px] text-subtle">of max work · estimate</span>
      </div>

      <dl className="mt-2 space-y-1 text-xs">
        <ScoreRow
          label="Task match"
          value={konnex.task_match}
          weight={konnex.weights.task_match}
        />
        <ScoreRow
          label="Efficiency"
          value={konnex.efficiency}
          weight={konnex.weights.efficiency}
        />
        <ScoreRow
          label="Evidence quality"
          value={konnex.evidence_quality}
          weight={konnex.weights.evidence_quality}
        />
        <div className="flex items-center justify-between gap-2">
          <dt className="text-subtle">Safety gate</dt>
          <dd className={`font-mono ${gated ? 'text-red-400' : 'text-fg'}`}>
            {gated
              ? `${konnex.safety_violations} violation${
                  konnex.safety_violations === 1 ? '' : 's'
                } — score 0`
              : 'open (0 violations)'}
          </dd>
        </div>
      </dl>

      <p className="mt-2 text-[10px] leading-relaxed text-subtle">
        gate(safety) × weighted sum. Konnex does not publish its per-subnet
        weight vector; 50 / 30 / 20 is our configured estimate.
      </p>
    </div>
  )
}
