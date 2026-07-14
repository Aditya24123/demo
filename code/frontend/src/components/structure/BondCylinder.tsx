import { useMemo } from 'react';
import { Quaternion, Vector3 } from 'three';
import type { BondSegment } from './structureMath';
import { elementColor } from './elementColors';

type BondCylinderProps = {
  bond: BondSegment;
  radius?: number;
  color?: string;
};

export function BondCylinder({ bond, radius = 0.045, color }: BondCylinderProps) {
  const { firstMidpoint, secondMidpoint, halfLength, quaternion } = useMemo(() => {
    const a = new Vector3(...bond.a);
    const b = new Vector3(...bond.b);
    const dir = new Vector3().subVectors(b, a);
    const len = dir.length();
    const mid = new Vector3().addVectors(a, b).multiplyScalar(0.5);
    const first = new Vector3().addVectors(a, mid).multiplyScalar(0.5);
    const second = new Vector3().addVectors(mid, b).multiplyScalar(0.5);
    const q = new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), dir.normalize());
    return {
      firstMidpoint: [first.x, first.y, first.z] as [number, number, number],
      secondMidpoint: [second.x, second.y, second.z] as [number, number, number],
      halfLength: len / 2,
      quaternion: q,
    };
  }, [bond]);

  if (!Number.isFinite(halfLength) || halfLength <= 0.001) return null;

  return (
    <group>
      <mesh position={firstMidpoint} quaternion={quaternion}>
        <cylinderGeometry args={[radius, radius, halfLength, 16]} />
        <meshStandardMaterial color={color || elementColor(bond.aElement)} metalness={0.05} roughness={0.55} />
      </mesh>
      <mesh position={secondMidpoint} quaternion={quaternion}>
        <cylinderGeometry args={[radius, radius, halfLength, 16]} />
        <meshStandardMaterial color={color || elementColor(bond.bElement)} metalness={0.05} roughness={0.55} />
      </mesh>
    </group>
  );
}
