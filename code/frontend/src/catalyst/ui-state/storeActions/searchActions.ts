// @ts-nocheck
import { api } from '@/lib/api';
import { normalizeCandidateFromRaw } from '../../bridge/normalizers';
import type { AppState } from '../appStoreTypes';

type SetState = any;
type GetState = any;

export function createSearchActions(set: SetState, get: GetState): Partial<AppState> {
  return {
  runSearch: async (query, filters = {}) => {
    if (!query.trim() && Object.keys(filters).length === 0) {
      set({ searchResults: [] });
      return [];
    }
    set({ searchLoading: true, searchError: null, searchFilters: filters });
    try {
      const data = await api.search(query, filters);
      const results = (data.results || []).map(normalizeCandidateFromRaw);
      set({ searchResults: results, searchLoading: false });
      return results;
    } catch (err) {
      set({ searchLoading: false, searchError: 'Search failed' });
      get().addToast('Search failed', 'error');
      return [];
    }
  },

  clearSearch: () => set({ searchResults: [], searchError: null, searchFilters: {} }),

  // ?? Screen ??????????????????????????????????????????????????????????????????
  runScreen: async (requirement) => {
    set({ screenLoading: true, screenError: null, screenRequirement: requirement });
    try {
      const data = await api.screen({
        requirement,
        context: { session_id: get().currentSessionId || undefined },
        options: { limit: 8 },
      });
      const results = (data.candidates || []).map(normalizeCandidateFromRaw);
      set({ screenResults: results, screenLoading: false });
      return results;
    } catch (err) {
      set({ screenLoading: false, screenError: 'Screening failed' });
      get().addToast('Screening failed', 'error');
      return [];
    }
  },

  clearScreen: () => set({ screenResults: [], screenRequirement: '', screenError: null }),

  };
}
