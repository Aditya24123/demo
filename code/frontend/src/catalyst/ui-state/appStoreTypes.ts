import type {
  SystemStatusVM,
  GraphNodeVM,
  GraphNodeDetail,
  GraphEdgeVM,
  GraphSettingsVM,
  WorkspaceVM,
  AgentMessageVM,
  CandidateRowVM,
  EdgeVM,
  ResearchVM,
  SessionVM,
  CompareVM,
  ProjectVM,
} from '../bridge/viewModels';

export type Toast = { id: string; message: string; type: 'error' | 'info' | 'success' | 'warning' };

export type AgentAttachment = {
  name: string;
  mime_type: string;
  data: string;
};

export const DEFAULT_GRAPH_SETTINGS: GraphSettingsVM = {
  search: '',
  showClusters: false,
  showMaterials: true,
  showElements: true,
  showOrphans: true,
  showLabels: true,
  showArrows: false,
  showEdgeLabels: false,
  nodeSize: 1.0,
  linkThickness: 0.9,
  textFadeThreshold: 1.35,
  collisionPadding: 10,
  collisionStrength: 0.95,
  collisionIterations: 4,
  chargeDistanceMin: 24,
  chargeDistanceMax: 210,
  localRepelBoost: 2.15,
  clusterSpread: 1.75,
  centerForce: 0.34,
  repelForce: 58,
  linkForce: 0.42,
  linkDistance: 58,
  motion: 'subtle',
  edgeDensity: 'normal',
  localDepth: 1,
  groups: [],
};

export const DEFAULT_STATUS: SystemStatusVM = {
  api: 'checking',
  backendLabel: 'Catalyst backend',
  provider: { llmConfigured: false, activeProvider: null, researchSources: {} },
};

export const ACTIVE_PROJECT_STORAGE_KEY = 'catalyst.activeProjectId';

export interface AppState {
  systemStatus: SystemStatusVM;
  isOffline: boolean;
  startupError: string | null;
  rawSettings: any;
  rawCatalog: any;
  rawHealth: any;

  projects: ProjectVM[];
  projectsLoading: boolean;
  projectsError: string | null;
  activeProjectId: string | null;

  graphNodes: GraphNodeVM[];
  graphEdges: GraphEdgeVM[];
  neighborhoodByKey: Record<string, { nodes: GraphNodeVM[]; edges: GraphEdgeVM[]; depth: number }>;
  neighborhoodLoadingKey: string | null;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  graphColorMode: 'type' | 'stability' | 'band_gap' | 'element';
  graphSettings: GraphSettingsVM;
  graphLoading: boolean;
  graphError: string | null;
  selectedGraphNodeDetail: GraphNodeDetail | null;
  graphNodeDetailLoading: boolean;
  graphNodeDetailError: string | null;

  workspace: WorkspaceVM | null;
  workspaceLoading: boolean;
  workspaceError: string | null;
  structureById: Record<string, any>;
  detailsById: Record<string, any>;
  structureLoadingById: Record<string, boolean>;
  detailsLoadingById: Record<string, boolean>;
  structureErrorById: Record<string, string | null>;
  detailsErrorById: Record<string, string | null>;

  edgeDetail: EdgeVM | null;
  edgeLoading: boolean;
  edgeError: string | null;

  searchResults: CandidateRowVM[];
  searchLoading: boolean;
  searchError: string | null;
  searchFilters: Record<string, any>;

  screenResults: CandidateRowVM[];
  screenRequirement: string;
  screenLoading: boolean;
  screenError: string | null;

  agentMessages: AgentMessageVM[];
  agentLoading: boolean;
  agentError: string | null;
  agentActivity: string | null;
  agentTurnStartedAt: number | null;
  agentLastTurnDurationMs: number | null;

  candidates: CandidateRowVM[];
  compareData: CompareVM | null;
  compareLoading: boolean;
  compareError: string | null;

  research: ResearchVM | null;
  researchLoading: boolean;
  researchError: string | null;
  researchRuns: Record<string, any>;

  sessions: SessionVM[];
  currentSessionId: string | null;
  sessionsLoading: boolean;

  toasts: Toast[];

  initialize: () => Promise<void>;
  selectNode: (id: string | null) => Promise<void>;
  prefetchMaterialWorkspace: (materialId: string) => Promise<void>;
  selectGraphNode: (id: string) => Promise<void>;
  selectEdge: (id: string | null) => Promise<void>;
  expandNeighborhood: (
    materialId: string,
    options?: { depth?: number; limit_nodes?: number; silent?: boolean; force?: boolean },
  ) => Promise<void>;
  applyUiActions: (actions: Array<Record<string, unknown>> | null | undefined) => Promise<void>;
  loadMaterialStructure: (materialId: string, force?: boolean) => Promise<any>;
  loadMaterialDetails: (
    materialId: string,
    options?: { sections?: string[]; limit?: number; downsample?: boolean; force?: boolean },
  ) => Promise<any>;
  runSearch: (query: string, filters?: Record<string, any>) => Promise<CandidateRowVM[]>;
  clearSearch: () => void;
  runScreen: (requirement: string) => Promise<CandidateRowVM[]>;
  clearScreen: () => void;
  sendAgentMessage: (text: string, attachments?: AgentAttachment[]) => Promise<void>;
  loadProjects: () => Promise<void>;
  createProject: (input: { name: string; description?: string }) => Promise<ProjectVM>;
  selectProject: (projectId: string | null) => void;
  renameProject: (projectId: string, name: string) => Promise<void>;
  deleteProject: (projectId: string) => Promise<void>;
  clearAgentMessages: () => void;
  addCandidate: (workspace: WorkspaceVM) => void;
  addCandidateRaw: (raw: any) => void;
  removeCandidate: (materialId: string) => void;
  clearCandidates: () => void;
  runCompare: () => Promise<void>;
  exportSubgraph: (materialIds?: string[]) => Promise<void>;
  exportCandidates: (format?: 'json' | 'csv') => Promise<void>;
  loadResearchStatus: () => Promise<void>;
  runResearch: (query: string, context?: any) => Promise<void>;
  loadSessions: () => Promise<void>;
  createSession: () => Promise<string>;
  switchSession: (id: string) => Promise<void>;
  renameSession: (id: string, title: string) => Promise<void>;
  archiveSession: (id: string, archived?: boolean) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  clearAllSessions: () => Promise<void>;
  updateSettings: (body: Record<string, unknown>) => Promise<void>;
  setGraphColorMode: (mode: AppState['graphColorMode']) => void;
  setGraphSettings: (patch: Partial<GraphSettingsVM>) => void;
  resetGraphSettings: () => void;
  addToast: (message: string, type?: Toast['type']) => void;
  removeToast: (id: string) => void;
  retryInit: () => Promise<void>;
}
