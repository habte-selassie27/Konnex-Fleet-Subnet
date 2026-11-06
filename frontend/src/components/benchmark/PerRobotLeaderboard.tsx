import { Trophy } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../../services/api'
import type { BenchmarkResult } from '../../types'

export function PerRobotLeaderboard() {
  const [rows, setRows] = useState<BenchmarkResult[]>([])

  useEffect(() => {
    let cancelled = false
    api
      .listBenchmarks()
      .then((data) => {
        if (cancelled) return
        setRows(data.filter((r) => r.harness === 'live_mission' && r.per_robot && r.per_robot.length > 0))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const latest = rows[rows.length - 1]
  if (!latest || !latest.per_robot || latest.per_robot.length === 0) return null

  const sorted = [...latest.per_robot].sort((a, b) => b.tasks_completed - a.tasks_completed)

  return (
    <section aria-label="Per-robot leaderboard" className="rounded-xl border border-line/60 bg-panel p-4">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
        <Trophy className="h-3.5 w-3.5" aria-hidden="true" />
        Per-robot leaderboard
      </h2>
      <p className="mt-1 text-[10px] text-subtle">
        {latest.policy} · mission #{latest.experiment_id.replace('live_', '').slice(0, 8)}
      </p>
      <table className="mt-3 w-full text-left text-xs">
        <thead>
          <tr className="border-b border-line text-subtle">
            <th className="pb-2 pr-2 font-medium">Robot</th>
            <th className="pb-2 pr-2 font-medium">Tasks</th>
            <th className="pb-2 pr-2 font-medium">Battery</th>
            <th className="pb-2 pr-2 font-medium">State</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.robot_id} className="border-b border-line/40 last:border-b-0">
              <td className="py-2 pr-2 font-mono text-fg">{r.robot_id}</td>
              <td className="py-2 pr-2 font-mono text-fg">
                {r.tasks_completed}/{r.tasks_assigned}
              </td>
              <td className="py-2 pr-2 font-mono text-fg">
                {r.battery_pct === null ? '—' : `${(r.battery_pct * 100).toFixed(0)}%`}
              </td>
              <td className="py-2 pr-2 text-muted">{r.final_nav_state ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
