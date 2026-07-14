import { SettingsBlock } from '../uiAtoms';

export function SettingsMode({
  status,
  backendUrl,
  isOffline,
  theme,
  setTheme,
  density,
  setDensity,
  hopDepth,
  setHopDepth,
  rawSettings,
}: {
  status: any;
  backendUrl: string;
  isOffline: boolean;
  theme: 'dark' | 'light';
  setTheme: (theme: 'dark' | 'light') => void;
  density: string;
  setDensity: (density: any) => void;
  hopDepth: number;
  setHopDepth: (depth: number) => void;
  rawSettings: any;
}) {
  return (
    <section className="no-scrollbar min-w-0 flex-1 overflow-auto p-5 pb-28" style={{ background: 'var(--cat-bg)' }}>
      <div className="mx-auto grid max-w-4xl gap-4">
        <SettingsBlock title="Runtime">
          <div className="space-y-2 text-sm">
            <Row label="Backend" value={backendUrl || '?'} />
            <Row label="Status" value={isOffline ? 'offline' : status?.status || 'ok'} />
            <Row label="Provider" value={status?.provider?.activeProvider || 'not configured'} />
          </div>
        </SettingsBlock>
        <SettingsBlock title="Appearance">
          <div className="flex flex-wrap gap-2">
            {(['dark', 'light'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTheme(t)}
                className="rounded-xl px-3 py-1.5 text-sm capitalize"
                style={{
                  background: theme === t ? 'var(--cat-accent-muted)' : 'var(--cat-surface-2)',
                  color: theme === t ? 'var(--cat-accent)' : 'var(--cat-text-2)',
                }}
              >
                {t}
              </button>
            ))}
            {(['comfortable', 'compact'] as const).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDensity(d)}
                className="rounded-xl px-3 py-1.5 text-sm capitalize"
                style={{
                  background: density === d ? 'var(--cat-accent-muted)' : 'var(--cat-surface-2)',
                  color: density === d ? 'var(--cat-accent)' : 'var(--cat-text-2)',
                }}
              >
                {d}
              </button>
            ))}
          </div>
        </SettingsBlock>
        <SettingsBlock title="Graph">
          <label className="block text-sm" style={{ color: 'var(--cat-text-3)' }}>
            Default hop depth
            <select
              className="mt-1 h-10 w-full rounded-xl border px-3 text-sm outline-none"
              style={{ borderColor: 'var(--cat-border)', background: 'var(--cat-surface-2)', color: 'var(--cat-text-1)' }}
              value={hopDepth}
              onChange={(e) => setHopDepth(Number(e.target.value))}
            >
              {[1, 2, 3, 4, 5].map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
        </SettingsBlock>
        <SettingsBlock title="Settings payload">
          <pre className="no-scrollbar max-h-48 overflow-auto rounded-xl border p-3 text-xs" style={{ borderColor: 'var(--cat-border)', background: 'var(--cat-surface-2)', color: 'var(--cat-text-2)' }}>
            {JSON.stringify(rawSettings || {}, null, 2)}
          </pre>
        </SettingsBlock>
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span style={{ color: 'var(--cat-text-3)' }}>{label}</span>
      <span className="truncate font-mono text-xs" style={{ color: 'var(--cat-text-1)' }}>
        {value}
      </span>
    </div>
  );
}
