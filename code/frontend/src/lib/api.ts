/** Local monorepo default (backend on 8766). Override via VITE_CATALYST_API_BASE or runtime-config.json
 *  (e.g. https://mini.tail3bfb03.ts.net:8766 for the remote mini box). */
const LOCAL_API_BASE = 'http://127.0.0.1:8766';
const defaultApiBase = window.location.port === '5173' ? LOCAL_API_BASE : '';
const buildApiBase = import.meta.env.VITE_CATALYST_API_BASE || '';

type RuntimeConfig = {
  apiBaseUrl?: string;
};

let apiBasePromise: Promise<string> | null = null;

export async function getApiBase(): Promise<string> {
  if (buildApiBase) return buildApiBase;
  if (!apiBasePromise) {
    apiBasePromise = fetch(`${import.meta.env.BASE_URL}runtime-config.json`, { cache: 'no-store' })
      .then(async (res) => {
        if (!res.ok) return defaultApiBase;
        const config = (await res.json()) as RuntimeConfig;
        const fromConfig = (config.apiBaseUrl || '').trim();
        return fromConfig || defaultApiBase;
      })
      .catch(() => defaultApiBase);
  }
  return apiBasePromise;
}

export const API_BASE = buildApiBase || defaultApiBase;

/** Resolve ws(s):// base for live voice and other sockets. */
export async function getWsBase(): Promise<string> {
  const base = (await getApiBase()) || (window.location.port === '5173' ? LOCAL_API_BASE : window.location.origin);
  try {
    const url = new URL(base, window.location.origin);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return url.origin;
  } catch {
    return 'ws://127.0.0.1:8766';
  }
}

