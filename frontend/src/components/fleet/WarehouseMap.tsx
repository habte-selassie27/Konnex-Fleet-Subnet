// WarehouseMap — Three.js 3D warehouse (AGENTS.md §1.4). Renders live robot
// positions from the Zustand store; shows OfflineIndicator when offline.
// Never renders mock robots (AGENTS.md §1.6).
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { useFleetState } from '../../hooks/useFleetState'
import { useFleetStore } from '../../store/fleetStore'
import { OfflineIndicator } from '../shared/OfflineIndicator'
import { WarehouseRobot } from './WarehouseRobot'

const WORLD_WIDTH = 40 // meters
const WORLD_DEPTH = 30 // meters

export function WarehouseMap() {
  const { robots, isOnline } = useFleetState()
  const mission = useFleetStore((s) => s.mission)

  if (!isOnline) {
    return <OfflineIndicator message="Simulator offline — no live data" />
  }

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-slate-700 bg-slate-950">
      <Canvas camera={{ position: [0, 22, 24], fov: 50 }} dpr={[1, 2]}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 20, 10]} intensity={0.8} />

        {/* Warehouse floor */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
          <planeGeometry args={[WORLD_WIDTH, WORLD_DEPTH]} />
          <meshStandardMaterial color="#0f172a" />
        </mesh>

        {/* Floor grid */}
        <gridHelper
          args={[WORLD_WIDTH, WORLD_WIDTH, 0x1e293b, 0x334155]}
          position={[0, 0.01, 0]}
        />

        {/* Walls */}
        <Wall x={0} z={-WORLD_DEPTH / 2} width={WORLD_WIDTH} height={3} />
        <Wall x={0} z={WORLD_DEPTH / 2} width={WORLD_WIDTH} height={3} />
        <Wall x={-WORLD_WIDTH / 2} z={0} width={WORLD_DEPTH} height={3} />
        <Wall x={WORLD_WIDTH / 2} z={0} width={WORLD_DEPTH} height={3} />

        {/* Live robots — positions from WebSocket */}
        {robots.map((robot) => (
          <WarehouseRobot key={robot.id} robot={robot} />
        ))}

        <OrbitControls
          enablePan
          enableZoom
          enableRotate
          maxPolarAngle={Math.PI / 2.15}
          minDistance={6}
          maxDistance={60}
        />
      </Canvas>

      {/* HUD overlay */}
      <div className="pointer-events-none absolute left-3 top-3 flex gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-900/80 px-3 py-1 text-xs font-medium text-emerald-400 ring-1 ring-slate-700">
          <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" aria-hidden="true" />
          LIVE
        </span>
        {mission ? (
          <span className="inline-flex items-center rounded-full bg-slate-900/80 px-3 py-1 text-xs font-medium text-slate-300 ring-1 ring-slate-700">
            Mission {mission.mission_id.slice(0, 8)} · {mission.completed_tasks}/{mission.total_tasks} tasks
          </span>
        ) : null}
      </div>
    </div>
  )
}

function Wall({ x, z, width, height }: { x: number; z: number; width: number; height: number }) {
  return (
    <mesh position={[x, height / 2, z]}>
      <boxGeometry args={[width, height, 0.25]} />
      <meshStandardMaterial color="#1e293b" />
    </mesh>
  )
}
