// Simulation engine for the Konnex Fleet Intelligence viewport.
//
// Runs a deterministic, local multi-agent AMR sim (idle → cargo → depot → stack),
// driven entirely client-side from a per-run seed. It is the fallback viewer when
// the live Gazebo backend is not connected: the HUD badge then reads SIM instead
// of LIVE, and the map renders the engine's own state rather than any fabricated
// "live" feed. When the WebSocket is online, the live renderer path
// (WarehouseMap / WarehouseRobot) stays active — this engine is not mixed in
// behind a fake LIVE badge. Per AGENTS.md §1.6 / §0.3 that distinction is the
// whole point.
//
// Tick loop is rAF-driven; React reads a snapshot at ~12 Hz so mesh motion stays
// smooth and React does not churn per frame.
//
// Physical model
// --------------
// Crates spawn on free floor cells. An idle cart is auctioned the nearest crate,
// drives an adjacent approach cell, aligns its forks, lifts the crate (it becomes
// a child of the cart's gripper anchor in the scene graph), carries it to the
// storage bin, and places it into an exact (col, row, layer) stack slot.
//
// All geometry constants here are shared with the R3F meshes so the visual
// placement and the engine state can never disagree.
//
// Payments / agent-economy
// -------------------------
// The engine does not gate or fire payments itself. Payments are driven by live
// fleet telemetry through the backend's fleet-payment bridge / payments router
// (backend/services/fleet_payment_bridge.py, backend/routers/payments.py): a
// robot is only paid when the bridge classifies it as FAILED (maintenance) or
// critically low on battery (charging). The client-side sim is not a payment
// source — it is a fallback viewer. To drive the agent wallet and transaction
// history with deterministic numbers, run `make payment-demo`; that runs a
// deterministic quote -> authorize -> execute cycle and settles USDC on Arc
// (mock by default, labeled as such in the panel). That is the honest way to
// put numbers in the FleetPay panel without awaiting a real mission failure.
//
// Client-side hook: when a cart in the sim reaches its task delivery and drops
// off a crate, it emits a TEAM_REWARD event carrying the cart id, the task id,
// and the reward amount (battery units cashed in at the configured rate). That
// event is the natural future extension point for a client-side payment preview,
// but it is currently informational only — no USDC moves, no Arc tx, no wallet
// spend. Extending it to a real payment path would require either a live backend
// endpoint or a clearly-labeled client-side demo overlay, and should never fake
// an on-chain settlement (AGENTS.md Law 1).

// ─── World ─────────────────────────────────────────────────────────────────────

export const WORLD_W = 40
export const WORLD_D = 30
const CELL = 1
const GRID_W = WORLD_W
const GRID_D = WORLD_D
const W = GRID_W
const D = GRID_D

// ─── Storage bin (physical drop-off container) ─────────────────────────────────

export const DEPOT_COLS = 3
export const DEPOT_ROWS = 3
export const MAX_LAYERS = 4
export const CRATE_SIZE = 0.5
export const SLOT_PITCH = 0.54
export const LAYER_PITCH = 0.5
export const BIN_W = 2.2
export const BIN_D = 2.2
export const BIN_WALL_H = 0.55
export const BIN_FLOOR_Y = 0.08
export const BIN_CAPACITY = DEPOT_COLS * DEPOT_ROWS * MAX_LAYERS

/**
 * Crate-drop bounds for one run. The run-setup form lets an operator drop any
 * count in this range, or roll one at random; the bin grows taller when a run
 * drops more crates than its 9 bays × 4 layers can hold.
 */
export const MIN_ITEMS = 5
export const MAX_ITEMS = 40
/** Default drop count — the 36 slots of the current bin grid. */
export const DEFAULT_ITEMS = BIN_CAPACITY

/** Clamp a requested crate count into the supported range. */
export function clampItemCount(count: number): number {
  if (!Number.isFinite(count)) return DEFAULT_ITEMS
  return Math.min(MAX_ITEMS, Math.max(MIN_ITEMS, Math.round(count)))
}

/**
 * Roll a random crate count for a run. `rand` is injectable so a seeded caller
 * (or a test) can drive it instead of Math.random.
 */
export function randomItemCount(rand: () => number = Math.random): number {
  return clampItemCount(MIN_ITEMS + Math.floor(rand() * (MAX_ITEMS - MIN_ITEMS + 1)))
}

/**
 * Minimum gap between cart start positions. Carts are 1.2 m wide and the engine
 * flags a proximity stop under 1.4 m, so a run must never begin tighter than this.
 */
export const MIN_CART_SEPARATION_M = 2.2

/**
 * Where the fleet parks once the bin is full: a few metres back from the bin so
 * the finished stacks stay readable and every cart is visible on its own spot
 * instead of all five ending nose-to-tail against the deposit frontage.
 */
export const PARK_MIN_DEPOT_M = 3.4
export const PARK_MAX_DEPOT_M = 7.0
/** One parking spot per cart in the fleet. */
export const PARK_SLOTS = 5
/** Seconds the fleet gets to reach its parking spot before the run is called done. */
export const PARK_SETTLE_TIMEOUT_S = 12

/**
 * PoPW energy unit: 1 u = 1 % of one cart battery. A full cart therefore holds
 * 100 u, and a five-cart fleet has a 500 u budget — the same budget the
 * validator's evaluation artifacts use (data/artifacts/*). The engine tracks
 * cumulative drain in battery units (0..1); the dashboard multiplies by this.
 */
export const CART_BATTERY_UNITS = 100

export const DEPOT_CENTER = { x: 14, z: -13 }

// Grid row immediately in front of the bin (bin front face sits at z ≈ -11.9).
export const APPROACH_ROW = 25

// Cart fork-carriage travel. `liftY` is the height of the fork tines above the
// floor, shared verbatim with the R3F cart so mesh and state agree.
export const LIFT_LOW = 0.16
export const LIFT_HIGH = 0.52
/** Crate centre height above the tines when carried (crate rests on the forks). */
export const CARRIED_CRATE_OFFSET = 0.3

/** World position of a stack slot (row 0 = front row, closest to the aisle). */
export function slotWorld(col: number, row: number): { x: number; z: number } {
  return {
    x: DEPOT_CENTER.x + (col - 1) * SLOT_PITCH,
    z: DEPOT_CENTER.z + (1 - row) * SLOT_PITCH,
  }
}

/** World Y of the centre of a crate resting at `layer` inside the bin. */
export function layerY(layer: number): number {
  return BIN_FLOOR_Y + CRATE_SIZE / 2 + layer * LAYER_PITCH
}

