import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { Stars, Cloud, Grid } from '@react-three/drei'
import { EffectComposer, Bloom } from '@react-three/postprocessing'
import * as THREE from 'three'

const METEOR_COUNT = 6

function DaySkyDome() {
  return (
    <mesh scale={[-1, 1, 1]}>
      <sphereGeometry args={[40, 64, 64]} />
      <meshBasicMaterial
        side={THREE.BackSide}
        color="#7ec8f8"
        transparent
        opacity={0.35}
        depthWrite={false}
      />
    </mesh>
  )
}

function TwinkleStars() {
  return (
    <>
      <Stars
        radius={80}
        depth={60}
        count={4500}
        factor={2.8}
        saturation={0.15}
        fade
        speed={0.35}
      />
      <Stars
        radius={55}
        depth={40}
        count={1200}
        factor={1.2}
        saturation={0}
        fade
        speed={0.15}
      />
    </>
  )
}

function Meteor({ index }) {
  const groupRef = useRef()
  const headMatRef = useRef()
  const trailMatRef = useRef()
  const glowMatRef = useRef()

  const config = useMemo(() => {
    const angle = -0.6 + (index / METEOR_COUNT) * 0.35
    const startX = 8 + Math.random() * 6
    const startY = 6 + Math.random() * 4
    const startZ = -8 - Math.random() * 10
    const length = 2.5 + Math.random() * 2
    const speed = 0.22 + Math.random() * 0.12
    const delay = index * 1.8 + Math.random() * 3
    const dir = new THREE.Vector3(Math.cos(angle), Math.sin(angle) * -0.85, 0.15).normalize()
    return { startX, startY, startZ, length, speed, delay, dir, angle }
  }, [index])

  useFrame(({ clock }) => {
    if (!groupRef.current) return

    const cycle = 5.5
    const elapsed = clock.getElapsedTime()
    const phase = ((elapsed * config.speed + config.delay) % cycle) / cycle

    if (phase > 0.82) {
      groupRef.current.visible = false
      return
    }

    groupRef.current.visible = true
    const travel = phase / 0.82
    const fade = phase < 0.08 ? phase / 0.08 : phase > 0.65 ? 1 - (phase - 0.65) / 0.17 : 1

    groupRef.current.position.set(
      config.startX + config.dir.x * travel * 14,
      config.startY + config.dir.y * travel * 14,
      config.startZ + config.dir.z * travel * 6,
    )

    if (trailMatRef.current) trailMatRef.current.opacity = 0.55 * fade
    if (glowMatRef.current) glowMatRef.current.opacity = 0.25 * fade
    if (headMatRef.current) headMatRef.current.opacity = 0.95 * fade
  })

  return (
    <group
      ref={groupRef}
      rotation={[0, 0, config.angle - Math.PI / 2]}
      visible={false}
    >
      <mesh position={[0, config.length / 2, 0]}>
        <boxGeometry args={[0.025, config.length, 0.025]} />
        <meshBasicMaterial
          ref={trailMatRef}
          color="#e0f2fe"
          transparent
          opacity={0.5}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[0, config.length * 0.92, 0]}>
        <boxGeometry args={[0.06, config.length * 0.35, 0.06]} />
        <meshBasicMaterial
          ref={glowMatRef}
          color="#bae6fd"
          transparent
          opacity={0.25}
          depthWrite={false}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.06, 16, 16]} />
        <meshBasicMaterial
          ref={headMatRef}
          color="#ffffff"
          transparent
          opacity={0.95}
          depthWrite={false}
        />
      </mesh>
    </group>
  )
}

function Meteors() {
  return (
    <>
      {Array.from({ length: METEOR_COUNT }, (_, i) => (
        <Meteor key={i} index={i} />
      ))}
    </>
  )
}

function SoftClouds() {
  return (
    <>
      <Cloud opacity={0.22} speed={0.08} bounds={[14, 2, 2]} segments={22} position={[-6, 3, -12]} color="#ffffff" />
      <Cloud opacity={0.18} speed={0.06} bounds={[12, 2, 2]} segments={18} position={[5, 4.5, -14]} color="#f0f9ff" />
      <Cloud opacity={0.14} speed={0.05} bounds={[10, 1.5, 2]} segments={16} position={[0, 2, -16]} color="#e0f2fe" />
    </>
  )
}

export default function SolarScene3D() {
  const rigRef = useRef()

  useFrame(({ clock }) => {
    if (rigRef.current) {
      rigRef.current.rotation.y = Math.sin(clock.getElapsedTime() * 0.04) * 0.03
    }
  })

  return (
    <>
      <color attach="background" args={['#87CEEB']} />
      <fog attach="fog" args={['#bae6fd', 14, 45]} />

      <ambientLight intensity={0.85} color="#e0f2fe" />
      <directionalLight position={[8, 12, 6]} intensity={1.1} color="#ffffff" />
      <directionalLight position={[-4, 6, -2]} intensity={0.35} color="#93c5fd" />
      <hemisphereLight args={['#7dd3fc', '#dbeafe', 0.65]} />

      <DaySkyDome />

      <Grid
        position={[0, -3.2, -4]}
        rotation={[0, 0, 0]}
        args={[40, 40]}
        cellSize={0.55}
        cellThickness={0.45}
        cellColor="#93c5fd"
        sectionSize={2.75}
        sectionThickness={0.85}
        sectionColor="#60a5fa"
        fadeDistance={38}
        fadeStrength={1.8}
        infiniteGrid
      />

      <group ref={rigRef}>
        <TwinkleStars />
        <SoftClouds />
        <Meteors />
      </group>

      <EffectComposer multisampling={4}>
        <Bloom
          luminanceThreshold={0.55}
          luminanceSmoothing={0.9}
          intensity={0.45}
          mipmapBlur
        />
      </EffectComposer>
    </>
  )
}
