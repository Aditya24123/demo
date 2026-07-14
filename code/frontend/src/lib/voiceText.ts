/**
 * Filter Live model noise so chat only shows user-facing speech/transcripts.
 * Tool dumps, "thinking" monologues, and JSON function calls stay out of the thread.
 */

const INTERNAL_PATTERNS: RegExp[] = [
  /^TOOL_CALL\s*:/i,
  /^Using\s+[\w_.-]+\s*\.\.\.?$/i,
  /function\s*call/i,
  /functionCall/i,
  /"name"\s*:\s*"[a-z0-9_]+"\s*,\s*"args"/i,
  /^\s*```(?:json|tool|typescript|python)?\s*[\s\S]*"name"\s*:/i,
  /^\s*Thought\s*:/i,
  /^\s*\*\*Thinking\*\*/i,
  /^\s*Thinking\b[.?]*$/i,
  /^\s*\[thinking\]/i,
  /^\s*Live tools ready\b/i,
  /^\s*tool_call\b/i,
  /^\s*call\s+[a-z_]+\s*\(/i,
];

export function isInternalLiveText(text: string | null | undefined): boolean {
  const t = String(text || '').trim();
  if (!t) return true;
  if (t.length > 4000 && /"name"\s*:/.test(t) && /"args"\s*:/.test(t)) return true;
  return INTERNAL_PATTERNS.some((re) => re.test(t));
}

/** Strip leading thought blocks; return null if nothing user-facing remains. */
export function sanitizeLiveAssistantText(text: string | null | undefined): string | null {
  let t = String(text || '').trim();
  if (!t || isInternalLiveText(t)) return null;

  // Drop fenced tool/json blocks
  t = t.replace(/```(?:json|tool)[\s\S]*?```/gi, '').trim();
  // Drop "Thought: ?" lines
  t = t
    .split('\n')
    .filter((line) => {
      const s = line.trim();
      if (!s) return true;
      if (/^Thought\s*:/i.test(s)) return false;
      if (/^TOOL_CALL\s*:/i.test(s)) return false;
      if (/^Using\s+[\w_.-]+/i.test(s) && s.length < 80) return false;
      return true;
    })
    .join('\n')
    .trim();

  if (!t || isInternalLiveText(t)) return null;
  return t;
}
