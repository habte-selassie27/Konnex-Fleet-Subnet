// CargoCrate — the collectible industrial crate, drawn in three placements:
//
//   floor    → resting on the warehouse floor with a pulsing target ring
//   carried  → parented to a cart's gripperAnchor, riding the forks
//   stacked  → locked into an exact (col, row, layer) bay slot in the bin
//
// Body is dark steel with neon corner brackets, per the scene brief. Geometry is
// a single 0.5 m composite; the engine supplies every position so visuals and
// mission state cannot drift.
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

import type { CargoTask } from '../../simulation/engine'
import { CARRIED_CRATE_OFFSET, CRATE_SIZE } from '../../simulation/engine'
import type { ScenePalette } from './scenePalette'

/** Resting height of a crate centre on the floor. */
export const FLOOR_CRATE_Y = CRATE_SIZE / 2 + 0.02

interface CargoCrateProps {
  task: CargoTask
  palette: ScenePalette
  mode: 'floor' | 'carried' | 'stacked'
}

export function CargoCrate(props: CargoCrateProps) {
  if (props.mode === 'carried') {
    return (
      <group position={[0, CARRIED_CRATE_OFFSET, 0]}>
        <CrateBody palette={props.palette} />
      </group>
    )
  }
  if (props.mode === 'stacked') return <StackedCrate {...props} />
  return <FloorCrate {...props} />
}

// ─── placements ────────────────────────────────────────────────────────────────

function FloorCrate({ task, palette }: CargoCrateProps) {
  const bobRef = useRef<THREE.Group>(null)
  const ringRef = useRef<THREE.Mesh>(null)
  const markerRef = useRef<THREE.Mesh>(null)
  const t0 = useRef(performance.now())

  useFrame(() => {
    const t = (performance.now() - t0.current) / 1000
    const phase = task.spawnPhase

    if (bobRef.current) {
      bobRef.current.position.y = FLOOR_CRATE_Y + Math.sin(t * 1.7 + phase) * 0.018
      bobRef.current.rotation.y = Math.sin(t * 0.4 + phase) * 0.05
    }
    if (ringRef.current) {
      const pulse = 1 + Math.sin(t * 2.2 + phase) * 0.08
      ringRef.current.scale.setScalar(pulse)
    }
    if (markerRef.current) {
      markerRef.current.rotation.y = t * 0.9
      markerRef.current.position.y = 0.88 + Math.sin(t * 1.9 + phase) * 0.05
    }
  })

  return (
    <group position={[task.pickup.x, 0, task.pickup.z]}>
      <group ref={bobRef} position={[0, FLOOR_CRATE_Y, 0]}>
        <CrateBody palette={palette} />
      </group>

      {/* floor target ring — marks an uncollected crate */}
      <mesh ref={ringRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
        <ringGeometry args={[0.4, 0.48, 36]} />
        <meshBasicMaterial
          color={palette.crateAccent}
          transparent
          opacity={0.5}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* floating target pip so crates read from a distance */}
      <mesh ref={markerRef} position={[0, 0.88, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.15, 0.012, 8, 28]} />
        <meshBasicMaterial color={palette.crateAccent} transparent opacity={0.85} />
      </mesh>
    </group>
  )
}

function StackedCrate({ task, palette }: CargoCrateProps) {
  const groupRef = useRef<THREE.Group>(null)
  const target = task.stackTarget
  // settle from slightly above the slot so the placement reads as a drop
  const settle = useRef(1)

  useFrame((_, delta) => {
    if (!groupRef.current) return
    settle.current = Math.max(0, settle.current - delta * 3.2)
    groupRef.current.position.y = (target?.y ?? 0) + settle.current * 0.22
  })

  if (!target) return null

  return (
    <group ref={groupRef} position={[target.x, target.y, target.z]}>
      <CrateBody palette={palette} />
    </group>
  )
}

// ─── shared geometry ───────────────────────────────────────────────────────────

function CrateBody({ palette }: { palette: ScenePalette }) {
  const half = CRATE_SIZE / 2
  const edge = 0.038

  return (
    <group>
      {/* steel body */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[CRATE_SIZE, CRATE_SIZE, CRATE_SIZE]} />
        <meshStandardMaterial color={palette.crateBody} metalness={0.85} roughness={0.28} />
      </mesh>

      {/* recessed side panels */}
      <mesh position={[0, 0, half + 0.001]}>
        <boxGeometry args={[CRATE_SIZE - 0.16, CRATE_SIZE - 0.16, 0.01]} />
        <meshStandardMaterial color={palette.crateEdge} metalness={0.6} roughness={0.5} />
      </mesh>
      <mesh position={[0, 0, -half - 0.001]}>
        <boxGeometry args={[CRATE_SIZE - 0.16, CRATE_SIZE - 0.16, 0.01]} />
        <meshStandardMaterial color={palette.crateEdge} metalness={0.6} roughness={0.5} />
      </mesh>

      {/* neon corner brackets — 4 vertical edges */}
      {[
        [-half, -half],
        [half, -half],
        [-half, half],
        [half, half],
      ].map(([x, z], i) => (
        <mesh key={`corner-${i}`} position={[x, 0, z]}>
          <boxGeometry args={[edge, CRATE_SIZE + 0.004, edge]} />
          <meshStandardMaterial
            color={palette.crateAccent}
            emissive={palette.crateAccent}
            emissiveIntensity={1.1}
            metalness={0.2}
            roughness={0.35}
          />
        </mesh>
      ))}

      {/* top rim */}
      <mesh position={[0, half, half]}>
        <boxGeometry args={[CRATE_SIZE, edge, edge]} />
        <meshStandardMaterial
          color={palette.crateAccent}
          emissive={palette.crateAccent}
          emissiveIntensity={0.7}
          metalness={0.3}
          roughness={0.4}
        />
      </mesh>
      <mesh position={[0, half, -half]}>
        <boxGeometry args={[CRATE_SIZE, edge, edge]} />
        <meshStandardMaterial
          color={palette.crateAccent}
          emissive={palette.crateAccent}
          emissiveIntensity={0.7}
          metalness={0.3}
          roughness={0.4}
        />
      </mesh>
      <mesh position={[half, half, 0]}>
        <boxGeometry args={[edge, edge, CRATE_SIZE]} />
        <meshStandardMaterial
          color={palette.crateAccent}
          emissive={palette.crateAccent}
          emissiveIntensity={0.7}
          metalness={0.3}
          roughness={0.4}
        />
      </mesh>
      <mesh position={[-half, half, 0]}>
        <boxGeometry args={[edge, edge, CRATE_SIZE]} />
        <meshStandardMaterial
          color={palette.crateAccent}
          emissive={palette.crateAccent}
          emissiveIntensity={0.7}
          metalness={0.3}
          roughness={0.4}
        />
      </mesh>
    </group>
  )
}
