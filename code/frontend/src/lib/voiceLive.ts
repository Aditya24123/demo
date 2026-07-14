import { getWsBase } from '@/lib/api';
import { voiceStore } from '@/lib/voiceStore';
import { isInternalLiveText, sanitizeLiveAssistantText } from '@/lib/voiceText';
import { useAppStore } from '@/catalyst/ui-state/appStore';

type StartOpts = {
  sessionId?: string | null;
  workspace?: Record<string, unknown> | null;
  /** Start screen share immediately after Live connects. */
  withScreenShare?: boolean;
};

let socket: WebSocket | null = null;
let intentionalClose = false;
let micStream: MediaStream | null = null;
let inputContext: AudioContext | null = null;
let outputContext: AudioContext | null = null;
let inputSource: MediaStreamAudioSourceNode | null = null;
let inputProcessor: ScriptProcessorNode | null = null;
let inputSilencer: GainNode | null = null;
let outputCursor = 0;
/** Stable segment for the current assistant spoken answer (not tools). */
let assistantAnswerSegment: string | null = null;
let pendingScreenShare = false;

// Screen share capture
let screenStream: MediaStream | null = null;
let screenVideo: HTMLVideoElement | null = null;
let screenCanvas: HTMLCanvasElement | null = null;
let screenTimer: ReturnType<typeof setInterval> | null = null;
const SCREEN_FPS_MS = 900;
const SCREEN_MAX_W = 1280;

export async function connectVoiceLive(opts: StartOpts = {}): Promise<void> {
  // Always tear down any prior session first (hard stop).
  await hardStopVoice({ silent: true, preserveError: false });
  intentionalClose = false;
  assistantAnswerSegment = null;
  pendingScreenShare = Boolean(opts.withScreenShare);

  voiceStore.clearTranscript();
  voiceStore.set({
    isActive: true,
    isConnecting: true,
    isConnected: false,
    viewMode: 'none',
    lastError: null,
    startedAt: null,
    isSpeaking: false,
    activity: 'Connecting?',
    isThinking: true,
    screenActive: false,
    isMuted: false,
  });

  try {
    await startMicrophoneCapture();
    outputContext = new AudioContext({ sampleRate: 24000 });
    await outputContext.resume();

    const origin = await getWsBase();
    const ws = new WebSocket(`${origin}/voice/live`);
    socket = ws;

    ws.onopen = () => {
      try {
        ws.send(
          JSON.stringify({
            type: 'start',
            session_id: opts.sessionId || 'default',
            current_workspace: opts.workspace || null,
          }),
        );
      } catch {
        /* ignore */
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(String(event.data));
        handleVoiceMessage(msg);
      } catch {
        /* ignore malformed/non-json frames */
      }
    };

    ws.onerror = () => {
      if (intentionalClose) return;
      voiceStore.set({
        isConnecting: false,
        isConnected: false,
        startedAt: null,
        isSpeaking: false,
        activity: null,
        isThinking: false,
        lastError: 'WebSocket error ? is the Catalyst backend running with voice configured?',
      });
    };

    ws.onclose = () => {
      const wasIntentional = intentionalClose;
      socket = null;
      // Full teardown when remote closes (including hangup)
      void hardStopVoice({
        silent: true,
        preserveError: wasIntentional ? false : true,
        skipSocketClose: true,
        keepErrorIfSet: !wasIntentional,
      });
      if (!wasIntentional) {
        const current = voiceStore.get();
        voiceStore.resetCallFlags({
          lastError: current.lastError || 'Voice connection closed',
        });
      }
    };
  } catch (err) {
    await hardStopVoice({
      silent: true,
      preserveError: true,
    });
    voiceStore.resetCallFlags({
      lastError: err instanceof Error ? err.message : 'Unable to start voice mode',
    });
  }
}

/**
 * Hard-stop Live: stop mic + screen + audio graphs + WS.
 * Safe to call multiple times. Does not leave the mic listening.
 */
