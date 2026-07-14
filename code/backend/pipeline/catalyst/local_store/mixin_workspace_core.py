from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from catalyst.local_store.helpers import (
    EVIDENCE_FILES,
    TARGET_EVIDENCE_FILES,
    _decode_row,
    _downsample_sequence,
    _first_present,
    _metric,
    _path_value,
    _read_jsonl_matches,
    _section_first,
)
from catalyst.util import read_jsonl, to_jsonable

class LocalStoreWorkspaceCoreMixin:
    def workspace(self, material_id: str) -> dict[str, Any] | None:
        material = self.get_material(material_id)
        if not material:
            return None
        mid = str(material["material_id"])
        index_rows = self.query_df("SELECT * FROM material_workspace_index WHERE material_id = ? LIMIT 1", [mid])
        workspace_index = _decode_row(index_rows.iloc[0].to_dict()) if not index_rows.empty else {}
        evidence = self.evidence(material_id)
        graph = self.neighborhood(material_id)
        relation_count = sum(1 for edge in graph["edges"] if edge.get("recipe_name"))
        return {
            "material_id": material_id,
            "resolved_material_id": mid,
            "material": material,
            "workspace_index": workspace_index,
            "summary": {
                "formula_pretty": material.get("formula_pretty"),
                "chemsys": material.get("chemsys"),
                "is_stable": material.get("is_stable"),
                "energy_above_hull": material.get("energy_above_hull"),
                "formation_energy_per_atom": material.get("formation_energy_per_atom"),
                "band_gap": material.get("band_gap"),
                "is_metal": material.get("is_metal"),
                "is_magnetic": material.get("is_magnetic"),
                "ordering": material.get("ordering"),
                "source_release": material.get("source_release"),
            },
            "structure": {
                "symmetry": material.get("symmetry"),
                "lattice": material.get("lattice_conventional") or material.get("lattice"),
                "atomic_position_summary": material.get("atomic_position_summary") or [],
                "nsites": material.get("nsites"),
                "density": material.get("density"),
                "volume": material.get("volume"),
            },
            "properties": {
                "thermo": {
                    "energy_above_hull": material.get("energy_above_hull"),
                    "formation_energy_per_atom": material.get("formation_energy_per_atom"),
                    "is_stable": material.get("is_stable"),
                    "decomposes_to": material.get("decomposes_to") or [],
                },
                "electronic": {
                    "band_gap": material.get("band_gap"),
                    "is_gap_direct": material.get("is_gap_direct"),
                    "is_metal": material.get("is_metal"),
                    "cbm": material.get("cbm"),
                    "vbm": material.get("vbm"),
                    "efermi": material.get("efermi"),
                },
                "magnetism": {
                    "is_magnetic": material.get("is_magnetic"),
                    "ordering": material.get("ordering"),
                    "total_magnetization_normalized_formula_units": material.get(
                        "total_magnetization_normalized_formula_units"
                    ),
                },
                "mechanical": {
                    "bulk_modulus_vrh": material.get("bulk_modulus_vrh"),
                    "shear_modulus_vrh": material.get("shear_modulus_vrh"),
                    "universal_anisotropy": material.get("universal_anisotropy"),
                    "homogeneous_poisson": material.get("homogeneous_poisson"),
                },
            },
            "evidence": evidence,
            "graph": graph,
            "relation_count": relation_count,
            "actions": [
                {"id": "expand_neighborhood", "label": "Expand graph neighborhood"},
                {"id": "inspect_edges", "label": "Inspect relation recipes"},
                {"id": "export_subgraph", "label": "Export subgraph JSON"},
            ],
        }

    def structure(self, material_id: str) -> dict[str, Any] | None:
        material = self.get_material(material_id)
        if not material:
            return None

        mid = str(material["material_id"])
        processed_path = self.paths.processed_root / EVIDENCE_FILES["structure"]
        structure_rows, _ = _read_jsonl_matches(processed_path, key="material_id", value=mid, limit=1)
        structure_row = structure_rows[0] if structure_rows else {}
        raw_structure = structure_row.get("structure")

        if not raw_structure:
            target_dir = self._target_dir(mid)
            target_core = target_dir / TARGET_EVIDENCE_FILES["structure"]
            if target_core.exists():
                target_rows = read_jsonl(target_core)
                if target_rows:
                    raw_structure = target_rows[0].get("structure") or target_rows[0]

        lattice = {}
        sites: list[dict[str, Any]] = []
        symmetry = structure_row.get("symmetry") or material.get("symmetry")
        if isinstance(raw_structure, dict):
            lattice = to_jsonable(raw_structure.get("lattice") or {})
            raw_sites = raw_structure.get("sites") or []
            if isinstance(raw_sites, list):
                for idx, site in enumerate(raw_sites):
                    if not isinstance(site, dict):
                        continue
                    species = site.get("species") or []
                    element = None
                    if species and isinstance(species, list):
                        first = species[0]
                        if isinstance(first, dict):
                            element = first.get("element")
                    sites.append(
                        {
                            "index": idx,
                            "label": site.get("label") or element or f"site_{idx}",
                            "element": element or site.get("label"),
                            "abc": to_jsonable(site.get("abc") or []),
                            "xyz": to_jsonable(site.get("xyz") or []),
                            "species": to_jsonable(species),
                        }
                    )

        if not lattice:
            lattice = to_jsonable(material.get("lattice_conventional") or material.get("lattice") or {})

        has_full_structure = bool(sites and lattice)
        return {
            "material_id": material_id,
            "resolved_material_id": mid,
            "source_release": material.get("source_release") or self.paths.source_release,
            "formula_pretty": material.get("formula_pretty"),
            "chemsys": material.get("chemsys"),
            "symmetry": to_jsonable(symmetry),
            "lattice": lattice,
            "sites": sites,
            "nsites": material.get("nsites") or len(sites),
            "density": material.get("density"),
            "volume": material.get("volume"),
            "structure": to_jsonable(raw_structure) if isinstance(raw_structure, dict) else None,
            "has_full_structure": has_full_structure,
            "message": None if has_full_structure else "Full 3D structure record unavailable in local snapshot",
        }

