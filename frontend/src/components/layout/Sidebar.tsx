// Sidebar — 280px robot status rail (AGENTS.md §1.3 layout rules).
import { useFleetState } from '../../hooks/useFleetState'
import { FleetSummary } from '../fleet/FleetSummary'
import { RobotCard } from '../fleet/RobotCard'

export function Sidebar() {
  const { robots } = useFleetState()

  return (
    <aside className="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-r border-slate-800 bg-slate-950 p-4" aria-label="Fleet sidebar">
      <FleetSummary />
      {robots.length === 0 ? (
        <p className="text-center text-xs text-slate-500">Waiting for robot telemetry…</p>
      ) : (
        <ul className="space-y-2">
          {robots.map((robot) => (
            <RobotCard key={robot.id} robot={robot} />
          ))}
        </ul>
      )}
    </aside>
  )
}
