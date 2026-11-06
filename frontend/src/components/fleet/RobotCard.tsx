// RobotCard — sidebar per-cart status (AGENTS.md §1.2 fleet/). Always shows
// color + icon + text for state (accessibility), plus battery and the cart's
// current crate/task. The card shape is the FleetRobotCard built by
// data/fleetRail.ts — SIM carts and backend robots normalise to the same card.
import {
  AlertTriangle,
  BatteryCharging,
  CircleDot,
  Package,
  PackageCheck,
  Move,
  PackageOpen,
  WifiOff,
  Wrench,
  Zap,
} from 'lucide-react'
import type { FleetRobotCard, RobotNavKind } from '../../data/fleetRail'

const NAV_META: Record<
  RobotNavKind,
  { label: string; icon: typeof Move; className: string }
> = {
  idle: { label: 'Idle', icon: CircleDot, className: 'bg-slate-800 text-slate-300' },
  staging: {
    label: 'Staging',
    icon: CircleDot,
    className: 'bg-slate-700/60 text-slate-200',
  },
  moving: { label: 'Moving', icon: Move, className: 'bg-sky-500/15 text-sky-500' },
  picking: {
    label: 'Picking up',
    icon: PackageOpen,
    className: 'bg-violet-500/15 text-violet-500',
  },
  depositing: {
    label: 'Delivering',
    icon: PackageCheck,
    className: 'bg-emerald-500/15 text-emerald-500',
  },
  charging: {
    label: 'Charging',
    icon: BatteryCharging,
    className: 'bg-amber-500/15 text-amber-500',
  },
  blocked: {
    label: 'Blocked',
    icon: AlertTriangle,
    className: 'bg-orange-500/15 text-orange-500',
  },
  failed: { label: 'Failed', icon: Zap, className: 'bg-red-500/15 text-red-500' },
}

/** Battery bar fill colour changes before a hard floor, with a text label too. */
function batteryClass(pct: number): string {
  if (pct <= 0.15) return 'bg-red-500'
  if (pct <= 0.3) return 'bg-amber-500'
  return 'bg-sky-500'
}

export function RobotCard({ robot }: { robot: FleetRobotCard }) {
  const meta = NAV_META[robot.nav] ?? NAV_META.idle
  const StatusIcon = meta.icon
  const batteryPct = Math.round(robot.battery_pct * 100)

  return (
    <li
      aria-label={`${robot.id} — ${meta.label}`}
      className="rounded-xl border border-line/60 bg-panel p-3 transition-colors duration-200"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate font-mono text-sm font-semibold text-fg">{robot.id}</span>
          {robot.offline && (
            <WifiOff className="h-3.5 w-3.5 shrink-0 text-muted" aria-label="Offline" />
          )}
        </span>
        <span
          className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${meta.className}`}
        >
          <StatusIcon className="h-3 w-3" aria-hidden="true" />
          {meta.label}
        </span>
      </div>

      <div className="mt-2 flex items-center justify-between gap-2 text-xs text-subtle">
        <span className="flex min-w-0 items-center gap-1.5">
          {robot.task_label ? (
            <>
              <Package className="h-3 w-3 shrink-0" aria-hidden="true" />
              <span className="truncate text-muted">{robot.task_label}</span>
            </>
          ) : (
            <>
              <Wrench className="h-3 w-3 shrink-0" aria-hidden="true" />
              <span>No task assigned</span>
            </>
          )}
        </span>
        <span className="shrink-0 font-mono">
          x {robot.position.x.toFixed(1)} · y {robot.position.y.toFixed(1)}
        </span>
      </div>

      <div className="mt-2 flex items-center gap-2">
        <div
          className="h-1.5 flex-1 overflow-hidden rounded-full bg-elevated"
          role="img"
          aria-label={`Battery ${batteryPct}%`}
        >
          <div
            className={`h-full rounded-full transition-all duration-500 ${batteryClass(robot.battery_pct)}`}
            style={{ width: `${batteryPct}%` }}
          />
        </div>
        <span className="w-8 text-right font-mono text-[10px] text-subtle">{batteryPct}%</span>
      </div>
    </li>
  )
}
