export type HomeTab = 'neighbors' | 'structure' | 'spectra';
export type RailMode = 'home' | 'genes' | 'notebook' | 'graph' | 'candidates' | 'add_material' | 'settings';
export type CommandMode = 'search' | 'ask' | 'screen';

export type SearchFilters = {
  stable: 'any' | 'stable';
  metal: 'any' | 'metal' | 'non_metal';
  magnetic: 'any' | 'magnetic' | 'non_magnetic';
  band_gap_min: string;
  band_gap_max: string;
  density_min: string;
  density_max: string;
  elements: string;
  evidence: string;
};

export const EMPTY_FILTERS: SearchFilters = {
  stable: 'any',
  metal: 'any',
  magnetic: 'any',
  band_gap_min: '',
  band_gap_max: '',
  density_min: '',
  density_max: '',
  elements: '',
  evidence: '',
};
