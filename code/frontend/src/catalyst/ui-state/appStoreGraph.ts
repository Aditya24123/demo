import type { GraphEdgeVM, GraphNodeVM } from '../bridge/viewModels';

export function mergeGraphNodes(base: GraphNodeVM[], incoming: GraphNodeVM[]): GraphNodeVM[] {
  const next = [...base];
  incoming.forEach((node) => {
    const idx = next.findIndex((n) => n.id === node.id);
    if (idx >= 0) next[idx] = { ...next[idx], ...node };
    else next.push(node);
  });
  return next;
}

export function mergeGraphEdges(base: GraphEdgeVM[], incoming: GraphEdgeVM[]): GraphEdgeVM[] {
  const next = [...base];
  incoming.forEach((edge) => {
    if (!next.find((e) => e.id === edge.id)) next.push(edge);
  });
  return next;
}

export function dispatchGraphFocus(materialId: string, action: any) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent('catalyst:graph-focus-node', {
      detail: {
        materialId,
        nodeId: materialId,
        scale: action?.scale,
        durationMs: action?.duration_ms || action?.durationMs,
      },
    }),
  );
}
