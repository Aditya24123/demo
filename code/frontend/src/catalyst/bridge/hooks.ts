// ?? Catalyst Bridge: Public Hooks ????????????????????????????????????????????
// Components consume ONLY these hooks. Never import appStore or api directly.

import { useAppStore } from '../ui-state/appStore';
import { useLayoutStore } from '../ui-state/layoutStore';
import { API_BASE } from '@/lib/api';
import { modelDisplayLabel, providerDisplayLabel } from './modelLabels';
import type { CatalystCommand, WorkspaceVM } from './viewModels';
import type { ModelCapability } from './viewModels';

// ?? System Status ?????????????????????????????????????????????????????????????

export function useCatalystStatus() {
  return {
    status: useAppStore((s) => s.systemStatus),
    backendUrl: API_BASE,
    isOffline: useAppStore((s) => s.isOffline),
    startupError: useAppStore((s) => s.startupError),
    retry: useAppStore((s) => s.retryInit),
  };
}

// ?? Graph ?????????????????????????????????????????????????????????????????????

export function useCatalystGraph() {
  const nodes = useAppStore((s) => s.graphNodes);
  const edges = useAppStore((s) => s.graphEdges);
  const selectedNodeId = useAppStore((s) => s.selectedNodeId);
  const selectedEdgeId = useAppStore((s) => s.selectedEdgeId);
  const colorMode = useAppStore((s) => s.graphColorMode);
  const graphSettings = useAppStore((s) => s.graphSettings);
  const isLoading = useAppStore((s) => s.graphLoading);
  const error = useAppStore((s) => s.graphError);
  const selectNode = useAppStore((s) => s.selectNode);
  const selectGraphNode = useAppStore((s) => s.selectGraphNode);
  const selectEdge = useAppStore((s) => s.selectEdge);
  const setColorMode = useAppStore((s) => s.setGraphColorMode);
  const setGraphSettings = useAppStore((s) => s.setGraphSettings);
  const resetGraphSettings = useAppStore((s) => s.resetGraphSettings);
  const expandNeighborhood = useAppStore((s) => s.expandNeighborhood);

  const counts = {
    clusters: nodes.filter((n) => n.type === 'cluster').length,
    materials: nodes.filter((n) => n.type === 'material').length,
    elements: nodes.filter((n) => n.type === 'element').length,
    edges: edges.length,
  };

  return {
    nodes,
    edges,
    selectedNodeId,
    selectedEdgeId,
    colorMode,
    graphSettings,
    counts,
    isLoading,
    error,
    selectNode,
    selectGraphNode,
    selectEdge,
    setColorMode,
    setGraphSettings,
    resetGraphSettings,
    expandNeighborhood,
  };
}

// ?? Workspace ?????????????????????????????????????????????????????????????????

export function useCatalystWorkspace() {
  return {
    workspace: useAppStore((s) => s.workspace),
    isLoading: useAppStore((s) => s.workspaceLoading),
    error: useAppStore((s) => s.workspaceError),
    nodeDetail: useAppStore((s) => s.selectedGraphNodeDetail),
    nodeDetailLoading: useAppStore((s) => s.graphNodeDetailLoading),
    nodeDetailError: useAppStore((s) => s.graphNodeDetailError),
    edgeDetail: useAppStore((s) => s.edgeDetail),
    edgeLoading: useAppStore((s) => s.edgeLoading),
  };
}

export function useCatalystMaterialData() {
  return {
    structureById: useAppStore((s) => s.structureById),
    detailsById: useAppStore((s) => s.detailsById),
    structureLoadingById: useAppStore((s) => s.structureLoadingById),
    detailsLoadingById: useAppStore((s) => s.detailsLoadingById),
    structureErrorById: useAppStore((s) => s.structureErrorById),
    detailsErrorById: useAppStore((s) => s.detailsErrorById),
    loadMaterialStructure: useAppStore((s) => s.loadMaterialStructure),
    loadMaterialDetails: useAppStore((s) => s.loadMaterialDetails),
  };
}

// ?? Search ????????????????????????????????????????????????????????????????????

export function useCatalystSearch() {
  return {
    results: useAppStore((s) => s.searchResults),
    isLoading: useAppStore((s) => s.searchLoading),
    error: useAppStore((s) => s.searchError),
    filters: useAppStore((s) => s.searchFilters),
    runSearch: useAppStore((s) => s.runSearch),
    clearSearch: useAppStore((s) => s.clearSearch),
    screenResults: useAppStore((s) => s.screenResults),
    screenRequirement: useAppStore((s) => s.screenRequirement),
    screenLoading: useAppStore((s) => s.screenLoading),
    runScreen: useAppStore((s) => s.runScreen),
    clearScreen: useAppStore((s) => s.clearScreen),
  };
}

