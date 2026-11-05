// Zustand fleet store (AGENTS.md §1.2 store/). Holds live robot states, the
// active mission snapshot, online/offline flag, a rolling event log, and an
// energy-consumption time series (1 sample/second, for the EnergyChart).
// Only the useFleetSocket hook writes to it; components subscribe.
import { create } from 'zustand'
import type { EnergySample, FleetEvent, MissionUpdate, RobotState } from '../types'

const MAX_EVENT_LOG = 50
const MAX_ENERGY_SAMPLES = 900
const ENERGY_SAMPLE_INTERVAL_S = 1.0

interface FleetState {
  robots: Record<string, RobotState>
  robotOrder: string[]
  mission: MissionUpdate | null
  isOnline: boolean
  offlineReason: string
  eventLog: FleetEvent[]
  lastCollisionAt: number | null
  energyHistory: EnergySample[]
  setOnline: (online: boolean, reason?: string) => void
  upsertRobot: (robot: RobotState) => void
  setMission: (mission: MissionUpdate) => void
  recordEvent: (event: FleetEvent) => void
  recordEnergySample: (t: number, energy: number) => void
  reset: () => void
}

export const useFleetStore = create<FleetState>((set) => ({
  robots: {},
  robotOrder: [],
  mission: null,
  isOnline: false,
  offlineReason: 'Simulator offline — no live data',
  eventLog: [],
  lastCollisionAt: null,
  energyHistory: [],

  setOnline: (online, reason) =>
    set((state) => ({
      isOnline: online,
      offlineReason: reason ?? state.offlineReason,
    })),

  upsertRobot: (robot) =>
    set((state) => {
      const robots = { ...state.robots, [robot.id]: robot }
      const robotOrder = state.robotOrder.includes(robot.id)
        ? state.robotOrder
        : [...state.robotOrder, robot.id]
      return { robots, robotOrder }
    }),

  setMission: (mission) =>
    set((state) => ({
      mission,
      // A new mission restarts elapsed time at 0 — clearing the energy series
      // keeps the chart honest (no discontinuity from a previous mission).
      energyHistory:
        state.mission?.mission_id === mission.mission_id
          ? state.energyHistory
          : [],
    })),

  recordEvent: (event) =>
    set((state) => ({
      eventLog: [...state.eventLog.slice(-(MAX_EVENT_LOG - 1)), event],
      lastCollisionAt:
        event.type === 'COLLISION_DETECTED' && !event.near_miss
          ? event.timestamp
          : state.lastCollisionAt,
    })),

  recordEnergySample: (t, energy) =>
    set((state) => {
      const last = state.energyHistory[state.energyHistory.length - 1]
      // Throttle to ~1 sample/second so the 10 Hz mission stream does not
      // flood the chart series (still resolves to the same curve).
      if (last && t - last.t < ENERGY_SAMPLE_INTERVAL_S) return {}
      const energyHistory = [...state.energyHistory, { t, energy }].slice(-MAX_ENERGY_SAMPLES)
      return { energyHistory }
    }),

  reset: () =>
    set({
      robots: {},
      robotOrder: [],
      mission: null,
      isOnline: false,
      eventLog: [],
      lastCollisionAt: null,
      energyHistory: [],
    }),
}))