export async function disconnectVoiceLive(opts: { preserveError?: boolean; silent?: boolean } = {}): Promise<void> {
  await hardStopVoice({
    silent: opts.silent,
    preserveError: opts.preserveError,
  });
}

async function hardStopVoice(opts: {
  silent?: boolean;
  preserveError?: boolean;
  skipSocketClose?: boolean;
  keepErrorIfSet?: boolean;
} = {}): Promise<void> {
  intentionalClose = true;
  assistantAnswerSegment = null;
  pendingScreenShare = false;

  stopScreenShareInternal();

  if (!opts.skipSocketClose && socket) {
    const ws = socket;
    socket = null;
    try {
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        try {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'stop' }));
          }
        } catch {
          /* ignore */
        }
        try {
          ws.close(1000, 'client_end');
        } catch {
          /* ignore */
        }
      }
    } catch {
      /* ignore */
    }
  } else if (opts.skipSocketClose) {
    socket = null;
  }

  cleanupAudio();

  const prevError = voiceStore.get().lastError;
  if (opts.silent) {
    voiceStore.set({
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
      lastError: opts.preserveError
        ? prevError
        : opts.keepErrorIfSet
          ? prevError
          : null,
    });
    return;
  }
  voiceStore.resetCallFlags({
    lastError: opts.preserveError ? prevError : null,
  });
}

export function isVoiceSocketOpen(): boolean {
  return !!socket && socket.readyState === WebSocket.OPEN;
}

/** Toggle display capture for Live (JPEG frames over the same WS). */
export async function setScreenShareEnabled(enabled: boolean): Promise<void> {
  if (!enabled) {
    stopScreenShareInternal();
    voiceStore.set({ screenActive: false });
    return;
  }
  if (!isVoiceSocketOpen()) {
    throw new Error('Start voice mode first, then share your screen.');
  }
  try {
    await startScreenShareInternal();
    voiceStore.set({ screenActive: true, lastError: null });
  } catch (err) {
    stopScreenShareInternal();
    voiceStore.set({
      screenActive: false,
      lastError: err instanceof Error ? err.message : 'Screen share failed',
    });
    throw err;
  }
}

export function isScreenShareActive(): boolean {
  return Boolean(screenStream && screenStream.active);
}

function stopScreenShareInternal(): void {
  if (screenTimer != null) {
    clearInterval(screenTimer);
    screenTimer = null;
  }
  if (screenStream) {
    for (const track of screenStream.getTracks()) {
      try {
        track.stop();
      } catch {
        /* ignore */
      }
    }
  }
  screenStream = null;
  if (screenVideo) {
    try {
      screenVideo.pause();
      screenVideo.srcObject = null;
    } catch {
      /* ignore */
    }
  }
  screenVideo = null;
  screenCanvas = null;
}

async function startScreenShareInternal(): Promise<void> {
  stopScreenShareInternal();
  if (!navigator.mediaDevices?.getDisplayMedia) {
    throw new Error('Screen share is not available in this browser.');
  }
  screenStream = await navigator.mediaDevices.getDisplayMedia({
    video: {
      frameRate: { ideal: 2, max: 5 },
      width: { ideal: SCREEN_MAX_W },
    },
    audio: false,
  });
  const track = screenStream.getVideoTracks()[0];
  if (track) {
    track.addEventListener('ended', () => {
      stopScreenShareInternal();
      voiceStore.set({ screenActive: false });
    });
  }

  screenVideo = document.createElement('video');
  screenVideo.muted = true;
  screenVideo.playsInline = true;
  screenVideo.srcObject = screenStream;
  await screenVideo.play();

  screenCanvas = document.createElement('canvas');
  screenTimer = setInterval(() => {
    void pushScreenFrame();
  }, SCREEN_FPS_MS);
  // first frame soon
  void pushScreenFrame();
}