// ?? Agent ?????????????????????????????????????????????????????????????????????

/** Optional gateway presets when that provider is active. */
const MICRO_MODEL_PRESETS = ['auto/best-chat', 'auto/best-reasoning', 'auto/best-fast'];
/** Primary agent profiles (ids are internal; UI shows generic labels). */
const PRIMARY_MODEL_PRESETS = [
  'agy/3.5-flash-low',
  'agy/3.5-flash-medium',
  'agy/3.5-flash-high',
  'agy/3.1-pro-low',
  'agy/3.1-pro-high',
  'gemini-3.1-flash-lite',
  'gemini-2.5-flash',
  'gemini-2.5-pro',
];

/** Drop legacy gateway junk if it lingers in saved settings. */
const LEGACY_MODEL_BLOCKLIST = /minimax|omnirouter|omni[-_]?|abab|m2\.|claude-via-micro/i;

export function useCatalystAgent() {
  const systemStatus = useAppStore((s) => s.systemStatus);
  const rawSettings = useAppStore((s) => s.rawSettings);
  const updateSettings = useAppStore((s) => s.updateSettings);
  const providersRoot = rawSettings?.settings?.providers || rawSettings?.providers || {};
  const activeProvider = systemStatus.provider.activeProvider || providersRoot?.active_provider || null;
  const modelsMap = (providersRoot?.models || {}) as Record<string, string>;
  const configuredModel = activeProvider ? modelsMap[activeProvider] || null : null;
  const modelCapability: ModelCapability = {
    providerId: activeProvider,
    modelId: configuredModel || null,
    label: modelDisplayLabel(configuredModel) || providerDisplayLabel(activeProvider) || 'Agent model',
    supportsTools: true,
    supportsReasoning: true,
    reasoningEfforts: ['minimal', 'low', 'medium', 'high'],
    supportsImages: activeProvider === 'gemini' || String(activeProvider || '').includes('openai'),
    supportsAudio: false,
    supportsStreaming: true,
  };
  const availableModels = (() => {
    const isMicro = activeProvider === 'micro' || String(activeProvider || '').includes('micro');
    const presets = isMicro ? MICRO_MODEL_PRESETS : PRIMARY_MODEL_PRESETS;
    const fromSettings = isMicro
      ? Object.entries(modelsMap)
          .filter(([k, v]) => k === 'micro' && v)
          .map(([, v]) => String(v))
      : Object.entries(modelsMap)
          .filter(([k, v]) => k !== 'micro' && v && !LEGACY_MODEL_BLOCKLIST.test(String(v)))
          .map(([, v]) => String(v));
    const seed = configuredModel && !LEGACY_MODEL_BLOCKLIST.test(configuredModel) ? [configuredModel] : [];
    return Array.from(new Set([...seed, ...fromSettings, ...presets])).filter(
      (m) => !LEGACY_MODEL_BLOCKLIST.test(m),
    );
  })();

  return {
    messages: useAppStore((s) => s.agentMessages),
    isRunning: useAppStore((s) => s.agentLoading),
    error: useAppStore((s) => s.agentError),
    activity: useAppStore((s) => s.agentActivity),
    turnStartedAt: useAppStore((s) => s.agentTurnStartedAt),
    lastTurnDurationMs: useAppStore((s) => s.agentLastTurnDurationMs),
    modelCapability,
    availableModels,
    modelLabel: modelDisplayLabel,
    setModel: async (modelId: string) => {
      if (!activeProvider || !modelId.trim()) return;
      const next = modelId.trim();
      // Sync effort from profile suffix (?-high ? high).
      if (typeof window !== 'undefined' && (next.includes('high') || next.includes('low') || next.includes('medium'))) {
        const effort =
          next.includes('high') ? 'high' : next.includes('low') || next.includes('minimal') ? 'low' : 'medium';
        if (/-high|high\)|\/high/i.test(next) || next.endsWith('high')) {
          window.localStorage.setItem('catalyst-agent-effort', effort);
        } else if (next.includes('low') || next.includes('minimal')) {
          window.localStorage.setItem('catalyst-agent-effort', 'low');
        } else if (next.includes('medium')) {
          window.localStorage.setItem('catalyst-agent-effort', 'medium');
        }
      }
      await updateSettings({
        providers: {
          active_provider: activeProvider || 'gemini',
          models: {
            ...modelsMap,
            [activeProvider || 'gemini']: next,
          },
        },
      });
    },
    mode: systemStatus.provider.llmConfigured ? 'provider_backed' : 'deterministic_tool_agent',
    sessionId: useAppStore((s) => s.currentSessionId),
    sendMessage: useAppStore((s) => s.sendAgentMessage),
    clearMessages: useAppStore((s) => s.clearAgentMessages),
    newChat: useAppStore((s) => s.createSession),
  };
}

