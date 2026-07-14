import { Check, RotateCcw, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useCatalystLayout } from '@/catalyst/bridge/hooks';

export function DemoMissionProgress() {
  const { demoState, resetDemo, setRailMode, resetGenomicsCamera } = useCatalystLayout();
  const [now, setNow] = useState(Date.now());
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastNarrationStart = useRef<number | null>(null);

  useEffect(() => {
    if (!demoState.running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [demoState.running]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !demoState.running || !demoState.startedAt || lastNarrationStart.current === demoState.startedAt) return;
    lastNarrationStart.current = demoState.startedAt;
    audio.currentTime = 0;
    void audio.play().then(() => {
      // Audio is intentionally ambient: the guided investigation owns playback.
    }).catch(() => {});
  }, [demoState.running, demoState.startedAt]);

  const currentIndex = useMemo(
    () => demoState.mission.findIndex((step) => step.id === demoState.currentStepId),
    [demoState.currentStepId, demoState.mission],
  );
  if (!demoState.scenarioId) return null;
  const elapsed = demoState.startedAt ? Math.max(0, now - demoState.startedAt) : 0;
  const seconds = Math.floor(elapsed / 1000);

  const reset = () => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    window.dispatchEvent(new CustomEvent('catalyst:demo-reset'));
    resetDemo();
    resetGenomicsCamera();
    setRailMode('home');
  };

  return (
    <div style={{ position: 'fixed', top: 12, left: '50%', transform: 'translateX(-50%)', zIndex: 80, width: 'min(720px, calc(100vw - 380px))', minWidth: 420, border: '1px solid rgba(56,189,248,.34)', borderRadius: 14, background: 'rgba(5,10,18,.92)', boxShadow: '0 18px 60px rgba(0,0,0,.35)', backdropFilter: 'blur(16px)', padding: '10px 12px', color: '#e2e8f0' }}>
      <audio ref={audioRef} src="/audio/from-sunscreen-to-dna.mp3" preload="auto" />
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        <Sparkles size={15} color="#67e8f9" />
        <strong style={{ fontSize: 12, flex: 1 }}>{demoState.title}</strong>
        <span style={{ fontSize: 11, color: '#94a3b8' }}>{demoState.complete ? 'Complete' : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`}</span>
        <button type="button" onClick={reset} title="Reset demo" style={{ display: 'inline-flex', alignItems: 'center', gap: 5, border: '1px solid rgba(148,163,184,.25)', borderRadius: 8, padding: '4px 7px', color: '#cbd5e1', background: 'rgba(15,23,42,.72)', fontSize: 11 }}><RotateCcw size={12} /> Reset</button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.max(1, demoState.mission.length)}, minmax(0, 1fr))`, gap: 5, marginTop: 9 }}>
        {demoState.mission.map((step, index) => {
          const done = demoState.complete || index < currentIndex;
          const active = !demoState.complete && index === currentIndex;
          return <div key={step.id} style={{ minWidth: 0 }}><div style={{ height: 3, borderRadius: 10, background: done ? '#22d3ee' : active ? '#38bdf8' : '#263244', boxShadow: active ? '0 0 14px rgba(56,189,248,.7)' : 'none' }} /><div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 5, fontSize: 9.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: done || active ? '#dbeafe' : '#64748b' }}>{done && <Check size={10} />}{step.label}</div></div>;
        })}
      </div>
    </div>
  );
}
