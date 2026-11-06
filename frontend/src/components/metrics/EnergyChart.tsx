// EnergyChart — energy consumption over time (AGENTS.md §1.2 metrics/).
//
// Two data sources, both real:
//  • Live mode      — the store's `energy_consumed` samples from MISSION_UPDATE
//                     (1/s throttle in the store).
//  • Simulation     — the caller passes the sim run's 1 Hz energy series (see
//                     useSimulationEnergyHistory), so the chart shows the exact
//                     run the viewport is animating.
//
// Shows "No data yet" when the series is empty — never zeros. Colors follow the
// theme tokens so the chart reads correctly in dark and light mode.
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { EnergySample } from '../../types'
import { useFleetStore } from '../../store/fleetStore'

interface EnergyChartProps {
  /** Series override — the simulation run's samples, when the scene is SIM. */
  history?: EnergySample[]
}

export function EnergyChart({ history: historyProp }: EnergyChartProps = {}) {
  const storeHistory = useFleetStore((s) => s.energyHistory)
  const isOnline = useFleetStore((s) => s.isOnline)

  // Explicit series (SIM run) is client-side data — it doesn't depend on the
  // WebSocket being up. The store series is live-backend data and only counts
  // while the simulator is online.
  const history = historyProp ?? (isOnline ? storeHistory : [])

  if (history.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-line text-xs text-subtle">
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
          <CartesianGrid stroke="rgb(var(--line))" vertical={false} />
          <XAxis
            dataKey="t"
            stroke="rgb(var(--line-strong))"
            tick={{ fontSize: 10, fill: 'rgb(var(--subtle))' }}
            tickFormatter={(v: number) => `${Math.round(v)}s`}
          />
          <YAxis
            stroke="rgb(var(--line-strong))"
            tick={{ fontSize: 10, fill: 'rgb(var(--subtle))' }}
            width={46}
          />
          <Tooltip
            contentStyle={{
              background: 'rgb(var(--panel))',
              border: '1px solid rgb(var(--line))',
              borderRadius: 8,
              color: 'rgb(var(--fg))',
              fontSize: 12,
            }}
            labelFormatter={(v) => `t = ${v}s`}
            formatter={(value) => [`${Number(value).toFixed(1)} u`, 'Energy']}
          />
          <Area
            type="monotone"
            dataKey="energy"
            stroke="#0ea5e9"
            strokeWidth={2}
            fill="url(#energyFill)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
