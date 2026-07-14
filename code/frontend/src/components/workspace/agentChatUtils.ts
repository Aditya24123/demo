import { useEffect, useState } from 'react';

export function useElapsedMs(active: boolean, startedAt: number | null): number {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!active || !startedAt) return undefined;
    const tick = () => setElapsedMs(Math.max(0, Date.now() - startedAt));
    const kickoff = window.setTimeout(tick, 0);
    const interval = window.setInterval(tick, 1000);
    return () => {
      window.clearTimeout(kickoff);
      window.clearInterval(interval);
    };
  }, [active, startedAt]);

  if (!active || !startedAt) return 0;
  return elapsedMs;
}

export function formatDuration(elapsedMs: number): string {
  const seconds = Math.max(0, Math.floor(elapsedMs / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

export function voiceStatusLabel(state: {
  lastError?: string | null;
  isConnecting?: boolean;
  isConnected?: boolean;
  isMuted?: boolean;
  isSpeaking?: boolean;
}): string {
  if (state.lastError) return 'Error';
  if (state.isConnecting) return 'Connecting';
  if (state.isMuted) return 'Muted';
  if (state.isSpeaking) return 'Speaking';
  return state.isConnected ? 'Listening' : 'Ending';
}
