// Regression tests for the SIM playback state machine.
//
// The bug these lock down: the run used to be restarted (engine.reset()) on any
// store update, so Pause rewound the fleet instead of freezing it and Resume was
// a no-op. These tests drive the rAF loop by hand and assert that Pause keeps
// the engine — and every cart position — exactly where it was.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useSimulationProvider } from './useSimulation'

let pendingFrames: Map<number, FrameRequestCallback>
let nextFrameId: number

function runFrame(nowMs: number) {
  const callbacks = [...pendingFrames.values()]
  pendingFrames.clear()
  for (const cb of callbacks) cb(nowMs)
}

describe('SIM playback state machine', () => {
  beforeEach(() => {
    pendingFrames = new Map()
    nextFrameId = 1
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      const id = nextFrameId++
      pendingFrames.set(id, cb)
      return id
    })
    vi.stubGlobal('cancelAnimationFrame', (id: number) => {
      pendingFrames.delete(id)
    })
    useSimulationProvider.getState().stop()
  })

  afterEach(() => {
    useSimulationProvider.getState().stop()
    vi.unstubAllGlobals()
  })

  it('advances only while running', () => {
    const provider = useSimulationProvider.getState()
    provider.start()

    expect(useSimulationProvider.getState().runState).toBe('running')
    runFrame(16) // first frame primes lastFrameAt with dt = 0
    runFrame(32)

    const engine = useSimulationProvider.getState().engine
    expect(engine).not.toBeNull()
    expect(engine!.simTime).toBeGreaterThan(0)
  })

  it('pause freezes the run in place instead of restarting it', () => {
    const provider = useSimulationProvider.getState()
    provider.start()
    runFrame(16)
    runFrame(32)
    runFrame(48)

    const engine = useSimulationProvider.getState().engine!
    const simTimeAtPause = engine.simTime
    const cartsAtPause = engine.robots.map((r) => ({ x: r.x, z: r.z }))

    provider.pause()

    expect(useSimulationProvider.getState().runState).toBe('paused')
    // Nothing is rescheduled, so no further frames can tick the engine.
    expect(pendingFrames.size).toBe(0)

    // No reset happened: clock, counters and every cart are untouched.
    expect(engine.simTime).toBe(simTimeAtPause)
    expect(engine.robots.map((r) => ({ x: r.x, z: r.z }))).toEqual(cartsAtPause)
    expect(useSimulationProvider.getState().engine).toBe(engine)
  })

  it('resume continues from the paused state without jumping forward', () => {
    const provider = useSimulationProvider.getState()
    provider.start()
    runFrame(16)
    runFrame(32)

    const engine = useSimulationProvider.getState().engine!
    provider.pause()
    const simTimeAtPause = engine.simTime

    provider.resume()
    expect(useSimulationProvider.getState().runState).toBe('running')

    // The first frame after resume uses dt = 0, so the pause length is not
    // replayed as a single giant step.
    runFrame(10_000)
    expect(engine.simTime).toBe(simTimeAtPause)

    runFrame(10_016)
    expect(engine.simTime).toBeGreaterThan(simTimeAtPause)
  })

  it('start is idempotent while already running', () => {
    const provider = useSimulationProvider.getState()
    provider.start()
    runFrame(16)
    runFrame(32)

    const engine = useSimulationProvider.getState().engine!
    const simTime = engine.simTime

    provider.start()

    expect(useSimulationProvider.getState().engine).toBe(engine)
    expect(engine.simTime).toBe(simTime)
  })

  it('reset stages a fresh run and stops the loop', () => {
    const provider = useSimulationProvider.getState()
    provider.start()
    runFrame(16)
    runFrame(32)
    runFrame(48)

    const engine = useSimulationProvider.getState().engine!
    provider.reset()

    expect(useSimulationProvider.getState().runState).toBe('idle')
    expect(pendingFrames.size).toBe(0)
    expect(engine.simTime).toBe(0)
    expect(engine.completed).toBe(0)
    // Restaged, not left mid-route: every crate is back on the floor and every
    // cart is idle again at a fresh start cell.
    expect(engine.tasks).toHaveLength(engine.itemCount)
    expect(engine.tasks.every((t) => t.spawnT === 0)).toBe(true)
    expect(engine.robots.every((r) => r.nav_state === 'idle')).toBe(true)

    // Start runs the staged floor as it stands — it must not swap in a different
    // layout under the user's eyes.
    const staged = engine.robots.map((r) => ({ x: r.x, z: r.z }))
    provider.start()
    expect(useSimulationProvider.getState().runState).toBe('running')
    expect(engine.robots.map((r) => ({ x: r.x, z: r.z }))).toEqual(staged)
    runFrame(16)
    runFrame(32)
    expect(engine.simTime).toBeGreaterThan(0)
  })

  it('starts a run with the crate count the setup form asked for', () => {
    const provider = useSimulationProvider.getState()
    provider.start({ itemCount: 7 })

    const state = useSimulationProvider.getState()
    expect(state.runState).toBe('running')
    expect(state.itemCount).toBe(7)
    expect(state.engine!.itemCount).toBe(7)
    expect(state.engine!.tasks).toHaveLength(7)
    // The run is seeded, and the mission id / form readout name that seed.
    expect(state.engine!.seed).toBe(state.seed)
  })

  it('applies a new crate count to a run that is already going', () => {
    const provider = useSimulationProvider.getState()
    provider.start({ itemCount: 30 })
    const first = useSimulationProvider.getState().engine!
    runFrame(16)
    runFrame(32)

    provider.start({ itemCount: 6 })

    // Same engine instance, restaged in place: empty clock, six crates, running.
    const second = useSimulationProvider.getState().engine!
    expect(second).toBe(first)
    expect(second.itemCount).toBe(6)
    expect(second.tasks).toHaveLength(6)
    expect(second.simTime).toBe(0)
    expect(second.completed).toBe(0)
    expect(useSimulationProvider.getState().runState).toBe('running')
  })
})