async function pushScreenFrame(): Promise<void> {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  if (!screenVideo || !screenCanvas || screenVideo.readyState < 2) return;
  const vw = screenVideo.videoWidth || 0;
  const vh = screenVideo.videoHeight || 0;
  if (vw < 2 || vh < 2) return;

  let tw = vw;
  let th = vh;
  if (tw > SCREEN_MAX_W) {
    th = Math.round((th * SCREEN_MAX_W) / tw);
    tw = SCREEN_MAX_W;
  }
  screenCanvas.width = tw;
  screenCanvas.height = th;
  const ctx = screenCanvas.getContext('2d');
  if (!ctx) return;
  ctx.drawImage(screenVideo, 0, 0, tw, th);

  const blob = await new Promise<Blob | null>((resolve) => {
    screenCanvas!.toBlob((b) => resolve(b), 'image/jpeg', 0.72);
  });
  if (!blob) return;
  const buf = await blob.arrayBuffer();
  const data = bytesToBase64(new Uint8Array(buf));
  try {
    socket.send(
      JSON.stringify({
        type: 'video',
        data,
        mimeType: 'image/jpeg',
      }),
    );
  } catch {
    /* ignore send failures mid-teardown */
  }
}

function handleVoiceMessage(msg: Record<string, unknown>): void {
  const type = String(msg.type || '');

  if (type === 'ready' || type === 'setup_complete') {
    voiceStore.set({
      isConnecting: false,
      isConnected: true,
      lastError: null,
      isSpeaking: false,
      startedAt: voiceStore.get().startedAt || Date.now(),
      // Idle listening state so the UI isn't empty after connect
      activity: 'Listening?',
      isThinking: true,
    });
    if (pendingScreenShare) {
      pendingScreenShare = false;
      void setScreenShareEnabled(true).catch(() => {
        /* error already stored */
      });
    }
    return;
  }
  if (type === 'error') {
    // Don't leave mic open on fatal live errors
    void hardStopVoice({ silent: true, preserveError: true });
    voiceStore.resetCallFlags({
      lastError: String(msg.message || 'Voice mode failed'),
    });
    return;
  }
  if (type === 'status') {
    const text = String(msg.text || msg.message || '').trim();
    if (text) {
      const idle = /^listening/i.test(text);
      voiceStore.set({
        activity: text,
        isThinking: true,
        isSpeaking: idle ? false : voiceStore.get().isSpeaking,
      });
    }
    return;
  }
  if (type === 'audio') {
    const data = String(msg.data || '');
    if (data) {
      const cur = voiceStore.get().activity || '';
      voiceStore.set({
        isSpeaking: true,
        isThinking: true,
        activity: cur.startsWith('Using') || cur.includes('?') && !cur.startsWith('Listening')
          ? cur
          : 'Speaking?',
      });
      void playPcmAudio(data, parsePcmRate(String(msg.mimeType || 'audio/pcm;rate=24000')));
    }
    return;
  }
  if (type === 'input_transcript') {
    const text = String(msg.text || '').trim();
    if (!text || isInternalLiveText(text)) return;
    voiceStore.set({ isSpeaking: false });
    assistantAnswerSegment = null;
    voiceStore.setActivity('Thinking?', true);
    const seg = transcriptSegmentId(msg) || `user-turn:${voiceStore.get().startedAt || Date.now()}`;
    voiceStore.appendTranscript({
      role: 'user',
      text,
      segmentId: seg,
    });
    return;
  }
  if (type === 'output_transcript') {
    const raw = String(msg.text || '');
    const cleaned =
      sanitizeLiveAssistantText(raw) || (raw.trim() && !isInternalLiveText(raw) ? raw.trim() : null);
    if (!cleaned) {
      voiceStore.setActivity('Speaking?', true);
      return;
    }
    if (!assistantAnswerSegment) {
      assistantAnswerSegment = transcriptSegmentId(msg) || `answer:${Date.now()}`;
    }
    voiceStore.set({ isSpeaking: true, isThinking: false, activity: null });
    voiceStore.appendTranscript({
      role: 'assistant',
      text: cleaned,
      segmentId: assistantAnswerSegment,
    });
    return;
  }
  if (type === 'agent_text' || type === 'transcript' || type === 'text') {
    // Mostly model thoughts when transcription is enabled ? prefer output_transcript
    const cleaned = sanitizeLiveAssistantText(String(msg.text || msg.content || ''));
    if (!cleaned) {
      const act = voiceStore.get().activity;
      if (!act || act === 'Listening?') voiceStore.setActivity('Thinking?', true);
      return;
    }
    if (!assistantAnswerSegment) {
      assistantAnswerSegment = transcriptSegmentId(msg) || `answer:${Date.now()}`;
    }
    voiceStore.set({ isSpeaking: true, isThinking: false, activity: null });
    voiceStore.appendTranscript({
      role: 'assistant',
      text: cleaned,
      segmentId: assistantAnswerSegment,
    });
    return;
  }
  if (type === 'tool_call') {
    const name = String(msg.name || 'tool');
    const label =
      typeof msg.status === 'string' && msg.status.trim()
        ? String(msg.status).trim()
        : friendlyToolLabel(name, msg.args);
    voiceStore.setActivity(label, true);
    return;
  }
  if (type === 'tool_result') {
    voiceStore.setActivity('Updating workspace?', true);
    void applyVoiceUiActions(msg);
    return;
  }
  if (type === 'tool_error') {
    voiceStore.setActivity('Tool issue ? continuing?', true);
    return;
  }
  if (type === 'turn_complete') {
    voiceStore.set({
      isSpeaking: false,
      isThinking: true,
      activity: 'Listening?',
    });
    assistantAnswerSegment = null;
    void applyVoiceUiActions(msg);
    return;
  }
}

