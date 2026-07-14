/** Live agent activity shimmer + markdown heading helpers. */

/** Shimmer status while the agent runs ? tool steps or the latest markdown section heading. */
export function ActivityLine({ label }: { label: string }) {
  return (
    <div className="jarvis-thinking" aria-live="polite" aria-atomic="true">
      <span className="jarvis-thinking-shimmer">{label}</span>
      <span className="jarvis-thinking-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
    </div>
  );
}

/** Last ATX heading in partial markdown (## Section ? "Section"). */
export function latestMarkdownHeading(text: string): string | null {
  if (!text) return null;
  const re = /^(#{1,6})\s+(.+?)\s*$/gm;
  let last: string | null = null;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    const title = match[2].replace(/\s+#+\s*$/, '').trim();
    if (title) last = title;
  }
  return last;
}
