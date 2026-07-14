// @ts-nocheck
import { api } from '@/lib/api';
import { normalizeResearch } from '../../bridge/normalizers';
import type { AppState } from '../appStoreTypes';

type SetState = any;
type GetState = any;

export function createResearchActions(set: SetState, get: GetState): Partial<AppState> {
  return {
  loadResearchStatus: async () => {
    set({ researchLoading: true });
    try {
      const data = await api.getResearchStatus();
      set({ research: normalizeResearch(data), researchLoading: false });
    } catch {
      set({ researchLoading: false });
    }
  },

  runResearch: async (query, context) => {
    const sessionId = get().currentSessionId || 'default';
    set({ researchLoading: true, researchError: null });
    try {
      const data = await api.researchQuery({ session_id: sessionId, query, context });
      const runId = data.run_id;
      if (runId) {
        set((s) => ({ researchRuns: { ...s.researchRuns, [runId]: { status: 'pending' } } }));
      }
      set({ researchLoading: false });
      get().addToast('Research query submitted', 'info');
    } catch {
      set({ researchLoading: false, researchError: 'Research query failed' });
      get().addToast('Research failed', 'error');
    }
  },

  };
}
