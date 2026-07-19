import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { CapsuleGeometry } from 'three'
import * as THREE from 'three'

function Nucleotide({ position, rotation }: { position: [number, number, number]; rotation: [number, number, number] }) {
  const geometry = useMemo(() => new CapsuleGeometry(0.3, 0.8, 4, 8), [])

  return (
    <mesh position={position} rotation={rotation} geometry={geometry} castShadow>
      <meshPhysicalMaterial
        color="#F0F0F3"
        roughness={0.4}
        metalness={0.1}
        clearcoat={0.1}
        clearcoatRoughness={0.2}
      />
    </mesh>
  )
}

function Rung({ start, end }: { start: [number, number, number]; end: [number, number, number] }) {
  const direction = new THREE.Vector3(...end).sub(new THREE.Vector3(...start))
  const length = direction.length()
  const mid = new THREE.Vector3(...start).add(new THREE.Vector3(...end)).multiplyScalar(0.5)

  const quaternion = new THREE.Quaternion()
  quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.clone().normalize())

  return (
    <mesh position={[mid.x, mid.y, mid.z]} quaternion={quaternion}>
      <cylinderGeometry args={[0.08, 0.08, length, 8]} />
      <meshPhysicalMaterial
        color="#E8E8EE"
        roughness={0.3}
        metalness={0.05}
        clearcoat={0.2}
        clearcoatRoughness={0.1}
      />
    </mesh>
  )
}

function HelixStructure() {
  const groupRef = useRef<THREE.Group>(null)
  const helixRadius = 2.5
  const spacing = 1.2
  const twistFactor = 0.6
  const count = 20

  const nucleotides = useMemo(() => {
    const items: { position: [number, number, number]; rotation: [number, number, number]; key: string }[] = []
    const rungs: { start: [number, number, number]; end: [number, number, number]; key: string }[] = []

    for (let i = 0; i < count; i++) {
      const y = (i - count / 2) * spacing
      const angle = i * twistFactor

      // Strand 1
      const x1 = Math.cos(angle) * helixRadius
      const z1 = Math.sin(angle) * helixRadius
      items.push({
        position: [x1, y, z1],
        rotation: [0, 0, angle + Math.PI / 2],
        key: `s1-${i}`,
      })

      // Strand 2 (opposite phase)
      const angle2 = angle + Math.PI
      const x2 = Math.cos(angle2) * helixRadius
      const z2 = Math.sin(angle2) * helixRadius
      items.push({
        position: [x2, y, z2],
        rotation: [0, 0, angle2 + Math.PI / 2],
        key: `s2-${i}`,
      })

      // Rung connecting the strands
      rungs.push({
        start: [x1, y, z1],
        end: [x2, y, z2],
        key: `rung-${i}`,
      })
    }

    return { items, rungs }
  }, [])

  useFrame((state) => {
    if (!groupRef.current) return
    groupRef.current.rotation.y += 0.005
    groupRef.current.rotation.x = state.mouse.y * 0.1
    groupRef.current.rotation.z = state.mouse.x * 0.05
    groupRef.current.position.y = Math.sin(state.clock.elapsedTime * 0.5) * 0.3
  })

  return (
    <group ref={groupRef}>
      {nucleotides.items.map((n) => (
        <Nucleotide key={n.key} position={n.position} rotation={n.rotation} />
      ))}
      {nucleotides.rungs.map((r) => (
        <Rung key={r.key} start={r.start} end={r.end} />
      ))}
    </group>
  )
}

export default function DNAHelix() {
  return (
    <div style={{ width: '100%', height: '60vh', minHeight: '400px' }}>
      <Canvas
        camera={{ position: [0, 0, 18], fov: 45 }}
        dpr={[1, 2]}
        gl={{ alpha: true, antialias: true }}
        style={{ background: 'transparent' }}
      >
        <ambientLight intensity={0.6} color="#ffffff" />
        <directionalLight intensity={1.2} color="#ffffff" position={[-5, 5, 5]} castShadow />
        <directionalLight intensity={0.5} color="#D1D1D6" position={[5, -5, 5]} />
        <rectAreaLight intensity={0.5} color="#E8E8EE" position={[0, 0, -5]} width={10} height={10} />
        <HelixStructure />
      </Canvas>
    </div>
  )
}
