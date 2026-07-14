"""Small, deterministic genomics showcase pack for the Catalyst Genes rail.

This is intentionally a demo dataset, not a clinical interpretation service. The
sequence windows are short visual cutouts that make the 3D workspace inspectable
without downloading or claiming to render an entire gene.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_CASES: dict[str, dict[str, Any]] = {
    "brca1": {
        "case_id": "brca1",
        "title": "BRCA1 marker",
        "gene": "BRCA1",
        "subtitle": "DNA repair-associated gene",
        "kind": "variant",
        "variant_id": "rs80357906",
        "sequence_window": "AAAGCGTGGGAATTACAGATAAATTAAAACTG",
        "highlighted_index": 7,
        "summary": "A representative BRCA1 sequence window with one highlighted variant marker.",
        "interpretation": "This showcase visualises a short sequence cutout only; use the linked source for record-level evidence.",
        "source_label": "Ensembl sequence reference + curated demo marker",
        "source_url": "https://rest.ensembl.org/sequence/id/ENSG00000012048?content-type=text/x-fasta",
    },
    "hbb": {
        "case_id": "hbb",
        "title": "HBB marker",
        "gene": "HBB",
        "subtitle": "Hemoglobin beta gene",
        "kind": "variant",
        "variant_id": "rs334",
        "sequence_window": "ACATTTGCTTCTGACACAACTGTGTTCACTAGC",
        "highlighted_index": 7,
        "summary": "A representative HBB sequence window with a highlighted coding marker.",
        "interpretation": "This is a grounded demo reference, not a diagnostic result or a complete clinical interpretation.",
        "source_label": "MyVariant reference + curated demo marker",
        "source_url": "https://myvariant.info/v1/query?q=rs334",
    },
    "ctg": {
        "case_id": "ctg",
        "title": "CTG expansion",
        "gene": "DMPK",
        "subtitle": "Myotonic dystrophy repeat model",
        "kind": "repeat_expansion",
        "sequence_window": "CTGCTGCTGCTGCTGCTGCTGCTGCTGCTGCTG",
        "highlighted_index": 8,
        "summary": "A repeat-expansion model. The slider controls the demonstration repeat count.",
        "interpretation": "This educational demo classifies the supplied repeat-count bands and does not make an individual health assessment.",
        "source_label": "Curated educational demo model",
        "default_repeat_count": 55,
    },
}


def list_cases() -> list[dict[str, Any]]:
    return [deepcopy(_CASES[key]) for key in ("brca1", "hbb", "ctg")]


def repeat_interpretation(repeat_count: int) -> dict[str, Any]:
    count = max(0, min(100, int(repeat_count)))
    if count <= 37:
        return {"repeat_count": count, "band": "normal", "label": "Normal range", "range": "Up to 37 repeats", "color": "#34d399"}
    if count <= 49:
        return {"repeat_count": count, "band": "pre_mutation", "label": "Pre-mutation range", "range": "38-49 repeats", "color": "#fbbf24"}
    return {"repeat_count": count, "band": "disease_range", "label": "Disease range", "range": "50+ repeats", "color": "#fb7185"}


def get_case(case_id: str, *, repeat_count: int | None = None) -> dict[str, Any] | None:
    record = _CASES.get(str(case_id).strip().lower())
    if not record:
        return None
    payload = deepcopy(record)
    if payload["case_id"] == "ctg":
        payload["repeat"] = repeat_interpretation(repeat_count if repeat_count is not None else payload["default_repeat_count"])
    return payload


def tool_result(case_id: str, *, repeat_count: int | None = None) -> dict[str, Any]:
    payload = get_case(case_id, repeat_count=repeat_count)
    if not payload:
        return {"ok": False, "error": "Unknown genomics demo case. Use brca1, hbb, or ctg."}
    return {"ok": True, "case": payload, "scope": "educational demo; not diagnostic or clinical advice"}
