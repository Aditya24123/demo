import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { useAppStore } from '@/catalyst/ui-state/appStore';
import {
  useCatalystAgent,
  useCatalystCandidates,
  useCatalystGraph,
  useCatalystLayout,
  useCatalystMaterialData,
  useCatalystResearch,
  useCatalystSearch,
  useCatalystSettings,
  useCatalystStatus,
  useCatalystWorkspace,
} from '@/catalyst/bridge/hooks';
import { EdgeSheet } from '@/components/evidence/EdgeSheet';
import { EVIDENCE_SECTIONS, PROPERTY_SECTIONS, SPECTRA_SECTIONS } from './constants';
import { HomeWorkspace } from './HomeWorkspace';
import { WorkspaceRail } from './WorkspaceRail';
import './JarvisShell.css';
import { CandidatesMode } from './modes/CandidatesMode';
import { AddMode } from './modes/AddMode';
import { GenesMode } from './modes/GenesMode';
import { SettingsMode } from './modes/SettingsMode';
import { type HomeTab, type RailMode } from './types';
import { detailCacheKey, hopLimitNodes } from './utils';
import { DemoNarrationAudio } from './DemoNarrationAudio';

const GraphMode = lazy(() => import('./modes/GraphMode').then((module) => ({ default: module.GraphMode })));
const NotebookMode = lazy(() => import('./modes/NotebookMode').then((module) => ({ default: module.NotebookMode })));
const ContextInspector = lazy(() =>
  import('./ContextInspector').then((module) => ({ default: module.ContextInspector })),
);

