// useFleetRail — the fleet sidebar's data source.
//
// SIM mode  → the simulation engine snapshot (same data as the 3D scene and the
//             FLEET OUTPUT HUD), so every cart card is current.
// Live mode → WebSocket telemetry, falling back to the captured run.
import { useMemo } from 'react'

import {
  cardsFromRobots,
  countCards,
  railFromSimulation,
  type FleetRail,
} from '../data/fleetRail'
import { useSimulationProvider, useSimulationSnapshot } from '../simulation/useSimulation'
import { useFleetView } from './useFleetView'

export function useFleetRail(): FleetRail {
  const mode = useSimulationProvider((s) => s.mode)
  const { snapshot } = useSimulationSnapshot()
  const view = useFleetView()

  return useMemo(() => {
    if (mode === 'sim' && snapshot && snapshot.robots.length > 0) {
      return railFromSimulation(snapshot.robots, snapshot.tasks)
    }

    const cards = cardsFromRobots(view.robots)
    return {
      source: view.source,
      cards,
      counts: countCards(cards),
      // Recorded runs report their own aggregate; averaged per-robot values are
      // rounded in the capture and would disagree (57.4 % vs 58 %).
      avgBattery: view.avgBattery,
      capturedAt: view.mission?.captured_at ?? null,
      missionId: view.mission?.mission_id ?? null,
    }
  }, [mode, snapshot, view])
}
