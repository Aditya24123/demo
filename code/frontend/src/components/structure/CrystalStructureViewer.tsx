import { useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { GizmoHelper, GizmoViewport, OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import type { Structure3DVM } from '@/catalyst/bridge/viewModels';
import { AtomMesh } from './AtomMesh';
import { BondCylinder } from './BondCylinder';
import { UnitCell } from './UnitCell';
import { computeBondSegments, parseStructure } from './structureMath';
import type { Group } from 'three';
import type { DemoAnimation } from '@/catalyst/ui-state/layoutStore';
import type { BondSegment, ParsedSite, Vec3 } from './structureMath';

type CrystalStructureViewerProps = {
  structure: Structure3DVM | null;
  showBonds: boolean;
  showUnitCell: boolean;
  atomScale: number;
  resetNonce: number;
  demoAnimation?: DemoAnimation | null;
};

function easeInOut(value: number): number {
  const t = Math.max(0, Math.min(1, value));
  return t * t * (3 - 2 * t);
}

function scatterOffset(index: number): Vec3 {
  const angle = index * 2.399963;
  const radius = 4.4 + (index % 4) * 0.72;
  return [Math.cos(angle) * radius, Math.sin(angle) * radius, ((index % 7) - 3) * 1.15];
}

function AnimatedAtom({ site, scale, animation }: { site: ParsedSite; scale: number; animation?: DemoAnimation | null }) {
  const ref = useRef<Group | null>(null);
  const offset = useMemo(() => scatterOffset(site.index), [site.index]);
  useFrame(() => {
    if (!ref.current) return;
    if (!animation || animation.phase !== 'assemble') {
      ref.current.position.set(0, 0, 0);
      ref.current.rotation.set(0, 0, 0);
      return;
    }
    const progress = easeInOut((Date.now() - animation.startedAt) / animation.durationMs);
    const remaining = 1 - progress;
    ref.current.position.set(offset[0] * remaining, offset[1] * remaining, offset[2] * remaining);
    ref.current.rotation.set(remaining * 1.1, remaining * (site.index % 3), remaining * 0.7);
  });
  return <group ref={ref}><AtomMesh site={site} scale={scale} /></group>;
}

function AnimatedStructure({ sites, bonds, latticeVectors, showBonds, showUnitCell, atomScale, animation }: { sites: ParsedSite[]; bonds: BondSegment[]; latticeVectors: Vec3[]; showBonds: boolean; showUnitCell: boolean; atomScale: number; animation?: DemoAnimation | null }) {
  const [settled, setSettled] = useState(!animation);
  useEffect(() => { setSettled(!animation || animation.phase !== 'assemble'); }, [animation?.nonce, animation?.phase]);
  useFrame(() => {
    if (animation?.phase === 'assemble' && !settled && Date.now() - animation.startedAt >= animation.durationMs * 0.78) setSettled(true);
  });
  return <group>
    {(showUnitCell || (settled && Boolean(animation))) && <UnitCell vectors={latticeVectors} />}
    {showBonds && settled && bonds.map((bond, idx) => <BondCylinder key={idx} bond={bond} />)}
    {sites.map((site) => <AnimatedAtom key={`${site.label}-${site.index}`} site={site} scale={atomScale} animation={animation} />)}
  </group>;
}

export function CrystalStructureViewer({
  structure,
  showBonds,
  showUnitCell,
  atomScale,
  resetNonce,
  demoAnimation,
}: CrystalStructureViewerProps) {
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const parsed = useMemo(() => parseStructure(structure), [structure]);
  const bonds = useMemo(
    () =>
      showBonds
        ? computeBondSegments(parsed.sites, {
            latticeVectors: parsed.latticeVectors,
            periodic: parsed.latticeVectors.length === 3,
          })
        : [],
    [parsed.latticeVectors, parsed.sites, showBonds],
  );

  const radius = useMemo(() => {
    const distances = parsed.sites.map((site) => Math.hypot(...site.position));
    const latticeExtent = parsed.latticeVectors.flatMap((vector) => vector).map(Math.abs);
    return Math.max(1.5, ...distances, ...(latticeExtent.length ? [Math.max(...latticeExtent) * 0.7] : []));
  }, [parsed.latticeVectors, parsed.sites]);
  const cameraDistance = Math.max(8, radius * 2.9);

  useEffect(() => {
    if (!controlsRef.current) return;
    controlsRef.current.reset();
  }, [resetNonce]);

  if (!structure || !parsed.sites.length) {
    return (
      <div className="flex h-full items-center justify-center text-sm" style={{ color: 'var(--text-3)' }}>
        Full 3D structure record unavailable in local snapshot
      </div>
    );
  }

  return (
    <Canvas
      key={`${structure.material_id || structure.formula_pretty || 'structure'}-${parsed.sites.length}`}
      camera={{ position: [cameraDistance * 0.72, cameraDistance * 0.52, cameraDistance], fov: 38, near: 0.05, far: Math.max(2000, cameraDistance * 12) }}
      gl={{ antialias: true, preserveDrawingBuffer: false, powerPreference: 'high-performance' }}
      dpr={[1, 2]}
      style={{ background: 'transparent' }}
    >
      <color attach="background" args={['#0b0d10']} />
      <ambientLight intensity={0.82} />
      <hemisphereLight args={['#e8f0ff', '#12141a', 0.95]} />
      <directionalLight position={[cameraDistance, cameraDistance * 1.4, cameraDistance]} intensity={1.45} />
      <directionalLight position={[-cameraDistance, -cameraDistance * 0.4, -cameraDistance]} intensity={0.55} color="#9bb4d8" />
      <pointLight position={[0, cameraDistance, 0]} intensity={0.35} color="#cfe0ff" />

      <AnimatedStructure sites={parsed.sites} bonds={bonds} latticeVectors={parsed.latticeVectors} showBonds={showBonds} showUnitCell={showUnitCell} atomScale={atomScale} animation={demoAnimation} />

      <GizmoHelper alignment="bottom-right" margin={[56, 56]}>
        <GizmoViewport axisColors={['#ef4444', '#22c55e', '#3b82f6']} labelColor="white" />
      </GizmoHelper>

      <OrbitControls
        ref={controlsRef}
        enableDamping
        dampingFactor={0.08}
        minDistance={Math.max(2, radius * 0.55)}
        maxDistance={cameraDistance * 3}
        makeDefault
      />
    </Canvas>
  );
}
