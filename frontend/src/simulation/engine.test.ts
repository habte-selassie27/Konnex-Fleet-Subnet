// Engine integration tests — the pick-and-place cycle is the core of the demo,
// so it is tested by actually running the simulation loop, not by mocking it.
import { describe, expect, it } from 'vitest'

import {
  BIN_CAPACITY,
  DEFAULT_ITEMS,
  DEPOT_CENTER,
  MAX_ITEMS,
  MAX_LAYERS,
  MIN_CART_SEPARATION_M,
  MIN_ITEMS,
  PARK_MIN_DEPOT_M,
  SimulationEngine,
  blocks,
  cellToWorld,
  clampItemCount,
  distance,
  layerY,
  randomItemCount,
  slotWorld,
  worldToCell,
  type CargoTask,
} from './engine'

/** Advance the engine in fixed 60 Hz steps. */
function run(engine: SimulationEngine, seconds: number): void {
  const dt = 1 / 60
  const steps = Math.round(seconds / dt)
  for (let i = 0; i < steps; i++) engine.tick(dt)
}

function runUntil(engine: SimulationEngine, predicate: () => boolean, maxSeconds: number): void {
  const dt = 1 / 60
  const steps = Math.round(maxSeconds / dt)
  for (let i = 0; i < steps; i++) {
    if (predicate()) return
    engine.tick(dt)
  }
}

describe('grid <-> world', () => {
  it('round-trips every cell centre', () => {
    for (let x = 0; x < 40; x += 3) {
      for (let z = 0; z < 30; z += 3) {
        const world = cellToWorld({ x, z })
        expect(worldToCell(world.x, world.z)).toEqual({ x, z })
      }
    }
  })
})

describe('SimulationEngine mission cycle', () => {
  it('stages every crate on the floor before the first tick', () => {
    const engine = new SimulationEngine()
    expect(engine.robots).toHaveLength(5)
    expect(engine.tasks).toHaveLength(BIN_CAPACITY)
    expect(engine.totalSpawned).toBe(BIN_CAPACITY)
    // Dropped at t = 0, i.e. before any cart has had a chance to move.
    expect(engine.tasks.every((t) => t.spawnT === 0)).toBe(true)
    expect(engine.tasks.every((t) => t.status === 'bouncing')).toBe(true)
    // One pick cell per crate — no two crates share a spot.
    expect(new Set(engine.tasks.map((t) => `${t.pickupCell.x},${t.pickupCell.z}`)).size).toBe(
      BIN_CAPACITY,
    )

    // Nothing is spawned mid-run: the scenario stays exactly what was staged.
    run(engine, 120)
    expect(engine.totalSpawned).toBe(BIN_CAPACITY)
    expect(engine.tasks).toHaveLength(BIN_CAPACITY)
  })

  it('is deterministic for a given seed', () => {
    const a = new SimulationEngine()
    const b = new SimulationEngine()
    a.reset(2024)
    b.reset(2024)
    run(a, 3)
    run(b, 3)

    expect(a.robots.map((r) => [r.x.toFixed(4), r.z.toFixed(4)])).toEqual(
      b.robots.map((r) => [r.x.toFixed(4), r.z.toFixed(4)]),
    )
    expect(a.tasks.map((t) => t.id)).toEqual(b.tasks.map((t) => t.id))
  })

  it('picks a crate up, carries it, and stacks it in the bin', () => {
    const engine = new SimulationEngine()
    engine.reset(77)

    runUntil(engine, () => engine.completed > 0, 180)

    expect(engine.completed).toBeGreaterThan(0)
    expect(engine.collected).toBeGreaterThanOrEqual(engine.completed)

    const kinds = engine.events.map((e) => e.kind)
    expect(kinds).toContain('pickup')
    expect(kinds).toContain('stack')

    const delivered = engine.tasks.filter((t) => t.status === 'delivered')
    expect(delivered.length).toBe(engine.completed)
    for (const task of delivered) {
      expect(task.stack).not.toBeNull()
      expect(task.stackTarget).not.toBeNull()
      expect(task.stack?.layer).toBeGreaterThanOrEqual(0)
      expect(task.stack?.layer).toBeLessThan(MAX_LAYERS)
    }
  })

  it('places each crate at the exact slot coordinate for its layer', () => {
    const engine = new SimulationEngine()
    engine.reset(9)
    runUntil(engine, () => engine.completed > 0, 180)

    const task = engine.tasks.find((t: CargoTask) => t.status === 'delivered')
    expect(task?.stack).toBeTruthy()
    if (!task?.stack || !task.stackTarget) throw new Error('no delivered crate')

    const expected = slotWorld(task.stack.col, task.stack.row)
    expect(task.stackTarget.x).toBeCloseTo(expected.x, 6)
    expect(task.stackTarget.z).toBeCloseTo(expected.z, 6)
    expect(task.stackTarget.y).toBeCloseTo(layerY(task.stack.layer), 6)
  })

  it('fills one bay to MAX_LAYERS before starting the next', () => {
    const engine = new SimulationEngine()
    engine.reset(5)
    runUntil(engine, () => engine.completed >= 5, 400)

    const layers = engine.depot.slots.map((s) => s.layers).sort((a, b) => b - a)
    expect(layers[0]).toBe(MAX_LAYERS)
    expect(layers.reduce((a, b) => a + b, 0)).toBe(engine.completed)
  })

  it('never exceeds the bin capacity and reports when full', () => {
    const engine = new SimulationEngine()
    expect(engine.binFull()).toBe(false)
    expect(BIN_CAPACITY).toBe(36)
    expect(DEFAULT_ITEMS).toBe(BIN_CAPACITY)
  })

  it('reports a full bin only once every crate is physically stacked', () => {
    const engine = new SimulationEngine()
    engine.reset(11)

    // Regression: slot bookings held by carts still driving used to count as
    // stacked crates, so the run declared "mission complete" at ~31/36 with
    // crates still on the floor. A full bin must mean 36 crates in the bin.
    runUntil(engine, () => engine.binFull(), 900)

    expect(engine.binFull()).toBe(true)
    // Finishes inside the mission time limit rather than timing out at 600 s.
    expect(engine.simTime).toBeLessThan(600)
    expect(engine.completed).toBe(BIN_CAPACITY)
    expect(engine.depot.slots.reduce((sum, s) => sum + s.layers, 0)).toBe(BIN_CAPACITY)
    expect(engine.depot.slots.reduce((sum, s) => sum + s.reserved, 0)).toBe(0)
    expect(engine.tasks.filter((t) => t.status === 'in_transit')).toHaveLength(0)
  })

  it('keeps the event feed bounded', () => {
    const engine = new SimulationEngine()
    run(engine, 400)
    expect(engine.events.length).toBeLessThanOrEqual(40)
    // newest events last
    const ids = engine.events.map((e) => e.id)
    expect([...ids].sort((a, b) => a - b)).toEqual(ids)
  })

  it('accumulates battery energy drawn by the fleet', () => {
    const engine = new SimulationEngine()
    engine.reset(77)
    const before = engine.snapshot().energyUsed
    run(engine, 60)
    expect(engine.snapshot().energyUsed).toBeGreaterThan(before)
    // reset clears the counter for a fresh demo
    engine.reset(77)
    expect(engine.snapshot().energyUsed).toBe(0)
  })
})

