import { GizmoHelper, GizmoViewport, Line, OrbitControls, Sphere } from '@react-three/drei';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { Vector3, type Group } from 'three';
import type { DemoAnimation } from '@/catalyst/ui-state/layoutStore';

type DnaViewerProps = { basePairs: string[]; selectedIndex: number; onSelect: (index: number) => void; resetNonce: number; demoAnimation?: DemoAnimation | null };
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

function smooth(value: number): number {
  const t = Math.max(0, Math.min(1, value));
  return t * t * (3 - 2 * t);
}

function AnimatedPair({ pair, index, total, selected, bases, onSelect, animation }: { pair: { left: Vec3; right: Vec3 }; index: number; total: number; selected: boolean; bases: string; onSelect: (index: number) => void; animation?: DemoAnimation | null }) {
  const ref = useRef<Group | null>(null);
  const fragment = Math.min(3, Math.floor(index / Math.max(1, Math.ceil(total / 4))));
  const entryOffsets: Vec3[] = [[-4.8, 2.8, -2.2], [4.6, -2.6, 1.4], [-3.8, -3.2, 2.4], [4.4, 3.1, -1.4]];
  const entryRotations: Vec3[] = [[1.1, -0.8, 0.5], [-0.9, 1.2, -0.6], [0.7, 0.8, 1.1], [-1.0, -1.1, 0.8]];
  useFrame(() => {
    if (!ref.current) return;
    const assembling = animation?.phase === 'assemble';
    const progress = assembling ? smooth((Date.now() - animation.startedAt) / animation.durationMs) : 1;
    const remaining = 1 - progress;
    const offset = entryOffsets[fragment]; const rotation = entryRotations[fragment];
    ref.current.position.set(offset[0] * remaining, offset[1] * remaining, offset[2] * remaining);
    ref.current.rotation.set(rotation[0] * remaining, rotation[1] * remaining, rotation[2] * remaining);
  });
  const [leftBase, rightBase] = bases || ['A', 'T'];
  const rungColor = selected ? '#fb7185' : '#64748b';
  return <group ref={ref}>
    <Line points={[pair.left, pair.right]} color={rungColor} lineWidth={selected ? 4 : 2} transparent opacity={selected ? 1 : 0.76} />
    <Sphere args={[selected ? 0.18 : 0.11, 20, 20]} position={pair.left} onClick={(event) => { event.stopPropagation(); onSelect(index); }} onPointerOver={(event) => { event.stopPropagation(); document.body.style.cursor = 'pointer'; }} onPointerOut={() => { document.body.style.cursor = ''; }}><meshStandardMaterial color={selected ? '#fb7185' : BASE_COLORS[leftBase] || '#cbd5e1'} emissive={selected ? '#7f1d1d' : '#000000'} emissiveIntensity={selected ? 0.6 : 0} /></Sphere>
    <Sphere args={[selected ? 0.18 : 0.11, 20, 20]} position={pair.right} onClick={(event) => { event.stopPropagation(); onSelect(index); }}><meshStandardMaterial color={selected ? '#fb7185' : BASE_COLORS[rightBase] || '#cbd5e1'} emissive={selected ? '#7f1d1d' : '#000000'} emissiveIntensity={selected ? 0.6 : 0} /></Sphere>
  </group>;
}

function SequenceWindow({ basePairs, selectedIndex, onSelect, demoAnimation }: Omit<DnaViewerProps, 'resetNonce'>) {
  const positions = useMemo(() => basePairs.map((_, index) => pairPositions(index, basePairs.length)), [basePairs]);
  const [connected, setConnected] = useState(demoAnimation?.phase !== 'assemble');
  useEffect(() => { setConnected(demoAnimation?.phase !== 'assemble'); }, [demoAnimation?.nonce, demoAnimation?.phase]);
  useFrame(() => {
    if (demoAnimation?.phase === 'assemble' && !connected && Date.now() - demoAnimation.startedAt >= demoAnimation.durationMs * 0.74) setConnected(true);
  });
  return <group>
    {connected && <><Line points={positions.map((pair) => pair.left)} color="#5eead4" lineWidth={3.2} transparent opacity={0.96} /><Line points={positions.map((pair) => pair.right)} color="#93c5fd" lineWidth={3.2} transparent opacity={0.96} /><WireBox depth={Math.max(4.8, basePairs.length * 0.34 + 0.8)} /></>}
    {positions.map((pair, index) => {
      const selected = index === selectedIndex;
      return <AnimatedPair key={`${index}-${basePairs[index]}`} pair={pair} index={index} total={basePairs.length} selected={selected} bases={basePairs[index]} onSelect={onSelect} animation={demoAnimation} />;
    })}
  </group>;
}

function DemoDnaCamera({ animation, selectedIndex, total, controlsRef }: { animation?: DemoAnimation | null; selectedIndex: number; total: number; controlsRef: React.MutableRefObject<OrbitControlsImpl | null> }) {
  const { camera } = useThree();
  const startPosition = useRef(new Vector3());
  const startTarget = useRef(new Vector3());
  useEffect(() => {
    if (animation?.phase !== 'focus') return;
    startPosition.current.copy(camera.position);
    if (controlsRef.current) startTarget.current.copy(controlsRef.current.target);
  }, [animation?.nonce, animation?.phase, camera, controlsRef]);
  useFrame(() => {
    if (animation?.phase !== 'focus') return;
    const t = smooth((Date.now() - animation.startedAt) / animation.durationMs);
    const z = (selectedIndex - (total - 1) / 2) * 0.31;
    camera.position.lerpVectors(startPosition.current, new Vector3(3.0, 2.35, z + 3.7), t);
    if (controlsRef.current) {
      controlsRef.current.target.lerpVectors(startTarget.current, new Vector3(0, 0, z), t);
      controlsRef.current.update();
    }
  });
  return null;
}

export function DnaViewer({ basePairs, selectedIndex, onSelect, resetNonce, demoAnimation }: DnaViewerProps) {
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const safeSelectedIndex = Math.max(0, Math.min(basePairs.length - 1, selectedIndex));
  useEffect(() => { controlsRef.current?.reset(); }, [resetNonce]);
  return <Canvas camera={{ position: [4.8, 4.1, 6.8], fov: 36, near: 0.05, far: 100 }} dpr={[1, 2]} gl={{ antialias: true, powerPreference: 'high-performance' }} style={{ background: 'transparent' }}>
    <color attach="background" args={['#090d15']} /><ambientLight intensity={0.75} /><hemisphereLight args={['#dbeafe', '#0b1020', 1.1]} /><directionalLight position={[5, 7, 8]} intensity={1.45} color="#dbeafe" /><pointLight position={[-3, 1, 4]} intensity={0.7} color="#5eead4" />
    <SequenceWindow basePairs={basePairs} selectedIndex={safeSelectedIndex} onSelect={onSelect} demoAnimation={demoAnimation} />
    <DemoDnaCamera animation={demoAnimation} selectedIndex={safeSelectedIndex} total={basePairs.length} controlsRef={controlsRef} />
    <GizmoHelper alignment="bottom-right" margin={[44, 44]}><GizmoViewport axisColors={['#ef4444', '#22c55e', '#3b82f6']} labelColor="white" /></GizmoHelper>
    <OrbitControls ref={controlsRef} enableDamping dampingFactor={0.08} minDistance={3.6} maxDistance={16} makeDefault />
  </Canvas>;
}
