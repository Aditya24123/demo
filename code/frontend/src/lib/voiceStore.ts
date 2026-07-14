import { useSyncExternalStore } from 'react';

export type VoiceViewMode = 'none' | 'sidebar' | 'fullscreen';

export type VoiceTranscriptLine = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  at: number;
  segmentId?: string;
};

export interface VoiceState {
  isActive: boolean;
  isConnecting: boolean;
  isConnected: boolean;
  viewMode: VoiceViewMode;
  isMuted: boolean;
  cameraActive: boolean;
  screenActive: boolean;
  lastError: string | null;
  transcript: VoiceTranscriptLine[];
  startedAt: number | null;
  isSpeaking: boolean;
  /** Shimmer label while live turn is thinking / calling tools (not shown as chat text). */
  activity: string | null;
  isThinking: boolean;
}

const INITIAL_STATE: VoiceState = {
  isActive: false,
  isConnecting: false,
  isConnected: false,
  viewMode: 'none',
  isMuted: false,
  cameraActive: false,
  screenActive: false,
  lastError: null,
  transcript: [],
  startedAt: null,
  isSpeaking: false,
  activity: null,
  isThinking: false,
};

function createStore() {
  let state: VoiceState = { ...INITIAL_STATE };
  const listeners = new Set<() => void>();
  let snapshot = state;

  return {
    get() {
      return snapshot;
    },
    set(updates: Partial<VoiceState>) {
      state = { ...state, ...updates };
      snapshot = state;
      listeners.forEach((fn) => fn());
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    appendTranscript(line: Omit<VoiceTranscriptLine, 'id' | 'at'>) {
      const at = Date.now();
      const previous = state.transcript[state.transcript.length - 1];
      const sameSegment = Boolean(line.segmentId && previous?.segmentId && line.segmentId === previous.segmentId);
      const sameFallbackWindow = !line.segmentId && !previous?.segmentId && previous?.role === line.role && at - previous.at <= 1200;
      if (previous && previous.role === line.role && (sameSegment || sameFallbackWindow)) {
        const merged: VoiceTranscriptLine = {
          ...previous,
          text: mergeTranscriptDelta(previous.text, line.text),
          at,
          segmentId: line.segmentId || previous.segmentId,
        };
        this.set({ transcript: [...state.transcript.slice(0, -1), merged] });
        return;
      }
      const entry: VoiceTranscriptLine = {
        id: `vt_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        at,
        ...line,
      };
      this.set({ transcript: [...state.transcript.slice(-80), entry] });
    },
    clearTranscript() {
      this.set({ transcript: [] });
    },
    toggleMute() {
      this.set({ isMuted: !state.isMuted });
    },
    toggleCamera() {
      this.set({ cameraActive: !state.cameraActive });
    },
    toggleScreen() {
      this.set({ screenActive: !state.screenActive });
    },
    setViewMode(mode: VoiceViewMode) {
      this.set({ viewMode: mode });
    },
    resetCallFlags(extra: Partial<VoiceState> = {}) {
      this.set({
        isActive: false,
        isConnecting: false,
        isConnected: false,
        isMuted: false,
        cameraActive: false,
        screenActive: false,
        startedAt: null,
        isSpeaking: false,
        activity: null,
        isThinking: false,
        ...extra,
      });
    },
    setActivity(label: string | null, thinking = true) {
      this.set({
        activity: label,
        isThinking: Boolean(thinking && label),
      });
    },
    clearActivity() {
      this.set({ activity: null, isThinking: false });
    },
  };
}

export const voiceStore = createStore();

function mergeTranscriptDelta(previous: string, next: string): string {
  if (!next) return previous;
  if (!previous) return next;
  if (next.startsWith(previous)) return next;
  if (previous.endsWith(next)) return previous;
  if (previous.includes(next) && next.length < previous.length) return previous;

  const maxOverlap = Math.min(previous.length, next.length, 64);
  for (let size = maxOverlap; size > 0; size -= 1) {
    if (previous.slice(-size) === next.slice(0, size)) {
      return `${previous}${next.slice(size)}`;
    }
  }

  const needsSpace = !/\s$/.test(previous) && !/^\s|^[,.;:!?)}\]]/.test(next);
  return `${previous}${needsSpace ? ' ' : ''}${next}`;
}

export function useVoiceState() {
  return useSyncExternalStore(voiceStore.subscribe, voiceStore.get, voiceStore.get);
}

export function useVoiceActions() {
  return {
    toggleMute: () => voiceStore.toggleMute(),
    toggleCamera: () => voiceStore.toggleCamera(),
    toggleScreen: () => voiceStore.toggleScreen(),
    setViewMode: (mode: VoiceViewMode) => voiceStore.setViewMode(mode),
    clearTranscript: () => voiceStore.clearTranscript(),
    set: (updates: Partial<VoiceState>) => voiceStore.set(updates),
  };
}