describe('run setup — crate drop count (5..40)', () => {
  it('stages exactly the requested count, all before the first tick', () => {
    const engine = new SimulationEngine()
    engine.reset(31, 12)

    expect(engine.itemCount).toBe(12)
    expect(engine.binCapacity).toBe(12)
    expect(engine.tasks).toHaveLength(12)
    expect(engine.totalSpawned).toBe(12)
    expect(engine.tasks.every((t) => t.spawnT === 0)).toBe(true)
    expect(engine.snapshot().binCapacity).toBe(12)

    // No crate is added mid-run: the floor is exactly what was staged.
    run(engine, 30)
    expect(engine.totalSpawned).toBe(12)
    expect(engine.tasks).toHaveLength(12)
  })

  it('clamps out-of-range counts into the supported drop', () => {
    const engine = new SimulationEngine()
    engine.reset(1, 2)
    expect(engine.tasks).toHaveLength(MIN_ITEMS)

    engine.reset(1, 400)
    expect(engine.tasks).toHaveLength(MAX_ITEMS)
  })

  it('rolls a random count inside 5..40', () => {
    for (let i = 0; i < 200; i++) {
      const n = randomItemCount()
      expect(Number.isInteger(n)).toBe(true)
      expect(n).toBeGreaterThanOrEqual(MIN_ITEMS)
      expect(n).toBeLessThanOrEqual(MAX_ITEMS)
    }
    expect(randomItemCount(() => 0)).toBe(MIN_ITEMS)
    expect(randomItemCount(() => 0.999999)).toBe(MAX_ITEMS)
    expect(clampItemCount(1)).toBe(MIN_ITEMS)
    expect(clampItemCount(999)).toBe(MAX_ITEMS)
    expect(clampItemCount(Number.NaN)).toBe(DEFAULT_ITEMS)
  })

  it('builds taller stacks when a run drops more than the 36-slot grid holds', () => {
    const engine = new SimulationEngine()
    // 40 crates need 5 layers over the 9 bays; the default grid holds 4 layers.
    engine.reset(7, MAX_ITEMS)
    expect(engine.tasks).toHaveLength(MAX_ITEMS)

    runUntil(engine, () => engine.binFull(), 900)

    expect(engine.binFull()).toBe(true)
    expect(engine.completed).toBe(MAX_ITEMS)
    expect(engine.depot.slots.reduce((sum, s) => sum + s.layers, 0)).toBe(MAX_ITEMS)
    expect(Math.max(...engine.depot.slots.map((s) => s.layers))).toBeGreaterThan(MAX_LAYERS)
    expect(engine.tasks.filter((t) => t.status !== 'delivered')).toHaveLength(0)
  })
})

