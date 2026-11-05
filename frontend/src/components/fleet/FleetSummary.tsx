// FleetSummary — aggregate fleet stats (AGENTS.md §1.2 fleet/).
import { useFleetState } from '../../hooks/useFleetState'

export function FleetSummary() {
  const { robotCount, movingCount, idleCount, failedCount, chargingCount, avgBattery } =
    useFleetState()

  const stats = [
    { label: 'Robots', value: robotCount },
    { label: 'Moving', value: movingCount },
    { label: 'Idle', value: idleCount },
    { label: 'Charging', value: chargingCount },
    { label: 'Failed', value: failedCount },
  ]

  return (
    <section aria-label="Fleet summary" className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Fleet</h2>
      <dl className="mt-3 grid grid-cols-3 gap-3">
        {stats.map((stat) => (
          <div key={stat.label}>
            <dt className="text-[10px] uppercase tracking-wide text-slate-500">{stat.label}</dt>
            <dd className="mt-0.5 font-mono text-lg font-semibold text-slate-100">{stat.value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-slate-500">Avg battery</span>
        <span className="font-mono font-medium text-slate-200">{Math.round(avgBattery * 100)}%</span>
      </div>
    </section>
  )
}
