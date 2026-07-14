// @ts-nocheck
import { api } from '@/lib/api';
import { buildAgentWorkspaceContext } from '../agentContext';
import { useLayoutStore } from '../layoutStore';
import { normalizeAgentMessage, normalizeCandidateFromRaw } from '../../bridge/normalizers';
import type { AgentAttachment, AppState } from '../appStoreTypes';

type SetState = any;
type GetState = any;

export function createAgentActions(set: SetState, get: GetState): Partial<AppState> {
  return {
  sendAgentMessage: async (text, attachments = []) => {
    const sessionId = get().currentSessionId || 'default';
    const userMsg = normalizeAgentMessage({ text, timestamp: Date.now() }, 'user');
    const streamId = `stream-${Date.now()}`;
    const startedAt = Date.now();
    set((s) => ({
      agentMessages: [
        ...s.agentMessages,
        userMsg,
        normalizeAgentMessage({ id: streamId, text: '', timestamp: Date.now() }, 'assistant'),
      ],
      agentLoading: true,
      agentError: null,
      agentActivity: 'Thinking?',
      agentTurnStartedAt: startedAt,
      agentLastTurnDurationMs: null,
    }));

    const activeSession = get().sessions.find((session) => session.id === sessionId);
    if (activeSession && (activeSession.messageCount || 0) === 0) {
      const title = text.trim().replace(/\s+/g, ' ').slice(0, 52) || 'New chat';
      set((state) => ({
        sessions: state.sessions.map((session) => (session.id === sessionId ? { ...session, title, messageCount: 1 } : session)),
      }));
      if (!sessionId.startsWith('local-')) void api.patchSession(sessionId, { title }).catch(() => {});
    }

    const layout = useLayoutStore.getState();
    const ws = get().workspace;
    const activeProjectId = get().activeProjectId;
    const project = get().projects.find((item) => item.projectId === activeProjectId) || null;
    const agentEffort =
      (typeof window !== 'undefined' && window.localStorage.getItem('catalyst-agent-effort')) || 'medium';
    const providersRoot = get().rawSettings?.settings?.providers || get().rawSettings?.providers || {};
    const modelsMap = (providersRoot?.models || {}) as Record<string, string>;
    const activeProvider = providersRoot?.active_provider || 'gemini';
    const agentModelProfile = modelsMap[activeProvider] || modelsMap.gemini || null;
    const currentWorkspace = buildAgentWorkspaceContext({
      railMode: layout.railMode,
      hopDepth: layout.hopDepth,
      workspaceTab: layout.workspaceTab,
      activeProjectId,
      projectName: project?.name,
      materialId: ws?.resolvedMaterialId,
      formulaPretty: ws?.title,
      chemsys: ws?.subtitle,
      visibleMaterialIds: get()
        .graphNodes.filter((n) => n.type === 'material')
        .slice(0, 20)
        .map((n) => n.id),
      selectedEdgeId: get().selectedEdgeId,
      agentEffort,
      agentModelProfile,
      genomicsCaseId: layout.genomicsCaseId,
      genomicsVariantIndex: layout.genomicsVariantIndex,
      genomicsRepeatCount: layout.genomicsRepeatCount,
      genomeState: layout.genomeState,
    });

    const patchStreamText = (chunk: string) => {
      set((s) => ({
        agentMessages: s.agentMessages.map((msg) =>
          msg.id === streamId ? { ...msg, text: `${msg.text || ''}${chunk}` } : msg,
        ),
      }));
    };

    const finishFromChatResponse = async (response: any) => {
      const rawMsg = response?.assistant_message || {};
      const finalText = String(rawMsg.text || rawMsg.content || '');
      set((s) => ({
        agentMessages: s.agentMessages.map((msg) => {
          if (msg.id !== streamId) return msg;
          return normalizeAgentMessage(
            {
              ...rawMsg,
              id: rawMsg.id || streamId,
              text: finalText || msg.text,
              candidateResults: response?.candidate_results || rawMsg.candidateResults,
              actions: response?.actions || rawMsg.actions,
              ui_actions: response?.ui_actions || rawMsg.ui_actions,
            },
            'assistant',
          );
        }),
        agentLoading: false,
        agentActivity: null,
        agentTurnStartedAt: null,
        agentLastTurnDurationMs: Date.now() - (s.agentTurnStartedAt || startedAt),
        currentSessionId: response?.session_id || s.currentSessionId,
      }));

      if (response?.candidate_results?.length) {
        set({
          screenResults: response.candidate_results.map(normalizeCandidateFromRaw),
          screenRequirement: text,
        });
      }
      const uiActions = response?.ui_actions || rawMsg.ui_actions || [];
      if (uiActions.length) await get().applyUiActions(uiActions);
    };

    try {
      let sawTokens = false;
      let sawDone = false;
      const streamController = new AbortController();
      const resetListener = () => streamController.abort();
      if (typeof window !== 'undefined') window.addEventListener('catalyst:demo-reset', resetListener, { once: true });
      await api.agentChatStream(
        {
          session_id: sessionId,
          message: text,
          current_workspace: currentWorkspace as Record<string, unknown>,
          attachments,
        },
        {
          onStatus: (status) => {
            const label = String(status || '').trim();
            if (label) set({ agentActivity: label });
          },
          onToken: (token) => {
            // Keep last status/tool label until UI derives a markdown heading.
            if (!sawTokens) {
              sawTokens = true;
              set((s) => ({
                agentActivity: s.agentActivity && s.agentActivity !== 'Thinking?' ? s.agentActivity : 'Writing answer?',
              }));
            }
            patchStreamText(token);
          },
          onCheckpoint: async (actions, actionId) => {
            await get().applyUiActions(actions);
            if (actionId) await api.confirmAction(actionId).catch(() => {});
          },
          signal: streamController.signal,
          onDone: (response) => {
            sawDone = true;
            void finishFromChatResponse(response);
          },
          onError: (message) => {
            sawDone = true;
            set((s) => ({
              agentMessages: s.agentMessages.map((msg) =>
                msg.id === streamId
                  ? normalizeAgentMessage({ id: streamId, text: `Error: ${message}`, timestamp: Date.now() }, 'error')
                  : msg,
              ),
              agentLoading: false,
              agentActivity: null,
              agentTurnStartedAt: null,
              agentLastTurnDurationMs: Date.now() - (s.agentTurnStartedAt || startedAt),
            }));
          },
        },
      );
      if (typeof window !== 'undefined') window.removeEventListener('catalyst:demo-reset', resetListener);
      // Stream closed without a terminal event ? fall through to non-stream below.
      if (sawDone || !get().agentLoading) return;
      if (sawTokens) {
        set({ agentLoading: false, agentActivity: null, agentTurnStartedAt: null });
        return;
      }
      throw new Error('stream_incomplete');
    } catch (streamErr) {
      if (streamErr instanceof DOMException && streamErr.name === 'AbortError') {
        set((s) => ({
          agentMessages: s.agentMessages.map((msg) => msg.id === streamId ? { ...msg, text: msg.text || 'Demo reset.' } : msg),
          agentLoading: false,
          agentActivity: null,
          agentTurnStartedAt: null,
          agentLastTurnDurationMs: Date.now() - (s.agentTurnStartedAt || startedAt),
        }));
        return;
      }
      // Silent non-stream fallback ? keep "Thinking?" (never flash "Retrying?").
      try {
        set((s) => ({ agentActivity: s.agentActivity || 'Thinking?' }));
        const response = await api.agentChat({
          session_id: sessionId,
          message: text,
          current_workspace: currentWorkspace,
          attachments,
        });
        await finishFromChatResponse(response);
      } catch (fallbackErr) {
        const errMsg = normalizeAgentMessage(
          {
            id: streamId,
            text: `Error: ${fallbackErr instanceof Error ? fallbackErr.message : 'Agent unavailable'}`,
            timestamp: Date.now(),
          },
          'error',
        );
        set((s) => ({
          agentMessages: s.agentMessages.map((msg) => (msg.id === streamId ? errMsg : msg)),
          agentLoading: false,
          agentActivity: null,
          agentTurnStartedAt: null,
          agentLastTurnDurationMs: Date.now() - (s.agentTurnStartedAt || startedAt),
        }));
      }
    }
  },

  clearAgentMessages: () => set({ agentMessages: [] }),
  };
}
