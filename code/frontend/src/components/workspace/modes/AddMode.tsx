import { Paperclip, Send } from 'lucide-react';

export function AddMode({
  prompt,
  setPrompt,
  mode,
  setMode,
  loading,
  onQueue,
  onAsk,
}: {
  prompt: string;
  setPrompt: (value: string) => void;
  mode: 'chat' | 'task' | 'research';
  setMode: (mode: 'chat' | 'task' | 'research') => void;
  loading: boolean;
  onQueue: () => void | Promise<void>;
  onAsk: () => void;
}) {
  return (
    <section className="no-scrollbar min-w-0 flex-1 overflow-auto p-5 pb-28" style={{ background: 'var(--cat-bg)' }}>
      <div className="mx-auto grid max-w-6xl gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="rounded-2xl border p-6" style={{ borderColor: 'var(--cat-border)', background: 'var(--cat-surface-1)' }}>
          <h1 className="text-2xl font-semibold">Add material evidence</h1>
          <p className="mt-2 text-sm" style={{ color: 'var(--cat-text-3)' }}>
            Queue research or ask the agent to normalize a candidate.
          </p>
          <div className="mt-4 flex gap-2">
            {(['chat', 'task', 'research'] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setMode(item)}
                className="rounded-xl px-3 py-1.5 text-sm capitalize"
                style={{
                  background: mode === item ? 'var(--cat-accent-muted)' : 'var(--cat-surface-2)',
                  color: mode === item ? 'var(--cat-accent)' : 'var(--cat-text-2)',
                }}
              >
                {item}
              </button>
            ))}
          </div>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="mt-4 min-h-[280px] w-full resize-none rounded-2xl border p-4 text-sm outline-none"
            style={{ borderColor: 'var(--cat-border)', background: 'var(--cat-surface-2)', color: 'var(--cat-text-1)' }}
            placeholder="Describe the material, paste a source URL, or summarize evidence."
          />
          <div className="mt-3 flex items-center justify-between">
            <button type="button" className="inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm" style={{ borderColor: 'var(--cat-border)' }}>
              <Paperclip className="h-4 w-4" /> Attach
            </button>
            <div className="flex gap-2">
              <button type="button" onClick={onAsk} className="inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm" style={{ borderColor: 'var(--cat-border)' }}>
                <Send className="h-4 w-4" /> Chat
              </button>
              <button type="button" onClick={onQueue} disabled={loading} className="rounded-xl px-4 py-2 text-sm disabled:opacity-50" style={{ background: 'var(--cat-accent)', color: 'var(--cat-bg)' }}>
                {loading ? 'Queueing' : 'Queue research'}
              </button>
            </div>
          </div>
        </div>
        <div className="rounded-2xl border p-5" style={{ borderColor: 'var(--cat-border)', background: 'var(--cat-surface-1)' }}>
          <h2 className="text-lg font-semibold">Research run</h2>
          <div className="mt-4 rounded-xl border p-3 text-sm" style={{ borderColor: 'var(--cat-border)', background: 'var(--cat-surface-2)', color: 'var(--cat-text-3)' }}>
            Pending runs appear here when available.
          </div>
        </div>
      </div>
    </section>
  );
}
