import { lazy, Suspense } from 'react';
import type { CandidateRowVM, GraphEdgeVM, GraphNodeVM, Structure3DVM, WorkspaceVM } from '@/catalyst/bridge/viewModels';
import type { InspectorTab } from '@/catalyst/ui-state/layoutStore';
import type { HomeTab } from './types';
import { MaterialCanvas } from './MaterialCanvas';
import { ResultsPanel } from './ResultsPanel';
import type { SpectraDetails } from './SpectraPanel';

const ContextInspector = lazy(() =>
  import('./ContextInspector').then((module) => ({ default: module.ContextInspector })),
);

export function HomeWorkspace(props: {
  workspace: WorkspaceVM | null;
  workspaceLoading: boolean;
  workspaceError: string | null;
  startupError: string | null;
  isOffline: boolean;
  retry: () => void;
  showResultsPanel: boolean;
  resultsOpen: boolean;
  resultsAvailable: boolean;
  onToggleResults: () => void;
  results: CandidateRowVM[];
  onCloseResults: () => void;
  onOpenMaterial: (id: string) => void;
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
  propertyDetails: unknown;
  propertyLoading: boolean;
  propertyError: string | null;
  evidenceDetails: unknown;
  selectedCandidateIds: Set<string>;
  addCandidate: (workspace: WorkspaceVM) => void;
  removeCandidate: (materialId: string) => void;
  inspectorOpen: boolean;
  setInspectorOpen: (open: boolean) => void;
  inspectorTab: InspectorTab;
  setInspectorTab: (tab: InspectorTab) => void;
}) {
  const {
    showResultsPanel,
    results,
    onOpenMaterial,
    onCloseResults,
    workspace,
    inspectorOpen,
    setInspectorOpen,
    inspectorTab,
    setInspectorTab,
  } = props;

  return (
    <section className="relative flex min-h-0 min-w-0 flex-1 flex-col">
      <div
        className="jarvis-home-grid grid min-h-0 flex-1"
        style={{
          gridTemplateColumns: `${showResultsPanel ? '260px ' : ''}minmax(0,1fr)${inspectorOpen ? ' var(--inspector-width,400px)' : ''}`,
        }}
      >
        {showResultsPanel ? (
          <ResultsPanel results={results} onOpenMaterial={onOpenMaterial} onClose={onCloseResults} selectedId={workspace?.resolvedMaterialId || null} />
        ) : null}
        <div className="relative min-h-0 min-w-0">
          <MaterialCanvas
            workspace={props.workspace}
            workspaceLoading={props.workspaceLoading}
            workspaceError={props.workspaceError}
            activeTab={props.activeTab}
            setActiveTab={props.setActiveTab}
            hopDepth={props.hopDepth}
            setHopDepth={props.setHopDepth}
            graphNodes={props.graphNodes}
            graphEdges={props.graphEdges}
            seedCandidates={props.seedCandidates}
            structure={props.structure}
            structureLoading={props.structureLoading}
            structureError={props.structureError}
            spectraDetails={props.spectraDetails}
            detailsLoading={props.detailsLoading}
            detailsError={props.detailsError}
            selectedCandidateIds={props.selectedCandidateIds}
            addCandidate={props.addCandidate}
            removeCandidate={props.removeCandidate}
            resultsOpen={props.resultsOpen}
            resultsAvailable={props.resultsAvailable}
            onToggleResults={props.onToggleResults}
            inspectorOpen={inspectorOpen}
            onToggleInspector={() => setInspectorOpen(!inspectorOpen)}
          />
        </div>
        {inspectorOpen ? (
          <Suspense fallback={<div className="jarvis-inspector-loading">Loading agent</div>}>
            <ContextInspector
              workspace={workspace}
              propertyDetails={props.propertyDetails}
              propertyLoading={props.propertyLoading}
              propertyError={props.propertyError}
              evidenceDetails={props.evidenceDetails}
              spectraDetails={props.spectraDetails}
              inspectorTab={inspectorTab}
              setInspectorTab={setInspectorTab}
              onCollapse={() => setInspectorOpen(false)}
            />
          </Suspense>
        ) : null}
      </div>
    </section>
  );
}
