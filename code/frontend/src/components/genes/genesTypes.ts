export type GenomicsCase = {
  case_id: 'brca1' | 'hbb' | 'ctg'; title: string; gene: string; subtitle: string; kind: 'variant' | 'repeat_expansion'; variant_id?: string;
  sequence_window: string; highlighted_index: number; summary: string; interpretation: string; source_label: string; source_url?: string; default_repeat_count?: number;
};
