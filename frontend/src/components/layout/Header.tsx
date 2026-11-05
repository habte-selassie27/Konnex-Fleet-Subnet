// Header — top bar with live/offline badge, real policy name (from the
// MISSION_UPDATE WS contract) and mission context.
import { useFleetStore } from '../../store/fleetStore'

export function Header() {
  const isOnline = useFleetStore((s) => s.isOnline)
  const mission = useFleetStore((s) => s.mission)

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950 px-4">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-slate-100">Konnex Fleet Intelligence</h1>
        {isOnline ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-medium text-emerald-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" aria-hidden="true" />
            LIVE
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/15 px-2.5 py-0.5 text-xs font-medium text-red-400">
            <span className="h-1.5 w-1.5 rounded-full bg-red-400" aria-hidden="true" />
            OFFLINE
          </span>
        )}
      </div>

      <div className="flex items-center gap-4 text-xs text-slate-400">
        {mission && (
          <>
            <span>
              Policy{' '}
              <span className="font-mono text-slate-200">{mission.policy || '—'}</span>
            </span>
            <span className="font-mono">
              {mission.completed_tasks}/{mission.total_tasks} tasks
            </span>
          </>
        )}
      </div>
    </header>
  )
}
