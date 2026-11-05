// useFleetView — the dashboard's single fleet/mission data source.
//
// Wraps resolveFleetView() with the Zustand subscriptions so every panel reads
// the same snapshot and the same `source` flag ('live' | 'recorded' | 'none').
import { useMemo } from 'react'

import { MISSION_RECORD } from '../data/missionRecord'
import { resolveFleetView, type FleetView } from '../data/missionView'
import { useFleetStore } from '../store/fleetStore'
import type { RobotState } from '../types'

export function useFleetView(): FleetView {
  const robots = useFleetStore((s) => s.robots)
  const robotOrder = useFleetStore((s) => s.robotOrder)
  const mission = useFleetStore((s) => s.mission)
  const isOnline = useFleetStore((s) => s.isOnline)

  return useMemo(() => {
    const liveRobots = robotOrder.map((id) => robots[id]).filter(Boolean) as RobotState[]
    return resolveFleetView({
      isOnline,
      robots: liveRobots,
      mission,
      record: MISSION_RECORD,
    })
  }, [robots, robotOrder, mission, isOnline])
}
