import { Bot } from 'lucide-react';
import { GraphCanvas } from '@/components/graph/GraphCanvas';
import { GraphControls } from '@/components/graph/GraphControls';

export function GraphMode({ openAgent, showAgentButton = true }: { openAgent: () => void; showAgentButton?: boolean }) {
  return (
    <section className="relative min-w-0 flex-1" style={{ background: 'var(--cat-bg)' }}>
      <GraphCanvas />
      <GraphControls />
      {showAgentButton ? <button
        type="button"
        onClick={openAgent}
        className="jarvis-graph-agent-button"
        title="Open agent"
      >
        <Bot className="h-5 w-5" />
      </button> : null}
    </section>
  );
}
