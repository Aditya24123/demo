/**
 * User-facing model / provider labels (hackathon-safe).
 * Internal ids stay unchanged for routing; only display is generic.
 */

const MODEL_LABELS: Record<string, string> = {
  // Subscription profiles (internal ids)
  'agy/3.5-flash-low': 'Fast',
  'agy/3.5-flash-medium': 'Balanced',
  'agy/3.5-flash-high': 'Deep',
  'agy/3.1-pro-low': 'Pro ? Fast',
  'agy/3.1-pro-high': 'Pro ? Deep',
  'agy/claude-sonnet-thinking': 'Reasoning ? Sonnet',
  'agy/claude-opus-thinking': 'Reasoning ? Opus',
  'agy/gpt-oss-120b': 'Open ? 120B',
  // Direct API fallbacks
  'gemini-3.1-flash-lite': 'Lite',
  'gemini-2.5-flash': 'Standard',
  'gemini-2.5-pro': 'Pro',
  // Micro gateway
  'auto/best-chat': 'Auto ? Chat',
  'auto/best-reasoning': 'Auto ? Reasoning',
  'auto/best-fast': 'Auto ? Fast',
  'auto/best-coding': 'Auto ? Coding',
  'auto/fast': 'Auto ? Fast',
};

const PROVIDER_LABELS: Record<string, string> = {
  gemini: 'Primary',
  micro: 'Gateway',
  groq: 'Groq',
  mistral: 'Mistral',
  nvidia: 'NVIDIA',
  ollama: 'Local',
  ollama_cloud: 'Cloud local',
  openai: 'OpenAI',
};

/** Hide vendor-y substrings if an unknown id slips through. */
function scrubRawId(id: string): string {
  return id
    .replace(/^agy\//i, '')
    .replace(/^gemini[-_]?/i, '')
    .replace(/antigravity/gi, 'agent')
    .replace(/google/gi, '')
    .replace(/[-_]+/g, ' ')
    .trim();
}

export function modelDisplayLabel(modelId: string | null | undefined): string {
  const id = String(modelId || '').trim();
  if (!id) return 'Default model';
  if (MODEL_LABELS[id]) return MODEL_LABELS[id];
  // CLI display names that may leak through citations
  if (/flash \(low\)/i.test(id)) return 'Fast';
  if (/flash \(medium\)/i.test(id)) return 'Balanced';
  if (/flash \(high\)/i.test(id)) return 'Deep';
  if (/pro \(low\)/i.test(id)) return 'Pro ? Fast';
  if (/pro \(high\)/i.test(id)) return 'Pro ? Deep';
  if (/claude sonnet/i.test(id)) return 'Reasoning ? Sonnet';
  if (/claude opus/i.test(id)) return 'Reasoning ? Opus';
  if (/gpt-oss|120b/i.test(id)) return 'Open ? 120B';
  const scrubbed = scrubRawId(id);
  return scrubbed || 'Model';
}

export function providerDisplayLabel(providerId: string | null | undefined): string {
  const id = String(providerId || '').trim().toLowerCase();
  if (!id) return 'Agent';
  if (PROVIDER_LABELS[id]) return PROVIDER_LABELS[id];
  if (id === 'antigravity' || id === 'agy') return 'Agent';
  return scrubRawId(id) || 'Provider';
}
