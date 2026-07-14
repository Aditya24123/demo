/** Lean first-paint sections ? avoid scanning every evidence JSONL on every select. */
export const PROPERTY_SECTIONS = [
  'thermo',
  'electronic_structure',
  'magnetism',
  'elasticity',
  'dielectric',
  'bonds',
  'surfaces',
  'spectra',
] as const;

export const SPECTRA_SECTIONS = ['spectra'] as const;

/** Keep evidence load small; full dumps were stacking with property loads and freezing the API. */
export const EVIDENCE_SECTIONS = [
  'thermo',
  'electronic_structure',
  'bonds',
  'spectra',
] as const;

export const ABOUT_TABS = [
  { id: 'thermodynamic', label: 'Thermo' },
  { id: 'electronic', label: 'Electronic' },
  { id: 'magnetic', label: 'Magnetic' },
  { id: 'mechanical', label: 'Mechanical' },
  { id: 'dielectric', label: 'Dielectric' },
  { id: 'surface', label: 'Surface' },
  { id: 'bonds', label: 'Bonds' },
  { id: 'spectra', label: 'Spectra' },
  { id: 'evidence', label: 'Evidence' },
] as const;

export const COMPARE_TABS = [
  { id: 'key', label: 'Key' },
  ...ABOUT_TABS,
] as const;
