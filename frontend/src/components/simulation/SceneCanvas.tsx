// SceneCanvas — the WebGL warehouse for the Fleet Intelligence viewport.
//
// Renders the local simulation (mode = 'sim') as a physical industrial floor:
// procedural shelf racks, the storage bin, 5 AMR carts and every crate. In 'live'
// mode the WebSocket renderer stays authoritative — this canvas is not mixed in
// behind a fake LIVE badge (AGENTS.md §1.6 / §0.3).
//
// The scene palette flips with the dashboard theme, so dark/light mode is a
// single class on <html> away.
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'

import {
  SHELF_DEFS,
  WORLD_D,
  WORLD_W,
  type CargoTask,
} from '../../simulation/engine'
import { useSimulationProvider, useSimulationSnapshot } from '../../simulation/useSimulation'
import { useUiStore } from '../../store/uiStore'
import { SCENE_PALETTES, type ScenePalette } from './scenePalette'
import { AMRCart } from './AMRCart'
import { CargoCrate } from './CargoCrate'
import { StorageBin } from './StorageBin'

const CAMERA_TARGET: [number, number, number] = [0, 0, -2]

export function SceneCanvas() {
  const initialized = useSimulationProvider((s) => s.initialized)
  const mode = useSimulationProvider((s) => s.mode)
  const theme = useUiStore((s) => s.theme)
  const palette = SCENE_PALETTES[theme]

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-line bg-surface transition-colors duration-200">
      {!initialized ? (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="rounded-full bg-panel px-3 py-1 text-xs font-medium text-muted ring-1 ring-line">
            Initializing simulation
          </span>
        </div>
      ) : mode === 'live' ? (
        <LiveModeFallback />
      ) : (
        <R3fScene palette={palette} />
      )}
    </div>
  )
}

function R3fScene({ palette }: { palette: ScenePalette }) {
  const { snapshot } = useSimulationSnapshot()
  const robots = snapshot?.robots ?? []
  const tasks = snapshot?.tasks ?? []
  const depot = snapshot?.depot

  // Which crate is physically attached to which cart right now. A crate becomes
  // a child of the cart the moment the forks engage, and is reparented into the
  // bin the moment the stack completes.
  const carriedByRobot = new Map<string, CargoTask>()
  const carriedIds = new Set<string>()
  for (const robot of robots) {
    const task = robot.assignedTaskId
      ? tasks.find((t) => t.id === robot.assignedTaskId)
      : undefined
    if (!task) continue
    const attached =
      robot.nav_state === 'moving_to_depot' ||
      robot.nav_state === 'depositing_stack' ||
      (robot.nav_state === 'picking_up' && robot.animT > 0.4)
    if (attached) {
      carriedByRobot.set(robot.id, task)
      carriedIds.add(task.id)
    }
  }

  const floorCrates = tasks.filter(
    (t) => (t.status === 'bouncing' || t.status === 'assigned') && !carriedIds.has(t.id),
  )
  const stackedCrates = tasks.filter((t) => t.status === 'delivered' && t.stackTarget)

  const occupancy = new Map<string, number>()
  for (const slot of depot?.slots ?? []) {
    occupancy.set(`${slot.col}-${slot.row}`, slot.layers)
  }

  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: [20, 15, 12], fov: 48, near: 0.5, far: 200 }}
      gl={{ antialias: true, powerPreference: 'high-performance' }}
    >
      <color attach="background" args={[palette.background]} />
      <fog attach="fog" args={[palette.fogColor, palette.fogNear, palette.fogFar]} />

      <ambientLight color={palette.ambientColor} intensity={palette.ambientIntensity} />
      <hemisphereLight
        color={palette.rimColor}
        groundColor={palette.floor}
        intensity={0.7}
      />
      <directionalLight
        position={[10, 20, 15]}
        color={palette.keyColor}
        intensity={palette.keyIntensity}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={1}
        shadow-camera-far={80}
        shadow-camera-left={-28}
        shadow-camera-right={28}
        shadow-camera-top={24}
        shadow-camera-bottom={-24}
        shadow-bias={-0.0004}
      />
      <directionalLight
        position={[-14, 12, -18]}
        color={palette.rimColor}
        intensity={palette.rimIntensity}
      />

      <WarehouseFloor palette={palette} />
      <Walls palette={palette} />

      {SHELF_DEFS.map((shelf, i) => (
        <ShelfRack
          key={`shelf-${i}`}
          palette={palette}
          x={shelf.x + shelf.w / 2 - WORLD_W / 2}
          z={-(shelf.z + shelf.d / 2) + WORLD_D / 2}
          width={shelf.w}
          depth={shelf.d}
        />
      ))}

      <StorageBin palette={palette} occupancy={occupancy} />

      {stackedCrates.map((task) => (
        <CargoCrate key={task.id} task={task} palette={palette} mode="stacked" />
      ))}

      {floorCrates.map((task) => (
        <CargoCrate key={task.id} task={task} palette={palette} mode="floor" />
      ))}

      {robots.map((robot) => (
        <AMRCart
          key={robot.id}
          robot={robot}
          palette={palette}
          carrying={carriedByRobot.get(robot.id) ?? null}
        />
      ))}

      <OrbitControls
        enablePan
        enableZoom
        enableRotate
        maxPolarAngle={Math.PI / 2.15}
        minDistance={8}
        maxDistance={70}
        target={CAMERA_TARGET}
      />
    </Canvas>
  )
}

