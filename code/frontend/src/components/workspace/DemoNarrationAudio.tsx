import { useEffect, useRef } from 'react';
import { useCatalystLayout } from '@/catalyst/bridge/hooks';

/**
 * Keeps the guided narration in sync with the deterministic demo without
 * adding visible controls or progress chrome to the scientific workspace.
 */
export function DemoNarrationAudio() {
  const { demoState } = useCatalystLayout();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastNarrationStart = useRef<number | null>(null);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !demoState.running || !demoState.startedAt || lastNarrationStart.current === demoState.startedAt) return;
    lastNarrationStart.current = demoState.startedAt;
    audio.currentTime = 0;
    void audio.play().catch(() => {});
  }, [demoState.running, demoState.startedAt]);

  useEffect(() => {
    const reset = () => {
      const audio = audioRef.current;
      if (!audio) return;
      audio.pause();
      audio.currentTime = 0;
      lastNarrationStart.current = null;
    };
    window.addEventListener('catalyst:demo-reset', reset);
    return () => window.removeEventListener('catalyst:demo-reset', reset);
  }, []);

  return <audio ref={audioRef} src="/audio/from-sunscreen-to-dna.mp3" preload="auto" />;
}
