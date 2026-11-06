// Auto-start a backend mission when a SIM run finishes, so the run is captured
// as a real benchmark row (experiments/results/live_missions/) without any
// manual POST. Zero user input.
import { useEffect, useRef } from 'react'

import { useSimulationProvider } from '../simulation/useSimulation'
import { api } from '../services/api'

const POLICY = 'nearest'

export function useAutoCaptureSim(): void {
  const runState = useSimulationProvider((s) => s.runState)
  const seed = useSimulationProvider((s) => s.seed)
  const itemCount = useSimulationProvider((s) => s.itemCount)
  const firedRef = useRef<number | null>(null)

  useEffect(() => {
    if (runState !== 'finished') return
    if (firedRef.current === seed) return
    firedRef.current = seed
    void api
      .createMission({
        robot_count: 5,
        task_count: Math.max(1, itemCount),
        seed,
        policy: POLICY,
        time_limit_s: 600,
      })
      .catch(() => {
        // Non-fatal: benchmark capture is best-effort.
      })
  }, [runState, seed, itemCount])
}
