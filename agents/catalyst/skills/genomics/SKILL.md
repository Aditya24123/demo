# Genomics workspace skill

Use this skill only when the live RunContext surface is `genes`. The `viewport.genome` object is authoritative for the current gene, visible gene-relative interval, selected nucleotide, selected variant, and visible sequence window.

Rules:

- Treat `visible_sequence` as the only sequence available in chat. It is intentionally bounded; do not imply that it is the full gene.
- Use `inspect_genomics_case` for the curated BRCA1, HBB, and CTG showcase facts.
- Use `control_genome_view` for UI commands: `highlight`, `zoom`, or `showSequence`.
- Prefer the currently selected coordinate and variant from RunContext over older chat messages.
- Keep the demo educational. Do not make diagnostic, pathogenicity, or treatment claims.
