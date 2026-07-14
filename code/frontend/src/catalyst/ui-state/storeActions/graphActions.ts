// @ts-nocheck
import { api } from '@/lib/api';
import {
  normalizeEdge,
  normalizeEdgeDetail,
  normalizeFallbackWorkspace,
  normalizeNode,
  normalizeWorkspace,
} from '../../bridge/normalizers';
import { toCatalystError } from '../../bridge/errors';
import { useLayoutStore } from '../layoutStore';
import { applyUiActions } from '../uiActions';
import { dispatchGraphFocus, mergeGraphEdges, mergeGraphNodes } from '../appStoreGraph';
import type { AppState } from '../appStoreTypes';

type SetState = any;
type GetState = any;

export function createGraphActions(set: SetState, get: GetState): Partial<AppState> {
  return {
  selectGraphNode: async (id) => {
    set({ selectedNodeId: id, workspace: null, edgeDetail: null, graphNodeDetailLoading: true, graphNodeDetailError: null });
    try {
      const nodeDetail = await api.getGraphNode(id);
      set({ selectedGraphNodeDetail: nodeDetail, graphNodeDetailLoading: false });
      if (nodeDetail.type === 'material') {
        get().selectNode(id);
      }
    } catch (err) {
      set({ graphNodeDetailLoading: false, graphNodeDetailError: 'Failed to load node details' });
    }
  },

  selectNode: async (id) => {
    if (!id) {
      set({ selectedNodeId: null, workspace: null, edgeDetail: null, selectedEdgeId: null, selectedGraphNodeDetail: null });
      return;
    }

    const nodes = get().graphNodes;
    const node = nodes.find((n) => n.id === id);
    let targetId = id;

    // Cluster with representative ? navigate to it
    if (node?.type === 'cluster') {
      if (node.representative_material_id) {
        targetId = node.representative_material_id;
      } else {
        set({ selectedNodeId: id, workspace: null, workspaceError: null });
        return;
      }
    }

    set({ selectedNodeId: id, workspaceLoading: true, workspaceError: null, selectedEdgeId: null, edgeDetail: null });

    try {
      const data = await api.getWorkspace(targetId);
      const vm = normalizeWorkspace(data, false);
      // Merge workspace graph
      if (data?.graph) {
        const inNodes = (data.graph.nodes || []).map(normalizeNode);
        const inEdges = (data.graph.edges || data.graph.links || []).map(normalizeEdge);
        set((s) => ({
          graphNodes: mergeGraphNodes(s.graphNodes, inNodes),
          graphEdges: mergeGraphEdges(s.graphEdges, inEdges),
        }));
      }
      set({ workspace: vm, workspaceLoading: false });
      // Prefetch selected-material enrich + structure/details so Spectra/Structure open instantly.
      void get().prefetchMaterialWorkspace(vm.resolvedMaterialId || targetId);
    } catch (err) {
      const ce = toCatalystError('material', err);
      if (ce.status === 404 || true) {
        // Fallback
        try {
          const [mat, ev] = await Promise.all([api.getMaterial(targetId), api.getEvidence(targetId)]);
          const vm = normalizeFallbackWorkspace(mat, ev);
          if (vm.elements?.length) {
            const fallbackNodes = [
              normalizeNode({ id: targetId, label: mat.formula_pretty, type: 'material', ...mat }),
              ...vm.elements.map((el: string) => normalizeNode({ id: el, label: el, type: 'element', symbol: el })),
            ];
            const fallbackEdges = vm.elements.map((el: string) =>
              normalizeEdge({ source: targetId, target: el, type: 'CONTAINS_ELEMENT', weight: 1 }),
            );
            set((s) => ({
              graphNodes: mergeGraphNodes(s.graphNodes, fallbackNodes),
              graphEdges: mergeGraphEdges(s.graphEdges, fallbackEdges),
            }));
          }
          set({ workspace: vm, workspaceLoading: false });
          void get().prefetchMaterialWorkspace(vm.resolvedMaterialId || targetId);
        } catch (fbErr) {
          set({ workspaceLoading: false, workspaceError: 'Material data unavailable' });
          get().addToast('Failed to load material', 'error');
        }
      }
    }
  },

  prefetchMaterialWorkspace: async (materialId) => {
    const id = String(materialId || '').trim();
    if (!id) return;

    // Track in-flight prefetches so StrictMode / rapid selects don't pile up.
    const inflightKey = `_prefetch_${id}`;
    if ((get() as any)[inflightKey]) return;
    (get() as any)[inflightKey] = true;

    const propertySections = [
      'thermo',
      'electronic_structure',
      'magnetism',
      'elasticity',
      'dielectric',
      'bonds',
      'surfaces',
      'spectra',
    ];

    try {
      // 1) Local-first, parallel, no force ? paint properties/structure ASAP.
      await Promise.all([
        get().loadMaterialStructure(id, false),
        get().loadMaterialDetails(id, {
          sections: propertySections,
          limit: 8,
          downsample: true,
          force: false,
        }),
        get().loadMaterialDetails(id, {
          sections: ['spectra'],
          limit: 8,
          downsample: true,
          force: false,
        }),
      ]);

      // 2) Enrich AFTER local paint. Cache hit is cheap; miss may hit MP (~3s) but
      //    must not block structure/properties. Never use refresh:true (was re-running MP).
      let enrich: any = null;
      try {
        enrich = await api.enrichMaterial(id);
      } catch {
        enrich = null;
      }

      // 3) Merge description/capabilities into workspace (OR-merge flags so Spectra never flips off).
      const ws = get().workspace;
      if (ws && (ws.resolvedMaterialId === id || ws.materialId === id) && enrich) {
        const prevCaps = ws.capabilities || {};
        const nextCaps = enrich?.capabilities || {};
        const mergedCaps = {
          ...prevCaps,
          ...nextCaps,
          // Sticky true: once local/enrich says spectra exist, keep the tab available.
          spectra: Boolean(prevCaps.spectra || nextCaps.spectra || Number(enrich?.spectra?.count || 0) > 0),
          structure: Boolean(prevCaps.structure || nextCaps.structure),
          summary: Boolean(prevCaps.summary || nextCaps.summary || enrich?.description),
        };
        set({
          workspace: {
            ...ws,
            description: enrich?.description || ws.description || null,
            capabilities: mergedCaps,
            mpMaterialId: enrich?.mp_material_id || ws.mpMaterialId || null,
          },
        });
      }

      // 4) If enrich brought spectra, inject into details cache immediately (don't wait for re-fetch).
      const spectraCount = Number(enrich?.spectra?.count || 0);
      const remoteRecords = Array.isArray(enrich?.spectra?.records) ? enrich.spectra.records : [];
      if (spectraCount > 0 && remoteRecords.length) {
        const inject = (sections: string[]) => {
          const cacheKey = `${id}::${sections.join(',')}::8::true`;
          const existing = get().detailsById[cacheKey] || {
            material_id: id,
            resolved_material_id: id,
            details: {},
          };
          set((s) => ({
            detailsById: {
              ...s.detailsById,
              [cacheKey]: {
                ...existing,
                details: {
                  ...(existing as any).details,
                  spectra: {
                    records: remoteRecords,
                    count: spectraCount,
                    truncated: false,
                    source: enrich?.spectra?.source || 'materials_project_api',
                  },
                },
              },
            },
          }));
        };
        inject(propertySections);
        inject(['spectra']);
      }

      // 5) Re-pull local+cache-merged details / structure when enrich filled gaps.
      if (spectraCount > 0 || enrich?.structure?.sites?.length || enrich?.description) {
        await Promise.all([
          spectraCount > 0
            ? get().loadMaterialDetails(id, {
                sections: propertySections,
                limit: 8,
                downsample: true,
                force: true,
              })
            : Promise.resolve(null),
          spectraCount > 0
            ? get().loadMaterialDetails(id, {
                sections: ['spectra'],
                limit: 8,
                downsample: true,
                force: true,
              })
            : Promise.resolve(null),
          enrich?.structure?.sites?.length ? get().loadMaterialStructure(id, true) : Promise.resolve(null),
        ]);
      }

      if (enrich?.mp_error) {
        // Soft toast only when MP was expected and failed hard (missing key, etc.)
        const err = String(enrich.mp_error);
        if (err.includes('MP_API_KEY') || err.includes('not configured')) {
          get().addToast('MP_API_KEY not set ? spectra/summary enrich disabled', 'warning');
        }
      }
    } catch {
      // Soft-fail: local data still works; enrich is progressive enhancement.
    } finally {
      (get() as any)[inflightKey] = false;
    }
  },

  // ?? Edge selection ??????????????????????????????????????????????????????????
  loadMaterialStructure: async (materialId, force = false) => {
    const id = String(materialId || '').trim();
    if (!id) return null;
    if (!force && get().structureById[id]) return get().structureById[id];

    set((s) => ({
      structureLoadingById: { ...s.structureLoadingById, [id]: true },
      structureErrorById: { ...s.structureErrorById, [id]: null },
    }));

    try {
      const data = await api.getStructure(id);
      set((s) => ({
        structureById: { ...s.structureById, [id]: data },
        structureLoadingById: { ...s.structureLoadingById, [id]: false },
      }));
      return data;
    } catch {
      set((s) => ({
        structureLoadingById: { ...s.structureLoadingById, [id]: false },
        structureErrorById: { ...s.structureErrorById, [id]: 'Failed to load structure' },
      }));
      return null;
    }
  },

  loadMaterialDetails: async (materialId, options = {}) => {
    const id = String(materialId || '').trim();
    if (!id) return null;
    const cacheKey = `${id}::${(options.sections || []).join(',')}::${options.limit ?? ''}::${options.downsample ?? ''}`;
    if (!options.force && get().detailsById[cacheKey]) return get().detailsById[cacheKey];

    set((s) => ({
      detailsLoadingById: { ...s.detailsLoadingById, [cacheKey]: true },
      detailsErrorById: { ...s.detailsErrorById, [cacheKey]: null },
    }));

    try {
      const data = await api.getMaterialDetails(id, {
        sections: options.sections,
        limit: options.limit,
        downsample: options.downsample,
      });
      set((s) => ({
        detailsById: { ...s.detailsById, [cacheKey]: data },
        detailsLoadingById: { ...s.detailsLoadingById, [cacheKey]: false },
      }));
      return data;
    } catch {
      set((s) => ({
        detailsLoadingById: { ...s.detailsLoadingById, [cacheKey]: false },
        detailsErrorById: { ...s.detailsErrorById, [cacheKey]: 'Failed to load details' },
      }));
      return null;
    }
  },

  selectEdge: async (id) => {
    if (!id) { set({ selectedEdgeId: null, edgeDetail: null }); return; }
    set({ selectedEdgeId: id, edgeLoading: true, edgeError: null });
    try {
      const data = await api.getEdge(id);
      set({ edgeDetail: normalizeEdgeDetail(data), edgeLoading: false });
    } catch (err) {
      set({ edgeLoading: false, edgeError: 'Failed to load edge' });
      get().addToast('Failed to load edge data', 'error');
    }
  },

  // ?? Neighborhood ????????????????????????????????????????????????????????????
  expandNeighborhood: async (materialId, options = {}) => {
    const id = String(materialId || '').trim();
    if (!id) return;
    const depth = Math.max(1, Math.min(5, Number(options.depth ?? get().graphSettings.localDepth ?? 1)));
    // Keep in sync with hopLimitNodes() / backend le=800.
    const limit_nodes = Math.max(10, Math.min(800, Number(options.limit_nodes ?? Math.min(800, 48 + depth * 140))));
    const silent = Boolean(options.silent);
    // Include limit in cache key so hop budgets aren't stuck on an older smaller fetch.
    const key = `${id}::${depth}::${limit_nodes}`;
    const cached = get().neighborhoodByKey[key];
    // Skip only successful non-empty or intentional empty caches; allow retry after errors.
    if (cached && !options.force) {
      return;
    }
    // Coalesce concurrent loads for the same key.
    if (get().neighborhoodLoadingKey === key && !options.force) {
      return;
    }
    set({ neighborhoodLoadingKey: key });
    try {
      const data = await api.getNeighborhood(id, depth, limit_nodes);
      const inNodes = (data.nodes || []).map(normalizeNode);
      const inEdges = (data.edges || data.links || []).map(normalizeEdge);
      set((s) => ({
        graphNodes: mergeGraphNodes(s.graphNodes, inNodes),
        graphEdges: mergeGraphEdges(s.graphEdges, inEdges),
        neighborhoodByKey: {
          ...s.neighborhoodByKey,
          [key]: { nodes: inNodes, edges: inEdges, depth },
        },
        neighborhoodLoadingKey: s.neighborhoodLoadingKey === key ? null : s.neighborhoodLoadingKey,
      }));
      if (!silent) get().addToast(`Loaded ${depth}-hop neighborhood (${inNodes.length} nodes)`, 'success');
    } catch {
      // Do NOT poison the cache with empty data ? that made hop>1 look permanently broken.
      set((s) => ({
        neighborhoodLoadingKey: s.neighborhoodLoadingKey === key ? null : s.neighborhoodLoadingKey,
      }));
      if (!silent) get().addToast('Failed to expand neighborhood', 'error');
    }
  },

  applyUiActions: async (actions) => {
    const layout = useLayoutStore.getState();
    await applyUiActions(actions as Array<Record<string, unknown>>, {
      layout: {
        setRailMode: layout.setRailMode,
        setWorkspaceTab: layout.setWorkspaceTab,
        setHopDepth: layout.setHopDepth,
        setInspectorOpen: layout.setInspectorOpen,
        setInspectorTab: layout.setInspectorTab,
        openSheet: layout.openSheet as (sheet: string | null) => void,
      },
      selectNode: (id) => get().selectNode(id),
      loadMaterialStructure: (materialId, force) => get().loadMaterialStructure(materialId, force),
      expandNeighborhood: (materialId, options) => get().expandNeighborhood(materialId, options),
      selectProject: (projectId) => get().selectProject(projectId),
      getWorkspace: () => get().workspace,
      addToast: (message, type) => get().addToast(message, type),
      clearGraphSearch: () => set((s) => ({ graphSettings: { ...s.graphSettings, search: '' } })),
      dispatchGraphFocus: (materialId, action) => dispatchGraphFocus(materialId, action),
    });
  },

  };
}
