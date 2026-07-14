import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import 'katex/dist/katex.min.css';
import {
  useCatalystAgent,
  useCatalystLayout,
  useCatalystProjects,
  useCatalystSessions,
  useCatalystWorkspace,
} from '@/catalyst/bridge/hooks';
import type { AgentAttachment } from '@/catalyst/ui-state/appStore';
import { agentSurfaceFromRail, type AgentSurface } from '@/catalyst/ui-state/agentContext';
import { useLayoutStore } from '@/catalyst/ui-state/layoutStore';
import { connectVoiceLive, disconnectVoiceLive, setScreenShareEnabled } from '@/lib/voiceLive';
import { useVoiceActions, useVoiceState } from '@/lib/voiceStore';
import { isInternalLiveText } from '@/lib/voiceText';
import { ActivityLine, latestMarkdownHeading } from './agentChatActivity';
import { CapabilityMenu } from './agentCapabilityMenu';
import { formatDuration, useElapsedMs, voiceStatusLabel } from './agentChatUtils';
import { getSpeechRecognition, type SpeechRecognitionLike } from './agentSpeech';
import { ChevronRightIcon, JarvisRawIcon, MicIcon, PlusIcon, SendArrowIcon, SpinnerIcon, VoiceBarsIcon } from './JarvisIcons';

const MATERIALS_STARTERS = [
  'Compare this material to similar candidates',
  'Explain the graph neighborhood and key properties',
  'Show the crystal structure',
  'Screen for stable oxides above 2 eV',
];

const PROJECT_STARTERS = [
  'Summarize the research notebook',
  'List project files and what they contain',
  'Update the notebook with next experiment steps',
  'What did the last project run conclude?',
];

const GENES_STARTERS = [
  'Explain the visible DNA marker',
  'What does this BRCA1 demo case show?',
  'Open the HBB marker',
  'Set the CTG repeat count to 55',
];

/** Single-line compact height; grows upward only when content wraps (Jarvis-style). */
const COMPOSER_MIN_HEIGHT = 36;
const COMPOSER_MAX_HEIGHT = 120;

