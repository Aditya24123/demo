import { useState } from 'react';
import type { CandidateRowVM, CompareVM, PropertyMetricVM } from '@/catalyst/bridge/viewModels';
import { COMPARE_TABS } from '../constants';
import { formatValue, getCompareRows, metricNumber, renderMetric } from '../utils';
import { EmptyGroupState } from '../PropertyPanels';
import { MetricList, StatePanel } from '../uiAtoms';

export function CandidatesMode({
  candidates,
  canCompare,
  canExport,
  compareData,
  compareLoading,
  onCompare,
  onRemove,
  onExportJson,
  onExportCsv,
  onExportSubgraph,
}: {
  candidates: CandidateRowVM[];
  canCompare: boolean;
  canExport: boolean;
  compareData: any;
  compareLoading: boolean;
  onCompare: () => void;
  onRemove: (materialId: string) => void;
  onExportJson: () => void;
  onExportCsv: () => void;
  onExportSubgraph: () => void;
}) {
  const [activeCompareTab, setActiveCompareTab] = useState<(typeof COMPARE_TABS)[number]['id']>('key');
  return (
    <section className="no-scrollbar min-w-0 flex-1 overflow-auto p-5 pb-28" style={{ background: 'var(--cat-bg)' }}>
      <div className="mx-auto max-w-7xl rounded-2xl border p-6" style={{ borderColor: 'var(--cat-border)', background: 'var(--cat-surface-1)' }}>
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">Candidates</h1>
            <p className="mt-1 text-sm" style={{ color: 'var(--cat-text-3)' }}>
              Compare and export grounded local evidence.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={!canCompare || compareLoading} onClick={onCompare} className="rounded-xl px-4 py-2 text-sm disabled:opacity-50" style={{ background: 'var(--cat-accent)', color: 'var(--cat-bg)' }}>
              {compareLoading ? 'Comparing' : 'Compare'}
            </button>
            <button type="button" disabled={!canExport} onClick={onExportJson} className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50" style={{ borderColor: 'var(--cat-border)' }}>
              JSON
            </button>
            <button type="button" disabled={!canExport} onClick={onExportCsv} className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50" style={{ borderColor: 'var(--cat-border)' }}>
              CSV
            </button>
            <button type="button" disabled={!canExport} onClick={onExportSubgraph} className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50" style={{ borderColor: 'var(--cat-border)' }}>
              Subgraph
            </button>
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {candidates.length ? (
            candidates.map((candidate) => (
              <div key={candidate.material_id} className="rounded-2xl border p-4" style={{ borderColor: 'var(--cat-border)' }}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-lg font-semibold">{candidate.formula_pretty}</div>
                    <div className="font-mono text-xs" style={{ color: 'var(--cat-text-3)' }}>
                      {candidate.material_id}
                    </div>
                  </div>
                  <button type="button" onClick={() => onRemove(candidate.material_id)} className="text-xs" style={{ color: 'var(--cat-text-3)' }}>
                    remove
                  </button>
                </div>
                <MetricList
                  compact
                  rows={[
                    ['Band gap', formatValue(candidate.band_gap, 'eV')],
                    ['Hull', formatValue(candidate.energy_above_hull, 'eV/atom')],
                    ['Density', formatValue(candidate.density, 'g/cm3')],
                  ]}
                />
              </div>
            ))
          ) : (
            <StatePanel title="No candidates selected" text="Add candidates from Home to compare and export." />
          )}
        </div>
        {compareData?.materials?.length ? (
          <CompareBlock compareData={compareData as CompareVM} activeTab={activeCompareTab} setActiveTab={setActiveCompareTab} />
        ) : null}
      </div>
    </section>
  );
}

function CompareBlock({
  compareData,
  activeTab,
  setActiveTab,
}: {
  compareData: CompareVM;
  activeTab: (typeof COMPARE_TABS)[number]['id'];
  setActiveTab: (tab: (typeof COMPARE_TABS)[number]['id']) => void;
}) {
  const materials = (compareData.materials || []) as Array<Record<string, any>>;
  const rows = getCompareRows(materials, activeTab);
  return (
    <div className="mt-5 rounded-2xl border p-3" style={{ borderColor: 'var(--cat-border)', background: 'var(--cat-surface-2)' }}>
      <div className="no-scrollbar mb-3 flex gap-1 overflow-x-auto rounded-xl border p-1" style={{ borderColor: 'var(--cat-border-subtle)', background: 'var(--cat-surface-1)' }}>
        {COMPARE_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className="shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium"
            style={{
              background: activeTab === tab.id ? 'var(--cat-accent-muted)' : 'transparent',
              color: activeTab === tab.id ? 'var(--cat-accent)' : 'var(--cat-text-2)',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {!rows.length ? (
        <EmptyGroupState label={COMPARE_TABS.find((t) => t.id === activeTab)?.label || activeTab} />
      ) : (
        <div className="no-scrollbar overflow-auto">
          <table className="w-full min-w-[720px] border-separate border-spacing-0 text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 border-b px-3 py-2 text-left" style={{ borderColor: 'var(--cat-border)', background: 'var(--cat-surface-2)' }}>
                  Metric
                </th>
                {materials.map((m) => (
                  <th key={String(m.material_id)} className="border-b px-3 py-2 text-left" style={{ borderColor: 'var(--cat-border)' }}>
                    {m.formula_pretty || m.material_id}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label}>
                  <td className="sticky left-0 border-b px-3 py-2 font-medium" style={{ borderColor: 'var(--cat-border-subtle)', background: 'var(--cat-surface-2)' }}>
                    {row.label}
                  </td>
                  {materials.map((m) => {
                    const cell = row.values[String(m.material_id)] as PropertyMetricVM | undefined;
                    const numeric = metricNumber(cell || {});
                    return (
                      <td key={`${row.label}-${m.material_id}`} className="border-b px-3 py-2 font-mono" style={{ borderColor: 'var(--cat-border-subtle)' }}>
                        {cell ? renderMetric(cell) : '-'}
                        {cell && Number.isFinite(numeric) && row.max > 0 ? (
                          <div className="mt-1 h-1 overflow-hidden rounded-full" style={{ background: 'var(--cat-surface-3)' }}>
                            <div className="h-full rounded-full" style={{ width: `${Math.max(6, Math.min(100, (Math.abs(numeric) / row.max) * 100))}%`, background: 'var(--cat-accent)' }} />
                          </div>
                        ) : null}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
