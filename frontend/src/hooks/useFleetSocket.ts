// WebSocket hook (AGENTS.md §1.5). Connects to /ws/fleet, reconnects on a
// fixed 2 s delay (capped at 10 attempts), and dispatches typed events into
// the store. Positions arrive at ~10 Hz (≤100 ms), satisfying the live-data
// rule. An auth rejection (4401) is surfaced as an offline reason and stops
// retrying — retrying a bad key is pointless.
import { useCallback, useEffect, useRef } from 'react'
import { useFleetStore } from '../store/fleetStore'
import type { FleetEvent, MissionUpdateEvent } from '../types'

const API_KEY = import.meta.env.VITE_WS_API_KEY ?? 'dev-only-key'
const WS_URL =
  import.meta.env.VITE_WS_URL ??
  `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/fleet?api_key=${encodeURIComponent(API_KEY)}`

const RECONNECT_DELAY_MS = 2000
const MAX_RECONNECT_ATTEMPTS = 10

function isFleetEvent(payload: unknown): payload is FleetEvent {
  if (typeof payload !== 'object' || payload === null) return false
  const type = (payload as { type?: unknown }).type
  return (
    type === 'ROBOT_STATE_UPDATE' ||
    type === 'MISSION_UPDATE' ||
    type === 'TASK_COMPLETED' ||
    type === 'COLLISION_DETECTED' ||
    type === 'SIMULATOR_OFFLINE'
  )
}

export function useFleetSocket(): void {
  const wsRef = useRef<WebSocket | null>(null)
  const attemptsRef = useRef(0)
  const setOnline = useFleetStore((s) => s.setOnline)
  const upsertRobot = useFleetStore((s) => s.upsertRobot)
  const setMission = useFleetStore((s) => s.setMission)
  const recordEvent = useFleetStore((s) => s.recordEvent)
  const recordEnergySample = useFleetStore((s) => s.recordEnergySample)

  const handleEvent = useCallback(
    (event: FleetEvent) => {
      recordEvent(event)
      switch (event.type) {
        case 'ROBOT_STATE_UPDATE':
          upsertRobot(event.state)
          break
        case 'MISSION_UPDATE':
          setMission(toMissionUpdate(event))
          recordEnergySample(event.elapsed_seconds, event.energy_consumed)
          break
        case 'SIMULATOR_OFFLINE':
          setOnline(false, event.reason)
          break
        case 'TASK_COMPLETED':
        case 'COLLISION_DETECTED':
          break
        case 'MISSION_COMPLETE':
          window.dispatchEvent(new CustomEvent('mission-complete', { detail: event }))
          break
      }
    },
    [recordEvent, upsertRobot, setMission, setOnline, recordEnergySample],
  )

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      attemptsRef.current = 0
      setOnline(true)
    }

    ws.onmessage = (message: MessageEvent<string>) => {
      try {
        const payload: unknown = JSON.parse(message.data)
        if (isFleetEvent(payload)) handleEvent(payload)
      } catch {
        // Malformed frame — ignore and keep streaming.
      }
    }

    ws.onclose = (event) => {
      setOnline(false, event.code === 4401 ? 'Invalid API key' : undefined)
      if (event.code === 4401) {
        attemptsRef.current = MAX_RECONNECT_ATTEMPTS // do not retry a bad key
        return
      }
      if (attemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        attemptsRef.current += 1
        window.setTimeout(connect, RECONNECT_DELAY_MS)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [handleEvent, setOnline])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])
}

function toMissionUpdate(event: MissionUpdateEvent) {
  // Extract the mission fields (drop the event discriminator + timestamp).
  return {
    mission_id: event.mission_id,
    status: event.status,
    policy: event.policy,
    completed_tasks: event.completed_tasks,
    total_tasks: event.total_tasks,
    collision_count: event.collision_count,
    failure_count: event.failure_count,
    elapsed_seconds: event.elapsed_seconds,
    energy_consumed: event.energy_consumed,
    popw_score: event.popw_score,
  }
}
