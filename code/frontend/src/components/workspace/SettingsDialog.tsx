import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useCatalystLayout, useCatalystSettings, useCatalystStatus } from '@/catalyst/bridge/hooks';
import { modelDisplayLabel, providerDisplayLabel } from '@/catalyst/bridge/modelLabels';
import { XIcon } from './JarvisIcons';

type SettingsTab = 'general' | 'providers' | 'services' | 'runtime';

export function SettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { status, backendUrl, isOffline } = useCatalystStatus();
  const { rawSettings, providerStatus, updateSettings } = useCatalystSettings();
  const { theme, setTheme, density, setDensity, hopDepth, setHopDepth } = useCatalystLayout();
  const [tab, setTab] = useState<SettingsTab>('general');
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const titleId = useId();
  const providerNames: string[] = rawSettings?.providers?.provider_order || ['gemini'];
  const initialProvider = rawSettings?.providers?.active_provider || status?.provider?.activeProvider || providerNames[0] || 'gemini';
  const [selectedProvider, setSelectedProvider] = useState(initialProvider);
  const [modelDraft, setModelDraft] = useState(String(rawSettings?.providers?.models?.[initialProvider] || ''));
  const [baseUrlDraft, setBaseUrlDraft] = useState(String(rawSettings?.providers?.base_urls?.[initialProvider] || ''));
  const [keyEnvDraft, setKeyEnvDraft] = useState(String(rawSettings?.providers?.api_key_envs?.[initialProvider] || ''));
  const [apiKeyDraft, setApiKeyDraft] = useState('');
  const [newProviderName, setNewProviderName] = useState('');
  const [savingProvider, setSavingProvider] = useState(false);
  const [testingProvider, setTestingProvider] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [serviceId, setServiceId] = useState('');
  const [serviceTask, setServiceTask] = useState('');
  const [serviceEndpoint, setServiceEndpoint] = useState('');
  const [serviceModel, setServiceModel] = useState('');
  const [serviceKeyEnv, setServiceKeyEnv] = useState('');
  const [savingService, setSavingService] = useState(false);
  const displayedProviderNames = Array.from(new Set([...providerNames, selectedProvider]));

  useEffect(() => {
    if (!open) return undefined;

    const previous = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusTimer = window.setTimeout(() => closeRef.current?.focus(), 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      previous?.focus?.();
    };
  }, [onClose, open]);

  if (!open) return null;

  const provider = status?.provider?.activeProvider || 'Not configured';
  const configuredModel =
    rawSettings?.providers?.models?.[provider] ||
    rawSettings?.settings?.providers?.models?.[provider] ||
    'Backend selected';

  return createPortal(
    <div className="jarvis-dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        ref={dialogRef}
        className="jarvis-settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="jarvis-settings-header">
          <h2 id={titleId}>Settings</h2>
          <button
            ref={closeRef}
            type="button"
            className="jarvis-icon-button"
            onClick={onClose}
            title="Close"
            aria-label="Close settings"
          >
            <XIcon className="h-4 w-4" />
          </button>
        </header>

        <div className="jarvis-settings-layout">
          <nav className="jarvis-settings-nav" aria-label="Settings sections">
            <button type="button" className={tab === 'general' ? 'active' : ''} onClick={() => setTab('general')} aria-current={tab === 'general' ? 'page' : undefined}>
              General
            </button>
            <button type="button" className={tab === 'providers' ? 'active' : ''} onClick={() => setTab('providers')} aria-current={tab === 'providers' ? 'page' : undefined}>
              Models
            </button>
            <button type="button" className={tab === 'services' ? 'active' : ''} onClick={() => setTab('services')} aria-current={tab === 'services' ? 'page' : undefined}>
              Services
            </button>
            <button type="button" className={tab === 'runtime' ? 'active' : ''} onClick={() => setTab('runtime')} aria-current={tab === 'runtime' ? 'page' : undefined}>
              Runtime
            </button>
          </nav>

          <div className="jarvis-settings-content">
            {tab === 'general' ? (
              <>
                <SettingsRow label="Theme">
                  <select value={theme} onChange={(event) => setTheme(event.target.value as 'dark' | 'light')}>
                    <option value="dark">Dark</option>
                    <option value="light">Light</option>
                  </select>
                </SettingsRow>
                <SettingsRow label="Density">
                  <select value={density} onChange={(event) => setDensity(event.target.value as 'comfortable' | 'compact')}>
                    <option value="comfortable">Comfortable</option>
                    <option value="compact">Compact</option>
                  </select>
                </SettingsRow>
                <SettingsRow label="Graph depth">
                  <select value={hopDepth} onChange={(event) => setHopDepth(Number(event.target.value))}>
                    {[1, 2, 3, 4, 5].map((depth) => (
                      <option key={depth} value={depth}>
                        {depth} hops
                      </option>
                    ))}
                  </select>
                </SettingsRow>
              </>
            ) : tab === 'providers' ? (
              <>
                <div className="jarvis-settings-section-heading">Model provider</div>
                <SettingsRow label="Provider">
                  <select
                    value={selectedProvider}
                    onChange={(event) => {
                      const next = event.target.value;
                      setSelectedProvider(next);
                      setModelDraft(String(rawSettings?.providers?.models?.[next] || ''));
                      setBaseUrlDraft(String(rawSettings?.providers?.base_urls?.[next] || ''));
                      setKeyEnvDraft(String(rawSettings?.providers?.api_key_envs?.[next] || ''));
                    }}
                  >
                    {displayedProviderNames.map((name) => (
                      <option key={name} value={name}>{providerDisplayLabel(name)}</option>
                    ))}
                  </select>
                </SettingsRow>
                <SettingsRow label="Status">
                  <strong>{providerStatus?.providers?.[selectedProvider] || 'not configured'}</strong>
                </SettingsRow>
                <SettingsRow label="Model">
                  <input
                    value={modelDraft}
                    onChange={(event) => setModelDraft(event.target.value)}
                    placeholder="Backend default"
                    className="jarvis-settings-input"
                  />
                  {modelDraft ? (
                    <div className="jarvis-settings-note" style={{ marginTop: 6 }}>
                      Shows as: {modelDisplayLabel(modelDraft)}
                    </div>
                  ) : null}
                </SettingsRow>
                <SettingsRow label="Base URL">
                  <input
                    value={baseUrlDraft}
                    onChange={(event) => setBaseUrlDraft(event.target.value)}
                    placeholder="https://provider.example/v1"
                    className="jarvis-settings-input"
                  />
                </SettingsRow>
                <SettingsRow label="API key env">
                  <input
                    value={keyEnvDraft}
                    onChange={(event) => setKeyEnvDraft(event.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ''))}
                    placeholder="MICRO_API_KEY"
                    className="jarvis-settings-input"
                  />
                </SettingsRow>
                <SettingsRow label="API key (server)">
                  <input
                    type="password"
                    value={apiKeyDraft}
                    onChange={(event) => setApiKeyDraft(event.target.value)}
                    placeholder="Paste key ? stored only as server env/secret, not returned"
                    className="jarvis-settings-input"
                    autoComplete="off"
                  />
                </SettingsRow>
                <div className="jarvis-provider-add-row">
                  <input
                    value={newProviderName}
                    onChange={(event) => setNewProviderName(event.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
                    placeholder="custom-provider"
                    aria-label="New provider ID"
                  />
                  <button
                    type="button"
                    className="jarvis-secondary-button"
                    disabled={!newProviderName || displayedProviderNames.includes(newProviderName)}
                    onClick={() => {
                      setSelectedProvider(newProviderName);
                      setModelDraft('');
                      setBaseUrlDraft('');
                      setKeyEnvDraft('');
                      setApiKeyDraft('');
                      setNewProviderName('');
                      setTestResult(null);
                    }}
                  >
                    Add provider
                  </button>
                </div>
                <div className="jarvis-settings-note">
                  Keys live on the server (env var named above). The browser never receives secrets back. Default path is the primary cloud agent; optional micro gateway is OpenAI-compatible last-resort only.
                </div>
                {testResult ? <div className="jarvis-settings-note">{testResult}</div> : null}
                <div className="jarvis-settings-save-row">
                  <button
                    type="button"
                    className="jarvis-secondary-button"
                    disabled={testingProvider || !baseUrlDraft.trim()}
                    onClick={async () => {
                      setTestingProvider(true);
                      setTestResult(null);
                      try {
                        const base = baseUrlDraft.trim().replace(/\/$/, '');
                        const headers: Record<string, string> = {};
                        if (apiKeyDraft.trim()) headers.Authorization = `Bearer ${apiKeyDraft.trim()}`;
                        const response = await fetch(`${base}/models`, { headers });
                        if (!response.ok) throw new Error(`HTTP ${response.status}`);
                        const data = await response.json();
                        const count = Array.isArray(data?.data) ? data.data.length : 0;
                        setTestResult(`Gateway reachable ? ${count || '?'} models`);
                      } catch (err) {
                        setTestResult(`Gateway check failed: ${err instanceof Error ? err.message : 'unknown error'}`);
                      } finally {
                        setTestingProvider(false);
                      }
                    }}
                  >
                    {testingProvider ? 'Testing...' : 'Test endpoint'}
                  </button>
                  <button
                    type="button"
                    className="jarvis-primary-button"
                    disabled={savingProvider}
                    onClick={async () => {
                      setSavingProvider(true);
                      try {
                        await updateSettings({
                          providers: {
                            active_provider: selectedProvider,
                            provider_order: displayedProviderNames,
                            models: {
                              ...(rawSettings?.providers?.models || {}),
                              ...(modelDraft.trim() ? { [selectedProvider]: modelDraft.trim() } : {}),
                            },
                            base_urls: {
                              ...(rawSettings?.providers?.base_urls || {}),
                              ...(baseUrlDraft.trim() ? { [selectedProvider]: baseUrlDraft.trim().replace(/\/$/, '') } : {}),
                            },
                            api_key_envs: {
                              ...(rawSettings?.providers?.api_key_envs || {}),
                              ...(keyEnvDraft.trim() ? { [selectedProvider]: keyEnvDraft.trim() } : {}),
                            },
                          },
                        });
                        if (apiKeyDraft.trim()) {
                          setTestResult(
                            `Provider saved. Paste the key into the server secret/env (${keyEnvDraft.trim() || 'API_KEY'}) if not already set ? this UI does not upload secrets to disk by default.`,
                          );
                          setApiKeyDraft('');
                        }
                      } finally {
                        setSavingProvider(false);
                      }
                    }}
                  >
                    {savingProvider ? 'Saving...' : 'Save provider'}
                  </button>
                </div>
              </>
            ) : tab === 'services' ? (
              <>
                <div className="jarvis-settings-section-heading">Scientific model services</div>
                {Object.entries(rawSettings?.model_services || {}).map(([id, service]) => {
                  const value = service as { task?: string; endpoint?: string; model?: string; api_key_env?: string; enabled?: boolean };
                  return (
                    <button
                      key={id}
                      type="button"
                      className="jarvis-service-row"
                      onClick={() => {
                        setServiceId(id);
                        setServiceTask(value.task || '');
                        setServiceEndpoint(value.endpoint || '');
                        setServiceModel(value.model || '');
                        setServiceKeyEnv(value.api_key_env || '');
                      }}
                    >
                      <span><strong>{id}</strong><small>{value.task || 'Unspecified task'}</small></span>
                      <span>{value.enabled === false ? 'Disabled' : 'Enabled'}</span>
                    </button>
                  );
                })}
                {!Object.keys(rawSettings?.model_services || {}).length ? (
                  <div className="jarvis-settings-note">No scientific services configured yet.</div>
                ) : null}
                <SettingsRow label="Service ID">
                  <input value={serviceId} onChange={(event) => setServiceId(event.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))} placeholder="protein-fold" className="jarvis-settings-input" />
                </SettingsRow>
                <SettingsRow label="Task">
                  <input value={serviceTask} onChange={(event) => setServiceTask(event.target.value)} placeholder="protein-structure-prediction" className="jarvis-settings-input" />
                </SettingsRow>
                <SettingsRow label="Endpoint">
                  <input value={serviceEndpoint} onChange={(event) => setServiceEndpoint(event.target.value)} placeholder="https://models.example/predict" className="jarvis-settings-input" />
                </SettingsRow>
                <SettingsRow label="Model">
                  <input value={serviceModel} onChange={(event) => setServiceModel(event.target.value)} placeholder="Optional model ID" className="jarvis-settings-input" />
                </SettingsRow>
                <SettingsRow label="API key env">
                  <input value={serviceKeyEnv} onChange={(event) => setServiceKeyEnv(event.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ''))} placeholder="MODEL_API_KEY" className="jarvis-settings-input" />
                </SettingsRow>
                <div className="jarvis-settings-save-row">
                  <button
                    type="button"
                    className="jarvis-primary-button"
                    disabled={savingService || !serviceId || !serviceTask || !serviceEndpoint}
                    onClick={async () => {
                      setSavingService(true);
                      try {
                        await updateSettings({
                          model_services: {
                            ...(rawSettings?.model_services || {}),
                            [serviceId]: {
                              endpoint: serviceEndpoint.trim(),
                              task: serviceTask.trim(),
                              model: serviceModel.trim() || null,
                              api_key_env: serviceKeyEnv.trim() || null,
                              enabled: true,
                            },
                          },
                        });
                      } finally {
                        setSavingService(false);
                      }
                    }}
                  >
                    {savingService ? 'Saving...' : 'Save service'}
                  </button>
                </div>
              </>
            ) : (
              <>
                <SettingsValue label="Backend" value={backendUrl || 'Unavailable'} mono />
                <SettingsValue label="Status" value={isOffline ? 'Offline' : status.api === 'online' ? 'Connected' : 'Checking'} />
                <SettingsValue label="Provider" value={provider} />
                <SettingsValue label="Model" value={configuredModel} mono />
              </>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function SettingsRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="jarvis-settings-row">
      <span>{label}</span>
      {children}
    </label>
  );
}

function SettingsValue({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="jarvis-settings-row">
      <span>{label}</span>
      <strong className={mono ? 'jarvis-code' : ''}>{value}</strong>
    </div>
  );
}
