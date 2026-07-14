import { create } from 'zustand';
import { DEFAULT_GENOME_STATE, normalizeGenomeState, type GenomeState } from './genomeState';

export type ActiveSheet =
  | 'inspector'
  | 'agent'
  | 'candidates'
  | 'compare'
  | 'evidence'
  | 'edge'
  | 'research'
  | 'settings'
  | 'sessions'
  | null;

export type RailMode = 'home' | 'genes' | 'notebook' | 'graph' | 'candidates' | 'add_material' | 'settings';
export type WorkspaceTab = 'neighbors' | 'structure' | 'spectra';
export type CommandMode = 'search' | 'ask' | 'screen';
export type DensityMode = 'comfortable' | 'compact';
export type InspectorTab = 'overview' | 'properties' | 'evidence' | 'agent';
export type GenomicsCaseId = 'brca1' | 'hbb' | 'ctg';
export type DemoMissionItem = { id: string; label: string };
export type DemoAnimation = { phase: 'assemble' | 'focus'; startedAt: number; durationMs: number; nonce: number };
export type DemoState = {
  scenarioId: string | null;
  title: string;
  running: boolean;
  complete: boolean;
  totalMs: number;
  startedAt: number | null;
  currentStepId: string | null;
  mission: DemoMissionItem[];
  briefTitle: string | null;
};

const EMPTY_DEMO_STATE: DemoState = {
  scenarioId: null,
  title: '',
  running: false,
  complete: false,
  totalMs: 0,
  startedAt: null,
  currentStepId: null,
  mission: [],
  briefTitle: null,
};

export interface LayoutState {
  activeSheet: ActiveSheet;
  openSheet: (sheet: ActiveSheet) => void;
  closeSheet: () => void;
  toggleSheet: (sheet: ActiveSheet) => void;

  searchMode: CommandMode;
  setSearchMode: (mode: CommandMode) => void;
  searchOpen: boolean;
  setSearchOpen: (open: boolean) => void;

  graphControlsOpen: boolean;
  setGraphControlsOpen: (open: boolean) => void;

  candidateTrayExpanded: boolean;
  setCandidateTrayExpanded: (v: boolean) => void;

  railMode: RailMode;
  setRailMode: (mode: RailMode) => void;
  workspaceTab: WorkspaceTab;
  setWorkspaceTab: (tab: WorkspaceTab) => void;
  hopDepth: number;
  setHopDepth: (depth: number) => void;

  genomicsCaseId: GenomicsCaseId;
  setGenomicsCaseId: (caseId: GenomicsCaseId) => void;
  genomicsVariantIndex: number;
  setGenomicsVariantIndex: (index: number) => void;
  genomicsRepeatCount: number;
  setGenomicsRepeatCount: (count: number) => void;
  genomicsResetNonce: number;
  resetGenomicsCamera: () => void;
  genomeState: GenomeState;
  setGenomeState: (state: Partial<GenomeState>) => void;
  setGenomeSelection: (position: number) => void;
  setGenomeViewport: (start: number, end: number) => void;
  genomeSequenceVisible: boolean;
  setGenomeSequenceVisible: (visible: boolean) => void;
  demoState: DemoState;
  demoMaterialAnimation: DemoAnimation | null;
  demoDnaAnimation: DemoAnimation | null;
  applyDemoAction: (action: Record<string, unknown>) => void;
  resetDemo: () => void;

  inspectorOpen: boolean;
  setInspectorOpen: (open: boolean) => void;
  toggleInspector: () => void;
  inspectorTab: InspectorTab;
  setInspectorTab: (tab: InspectorTab) => void;
  railExpanded: boolean;
  setRailExpanded: (open: boolean) => void;
  toggleRailExpanded: () => void;

  theme: 'dark' | 'light';
  setTheme: (theme: 'dark' | 'light') => void;
  toggleTheme: () => void;

  density: DensityMode;
  setDensity: (density: DensityMode) => void;
}

const readStored = (key: string): string | null => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(key);
};

const writeStored = (key: string, value: string): void => {
  if (typeof window === 'undefined') return;
  localStorage.setItem(key, value);
};

const readStoredTheme = (): 'dark' | 'light' => {
  const stored = readStored('catalyst-theme');
  return stored === 'light' || stored === 'dark' ? stored : 'dark';
};

const readStoredDensity = (): DensityMode => {
  const stored = readStored('catalyst-density');
  return stored === 'compact' || stored === 'comfortable' ? stored : 'comfortable';
};

const readStoredRailMode = (): RailMode => {
  return 'home';
};

const readStoredSearchMode = (): CommandMode => {
  const stored = readStored('catalyst-command-mode');
  return stored === 'search' || stored === 'ask' || stored === 'screen' ? stored : 'search';
};

const readStoredHopDepth = (): number => {
  const raw = Number(readStored('catalyst-hop-depth') || '2');
  if (!Number.isFinite(raw)) return 2;
  return Math.max(1, Math.min(5, Math.round(raw)));
};

