// StorageBin — the physical drop-off container.
//
// Open-top industrial bin: 4 side walls + a floor plate, dark slate metal with a
// glowing emerald rim. Interior is sized for a 3×3 grid of 0.5 m crates stacked
// 4 layers high (see engine constants), and the floor carries a marker per bay
// so the stacking grid is legible from the default camera.
import * as THREE from 'three'

import {
  BIN_D,
  BIN_W,
  BIN_WALL_H,
  DEPOT_COLS,
  DEPOT_CENTER,
  DEPOT_ROWS,
  BIN_FLOOR_Y,
  SLOT_PITCH,
} from '../../simulation/engine'
import type { ScenePalette } from './scenePalette'

const WALL_T = 0.07
const BASE_H = BIN_FLOOR_Y

interface StorageBinProps {
  palette: ScenePalette
  /** number of crates placed per bay, for highlighting occupied slots */
  occupancy: Map<string, number>
}

export function StorageBin({ palette, occupancy }: StorageBinProps) {
  const innerW = BIN_W - WALL_T * 2
  const innerD = BIN_D - WALL_T * 2
  const wallY = BASE_H + BIN_WALL_H / 2
  const rimY = BASE_H + BIN_WALL_H

  return (
    <group position={[DEPOT_CENTER.x, 0, DEPOT_CENTER.z]}>
      {/* base / floor plate */}
      <mesh receiveShadow castShadow position={[0, BASE_H / 2, 0]}>
        <boxGeometry args={[BIN_W + 0.12, BASE_H, BIN_D + 0.12]} />
        <meshStandardMaterial color={palette.binBody} metalness={0.75} roughness={0.35} />
      </mesh>

      {/* interior floor */}
      <mesh receiveShadow position={[0, BASE_H + 0.005, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[innerW, innerD]} />
        <meshStandardMaterial color={palette.binInterior} metalness={0.5} roughness={0.7} />
      </mesh>

      {/* four walls */}
      <mesh castShadow receiveShadow position={[0, wallY, BIN_D / 2 - WALL_T / 2]}>
        <boxGeometry args={[BIN_W, BIN_WALL_H, WALL_T]} />
        <meshStandardMaterial color={palette.binBody} metalness={0.8} roughness={0.32} />
      </mesh>
      <mesh castShadow receiveShadow position={[0, wallY, -BIN_D / 2 + WALL_T / 2]}>
        <boxGeometry args={[BIN_W, BIN_WALL_H, WALL_T]} />
        <meshStandardMaterial color={palette.binBody} metalness={0.8} roughness={0.32} />
      </mesh>
      <mesh castShadow receiveShadow position={[BIN_W / 2 - WALL_T / 2, wallY, 0]}>
        <boxGeometry args={[WALL_T, BIN_WALL_H, BIN_D - WALL_T * 2]} />
        <meshStandardMaterial color={palette.binBody} metalness={0.8} roughness={0.32} />
      </mesh>
      <mesh castShadow receiveShadow position={[-BIN_W / 2 + WALL_T / 2, wallY, 0]}>
        <boxGeometry args={[WALL_T, BIN_WALL_H, BIN_D - WALL_T * 2]} />
        <meshStandardMaterial color={palette.binBody} metalness={0.8} roughness={0.32} />
      </mesh>

      {/* glowing emerald rim */}
      <mesh position={[0, rimY, BIN_D / 2 - WALL_T / 2]}>
        <boxGeometry args={[BIN_W, 0.045, WALL_T + 0.02]} />
        <meshStandardMaterial
          color={palette.binRim}
          emissive={palette.binRim}
          emissiveIntensity={1.4}
          metalness={0.3}
          roughness={0.35}
        />
      </mesh>
      <mesh position={[0, rimY, -BIN_D / 2 + WALL_T / 2]}>
        <boxGeometry args={[BIN_W, 0.045, WALL_T + 0.02]} />
        <meshStandardMaterial
          color={palette.binRim}
          emissive={palette.binRim}
          emissiveIntensity={1.4}
          metalness={0.3}
          roughness={0.35}
        />
      </mesh>
      <mesh position={[BIN_W / 2 - WALL_T / 2, rimY, 0]}>
        <boxGeometry args={[WALL_T + 0.02, 0.045, BIN_D]} />
        <meshStandardMaterial
          color={palette.binRim}
          emissive={palette.binRim}
          emissiveIntensity={1.4}
          metalness={0.3}
          roughness={0.35}
        />
      </mesh>
      <mesh position={[-BIN_W / 2 + WALL_T / 2, rimY, 0]}>
        <boxGeometry args={[WALL_T + 0.02, 0.045, BIN_D]} />
        <meshStandardMaterial
          color={palette.binRim}
          emissive={palette.binRim}
          emissiveIntensity={1.4}
          metalness={0.3}
          roughness={0.35}
        />
      </mesh>

      {/* corner posts */}
      {[
        [BIN_W / 2 - WALL_T / 2, BIN_D / 2 - WALL_T / 2],
        [-BIN_W / 2 + WALL_T / 2, BIN_D / 2 - WALL_T / 2],
        [BIN_W / 2 - WALL_T / 2, -BIN_D / 2 + WALL_T / 2],
        [-BIN_W / 2 + WALL_T / 2, -BIN_D / 2 + WALL_T / 2],
      ].map(([x, z], i) => (
        <mesh key={`post-${i}`} position={[x, wallY, z]}>
          <boxGeometry args={[WALL_T + 0.06, BIN_WALL_H + 0.12, WALL_T + 0.06]} />
          <meshStandardMaterial color={palette.binBody} metalness={0.9} roughness={0.25} />
        </mesh>
      ))}

      {/* bay markers on the bin floor */}
      {Array.from({ length: DEPOT_ROWS }).map((_, row) =>
        Array.from({ length: DEPOT_COLS }).map((_, col) => {
          const x = (col - 1) * SLOT_PITCH
          const z = (1 - row) * SLOT_PITCH
          const filled = (occupancy.get(`${col}-${row}`) ?? 0) > 0
          return (
            <mesh
              key={`slot-${col}-${row}`}
              rotation={[-Math.PI / 2, 0, 0]}
              position={[x, BASE_H + 0.012, z]}
            >
              <planeGeometry args={[SLOT_PITCH - 0.06, SLOT_PITCH - 0.06]} />
              <meshBasicMaterial
                color={palette.binRim}
                transparent
                opacity={filled ? 0.04 : 0.22}
                depthWrite={false}
                side={THREE.DoubleSide}
              />
            </mesh>
          )
        }),
      )}

      {/* soft emerald fill so the bay reads in the dark palette */}
      <pointLight
        position={[0, BASE_H + 1.1, 0]}
        color={palette.binRim}
        intensity={palette.rimIntensity * 6}
        distance={7}
        decay={2}
      />
    </group>
  )
}