/** Human-readable bay id, e.g. "A1" .. "C3". */
export function bayLabel(col: number, row: number): string {
  return `${String.fromCharCode(65 + col)}${row + 1}`
}

// ─── Grid / occupancy ──────────────────────────────────────────────────────────

export interface GridPoint {
  x: number // cell column index, 0..W-1
  z: number // cell row index, 0..D-1
}

export function cellToWorld(gp: GridPoint): { x: number; z: number } {
  return { x: (gp.x + 0.5) * CELL - WORLD_W / 2, z: -((gp.z + 0.5) * CELL - WORLD_D / 2) }
}

export function worldToCell(x: number, z: number): GridPoint {
  // Exact inverse of cellToWorld: x = (c + 0.5) - W/2, z = -(r + 0.5) + D/2.
  // (The previous inverse was off by half a cell, which made path goals land on
  // the neighbouring cell and carts stop short of their target.)
  return {
    x: Math.max(0, Math.min(W - 1, Math.round(x + WORLD_W / 2 - 0.5))),
    z: Math.max(0, Math.min(D - 1, Math.round(-z + WORLD_D / 2 - 0.5))),
  }
}

export function distance(a: { x: number; z: number }, b: { x: number; z: number }): number {
  const dx = a.x - b.x
  const dz = a.z - b.z
  return Math.sqrt(dx * dx + dz * dz)
}

/**
 * Paths are found on the grid (cell indices) but followed in world metres.
 * Every assignment must go through this conversion — mixing the two spaces was
 * why carts used to drive to nonsense coordinates.
 */
function toWorldPath(cells: Array<{ x: number; z: number }>): Array<{ x: number; z: number }> {
  return cells.map((c) => cellToWorld(c))
}

// ─── Obstacles (shelf racks) ────────────────────────────────────────────────────

export interface ShelfDef {
  x: number
  z: number
  w: number
  d: number
}

export const SHELF_DEFS: readonly ShelfDef[] = [
  { x: 6, z: 6, w: 4, d: 1 },
  { x: 6, z: 12, w: 4, d: 1 },
  { x: 6, z: 18, w: 4, d: 1 },
  { x: 14, z: 4, w: 1, d: 4 },
  { x: 14, z: 10, w: 1, d: 4 },
  { x: 14, z: 16, w: 1, d: 4 },
  { x: 22, z: 7, w: 4, d: 1 },
  { x: 22, z: 14, w: 4, d: 1 },
  { x: 28, z: 5, w: 1, d: 4 },
  { x: 28, z: 11, w: 1, d: 4 },
  { x: 28, z: 17, w: 1, d: 4 },
  { x: 18, z: 24, w: 3, d: 1 },
  { x: 10, z: 25, w: 1, d: 3 },
]

export function isDepotCell(c: number, r: number): boolean {
  return c >= 32 && c < 36 && r >= 26 && r < 30
}

export function isStagingCell(c: number, r: number): boolean {
  return c >= 4 && c < 8 && r >= 2 && r < 6
}

// grid[r][c] == true means the cell centre is blocked.
export const blocks: boolean[][] = Array.from({ length: D }, () => new Array(W).fill(false))

for (const s of SHELF_DEFS) {
  for (let r = s.z; r < s.z + s.d; r += 1) {
    for (let c = s.x; c < s.x + s.w; c += 1) {
      blocks[r][c] = true
    }
  }
}

// The bin body is solid: carts must stop in the aisle (APPROACH_ROW) in front of
// it rather than drive through the walls.
for (let r = 26; r < 30; r += 1) {
  for (let c = 32; c < 36; c += 1) {
    blocks[r][c] = true
  }
}

// ─── A* on the 4-connected grid ───────────────────────────────────────────────

interface QueueEntry {
  f: number
  r: number
  c: number
  parent: QueueEntry | null
}

function heuristic(a: GridPoint, b: GridPoint): number {
  // 4-connected grid => Manhattan distance is exact.
  return Math.abs(a.x - b.x) + Math.abs(a.z - b.z)
}

export function findPath(
  start: GridPoint,
  goal: GridPoint,
): Array<{ x: number; z: number }> {
  if (start.x === goal.x && start.z === goal.z) return []
  if (blocks[goal.z][goal.x] || blocks[start.z][start.x]) return []

  const gScore = new Map<string, number>()
  const closed = new Set<string>()
  const key = (r: number, c: number): string => `${r},${c}`

  const startKey = key(start.z, start.x)
  gScore.set(startKey, 0)

  const open: QueueEntry[] = []
  open.push({ f: heuristic(start, goal), r: start.z, c: start.x, parent: null })

  while (open.length) {
    // linear scan for min-f — cheap at this grid size (1200 cells)
    let best = 0
    for (let i = 1; i < open.length; i++) if (open[i].f < open[best].f) best = i
    const curr = open.splice(best, 1)[0]
    const ck = key(curr.r, curr.c)
    if (closed.has(ck)) continue
    closed.add(ck)

    if (curr.c === goal.x && curr.r === goal.z) {
      const out: Array<{ x: number; z: number }> = []
      let n: QueueEntry | null = curr
      while (n) {
        out.push({ x: n.c, z: n.r })
        n = n.parent
      }
      out.reverse()
      // drop the start cell — the cart is already there
      return out.slice(1)
    }

    const curG = gScore.get(ck)!
    for (const [dr, dc] of [
      [1, 0],
      [-1, 0],
      [0, 1],
      [0, -1],
    ] as const) {
      const nr = curr.r + dr
      const nc = curr.c + dc
      if (nr < 0 || nr >= D || nc < 0 || nc >= W) continue
      if (blocks[nr][nc]) continue
      const nk = key(nr, nc)
      if (closed.has(nk)) continue
      const tentative = curG + 1
      const prev = gScore.get(nk)
      if (prev === undefined || tentative < prev) {
        gScore.set(nk, tentative)
        open.push({
          f: tentative + heuristic({ x: nc, z: nr }, goal),
          r: nr,
          c: nc,
          parent: curr,
        })
      }
    }
  }

  return [] // no path
}

// ─── State machine ─────────────────────────────────────────────────────────────

export type RobotNavState =
  | 'idle'
  | 'moving_to_cargo'
  | 'picking_up'
  | 'moving_to_depot'
  | 'depositing_stack'
  | 'charging'
  | 'staging'

export interface RobotSim {
  id: string
  index: number
  // world-space metres (x over, z into the screen)
  x: number
  z: number
  heading: number // radians around Y; local +Z (the forks) points along travel
  vx: number
  vz: number
  battery: number // 0..1
  nav_state: RobotNavState
  task_id: string | null

