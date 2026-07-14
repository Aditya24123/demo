/**
 * Live-shell UI action executor.
 *
 * Agent tools emit ui_actions (select_node, set_workspace_tab, open_inspector, ?).
 * Those must drive the Jarvis workspace layout (railMode / inspectorOpen / workspaceTab),
 * not only the legacy activeSheet sheet system.
 */

import type { WorkspaceVM } from '../bridge/viewModels';

export type LayoutApi = {
  setRailMode: (mode: 'home' | 'genes' | 'notebook' | 'graph' | 'candidates' | 'add_material' | 'settings') => void;
  setWorkspaceTab: (tab: 'neighbors' | 'structure' | 'spectra') => void;
  setHopDepth?: (depth: number) => void;
  setGenomicsCaseId?: (caseId: 'brca1' | 'hbb' | 'ctg') => void;
  setGenomicsVariantIndex?: (index: number) => void;
  setGenomicsRepeatCount?: (count: number) => void;
  resetGenomicsCamera?: () => void;
  setGenomeSelection?: (position: number) => void;
  setGenomeViewport?: (start: number, end: number) => void;
  setGenomeSequenceVisible?: (visible: boolean) => void;
  applyDemoAction?: (action: Record<string, unknown>) => void;
  setInspectorOpen: (open: boolean) => void;
  setInspectorTab: (tab: 'overview' | 'properties' | 'evidence' | 'agent') => void;
  /** Legacy sheet API ? kept only for non-workspace sheets if needed. */
  openSheet?: (sheet: string | null) => void;
};

export type UiActionDeps = {
  layout: LayoutApi;
  selectNode: (id: string | null) => Promise<void>;
  loadMaterialStructure: (materialId: string, force?: boolean) => Promise<unknown>;
  expandNeighborhood?: (
    materialId: string,
    options?: { depth?: number; limit_nodes?: number; silent?: boolean; force?: boolean },
  ) => Promise<void>;
  selectProject: (projectId: string | null) => void;
  getWorkspace: () => WorkspaceVM | null;
  addToast: (message: string, type?: 'error' | 'info' | 'success' | 'warning') => void;
  clearGraphSearch?: () => void;
  dispatchGraphFocus?: (materialId: string, action: Record<string, unknown>) => void;
};

export type UiActionResult = {
  selectedMaterialId: string | null;
  workspaceTab: 'neighbors' | 'structure' | 'spectra' | null;
  openedInspector: boolean;
  openedGraph: boolean;
  selectionOk: boolean | null;
  structureOk: boolean | null;
  errors: string[];
};

export function materialIdFromUiAction(action: Record<string, unknown> | null | undefined): string | null {
  if (!action || typeof action !== 'object') return null;
  const payload = (action.payload && typeof action.payload === 'object' ? action.payload : {}) as Record<string, unknown>;
  const raw =
    action.material_id ||
    action.materialId ||
    payload.material_id ||
    payload.materialId ||
    action.node_id ||
    action.nodeId ||
    null;
  if (raw == null) return null;
  const id = String(raw).trim();
  return id || null;
}

export function workspaceMatchesMaterial(workspace: WorkspaceVM | null, materialId: string): boolean {
  if (!workspace || !materialId) return false;
  const want = materialId.trim().toLowerCase();
  const resolved = String(workspace.resolvedMaterialId || '').trim().toLowerCase();
  const title = String(workspace.title || '').trim().toLowerCase();
  if (resolved && resolved === want) return true;
  if (title && title === want) return true;
  // Formula-like ids sometimes appear without mp- prefix match
  if (resolved && want.includes(resolved)) return true;
  if (title && (want === title || title.includes(want) || want.includes(title))) return true;
  return false;
}

/**
 * Collapse and apply agent ui_actions against the live shell.
 * Idempotent preference: last select / last tab wins; focus events still fan out.
 */