export function useCatalystProjects() {
  return {
    projects: useAppStore((s) => s.projects),
    activeProjectId: useAppStore((s) => s.activeProjectId),
    isLoading: useAppStore((s) => s.projectsLoading),
    error: useAppStore((s) => s.projectsError),
    loadProjects: useAppStore((s) => s.loadProjects),
    createProject: useAppStore((s) => s.createProject),
    selectProject: useAppStore((s) => s.selectProject),
    renameProject: useAppStore((s) => s.renameProject),
    deleteProject: useAppStore((s) => s.deleteProject),
  };
}

// ?? Candidates ????????????????????????????????????????????????????????????????

export function useCatalystCandidates() {
  const candidates = useAppStore((s) => s.candidates);
  const compareData = useAppStore((s) => s.compareData);
  const compareLoading = useAppStore((s) => s.compareLoading);
  const compareError = useAppStore((s) => s.compareError);

  return {
    candidates,
    compareData,
    compareLoading,
    compareError,
    canCompare: candidates.length >= 2,
    canExport: candidates.length > 0,
    addCandidate: useAppStore((s) => s.addCandidate),
    addCandidateRaw: useAppStore((s) => s.addCandidateRaw),
    removeCandidate: useAppStore((s) => s.removeCandidate),
    clearCandidates: useAppStore((s) => s.clearCandidates),
    runCompare: useAppStore((s) => s.runCompare),
    exportCandidates: useAppStore((s) => s.exportCandidates),
    exportSubgraph: useAppStore((s) => s.exportSubgraph),
  };
}

// ?? Research ??????????????????????????????????????????????????????????????????

export function useCatalystResearch() {
  return {
    research: useAppStore((s) => s.research),
    isLoading: useAppStore((s) => s.researchLoading),
    error: useAppStore((s) => s.researchError),
    runs: useAppStore((s) => s.researchRuns),
    runResearch: useAppStore((s) => s.runResearch),
    refresh: useAppStore((s) => s.loadResearchStatus),
  };
}

// ?? Settings ??????????????????????????????????????????????????????????????????

export function useCatalystSettings() {
  const systemStatus = useAppStore((s) => s.systemStatus);
  const rawSettings = useAppStore((s) => s.rawSettings);
  const updateSettings = useAppStore((s) => s.updateSettings);

  return {
    status: systemStatus,
    rawSettings: rawSettings?.settings || {},
    providerStatus: rawSettings?.provider_status || {},
    provider: systemStatus.provider,
    catalog: systemStatus.catalog,
    updateSettings,
  };
}

// ?? Sessions ??????????????????????????????????????????????????????????????????

export function useCatalystSessions() {
  return {
    sessions: useAppStore((s) => s.sessions),
    currentSessionId: useAppStore((s) => s.currentSessionId),
    isLoading: useAppStore((s) => s.sessionsLoading),
    createSession: useAppStore((s) => s.createSession),
    switchSession: useAppStore((s) => s.switchSession),
    renameSession: useAppStore((s) => s.renameSession),
    archiveSession: useAppStore((s) => s.archiveSession),
    deleteSession: useAppStore((s) => s.deleteSession),
    loadSessions: useAppStore((s) => s.loadSessions),
  };
}

// ?? Layout ????????????????????????????????????????????????????????????????????

