/** Compact live state for the bounded DNA viewer and its AI context. */
export type SelectedVariant = { hgvs: string; reference: string; alternate: string; id?: string; position?: number };

export type GenomeState = {
  gene: string;
  coordinate_system: 'gene_relative_1_based_inclusive';
  visibleStart: number;
  visibleEnd: number;
  selectedPosition: number;
  sequence: string;
  geneLength: number;
  selectedVariant: SelectedVariant | null;
  source?: { provider?: string; ensembl_id?: string; cached?: boolean };
};

export const DEFAULT_GENOME_STATE: GenomeState = {
  gene: 'BRCA1',
  coordinate_system: 'gene_relative_1_based_inclusive',
  visibleStart: 12755,
  visibleEnd: 12786,
  selectedPosition: 12770,
  sequence: '',
  geneLength: 0,
  selectedVariant: { hgvs: 'c.68_69delAG', reference: 'AG', alternate: '-', id: 'rs80357906', position: 12770 },
};

export function normalizeGenomeState(input: Partial<GenomeState>): GenomeState {
  const start = Math.max(1, Math.round(Number(input.visibleStart) || DEFAULT_GENOME_STATE.visibleStart));
  const end = Math.max(start, Math.round(Number(input.visibleEnd) || start));
  return {
    ...DEFAULT_GENOME_STATE,
    ...input,
    gene: String(input.gene || DEFAULT_GENOME_STATE.gene).toUpperCase(),
    visibleStart: start,
    visibleEnd: end,
    selectedPosition: Math.max(start, Math.min(end, Math.round(Number(input.selectedPosition) || start))),
    sequence: String(input.sequence || '').replace(/[^ACGTN]/gi, '').toUpperCase(),
    geneLength: Math.max(0, Math.round(Number(input.geneLength) || 0)),
  };
}
