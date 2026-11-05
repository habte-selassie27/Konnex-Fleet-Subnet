import { beforeEach, describe, expect, it } from 'vitest'
import { useFleetStore } from './fleetStore'
import type { RobotState } from '../types'

const robot: RobotState = {
  id: 'robot_0',
  position: { x: 1, y: 2 },
  orientation: 0,
  velocity: { x: 0, y: 0 },
  battery_pct: 1.0,
  current_task_id: null,
  nav_state: 'idle',
  in_collision: false,
  comm_state: 'online',
  timestamp: 0,
  distance_traveled: 0,
}

describe('fleetStore', () => {
  beforeEach(() => {
    useFleetStore.getState().reset()
  })

  it('upserts robots and maintains stable ordering', () => {
    useFleetStore.getState().upsertRobot(robot)
    useFleetStore.getState().upsertRobot({ ...robot, id: 'robot_1', position: { x: 3, y: 4 } })
    useFleetStore.getState().upsertRobot({ ...robot, id: 'robot_0', battery_pct: 0.5 })

    const state = useFleetStore.getState()
    expect(state.robotOrder).toEqual(['robot_0', 'robot_1'])
    expect(state.robots['robot_0'].battery_pct).toBe(0.5)
    expect(Object.keys(state.robots)).toHaveLength(2)
  })

  it('records events and tracks the last collision', () => {
    useFleetStore.getState().recordEvent({ type: 'TASK_COMPLETED', task_id: 't1', timestamp: 1 })
    useFleetStore.getState().recordEvent({
      type: 'COLLISION_DETECTED',
      robot_id: 'robot_0',
      near_miss: false,
      timestamp: 2,
    })

    const state = useFleetStore.getState()
    expect(state.eventLog).toHaveLength(2)
    expect(state.lastCollisionAt).toBe(2)
  })

  it('setMission stores the mission snapshot', () => {
    useFleetStore.getState().setMission({
      mission_id: 'm1',
      status: 'running',
      policy: 'nearest',
      completed_tasks: 4,
      total_tasks: 20,
      collision_count: 0,
      failure_count: 0,
      elapsed_seconds: 12.5,
      energy_consumed: 3.2,
      popw_score: null,
    })
    expect(useFleetStore.getState().mission?.completed_tasks).toBe(4)
    expect(useFleetStore.getState().mission?.policy).toBe('nearest')
  })

  it('records energy samples throttled to ~1/second', () => {
    const record = useFleetStore.getState().recordEnergySample
    record(0, 0)
    record(0.2, 1) // < 1s since last -> dropped
    record(1.0, 2)
    record(2.5, 3)
    record(2.6, 9) // dropped

    const history = useFleetStore.getState().energyHistory
    expect(history).toEqual([
      { t: 0, energy: 0 },
      { t: 1.0, energy: 2 },
      { t: 2.5, energy: 3 },
    ])
  })

  it('reset clears the energy history', () => {
    useFleetStore.getState().recordEnergySample(0, 0)
    useFleetStore.getState().reset()
    expect(useFleetStore.getState().energyHistory).toEqual([])
  })

  it('setMission clears energy history when the mission changes', () => {
    const base = {
      status: 'running' as const,
      policy: 'nearest',
      completed_tasks: 0,
      total_tasks: 20,
      collision_count: 0,
      failure_count: 0,
      energy_consumed: 2,
      popw_score: 60,
    }
    useFleetStore.getState().setMission({ ...base, mission_id: 'm1', elapsed_seconds: 1 })
    useFleetStore.getState().recordEnergySample(0, 0)
    useFleetStore.getState().recordEnergySample(1, 2)
    expect(useFleetStore.getState().energyHistory).toHaveLength(2)

    // Same mission id -> series continues.
    useFleetStore.getState().setMission({ ...base, mission_id: 'm1', elapsed_seconds: 2 })
    expect(useFleetStore.getState().energyHistory).toHaveLength(2)

    // New mission id -> series resets (fresh chart for the new mission).
    useFleetStore.getState().setMission({
      ...base,
      mission_id: 'm2',
      elapsed_seconds: 0,
      energy_consumed: 0,
    })
    expect(useFleetStore.getState().energyHistory).toEqual([])
  })
})
