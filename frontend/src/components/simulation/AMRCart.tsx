// AMRCart — procedural industrial Autonomous Mobile Robot cart.
//
// Built entirely from composite Three.js primitives (no external .gltf), per the
// scene brief:
//   • 1.2 m × 0.3 m × 1.8 m metallic chassis with 4 driven wheels
//   • top-mounted LiDAR rig with a spinning cyan scan line
//   • rear status LED bar that encodes nav state by colour
//   • forward mast + two fork tines that slide under a crate and lift it
//   • a `gripperAnchor` group that physically parents the carried crate, so the
//     crate is locked to the cart in the scene graph while driving
//
// Local +Z is the fork/forward direction; the engine keeps `heading` aligned to
// the travel vector, so rotation.y = heading points the forks at the load.
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

import type { CargoTask, RobotSim } from '../../simulation/engine'
import type { ScenePalette } from './scenePalette'
import { ledColorFor } from './scenePalette'
import { CargoCrate } from './CargoCrate'

export const CART_W = 1.2
export const CART_H = 0.3
export const CART_L = 1.8
const WHEEL_R = 0.2
const WHEEL_W = 0.1
const DECK_Y = 0.5
const FORK_Z = 1
const FORK_TRAVEL = 0.4
const MAST_TOP = 1.95

interface AMRCartProps {
  robot: RobotSim
  palette: ScenePalette
  carrying: CargoTask | null
}

