// MetricsDashboard — right-hand metrics panel (AGENTS.md §1.2 metrics/).
// Shows real mission data; "No data yet" when absent (never zeros).
import { AlertTriangle, Clock, Gauge, PackageCheck } from 'lucide-react'
import { useFleetStore } from '../../store/fleetStore'
import { EnergyChart } from './EnergyChart'
import { ScoreGauge } from './ScoreGauge'

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export function MetricsDashboard() {
  const mission = useFleetStore((s) => s.mission)
  const isOnline = useFleetStore((s) => s.isOnline)

  if (!isOnline || !mission) {
    return (
      <section aria-label="Mission metrics" className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Metrics</h2>
        <div className="mt-6 text-center">
          <ScoreGauge score={null} />
          <p className="mt-4 text-xs text-slate-500">No data yet</p>
        </div>
      </section>
    )
  }

  const progress =
    mission.total_tasks > 0 ? Math.round((mission.completed_tasks / mission.total_tasks) * 100) : 0

  return (
    <section aria-label="Mission metrics" className="space-y-4">
      <div className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">PoPW Score</h2>
        <div className="mt-3">
          <ScoreGauge score={mission.popw_score} />
        </div>
      </div>

      <div className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Mission</h2>
        <dl className="mt-3 space-y-3">          <MetricRow icon={PackageCheck} label="Tasks" value={`${mission.completed_tasks} / ${mission.total_tasks}`} />
          <MetricRow icon={Clock} label="Elapsed" value={formatElapsed(mission.elapsed_seconds)} />
          <MetricRow icon={AlertTriangle} label="Collisions" value={String(mission.collision_count)} />
        </dl>

        <div className="mt-4">
          <div className="mb-1 flex justify-between text-xs">
            <span className="text-slate-500">Completion</span>
            <span className="font-mono text-slate-300">{progress}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-800" role="img" aria-label={`Task completion ${progress}%`}>
            <div
              className="h-full rounded-full bg-sky-500 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Energy</h2>
          <span className="font-mono text-xs font-medium text-slate-300">
            {mission.energy_consumed.toFixed(1)} u
          </span>
        </div>
        <div className="mt-3">
          <EnergyChart />
        </div>
      </div>

      <div className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
          <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
          Status
        </h2>
        <p className="mt-2 text-sm capitalize text-slate-200">{mission.status}</p>
      </div>
    </section>
  )
}

interface MetricRowProps {
  icon: typeof Clock
  label: string
  value: string
}

function MetricRow({ icon: Icon, label, value }: MetricRowProps) {
  return (
    <div className="flex items-center justify-between">
      <dt className="flex items-center gap-2 text-xs text-slate-500">
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        {label}
      </dt>
      <dd className="font-mono text-sm font-medium text-slate-200">{value}</dd>
    </div>
  )
}