describe('random cart start positions', () => {
  it('places all five carts on clear cells, apart from each other and off the crates', () => {
    const engine = new SimulationEngine()
    engine.reset(4242, 20)

    expect(engine.robots).toHaveLength(5)
    for (const robot of engine.robots) {
      const cell = worldToCell(robot.x, robot.z)
      expect(blocks[cell.z][cell.x]).toBe(false)
      expect(robot.x).toBeGreaterThan(-20)
      expect(robot.x).toBeLessThan(20)
      expect(robot.z).toBeGreaterThan(-15)
      expect(robot.z).toBeLessThan(15)
    }

    for (let i = 0; i < engine.robots.length; i++) {
      for (let j = i + 1; j < engine.robots.length; j++) {
        const a = engine.robots[i]
        const b = engine.robots[j]
        const gap = Math.hypot(a.x - b.x, a.z - b.z)
        expect(gap).toBeGreaterThanOrEqual(MIN_CART_SEPARATION_M - 1e-6)
      }
    }

    // No crate is dropped on a cell a cart starts from.
    const crateCells = new Set(engine.tasks.map((t) => `${t.pickupCell.x},${t.pickupCell.z}`))
    for (const robot of engine.robots) {
      const cell = worldToCell(robot.x, robot.z)
      expect(crateCells.has(`${cell.x},${cell.z}`)).toBe(false)
    }
  })

  it('stages a seed identically, and different seeds differently', () => {
    const a = new SimulationEngine()
    const b = new SimulationEngine()
    a.reset(1000, 20)
    b.reset(1000, 20)
    const cars = (e: SimulationEngine) => e.robots.map((r) => [r.x, r.z])
    const drops = (e: SimulationEngine) => e.tasks.map((t) => `${t.pickupCell.x},${t.pickupCell.z}`)
    expect(cars(a)).toEqual(cars(b))
    expect(drops(a)).toEqual(drops(b))

    a.reset(2000, 20)
    expect(cars(a)).not.toEqual(cars(b))
    expect(drops(a)).not.toEqual(drops(b))
  })
})

describe('dispatch policies', () => {
  it('fills the bin under every allocator', () => {
    for (const policy of ['nearest', 'hungarian', 'cost_optimizer'] as const) {
      const engine = new SimulationEngine()
      engine.reset(4242, 12, policy)
      expect(engine.policy).toBe(policy)
      runUntil(engine, () => engine.binFull(), 900)
      expect(engine.binFull(), policy).toBe(true)
      expect(engine.snapshot().policy).toBe(policy)
    }
  })
})

describe('end of a run — the fleet parks clear of the bin', () => {
  it('parks each cart on its own spot, away from the deposit frontage', () => {
    const engine = new SimulationEngine()
    engine.reset(11, 5)
    runUntil(engine, () => engine.runComplete(), 900)

    expect(engine.binFull()).toBe(true)
    // Every cart settled on the floor, not still driving.
    for (const robot of engine.robots) {
      expect(robot.nav_state).toBe('staging')
      expect(robot.pathIndex).toBeGreaterThanOrEqual(robot.path.length)
    }

    // Five distinct spots, all at least a cart-width + margin apart…
    for (let i = 0; i < engine.robots.length; i++) {
      for (let j = i + 1; j < engine.robots.length; j++) {
        const a = engine.robots[i]
        const b = engine.robots[j]
        expect(distance({ x: a.x, z: a.z }, { x: b.x, z: b.z })).toBeGreaterThanOrEqual(
          MIN_CART_SEPARATION_M - 1e-6,
        )
      }
    }

    // … and none of them nose-to-tail against the bin, where the piled-up fleet
    // used to hide the finished stacks.
    for (const robot of engine.robots) {
      expect(distance({ x: robot.x, z: robot.z }, DEPOT_CENTER)).toBeGreaterThanOrEqual(
        PARK_MIN_DEPOT_M - 1e-6,
      )
    }
  })

  it('does not report the run complete until the carts have parked', () => {
    const engine = new SimulationEngine()
    engine.reset(11, 5)
    runUntil(engine, () => engine.binFull(), 900)

    // The bin fills while the fleet is still standing on the aisle.
    expect(engine.runComplete()).toBe(false)

    runUntil(engine, () => engine.runComplete(), 60)
    expect(engine.cartsParked()).toBe(true)
  })
})
