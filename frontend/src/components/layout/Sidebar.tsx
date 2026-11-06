// Sidebar — the 280px fleet status rail (AGENTS.md §1.3 layout rules).
//
// Data comes from useFleetRail: in SIM mode it renders the simulation engine's
// carts (Cart-01…05) from the same snapshot the 3D scene animates, never the
// stale backend/recorded robot ids; otherwise it renders live/captured robot
// telemetry. FleetSummary names the provenance (SIM badge), so the rail is
// never mistaken for a live feed (AGENTS.md Law 1).
import { useFleetRail } from '../../hooks/useFleetRail'
import { FleetSummary } from '../fleet/FleetSummary'
import { RobotCard } from '../fleet/RobotCard'

export function Sidebar() {
  const { cards, counts, avgBattery, source, capturedAt } = useFleetRail()

  return (
    <aside
      className="flex h-full w-72 shrink-0 flex-col gap-4 overflow-y-auto border-r border-line bg-surface p-4 transition-colors duration-200"
      aria-label="Fleet sidebar"
    >
      <FleetSummary counts={counts} avgBattery={avgBattery} source={source} capturedAt={capturedAt} />
      {cards.length === 0 ? (
        <p className="text-center text-xs text-subtle">Waiting for robot telemetry…</p>
      ) : (
        <ul className="space-y-2">
          {cards.map((card) => (
            <RobotCard key={card.id} robot={card} />
          ))}
        </ul>
      )}
    </aside>
  )
}
