# Context-aware genomic assistant

The Genes workspace is intentionally windowed. `GenomeSequenceRepository` owns complete cached FASTA records in `data/local/genomics/`, while `GET /genomics/state/{gene}` returns only the requested, inclusive gene-relative window.

## Live state contract

The frontend keeps one `GenomeState` in `layoutStore`:

```json
{
  "gene": "BRCA1",
  "visibleStart": 12755,
  "visibleEnd": 12786,
  "selectedPosition": 12770,
  "sequence": "...only the visible window...",
  "geneLength": 125954,
  "selectedVariant": {"hgvs": "c.68_69delAG", "reference": "AG", "alternate": "-"}
}
```

`buildAgentWorkspaceContext` forwards that same bounded state on every turn. The backend exposes it as `viewport.genome`; it does not put the complete FASTA record into an agent prompt.

## UI commands

The agent tool `control_genome_view` emits frontend-safe UI actions:

| Agent command | UI action | Result |
| --- | --- | --- |
| `highlight` + `position` | `genome_highlight` | Selects a displayed gene-relative nucleotide. |
| `zoom` + `start`, `end` | `genome_zoom` | Changes the bounded viewport; the UI then refreshes its sequence window. |
| `showSequence` | `genome_show_sequence` | Reveals the current window only. |

To add a gene, register its `GeneSpec` in `catalyst/genome_sequences.py`, add its case metadata, and allow it in `control_genome_view`. The state contract and renderer do not change.

All genomics content in this demo is educational and must not be treated as clinical interpretation.
