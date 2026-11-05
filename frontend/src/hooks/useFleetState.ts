// Derived fleet state (AGENTS.md §1.2 hooks/). Selectors over the store that
// components consume — never raw store access in components.
import { useMemo } from 'react'
import { useFleetStore } from '../store/fleetStore'
import type { RobotState } from '../types'

export interface FleetDerived {
  robots: RobotState[]
  robotCount: number
  movingCount: number
  idleCount: number
  failedCount: number
  chargingCount: number
  avgBattery: number
  isOnline: boolean
}

export function useFleetState(): FleetDerived {
  const robots = useFleetStore((s) => s.robots)
  const robotOrder = useFleetStore((s) => s.robotOrder)
  const isOnline = useFleetStore((s) => s.isOnline)

  return useMemo(() => {
    const list = robotOrder.map((id) => robots[id]).filter(Boolean) as RobotState[]
    const counts = { moving: 0, idle: 0, failed: 0, charging: 0 }
    let batterySum = 0
    for (const robot of list) {
      batterySum += robot.battery_pct
      switch (robot.nav_state) {
        case 'moving':
          counts.moving += 1
          break
        case 'charging':
          counts.charging += 1
          break
        case 'failed':
          counts.failed += 1
          break
        default:
          counts.idle += 1
      }
    }
    return {
      robots: list,
      robotCount: list.length,
      movingCount: counts.moving,
      idleCount: counts.idle,
      failedCount: counts.failed,
      chargingCount: counts.charging,
      avgBattery: list.length > 0 ? batterySum / list.length : 0,
      isOnline,
    }
  }, [robots, robotOrder, isOnline])
}
