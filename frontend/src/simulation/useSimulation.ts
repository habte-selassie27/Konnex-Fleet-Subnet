// Hooks for binding SimulationEngine to the React tree.
// Strategy:
//  • The engine runs on rAF off the React render path.
//  • A Zustand store holds the last published snapshot (published at ~12 Hz, not
//    every frame) so React components only re-render when new state is published.
//  • Mesh components read live engine objects through the snapshot and interpolate
//    in useFrame, so motion is smooth and React does not churn per frame.
import { create } from 'zustand'

import type { EnergySample } from '../types'
import {
  CART_BATTERY_UNITS,
  DEFAULT_ITEMS,
  EngineSnapshot,
  SimPolicy,
  SimulationEngine,
  clampItemCount,
} from './engine'

export {
  WORLD_W,
  WORLD_D,
  DEPOT_COLS,
  DEPOT_ROWS,
  CRATE_SIZE,
  SLOT_PITCH,
  LAYER_PITCH,
  MAX_LAYERS,
  BIN_CAPACITY,
  MIN_ITEMS,
  MAX_ITEMS,
  DEFAULT_ITEMS,
  SIM_POLICIES,
  SIM_POLICY_ALGORITHMS,
  type SimPolicy,
  clampItemCount,
  randomItemCount,
  DEPOT_CENTER,
  BIN_W,
  BIN_D,
  BIN_WALL_H,
  BIN_FLOOR_Y,
  SHELF_DEFS,
  slotWorld,
  layerY,
  bayLabel,
  cellToWorld,
  worldToCell,
  LIFT_LOW,
  LIFT_HIGH,
  CARRIED_CRATE_OFFSET,
} from './engine'

const SNAPSHOT_INTERVAL_MS = 83 // ~12 Hz snapshots — smooth enough for the HUD

interface SimulationState {
  dirty: boolean
  snapshot: EngineSnapshot | null
  /** Cumulative energy samples from the same run as `snapshot`. */
  energyHistory: EnergySample[]
  /** The live engine instance owned by the simulation provider. */
  engine: SimulationEngine | null
  reset: () => void
}

const MAX_ENERGY_SAMPLES = 900
const ENERGY_SAMPLE_INTERVAL_S = 1.0

// Zustand store: holds the latest snapshot published by the engine loop.
const useSimStore = create<SimulationState>((set) => ({
  dirty: false,
  snapshot: null,
  energyHistory: [],
  engine: null,
  reset: () => set({ dirty: false, snapshot: null, energyHistory: [], engine: null }),
}))

/** True playback state of the local engine run. This is the single source of
 * truth for the SIM badge and the play-control button labels, so the dashboard
 * can never imply the sim is running when it is not (AGENTS.md §1.6 / §0.3).
 */
export type SimRunState = 'idle' | 'running' | 'paused' | 'finished'

