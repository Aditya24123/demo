import type { PropertyGroupVM, PropertyMetricVM, WorkspaceVM } from '@/catalyst/bridge/viewModels';
import { metricNumber, renderMetric } from './utils';

function isAvailable(item: PropertyMetricVM): boolean {
  if (item.available === false) return false;
  if (item.value === null || item.value === undefined || item.value === '') return false;
  if (item.value === '-') return false;
  // Hide ugly raw JSON dumps like decomposes_to objects unless short.
  if (typeof item.value === 'object' && !Array.isArray(item.value)) {
    const text = JSON.stringify(item.value);
    if (text.length > 48) return false;
  }
  return true;
}

export function PropertyGroupTab({ group, label }: { group?: PropertyGroupVM | null; label: string }) {
  const items = (group?.items || []).filter(isAvailable);
  if (!items.length) return <EmptyGroupState label={label} />;
  const numericMax = Math.max(
    0,
    ...items.map((item) => Math.abs(metricNumber(item))).filter((value) => Number.isFinite(value)),
  );
  return (
    <div className="space-y-2">
      <div className="jarvis-property-group-header">
        <div className="text-sm font-semibold">{group?.label || label}</div>
      </div>
      {items.map((item) => (
        <MetricValueRow key={item.label} item={item} max={numericMax} />
      ))}
    </div>
  );
}

function MetricValueRow({ item, max }: { item: PropertyMetricVM; max: number }) {
  const numeric = metricNumber(item);
  const hasBar = Number.isFinite(numeric) && max > 0;
  const valueText = renderMetric(item);
  const longValue = typeof valueText === 'string' && valueText.length > 42;
  return (
    <div className="jarvis-property-metric-row">
      <div className={`jarvis-property-metric-main ${longValue ? 'jarvis-property-metric-main-stack' : ''}`}>
        <div className="jarvis-property-metric-label" style={{ color: 'var(--cat-text-1)' }}>
          {item.label}
        </div>
        <div
          className={`jarvis-property-metric-value ${longValue ? 'jarvis-property-metric-value-long' : ''}`}
          style={{ color: 'var(--cat-text-1)' }}
          title={typeof valueText === 'string' ? valueText : undefined}
        >
          {valueText}
        </div>
      </div>
      {hasBar ? (
        <div className="mt-2 h-1 overflow-hidden rounded-full" style={{ background: 'var(--cat-surface-3)' }}>
          <div
            className="h-full rounded-full"
            style={{
              width: `${Math.max(6, Math.min(100, (Math.abs(numeric) / max) * 100))}%`,
              background: numeric < 0 ? 'var(--cat-chart-violet)' : 'var(--cat-accent)',
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

export function EmptyGroupState({ label, compactText }: { label: string; compactText?: string }) {
  return (
    <div className="flex min-h-[180px] items-center justify-center text-center">
      <div className="max-w-xs">
        <div className="text-sm font-semibold">{compactText ? label : `No ${label.toLowerCase()} available.`}</div>
        <p className="mt-2 text-xs" style={{ color: 'var(--cat-text-3)' }}>
          {compactText || 'Only properties present for this material are shown.'}
        </p>
      </div>
    </div>
  );
}

// Kept for other callers; key properties block removed from main inspector UI.
export function KeyPropertyBlock({
  group,
  workspace,
}: {
  group?: PropertyGroupVM | null;
  workspace: WorkspaceVM;
  evidenceSections?: number;
  evidenceRecords?: number;
}) {
  const rows = (group?.items || []).filter(isAvailable).slice(0, 8);
  const fallbackRows: PropertyMetricVM[] = workspace.metrics
    .filter((metric) => metric.value !== null && metric.value !== undefined)
    .slice(0, 7)
    .map((metric) => ({
      label: metric.label,
      value: metric.value,
      unit: metric.unit,
      available: true,
    }));
  const items = rows.length ? rows : fallbackRows;
  if (!items.length) return null;
  return (
    <div className="jarvis-key-properties">
      <div className="jarvis-key-properties-grid">
        {items.map((item) => (
          <div key={item.label} className="min-w-0">
            <div className="jarvis-property-label truncate">{item.label}</div>
            <div className="jarvis-property-value truncate">{renderMetric(item)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
