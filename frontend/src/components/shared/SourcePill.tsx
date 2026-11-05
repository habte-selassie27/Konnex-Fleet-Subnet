// SourcePill — states the provenance of whatever data is on screen.
//
// AGENTS.md Law 1: the dashboard must never imply a live feed when it is
// rendering a capture. The badge is therefore driven by the same `source` flag
// that selects the data (data/missionView.ts), so it cannot drift.
import { Activity, CircleSlash, History, Radio } from 'lucide-react'

import type { FleetSource } from '../../data/missionView'
import { StatusBadge } from './StatusBadge'

interface SourcePillProps {
  source: FleetSource
  capturedAt?: string | null
  className?: string
}

const META = {
  simulation: {
    label: 'SIM',
    icon: Activity,
    className: 'bg-cyan-500/15 text-cyan-500',
    title: 'Client-side simulation engine — same snapshot as the 3D viewport',
  },
  live: {
    label: 'LIVE',
    icon: Radio,
    className: 'bg-emerald-500/15 text-emerald-500',
    title: 'Streaming from the fleet WebSocket',
  },
  recorded: {
    label: 'RECORDED',
    icon: History,
    className: 'bg-amber-500/15 text-amber-500',
    title: 'Captured mission run — not a live feed',
  },
  none: {
    label: 'NO DATA',
    icon: CircleSlash,
    className: 'bg-elevated text-subtle',
    title: 'No telemetry and no captured run',
  },
} as const

export function SourcePill({ source, capturedAt, className }: SourcePillProps) {
  const meta = META[source]
  const title =
    source === 'recorded' && capturedAt
      ? `${meta.title} · ${new Date(capturedAt).toLocaleString()}`
      : meta.title

  return (
    <span title={title} className={className}>
      <StatusBadge label={meta.label} icon={meta.icon} className={meta.className} />
    </span>
  )
}