  // anim
  liftY: number // carriage height above the deck, metres
  forkExtension: number // 0 = retracted, 1 = fully extended

  // path
  path: Array<{ x: number; z: number }>
  pathIndex: number

  // move
  speed: number // m/s
  // pick / deposit animation progress 0..1
  animT: number

  // task assignment
  assignedTaskId: string | null
  depositStack: { col: number; row: number; layer: number } | null

  // collision cooldown so we don't flip-flop back and forth
  collisionCooldown: number
}

// ─── Dispatch policy ───────────────────────────────────────────────────────────

/**
 * Which allocator dispatches the floor crates to the carts.
 *
 * - `nearest`        — contract-net auction: the cheapest idle cart takes the
 *                      next crate (greedy, one dispatch per tick).
 * - `hungarian`      — optimal one-to-one matching of every idle cart to a
 *                      crate each dispatch round (global minimum total cost).
 * - `cost_optimizer` — multi-factor cost: distance, battery reserve and local
 *                      congestion, so a low-battery cart is not sent across the
 *                      floor and converging carts are spread out.
 */
export type SimPolicy = 'nearest' | 'hungarian' | 'cost_optimizer'

export const SIM_POLICIES: SimPolicy[] = ['nearest', 'hungarian', 'cost_optimizer']

export const SIM_POLICY_ALGORITHMS: Record<SimPolicy, string> = {
  nearest: 'NearestTaskAllocator',
  hungarian: 'HungarianAllocator',
  cost_optimizer: 'CostOptimizerAllocator',
}

// ─── Cargo task ─────────────────────────────────────────────────────────────────

export interface CargoTask {
  id: string
  index: number
  spawnT: number
  pickup: { x: number; z: number } // metres
  pickupCell: GridPoint
  status: 'bouncing' | 'assigned' | 'in_transit' | 'delivered'
  assignedRobot: string | null
  // spawn animation offset so crates appear at staggered heights
  spawnPhase: number
  // exact stack slot once delivered
  stack: { col: number; row: number; layer: number } | null
  stackTarget: { x: number; y: number; z: number } | null
}

// ─── Depot slots ────────────────────────────────────────────────────────────────

export interface DepotSlot {
  col: number
  row: number
  layers: number // placed crates, 0..MAX_LAYERS
  reserved: number // slots claimed by carts currently en route
}

export interface DepotMatrix {
  slots: DepotSlot[]
}

function makeDepot(): DepotMatrix {
  const slots: DepotSlot[] = []
  for (let row = 0; row < DEPOT_ROWS; row++) {
    for (let col = 0; col < DEPOT_COLS; col++) {
      slots.push({ col, row, layers: 0, reserved: 0 })
    }
  }
  return { slots }
}

// ─── Sim events (HUD status feed) ──────────────────────────────────────────────

export type SimEventKind = 'spawn' | 'assign' | 'pickup' | 'stack' | 'collision' | 'charge' | 'full'

export interface SimEvent {
  id: number
  t: number
  kind: SimEventKind
  robotId: string | null
  taskId: string | null
  message: string
}

// ─── Engine ─────────────────────────────────────────────────────────────────────

export interface EngineSnapshot {
  robots: RobotSim[]
  tasks: CargoTask[]
  depot: DepotMatrix
  simTime: number
  collisions: number
  /** crates picked up off the floor */
  collected: number
  /** crates placed in the storage bin */
  stacked: number
  /**
   * Cumulative battery energy drawn by the fleet, in battery units (0..1 per
   * cart). Multiply by 100 for the PoPW energy unit used by the dashboard:
   * 1 u = 1 % of one cart battery. Charging does not subtract from this — it
   * counts energy actually consumed, not net state of charge.
   */
  energyUsed: number
  totalSpawned: number
  /** crates stacked per minute over the trailing 60 s window */
  throughputPerMin: number
  events: SimEvent[]
  /** seed this run was staged from — a new start rolls a new seed, so new layout */
  seed: number
  /** crates dropped on the floor for this run (5..40) */
  itemCount: number
  /** bin slots this run has to fill (= itemCount) */
  binCapacity: number
  binFull: boolean
  /** allocator dispatching crates to carts for this run */
  policy: SimPolicy
}

const THROUGHPUT_WINDOW_S = 60
const EVENT_LOG_LIMIT = 40

/**
 * Hungarian / Kuhn-Munkres optimal assignment for a rectangular cost matrix
 * (rows must be the smaller side; callers transpose when they are not).
 * Returns `[row, col]` pairs minimising the total cost.
 */
function optimalPairs(cost: number[][]): Array<[number, number]> {
  const n = cost.length
  if (n === 0) return []
  const m = cost[0].length
  if (m === 0) return []

  const u = new Array<number>(n + 1).fill(0)
  const v = new Array<number>(m + 1).fill(0)
  const p = new Array<number>(m + 1).fill(0)
  const way = new Array<number>(m + 1).fill(0)

  for (let i = 1; i <= n; i++) {
    p[0] = i
    let j0 = 0
    const minv = new Array<number>(m + 1).fill(Infinity)
    const used = new Array<boolean>(m + 1).fill(false)
    do {
      used[j0] = true
      const i0 = p[j0]
      let delta = Infinity
      let j1 = 0
      for (let j = 1; j <= m; j++) {
        if (used[j]) continue
        const cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
        if (cur < minv[j]) {
          minv[j] = cur
          way[j] = j0
        }
        if (minv[j] < delta) {
          delta = minv[j]
          j1 = j
        }
      }
      for (let j = 0; j <= m; j++) {
        if (used[j]) {
          u[p[j]] += delta
          v[j] -= delta
        } else {
          minv[j] -= delta
        }
      }
      j0 = j1
    } while (p[j0] !== 0)

    do {
      const j1 = way[j0]
      p[j0] = p[j1]
      j0 = j1
    } while (j0 !== 0)
  }

  const pairs: Array<[number, number]> = []
  for (let j = 1; j <= m; j++) {
    if (p[j] !== 0) pairs.push([p[j] - 1, j - 1])
  }
  return pairs
}

