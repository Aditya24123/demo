import { useEffect, useMemo, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { GizmoHelper, GizmoViewport, OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import type { Structure3DVM } from '@/catalyst/bridge/viewModels';
import { AtomMesh } from './AtomMesh';
import { BondCylinder } from './BondCylinder';
import { UnitCell } from './UnitCell';
import { computeBondSegments, parseStructure } from './structureMath';

type CrystalStructureViewerProps = {
  structure: Structure3DVM | null;
  showBonds: boolean;
  showUnitCell: boolean;
  atomScale: number;
  resetNonce: number;
};

export function CrystalStructureViewer({
  structure,
  showBonds,
  showUnitCell,
  atomScale,
  resetNonce,
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

      <group>
        {showUnitCell && <UnitCell vectors={parsed.latticeVectors} />}
        {bonds.map((bond, idx) => (
          <BondCylinder key={idx} bond={bond} />
        ))}
        {parsed.sites.map((site) => (
          <AtomMesh key={`${site.label}-${site.index}`} site={site} scale={atomScale} />
        ))}
      </group>

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
