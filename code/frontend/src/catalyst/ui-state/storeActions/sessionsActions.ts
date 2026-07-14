// @ts-nocheck
import { api } from '@/lib/api';
import { normalizeAgentMessage, normalizeSession } from '../../bridge/normalizers';
import type { SessionVM } from '../../bridge/viewModels';
import type { AppState } from '../appStoreTypes';
import { useLayoutStore } from '../layoutStore';

type SetState = any;
type GetState = any;

export function createSessionActions(set: SetState, get: GetState): Partial<AppState> {
  return {
  loadSessions: async () => {
    set({ sessionsLoading: true });
    try {
      const data = await api.getSessions();
      const sessions = (data?.sessions || []).map(normalizeSession);
      set({ sessions, sessionsLoading: false });
    } catch {
      set({ sessionsLoading: false });
    }
  },

  createSession: async () => {
    // Stay on current rail (notebook/graph/home). Only open the agent inspector ?
    // never yank the user out of project notebook into the materials workspace.
    const layout = useLayoutStore.getState();
    layout.setInspectorOpen(true);
    layout.setInspectorTab('agent');
    try {
      const activeProjectId = get().activeProjectId;
      const s = await api.createSession({
        title: 'New chat',
        context: activeProjectId ? { project_id: activeProjectId } : {},
      });
      const ns = normalizeSession(s);
      if (!ns.id) throw new Error('Session create returned no id');
      set((state) => ({
        sessions: [ns, ...state.sessions.filter((item) => item.id !== ns.id)],
        currentSessionId: ns.id,
        agentMessages: [],
        agentLoading: false,
        agentError: null,
        agentActivity: null,
      }));
      get().addToast('New chat started', 'success');
      return ns.id;
    } catch (err) {
      console.error('createSession failed', err);
      const id = `local-${Date.now()}`;
      const local: SessionVM = { id, title: 'New chat (offline)', messageCount: 0 };
      set((state) => ({
        sessions: [local, ...state.sessions],
        currentSessionId: id,
        agentMessages: [],
        agentLoading: false,
        agentError: null,
        agentActivity: null,
      }));
      get().addToast('New chat started offline', 'warning');
      return id;
    }
  },

  switchSession: async (id) => {
    if (!id) return;
    // Preserve current rail mode (notebook stays notebook). Only focus agent panel.
    const layout = useLayoutStore.getState();
    layout.setInspectorOpen(true);
    layout.setInspectorTab('agent');
    // Always re-hydrate from server when switching ? even if already current
    // (avoids stuck empty transcripts after HMR / partial failures).
    set({
      currentSessionId: id,
      agentMessages: [],
      agentLoading: true,
      agentError: null,
      agentActivity: null,
    });
    if (id.startsWith('local-')) {
      set({ agentLoading: false });
      return;
    }
    try {
      const session = await api.getSession(id);
      const messages = (session?.messages || [])
        .filter((message: any) => ['user', 'assistant', 'error'].includes(String(message?.role)))
        .map((message: any) =>
          normalizeAgentMessage(
            {
              ...message,
              text: message.text || message.content || '',
            },
            message.role === 'user' ? 'user' : message.role === 'error' ? 'error' : 'assistant',
          ),
        );
      set({ agentMessages: messages, agentLoading: false });
      const projectId = session?.context?.project_id;
      if (projectId) get().selectProject(String(projectId));
      // Only jump material workspace when already on home materials surface ?
      // never force notebook users into a material select.
      const rail = useLayoutStore.getState().railMode;
      const materialId =
        session?.context?.current_material_id ||
        session?.context?.material_id ||
        session?.context?.last_focus_material_id;
      if (materialId && rail === 'home') {
        await get().selectNode(String(materialId));
      }
    } catch (err) {
      console.error('switchSession failed', err);
      set({ agentLoading: false });
      get().addToast('Could not open chat history', 'error');
    }
  },

  renameSession: async (id, title) => {
    const next = title.trim().slice(0, 80);
    if (!id || !next) return;
    set((state) => ({
      sessions: state.sessions.map((session) => (session.id === id ? { ...session, title: next } : session)),
    }));
    if (id.startsWith('local-')) return;
    try {
      await api.patchSession(id, { title: next });
    } catch {
      get().addToast('Could not rename chat', 'error');
      void get().loadSessions();
    }
  },

  archiveSession: async (id, archived = true) => {
    if (!id) return;
    set((state) => ({
      sessions: state.sessions.map((session) => (session.id === id ? { ...session, archived } : session)),
    }));
    if (id.startsWith('local-')) return;
    try {
      await api.patchSession(id, { context: { archived } });
      get().addToast(archived ? 'Chat archived' : 'Chat restored', 'success');
    } catch {
      get().addToast('Could not archive chat', 'error');
      void get().loadSessions();
    }
  },

  deleteSession: async (id) => {
    if (!id) return;
    const wasCurrent = get().currentSessionId === id;
    set((state) => ({ sessions: state.sessions.filter((session) => session.id !== id) }));
    if (!id.startsWith('local-')) {
      try {
        await api.deleteSession(id);
      } catch {
        get().addToast('Could not delete chat', 'error');
        void get().loadSessions();
        return;
      }
    }
    if (wasCurrent) {
      const remaining = get().sessions.filter((session) => !session.archived);
      if (remaining[0]) {
        await get().switchSession(remaining[0].id);
      } else {
        await get().createSession();
      }
    }
    get().addToast('Chat deleted', 'success');
  },

  clearAllSessions: async () => {
    await get().loadSessions();
    const ids = get().sessions.map((session) => session.id);
    for (const id of ids) {
      if (!id.startsWith('local-')) {
        try {
          await api.deleteSession(id);
        } catch {
          /* continue clearing */
        }
      }
    }
    set({ sessions: [], currentSessionId: null, agentMessages: [] });
    await get().createSession();
    get().addToast('All chats cleared', 'success');
  },

  };
}
