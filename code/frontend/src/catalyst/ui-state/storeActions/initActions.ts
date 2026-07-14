// @ts-nocheck
import { api } from '@/lib/api';
import {
  normalizeEdge,
  normalizeNode,
  normalizeSession,
  normalizeSystemStatus,
  normalizeWorkspace,
} from '../../bridge/normalizers';
import { toCatalystError } from '../../bridge/errors';
import { DEFAULT_STATUS, type AppState } from '../appStoreTypes';

type SetState = any;
type GetState = any;

export function createInitActions(set: SetState, get: GetState): Partial<AppState> {
  return {
  initialize: async () => {
    // Guard against React StrictMode / remount double-init storming the single-worker API.
    if ((get() as any)._initInFlight) return;
    (get() as any)._initInFlight = true;
    set({ isOffline: false, startupError: null, systemStatus: { ...DEFAULT_STATUS, api: 'checking' }, graphLoading: true });

    try {
      // 1. Health check
      let health: any = null;
      try {
        health = await api.getHealth();
        set({ rawHealth: health });
      } catch {
        set({
          isOffline: true,
          startupError: `Cannot reach the Catalyst backend at ${API_BASE}`,
          systemStatus: { ...DEFAULT_STATUS, api: 'offline' },
          graphLoading: false,
        });
        return;
      }

      // 2. Parallel: catalog + settings + sessions (do not wait on graph for sessions)
      const [catalogResult, settingsResult, sessionsResult] = await Promise.allSettled([
        api.getCatalog(),
        api.getSettings(),
        api.getSessions(),
      ]);
      const catalog = catalogResult.status === 'fulfilled' ? catalogResult.value : null;
      const settingsResp = settingsResult.status === 'fulfilled' ? settingsResult.value : null;

      set({
        rawCatalog: catalog,
        rawSettings: settingsResp,
        systemStatus: normalizeSystemStatus(health, catalog, settingsResp),
      });

      void get().loadProjects().catch(() => {});

      // 3. Sessions
      try {
        if (sessionsResult.status === 'fulfilled') {
          const sessions = (sessionsResult.value?.sessions || []).map(normalizeSession);
          set({ sessions, sessionsLoading: false });
          if (sessions.length === 0) {
            const newSession = await api.createSession({ title: 'Session 1' });
            const ns = normalizeSession(newSession);
            set({ sessions: [ns], currentSessionId: ns.id });
          } else if (!get().currentSessionId) {
            set({ currentSessionId: sessions[0].id });
          }
        } else {
          set({ currentSessionId: get().currentSessionId || `local-${Date.now()}`, sessionsLoading: false });
        }
      } catch {
        set({ currentSessionId: get().currentSessionId || `local-${Date.now()}`, sessionsLoading: false });
      }

      // 4. Smaller graph slice ? 600+elements was heavy on the single worker
      try {
        const graph = await api.getGraphView(220, 'overview', false, true);
        const nodes = (graph.nodes || []).map(normalizeNode);
        const edges = (graph.edges || graph.links || []).map(normalizeEdge);
        set({ graphNodes: nodes, graphEdges: edges, graphLoading: false, graphError: null });
      } catch {
        try {
          const overview = await api.getOverview(120);
          const nodes = (overview.nodes || []).map(normalizeNode);
          const edges = (overview.edges || overview.links || []).map(normalizeEdge);
          set({ graphNodes: nodes, graphEdges: edges, graphLoading: false, graphError: null });
        } catch {
          set({ graphLoading: false, graphError: 'Failed to load graph' });
          get().addToast('Failed to load graph', 'error');
        }
      }

      // 5. Initial material (non-blocking for UI shell)
      try {
        const random = await api.getRandomMaterial('curated');
        if (random?.material_id && !get().selectedNodeId && !get().workspace) {
          void get().selectNode(random.material_id);
        }
      } catch { /* non-critical */ }

      void get().loadResearchStatus().catch(() => {});
    } finally {
      (get() as any)._initInFlight = false;
    }
  },

  retryInit: () => get().initialize(),

  };
}