export async function applyUiActions(
  actions: Array<Record<string, unknown>> | null | undefined,
  deps: UiActionDeps,
): Promise<UiActionResult> {
  const result: UiActionResult = {
    selectedMaterialId: null,
    workspaceTab: null,
    openedInspector: false,
    openedGraph: false,
    selectionOk: null,
    structureOk: null,
    errors: [],
  };

  const list = Array.isArray(actions) ? actions : [];
  if (!list.length) return result;

  let materialToSelect: string | null = null;
  let openInspector = false;
  let workspaceTab: UiActionResult['workspaceTab'] = null;
  let openGraph = false;
  let hopDepth: number | null = null;
  let expandNeighborhood: { materialId: string; depth: number } | null = null;
  let projectRefresh: Record<string, unknown> | null = null;
  let openProjectRun: string | null = null;
  const focusEvents: Array<{ materialId: string; action: Record<string, unknown> }> = [];

  for (const action of list) {
    if (!action || typeof action !== 'object') continue;
    const type = String(action.type || '');

    if (type === 'refresh_project') {
      projectRefresh = action;
      continue;
    }
    if (type === 'open_project_run' || type === 'open_project') {
      const projectId = typeof action.project_id === 'string' ? action.project_id : null;
      if (projectId) openProjectRun = projectId;
      continue;
    }
    if (type === 'set_rail_mode') {
      const mode = String(action.mode || action.rail_mode || '');
      if (
        mode === 'home' ||
        mode === 'genes' ||
        mode === 'notebook' ||
        mode === 'graph' ||
        mode === 'candidates' ||
        mode === 'add_material' ||
        mode === 'settings'
      ) {
        deps.layout.setRailMode(mode);
      }
      continue;
    }
    if (type === 'set_inspector') {
      deps.layout.setInspectorOpen(Boolean(action.open));
      if (action.tab === 'overview' || action.tab === 'properties' || action.tab === 'evidence' || action.tab === 'agent') {
        deps.layout.setInspectorTab(action.tab);
      }
      continue;
    }
    if (type.startsWith('demo_')) {
      deps.layout.applyDemoAction?.(action);
      continue;
    }
    if (
      type === 'open_genomics_case' ||
      type === 'focus_genomics_variant' ||
      type === 'set_genomics_repeat_count' ||
      type === 'reset_genomics_camera'
    ) {
      deps.layout.setRailMode('genes');
      if (type === 'open_genomics_case' && (action.case_id === 'brca1' || action.case_id === 'hbb' || action.case_id === 'ctg')) deps.layout.setGenomicsCaseId?.(action.case_id);
      if (type === 'focus_genomics_variant') deps.layout.setGenomicsVariantIndex?.(Number(action.index) || 0);
      if (type === 'set_genomics_repeat_count') deps.layout.setGenomicsRepeatCount?.(Number(action.repeat_count) || 0);
      if (type === 'reset_genomics_camera') deps.layout.resetGenomicsCamera?.();
      continue;
    }
    if (type === 'genome_highlight' || type === 'genome_zoom' || type === 'genome_show_sequence') {
      deps.layout.setRailMode('genes');
      deps.layout.setGenomicsCaseId?.('brca1');
      if (type === 'genome_highlight') {
        const position = Number(action.position);
        if (Number.isFinite(position) && position > 0) deps.layout.setGenomeSelection?.(Math.round(position));
      }
      if (type === 'genome_zoom') {
        const start = Number(action.start);
        const end = Number(action.end);
        if (Number.isFinite(start) && Number.isFinite(end) && start > 0 && end >= start) {
          deps.layout.setGenomeViewport?.(Math.round(start), Math.round(end));
        }
      }
      if (type === 'genome_show_sequence') deps.layout.setGenomeSequenceVisible?.(true);
      continue;
    }
    if (type === 'set_workspace_tab') {
      const tab = action.tab;
      if (tab === 'neighbors' || tab === 'structure' || tab === 'spectra') {
        workspaceTab = tab;
      }
      continue;
    }
    if (type === 'set_hop_depth') {
      const raw = Number(action.depth ?? action.hops ?? action.hop_depth);
      if (Number.isFinite(raw)) hopDepth = Math.max(1, Math.min(5, Math.round(raw)));
      continue;
    }
    if (type === 'expand_neighborhood' || type === 'open_neighborhood' || type === 'open_neighbours') {
      const mid = materialIdFromUiAction(action);
      const rawDepth = Number(action.depth ?? action.hops ?? action.hop_depth ?? hopDepth ?? 1);
      const depth = Number.isFinite(rawDepth) ? Math.max(1, Math.min(5, Math.round(rawDepth))) : 1;
      if (mid) {
        expandNeighborhood = { materialId: mid, depth };
        if (!workspaceTab) workspaceTab = 'neighbors';
        materialToSelect = mid;
      }
      continue;
    }
    if (type === 'open_graph') {
      openGraph = true;
      continue;
    }

    if (
      type === 'select_node' ||
      type === 'open_inspector' ||
      type === 'highlight_node' ||
      type === 'zoom_to_node' ||
      type === 'open_material'
    ) {
      const materialId = materialIdFromUiAction(action);
      if (!materialId) continue;
      if (type === 'select_node' || type === 'open_inspector' || type === 'open_material') {
        materialToSelect = materialId;
      }
      if (type === 'open_inspector' || type === 'open_material') {
        openInspector = true;
      }
      focusEvents.push({ materialId, action });
    }
  }

  if (openProjectRun) {
    deps.selectProject(openProjectRun);
    deps.layout.setRailMode('notebook');
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('catalyst:project-refresh', { detail: { project_id: openProjectRun } }));
    }
  }

  if (projectRefresh && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('catalyst:project-refresh', { detail: projectRefresh }));
  }

  if (materialToSelect) {
    deps.clearGraphSearch?.();
    // Always land on home material canvas unless graph overview was also requested alone.
    if (!openGraph || workspaceTab) {
      deps.layout.setRailMode('home');
    } else {
      deps.layout.setRailMode('graph');
    }

    try {
      await deps.selectNode(materialToSelect);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to select material';
      result.errors.push(message);
      deps.addToast(`Could not select material ${materialToSelect}`, 'error');
    }

    const workspace = deps.getWorkspace();
    const ok = workspaceMatchesMaterial(workspace, materialToSelect);
    result.selectedMaterialId = materialToSelect;
    result.selectionOk = ok;

    if (!ok) {
      const detail = workspace?.resolvedMaterialId
        ? `still showing ${workspace.resolvedMaterialId}`
        : 'workspace did not update';
      result.errors.push(`Select failed for ${materialToSelect} (${detail})`);
      deps.addToast(`Could not focus ${materialToSelect} ? ${detail}`, 'error');
    } else {
      deps.layout.setInspectorOpen(true);
      result.openedInspector = true;
      if (openInspector) {
        deps.layout.setInspectorTab('properties');
      } else {
        deps.layout.setInspectorTab('agent');
      }
    }
  } else if (openInspector) {
    deps.layout.setInspectorOpen(true);
    deps.layout.setInspectorTab('properties');
    result.openedInspector = true;
  }

  if (hopDepth != null) {
    deps.layout.setHopDepth?.(hopDepth);
  }

  if (workspaceTab) {
    if (!openGraph) deps.layout.setRailMode('home');
    deps.layout.setWorkspaceTab(workspaceTab);
    result.workspaceTab = workspaceTab;

    if (workspaceTab === 'structure') {
      const structureId = materialToSelect || deps.getWorkspace()?.resolvedMaterialId || null;
      if (structureId) {
        try {
          const payload = await deps.loadMaterialStructure(structureId, true);
          const sites = (payload as { sites?: unknown[] } | null)?.sites;
          const ok = Array.isArray(sites) ? sites.length > 0 : Boolean(payload);
          result.structureOk = ok;
          if (!ok) {
            result.errors.push(`Structure empty for ${structureId}`);
            deps.addToast(`Structure unavailable for ${structureId}`, 'warning');
          }
        } catch (err) {
          result.structureOk = false;
          const message = err instanceof Error ? err.message : 'Structure load failed';
          result.errors.push(message);
          deps.addToast(`Could not load structure for ${structureId}`, 'error');
        }
      } else {
        result.structureOk = false;
        result.errors.push('Structure tab requested without a material');
        deps.addToast('No material selected for structure view', 'warning');
      }
    }

    if (workspaceTab === 'neighbors') {
      const nid =
        expandNeighborhood?.materialId ||
        materialToSelect ||
        deps.getWorkspace()?.resolvedMaterialId ||
        null;
      const depth = expandNeighborhood?.depth ?? hopDepth ?? 1;
      if (nid && deps.expandNeighborhood) {
        try {
          await deps.expandNeighborhood(nid, {
            depth,
            limit_nodes: Math.min(800, 48 + depth * 140),
            silent: true,
            force: true,
          } as { depth?: number; limit_nodes?: number; silent?: boolean; force?: boolean });
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Neighborhood load failed';
          result.errors.push(message);
          deps.addToast(`Could not load neighborhood for ${nid}`, 'warning');
        }
      }
    }
  } else if (expandNeighborhood && deps.expandNeighborhood) {
    deps.layout.setRailMode('home');
    deps.layout.setWorkspaceTab('neighbors');
    result.workspaceTab = 'neighbors';
    try {
      await deps.expandNeighborhood(expandNeighborhood.materialId, {
        depth: expandNeighborhood.depth,
        limit_nodes: Math.min(800, 48 + expandNeighborhood.depth * 140),
        silent: true,
        force: true,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Neighborhood load failed';
      result.errors.push(message);
    }
  }

  if (openGraph && !materialToSelect) {
    deps.layout.setRailMode('graph');
    result.openedGraph = true;
  } else if (openGraph && materialToSelect) {
    // Graph focus still dispatches; stay on home if structure/neighbors was requested.
    if (!workspaceTab) {
      deps.layout.setRailMode('graph');
      result.openedGraph = true;
    }
  }

  for (const event of focusEvents) {
    deps.dispatchGraphFocus?.(event.materialId, event.action);
  }

  return result;
}
