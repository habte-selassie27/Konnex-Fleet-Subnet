// WarehouseRobot — a single robot mesh on the 3D map. Position/heading come
// from the live WebSocket state; color encodes nav_state (with the sidebar
// RobotCard providing the always-present color+icon+text pairing).
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Mesh } from 'three'
import type { RobotState } from '../../types'

const STATE_COLORS: Record<string, string> = {
  idle: '#94a3b8', // slate-400
  moving: '#0ea5e9', // sky-500
  blocked: '#f97316', // orange-500
  charging: '#f59e0b', // amber-500
  failed: '#ef4444', // red-500
}

interface WarehouseRobotProps {
  robot: RobotState
}

export function WarehouseRobot({ robot }: WarehouseRobotProps) {
  const meshRef = useRef<Mesh>(null)

  // Smooth interpolation: nudge the mesh toward the latest WS position each
  // frame (positions arrive at ~10 Hz; rendering runs at 60 fps).
  useFrame(() => {
    const mesh = meshRef.current
    if (!mesh) return
    const targetX = robot.position.x - 20 // world origin at map center
    const targetZ = robot.position.y - 15
    mesh.position.x += (targetX - mesh.position.x) * 0.15
    mesh.position.z += (targetZ - mesh.position.z) * 0.15
    const targetRot = -robot.orientation
    mesh.rotation.y += (targetRot - mesh.rotation.y) * 0.15
  })

  const color = STATE_COLORS[robot.nav_state] ?? STATE_COLORS.idle

  return (
    <group>
      <mesh
        ref={meshRef}
        position={[robot.position.x - 20, 0.2, robot.position.y - 15]}
        rotation={[0, -robot.orientation, 0]}
      >
        <boxGeometry args={[0.5, 0.4, 0.5]} />
        <meshStandardMaterial color={color} />
      </mesh>
      {/* Heading indicator */}
      <mesh position={[robot.position.x - 20, 0.45, robot.position.y - 15]} rotation={[0, -robot.orientation, 0]}>
        <coneGeometry args={[0.12, 0.2, 8]} />
        <meshStandardMaterial color="#f8fafc" />
      </mesh>
    </group>
  )
}
