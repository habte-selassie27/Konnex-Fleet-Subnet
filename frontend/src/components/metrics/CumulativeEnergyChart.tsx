// CumulativeEnergyChart — energy view for a captured run.
//
// A capture carries only the final energy total, not a per-step series. This
// chart therefore plots the one point that is actually known — (elapsed,
// total) — against the mission budget. It does not interpolate a curve that
// was never recorded (AGENTS.md Law 1).
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

interface CumulativeEnergyChartProps {
  total: number
  elapsed_s: number
  time_limit_s: number
}

/** Round the Y axis up to a 20-unit step (211.8 → 220). */
function axisMaxFor(total: number): number {
  return Math.max(20, Math.ceil(total / 20) * 20)
}

export function CumulativeEnergyChart({
  total,
  elapsed_s,
  time_limit_s,
}: CumulativeEnergyChartProps) {
  if (!Number.isFinite(total) || total <= 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-line text-xs text-subtle">
        No energy data
      </div>
    )
  }

  const yMax = axisMaxFor(total)
  const yTicks = [0, yMax / 4, yMax / 2, (yMax * 3) / 4, yMax]
  const xMax = Math.max(time_limit_s, elapsed_s, 1)

  return (
    <div
      role="img"
      aria-label={`Cumulative energy ${total.toFixed(1)} units at ${Math.round(elapsed_s)} seconds`}
    >
      <ResponsiveContainer width="100%" height={160}>
        <ScatterChart margin={{ top: 8, right: 10, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="rgb(var(--line))" vertical={false} />
          <XAxis
            type="number"
            dataKey="elapsed"
            domain={[0, xMax]}
            ticks={[xMax]}
            tickFormatter={(value: number) => `${Math.round(value)}s`}
            stroke="rgb(var(--line-strong))"
            tick={{ fill: 'rgb(var(--subtle))', fontSize: 10 }}
          />
          <YAxis
            type="number"
            dataKey="energy"
            domain={[0, yMax]}
            ticks={yTicks}
            stroke="rgb(var(--line-strong))"
            tick={{ fill: 'rgb(var(--subtle))', fontSize: 10 }}
            width={46}
          />
          <Tooltip
            cursor={{ stroke: 'rgb(var(--line-strong))', strokeDasharray: '3 3' }}
            contentStyle={{
              background: 'rgb(var(--panel))',
              border: '1px solid rgb(var(--line))',
              borderRadius: 8,
              color: 'rgb(var(--fg))',
              fontSize: 12,
            }}
            formatter={(value, name) => [
              name === 'energy' ? `${Number(value).toFixed(1)} u` : `${Number(value)} s`,
              name === 'energy' ? 'Consumed' : 'Elapsed',
            ]}
          />
          <Scatter
            name="Mission total"
            data={[{ elapsed: elapsed_s, energy: total }]}
            fill="#0ea5e9"
            stroke="rgb(var(--panel))"
            strokeWidth={1.5}
          />
        </ScatterChart>
      </ResponsiveContainer>
      <p className="mt-1 text-center text-[10px] text-subtle">
        Final total only — the capture has no per-step energy series.
      </p>
    </div>
  )
}
