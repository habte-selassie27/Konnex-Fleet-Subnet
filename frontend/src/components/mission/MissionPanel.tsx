// MissionPanel — active mission overview + recent fleet events
// (AGENTS.md §1.2 mission/).
import { CheckCircle2, ListChecks } from 'lucide-react'
import { useFleetStore } from '../../store/fleetStore'

export function MissionPanel() {
  const mission = useFleetStore((s) => s.mission)
  const eventLog = useFleetStore((s) => s.eventLog)

  if (!mission) {
    return (
      <section aria-label="Active mission" className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Active Mission</h2>
        <p className="mt-3 text-sm text-slate-500">No mission running.</p>
      </section>
    )
  }

  const progress =
    mission.total_tasks > 0 ? Math.round((mission.completed_tasks / mission.total_tasks) * 100) : 0
  const recentEvents = [...eventLog].reverse().slice(0, 5)

  return (
    <section aria-label="Active mission" className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
          <ListChecks className="h-3.5 w-3.5" aria-hidden="true" />
          Active Mission
        </h2>
        <span className="rounded-full bg-sky-500/15 px-2.5 py-0.5 text-xs font-medium capitalize text-sky-400">
          {mission.status}
        </span>
      </div>

      <p className="mt-2 font-mono text-xs text-slate-500">#{mission.mission_id.slice(0, 8)}</p>

      <div className="mt-3">
        <div className="mb-1 flex justify-between text-xs">
          <span className="text-slate-500">Tasks</span>
          <span className="font-mono text-slate-300">
            {mission.completed_tasks}/{mission.total_tasks}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-800" role="img" aria-label={`Mission progress ${progress}%`}>
          <div className="h-full rounded-full bg-emerald-500 transition-all duration-500" style={{ width: `${progress}%` }} />
        </div>
      </div>

      {recentEvents.length > 0 && (
        <ul className="mt-4 space-y-1.5" aria-label="Recent fleet events">
          {recentEvents.map((event, index) => (
            <li key={`${event.type}-${event.timestamp}-${index}`} className="flex items-center gap-2 text-xs text-slate-400">
              {event.type === 'TASK_COMPLETED' ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" aria-hidden="true" />
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
