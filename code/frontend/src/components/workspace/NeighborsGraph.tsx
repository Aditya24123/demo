import { useEffect, useMemo } from 'react';
import { GraphCanvas } from '@/components/graph/GraphCanvas';
import { useAppStore } from '@/catalyst/ui-state/appStore';
import type { CandidateRowVM, GraphEdgeVM, GraphNodeVM, WorkspaceVM } from '@/catalyst/bridge/viewModels';
import { hopLimitNodes } from './utils';
import { LegendDot } from './uiAtoms';

export function NeighborsGraph({
  workspace,
  hopDepth,
}: {
  workspace: WorkspaceVM;
  nodes: GraphNodeVM[];
  edges: GraphEdgeVM[];
  hopDepth: number;
  seedCandidates: CandidateRowVM[];
}) {
  const depth = Math.max(1, Math.min(5, hopDepth));
  // Match WorkspaceShell budget so we hit the same cache entry.
  const limitNodes = hopLimitNodes(depth);
  const key = `${workspace.resolvedMaterialId}::${depth}::${limitNodes}`;
  const payload = useAppStore((s) => s.neighborhoodByKey[key]);
  const loadingKey = useAppStore((s) => s.neighborhoodLoadingKey);
  const expandNeighborhood = useAppStore((s) => s.expandNeighborhood);
  const hasPayload = payload !== undefined;

  // Ensure this hop depth is loaded when the Neighbors tab is visible.
  useEffect(() => {
    const mid = workspace.resolvedMaterialId;
    if (!mid) return;
    // force only when a prior empty/poisoned cache entry exists for this key.
    const poisoned = hasPayload && !(payload?.nodes?.length);
    void expandNeighborhood(mid, {
      depth,
      limit_nodes: limitNodes,
      silent: true,
      force: poisoned,
    });
  }, [workspace.resolvedMaterialId, depth, limitNodes, expandNeighborhood, hasPayload, payload?.nodes?.length]);

  const { localNodes, localEdges } = useMemo(() => {
    // Exact hop payload only ? never reuse seed candidates (they ignore hop depth).
    if (payload?.nodes?.length) {
      return {
        localNodes: payload.nodes,
        localEdges: payload.edges || [],
      };
    }
    return {
      localNodes: [
        {
          id: workspace.resolvedMaterialId,
          name: workspace.title,
          formula_pretty: workspace.title,
          type: 'material' as const,
          val: 6,
          color: 'var(--accent)',
        },
      ],
      localEdges: [] as GraphEdgeVM[],
    };
  }, [payload, workspace.resolvedMaterialId, workspace.title]);

  const isLoading = !hasPayload || loadingKey === key;

  const nodeCount = payload?.nodes?.length ?? 0;

  return (
    <div className="flex h-full min-h-[400px] flex-col">
      <div className="relative min-h-0 flex-1 overflow-hidden" style={{ background: 'var(--cat-bg)' }}>
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm" style={{ color: 'var(--cat-text-3)' }}>
            Loading {depth}-hop neighborhood?
          </div>
        ) : (
          // key forces a full remount so hop changes re-run layout (not a stale force-graph).
          <GraphCanvas
            key={`${workspace.resolvedMaterialId}::${depth}::${nodeCount}`}
            graphOverride={{ nodes: localNodes, edges: localEdges, selectedNodeId: workspace.resolvedMaterialId }}
          />
        )}
      </div>
      <div className="no-scrollbar flex items-center justify-center gap-6 overflow-x-auto py-2 text-xs" style={{ color: 'var(--cat-text-2)' }}>
        <span className="font-mono" style={{ color: 'var(--cat-text-3)' }}>
          {depth} hop{depth === 1 ? '' : 's'} ? {nodeCount} nodes
        </span>
        <LegendDot color="var(--cat-chart-green)" label="Similar" />
        <LegendDot color="var(--cat-chart-blue)" label="Family" />
        <LegendDot color="var(--cat-chart-violet)" label="Related" />
      </div>
    </div>
  );
}