/** Deterministic PRNG (mulberry32) so a reload reproduces the same mission. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function cartLabel(robot: RobotSim): string {
  return `Cart-${String(robot.index + 1).padStart(2, '0')}`
}

export function crateLabel(task: CargoTask): string {
  return `Crate #${task.index}`
}

export class SimulationEngine {
  public readonly robots: RobotSim[] = []
  public readonly tasks: CargoTask[] = []
  public depot: DepotMatrix = makeDepot()
  public simTime = 0
  public collisions = 0
  public collected = 0
  public completed = 0
  public totalSpawned = 0
  public energyUsed = 0
  public events: SimEvent[] = []

  /** allocator dispatching crates to carts (see SimPolicy) */
  public policy: SimPolicy = 'nearest'
  /** seed of the current run; reset(seed) pins it, the provider rolls one per run */
  public seed = 1337
  /** crates dropped on the floor for this run (MIN_ITEMS..MAX_ITEMS) */
  public itemCount = DEFAULT_ITEMS
  /** bin slots this run has to fill — the mission is done at this many stacked */
  public binCapacity = BIN_CAPACITY

  // cells currently holding a floor crate, so two crates never overlap
  private occupied: Set<string> = new Set()
  // cells a cart starts on, so no crate is dropped underneath a cart
  private robotStartCells: Set<string> = new Set()
  private rand: () => number = mulberry32(1337)
  private eventSeq = 0
  private completionTimes: number[] = []
  // stack layers needed per bay to hold this run's crates
  private layersPerSlot = MAX_LAYERS
  // parking spots for this floor, computed once the run ends
  private parkCellCache: GridPoint[] | null = null
  // sim time the bin filled; null until then
  private binFullAt: number | null = null

  constructor() {
    this.reset()
  }

  /**
   * Reset for a fresh run. Deterministic for a given (seed, itemCount): the same
   * seed always stages the same crate drop cells and the same cart starts, so a
   * run can be replayed — but a new seed gives a genuinely different floor.
   */
  reset(
    seed = 1337,
    itemCount: number = DEFAULT_ITEMS,
    policy: SimPolicy = this.policy,
  ): void {
    this.robots.length = 0
    this.tasks.length = 0
    this.depot = makeDepot()
    this.simTime = 0
    this.collisions = 0
    this.collected = 0
    this.completed = 0
    this.totalSpawned = 0
    this.energyUsed = 0
    this.events = []
    this.eventSeq = 0
    this.completionTimes = []
    this.parkCellCache = null
    this.binFullAt = null
    this.occupied.clear()
    this.robotStartCells.clear()
    this.rand = mulberry32(seed)
    this.seed = seed
    this.policy = policy
    this.itemCount = clampItemCount(itemCount)
    this.binCapacity = this.itemCount
    // 9 bays × 4 layers = 36 crates. A run that drops more than that needs
    // taller stacks so every crate has a slot to go into.
    this.layersPerSlot = Math.max(
      MAX_LAYERS,
      Math.ceil(this.binCapacity / (DEPOT_COLS * DEPOT_ROWS)),
    )

    // Carts start from seeded random cells instead of a fixed five-cell staging
    // bay, so every new run is a different dispatching floor (that is what a real
    // warehouse looks like). Start cells are kept MIN_CART_SEPARATION_M apart so a
    // run can never begin with two 1.2 m carts already touching.
    const startCells = this.randomStartCells(5)
    startCells.forEach((cell, i) => {
      const w = cellToWorld(cell)
      this.robotStartCells.add(`${cell.x},${cell.z}`)
      this.robots.push({
        id: `robot-${i}`,
        index: i,
        x: w.x,
        z: w.z,
        // face the bin so the first dispatch is never a 180° spin on the spot
        heading: Math.atan2(DEPOT_CENTER.x - w.x, DEPOT_CENTER.z - w.z),
        vx: 0,
        vz: 0,
        battery: 0.72 + this.rand() * 0.28,
        nav_state: 'idle',
        task_id: null,
        liftY: LIFT_LOW,
        forkExtension: 0,
        path: [],
        pathIndex: 0,
        speed: 1.8,
        animT: 0,
        assignedTaskId: null,
        depositStack: null,
        collisionCooldown: 0,
      })
    })

    // Stage the whole mission before the first tick: every crate the run will
    // ever have is on the floor at t = 0, so the fleet always starts from a fully
    // staged scenario and no crate appears mid-mission.
    this.spawnAllCrates()
  }

  // ── Spawning ──────────────────────────────────────────────────────────────────

  /**
   * Pick cart start cells from the run seed: candidates are shuffled with the
   * engine's own PRNG and taken greedily until `count` carts fit. Deterministic
   * for a seed, different for every new seed.
   */
  private randomStartCells(count: number): GridPoint[] {
    const candidates: GridPoint[] = []
    for (let r = 1; r < D - 1; r++) {
      for (let c = 1; c < W - 1; c++) {
        if (blocks[r][c]) continue
        // a 1.2 m cart centred on a cell that touches a rack would start clipped
        // into it, so require all four neighbours to be walkable too
        if (blocks[r - 1][c] || blocks[r + 1][c] || blocks[r][c - 1] || blocks[r][c + 1]) continue
        // keep the fleet off the bin frontage so the deposit aisle stays clear
        if (distance(cellToWorld({ x: c, z: r }), DEPOT_CENTER) < 3) continue
        candidates.push({ x: c, z: r })
      }
    }
    for (let i = candidates.length - 1; i > 0; i--) {
      const j = Math.floor(this.rand() * (i + 1))
      const tmp = candidates[i]
      candidates[i] = candidates[j]
      candidates[j] = tmp
    }

    const cells: GridPoint[] = []
    for (const cell of candidates) {
      const w = cellToWorld(cell)
      if (cells.some((p) => distance(cellToWorld(p), w) < MIN_CART_SEPARATION_M)) continue
      cells.push(cell)
      if (cells.length === count) break
    }
    return cells
  }

  private freeCells(): GridPoint[] {
    const out: GridPoint[] = []
    for (let r = 5; r < 24; r++) {
      for (let c = 4; c < 31; c++) {
        if (blocks[r][c]) continue
        const key = `${c},${r}`
        if (this.occupied.has(key)) continue
        const w = cellToWorld({ x: c, z: r })
        // keep spawns out of the cart staging area
        if (isStagingCell(c, r)) continue
        // never drop a crate on a cell a cart is starting from
        if (this.robotStartCells.has(key)) continue
        // require some travel to the bin so pickups are visible
        if (distance(w, DEPOT_CENTER) < 6) continue
        out.push({ x: c, z: r })
      }
    }
    return out
  }

  private spawnRandomCrate(): CargoTask | null {
    const cells = this.freeCells()
    if (cells.length === 0) return null
    const cell = cells[Math.floor(this.rand() * cells.length)]
    return this.spawnTask(this.simTime, cell, false)
  }

  /**
   * Drop every crate for the run in one go, called once from reset() and always
   * before the first tick. One summary event is logged instead of 36 identical
   * "waiting at pick zone" lines that would bury the action feed at t = 0.
   */
  private spawnAllCrates(): void {
    while (this.tasks.length < this.binCapacity) {
      if (!this.spawnRandomCrate()) break // floor exhausted — cannot happen on the current grid
    }
    this.pushEvent('spawn', null, null, `${this.tasks.length} crates staged on the floor`)
  }

  spawnTask(t: number, pickupCell: GridPoint, announce = true): CargoTask | null {
    if (blocks[pickupCell.z][pickupCell.x]) return null
    const key = `${pickupCell.x},${pickupCell.z}`
    if (this.occupied.has(key)) return null

    const w = cellToWorld(pickupCell)
    const task: CargoTask = {
      id: `cargo-${this.totalSpawned}`,
      index: this.totalSpawned,
      spawnT: t,
      pickup: { x: w.x, z: w.z },
      pickupCell,
      status: 'bouncing',
      assignedRobot: null,
      spawnPhase: (this.totalSpawned % 10) * 0.8,
      stack: null,
      stackTarget: null,
    }
    this.tasks.push(task)
    this.occupied.add(key)
    this.totalSpawned++
    if (announce) {
      this.pushEvent('spawn', null, task.id, `${crateLabel(task)} waiting at pick zone`)
    }
    return task
  }

  // ── Depot ─────────────────────────────────────────────────────────────────────

  /** Crates physically in the bin. A reserved slot is an in-flight crate, not a stacked one. */
  private usedCapacity(): number {
    return this.depot.slots.reduce((sum, s) => sum + s.layers, 0)
  }

  /**
   * The mission is done only when every slot physically holds a crate.
   *
   * Reservations are deliberately excluded. `reserveSlot()` books a slot at
   * auction time, so a cart holds a booking while it is still driving to the
   * pick zone and back — counting those bookings declared the mission complete
   * with crates still on the floor (31/36 stacked + 5 reserved = 36).
   */
  binFull(): boolean {
    return this.usedCapacity() >= this.binCapacity
  }

  /**
   * Reserve the next stack slot. Fills one tower to this run's layer height
   * before starting the next, which is how a real operator stacks a bay.
   */
  private reserveSlot(): { col: number; row: number; layer: number } | null {
    let best: DepotSlot | null = null
    for (const slot of this.depot.slots) {
      if (slot.layers + slot.reserved >= this.layersPerSlot) continue
      if (!best || slot.layers + slot.reserved > best.layers + best.reserved) best = slot
      if (best && best.layers + best.reserved === this.layersPerSlot - 1) break
    }
    if (!best) return null
    const layer = best.layers + best.reserved
    best.reserved += 1
    return { col: best.col, row: best.row, layer }
  }

  private releaseSlot(stack: { col: number; row: number; layer: number }): void {
    const slot = this.depot.slots.find((s) => s.col === stack.col && s.row === stack.row)
    if (slot) slot.reserved = Math.max(0, slot.reserved - 1)
  }

  // ── End-of-run parking ────────────────────────────────────────────────────────

  /**
   * Parking spots for a finished run, deterministic for a given floor.
   *
   * Every cart used to finish the mission standing on its deposit approach cell,
   * which piled all five on the same aisle row in front of the bin — the fleet
   * covered its own stacks and only the crates in the front bays read on screen.
   * These spots sit PARK_MIN..MAX metres back from the bin, fanned out either
   * side of its centre line and MIN_CART_SEPARATION_M apart, so all five carts
   * stay visible next to the full bin.
   */
  private parkCells(): GridPoint[] {
    if (this.parkCellCache) return this.parkCellCache

    const candidates: GridPoint[] = []
    for (let r = 21; r <= 24; r++) {
      for (let c = 2; c < W - 2; c++) {
        if (blocks[r][c]) continue
        // a 1.2 m cart needs its own cell and the four around it clear
        if (blocks[r - 1][c] || blocks[r + 1][c] || blocks[r][c - 1] || blocks[r][c + 1]) continue
        const key = `${c},${r}`
        if (this.occupied.has(key)) continue // never park on a crate
        const w = cellToWorld({ x: c, z: r })
        const d = distance(w, DEPOT_CENTER)
        if (d < PARK_MIN_DEPOT_M || d > PARK_MAX_DEPOT_M) continue
        candidates.push({ x: c, z: r })
      }
    }

    // Fan out from the bin's centre line, and take the deepest row first so the
    // spots read as a staggered rank rather than one shoulder-to-shoulder row.
    candidates.sort((a, b) => {
      const aw = cellToWorld(a)
      const bw = cellToWorld(b)
      const da = Math.abs(aw.x - DEPOT_CENTER.x)
      const db = Math.abs(bw.x - DEPOT_CENTER.x)
      if (Math.abs(da - db) > 1e-6) return da - db
      return bw.z - aw.z
    })

    const cells: GridPoint[] = []
    for (const cell of candidates) {
      const w = cellToWorld(cell)
      if (cells.some((p) => distance(cellToWorld(p), w) < MIN_CART_SEPARATION_M)) continue
      cells.push(cell)
      if (cells.length === PARK_SLOTS) break
    }
    this.parkCellCache = cells
    return cells
  }

  /** Parking spot for one cart; wheels off the same list when a spot is unusable. */
  private parkCellFor(index: number): GridPoint | null {
    const cells = this.parkCells()
    if (cells.length === 0) return null
    return cells[index % cells.length]
  }

  /**
   * Drive an idle cart to its parking spot once the bin is full. Before that the
   * fleet stays where it is, ready for the next crate auction.
   */
  private beginParking(robot: RobotSim): void {
    if (!this.binFull() || robot.task_id !== null) return
    const cell = this.parkCellFor(robot.index)
    if (!cell) return

    const target = cellToWorld(cell)
    robot.vx = 0
    robot.vz = 0
    robot.heading = Math.atan2(DEPOT_CENTER.x - robot.x, DEPOT_CENTER.z - robot.z)
    if (distance({ x: robot.x, z: robot.z }, target) < 0.35) {
      robot.path = []
      robot.pathIndex = 0
      robot.nav_state = 'staging'
      return
    }
    robot.path = toWorldPath(findPath(worldToCell(robot.x, robot.z), cell))
    robot.pathIndex = 0
    robot.nav_state = 'staging'
  }

  /** True when every cart has reached its parking spot and stopped. */
  cartsParked(): boolean {
    return this.robots.every((r) => r.nav_state === 'staging' && r.pathIndex >= r.path.length)
  }

  /**
   * A run is over when the bin is full *and* the fleet has parked — otherwise the
   * viewer freezes the frame while the carts are still driving, or with them all
   * heaped on the deposit aisle. A settle timeout keeps a blocked cart from
   * holding the run open forever.
   */
  runComplete(): boolean {
    if (!this.binFull()) return false
    if (this.cartsParked()) return true
    return this.binFullAt !== null && this.simTime - this.binFullAt >= PARK_SETTLE_TIMEOUT_S
  }

  // ── Auctions ──────────────────────────────────────────────────────────────────

  /** Free cell adjacent to `goal`, closest to `from`. Falls back to `goal`. */
  private approachCellFor(
    from: { x: number; z: number },
    goal: GridPoint,
  ): GridPoint {
    const candidates: GridPoint[] = [
      { x: goal.x + 1, z: goal.z },
      { x: goal.x - 1, z: goal.z },
      { x: goal.x, z: goal.z + 1 },
      { x: goal.x, z: goal.z - 1 },
    ].filter(
      (c) =>
        c.x >= 0 &&
        c.x < W &&
        c.z >= 0 &&
        c.z < D &&
        !blocks[c.z][c.x] &&
        !this.occupied.has(`${c.x},${c.z}`),
    )

    let best = goal
    let bestD = Infinity
    for (const c of candidates) {
      const d = distance(from, cellToWorld(c))
      if (d < bestD) {
        bestD = d
        best = c
      }
    }
    return best
  }

  private depotApproachCell(stack: { col: number; row: number }): GridPoint {
    const w = slotWorld(stack.col, stack.row)
    const aisleZ = cellToWorld({ x: 0, z: APPROACH_ROW }).z
    const col = Math.max(32, Math.min(35, worldToCell(w.x, aisleZ).x))
    return { x: col, z: APPROACH_ROW }
  }

  /**
   * Dispatch cost for one cart/crate pair, in metres. Each policy uses the same
   * inputs but weighs them differently, so the three runs genuinely differ.
   */
  private assignmentCost(robot: RobotSim, task: CargoTask): number {
    const d = distance({ x: robot.x, z: robot.z }, task.pickup)
    if (this.policy === 'cost_optimizer') {
      // Battery reserve matters more than a few metres saved, and carts that are
      // already bunched together cost more so the fleet spreads out.
      const batteryPenalty = (1 - robot.battery) * 20
      const neighbours = this.robots.filter(
        (other) =>
          other.id !== robot.id &&
          distance({ x: other.x, z: other.z }, { x: robot.x, z: robot.z }) < 4,
      ).length
      const congestion = neighbours / Math.max(1, this.robots.length - 1)
      return d * 0.6 + batteryPenalty + congestion * 12
    }
    // `nearest` and the per-pair cost the Hungarian assignment minimises.
    return d + 3.0 * (1 - robot.battery)
  }

  /** Contract-Net style auction: assign the cheapest idle cart to a task. */
  auctionTask(task: CargoTask): boolean {
    const candidates = this.robots.filter(
      (r) => r.nav_state === 'idle' && r.task_id === null && r.battery > 0.15,
    )
    if (candidates.length === 0) return false

    let best: RobotSim | null = null
    let bestCost = Infinity
    for (const r of candidates) {
      const cost = this.assignmentCost(r, task)
      if (cost < bestCost) {
        bestCost = cost
        best = r
      }
    }
    if (!best) return false

    return this.dispatch(best, task)
  }

  /**
   * Optimal one-to-one matching for every idle cart this round. Rows are the
   * smaller side (carts or crates), so the matrix is transposed whenever there
   * are fewer crates left than idle carts.
   */
  private dispatchBatch(): void {
    const idle = this.robots.filter(
      (r) => r.nav_state === 'idle' && r.task_id === null && r.battery > 0.15,
    )
    const pending = this.tasks.filter((t) => t.status === 'bouncing')
    if (idle.length === 0 || pending.length === 0) return

    if (idle.length <= pending.length) {
      const cost = idle.map((robot) => pending.map((task) => this.assignmentCost(robot, task)))
      for (const [robotIndex, taskIndex] of optimalPairs(cost)) {
        this.dispatch(idle[robotIndex], pending[taskIndex])
      }
      return
    }

    const cost = pending.map((task) => idle.map((robot) => this.assignmentCost(robot, task)))
    for (const [taskIndex, robotIndex] of optimalPairs(cost)) {
      this.dispatch(idle[robotIndex], pending[taskIndex])
    }
  }

  /** Book a stack slot and send `robot` to `task`'s crate. */
  private dispatch(robot: RobotSim, task: CargoTask): boolean {
    if (robot.nav_state !== 'idle' || robot.task_id !== null) return false
    if (task.status !== 'bouncing') return false

    const stack = this.reserveSlot()
    if (!stack) {
      // Every slot is either stacked or booked by a cart still en route. That is
      // not a full bin — waiting for those deliveries is what finishes the run.
      return false
    }

    const approach = this.approachCellFor(robot, task.pickupCell)
    const path = toWorldPath(findPath(worldToCell(robot.x, robot.z), approach))
    if (path.length === 0) {
      this.releaseSlot(stack)
      return false
    }

    robot.assignedTaskId = task.id
    robot.depositStack = stack
    robot.path = path
    robot.pathIndex = 0
    robot.liftY = LIFT_LOW
    robot.forkExtension = 0
    robot.animT = 0
    robot.nav_state = 'moving_to_cargo'

    task.status = 'assigned'
    task.assignedRobot = robot.id
    return true
  }

  // ── Pick / deposit logistics ──────────────────────────────────────────────────

  private startPickup(robot: RobotSim, task: CargoTask): void {
    if (distance({ x: robot.x, z: robot.z }, task.pickup) > 1.4) {
      const approach = this.approachCellFor(robot, task.pickupCell)
      robot.path = toWorldPath(findPath(worldToCell(robot.x, robot.z), approach))
      robot.pathIndex = 0
      robot.nav_state = 'moving_to_cargo'
      return
    }
    robot.nav_state = 'picking_up'
    robot.animT = 0
    robot.vx = 0
    robot.vz = 0
    // align the forks toward the crate
    robot.heading = Math.atan2(task.pickup.x - robot.x, task.pickup.z - robot.z)
  }

  completePickup(robot: RobotSim, task: CargoTask): void {
    robot.task_id = task.id
    task.status = 'in_transit'
    this.occupied.delete(`${task.pickupCell.x},${task.pickupCell.z}`)
    robot.liftY = LIFT_HIGH
    robot.forkExtension = 0.35
    this.collected++
    this.pushEvent('pickup', robot.id, task.id, `${cartLabel(robot)} attached ${crateLabel(task)}`)

    const stack = robot.depositStack
    if (!stack) {
      robot.nav_state = 'idle'
      return
    }
    const goal = this.depotApproachCell(stack)
    robot.path = toWorldPath(findPath(worldToCell(robot.x, robot.z), goal))
    robot.pathIndex = 0
    robot.nav_state = 'moving_to_depot'
  }

  startDeposit(robot: RobotSim, stack: { col: number; row: number; layer: number }): void {
    robot.nav_state = 'depositing_stack'
    robot.animT = 0
    robot.vx = 0
    robot.vz = 0
    const w = slotWorld(stack.col, stack.row)
    robot.heading = Math.atan2(w.x - robot.x, w.z - robot.z)
  }

  completeDeposit(robot: RobotSim, task: CargoTask): void {
    const stack = robot.depositStack
    if (!stack) return

    const slot = this.depot.slots.find((s) => s.col === stack.col && s.row === stack.row)
    if (slot) {
      slot.reserved = Math.max(0, slot.reserved - 1)
      slot.layers = Math.min(this.layersPerSlot, slot.layers + 1)
    }

    const w = slotWorld(stack.col, stack.row)
    task.status = 'delivered'
    task.stack = stack
    task.stackTarget = { x: w.x, y: layerY(stack.layer), z: w.z }
    task.assignedRobot = null

    robot.task_id = null
    robot.assignedTaskId = null
    robot.depositStack = null
    robot.liftY = LIFT_LOW
    robot.forkExtension = 0
    robot.animT = 0
    robot.nav_state = 'idle'

    this.completed++
    this.completionTimes.push(this.simTime)
    this.pushEvent(
      'stack',
      robot.id,
      task.id,
      `${cartLabel(robot)} stacked ${crateLabel(task)} into Bay ${bayLabel(stack.col, stack.row)}`,
    )
    emitTeamReward(this, robot, task.id)

    // Announce completion only now, when the last crate is physically stacked.
    if (this.binFull()) {
      this.pushEvent(
        'full',
        null,
        null,
        `Storage bin full — ${this.binCapacity}/${this.binCapacity} crates`,
      )
    }
  }

  // ── Tick ─────────────────────────────────────────────────────────────────────

  tick(dt: number): void {
    this.simTime += dt
    this.director()
    if (this.binFullAt === null && this.binFull()) this.binFullAt = this.simTime

    for (const robot of this.robots) {
      robot.collisionCooldown = Math.max(0, robot.collisionCooldown - dt)
      this.tickRobot(robot, dt)
    }

    this.detectCollisions()
    this.pruneCompletionTimes()
  }

  private director(): void {
    // Every crate is already staged by reset(), so the director only dispatches
    // work — there is no spawn timer and no crate can appear during the run.
    if (this.policy === 'hungarian') {
      this.dispatchBatch()
      return
    }
    // one auction per tick is plenty at 60 Hz
    for (const task of this.tasks) {
      if (task.status !== 'bouncing') continue
      if (this.auctionTask(task)) break
    }
  }

  private tickRobot(robot: RobotSim, dt: number): void {
    // battery
    if (robot.nav_state === 'charging') {
      robot.battery = Math.min(1, robot.battery + dt * 0.08)
    } else if (robot.vx !== 0 || robot.vz !== 0) {
      const drain = Math.min(robot.battery, dt * 0.0015)
      robot.battery -= drain
      this.energyUsed += drain
    } else {
      const drain = Math.min(robot.battery, dt * 0.0004)
      robot.battery -= drain
      this.energyUsed += drain
    }

    switch (robot.nav_state) {
      case 'idle':
        if (robot.battery < 0.15) this.sendToCharger(robot)
        else this.beginParking(robot)
        break
      case 'staging':
        if (robot.pathIndex < robot.path.length) this._moveTick(robot, dt)
        break
      case 'charging':
        this.chargeTick(robot)
        break
      case 'moving_to_cargo':
      case 'moving_to_depot':
        this._moveTick(robot, dt)
        break
      case 'picking_up':
        this.pickupTick(robot, dt)
        break
      case 'depositing_stack':
        this.depositTick(robot, dt)
        break
    }
  }

  private sendToCharger(robot: RobotSim): void {
    const pad = cellToWorld({ x: 5 + (robot.index % 2), z: 3 + (robot.index % 2) })
    robot.path = toWorldPath(findPath(worldToCell(robot.x, robot.z), worldToCell(pad.x, pad.z)))
    robot.pathIndex = 0
    robot.nav_state = 'charging'
    robot.vx = 0
    robot.vz = 0
    this.pushEvent('charge', robot.id, null, `${cartLabel(robot)} routing to charging pad`)
  }

  private chargeTick(robot: RobotSim): void {
    if (robot.pathIndex < robot.path.length) {
      this._moveTick(robot, 0.016)
      return
    }
    if (robot.battery >= 0.92) robot.nav_state = 'idle'
  }

  private _moveTick(robot: RobotSim, dt: number): void {
    const path = robot.path
    if (!path.length || robot.pathIndex >= path.length) return

    const target = path[robot.pathIndex]
    const dx = target.x - robot.x
    const dz = target.z - robot.z
    const dist = Math.sqrt(dx * dx + dz * dz)

    if (dist < 0.12) {
      robot.x = target.x
      robot.z = target.z
      robot.vx = 0
      robot.vz = 0
      robot.pathIndex++
      if (robot.pathIndex >= path.length) {
        if (robot.nav_state === 'moving_to_cargo') {
          const task = this.taskForRobot(robot)
          if (task) this.startPickup(robot, task)
        } else if (robot.nav_state === 'moving_to_depot') {
          const stack = robot.depositStack
          if (stack) this.startDeposit(robot, stack)
        }
      }
      return
    }

    const step = Math.min(robot.speed * dt, dist)
    robot.x += (dx / dist) * step
    robot.z += (dz / dist) * step
    robot.vx = (dx / dist) * robot.speed
    robot.vz = (dz / dist) * robot.speed
    // Local +Z is the fork direction; map it onto the travel vector.
    robot.heading = Math.atan2(dx, dz)
  }

  private pickupTick(robot: RobotSim, dt: number): void {
    robot.animT = Math.min(1, robot.animT + dt * 1.4) // ~0.7 s

    // forks slide under the crate, then the carriage lifts it clear of the floor
    if (robot.animT < 0.45) {
      robot.forkExtension = robot.animT / 0.45
      robot.liftY = LIFT_LOW
    } else {
      robot.forkExtension = 1
      const k = (robot.animT - 0.45) / 0.55
      robot.liftY = LIFT_LOW + (LIFT_HIGH - LIFT_LOW) * k
    }

    if (robot.animT >= 1) {
      const task = this.taskForRobot(robot)
      if (task) this.completePickup(robot, task)
      else robot.nav_state = 'idle'
    }
  }

  private depositTick(robot: RobotSim, dt: number): void {
    robot.animT = Math.min(1, robot.animT + dt / 1.6)
    const stack = robot.depositStack
    // tine height that puts the carried crate centre just above its slot
    const targetY = stack
      ? layerY(stack.layer) + 0.12 - CARRIED_CRATE_OFFSET
      : LIFT_LOW

    if (robot.animT < 0.35) {
      // extend forks over the bin
      robot.forkExtension = 0.35 + (robot.animT / 0.35) * 0.65
    } else if (robot.animT < 0.8) {
      // lower the crate onto its layer
      robot.forkExtension = 1
      const k = (robot.animT - 0.35) / 0.45
      robot.liftY = LIFT_HIGH + (targetY - LIFT_HIGH) * k
    } else {
      // release and retract
      robot.forkExtension = 1 - (robot.animT - 0.8) / 0.2
      robot.liftY = targetY
    }

    if (robot.animT >= 1) {
      const task = this.taskForRobot(robot)
      if (task) this.completeDeposit(robot, task)
      else robot.nav_state = 'idle'
    }
  }

  private taskForRobot(robot: RobotSim): CargoTask | null {
    if (!robot.assignedTaskId) return null
    return this.tasks.find((t) => t.id === robot.assignedTaskId) ?? null
  }

  // ── Collision avoidance ───────────────────────────────────────────────────────

  private detectCollisions(): void {
    // 1.2 m wide carts: a 1.4 m threshold keeps carts from overlapping while
    // tolerating the tight staging-area cluster that happens when all 5 carts
    // idle around the charging pad. The previous 1.1 m threshold triggered
    // constant proximity stops there and inflated the collision counter.
    const THRESHOLD = 1.4
    for (let i = 0; i < this.robots.length; i++) {
      for (let j = i + 1; j < this.robots.length; j++) {
        const a = this.robots[i]
        const b = this.robots[j]
        const d = distance({ x: a.x, z: a.z }, { x: b.x, z: b.z })
        if (d < THRESHOLD) this.pauseRobot(b, a)
      }
    }
  }

  private pauseRobot(robot: RobotSim, other: RobotSim): void {
    if (robot.collisionCooldown > 0) return
    const dx = other.x - robot.x
    const dz = other.z - robot.z
    const d = Math.sqrt(dx * dx + dz * dz)
    if (d < 0.001) return
    const vdot = (robot.vx * dx + robot.vz * dz) / d
    if (vdot > 0.6) {
      robot.vx = 0
      robot.vz = 0
      robot.collisionCooldown = 1
      this.collisions++
      this.pushEvent('collision', robot.id, null, `${cartLabel(robot)} proximity stop near ${cartLabel(other)}`)
    }
  }

  // ── Event log ────────────────────────────────────────────────────────────────

  private pushEvent(
    kind: SimEventKind,
    robotId: string | null,
    taskId: string | null,
    message: string,
  ): void {
    this.events.push({
      id: this.eventSeq++,
      t: this.simTime,
      kind,
      robotId,
      taskId,
      message,
    })
    if (this.events.length > EVENT_LOG_LIMIT) {
      this.events.splice(0, this.events.length - EVENT_LOG_LIMIT)
    }
  }

  private pruneCompletionTimes(): void {
    const cutoff = this.simTime - THROUGHPUT_WINDOW_S
    while (this.completionTimes.length && this.completionTimes[0] < cutoff) {
      this.completionTimes.shift()
    }
  }

  throughputPerMin(): number {
    const window = Math.min(THROUGHPUT_WINDOW_S, Math.max(this.simTime, 1))
    return (this.completionTimes.length / window) * 60
  }

  /**
   * Handler for the reward-policy preview the HUD shows when a cart completes a
   * task. This is informational only — no USDC moves, no Arc tx, no wallet spend.
   * Set to null to detach the preview (the HUD re-wires it on mount).
   */
  _onTeamReward: TeamRewardCallback | null = null

  /**
   * When a cart reaches its delivery point and drops a crate into the storage
   * bin, it emits a TEAM_REWARD event so the dashboard can show a preview of
   * what a reward-policy payout would look like. This is not a payment,
   * settlement, or on-chain action — the wallet and transaction history are
   * unaffected.
   */
  snapshot(): EngineSnapshot {
    return {
      robots: [...this.robots],
      tasks: [...this.tasks],
      depot: { slots: this.depot.slots.map((s) => ({ ...s })) },
      simTime: this.simTime,
      collisions: this.collisions,
      collected: this.collected,
      stacked: this.completed,
      energyUsed: this.energyUsed,
      totalSpawned: this.totalSpawned,
      throughputPerMin: this.throughputPerMin(),
      events: [...this.events],
      seed: this.seed,
      itemCount: this.itemCount,
      binCapacity: this.binCapacity,
      binFull: this.binFull(),
      policy: this.policy,
    }
  }
}

