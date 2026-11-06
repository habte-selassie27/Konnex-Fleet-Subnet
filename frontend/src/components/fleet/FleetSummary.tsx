// FleetSummary — aggregate fleet stats (AGENTS.md §1.2 fleet/). The counts and
// average battery come from the same useFleetRail snapshot that drives the cart
// cards and the 3D scene, so the summary can never disagree with what's on
// screen. The source pill states the provenance (SIM cart run, live telemetry,
// or a recorded capture — AGENTS.md Law 1).
import { Users } from 'lucide-react'

import type { FleetSource } from '../../data/missionView'
import { SourcePill } from '../shared/SourcePill'

interface FleetSummaryProps {
  counts: {
    total: number
    moving: number
    idle: number
    charging: number
    failed: number
  }
  /** Mean battery across the rail's robots, as a fraction [0, 1]. */
  avgBattery: number
  source: FleetSource
  /** Capture timestamp — only recorded runs have one. */
  capturedAt: string | null
}

export function FleetSummary({ counts, avgBattery, source, capturedAt }: FleetSummaryProps) {
  const stats = [
    { label: 'Robots', value: counts.total },
    { label: 'Moving', value: counts.moving },
    { label: 'Idle', value: counts.idle },
    { label: 'Charging', value: counts.charging },
    { label: 'Failed', value: counts.failed },
  ]

  return (
    <section
      aria-label="Fleet summary"
      className="rounded-xl border border-line/60 bg-panel p-4 transition-colors duration-200"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
          <Users className="h-3.5 w-3.5" aria-hidden="true" />
          Fleet
        </h2>
        <SourcePill source={source} capturedAt={capturedAt} />
      </div>

      {counts.total === 0 ? (
        <p className="mt-3 text-xs text-subtle">No robots to summarise yet.</p>
      ) : (
        <>
          <dl className="mt-3 grid grid-cols-3 gap-3">
            {stats.map((stat) => (
              <div key={stat.label}>
                <dt className="text-[10px] uppercase tracking-wide text-subtle">{stat.label}</dt>
                <dd className="mt-0.5 font-mono text-lg font-semibold text-fg">{stat.value}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-subtle">Avg battery</span>
            <span className="font-mono font-medium text-fg">{Math.round(avgBattery * 100)}%</span>
          </div>
        </>
      )}
    </section>
  )
}
