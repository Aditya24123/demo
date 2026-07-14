import type { Structure3DVM } from '@/catalyst/bridge/viewModels';

type StructureMetricsProps = {
  structure: Structure3DVM | null;
  floating?: boolean;
};

export function StructureMetrics({ structure, floating = false }: StructureMetricsProps) {
  if (!structure) return null;
  const symmetry = structure.symmetry || {};
  const items = [
    { label: 'Sites', value: String(structure.nsites ?? structure.sites.length ?? 0) },
    { label: 'Density', value: formatNumber(structure.density, 'g/cm?') },
    { label: 'Volume', value: formatNumber(structure.volume, '??') },
    {
      label: 'Space group',
      value: String((symmetry as Record<string, unknown>).symbol || (symmetry as Record<string, unknown>).number || '?'),
    },
  ];

  if (floating) {
    return (
      <div className="jarvis-structure-metrics-float">
        {items.map((item) => (
          <div key={item.label} className="jarvis-structure-metrics-float-row">
            <span>{item.label}</span>
            <strong className="font-mono">{item.value}</strong>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded-md border px-2 py-1.5" style={{ borderColor: 'var(--border)', background: 'var(--surface-1)' }}>
          <div style={{ color: 'var(--text-4)' }}>{item.label}</div>
          <div className="mt-0.5 font-mono text-[11px]" style={{ color: 'var(--text-2)' }}>
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}

function formatNumber(value: unknown, unit: string): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return '?';
  const rendered = n >= 10 ? n.toFixed(2) : n.toFixed(3);
  return `${rendered} ${unit}`;
}