// ─── Reward preview (informational only — no real payment fires) ─────────────────

/**
 * When a cart reaches its delivery point and drops a crate into the storage bin,
 * the engine emits a TEAM_REWARD event so the HUD can show a preview of what a
 * reward-policy payout would look like. This is not a payment, settlement, or
 * on-chain action — the wallet and transaction history are unaffected.
 */
export const TEAM_REWARD_USD_PER_CRATE = 1.25

export type TeamRewardEvent = {
  type: 'TEAM_REWARD'
  cart_id: string
  task_id: string
  reward_usdc: number
  reward_crates: number
  timestamp: number
}

type TeamRewardCallback = (event: TeamRewardEvent) => void

/**
 * Attach or detach the reward-policy preview callback on a simulation engine.
 * This is informational only — no USDC moves, no Arc tx, no wallet spend.
 */
export function setTeamRewardHandler(
  engine: SimulationEngine,
  cb: TeamRewardCallback | null,
): void {
  engine._onTeamReward = cb
}

/**
 * When a cart reaches its delivery point and drops a crate into the storage bin,
 * emit a TEAM_REWARD event through the engine's attached callback so the HUD can
 * show a preview of what a reward-policy payout would look like. This is not a
 * payment, settlement, or on-chain action — the wallet and transaction history
 * are unaffected.
 */
export function emitTeamReward(
  engine: SimulationEngine,
  cart: RobotSim,
  taskId: string,
): void {
  if (engine._onTeamReward) {
    engine._onTeamReward({
      type: 'TEAM_REWARD',
      cart_id: cart.id,
      task_id: taskId,
      reward_usdc: TEAM_REWARD_USD_PER_CRATE,
      reward_crates: 1,
      timestamp: performance.now(),
    })
  }
}