export const useSimulationProvider = create<{
  mode: 'sim' | 'live'
  engine: SimulationEngine | null
  initialized: boolean
  runState: SimRunState
  /** crates dropped on the floor for the next/current run (MIN_ITEMS..MAX_ITEMS) */
  itemCount: number
  /** seed of the scenario currently staged or running */
  seed: number
  /** allocator dispatching crates to carts (also carried by each snapshot) */
  policy: SimPolicy
  /** Switch the dispatch allocator; applies to the current run and later runs. */
  setPolicy: (policy: SimPolicy) => void
  /**
   * Run a mission. A scenario staged by reset() (idle, clock at zero, same crate
   * count) is run exactly as it stands; anything else — a finished run, an
   * explicit crate count from the setup form, or an explicit seed from the Run
   * Mission panel — stages a fresh run, so every run gets a different crate drop
   * and a different cart start layout. Providing `seed` makes the staged floor
   * reproducible from that seed alone.
   */
  start: (opts?: { itemCount?: number; seed?: number; policy?: SimPolicy }) => void
  pause: () => void
  resume: () => void
  stop: () => void
  reset: () => void
  setMode: (m: 'sim' | 'live') => void
}>((set, get) => {
  let engine: SimulationEngine | null = null
  let rafId: number | null = null
  let lastFrameAt = 0
  let lastSnapshotAt = 0
  let runState: SimRunState = 'idle'
  let seed = 1337

  /** New seed per staged run — this is what makes each start a new floor. */
  const rollSeed = () => Math.floor(Math.random() * 1_000_000)

  // Finished means the bin is full *and* the fleet has parked clear of it, so the
  // frozen frame shows all five carts instead of a heap on the deposit aisle.
  const isFinished = (e: SimulationEngine) => e.runComplete()

  const cancelLoop = () => {
    if (rafId != null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  const publish = (force = false) => {
    if (!engine) return
    const finished = isFinished(engine)
    const now = performance.now()
    // A finishing tick must always publish its final snapshot, even if the
    // 12 Hz throttle would otherwise skip this frame.
    if (!force && !finished && now - lastSnapshotAt < SNAPSHOT_INTERVAL_MS) return
    lastSnapshotAt = now

    const snapshot = engine.snapshot()
    const state = useSimStore.getState()
    const last = state.energyHistory[state.energyHistory.length - 1]
    // Throttle the energy series to ~1 Hz; the chart still resolves the same
    // curve and the 12 Hz telemetry does not flood it. Samples are only recorded
    // for real elapsed time — a freshly reset run must not seed a 0 J point that
    // reads as measured data.
    if (
      snapshot.simTime > 0 &&
      (!last || snapshot.simTime - last.t >= ENERGY_SAMPLE_INTERVAL_S)
    ) {
      useSimStore.setState({
        dirty: true,
        snapshot,
        energyHistory: [
          ...state.energyHistory,
          { t: snapshot.simTime, energy: snapshot.energyUsed * CART_BATTERY_UNITS },
        ].slice(-MAX_ENERGY_SAMPLES),
      })
    } else {
      useSimStore.setState({ dirty: true, snapshot })
    }

    // Keep the UI's run-state label honest with the engine's real state: the
    // mission ends when the bin is full, and the loop stops behind it so the
    // result is frozen rather than continuing to tick off-mission.
    if (finished && runState !== 'finished') {
      runState = 'finished'
      set({ runState })
    }
  }

  const loop = (now: number) => {
    rafId = null
    if (!engine) return

    const dt = lastFrameAt === 0 ? 0 : Math.min(0.05, (now - lastFrameAt) / 1000)
    lastFrameAt = now

    if (dt > 0) engine.tick(dt)
    publish()

    // Only the loop that is still supposed to be running reschedules itself;
    // pause()/reset()/finish all leave rafId null so nothing restarts in the
    // background.
    if (runState === 'running') rafId = requestAnimationFrame(loop)
  }

  /**
   * Start (or restart) a run. Idempotent while running so a double click — or a
   * double-invoked mount effect — never rewinds a live run.
   */
  const startRun = (opts?: { itemCount?: number; seed?: number; policy?: SimPolicy }) => {
    // Idempotent while running (double click, double-invoked mount effect) — but
    // an explicit crate count or seed always stages that new run.
    if (runState === 'running' && opts?.itemCount === undefined && opts?.seed === undefined) return
    cancelLoop()

    const policy = opts?.policy ?? get().policy

    // A brand-new engine holds the constructor's default scenario, which is not
    // staged for this run — only reset() stages one.
    const fresh = engine === null
    const current = engine ?? new SimulationEngine()
    engine = current

    const count = clampItemCount(opts?.itemCount ?? get().itemCount)
    // A scenario staged by reset() and never played yet is run exactly as staged
    // — unless the caller named a seed, which must produce that exact floor.
    const staged =
      !fresh &&
      runState === 'idle' &&
      current.simTime === 0 &&
      current.itemCount === count &&
      opts?.seed === undefined
    if (!staged) {
      seed = opts?.seed === undefined ? rollSeed() : Math.trunc(opts.seed)
      current.reset(seed, count, policy)
      useSimStore.getState().reset()
      useSimStore.setState({ engine: current })
    } else {
      // A staged floor runs as-is; only the allocator can change on this path.
      current.policy = policy
    }

    lastFrameAt = 0
    lastSnapshotAt = 0
    runState = 'running'
    set({
      engine: current,
      initialized: true,
      mode: 'sim',
      runState,
      seed: current.seed,
      itemCount: count,
      policy,
    })
    // prime the first snapshot so React shows something immediately
    publish(true)
    rafId = requestAnimationFrame(loop)
  }

  return {
    mode: 'sim',
    engine: null,
    initialized: false,
    runState: 'idle',
    itemCount: DEFAULT_ITEMS,
    seed,
    policy: 'nearest',
    start(opts) {
      startRun(opts)
    },
    setPolicy(policy) {
      if (engine) engine.policy = policy
      set({ policy })
    },
    pause() {
      if (runState !== 'running') return
      // Stop advancing the engine but keep it (and its last snapshot) intact so
      // every cart freezes exactly where it was.
      cancelLoop()
      runState = 'paused'
      set({ runState })
    },
    resume() {
      if (runState !== 'paused') return
      // lastFrameAt = 0 makes the next frame use dt = 0, so resuming does not
      // teleport carts forward by the length of the pause.
      lastFrameAt = 0
      runState = 'running'
      set({ runState })
      rafId = requestAnimationFrame(loop)
    },
    stop() {
      cancelLoop()
      runState = 'idle'
      set({ engine: null, initialized: false, runState })
    },
    reset() {
      // Stage a fresh run: new seed (new crate drop, new cart starts), bin empty,
      // clock at zero, loop stopped. The staged floor is what Start then runs, so
      // pressing Start never rewrites the scene the user is looking at.
      cancelLoop()
      if (!engine) engine = new SimulationEngine()
      seed = rollSeed()
      const count = clampItemCount(get().itemCount)
      engine.reset(seed, count, get().policy)
      useSimStore.getState().reset()
      useSimStore.setState({ engine })
      lastFrameAt = 0
      lastSnapshotAt = 0
      runState = 'idle'
      set({ engine, initialized: true, runState, seed, itemCount: count })
      publish(true)
    },
    setMode(m) {
      set({ mode: m })
    },
  }
})

export function useSimulationSnapshot() {
  const snapshot = useSimStore((s) => s.snapshot)
  const dirty = useSimStore((s) => s.dirty)
  const engine = useSimStore((s) => s.engine)
  return { snapshot, dirty, engine }
}

export function useSimulationEnergyHistory(): EnergySample[] {
  return useSimStore((s) => s.energyHistory)
}
