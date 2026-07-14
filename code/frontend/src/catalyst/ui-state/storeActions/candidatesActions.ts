// @ts-nocheck
import { api } from '@/lib/api';
import { normalizeCandidateFromRaw, normalizeCandidateRow, normalizeCompare } from '../../bridge/normalizers';
import type { AppState } from '../appStoreTypes';

type SetState = any;
type GetState = any;

export function createCandidateActions(set: SetState, get: GetState): Partial<AppState> {
  return {
  addCandidate: (workspace) => {
    const row = normalizeCandidateRow(workspace);
    set((s) => {
      if (s.candidates.some((c) => c.material_id === row.material_id)) return {};
      return { candidates: [...s.candidates, row] };
    });
    get().addToast(`${workspace.title} added to candidates`, 'success');
  },

  addCandidateRaw: (raw) => {
    const row = normalizeCandidateFromRaw(raw);
    set((s) => {
      if (s.candidates.some((c) => c.material_id === row.material_id)) return {};
      return { candidates: [...s.candidates, row] };
    });
  },

  removeCandidate: (materialId) => {
    set((s) => ({ candidates: s.candidates.filter((c) => c.material_id !== materialId) }));
  },

  clearCandidates: () => set({ candidates: [], compareData: null }),

  // ?? Compare ?????????????????????????????????????????????????????????????????
  runCompare: async () => {
    const ids = get().candidates.map((c) => c.material_id);
    if (ids.length < 2) { get().addToast('Select at least 2 candidates to compare', 'warning'); return; }
    set({ compareLoading: true, compareError: null });
    try {
      const data = await api.compare({ material_ids: ids, include_evidence: true, include_edges: true });
      set({ compareData: normalizeCompare(data), compareLoading: false });
    } catch {
      set({ compareLoading: false, compareError: 'Compare failed' });
      get().addToast('Compare failed', 'error');
    }
  },

  // ?? Export ???????????????????????????????????????????????????????????????????
  exportSubgraph: async (materialIds) => {
    const ids = materialIds || get().candidates.map((c) => c.material_id);
    if (!ids.length) { get().addToast('No materials to export', 'warning'); return; }
    try {
      const data = await api.exportSubgraph({ material_ids: ids, include_evidence: true });
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'catalyst-subgraph.json';
      document.body.appendChild(a); a.click();
      URL.revokeObjectURL(url); a.remove();
      get().addToast('Subgraph exported', 'success');
    } catch {
      get().addToast('Export failed', 'error');
    }
  },

  exportCandidates: async (format = 'json') => {
    const ids = get().candidates.map((c) => c.material_id);
    if (!ids.length) { get().addToast('No candidates to export', 'warning'); return; }
    try {
      const data = await api.exportCandidates({ material_ids: ids, format });
      const blob = new Blob([typeof data === 'string' ? data : JSON.stringify(data, null, 2)], {
        type: format === 'csv' ? 'text/csv' : 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `catalyst-candidates.${format}`;
      document.body.appendChild(a); a.click();
      URL.revokeObjectURL(url); a.remove();
      get().addToast('Candidates exported', 'success');
    } catch {
      get().addToast('Export failed', 'error');
    }
  },

  };
}
