import { ExternalLink, MessageCircle, RotateCcw, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { DnaViewer } from '@/components/genes/DnaViewer';
import type { GenomicsCase } from '@/components/genes/genesTypes';
import { useCatalystLayout } from '@/catalyst/bridge/hooks';
import { api } from '@/lib/api';

const FALLBACK_CASES: GenomicsCase[] = [
  { case_id: 'brca1', title: 'BRCA1 marker', gene: 'BRCA1', subtitle: 'DNA repair-associated gene', kind: 'variant', variant_id: 'rs80357906', sequence_window: 'AAAGCGTGGGAATTACAGATAAATTAAAACTG', highlighted_index: 7, summary: 'A representative BRCA1 sequence window with one highlighted variant marker.', interpretation: 'Demo sequence window - inspect the selected marker with Catalyst.', source_label: 'Curated demo snapshot' },
  { case_id: 'hbb', title: 'HBB marker', gene: 'HBB', subtitle: 'Hemoglobin beta gene', kind: 'variant', variant_id: 'rs334', sequence_window: 'ACATTTGCTTCTGACACAACTGTGTTCACTAGC', highlighted_index: 7, summary: 'A representative HBB sequence window with a highlighted coding marker.', interpretation: 'Demo sequence window - ask Catalyst to explain the marker context.', source_label: 'Curated demo snapshot' },
  { case_id: 'ctg', title: 'CTG expansion', gene: 'DMPK', subtitle: 'Myotonic dystrophy repeat model', kind: 'repeat_expansion', sequence_window: 'CTGCTGCTGCTGCTGCTGCTGCTGCTGCTGCTG', highlighted_index: 8, summary: 'A repeat-expansion model. The slider controls the demonstration repeat count.', interpretation: 'Repeat length is the visual parameter in this demo.', source_label: 'Curated demo snapshot', default_repeat_count: 55 },
];

function repeatState(value: number) {
  if (value <= 37) return { label: 'Normal range', color: '#34d399', text: 'Up to 37 repeats' };
  if (value <= 49) return { label: 'Pre-mutation range', color: '#fbbf24', text: '38-49 repeats' };
  return { label: 'Disease range', color: '#fb7185', text: '50+ repeats' };
}

export function GenesMode() {
  const [cases, setCases] = useState<GenomicsCase[]>(FALLBACK_CASES);
  const { genomicsCaseId, setGenomicsCaseId, genomicsVariantIndex, setGenomicsVariantIndex, genomicsRepeatCount, setGenomicsRepeatCount, genomicsResetNonce, resetGenomicsCamera, setInspectorOpen, setInspectorTab, genomeState, setGenomeState, setGenomeSelection, genomeSequenceVisible, setGenomeSequenceVisible } = useCatalystLayout();
  const selected = useMemo(() => cases.find((item) => item.case_id === genomicsCaseId) || cases[0], [cases, genomicsCaseId]);
  const repeat = repeatState(genomicsRepeatCount);

  useEffect(() => { void api.getGenomicsCases().then((payload) => { if (Array.isArray(payload?.cases) && payload.cases.length) setCases(payload.cases as GenomicsCase[]); }).catch(() => {}); }, []);
  useEffect(() => { if (selected) setGenomicsVariantIndex(selected.highlighted_index); }, [selected, setGenomicsVariantIndex]);
  useEffect(() => {
    if (selected?.gene !== 'BRCA1') return;
    let cancelled = false;
    void api.getGenomeState('BRCA1', {
      visibleStart: genomeState.gene === 'BRCA1' ? genomeState.visibleStart : undefined,
      visibleEnd: genomeState.gene === 'BRCA1' ? genomeState.visibleEnd : undefined,
      selectedPosition: genomeState.gene === 'BRCA1' ? genomeState.selectedPosition : undefined,
    }).then((state) => { if (!cancelled && state?.sequence) setGenomeState(state); }).catch(() => {});
    return () => { cancelled = true; };
  }, [selected?.gene, genomeState.gene, genomeState.visibleStart, genomeState.visibleEnd, genomeState.selectedPosition, setGenomeState]);
  if (!selected) return null;
  const isBrca = selected.gene === 'BRCA1';
  const displayedSequence = isBrca && genomeState.sequence ? genomeState.sequence : selected.sequence_window;
  const basePairs = displayedSequence.match(/.{1,2}/g) || [];
  const selectedIndex = isBrca
    ? Math.max(0, Math.min(basePairs.length - 1, Math.floor((genomeState.selectedPosition - genomeState.visibleStart) / 2)))
    : genomicsVariantIndex;
  const markerLabel = isBrca ? genomeState.selectedVariant?.id || selected.variant_id : selected.variant_id || 'CTG repeat region';

  return <div className="jarvis-mode-panel" style={{ display: 'flex', flex: 1, minWidth: 0, flexDirection: 'column', height: '100%', minHeight: 0 }}>
    <div className="jarvis-mode-header" style={{ padding: '16px 20px 8px' }}><h1 className="text-[18px] font-semibold tracking-tight" style={{ margin: 0 }}>DNA Variant Explorer</h1><p className="text-[13px]" style={{ margin: '6px 0 0', opacity: 0.72 }}>A bounded, inspectable sequence window - drag to rotate and scroll to zoom.</p></div>
    <div style={{ display: 'flex', flex: 1, minHeight: 0, gap: 12, padding: '8px 20px 20px' }}>
      <div style={{ flex: 1, minWidth: 0, minHeight: 420, position: 'relative', overflow: 'hidden', borderRadius: 14, border: '1px solid var(--border-subtle, #273244)', background: '#090d15' }}>
        <DnaViewer basePairs={basePairs} selectedIndex={selectedIndex} onSelect={(index) => isBrca ? setGenomeSelection(genomeState.visibleStart + index * 2) : setGenomicsVariantIndex(index)} resetNonce={genomicsResetNonce} />
        <div style={{ position: 'absolute', top: 12, left: 12, padding: '8px 10px', borderRadius: 10, background: 'rgba(9,13,21,0.82)', border: '1px solid rgba(148,163,184,0.22)', fontSize: 12 }}><div style={{ color: '#f8fafc', fontWeight: 650 }}>{selected.gene} sequence window</div><div style={{ color: '#94a3b8', marginTop: 2 }}>{isBrca ? `Positions ${genomeState.visibleStart}-${genomeState.visibleEnd}` : `Marker ${selectedIndex + 1} of ${basePairs.length}`}</div></div>
        <button type="button" onClick={resetGenomicsCamera} title="Reset camera" style={{ position: 'absolute', right: 12, top: 12, width: 34, height: 34, display: 'grid', placeItems: 'center', borderRadius: 9, border: '1px solid rgba(148,163,184,0.26)', background: 'rgba(9,13,21,0.82)', color: '#e2e8f0' }}><RotateCcw size={15} /></button>
      </div>
      <aside style={{ width: 286, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }}>
        <div style={{ display: 'grid', gap: 6 }}>{cases.map((item) => <button key={item.case_id} type="button" onClick={() => setGenomicsCaseId(item.case_id)} style={{ textAlign: 'left', padding: '10px 11px', borderRadius: 10, border: `1px solid ${item.case_id === selected.case_id ? '#38bdf8' : 'var(--border-subtle, #334155)'}`, background: item.case_id === selected.case_id ? 'rgba(14,116,144,0.18)' : 'var(--surface-1, rgba(15,23,42,0.6))', color: 'inherit' }}><div style={{ fontSize: 13, fontWeight: 650 }}>{item.title}</div><div style={{ fontSize: 11, opacity: 0.68, marginTop: 2 }}>{item.subtitle}</div></button>)}</div>
        <div style={{ padding: 13, borderRadius: 12, border: '1px solid var(--border-subtle, #334155)', background: 'var(--surface-1, rgba(15,23,42,0.6))' }}><div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '.08em', opacity: .58 }}>Selected marker</div><div style={{ marginTop: 7, fontSize: 17, fontWeight: 700 }}>{markerLabel}</div>{isBrca && <div style={{ marginTop: 5, fontSize: 12, color: '#bae6fd' }}>Position {genomeState.selectedPosition} ? {genomeState.selectedVariant?.hgvs} ? {genomeState.selectedVariant?.reference} ? {genomeState.selectedVariant?.alternate}</div>}<p style={{ margin: '8px 0', fontSize: 13, lineHeight: 1.5, opacity: .8 }}>{selected.summary}</p><div style={{ fontSize: 12, lineHeight: 1.45, color: '#bae6fd' }}>{selected.interpretation}</div><div style={{ marginTop: 10, fontSize: 11, opacity: .54 }}>{selected.source_url ? <a href={selected.source_url} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#94dfff' }}>{selected.source_label}<ExternalLink size={11} /></a> : selected.source_label}</div></div>
        {isBrca && <div style={{ padding: 11, borderRadius: 12, border: '1px solid rgba(56,189,248,0.25)', background: 'rgba(14,116,144,0.08)' }}><div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}><span style={{ fontSize: 12, fontWeight: 650 }}>Visible sequence only</span><button type="button" onClick={() => setGenomeSequenceVisible(!genomeSequenceVisible)} style={{ border: 0, borderRadius: 7, padding: '4px 7px', background: 'rgba(56,189,248,0.16)', color: '#bae6fd', fontSize: 11 }}>{genomeSequenceVisible ? 'Hide' : 'Show'}</button></div>{genomeSequenceVisible && <code style={{ display: 'block', marginTop: 8, overflowWrap: 'anywhere', fontSize: 11, lineHeight: 1.55, color: '#dbeafe' }}>{displayedSequence}</code>}</div>}
        {selected.kind === 'repeat_expansion' && <div style={{ padding: 13, borderRadius: 12, border: `1px solid ${repeat.color}55`, background: `${repeat.color}12` }}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}><span>CTG repeat count</span><strong style={{ color: repeat.color }}>{genomicsRepeatCount}</strong></div><input aria-label="CTG repeat count" type="range" min="0" max="100" value={genomicsRepeatCount} onChange={(event) => setGenomicsRepeatCount(Number(event.target.value))} style={{ width: '100%', marginTop: 9, accentColor: repeat.color }} /><div style={{ fontSize: 12, color: repeat.color, fontWeight: 650 }}>{repeat.label}</div><div style={{ marginTop: 2, fontSize: 11, opacity: .7 }}>{repeat.text}</div></div>}
        <button type="button" onClick={() => { setInspectorOpen(true); setInspectorTab('agent'); }} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 10px', borderRadius: 10, border: '1px solid rgba(56,189,248,0.28)', textAlign: 'left', fontSize: 12, background: 'rgba(56,189,248,0.08)', color: '#bae6fd' }}><MessageCircle size={14} /><span style={{ flex: 1 }}>Ask Catalyst about this case</span><Sparkles size={13} /></button>
      </aside>
    </div>
  </div>;
}
