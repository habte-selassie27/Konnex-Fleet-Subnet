// RobotCard — sidebar per-robot status (AGENTS.md §1.2 fleet/). Always shows
// color + icon + text for state (accessibility), plus battery and task.
import { AlertTriangle, BatteryCharging, CircleDot, Move, WifiOff, Zap } from 'lucide-react'
import type { RobotState } from '../../types'
import { StatusBadge } from '../shared/StatusBadge'

interface RobotCardProps {
  robot: RobotState
}

const NAV_META: Record<string, { label: string; icon: typeof Move; className: string }> = {
  idle: { label: 'Idle', icon: CircleDot, className: 'bg-slate-800 text-slate-300' },
  moving: { label: 'Moving', icon: Move, className: 'bg-sky-500/15 text-sky-400' },
  blocked: { label: 'Blocked', icon: AlertTriangle, className: 'bg-orange-500/15 text-orange-400' },
  charging: { label: 'Charging', icon: BatteryCharging, className: 'bg-amber-500/15 text-amber-400' },
  failed: { label: 'Failed', icon: Zap, className: 'bg-red-500/15 text-red-400' },
}

export function RobotCard({ robot }: RobotCardProps) {
  const meta = NAV_META[robot.nav_state] ?? NAV_META.idle
  const batteryPct = Math.round(robot.battery_pct * 100)
  const offline = robot.comm_state !== 'online'

  return (
    <li className="rounded-xl border border-slate-700/60 bg-slate-900 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-sm font-medium text-slate-200">{robot.id}</span>
        <StatusBadge label={meta.label} icon={meta.icon} className={meta.className} />
      </div>

      <div className="mt-2 flex items-center gap-2">
        <span className="text-xs text-slate-500">Battery</span>
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800" role="img" aria-label={`Battery ${batteryPct}%`}>
          <div
            className={`h-full rounded-full ${batteryPct <= 20 ? 'bg-red-500' : batteryPct <= 50 ? 'bg-amber-500' : 'bg-emerald-500'}`}
            style={{ width: `${batteryPct}%` }}
          />
        </div>
        <span className="font-mono text-xs text-slate-400">{batteryPct}%</span>
      </div>

      <div className="mt-2 flex items-center justify-between text-xs">
        <span className="font-mono text-slate-400">
          {robot.current_task_id ? `Task ${robot.current_task_id.slice(0, 8)}` : 'No task'}
        </span>
        {offline ? (
          <span className="inline-flex items-center gap-1 text-red-400">
            <WifiOff className="h-3 w-3" aria-hidden="true" /> Offline
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-slate-500">
            ({robot.position.x.toFixed(1)}, {robot.position.y.toFixed(1)})
          </span>
        )}
      </div>
    </li>
  )
}
