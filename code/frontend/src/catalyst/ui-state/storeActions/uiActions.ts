// @ts-nocheck
import { api } from '@/lib/api';
import { normalizeSystemStatus } from '../../bridge/normalizers';
import { DEFAULT_GRAPH_SETTINGS, type AppState } from '../appStoreTypes';
import { nextToastId } from './helpers';

type SetState = any;
type GetState = any;

export function createUiActions(set: SetState, get: GetState): Partial<AppState> {
  return {
  updateSettings: async (body) => {
    try {
      const data = await api.patchSettings(body);
      set({
        rawSettings: data,
        systemStatus: normalizeSystemStatus(get().rawHealth, get().rawCatalog, data),
      });
      get().addToast('Settings saved', 'success');
    } catch (err) {
      get().addToast(`Settings save failed: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    }
  },

  // ?? UI helpers ????????????????????????????????????????????????????????????????
  setGraphColorMode: (mode) => set({ graphColorMode: mode }),
  setGraphSettings: (patch) => set((s) => ({ graphSettings: { ...s.graphSettings, ...patch } })),
  resetGraphSettings: () => set({ graphSettings: DEFAULT_GRAPH_SETTINGS, graphColorMode: 'stability' }),

  addToast: (message, type = 'info') => {
    const id = nextToastId();
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }));
    setTimeout(() => get().removeToast(id), 4000);
  },

  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  };
}