// ??? typed fetch helper ????????????????????????????????????????????????????
async function apiFetch<T = any>(path: string, init?: RequestInit): Promise<T> {
  const apiBase = await getApiBase();
  const res = await fetch(`${apiBase}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail || body?.error?.message || detail;
    } catch {/* ignore */}
    throw Object.assign(new Error(detail), { status: res.status });
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

const jsonPatch = (body: unknown) => ({
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

const jsonPut = (body: unknown) => ({
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

// ??? System ????????????????????????????????????????????????????????????????
export const api = {
  // Startup health check
  getHealth: () =>
    apiFetch('/health'),

  // Dataset capabilities / counts
  getCatalog: () =>
    apiFetch('/catalog'),

  // Runtime settings + provider / research source status
  getSettings: () =>
    apiFetch('/settings'),

  getSettingsSchema: () =>
    apiFetch('/settings/schema'),

  patchSettings: (body: Record<string, unknown>) =>
    apiFetch('/settings', jsonPatch(body)),

  // Curated, offline-safe DNA Variant Explorer demo records.
  getGenomicsCases: () =>
    apiFetch('/genomics/cases'),

  getGenomicsCase: (caseId: 'brca1' | 'hbb' | 'ctg', repeatCount?: number) =>
    apiFetch(`/genomics/cases/${encodeURIComponent(caseId)}${repeatCount === undefined ? '' : `?repeat_count=${repeatCount}`}`),

  getGenomeState: (gene: string, options: { visibleStart?: number; visibleEnd?: number; selectedPosition?: number } = {}) => {
    const params = new URLSearchParams();
    if (options.visibleStart) params.set('visible_start', String(options.visibleStart));
    if (options.visibleEnd) params.set('visible_end', String(options.visibleEnd));
    if (options.selectedPosition) params.set('selected_position', String(options.selectedPosition));
    const query = params.toString();
    return apiFetch(`/genomics/state/${encodeURIComponent(gene)}${query ? `?${query}` : ''}`);
  },

  // Projects are server-owned workspaces, separate from the material snapshot.
  getProjects: (includeArchived = false) =>
    apiFetch(`/projects?include_archived=${String(includeArchived)}`),

  createProject: (body: { name: string; description?: string }) =>
    apiFetch('/projects', json(body)),

  getProject: (projectId: string) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}`),

  patchProject: (projectId: string, body: { name?: string; description?: string }) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}`, jsonPatch(body)),

  archiveProject: (projectId: string) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}/archive`, json({})),

  deleteProject: (projectId: string) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}`, { method: 'DELETE' }),

  createProjectFolder: (projectId: string, path: string) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}/folders`, json({ path })),

  getProjectWorkspace: (projectId: string) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}/workspace`),

  getProjectNotebook: (projectId: string) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}/notebook`),

  putProjectNotebook: (projectId: string, content: string) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}/notebook`, jsonPut({ content })),

  getProjectFile: (projectId: string, path: string) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}/files/${path.split('/').map(encodeURIComponent).join('/')}`),

  putProjectFile: (projectId: string, path: string, content: string) =>
    apiFetch(
      `/projects/${encodeURIComponent(projectId)}/files/${path.split('/').map(encodeURIComponent).join('/')}`,
      jsonPut({ content }),
    ),

  getProjectRuns: (projectId: string, limit = 50) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}/runs?limit=${limit}`),

  runProjectCodex: (projectId: string, body: { prompt: string; model?: string; reasoning_effort?: string }) =>
    apiFetch(`/projects/${encodeURIComponent(projectId)}/codex/run`, json(body)),

  // ??? Graph ??????????????????????????????????????????????????????????????
  getOverview: (limit_clusters = 250) =>
    apiFetch(`/graph/overview?limit_clusters=${limit_clusters}`),

  getGraphView: (limit_nodes = 500, mode = 'overview', include_elements = false, include_clusters = false) => {
    const params = new URLSearchParams({
      mode,
      limit_nodes: String(limit_nodes),
      include_elements: String(include_elements),
      include_clusters: String(include_clusters),
    });
    return apiFetch(`/graph/view?${params}`);
  },

  getMaterialGraph: (limit_materials = 10000, include_elements = true, include_clusters = true) => {
    const params = new URLSearchParams({
      limit_materials: String(limit_materials),
      include_elements: String(include_elements),
      include_clusters: String(include_clusters),
    });
    return apiFetch(`/graph/materials?${params}`);
  },
    
  getGraphNode: (node_id: string) =>
    apiFetch(`/graph/nodes/${encodeURIComponent(node_id)}`),

  getRandomMaterial: (mode: 'curated' | 'any' = 'curated') =>
    apiFetch(`/materials/random?mode=${mode}`),

  getMaterial: (material_id: string) =>
    apiFetch(`/materials/${encodeURIComponent(material_id)}`),

  getWorkspace: (material_id: string) =>
    apiFetch(`/materials/${encodeURIComponent(material_id)}/workspace`),

  getEvidence: (material_id: string) =>
    apiFetch(`/materials/${encodeURIComponent(material_id)}/evidence`),

  getNeighborhood: (material_id: string, depth = 1, limit_nodes = 80) => {
    const params = new URLSearchParams({
      depth: String(depth),
      limit_nodes: String(limit_nodes),
    });
    return apiFetch(`/materials/${encodeURIComponent(material_id)}/neighborhood?${params}`);
  },

  getStructure: (material_id: string) =>
    apiFetch(`/materials/${encodeURIComponent(material_id)}/structure`),

  getMaterialDetails: (
    material_id: string,
    options: { sections?: string[]; limit?: number; downsample?: boolean } = {},
  ) => {
    const params = new URLSearchParams();
    if (options.sections?.length) params.set('sections', options.sections.join(','));
    if (options.limit !== undefined) params.set('limit', String(options.limit));
    if (options.downsample !== undefined) params.set('downsample', String(options.downsample));
    const query = params.toString();
    return apiFetch(`/materials/${encodeURIComponent(material_id)}/details${query ? `?${query}` : ''}`);
  },

  /** Selected-material only enrich (local-first + optional single MP pull). */
  enrichMaterial: (material_id: string, options: { force?: boolean; refresh?: boolean } = {}) => {
    const params = new URLSearchParams();
    if (options.force) params.set('force', 'true');
    if (options.refresh) params.set('refresh', 'true');
    const query = params.toString();
    const path = `/materials/${encodeURIComponent(material_id)}/enrich${query ? `?${query}` : ''}`;
    return options.force ? apiFetch(path, { method: 'POST' }) : apiFetch(path);
  },

  getMaterialCapabilities: (material_id: string) =>
    apiFetch(`/materials/${encodeURIComponent(material_id)}/capabilities`),

  // Edge IDs can contain ':' ? backend uses :path param so encode carefully
  getEdge: (edge_id: string) =>
    apiFetch(`/edges/${encodeURIComponent(edge_id)}`),

  // ??? Search ?????????????????????????????????????????????????????????????
  search: (query: string, filters: Record<string, unknown> = {}) => {
    const params = new URLSearchParams({ limit: '20' });
    if (query) params.set('query', query);
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') params.set(k, String(v));
    });
    return apiFetch(`/search?${params}`);
  },

  // ??? Screening & Compare ????????????????????????????????????????????????
  screen: (body: {
    requirement: string;
    context?: { session_id?: string; current_material_id?: string; candidate_set_id?: string };
    options?: { limit?: number; include_research_candidates?: boolean; strict_required_properties?: boolean };
  }) => apiFetch('/screen', json(body)),

  compare: (body: { material_ids: string[]; include_evidence?: boolean; include_edges?: boolean }) =>
    apiFetch('/compare', json(body)),

  // ??? Candidate Sets ?????????????????????????????????????????????????????
  createCandidateSet: (body: { session_id: string; title: string; requirement?: string; candidates?: unknown[] }) =>
    apiFetch('/candidate-sets', json(body)),

  getCandidateSet: (id: string) =>
    apiFetch(`/candidate-sets/${id}`),

  patchCandidateSet: (id: string, body: Record<string, unknown>) =>
    apiFetch(`/candidate-sets/${id}`, jsonPatch(body)),

  // ??? Export ?????????????????????????????????????????????????????????????
  exportSubgraph: (body: { material_ids: string[]; include_evidence?: boolean; include_edge_details?: boolean; format?: 'json' }) =>
    apiFetch('/export/subgraph', json(body)),

  exportCandidates: (body: { candidate_set_id?: string; material_ids?: string[]; format: 'json' | 'csv' }) =>
    apiFetch('/export/candidates', json(body)),

  // ??? Agent ??????????????????????????????????????????????????????????????
  getAgentTools: () =>
    apiFetch('/agent/tools'),

  agentChat: (body: {
    session_id: string;
    message: string;
    current_workspace?: {
      agent_surface?: 'materials' | 'project';
      rail_mode?: string;
      project_id?: string;
      project_name?: string;
      material_id?: string;
      formula_pretty?: string;
      chemsys?: string;
      workspace_tab?: string | null;
      hop_depth?: number;
      selected_edge_id?: string | null;
      candidate_set_id?: string;
      visible_material_ids?: string[];
    };
    attachments?: unknown[];
    stream?: boolean;
  }) => apiFetch('/agent/chat', json(body)),

  /** Live SSE agent stream: status / token / done / error. */
  agentChatStream: async (
    body: {
      session_id: string;
      message: string;
      current_workspace?: Record<string, unknown>;
      attachments?: unknown[];
    },
    handlers: {
      onStatus?: (text: string) => void;
      onToken?: (text: string) => void;
      onDone?: (response: any) => void;
      onError?: (message: string) => void;
    } = {},
  ) => {
    const apiBase = await getApiBase();
    const res = await fetch(`${apiBase}/agent/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body),
    });
    if (!res.ok || !res.body) {
      let detail = res.statusText;
      try {
        const errBody = await res.json();
        detail = errBody?.detail || errBody?.error?.message || detail;
      } catch {
        /* ignore */
      }
      throw Object.assign(new Error(detail), { status: res.status });
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      for (const part of parts) {
        const line = part
          .split('\n')
          .map((l) => l.trim())
          .find((l) => l.startsWith('data:'));
        if (!line) continue;
        const raw = line.slice(5).trim();
        if (!raw || raw === '[DONE]') continue;
        let event: any;
        try {
          event = JSON.parse(raw);
        } catch {
          continue;
        }
        if (event.type === 'status' && event.text) handlers.onStatus?.(String(event.text));
        else if (event.type === 'token' && event.text) handlers.onToken?.(String(event.text));
        else if (event.type === 'done') handlers.onDone?.(event.response || event);
        else if (event.type === 'error') handlers.onError?.(String(event.message || 'Stream failed'));
      }
    }
  },

  confirmAction: (action_id: string) =>
    apiFetch(`/agent/actions/${action_id}/confirm`, json({})),

  // ??? Sessions ???????????????????????????????????????????????????????????
  getSessions: () =>
    apiFetch('/sessions'),

  createSession: (body: Record<string, unknown> = {}) =>
    apiFetch('/sessions', json(body)),

  getSession: (id: string) =>
    apiFetch(`/sessions/${id}`),

  patchSession: (id: string, body: Record<string, unknown>) =>
    apiFetch(`/sessions/${id}`, jsonPatch(body)),

  deleteSession: (id: string) =>
    apiFetch(`/sessions/${id}`, { method: 'DELETE' }),

  // ??? Research ???????????????????????????????????????????????????????????
  getResearchStatus: () =>
    apiFetch('/research/status'),

  researchQuery: (body: {
    session_id: string;
    query: string;
    context?: { current_material_id?: string; requirement?: string; missing_properties?: string[] };
    sources?: string[];
  }) => apiFetch('/research/query', json(body)),

  getResearchRun: (run_id: string) =>
    apiFetch(`/research/runs/${run_id}`),
};