function WarehouseFloor({ palette }: { palette: ScenePalette }) {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[WORLD_W, WORLD_D]} />
        <meshStandardMaterial color={palette.floor} metalness={0.15} roughness={0.9} />
      </mesh>

      {/* 1 m grid */}
      <gridHelper
        args={[WORLD_W, WORLD_W, palette.gridFine, palette.gridFine]}
        position={[0, 0.006, 0]}
        scale={[1, 1, WORLD_D / WORLD_W]}
        material-transparent
        material-opacity={palette.gridFineOpacity}
      />
      {/* 5 m section grid */}
      <gridHelper
        args={[WORLD_W, WORLD_W / 5, palette.gridSection, palette.gridSection]}
        position={[0, 0.012, 0]}
        scale={[1, 1, WORLD_D / WORLD_W]}
        material-transparent
        material-opacity={palette.gridSectionOpacity}
      />
    </group>
  )
}

function Walls({ palette }: { palette: ScenePalette }) {
  const wallDefs: Array<{ pos: [number, number, number]; size: [number, number, number] }> = [
    { pos: [0, 1.5, -WORLD_D / 2], size: [WORLD_W, 3, 0.25] },
    { pos: [0, 1.5, WORLD_D / 2], size: [WORLD_W, 3, 0.25] },
    { pos: [-WORLD_W / 2, 1.5, 0], size: [0.25, 3, WORLD_D] },
    { pos: [WORLD_W / 2, 1.5, 0], size: [0.25, 3, WORLD_D] },
  ]
  return (
    <group>
      {wallDefs.map((wall, i) => (
        <mesh key={`wall-${i}`} position={wall.pos} receiveShadow castShadow>
          <boxGeometry args={wall.size} />
          <meshStandardMaterial color={palette.wall} metalness={0.35} roughness={0.6} />
        </mesh>
      ))}
    </group>
  )
}

interface ShelfRackProps {
  palette: ScenePalette
  x: number
  z: number
  width: number
  depth: number
}

/** Industrial pallet rack: 4 uprights + 3 loaded shelf levels + an LED strip. */
function ShelfRack({ palette, x, z, width, depth }: ShelfRackProps) {
  const upright = 0.09
  const height = 2.1
  const levels = [0.55, 1.25, 1.95]

  return (
    <group position={[x, 0, z]}>
      {[
        [-width / 2 + upright / 2, -depth / 2 + upright / 2],
        [width / 2 - upright / 2, -depth / 2 + upright / 2],
        [-width / 2 + upright / 2, depth / 2 - upright / 2],
        [width / 2 - upright / 2, depth / 2 - upright / 2],
      ].map(([px, pz], i) => (
        <mesh key={`upright-${i}`} castShadow position={[px, height / 2, pz]}>
          <boxGeometry args={[upright, height, upright]} />
          <meshStandardMaterial color={palette.shelfEdge} metalness={0.85} roughness={0.35} />
        </mesh>
      ))}

      {levels.map((y, i) => (
        <mesh key={`level-${i}`} castShadow receiveShadow position={[0, y, 0]}>
          <boxGeometry args={[width - 0.04, 0.07, depth - 0.06]} />
          <meshStandardMaterial color={palette.shelfBody} metalness={0.7} roughness={0.45} />
        </mesh>
      ))}

      {/* LED strip along the aisle-facing edge */}
      <mesh position={[0, levels[levels.length - 1] + 0.06, depth / 2 - 0.02]}>
        <boxGeometry args={[width - 0.2, 0.025, 0.02]} />
        <meshStandardMaterial
          color={palette.shelfLed}
          emissive={palette.shelfLed}
          emissiveIntensity={0.55}
        />
      </mesh>
    </group>
  )
}

function LiveModeFallback() {
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      <span className="rounded-full bg-panel px-3 py-1 text-xs font-medium text-muted ring-1 ring-line">
        Live mode active — WebSocket renderer
      </span>
    </div>
  )
}