export function AgentChatBody({ compact = false, showInput = true }: { compact?: boolean; showInput?: boolean }) {
  const {
    messages,
    isRunning,
    mode,
    sendMessage,
    newChat,
    activity,
    modelCapability,
    availableModels,
    setModel,
  } = useCatalystAgent();
  const { workspace } = useCatalystWorkspace();
  const { activeProjectId, projects } = useCatalystProjects();
  const { railMode, genomicsCaseId, genomicsRepeatCount } = useCatalystLayout();
  const { currentSessionId, sessions, renameSession } = useCatalystSessions();
  const activeSession = sessions.find((session) => session.id === currentSessionId) || null;
  const activeProject = projects.find((project) => project.projectId === activeProjectId) || null;
  // Phase 5: surface follows the live rail — one copilot, shared context.
  const agentSurface: AgentSurface = agentSurfaceFromRail(railMode);
  const starters = agentSurface === 'project' ? PROJECT_STARTERS : agentSurface === 'genes' ? GENES_STARTERS : MATERIALS_STARTERS;
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const voiceState = useVoiceState();
  const voiceActions = useVoiceActions();
  const [input, setInput] = useState('');
  const [capabilitiesOpen, setCapabilitiesOpen] = useState(false);
  const [dictating, setDictating] = useState(false);
  const [composerError, setComposerError] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<AgentAttachment[]>([]);
  const voiceElapsedMs = useElapsedMs(voiceState.isConnected, voiceState.startedAt);

  const latestAssistant = useMemo(
    () => [...messages].reverse().find((msg) => msg.role === 'assistant') || null,
    [messages],
  );

  /** Live activity line: Thinking → tool status → latest markdown heading while tokens stream. */
  const activityLabel = useMemo(() => {
    // Voice live: shimmer for connect / think / tools (not chat text dumps)
    if (voiceState.isActive) {
      if (voiceState.isConnecting) return 'Connecting…';
      if (voiceState.activity) return voiceState.activity;
      if (voiceState.isThinking) return 'Thinking…';
      // Speaking with transcript already visible — no shimmer
      if (voiceState.isSpeaking) return null;
      return null;
    }
    if (!isRunning) return null;
    const streamed = latestAssistant?.text || '';
    const heading = latestMarkdownHeading(streamed);
    // Prefer live tool/status labels while waiting; once answer text exists, show section heading.
    if (streamed.trim()) {
      if (heading) return heading;
      if (activity && !/^thinking/i.test(activity)) return activity;
      return 'Writing…';
    }
    if (activity) return activity;
    return 'Thinking…';
  }, [
    activity,
    isRunning,
    latestAssistant?.text,
    voiceState.isActive,
    voiceState.isConnecting,
    voiceState.activity,
    voiceState.isThinking,
    voiceState.isSpeaking,
  ]);
  const showActivityShimmer = Boolean(
    activityLabel &&
      (isRunning ||
        (voiceState.isActive &&
          (voiceState.isConnecting ||
            voiceState.isThinking ||
            Boolean(voiceState.activity) ||
            // Connected idle / speaking without transcript yet still shows shimmer
            (voiceState.isConnected && !voiceState.isConnecting)))),
  );
  const bottomRef = useRef<HTMLDivElement>(null);
  const capabilityRef = useRef<HTMLDivElement>(null);
  const capabilityButtonRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const dictationRef = useRef<SpeechRecognitionLike | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const contextLine = useMemo(() => {
    const bits: string[] = [];
    bits.push(agentSurface === 'project' ? 'Project mode' : agentSurface === 'genes' ? 'Genes mode' : 'Materials mode');
    if (agentSurface === 'project') {
      bits.push(activeProject?.name || (activeProjectId ? 'project open' : 'no project'));
    } else if (agentSurface === 'genes') {
      bits.push(genomicsCaseId.toUpperCase());
      if (genomicsCaseId === 'ctg') bits.push(`${genomicsRepeatCount} repeats`);
    } else if (workspace?.title) {
      bits.push(workspace.title);
    }
    if (mode === 'provider_backed') bits.push('Active');
    else bits.push('Local fallback');
    if (modelCapability?.label) bits.push(modelCapability.label);
    return bits.join(' · ');
  }, [activeProject?.name, activeProjectId, agentSurface, genomicsCaseId, genomicsRepeatCount, mode, modelCapability?.label, workspace?.title]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isRunning, activityLabel, latestAssistant?.text, voiceState.transcript.length]);

  useEffect(() => {
    if (!capabilitiesOpen) return undefined;
    const onPointerDown = (event: PointerEvent) => {
      if (!capabilityRef.current?.contains(event.target as Node)) setCapabilitiesOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setCapabilitiesOpen(false);
        capabilityButtonRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [capabilitiesOpen]);

  function resizeComposer(element: HTMLTextAreaElement, value: string) {
    // Measure natural height, then clamp. align-items:end keeps +/send on the bottom
    // so growth is visual “from the top” (into the message list).
    element.style.height = '0px';
    element.style.overflowY = 'hidden';
    if (!value) {
      element.style.height = `${COMPOSER_MIN_HEIGHT}px`;
      return;
    }
    const natural = element.scrollHeight;
    const next = Math.min(Math.max(natural, COMPOSER_MIN_HEIGHT), COMPOSER_MAX_HEIGHT);
    element.style.height = `${next}px`;
    // Only scroll after the max expand limit (no visible scrollbar chrome via CSS).
    element.style.overflowY = natural > COMPOSER_MAX_HEIGHT ? 'auto' : 'hidden';
  }

  useEffect(() => {
    if (inputRef.current) resizeComposer(inputRef.current, input);
  }, [input]);

  async function handleSend(raw?: string) {
    const text = (raw ?? input).trim() || (attachments.length ? 'Analyze the attached image in this research context.' : '');
    if (!text || isRunning) return;
    if (agentSurface === 'project' && !activeProjectId) {
      setComposerError('Open or create a project (Notebook) so the agent has project context.');
      return;
    }
    setComposerError(null);
    setInput('');
    const pendingAttachments = attachments;
    setAttachments([]);
    if (inputRef.current) resizeComposer(inputRef.current, '');
    // Single session agent path — materials + project tools share context.
    await sendMessage(text, pendingAttachments);
  }

  function handleFileSelected(file: File | undefined) {
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) {
      setComposerError('Choose a file smaller than 8 MB.');
      return;
    }
    const isImage = file.type.startsWith('image/');
    const isAudio = file.type.startsWith('audio/');
    if (isImage && !modelCapability.supportsImages) {
      setComposerError('The active model does not accept images.');
      return;
    }
    if (isAudio && !modelCapability.supportsImages && !modelCapability.supportsAudio) {
      setComposerError('Use dictation (mic) for speech, or attach an image.');
      return;
    }
    if (!isImage && !isAudio) {
      setComposerError('Attach an image (or short audio clip). For speech, use dictation or Voice mode.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || '');
      const data = result.includes(',') ? result.slice(result.indexOf(',') + 1) : '';
      if (!data) return;
      setAttachments([{ name: file.name, mime_type: file.type || 'application/octet-stream', data }]);
      setComposerError(null);
      setCapabilitiesOpen(false);
      inputRef.current?.focus();
    };
    reader.onerror = () => setComposerError('Could not read that file.');
    reader.readAsDataURL(file);
  }

  function stopDictation() {
    if (dictationRef.current) {
      try {
        dictationRef.current.stop();
      } catch {
        /* ignore */
      }
      dictationRef.current = null;
      setDictating(false);
    }
  }

  async function endVoiceSession() {
    stopDictation();
    await disconnectVoiceLive({ preserveError: false, silent: false });
  }

  async function startVoiceSession(opts?: { withScreenShare?: boolean }) {
    stopDictation();
    voiceActions.setViewMode('none');
    const layout = useLayoutStore.getState();
    await connectVoiceLive({
      sessionId: currentSessionId,
      withScreenShare: opts?.withScreenShare,
      workspace: {
        project_id: activeProjectId || undefined,
        material_id: workspace?.resolvedMaterialId,
        resolved_material_id: workspace?.resolvedMaterialId,
        current_material_id: workspace?.resolvedMaterialId,
        formula_pretty: workspace?.title,
        title: workspace?.title,
        rail_mode: layout.railMode,
        workspace_tab: layout.workspaceTab,
        hop_depth: layout.hopDepth,
        agent_surface: agentSurface,
        genomics_case_id: layout.genomicsCaseId,
        genomics_variant_index: layout.genomicsVariantIndex,
        genomics_repeat_count: layout.genomicsRepeatCount,
      },
    });
    voiceActions.setViewMode('none');
  }

  async function handleVoiceClick() {
    if (!voiceState.isActive) {
      await startVoiceSession();
      return;
    }
    // End / Cancel — hard stop mic + screen + socket
    await endVoiceSession();
  }

  async function handleToggleScreenShare() {
    try {
      if (!voiceState.isActive) {
        // Start Live then share screen (model can see the workspace)
        await startVoiceSession({ withScreenShare: true });
        return;
      }
      if (voiceState.screenActive) {
        await setScreenShareEnabled(false);
      } else {
        await setScreenShareEnabled(true);
      }
    } catch (err) {
      setComposerError(err instanceof Error ? err.message : 'Screen share failed');
    }
  }

  function handleDictationClick() {
    if (dictationRef.current) {
      stopDictation();
      return;
    }
    // Dictation is local STT only — never leave Live voice half-open.
    if (voiceState.isActive) {
      void endVoiceSession();
    }
    const Recognition = getSpeechRecognition();
    if (!Recognition) {
      setComposerError('Dictation is not available in this browser. Try Chrome/Edge, or use Voice mode.');
      return;
    }
    setComposerError(null);
    const recognition = new Recognition();
    // Continuous until user stops — better for research prompts.
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = navigator.language || 'en-US';
    let committed = '';
    recognition.onresult = (event) => {
      let interim = '';
      let finalChunk = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const piece = event.results[i]?.[0]?.transcript || '';
        if (event.results[i]?.isFinal) finalChunk += piece;
        else interim += piece;
      }
      if (finalChunk.trim()) {
        committed = `${committed} ${finalChunk}`.replace(/\s+/g, ' ').trim();
      }
      const next = `${committed}${interim ? ` ${interim}` : ''}`.replace(/\s+/g, ' ').trim();
      if (!next) return;
      setInput((prev) => {
        // If user already typed, append dictation rather than wipe.
        if (prev.trim() && !committed.startsWith(prev.trim())) {
          const base = prev.trim();
          const merged = `${base} ${next}`.replace(/\s+/g, ' ').trim();
          window.setTimeout(() => {
            if (inputRef.current) resizeComposer(inputRef.current, merged);
          }, 0);
          return merged;
        }
        window.setTimeout(() => {
          if (inputRef.current) resizeComposer(inputRef.current, next);
        }, 0);
        return next;
      });
    };
    recognition.onerror = (event) => {
      const code = String(event?.error || '');
      if (code === 'aborted' || code === 'no-speech') return;
      setComposerError(code === 'not-allowed' ? 'Microphone permission denied for dictation.' : 'Dictation could not access the microphone.');
      setDictating(false);
      dictationRef.current = null;
    };
    recognition.onend = () => {
      // Auto-restart while still in dictating mode (browser ends after silence).
      if (dictationRef.current === recognition) {
        try {
          recognition.start();
          return;
        } catch {
          /* fall through */
        }
      }
      dictationRef.current = null;
      setDictating(false);
    };
    dictationRef.current = recognition;
    setDictating(true);
    recognition.start();
  }

  const hasText = input.trim().length > 0 || attachments.length > 0;
  const transcriptMessages = voiceState.transcript
    .filter((line) => line.role === 'user' || !isInternalLiveText(line.text))
    .map((line) => ({
      id: line.id,
      role: line.role,
      text: line.text,
    }));
  const mergedMessages = [...messages, ...transcriptMessages];
  const latestAssistantId = [...messages].reverse().find((message) => message.role === 'assistant')?.id || null;

  return (
    <div className={compact ? 'jarvis-agent-shell text-[13px]' : 'jarvis-agent-shell'}>
      {!compact ? (
        <div className="jarvis-agent-header">
          <div className="jarvis-agent-title">
            <span className="jarvis-agent-info" title={contextLine} aria-label={contextLine}>
              <img src="/icons/info.png" alt="" className="jarvis-agent-info-img" draggable={false} />
            </span>
            <div className="jarvis-agent-title-text">
              {editingTitle ? (
                <input
                  className="jarvis-session-title-input"
                  value={titleDraft}
                  autoFocus
                  onChange={(event) => setTitleDraft(event.target.value)}
                  onBlur={() => {
                    if (currentSessionId && titleDraft.trim()) void renameSession(currentSessionId, titleDraft);
                    setEditingTitle(false);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      if (currentSessionId && titleDraft.trim()) void renameSession(currentSessionId, titleDraft);
                      setEditingTitle(false);
                    }
                    if (event.key === 'Escape') setEditingTitle(false);
                  }}
                  aria-label="Rename session"
                />
              ) : (
                <button
                  type="button"
                  className="jarvis-session-title-button text-[15px] font-semibold leading-5"
                  title="Click to rename chat"
                  onClick={() => {
                    setTitleDraft(activeSession?.title || 'New chat');
                    setEditingTitle(true);
                  }}
                >
                  {activeSession?.title || 'New chat'}
                </button>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              if (isRunning) return;
              // New chat must not leave Live mic / screen share running.
              stopDictation();
              void disconnectVoiceLive({ silent: true });
              void newChat();
            }}
            disabled={isRunning}
            className="jarvis-icon-button disabled:opacity-40"
            title="New chat"
            aria-label="New chat"
          >
            <JarvisRawIcon name="newChat" className="h-4 w-4" />
          </button>
        </div>
      ) : null}

      <div className="jarvis-agent-scroll">
        {mergedMessages.length === 0 ? (
          <div className="jarvis-agent-empty">
            <p className="jarvis-empty-copy">
              {agentSurface === 'project'
                ? 'How can I help with this project?'
                : agentSurface === 'genes'
                  ? 'How can I help with this DNA variant demo?'
                  : 'How can I help with this material?'}
            </p>
            {starters.map((prompt) => (
              <button key={prompt} type="button" onClick={() => void handleSend(prompt)} className="jarvis-starter-button">
                <span>{prompt}</span>
                <ChevronRightIcon className="h-4 w-4 shrink-0 opacity-80" />
              </button>
            ))}
          </div>
        ) : (
          <div className="jarvis-message-stack">
            {mergedMessages.map((msg) => {
              const role = msg.role === 'user' ? 'user' : msg.role === 'assistant' ? 'assistant' : 'error';
              const messageTimestamp = 'timestamp' in msg && typeof msg.timestamp === 'number' ? msg.timestamp : Date.now();
              // Hide empty streaming placeholder — ActivityLine covers the wait state.
              if (role === 'assistant' && isRunning && msg.id === latestAssistantId && !(msg.text || '').trim()) {
                return null;
              }
              return (
                <Fragment key={msg.id}>
                  <article className={`jarvis-message jarvis-message-${role}`}>
                    {role === 'assistant' || role === 'error' ? (
                      <div>
                        <div className="jarvis-agent-message-meta">
                          <span>{role === 'assistant' ? 'Catalyst' : 'System'}</span>
                          <time dateTime={new Date(messageTimestamp).toISOString()}>{new Date(messageTimestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
                        </div>
                        <div className="jarvis-prose">
                          <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                            {msg.text || ''}
                          </ReactMarkdown>
                        </div>
                      </div>
                    ) : (
                      <div className="jarvis-message-text">{msg.text}</div>
                    )}
                  </article>
                </Fragment>
              );
            })}
            {showActivityShimmer && activityLabel ? <ActivityLine label={activityLabel} /> : null}
          </div>
        )}
        {mergedMessages.length === 0 && showActivityShimmer && activityLabel ? (
          <ActivityLine label={activityLabel} />
        ) : null}
        <div ref={bottomRef} />
      </div>

      {showInput ? (
        <div className="jarvis-agent-composer-wrap">
          {attachments.length ? (
            <div className="jarvis-agent-attachments">
              {attachments.map((attachment) => (
                <div key={attachment.name} className="jarvis-attachment-chip">
                  <span className="truncate">{attachment.name}</span>
                  <button type="button" onClick={() => setAttachments([])} aria-label={`Remove ${attachment.name}`}>x</button>
                </div>
              ))}
            </div>
          ) : null}
          <div className="jarvis-agent-composer">
            <div ref={capabilityRef} className="relative">
              <button
                ref={capabilityButtonRef}
                type="button"
                className="jarvis-composer-icon"
                title="Model and files"
                aria-label="Model and files"
                aria-haspopup="menu"
                aria-expanded={capabilitiesOpen}
                onClick={() => setCapabilitiesOpen((value) => !value)}
              >
                <PlusIcon className="h-5 w-5" />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,.md,.txt,.pdf,.csv,.json"
                className="sr-only"
                onChange={(event) => {
                  handleFileSelected(event.target.files?.[0]);
                  event.currentTarget.value = '';
                }}
              />
              {capabilitiesOpen ? (
                <CapabilityMenu
                  modelId={modelCapability.modelId || modelCapability.label}
                  models={availableModels}
                  supportsImages={modelCapability.supportsImages}
                  voiceActive={voiceState.isActive}
                  screenActive={voiceState.screenActive}
                  onSelectModel={(modelId) => {
                    void setModel(modelId);
                  }}
                  onAddFile={() => fileInputRef.current?.click()}
                  onToggleScreenShare={() => {
                    void handleToggleScreenShare();
                  }}
                  onClose={() => setCapabilitiesOpen(false)}
                />
              ) : null}
            </div>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(event) => {
                const next = event.target.value;
                setInput(next);
                resizeComposer(event.currentTarget, next);
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  void handleSend();
                }
              }}
              rows={1}
              placeholder={agentSurface === 'project' ? 'Ask about this project, notebook, or files...' : agentSurface === 'genes' ? 'Ask about this marker, sequence window, or CTG repeat count...' : 'Ask about materials, structure, or screening...'}
              className="jarvis-agent-input"
              style={{ height: COMPOSER_MIN_HEIGHT, overflowY: 'hidden', alignSelf: 'end' }}
            />
            <div className="jarvis-composer-actions">
              {voiceState.isActive ? (
                <button
                  type="button"
                  onClick={() => void handleVoiceClick()}
                  className={voiceState.isConnecting ? 'jarvis-voice-pill connecting' : 'jarvis-voice-pill'}
                  title={voiceState.isConnecting ? 'Cancel voice' : 'End voice'}
                  aria-label={voiceState.isConnecting ? 'Cancel voice' : 'End voice'}
                >
                  {voiceState.isConnecting ? (
                    <>
                      <SpinnerIcon className="h-4 w-4 animate-spin" />
                      <span>Cancel</span>
                    </>
                  ) : (
                    <>
                      <span className="jarvis-pill-dots" aria-hidden="true">
                        <span />
                        <span />
                        <span />
                      </span>
                      <span>End</span>
                    </>
                  )}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={handleDictationClick}
                    className={dictating ? 'jarvis-composer-icon active' : 'jarvis-composer-icon'}
                    title={dictating ? 'Stop dictation' : 'Dictate'}
                    aria-label={dictating ? 'Stop dictation' : 'Dictate'}
                  >
                    <MicIcon className="h-5 w-5" />
                  </button>
                  {hasText || isRunning ? (
                    <button
                      type="button"
                      onClick={() => void handleSend()}
                      disabled={isRunning || !hasText}
                      className="jarvis-send-button"
                      title="Send message"
                      aria-label="Send message"
                    >
                      {isRunning ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <SendArrowIcon className="h-5 w-5" />}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => void handleVoiceClick()}
                      className="jarvis-voice-button"
                      title="Voice mode"
                      aria-label="Voice mode"
                    >
                      <VoiceBarsIcon className="h-5 w-5" />
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
          {voiceState.isActive ? (
            <div className="jarvis-voice-status" aria-live="polite">
              {voiceState.isConnecting ? (
                <span className="jarvis-voice-status-connecting">Connecting...</span>
              ) : (
                <>
                  <span>
                    {voiceStatusLabel(voiceState)}
                    {voiceState.screenActive ? ' · Screen shared' : ''}
                  </span>
                  <strong>{formatDuration(voiceElapsedMs)}</strong>
                </>
              )}
            </div>
          ) : null}
          {voiceState.lastError ? <div className="jarvis-voice-error" role="alert">{voiceState.lastError}</div> : null}
          {composerError ? <div className="jarvis-voice-error" role="alert">{composerError}</div> : null}
        </div>
      ) : null}
    </div>
  );
}

