import { Suspense } from 'react'
import { Canvas } from '@react-three/fiber'
import SolarScene3D from './SolarScene3D'

function SceneLoader() {
  return null
}

export default function Background3D() {
  return (
    <div className="bg-3d-canvas" aria-hidden="true">
      <Canvas
        camera={{ position: [0, 1.2, 10], fov: 52, near: 0.1, far: 80 }}
        dpr={[1, 2]}
        gl={{
          antialias: true,
          alpha: false,
          powerPreference: 'high-performance',
          stencil: false,
        }}
      >
        <Suspense fallback={<SceneLoader />}>
          <SolarScene3D />
        </Suspense>
      </Canvas>
      <div className="bg-faint-grid" />
    </div>
  )
}