function friendlyToolLabel(name: string, args: unknown): string {
  const a = args && typeof args === 'object' ? (args as Record<string, unknown>) : {};
  const mid = String(a.material_id || a.query || a.formula || '').trim();
  const map: Record<string, string> = {
    resolve_material: mid ? `Resolving ${mid}?` : 'Resolving material?',
    search_materials: mid ? `Searching for ${mid}?` : 'Searching materials?',
    get_material_workspace: mid ? `Loading ${mid}?` : 'Loading material?',
    get_neighborhood: mid ? `Neighbors of ${mid}?` : 'Expanding neighborhood?',
    select_material: mid ? `Opening ${mid}?` : 'Selecting material?',
    get_material_details: mid ? `Properties for ${mid}?` : 'Fetching properties?',
    get_material_structure: mid ? `Structure for ${mid}?` : 'Loading structure?',
    compare_materials: 'Comparing materials?',
    open_project_material: 'Opening project material?',
    save_project_material: 'Saving project material?',
    screen_candidates: 'Screening candidates?',
  };
  return map[name] || `Using ${name.replace(/_/g, ' ')}?`;
}

function applyVoiceUiActions(msg: Record<string, unknown>): void {
  const actions = msg.ui_actions || msg.uiActions;
  if (!Array.isArray(actions) || !actions.length) return;
  void useAppStore.getState().applyUiActions(actions as Array<Record<string, unknown>>);
}

function transcriptSegmentId(msg: Record<string, unknown>): string | undefined {
  const value = msg.segment_id || msg.segmentId;
  return value ? String(value) : undefined;
}

