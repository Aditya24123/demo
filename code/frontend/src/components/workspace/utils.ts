import type { PropertyGroupVM, PropertyMetricVM } from '@/catalyst/bridge/viewModels';
import type { SearchFilters } from './types';

export function detailCacheKey(materialId: string, sections: string[], limit = 25, downsample = true): string {
  return `${materialId}::${sections.join(',')}::${limit}::${String(downsample)}`;
}

/** Hop budget for neighborhood fetches ? must stay ? backend /neighborhood limit_nodes max (800). */
export function hopLimitNodes(depth: number): number {
  const d = Math.max(1, Math.min(5, Math.round(Number(depth) || 1)));
  return Math.min(800, 48 + d * 140);
}

export function edgeEndpoint(value: unknown): string {
  if (value && typeof value === 'object' && 'id' in value) return String((value as { id: string }).id);
  return String(value);
}

export function formatValue(value: unknown, unit = ''): string {
  if (value === null || value === undefined || value === '') return '-';
  const n = Number(value);
  if (Number.isFinite(n)) {
    const rendered = Math.abs(n) >= 10 ? n.toFixed(2) : n.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
    return `${rendered}${unit ? ` ${unit}` : ''}`;
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return `${String(value)}${unit ? ` ${unit}` : ''}`;
}

export function getPropertyGroups(payload: unknown): PropertyGroupVM[] {
  const groups = (payload as { property_groups?: PropertyGroupVM[] } | null)?.property_groups;
  return Array.isArray(groups) ? groups : [];
}

export function findGroupInList(groups: PropertyGroupVM[], key: string): PropertyGroupVM | null {
  const alias: Record<string, string> = {
    thermo: 'thermodynamic',
    electronic_structure: 'electronic',
    magnetism: 'magnetic',
    elasticity: 'mechanical',
    surfaces: 'surface',
  };
  const normalized = alias[key] || key;
  return groups.find((group) => group.key === normalized || group.key === key) || null;
}

export function findPropertyGroup(payload: unknown, key: string): PropertyGroupVM | null {
  return findGroupInList(getPropertyGroups(payload), key);
}

export function compactValue(value: unknown): string {
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  return text.length > 42 ? `${text.slice(0, 42)}...` : text;
}

export function renderMetric(item: PropertyMetricVM): string {
  if (item.available === false || item.value === null || item.value === undefined || item.value === '') return '-';
  const raw = item.value;
  if (Array.isArray(raw)) return raw.length ? raw.slice(0, 3).map(compactValue).join(', ') : '-';
  if (typeof raw === 'object') return compactValue(raw);
  return formatValue(raw, item.unit || '');
}

export function metricNumber(item: Partial<PropertyMetricVM>): number {
  if (item.value === null || item.value === undefined || typeof item.value === 'boolean') return Number.NaN;
  if (typeof item.value === 'number') return item.value;
  if (typeof item.value === 'string') {
    const n = Number(item.value.replace(/[^0-9.+-]/g, ''));
    return Number.isFinite(n) ? n : Number.NaN;
  }
  return Number.NaN;
}

export function labelize(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

export function countActiveFilters(filters: SearchFilters): number {
  return Object.entries(filters).reduce((count, [key, value]) => {
    if (key === 'stable' || key === 'metal' || key === 'magnetic') return count + (value !== 'any' ? 1 : 0);
    return count + (value ? 1 : 0);
  }, 0);
}

export function compactSearchFilters(filters: SearchFilters): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (filters.stable === 'stable') out.stable = true;
  if (filters.metal === 'metal') out.metal = true;
  if (filters.metal === 'non_metal') out.metal = false;
  if (filters.magnetic === 'magnetic') out.magnetic = true;
  if (filters.magnetic === 'non_magnetic') out.magnetic = false;
  for (const key of ['band_gap_min', 'band_gap_max', 'density_min', 'density_max'] as const) {
    if (!filters[key].trim()) continue;
    const value = Number(filters[key]);
    if (Number.isFinite(value)) out[key] = value;
  }
  if (filters.elements.trim()) out.elements = filters.elements.trim();
  if (filters.evidence) out.evidence = filters.evidence;
  return out;
}

export function fallbackCompareItems(material: Record<string, unknown>, groupKey: string): PropertyMetricVM[] {
  const pairs: Record<string, Array<[string, string, string?]>> = {
    key: [
      ['Formula', 'formula_pretty'],
      ['Chemical system', 'chemsys'],
      ['Stable', 'is_stable'],
      ['Band gap', 'band_gap', 'eV'],
      ['Energy above hull', 'energy_above_hull', 'eV/atom'],
      ['Formation energy', 'formation_energy_per_atom', 'eV/atom'],
      ['Density', 'density', 'g/cm3'],
      ['Evidence sections', 'evidence_sections'],
    ],
    thermodynamic: [
      ['Energy above hull', 'energy_above_hull', 'eV/atom'],
      ['Formation energy', 'formation_energy_per_atom', 'eV/atom'],
      ['Energy per atom', 'energy_per_atom', 'eV'],
    ],
    electronic: [
      ['Band gap', 'band_gap', 'eV'],
      ['Direct gap', 'is_gap_direct'],
      ['Metal', 'is_metal'],
    ],
    magnetic: [
      ['Magnetic', 'is_magnetic'],
      ['Ordering', 'ordering'],
      ['Total magnetization', 'total_magnetization', 'muB'],
    ],
    mechanical: [
      ['Bulk modulus VRH', 'bulk_modulus_vrh', 'GPa'],
      ['Shear modulus VRH', 'shear_modulus_vrh', 'GPa'],
    ],
  };
  return (pairs[groupKey] || []).map(([label, key, unit]) => ({
    label,
    value: material[key] as PropertyMetricVM['value'],
    unit,
    source: 'compare',
    available: material[key] !== null && material[key] !== undefined && material[key] !== '',
  }));
}

export function getCompareRows(
  materials: Array<Record<string, unknown>>,
  groupKey: string,
): Array<{ label: string; values: Record<string, PropertyMetricVM>; max: number }> {
  const rows = new Map<string, { label: string; values: Record<string, PropertyMetricVM>; max: number }>();
  for (const material of materials) {
    const materialId = String(material.material_id);
    const groups = Array.isArray(material.property_groups) ? (material.property_groups as PropertyGroupVM[]) : [];
    const group = findGroupInList(groups, groupKey);
    const items = group?.items?.length ? group.items : fallbackCompareItems(material, groupKey);
    for (const item of items) {
      const current = rows.get(item.label) || { label: item.label, values: {}, max: 0 };
      current.values[materialId] = item;
      const n = Math.abs(metricNumber(item));
      if (Number.isFinite(n)) current.max = Math.max(current.max, n);
      rows.set(item.label, current);
    }
  }
  return Array.from(rows.values()).filter((row) =>
    Object.values(row.values).some((item) => item.available !== false && item.value !== null && item.value !== undefined && item.value !== ''),
  );
}
