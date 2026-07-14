import { useCallback, useEffect, useRef, useState } from 'react';
import { Bookmark, BookmarkCheck } from 'lucide-react';
import type { WorkspaceVM } from '@/catalyst/bridge/viewModels';
import type { HomeTab } from './types';
import { JarvisRawIcon } from './JarvisIcons';

const WORKSPACE_TABS: Array<{ id: HomeTab; label: string }> = [
  { id: 'structure', label: 'Structure' },
  { id: 'neighbors', label: 'Neighbors' },
  { id: 'spectra', label: 'Spectra' },
];

type MaterialHeaderProps = {
  workspace: WorkspaceVM;
  activeTab: HomeTab;
  setActiveTab: (tab: HomeTab) => void;
  hopDepth: number;
  setHopDepth: (depth: number) => void;
  isCandidate: boolean;
  addCandidate: (workspace: WorkspaceVM) => void;
  removeCandidate: (materialId: string) => void;
  resultsOpen: boolean;
  resultsAvailable: boolean;
  onToggleResults: () => void;
  inspectorOpen: boolean;
  onToggleInspector: () => void;
};

export function MaterialHeader({
  workspace,
  activeTab,
  setActiveTab,
  hopDepth,
  setHopDepth,
  isCandidate,
  addCandidate,
  removeCandidate,
  resultsOpen,
  resultsAvailable,
  onToggleResults,
  inspectorOpen,
  onToggleInspector,
}: MaterialHeaderProps) {
  const hopDepthRef = useRef(hopDepth);
  hopDepthRef.current = hopDepth;
  // Callback ref so wheel binds after the chip mounts (workspace-gated render).
  const [hopEl, setHopEl] = useState<HTMLButtonElement | null>(null);

  const nudgeHop = useCallback(
    (delta: number) => {
      const next = Math.max(1, Math.min(5, hopDepthRef.current + delta));
      if (next === hopDepthRef.current) return;
      hopDepthRef.current = next;
      setHopDepth(next);
    },
    [setHopDepth],
  );

  useEffect(() => {
    if (!hopEl) return undefined;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();
      if (event.deltaY === 0 && event.deltaX === 0) return;
      nudgeHop(event.deltaY < 0 || event.deltaX < 0 ? 1 : -1);
    };
    hopEl.addEventListener('wheel', onWheel, { passive: false });
    return () => hopEl.removeEventListener('wheel', onWheel);
  }, [hopEl, nudgeHop]);

  return (
    <div className="jarvis-material-header">
      {/* Row 1: title | tabs | tools ? single baseline so tabs don't sit above the chips. */}
      <div className="jarvis-material-title-row min-w-0">
        <h1 className="jarvis-material-title truncate">{workspace.title}</h1>
        {isCandidate ? <span className="jarvis-status-pill">In candidates</span> : null}
      </div>

      <div className="jarvis-workspace-tabs jarvis-workspace-tabs-center" role="tablist" aria-label="Material views">
        {WORKSPACE_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={activeTab === tab.id ? 'jarvis-workspace-tab active' : 'jarvis-workspace-tab'}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="jarvis-material-header-right">
        <div className="jarvis-workspace-actions">
          {resultsAvailable ? (
            <button
              type="button"
              onClick={onToggleResults}
              className={resultsOpen ? 'jarvis-icon-tool active' : 'jarvis-icon-tool'}
              title={resultsOpen ? 'Hide results' : 'Show results'}
              aria-label={resultsOpen ? 'Hide results' : 'Show results'}
            >
              {/* Same panel glyph as left-rail collapse for continuity. */}
              <JarvisRawIcon name="panel" className="h-5 w-5" />
            </button>
          ) : null}

          <button
            type="button"
            onClick={() => (isCandidate ? removeCandidate(workspace.resolvedMaterialId) : addCandidate(workspace))}
            className={isCandidate ? 'jarvis-icon-tool active' : 'jarvis-icon-tool'}
            title={isCandidate ? 'Remove from candidates' : 'Add to candidates'}
            aria-label={isCandidate ? 'Remove from candidates' : 'Add to candidates'}
          >
            {isCandidate ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
          </button>

          <button
            ref={setHopEl}
            type="button"
            className="jarvis-hop-chip"
            title="Hop depth ? scroll or click (1?5)"
            aria-label={`Hop depth ${hopDepth}. Scroll to change.`}
            onClick={() => setHopDepth(hopDepth >= 5 ? 1 : hopDepth + 1)}
          >
            <span className="jarvis-hop-label">hops</span>
            <span className="jarvis-hop-value">{hopDepth}</span>
          </button>
        </div>

        <button
          type="button"
          onClick={onToggleInspector}
          className={inspectorOpen ? 'jarvis-inspector-toggle active' : 'jarvis-inspector-toggle'}
          title={inspectorOpen ? 'Collapse inspector' : 'Open inspector'}
          aria-label={inspectorOpen ? 'Collapse inspector' : 'Open inspector'}
        >
          <JarvisRawIcon name="panel" className="jarvis-panel-icon-rtl" />
        </button>
      </div>

      {/* Row 2: id under title only */}
      <div className="jarvis-material-id">{workspace.resolvedMaterialId}</div>
    </div>
  );
}
