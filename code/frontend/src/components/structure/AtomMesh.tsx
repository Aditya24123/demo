import { Html, Sphere } from '@react-three/drei';
import { useState } from 'react';
import { elementColor } from './elementColors';
import type { ParsedSite } from './structureMath';

type AtomMeshProps = {
  site: ParsedSite;
  scale?: number;
};

export function AtomMesh({ site, scale = 0.36 }: AtomMeshProps) {
  const [hovered, setHovered] = useState(false);
  return (
    <Sphere
      args={[Math.max(0.1, site.radius * scale), 36, 36]}
      position={site.position}
      onPointerOver={(event) => { event.stopPropagation(); setHovered(true); document.body.style.cursor = 'pointer'; }}
      onPointerOut={() => { setHovered(false); document.body.style.cursor = ''; }}
    >
      <meshPhysicalMaterial
        color={elementColor(site.element)}
        metalness={0.14}
        roughness={0.22}
        clearcoat={0.62}
        clearcoatRoughness={0.18}
        reflectivity={0.55}
      />
      {hovered ? (
        <Html center position={[0, Math.max(0.34, site.radius * scale + 0.22), 0]} style={{ pointerEvents: 'none' }}>
          <div className="jarvis-atom-label">{site.element}<span>{site.index + 1}</span></div>
        </Html>
      ) : null}
    </Sphere>
  );
}
