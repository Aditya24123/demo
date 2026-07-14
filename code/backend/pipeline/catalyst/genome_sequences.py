"""Local, windowed genome-sequence access for the Catalyst Genes workspace.

The repository caches complete FASTA records under ``data/local/genomics`` but
never returns a full record to the UI or agent. Consumers receive a small,
1-based inclusive window and explicit coordinate metadata instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class GeneSpec:
    symbol: str
    ensembl_id: str
    selected_position: int
    selected_variant: dict[str, str]


GENES: dict[str, GeneSpec] = {
    "BRCA1": GeneSpec(
        symbol="BRCA1",
        ensembl_id="ENSG00000012048",
        # Gene-relative, 1-based display position used by the existing demo.
        selected_position=12_770,
        selected_variant={"hgvs": "c.68_69delAG", "reference": "AG", "alternate": "-", "id": "rs80357906"},
    ),
}


class GenomeSequenceRepository:
    """Load complete gene records locally, fetching once only when cache is absent."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self._memory: dict[str, str] = {}

    def _cache_path(self, spec: GeneSpec) -> Path:
        return self.repo_root / "data" / "local" / "genomics" / f"{spec.symbol.lower()}.fasta"

    @staticmethod
    def _parse_fasta(text: str) -> str:
        return "".join(line.strip().upper() for line in text.splitlines() if line and not line.startswith(">"))

    def sequence(self, gene: str) -> str:
        symbol = str(gene).strip().upper()
        if symbol not in GENES:
            raise KeyError(f"Unsupported gene: {gene}")
        if symbol in self._memory:
            return self._memory[symbol]
        spec = GENES[symbol]
        cache = self._cache_path(spec)
        if cache.is_file():
            sequence = self._parse_fasta(cache.read_text(encoding="utf-8"))
        else:
            url = f"https://rest.ensembl.org/sequence/id/{spec.ensembl_id}?content-type=text/x-fasta"
            request = Request(url, headers={"Accept": "text/x-fasta", "User-Agent": "Catalyst/0.1 genomics-demo"})
            with urlopen(request, timeout=12) as response:  # noqa: S310 - fixed Ensembl source, no user URL
                raw = response.read().decode("utf-8")
            sequence = self._parse_fasta(raw)
            if not sequence:
                raise RuntimeError(f"Ensembl returned no sequence for {symbol}")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(raw if raw.endswith("\n") else raw + "\n", encoding="utf-8")
        if not sequence:
            raise RuntimeError(f"Cached sequence is empty for {symbol}")
        self._memory[symbol] = sequence
        return sequence

    def state(
        self,
        gene: str,
        *,
        visible_start: int | None = None,
        visible_end: int | None = None,
        selected_position: int | None = None,
    ) -> dict[str, Any]:
        symbol = str(gene).strip().upper()
        spec = GENES.get(symbol)
        if not spec:
            raise KeyError(f"Unsupported gene: {gene}")
        sequence = self.sequence(symbol)
        total = len(sequence)
        selected = max(1, min(total, int(selected_position or spec.selected_position)))
        start = max(1, min(total, int(visible_start or max(1, selected - 15))))
        end = max(start, min(total, int(visible_end or min(total, start + 31))))
        return {
            "gene": symbol,
            "coordinate_system": "gene_relative_1_based_inclusive",
            "visibleStart": start,
            "visibleEnd": end,
            "selectedPosition": selected,
            "sequence": sequence[start - 1 : end],
            "geneLength": total,
            "selectedVariant": {**spec.selected_variant, "position": selected},
            "source": {"provider": "Ensembl", "ensembl_id": spec.ensembl_id, "cached": self._cache_path(spec).is_file()},
        }