async function startMicrophoneCapture(): Promise<void> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('Microphone access is not available in this browser context.');
  }

  micStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

  inputContext = new AudioContext({ sampleRate: 16000 });
  await inputContext.resume();
  inputSource = inputContext.createMediaStreamSource(micStream);
  inputProcessor = inputContext.createScriptProcessor(4096, 1, 1);
  inputSilencer = inputContext.createGain();
  inputSilencer.gain.value = 0;

  inputProcessor.onaudioprocess = (event) => {
    // Hard gate: never stream if session ended
    if (intentionalClose) return;
    if (!socket || socket.readyState !== WebSocket.OPEN || voiceStore.get().isMuted) return;
    if (!voiceStore.get().isActive || !voiceStore.get().isConnected) return;
    const channel = event.inputBuffer.getChannelData(0);
    const sourceRate = inputContext?.sampleRate || 16000;
    const pcm = sourceRate === 16000 ? channel : downsampleTo16k(channel, sourceRate);
    try {
      socket.send(
        JSON.stringify({
          type: 'audio',
          data: pcm16Base64(pcm),
          mimeType: 'audio/pcm;rate=16000',
        }),
      );
    } catch {
      /* ignore */
    }
  };

  inputSource.connect(inputProcessor);
  inputProcessor.connect(inputSilencer);
  inputSilencer.connect(inputContext.destination);
}

function cleanupAudio(): void {
  if (inputProcessor) {
    inputProcessor.onaudioprocess = null;
    try {
      inputProcessor.disconnect();
    } catch {
      /* ignore */
    }
  }
  if (inputSource) {
    try {
      inputSource.disconnect();
    } catch {
      /* ignore */
    }
  }
  if (inputSilencer) {
    try {
      inputSilencer.disconnect();
    } catch {
      /* ignore */
    }
  }
  if (micStream) {
    for (const track of micStream.getTracks()) {
      try {
        track.stop();
      } catch {
        /* ignore */
      }
    }
  }
  if (inputContext && inputContext.state !== 'closed') {
    try {
      void inputContext.close();
    } catch {
      /* ignore */
    }
  }
  if (outputContext && outputContext.state !== 'closed') {
    try {
      void outputContext.close();
    } catch {
      /* ignore */
    }
  }
  micStream = null;
  inputContext = null;
  outputContext = null;
  inputSource = null;
  inputProcessor = null;
  inputSilencer = null;
  outputCursor = 0;
}

function downsampleTo16k(input: Float32Array, inputRate: number): Float32Array {
  if (inputRate <= 16000) return input;
  const ratio = inputRate / 16000;
  const outLen = Math.max(1, Math.floor(input.length / ratio));
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i += 1) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    let count = 0;
    for (let j = start; j < end; j += 1) {
      sum += input[j];
      count += 1;
    }
    out[i] = count ? sum / count : input[start] || 0;
  }
  return out;
}

function pcm16Base64(samples: Float32Array): string {
  const bytes = new Uint8Array(samples.length * 2);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < samples.length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  }
  return bytesToBase64(bytes);
}

async function playPcmAudio(base64: string, sampleRate: number): Promise<void> {
  if (!outputContext || intentionalClose) return;
  if (outputContext.state === 'suspended') await outputContext.resume();

  const bytes = base64ToBytes(base64);
  if (bytes.byteLength < 2) return;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const frameCount = Math.floor(bytes.byteLength / 2);
  const buffer = outputContext.createBuffer(1, frameCount, sampleRate || 24000);
  const channel = buffer.getChannelData(0);

  for (let i = 0; i < frameCount; i += 1) {
    channel[i] = view.getInt16(i * 2, true) / 0x8000;
  }

  const source = outputContext.createBufferSource();
  source.buffer = buffer;
  source.connect(outputContext.destination);
  const startAt = Math.max(outputContext.currentTime + 0.02, outputCursor);
  source.start(startAt);
  outputCursor = startAt + buffer.duration;
}

function parsePcmRate(mimeType: string): number {
  const match = mimeType.match(/rate=(\d+)/);
  return match ? Number.parseInt(match[1], 10) : 24000;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  const size = 0x8000;
  for (let i = 0; i < bytes.length; i += size) {
    binary += String.fromCharCode(...bytes.subarray(i, i + size));
  }
  return btoa(binary);
}

function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}
