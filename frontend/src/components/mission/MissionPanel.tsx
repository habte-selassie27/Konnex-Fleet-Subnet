// MissionPanel — active mission overview + recent fleet events
// (AGENTS.md §1.2 mission/).
//
// Reads the same mission as the header, the fleet rail and the metrics rail
// (useMissionView): the event log is only rendered for live missions — a SIM
// run has its own action feed in the viewport, and the backend replay must
// never bleed into the SIM panel (AGENTS.md Law 1).
import { CheckCircle2, ListChecks } from 'lucide-react'

import type { MissionStatus } from '../../types'
import { useFleetStore } from '../../store/fleetStore'
import { useMissionView } from '../../hooks/useMissionView'
import { SourcePill } from '../shared/SourcePill'

const STATUS_STYLES: Record<MissionStatus, { label: string; className: string }> = {
  pending: { label: 'Pending', className: 'bg-elevated text-muted' },
  running: { label: 'Running', className: 'bg-sky-500/15 text-sky-500' },
  complete: { label: 'Complete', className: 'bg-emerald-500/15 text-emerald-500' },
  failed: { label: 'Failed', className: 'bg-red-500/15 text-red-500' },
  timed_out: { label: 'Timed out', className: 'bg-amber-500/15 text-amber-500' },
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export function MissionPanel() {
  const { mission, source } = useMissionView()
  const eventLog = useFleetStore((s) => s.eventLog)

  if (!mission) {
    return (
      <section aria-label="Active mission" className="rounded-xl border border-line/60 bg-panel p-4 transition-colors duration-200">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Active Mission</h2>
        <p className="mt-3 text-sm text-subtle">No mission running.</p>
      </section>
    )
  }

  const progress =
    mission.total_tasks > 0 ? Math.round((mission.completed_tasks / mission.total_tasks) * 100) : 0
  const status = STATUS_STYLES[mission.status] ?? STATUS_STYLES.pending
  const recentEvents =
    source === 'live' ? [...eventLog].reverse().slice(0, 5) : []

  return (
    <section aria-label="Active mission" className="rounded-xl border border-line/60 bg-panel p-4 transition-colors duration-200">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
          <ListChecks className="h-3.5 w-3.5" aria-hidden="true" />
          Active Mission
        </h2>
        <div className="flex items-center gap-2">
          <SourcePill source={source} capturedAt={mission.captured_at} />
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${status.className}`}
          >
            {status.label}
          </span>
        </div>
      </div>

      <p className="mt-2 font-mono text-xs text-subtle">#{mission.mission_id.slice(0, 8)}</p>

      <div className="mt-3">
        <div className="mb-1 flex justify-between text-xs">
          <span className="text-subtle">Tasks</span>
          <span className="font-mono text-fg">
            {mission.completed_tasks}/{mission.total_tasks}
          </span>
        </div>
        <div
          className="h-2 overflow-hidden rounded-full bg-elevated"
          role="img"
          aria-label={`Mission progress ${progress}%`}
        >
          <div className="h-full rounded-full bg-emerald-500 transition-all duration-500" style={{ width: `${progress}%` }} />
        </div>
      </div>

      {mission.time_limit_s !== null && mission.time_limit_s > 0 && (
        <div className="mt-3 flex justify-between text-xs">
          <span className="text-subtle">Time</span>
          <span className="font-mono text-fg">
            {formatElapsed(mission.elapsed_seconds)} / {formatElapsed(mission.time_limit_s)}
          </span>
        </div>
      )}

      {recentEvents.length > 0 && (
        <ul className="mt-4 space-y-1.5" aria-label="Recent fleet events">
          {recentEvents.map((event, index) => (
            <li
              key={`${event.type}-${event.timestamp}-${index}`}
              className="flex items-center gap-2 text-xs text-muted"
            >
              {event.type === 'TASK_COMPLETED' ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" aria-hidden="true" />
                  Task {event.task_id.slice(0, 8)} completed
                </>
              ) : (
                <span className="font-mono">{event.type}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