export function WorkspaceShell() {
  const initialize = useAppStore((s) => s.initialize);
  const { status, backendUrl, isOffline, startupError, retry } = useCatalystStatus();
  const { workspace, isLoading: workspaceLoading, error: workspaceError } = useCatalystWorkspace();
  const {
    railMode,
    setRailMode,
    workspaceTab,
    setWorkspaceTab,
    hopDepth,
    setHopDepth,
    inspectorOpen,
    setInspectorOpen,
    inspectorTab,
    setInspectorTab,
    theme,
    setTheme,
    density,
    setDensity,
  } = useCatalystLayout();
  const { results, screenResults } = useCatalystSearch();
  const { sendMessage } = useCatalystAgent();
  const { runResearch } = useCatalystResearch();
  const { nodes: graphNodes, edges: graphEdges, selectNode, expandNeighborhood } = useCatalystGraph();
  const {
    candidates,
    canCompare,
    canExport,
    runCompare,
    compareData,
    compareLoading,
    addCandidate,
    removeCandidate,
    exportCandidates,
    exportSubgraph,
  } = useCatalystCandidates();
  const { rawSettings } = useCatalystSettings();
  const {
    structureById,
    detailsById,
    structureLoadingById,
    detailsLoadingById,
    structureErrorById,
    detailsErrorById,
    loadMaterialStructure,
    loadMaterialDetails,
  } = useCatalystMaterialData();

  const [resultsOpen, setResultsOpen] = useState(true);
  const [researchPrompt, setResearchPrompt] = useState('');
  const [researchMode, setResearchMode] = useState<'chat' | 'task' | 'research'>('research');
  const [researchQueueing, setResearchQueueing] = useState(false);

  const activeMaterialId = workspace?.resolvedMaterialId || null;
  const activeTab = (workspaceTab === 'neighbors' || workspaceTab === 'structure' || workspaceTab === 'spectra' ? workspaceTab : 'structure') as HomeTab;
  const selectedCandidateIds = useMemo(() => new Set(candidates.map((c) => c.material_id)), [candidates]);

  const propertyKey = activeMaterialId ? detailCacheKey(activeMaterialId, [...PROPERTY_SECTIONS], 8, true) : '';
  // Match prefetch limit (8) so spectra share the warm cache instead of missing on limit=4.
  const spectraKey = activeMaterialId ? detailCacheKey(activeMaterialId, [...SPECTRA_SECTIONS], 8, true) : '';
  const evidenceKey = activeMaterialId ? detailCacheKey(activeMaterialId, [...EVIDENCE_SECTIONS], 8, true) : '';
  const propertyDetails = propertyKey ? detailsById[propertyKey] || null : null;
  // Fall back to property payload spectra if dedicated spectra key not warm yet.
  const spectraDetails =
    (spectraKey ? detailsById[spectraKey] : null) ||
    (propertyDetails && (propertyDetails as any)?.details?.spectra ? propertyDetails : null) ||
    null;
  const evidenceDetails = evidenceKey ? detailsById[evidenceKey] || null : null;
  const structurePayload = activeMaterialId ? structureById[activeMaterialId] || null : null;
  const structureLoading = !!(activeMaterialId && structureLoadingById[activeMaterialId]);
  const structureError = activeMaterialId ? structureErrorById[activeMaterialId] : null;
  const propertyError = detailsErrorById[propertyKey] || null;
  const propertyLoading = Boolean(activeMaterialId && !propertyDetails && !propertyError) || Boolean(detailsLoadingById[propertyKey]);

  const visibleResults = screenResults.length ? screenResults : results;
  const showResultsPanel = railMode === 'home' && resultsOpen && visibleResults.length > 0;
  const effectiveInspectorOpen = inspectorOpen;

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (!activeMaterialId) return;
    // Local-first loads only. Prefetch/enrich also warms these; avoid huge parallel dumps.
    void loadMaterialDetails(activeMaterialId, { sections: [...PROPERTY_SECTIONS], limit: 8, downsample: true });
    if (activeTab === 'structure') void loadMaterialStructure(activeMaterialId);
    // Always warm spectra payload (dedicated key) so Spectra tab is instant / not stuck loading.
    void loadMaterialDetails(activeMaterialId, {
      sections: [...SPECTRA_SECTIONS],
      limit: 8,
      downsample: true,
      force: activeTab === 'spectra',
    });
    // Prefetch hop payload on every hopDepth change (not only while Neighbors is open),
    // so scrolling hops on Structure still warms the cache and the chip always feels live.
    const depth = Math.max(1, Math.min(5, hopDepth));
    void expandNeighborhood(activeMaterialId, {
      depth,
      limit_nodes: hopLimitNodes(depth),
      silent: true,
    });
  }, [activeMaterialId, activeTab, hopDepth, expandNeighborhood, loadMaterialDetails, loadMaterialStructure]);

  return (
    <div className="relative flex h-dvh w-screen overflow-hidden" style={{ background: 'var(--cat-bg)', color: 'var(--cat-text-1)' }}>
      <DemoNarrationAudio />
      <WorkspaceRail mode={railMode as RailMode} setMode={setRailMode as (mode: RailMode) => void} />

      <div className="relative flex min-w-0 flex-1 overflow-hidden">
        {railMode === 'genes' ? (
          <div className="flex min-h-0 min-w-0 flex-1">
            <GenesMode />
            {inspectorOpen ? (
              <Suspense fallback={<div className="jarvis-inspector-loading">Loading agent</div>}>
                <ContextInspector
                  workspace={null}
                  propertyDetails={null}
                  propertyLoading={false}
                  propertyError={null}
                  evidenceDetails={null}
                  spectraDetails={null}
                  inspectorTab={inspectorTab}
                  setInspectorTab={setInspectorTab}
                  onCollapse={() => setInspectorOpen(false)}
                />
              </Suspense>
            ) : null}
          </div>
        ) : railMode === 'notebook' ? (
          <Suspense fallback={<div className="jarvis-mode-loading">Loading notebook</div>}>
            <NotebookMode />
          </Suspense>
        ) : railMode === 'graph' ? (
          <div className="flex min-h-0 min-w-0 flex-1">
            <Suspense fallback={<div className="jarvis-mode-loading">Loading graph</div>}>
              <GraphMode
                showAgentButton={!inspectorOpen}
                openAgent={() => {
                  setInspectorOpen(true);
                  setInspectorTab('agent');
                }}
              />
            </Suspense>
            {inspectorOpen ? (
              <Suspense fallback={<div className="jarvis-inspector-loading">Loading agent</div>}>
                <ContextInspector
                  workspace={workspace}
                  propertyDetails={propertyDetails}
                  propertyLoading={propertyLoading}
                  propertyError={propertyError}
                  evidenceDetails={evidenceDetails}
                  spectraDetails={spectraDetails}
                  inspectorTab={inspectorTab}
                  setInspectorTab={setInspectorTab}
                  onCollapse={() => setInspectorOpen(false)}
                />
              </Suspense>
            ) : null}
          </div>
        ) : railMode === 'add_material' ? (
          <AddMode
            prompt={researchPrompt}
            setPrompt={setResearchPrompt}
            mode={researchMode}
            setMode={setResearchMode}
            loading={researchQueueing}
            onQueue={async () => {
              setResearchQueueing(true);
              try {
                await runResearch(researchPrompt || 'Research and normalize a candidate material');
              } finally {
                setResearchQueueing(false);
              }
            }}
            onAsk={() => {
              if (!researchPrompt.trim()) return;
              void sendMessage(researchPrompt.trim());
              setRailMode('home');
              setInspectorOpen(true);
              setInspectorTab('agent');
            }}
          />
        ) : railMode === 'settings' ? (
          <SettingsMode
            status={status}
            backendUrl={backendUrl}
            isOffline={isOffline}
            theme={theme}
            setTheme={setTheme}
            density={density}
            setDensity={setDensity}
            hopDepth={hopDepth}
            setHopDepth={setHopDepth}
            rawSettings={rawSettings}
          />
        ) : railMode === 'candidates' ? (
          <CandidatesMode
            candidates={candidates}
            canCompare={canCompare}
            canExport={canExport}
            compareData={compareData}
            compareLoading={compareLoading}
            onCompare={() => void runCompare()}
            onRemove={removeCandidate}
            onExportJson={() => void exportCandidates('json')}
            onExportCsv={() => void exportCandidates('csv')}
            onExportSubgraph={() => void exportSubgraph(candidates.map((c) => c.material_id))}
          />
        ) : (
          <HomeWorkspace
            workspace={workspace}
            workspaceLoading={workspaceLoading}
            workspaceError={workspaceError}
            startupError={startupError}
            isOffline={isOffline}
            retry={retry}
            showResultsPanel={showResultsPanel}
            resultsOpen={resultsOpen}
            resultsAvailable={visibleResults.length > 0}
            onToggleResults={() => setResultsOpen((o) => !o)}
            results={visibleResults}
            onCloseResults={() => setResultsOpen(false)}
            onOpenMaterial={(id) => void selectNode(id)}
            activeTab={activeTab}
            setActiveTab={(tab) => setWorkspaceTab(tab)}
            hopDepth={hopDepth}
            setHopDepth={setHopDepth}
            graphNodes={graphNodes}
            graphEdges={graphEdges}
            seedCandidates={visibleResults}
            structure={structurePayload}
            structureLoading={structureLoading}
            structureError={structureError}
            spectraDetails={spectraDetails}
            detailsLoading={Boolean(detailsLoadingById[spectraKey])}
            detailsError={detailsErrorById[spectraKey] || null}
            propertyDetails={propertyDetails}
            propertyLoading={propertyLoading}
            propertyError={propertyError}
            evidenceDetails={evidenceDetails}
            selectedCandidateIds={selectedCandidateIds}
            addCandidate={addCandidate}
            removeCandidate={removeCandidate}
            inspectorOpen={effectiveInspectorOpen}
            setInspectorOpen={setInspectorOpen}
            inspectorTab={inspectorTab}
            setInspectorTab={setInspectorTab}
          />
        )}
      </div>
      <EdgeSheet />
    </div>
  );
}
