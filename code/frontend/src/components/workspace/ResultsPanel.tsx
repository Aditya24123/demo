import type { CandidateRowVM } from '@/catalyst/bridge/viewModels';
import { JarvisRawIcon } from './JarvisIcons';
import { formatValue } from './utils';

export function ResultsPanel({
  results,
  onOpenMaterial,
  onClose,
  selectedId,
}: {
  results: CandidateRowVM[];
  onOpenMaterial: (id: string) => void;
  onClose: () => void;
  selectedId: string | null;
}) {
  return (
    <aside className="min-h-0 border-r p-3" style={{ borderColor: 'var(--cat-border)', background: 'var(--cat-surface-1)' }}>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Results</h2>
          <span className="rounded-full px-2 py-0.5 text-xs" style={{ background: 'var(--cat-surface-2)', color: 'var(--cat-text-2)' }}>
            {results.length}
          </span>
        </div>
        <button type="button" title="Close results" onClick={onClose} className="jarvis-icon-tool" aria-label="Close results">
          <JarvisRawIcon name="panel" className="h-5 w-5" />
        </button>
      </div>
      <div className="no-scrollbar max-h-[calc(100vh-72px)] overflow-auto pr-1">
        {results.slice(0, 24).map((row, index) => {
          const selected = row.material_id === selectedId;
          return (
            <button
              key={row.material_id}
              type="button"
              onClick={() => onOpenMaterial(row.material_id)}
              className="mb-1.5 grid w-full grid-cols-[22px_1fr] items-start rounded-xl border px-3 py-2.5 text-left transition"
              style={{
                borderColor: selected ? 'var(--cat-accent)' : 'var(--cat-border-subtle)',
                borderLeftWidth: selected ? 3 : 1,
                background: selected ? 'var(--cat-accent-subtle)' : 'transparent',
                color: 'var(--cat-text-1)',
              }}
            >
              <span className="text-xs" style={{ color: selected ? 'var(--cat-accent)' : 'var(--cat-text-3)' }}>
                {index + 1}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold">{row.formula_pretty || row.material_id}</span>
                <span className="mt-0.5 block font-mono text-[11px]" style={{ color: 'var(--cat-text-3)' }}>
                  {row.material_id}
                </span>
                <span className="mt-1 block text-xs" style={{ color: 'var(--cat-text-2)' }}>
                  Eg {formatValue(row.band_gap, 'eV')} ? {row.is_stable ? 'stable' : 'unstable'}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