export const useLayoutStore = create<LayoutState>((set) => ({
  activeSheet: null,
  openSheet: (sheet) => set({ activeSheet: sheet }),
  closeSheet: () => set({ activeSheet: null }),
  toggleSheet: (sheet) => set((s) => ({ activeSheet: s.activeSheet === sheet ? null : sheet })),

  searchMode: readStoredSearchMode(),
  setSearchMode: (mode) => {
    writeStored('catalyst-command-mode', mode);
    set({ searchMode: mode });
  },
  searchOpen: false,
  setSearchOpen: (open) => set({ searchOpen: open }),

  graphControlsOpen: false,
  setGraphControlsOpen: (open) => set({ graphControlsOpen: open }),

  candidateTrayExpanded: false,
  setCandidateTrayExpanded: (v) => set({ candidateTrayExpanded: v }),

  railMode: readStoredRailMode(),
  setRailMode: (mode) => {
    writeStored('catalyst-rail-mode', mode);
    set({ railMode: mode });
  },
  workspaceTab: 'structure',
  setWorkspaceTab: (tab) => set({ workspaceTab: tab }),
  hopDepth: readStoredHopDepth(),
  setHopDepth: (depth) => {
    const next = Math.max(1, Math.min(5, Math.round(depth)));
    writeStored('catalyst-hop-depth', String(next));
    set({ hopDepth: next });
  },

  genomicsCaseId: 'brca1',
  setGenomicsCaseId: (caseId) => set({ genomicsCaseId: caseId }),
  genomicsVariantIndex: 7,
  setGenomicsVariantIndex: (index) => set({ genomicsVariantIndex: Math.max(0, Math.min(99, Math.round(index))) }),
  genomicsRepeatCount: 55,
  setGenomicsRepeatCount: (count) => set({ genomicsRepeatCount: Math.max(0, Math.min(100, Math.round(count))) }),
  genomicsResetNonce: 0,
  resetGenomicsCamera: () => set((s) => ({ genomicsResetNonce: s.genomicsResetNonce + 1 })),
  genomeState: DEFAULT_GENOME_STATE,
  setGenomeState: (state) => set((s) => ({ genomeState: normalizeGenomeState({ ...s.genomeState, ...state }) })),
  setGenomeSelection: (position) => set((s) => ({ genomeState: normalizeGenomeState({ ...s.genomeState, selectedPosition: position }) })),
  setGenomeViewport: (start, end) => set((s) => ({ genomeState: normalizeGenomeState({ ...s.genomeState, visibleStart: start, visibleEnd: end, selectedPosition: Math.max(start, Math.min(end, s.genomeState.selectedPosition)) }) })),
  genomeSequenceVisible: false,
  setGenomeSequenceVisible: (visible) => set({ genomeSequenceVisible: visible }),
  demoState: EMPTY_DEMO_STATE,
  demoMaterialAnimation: null,
  demoDnaAnimation: null,
  applyDemoAction: (action) => set((state) => {
    const type = String(action.type || '');
    if (type === 'demo_start') {
      return {
        demoState: {
          scenarioId: String(action.scenario_id || ''),
          title: String(action.title || 'Guided investigation'),
          running: true,
          complete: false,
          totalMs: Math.max(1, Number(action.total_ms) || 160_000),
          startedAt: Date.now(),
          currentStepId: null,
          mission: Array.isArray(action.mission) ? action.mission.map((item: any) => ({ id: String(item.id), label: String(item.label) })) : [],
          briefTitle: null,
        },
        demoMaterialAnimation: null,
        demoDnaAnimation: null,
        genomeSequenceVisible: false,
      };
    }
    if (type === 'demo_checkpoint') return { demoState: { ...state.demoState, currentStepId: String(action.step_id || '') } };
    if (type === 'demo_material_assemble') return { demoMaterialAnimation: { phase: 'assemble', startedAt: Date.now(), durationMs: Math.max(1000, Number(action.duration_ms) || 26_000), nonce: Number(action.nonce) || 1 } };
    if (type === 'demo_dna_assemble') return { demoDnaAnimation: { phase: 'assemble', startedAt: Date.now(), durationMs: Math.max(1000, Number(action.duration_ms) || 24_000), nonce: Number(action.nonce) || 1 } };
    if (type === 'demo_dna_focus') return { demoDnaAnimation: { phase: 'focus', startedAt: Date.now(), durationMs: Math.max(1000, Number(action.duration_ms) || 10_000), nonce: Number(action.nonce) || 2 } };
    if (type === 'demo_final_brief') return { demoState: { ...state.demoState, briefTitle: String(action.title || 'Science brief') } };
    if (type === 'demo_complete') return { demoState: { ...state.demoState, running: false, complete: true, currentStepId: 'complete' } };
    return {};
  }),
  resetDemo: () => set({ demoState: EMPTY_DEMO_STATE, demoMaterialAnimation: null, demoDnaAnimation: null, genomeSequenceVisible: false }),

  inspectorOpen: true,
  setInspectorOpen: (open) => set({ inspectorOpen: open }),
  toggleInspector: () => set((s) => ({ inspectorOpen: !s.inspectorOpen })),
  inspectorTab: 'agent',
  setInspectorTab: (tab) => set({ inspectorTab: tab }),
  railExpanded: false,
  setRailExpanded: (open) => set({ railExpanded: open }),
  toggleRailExpanded: () => set((s) => ({ railExpanded: !s.railExpanded })),

  theme: readStoredTheme(),
  setTheme: (theme) => {
    writeStored('catalyst-theme', theme);
    set({ theme });
  },
  toggleTheme: () =>
    set((s) => {
      const next = s.theme === 'dark' ? 'light' : 'dark';
      writeStored('catalyst-theme', next);
      return { theme: next };
    }),

  density: readStoredDensity(),
  setDensity: (density) => {
    writeStored('catalyst-density', density);
    set({ density });
  },
}));