export function AMRCart({ robot, palette, carrying }: AMRCartProps) {
  const rootRef = useRef<THREE.Group>(null)
  const carriageRef = useRef<THREE.Group>(null)
  const forkRef = useRef<THREE.Group>(null)
  const wheelRefs = useRef<Array<THREE.Mesh | null>>([])
  const lidarRef = useRef<THREE.Group>(null)
  const ledRef = useRef<THREE.MeshStandardMaterial>(null)

  const led = ledColorFor(palette, robot.nav_state)

  useFrame((_, delta) => {
    const g = rootRef.current
    if (g) {
      // frame-rate independent smoothing toward the engine position
      const k = 1 - Math.pow(0.0015, Math.min(delta, 0.1))
      g.position.x += (robot.x - g.position.x) * k
      g.position.z += (robot.z - g.position.z) * k

      let dh = robot.heading - g.rotation.y
      dh = Math.atan2(Math.sin(dh), Math.cos(dh))
      g.rotation.y += dh * k
    }

    const carriage = carriageRef.current
    if (carriage) {
      const k = 1 - Math.pow(0.0004, Math.min(delta, 0.1))
      carriage.position.y += (robot.liftY - carriage.position.y) * k
    }

    const fork = forkRef.current
    if (fork) {
      const k = 1 - Math.pow(0.0008, Math.min(delta, 0.1))
      const target = robot.forkExtension * FORK_TRAVEL
      fork.position.z += (target - fork.position.z) * k
    }

    const speed = Math.hypot(robot.vx, robot.vz)
    for (const wheel of wheelRefs.current) {
      if (wheel) wheel.rotation.y += (speed / WHEEL_R) * delta
    }

    if (lidarRef.current) lidarRef.current.rotation.y += delta * 2.4

    if (ledRef.current) {
      const target = new THREE.Color(led)
      ledRef.current.emissive.lerp(target, 0.2)
    }
  })

  const isIdle = robot.nav_state === 'idle' || robot.nav_state === 'staging'

  return (
    <group ref={rootRef} position={[robot.x, 0, robot.z]} rotation={[0, robot.heading, 0]}>
      {/* ground marker — a faint ring under the cart so idle carts are visible
          on the dark warehouse floor */}
      {(isIdle || robot.nav_state === 'charging') && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 0]}>
          <ringGeometry args={[0.5, 0.7, 32]} />
          <meshBasicMaterial
            color={palette.cartAccent}
            transparent
            opacity={0.18}
            depthWrite={false}
            side={THREE.DoubleSide}
          />
        </mesh>
      )}

      {/* chassis */}
      <mesh castShadow receiveShadow position={[0, CART_H / 2 + 0.16, 0]}>
        <boxGeometry args={[CART_W, CART_H, CART_L]} />
        <meshStandardMaterial color={palette.cartBody} metalness={0.8} roughness={0.22} />
      </mesh>

      {/* deck plate */}
      <mesh castShadow receiveShadow position={[0, DECK_Y, 0]}>
        <boxGeometry args={[CART_W - 0.1, 0.05, CART_L - 0.16]} />
        <meshStandardMaterial color={palette.cartDeck} metalness={0.7} roughness={0.35} />
      </mesh>

      {/* battery / electronics housing */}
      <mesh castShadow position={[0, 0.62, -0.35]}>
        <boxGeometry args={[0.78, 0.18, 0.9]} />
        <meshStandardMaterial color={palette.cartBody} metalness={0.65} roughness={0.4} />
      </mesh>

      {/* side accent rails */}
      <mesh position={[CART_W / 2 + 0.005, 0.4, 0]}>
        <boxGeometry args={[0.02, 0.05, CART_L - 0.3]} />
        <meshStandardMaterial
          color={palette.cartAccent}
          emissive={palette.cartAccent}
          emissiveIntensity={0.8}
          roughness={0.3}
        />
      </mesh>
      <mesh position={[-CART_W / 2 - 0.005, 0.4, 0]}>
        <boxGeometry args={[0.02, 0.05, CART_L - 0.3]} />
        <meshStandardMaterial
          color={palette.cartAccent}
          emissive={palette.cartAccent}
          emissiveIntensity={0.8}
          roughness={0.3}
        />
      </mesh>

      {/* driven wheels */}
      {[
        [-CART_W / 2 + 0.06, 0.62],
        [CART_W / 2 - 0.06, 0.62],
        [-CART_W / 2 + 0.06, -0.62],
        [CART_W / 2 - 0.06, -0.62],
      ].map(([x, z], i) => (
        <group key={i} position={[x, WHEEL_R, z]} rotation={[0, 0, Math.PI / 2]}>
          <mesh
            ref={(el) => {
              wheelRefs.current[i] = el
            }}
            castShadow
          >
            <cylinderGeometry args={[WHEEL_R, WHEEL_R, WHEEL_W, 20]} />
            <meshStandardMaterial color={palette.cartWheel} metalness={0.35} roughness={0.75} />
          </mesh>
          {/* hub */}
          <mesh>
            <cylinderGeometry args={[WHEEL_R * 0.45, WHEEL_R * 0.45, WHEEL_W + 0.02, 12]} />
            <meshStandardMaterial color={palette.cartDeck} metalness={0.85} roughness={0.3} />
          </mesh>
        </group>
      ))}

      {/* LiDAR / sensor rig — static base + spinning scan line */}
      <group position={[0, 0.71, 0.3]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.19, 0.22, 0.09, 24]} />
          <meshStandardMaterial color={palette.cartDeck} metalness={0.7} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0.1, 0]}>
          <cylinderGeometry args={[0.14, 0.16, 0.14, 24]} />
          <meshStandardMaterial color={palette.cartLidar} metalness={0.4} roughness={0.15} />
        </mesh>
        <group ref={lidarRef} position={[0, 0.14, 0]}>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <ringGeometry args={[0.11, 0.14, 28]} />
            <meshBasicMaterial color={palette.cartAccent} transparent opacity={0.85} side={THREE.DoubleSide} />
          </mesh>
          <mesh rotation={[0, 0, 0]} position={[0, 0.01, 0]}>
            <boxGeometry args={[0.55, 0.006, 0.012]} />
            <meshBasicMaterial color={palette.cartAccent} transparent opacity={0.55} />
          </mesh>
        </group>
      </group>

      {/* rear status LED bar */}
      <mesh position={[0, 0.46, -CART_L / 2 - 0.005]}>
        <boxGeometry args={[0.82, 0.07, 0.03]} />
        <meshStandardMaterial
          ref={ledRef}
          color={led}
          emissive={led}
          emissiveIntensity={1.6}
          roughness={0.3}
        />
      </mesh>

      {/* headlights */}
      <mesh position={[-0.38, 0.44, CART_L / 2 + 0.01]}>
        <boxGeometry args={[0.16, 0.07, 0.03]} />
        <meshStandardMaterial
          color={palette.headlightColor}
          emissive={palette.headlightColor}
          emissiveIntensity={1.4}
        />
      </mesh>
      <mesh position={[0.38, 0.44, CART_L / 2 + 0.01]}>
        <boxGeometry args={[0.16, 0.07, 0.03]} />
        <meshStandardMaterial
          color={palette.headlightColor}
          emissive={palette.headlightColor}
          emissiveIntensity={1.4}
        />
      </mesh>
      <pointLight
        position={[0, 0.5, CART_L / 2 + 0.4]}
        color={palette.headlightColor}
        intensity={palette.headlightIntensity}
        distance={7}
        decay={2}
      />

      {/* lift mast — two uprights + top crossbar */}
      {[-0.42, 0.42].map((x) => (
        <mesh key={`mast-${x}`} castShadow position={[x, (MAST_TOP + DECK_Y) / 2, 0.64]}>
          <boxGeometry args={[0.07, MAST_TOP - DECK_Y, 0.07]} />
          <meshStandardMaterial color={palette.cartDeck} metalness={0.85} roughness={0.28} />
        </mesh>
      ))}
      <mesh position={[0, MAST_TOP, 0.64]}>
        <boxGeometry args={[0.91, 0.07, 0.07]} />
        <meshStandardMaterial color={palette.cartDeck} metalness={0.85} roughness={0.28} />
      </mesh>

      {/* fork carriage — vertical travel = robot.liftY */}
      <group ref={carriageRef} position={[0, robot.liftY, 0]}>
        <mesh castShadow position={[0, 0, 0.58]}>
          <boxGeometry args={[0.86, 0.16, 0.09]} />
          <meshStandardMaterial color={palette.cartDeck} metalness={0.8} roughness={0.3} />
        </mesh>

        <group ref={forkRef}>
          {[-0.32, 0.32].map((x) => (
            <mesh key={`fork-${x}`} castShadow receiveShadow position={[x, 0, FORK_Z]}>
              <boxGeometry args={[0.14, 0.06, 0.8]} />
              <meshStandardMaterial color={palette.crateEdge} metalness={0.9} roughness={0.25} />
            </mesh>
          ))}

          {/* gripperAnchor: the carried crate is parented here and rides with the
              fork carriage (smoothed with the tines, not snapped to engine state) */}
          <group name="gripperAnchor" position={[0, 0, FORK_Z]}>
            {carrying ? <CargoCrate task={carrying} palette={palette} mode="carried" /> : null}
          </group>
        </group>
      </group>
    </group>
  )
}
