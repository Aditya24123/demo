import { lazy, Suspense, useEffect } from 'react';
import type { CandidateRowVM, GraphEdgeVM, GraphNodeVM, Structure3DVM, WorkspaceVM } from '@/catalyst/bridge/viewModels';
import type { HomeTab } from './types';
import { MaterialHeader } from './MaterialHeader';
import { NeighborsGraph } from './NeighborsGraph';
import { SpectraPanel, type SpectraDetails } from './SpectraPanel';
import { StatePanel } from './uiAtoms';

const CrystalStructurePanel = lazy(() =>
  import('@/components/structure/CrystalStructurePanel').then((module) => ({ default: module.CrystalStructurePanel })),
);

export function MaterialCanvas({
  workspace,
  workspaceLoading,
  workspaceError,
  activeTab,
  setActiveTab,
  hopDepth,
  setHopDepth,
  graphNodes,
  graphEdges,
  seedCandidates,
  structure,
  structureLoading,
  structureError,
  spectraDetails,
  detailsLoading,
  detailsError,
  selectedCandidateIds,
  addCandidate,
  removeCandidate,
  resultsOpen,
  resultsAvailable,
  onToggleResults,
  inspectorOpen,
  onToggleInspector,
}: {
  workspace: WorkspaceVM | null;
  workspaceLoading: boolean;
  workspaceError: string | null;
  activeTab: HomeTab;
  setActiveTab: (tab: HomeTab) => void;
  hopDepth: number;
  setHopDepth: (depth: number) => void;
  graphNodes: GraphNodeVM[];
  graphEdges: GraphEdgeVM[];
  seedCandidates: CandidateRowVM[];
  structure: Structure3DVM | null;
  structureLoading: boolean;
  structureError: string | null;
  spectraDetails: SpectraDetails;
  detailsLoading: boolean;
  detailsError: string | null;
  selectedCandidateIds: Set<string>;
  addCandidate: (workspace: WorkspaceVM) => void;
  removeCandidate: (materialId: string) => void;
  resultsOpen: boolean;
  resultsAvailable: boolean;
  onToggleResults: () => void;
  inspectorOpen: boolean;
  onToggleInspector: () => void;
}) {
  // Always keep all three tabs ? hiding Spectra when caps flip false felt like a bug.
  const isCandidate = workspace ? selectedCandidateIds.has(workspace.resolvedMaterialId) : false;

  useEffect(() => {
    if (activeTab !== 'neighbors' && activeTab !== 'structure' && activeTab !== 'spectra') {
      setActiveTab('structure');
    }
  }, [activeTab, setActiveTab]);

  return (
    <main className="jarvis-material-canvas">
      {workspaceLoading ? (
        <StatePanel title="Loading material" />
      ) : workspaceError ? (
        <StatePanel title={workspaceError} danger />
      ) : workspace ? (
        <div className="flex h-full min-h-0 flex-col">
          <MaterialHeader
            workspace={workspace}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            hopDepth={hopDepth}
            setHopDepth={setHopDepth}
            isCandidate={isCandidate}
            addCandidate={addCandidate}
            removeCandidate={removeCandidate}
            resultsOpen={resultsOpen}
            resultsAvailable={resultsAvailable}
            onToggleResults={onToggleResults}
            inspectorOpen={inspectorOpen}
            onToggleInspector={onToggleInspector}
          />

          <div className="jarvis-workspace-stage">
            {activeTab === 'neighbors' ? (
              <NeighborsGraph
                workspace={workspace}
                nodes={graphNodes}
                edges={graphEdges}
                hopDepth={hopDepth}
                seedCandidates={seedCandidates}
              />
            ) : activeTab === 'structure' ? (
              <Suspense fallback={<StatePanel title="Loading structure viewer" />}>
                <CrystalStructurePanel structure={structure} isLoading={structureLoading} error={structureError} />
              </Suspense>
            ) : (
              <SpectraPanel details={spectraDetails} loading={detailsLoading} error={detailsError} />
            )}
          </div>
        </div>
      ) : (
        <StatePanel title="Loading graph workspace" text="Catalyst is opening the default material workspace." />
      )}
    </main>
  );
}
