// EnergyChart — energy consumption over time (AGENTS.md §1.2 metrics/).
// Streams real `energy_consumed` samples from MISSION_UPDATE (1/s throttle in
// the store). Shows "No data yet" when the series is empty — never zeros.
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useFleetStore } from '../../store/fleetStore'

export function EnergyChart() {
  const history = useFleetStore((s) => s.energyHistory)
  const isOnline = useFleetStore((s) => s.isOnline)

  if (!isOnline || history.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-slate-700 text-xs text-slate-500">
        No data yet
      </div>
    )
  }

  const latest = history[history.length - 1]

  return (
    <div
      role="img"
      aria-label={`Energy consumption chart, current ${latest.energy.toFixed(1)} units`}
    >
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={history} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id="energyFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.45} />
              <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#1e293b" vertical={false} />
          <XAxis
            dataKey="t"
            stroke="#64748b"
            tick={{ fontSize: 10 }}
            tickFormatter={(v: number) => `${Math.round(v)}s`}
          />
          <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
          <Tooltip
            contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 12 }}
            labelFormatter={(v) => `t = ${v}s`}
            formatter={(value) => [`${Number(value).toFixed(1)} u`, 'Energy']}
          />
          <Area
            type="monotone"
            dataKey="energy"
            stroke="#0ea5e9"
            strokeWidth={2}
            fill="url(#energyFill)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