export function useCatalystLayout() {
  return {
    activeSheet: useLayoutStore((s) => s.activeSheet),
    openSheet: useLayoutStore((s) => s.openSheet),
    closeSheet: useLayoutStore((s) => s.closeSheet),
    toggleSheet: useLayoutStore((s) => s.toggleSheet),
    searchMode: useLayoutStore((s) => s.searchMode),
    setSearchMode: useLayoutStore((s) => s.setSearchMode),
    searchOpen: useLayoutStore((s) => s.searchOpen),
    setSearchOpen: useLayoutStore((s) => s.setSearchOpen),
    graphControlsOpen: useLayoutStore((s) => s.graphControlsOpen),
    setGraphControlsOpen: useLayoutStore((s) => s.setGraphControlsOpen),
    candidateTrayExpanded: useLayoutStore((s) => s.candidateTrayExpanded),
    setCandidateTrayExpanded: useLayoutStore((s) => s.setCandidateTrayExpanded),
    railMode: useLayoutStore((s) => s.railMode),
    setRailMode: useLayoutStore((s) => s.setRailMode),
    workspaceTab: useLayoutStore((s) => s.workspaceTab),
    setWorkspaceTab: useLayoutStore((s) => s.setWorkspaceTab),
    hopDepth: useLayoutStore((s) => s.hopDepth),
    setHopDepth: useLayoutStore((s) => s.setHopDepth),
    genomicsCaseId: useLayoutStore((s) => s.genomicsCaseId),
    setGenomicsCaseId: useLayoutStore((s) => s.setGenomicsCaseId),
    genomicsVariantIndex: useLayoutStore((s) => s.genomicsVariantIndex),
    setGenomicsVariantIndex: useLayoutStore((s) => s.setGenomicsVariantIndex),
    genomicsRepeatCount: useLayoutStore((s) => s.genomicsRepeatCount),
    setGenomicsRepeatCount: useLayoutStore((s) => s.setGenomicsRepeatCount),
    genomicsResetNonce: useLayoutStore((s) => s.genomicsResetNonce),
    resetGenomicsCamera: useLayoutStore((s) => s.resetGenomicsCamera),
    genomeState: useLayoutStore((s) => s.genomeState),
    setGenomeState: useLayoutStore((s) => s.setGenomeState),
    setGenomeSelection: useLayoutStore((s) => s.setGenomeSelection),
    setGenomeViewport: useLayoutStore((s) => s.setGenomeViewport),
    genomeSequenceVisible: useLayoutStore((s) => s.genomeSequenceVisible),
    setGenomeSequenceVisible: useLayoutStore((s) => s.setGenomeSequenceVisible),
    inspectorOpen: useLayoutStore((s) => s.inspectorOpen),
    setInspectorOpen: useLayoutStore((s) => s.setInspectorOpen),
    toggleInspector: useLayoutStore((s) => s.toggleInspector),
    inspectorTab: useLayoutStore((s) => s.inspectorTab),
    setInspectorTab: useLayoutStore((s) => s.setInspectorTab),
    railExpanded: useLayoutStore((s) => s.railExpanded),
    setRailExpanded: useLayoutStore((s) => s.setRailExpanded),
    toggleRailExpanded: useLayoutStore((s) => s.toggleRailExpanded),
    theme: useLayoutStore((s) => s.theme),
    toggleTheme: useLayoutStore((s) => s.toggleTheme),
    setTheme: useLayoutStore((s) => s.setTheme),
    density: useLayoutStore((s) => s.density),
    setDensity: useLayoutStore((s) => s.setDensity),
  };
}


// ?? Command Executor ??????????????????????????????????????????????????????????

export function useCommandExecutor() {
  const selectEdge = useAppStore((s) => s.selectEdge);
  const expandNeighborhood = useAppStore((s) => s.expandNeighborhood);
  const runScreen = useAppStore((s) => s.runScreen);
  const addCandidate = useAppStore((s) => s.addCandidate);
  const removeCandidate = useAppStore((s) => s.removeCandidate);
  const runCompare = useAppStore((s) => s.runCompare);
  const exportSubgraph = useAppStore((s) => s.exportSubgraph);
  const runResearch = useAppStore((s) => s.runResearch);
  const sendAgentMessage = useAppStore((s) => s.sendAgentMessage);
  const applyUiActions = useAppStore((s) => s.applyUiActions);
  const openSheet = useLayoutStore((s) => s.openSheet);
  const setRailMode = useLayoutStore((s) => s.setRailMode);
  const setInspectorOpen = useLayoutStore((s) => s.setInspectorOpen);
  const setInspectorTab = useLayoutStore((s) => s.setInspectorTab);

  return async function executeCommand(cmd: CatalystCommand, workspace?: WorkspaceVM | null) {
    switch (cmd.type) {
      case 'open_material':
        await applyUiActions([
          { type: 'select_node', material_id: cmd.materialId },
          { type: 'open_inspector', material_id: cmd.materialId },
        ]);
        break;
      case 'expand_neighborhood':
        await expandNeighborhood(cmd.materialId);
        break;
      case 'inspect_edge':
        await selectEdge(cmd.edgeId);
        openSheet('edge');
        break;
      case 'screen_candidates':
        await runScreen(cmd.requirement);
        setRailMode('candidates');
        break;
      case 'compare_candidates':
        await runCompare();
        setRailMode('candidates');
        break;
      case 'add_candidate':
        if (workspace) addCandidate(workspace);
        break;
      case 'remove_candidate':
        removeCandidate(cmd.materialId);
        break;
      case 'export_subgraph':
        await exportSubgraph(cmd.materialIds);
        break;
      case 'start_research':
        await runResearch(cmd.query, cmd.context);
        setRailMode('add_material');
        break;
      case 'open_settings':
        setRailMode('settings');
        break;
      case 'ask_agent':
        await sendAgentMessage(cmd.message);
        setInspectorOpen(true);
        setInspectorTab('agent');
        break;
    }
  };
}

// ?? Toasts ????????????????????????????????????????????????????????????????????

export function useCatalystToasts() {
  return {
    toasts: useAppStore((s) => s.toasts),
    addToast: useAppStore((s) => s.addToast),
    removeToast: useAppStore((s) => s.removeToast),
  };
}
