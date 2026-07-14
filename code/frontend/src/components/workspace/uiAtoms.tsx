import type { ReactNode } from 'react';

export function Badge({ children, tone }: { children: ReactNode; tone: 'good' | 'warn' | 'muted' }) {
  const color = tone === 'good' ? 'var(--accent)' : tone === 'warn' ? 'var(--warning)' : 'var(--text-3)';
  const background = tone === 'good' ? 'var(--accent-muted)' : tone === 'warn' ? 'rgba(240,195,106,0.18)' : 'var(--surface-2)';
  return (
    <span className="inline-flex rounded-xl px-3 py-1 text-sm" style={{ background, color }}>
      {children}
    </span>
  );
}

export function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-3 w-3 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

export function StatePanel({ title, text, danger = false }: { title: string; text?: string; danger?: boolean }) {
  return (
    <div
      className="flex h-full min-h-[360px] items-center justify-center rounded-2xl border text-center"
      style={{ borderColor: 'var(--border)', background: 'var(--surface-1)', color: danger ? 'var(--danger)' : 'var(--text-2)' }}
    >
      <div>
        <div className="text-xl font-semibold">{title}</div>
        {text ? (
          <p className="mt-2 text-base" style={{ color: 'var(--text-3)' }}>
            {text}
          </p>
        ) : null}
      </div>
    </div>
  );
}

export function OfflinePanel({ startupError, onRetry }: { startupError: string | null; onRetry: () => void }) {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center rounded-[22px] border" style={{ borderColor: 'var(--border)', background: 'var(--surface-1)' }}>
      <div className="max-w-md text-center">
        <div className="text-2xl font-semibold" style={{ color: 'var(--danger)' }}>
          Backend offline
        </div>
        <p className="mt-3" style={{ color: 'var(--text-3)' }}>
          {startupError || 'Unable to reach the Catalyst backend.'}
        </p>
        <button onClick={onRetry} className="mt-5 rounded-xl px-5 py-2" style={{ background: 'var(--accent)', color: 'var(--bg)' }}>
          Retry
        </button>
      </div>
    </div>
  );
}

export function MetricList({ rows, compact = false }: { rows: Array<[string, string]>; compact?: boolean }) {
  return (
    <div className={compact ? 'mt-3 space-y-1.5' : 'mt-4 space-y-2'}>
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-center justify-between gap-3 text-sm">
          <span style={{ color: 'var(--text-3)' }}>{label}</span>
          <span className="font-mono" style={{ color: 'var(--text-1)' }}>
            {value}
          </span>
        </div>
      ))}
    </div>
  );
}

export function SettingsBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border p-5" style={{ borderColor: 'var(--border)', background: 'var(--surface-1)' }}>
      <h2 className="mb-4 text-lg font-semibold">{title}</h2>
      {children}
    </div>
  );
}
