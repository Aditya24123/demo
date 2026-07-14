from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb
import pandas as pd
from pymatgen.core import Composition

from catalyst.build_processed import material_from_records
from catalyst.elements import build_element_nodes
from catalyst.graph_artifacts import build_graph_artifacts
from catalyst.resolver import build_material_id_resolver
from catalyst.util import read_jsonl, to_jsonable


EVIDENCE_FILES = {
    "structure": "material_structures.jsonl",
    "tasks": "material_tasks.jsonl",
    "thermo": "material_thermo.jsonl",
    "electronic_structure": "material_electronic_structure.jsonl",
    "magnetism": "material_magnetism.jsonl",
    "bonds": "material_bonds.jsonl",
    "auxiliary": "material_auxiliary_info.jsonl",
    "spectra": "material_spectra.jsonl",
    "elasticity": "material_elasticity.jsonl",
    "dielectric": "material_dielectric.jsonl",
    "piezoelectric": "material_piezoelectric.jsonl",
    "phonons": "material_phonons.jsonl",
    "surfaces": "material_surfaces.jsonl",
    "absorption": "material_absorption.jsonl",
    "eos": "material_eos.jsonl",
    "substrates": "material_substrates.jsonl",
}

TARGET_EVIDENCE_FILES = {
    "structure": "materials_core.jsonl",
    "summary": "materials_summary.jsonl",
    "thermo": "thermo.jsonl",
    "electronic_structure": "electronic_structure.jsonl",
    "magnetism": "magnetism.jsonl",
    "bonds": "bonds.jsonl",
    "chemenv": "chemenv.jsonl",
    "oxidation_states": "oxidation_states.jsonl",
    "doi": "doi.jsonl",
    "provenance": "provenance.jsonl",
    "substrates": "substrates.jsonl",
    "spectra": "xas.jsonl",
}


@dataclass(frozen=True)
class LocalPaths:
    repo_root: Path
    source_release: str

    @property
    def processed_root(self) -> Path:
        return self.repo_root / "data" / "processed" / "catalyst" / self.source_release

    @property
    def raw_root(self) -> Path:
        return self.repo_root / "data" / "raw" / "materials_project" / self.source_release

    @property
    def resolver_path(self) -> Path:
        return self.processed_root / "resolver" / "material_id_resolver.parquet"

    @property
    def graph_root(self) -> Path:
        return self.processed_root / "graph"

    @property
    def graph_manifest_path(self) -> Path:
        return self.graph_root / "graph_manifest.json"


def _decode_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _decode_value(value) for key, value in row.items()}


def _count_jsonl_matches(path: Path, material_id: str, key: str = "material_id") -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get(key)) == material_id:
                count += 1
    return count


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _read_jsonl_matches(
    path: Path,
    *,
    key: str,
    value: str,
    limit: int = 25,
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    truncated = False
    if not path.exists():
        return rows, truncated
    compact_needle = f'"{key}":"{value}"'
    spaced_needle = f'"{key}": "{value}"'
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            if compact_needle not in line and spaced_needle not in line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get(key)) != value:
                continue
            if len(rows) < limit:
                rows.append(row)
            else:
                truncated = True
                break
    return rows, truncated


def _downsample_sequence(values: Any, max_points: int = 320) -> Any:
    if not isinstance(values, list):
        return values
    if len(values) <= max_points:
        return values
    stride = max(1, len(values) // max_points)
    sampled = values[::stride]
    if sampled and sampled[-1] != values[-1]:
        sampled.append(values[-1])
    return sampled


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "nan", "none", "null"}:
        return True
    return False


def _first_present(*values: Any) -> Any:
    for value in values:
        if not _is_missing(value):
            return value
    return None


def _path_value(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _metric(label: str, value: Any, unit: str | None = None, source: str = "local") -> dict[str, Any]:
    return {
        "label": label,
        "value": to_jsonable(value) if not _is_missing(value) else None,
        "unit": unit,
        "source": source,
        "available": not _is_missing(value),
    }


def _section_first(details: dict[str, Any], section: str) -> dict[str, Any]:
    records = details.get(section, {}).get("records") or []
    first = records[0] if records else {}
    return first if isinstance(first, dict) else {}


