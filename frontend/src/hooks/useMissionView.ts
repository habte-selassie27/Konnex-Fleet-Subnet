// useMissionView — single mission/metrics data source that follows the SIM run
// when the scene is in SIM mode, and otherwise falls back to the resolved fleet
// view (live telemetry, then the captured run, then no data).
//
// This keeps Header, MissionPanel and the PoPW rail in lockstep with the 3D
// viewport and left fleet rail: when the scene shows SIM carts, the numbers are
// computed from that same engine snapshot; when it shows Live, they come from
// the WebSocket/capture (AGENTS.md Law 1 / §0.3).
import { useMemo } from 'react'

import { useFleetView } from './useFleetView'
import { useSimulationProvider, useSimulationSnapshot, useSimulationEnergyHistory } from '../simulation/useSimulation'
import { simMissionFromSnapshot } from '../data/simMission'
import type { EnergySample } from '../types'
import type { FleetSource, MissionView } from '../data/missionView'

export interface MissionViewResult {
  mission: MissionView | null
  source: FleetSource
  /** Only present when source === 'simulation'; same series as the viewport run. */
  energyHistory: EnergySample[] | null
}

export function useMissionView(): MissionViewResult {
  const mode = useSimulationProvider((s) => s.mode)
  const runState = useSimulationProvider((s) => s.runState)
  const { snapshot } = useSimulationSnapshot()
  const energyHistory = useSimulationEnergyHistory()
  const view = useFleetView()

  return useMemo(() => {
    if (mode === 'sim' && snapshot !== null) {
      return {
        // Pass the real playback state so a staged-but-not-started run reads as
        // pending instead of claiming to be running.
        mission: simMissionFromSnapshot(snapshot, runState),
        source: 'simulation',
        energyHistory,
      }
    }
    return { mission: view.mission, source: view.source, energyHistory: null }
  }, [mode, runState, snapshot, energyHistory, view])
}
