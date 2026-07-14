import { GizmoHelper, GizmoViewport, Line, OrbitControls, Sphere } from '@react-three/drei';
import { Canvas } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';

type DnaViewerProps = { basePairs: string[]; selectedIndex: number; onSelect: (index: number) => void; resetNonce: number };
type Vec3 = [number, number, number];
const BASE_COLORS: Record<string, string> = { A: '#38bdf8', T: '#f59e0b', C: '#a78bfa', G: '#34d399' };

function pairPositions(index: number, total: number): { left: Vec3; right: Vec3 } {
  const angle = index * 0.64;
  const z = (index - (total - 1) / 2) * 0.31;
  return { left: [Math.cos(angle) * 1.05, Math.sin(angle) * 1.05, z], right: [Math.cos(angle + Math.PI) * 1.05, Math.sin(angle + Math.PI) * 1.05, z] };
}

function WireBox({ depth }: { depth: number }) {
  const x = 1.55; const y = 1.55; const z = depth / 2;
  const corners: Vec3[] = [[-x, -y, -z], [x, -y, -z], [x, y, -z], [-x, y, -z], [-x, -y, z], [x, -y, z], [x, y, z], [-x, y, z]];
  const edges = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];
  return <group>{edges.map(([a, b]) => <Line key={`${a}-${b}`} points={[corners[a], corners[b]]} color="#475569" lineWidth={0.8} transparent opacity={0.2} />)}</group>;
}

function SequenceWindow({ basePairs, selectedIndex, onSelect }: Omit<DnaViewerProps, 'resetNonce'>) {
  const positions = useMemo(() => basePairs.map((_, index) => pairPositions(index, basePairs.length)), [basePairs]);
  return <group>
    <Line points={positions.map((pair) => pair.left)} color="#5eead4" lineWidth={3.2} transparent opacity={0.96} />
    <Line points={positions.map((pair) => pair.right)} color="#93c5fd" lineWidth={3.2} transparent opacity={0.96} />
    <WireBox depth={Math.max(4.8, basePairs.length * 0.34 + 0.8)} />
    {positions.map((pair, index) => {
      const selected = index === selectedIndex;
      const [leftBase, rightBase] = basePairs[index] || ['A', 'T'];
      const rungColor = selected ? '#fb7185' : '#64748b';
      return <group key={`${index}-${leftBase}${rightBase}`}>
        <Line points={[pair.left, pair.right]} color={rungColor} lineWidth={selected ? 4 : 2} transparent opacity={selected ? 1 : 0.76} />
        <Sphere args={[selected ? 0.18 : 0.11, 20, 20]} position={pair.left} onClick={(event) => { event.stopPropagation(); onSelect(index); }} onPointerOver={(event) => { event.stopPropagation(); document.body.style.cursor = 'pointer'; }} onPointerOut={() => { document.body.style.cursor = ''; }}><meshStandardMaterial color={selected ? '#fb7185' : BASE_COLORS[leftBase] || '#cbd5e1'} emissive={selected ? '#7f1d1d' : '#000000'} emissiveIntensity={selected ? 0.6 : 0} /></Sphere>
        <Sphere args={[selected ? 0.18 : 0.11, 20, 20]} position={pair.right} onClick={(event) => { event.stopPropagation(); onSelect(index); }}><meshStandardMaterial color={selected ? '#fb7185' : BASE_COLORS[rightBase] || '#cbd5e1'} emissive={selected ? '#7f1d1d' : '#000000'} emissiveIntensity={selected ? 0.6 : 0} /></Sphere>
      </group>;
    })}
  </group>;
}

export function DnaViewer({ basePairs, selectedIndex, onSelect, resetNonce }: DnaViewerProps) {
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const safeSelectedIndex = Math.max(0, Math.min(basePairs.length - 1, selectedIndex));
  useEffect(() => { controlsRef.current?.reset(); }, [resetNonce]);
  return <Canvas camera={{ position: [4.8, 4.1, 6.8], fov: 36, near: 0.05, far: 100 }} dpr={[1, 2]} gl={{ antialias: true, powerPreference: 'high-performance' }} style={{ background: 'transparent' }}>
    <color attach="background" args={['#090d15']} /><ambientLight intensity={0.75} /><hemisphereLight args={['#dbeafe', '#0b1020', 1.1]} /><directionalLight position={[5, 7, 8]} intensity={1.45} color="#dbeafe" /><pointLight position={[-3, 1, 4]} intensity={0.7} color="#5eead4" />
    <SequenceWindow basePairs={basePairs} selectedIndex={safeSelectedIndex} onSelect={onSelect} />
    <GizmoHelper alignment="bottom-right" margin={[44, 44]}><GizmoViewport axisColors={['#ef4444', '#22c55e', '#3b82f6']} labelColor="white" /></GizmoHelper>
    <OrbitControls ref={controlsRef} enableDamping dampingFactor={0.08} minDistance={3.6} maxDistance={16} makeDefault />
  </Canvas>;
}
