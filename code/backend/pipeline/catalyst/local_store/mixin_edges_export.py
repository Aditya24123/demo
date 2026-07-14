from __future__ import annotations

from typing import Any
from uuid import uuid4

from pymatgen.core import Composition

from catalyst.local_store.helpers import _decode_row
from catalyst.util import to_jsonable

class LocalStoreEdgesExportMixin:
    def edge(self, edge_id: str) -> dict[str, Any] | None:
        rows = self.query_df("SELECT * FROM material_material_edges WHERE edge_id = ? LIMIT 1", [edge_id])
        if rows.empty:
            if edge_id.startswith("element:"):
                return self._element_edge(edge_id)
            if edge_id.startswith("cluster:"):
                return self._cluster_edge(edge_id)
            return None
        row = _decode_row(rows.iloc[0].to_dict())
        return row

    def _element_edge(self, edge_id: str) -> dict[str, Any] | None:
        parts = edge_id.split(":", 2)
        if len(parts) != 3:
            return None
        _, material_id, element_symbol = parts
        rows = self.query_df(
            """
            SELECT *
            FROM material_element_edges
            WHERE material_id = ? AND element_symbol = ?
            LIMIT 1
            """,
            [material_id, element_symbol],
        )
        material = self.get_material(material_id)
        if rows.empty and not material:
            return None
        row = _decode_row(rows.iloc[0].to_dict()) if not rows.empty else {}
        formula = material.get("formula_pretty") if material else material_id
        fraction = row.get("atomic_fraction")
        return {
            "edge_id": edge_id,
            "id": edge_id,
            "source": material_id,
            "target": element_symbol,
            "source_id": material_id,
            "target_id": element_symbol,
            "type": row.get("edge_type", "CONTAINS_ELEMENT"),
            "edge_type": row.get("edge_type", "CONTAINS_ELEMENT"),
            "weight": fraction,
            "confidence": 1.0,
            "recipe": "material_element_membership",
            "recipe_name": "material_element_membership",
            "reason_summary": f"{formula} contains {element_symbol}"
            + (f" with atomic fraction {float(fraction):.3g}." if fraction is not None else "."),
            "feature_delta": {
                "stoich_amount": row.get("stoich_amount"),
                "stoich_amount_reduced": row.get("stoich_amount_reduced"),
                "atomic_fraction": row.get("atomic_fraction"),
                "normalized_fraction": row.get("normalized_fraction"),
                "element_count": row.get("element_count"),
            },
            "source_release": row.get("source_release") or self.paths.source_release,
        }

    def _cluster_edge(self, edge_id: str) -> dict[str, Any] | None:
        rows = self.query_df("SELECT * FROM graph_overview_clusters")
        clusters = [_decode_row(row) for row in rows.to_dict(orient="records")]
        for left in clusters:
            for right in clusters:
                left_id = str(left["cluster_id"])
                right_id = str(right["cluster_id"])
                if edge_id != f"cluster:{left_id}:{right_id}":
                    continue
                left_elements = set(left.get("dominant_elements_json") or [])
                right_elements = set(right.get("dominant_elements_json") or [])
                shared = sorted(left_elements.intersection(right_elements))
                if not shared:
                    return None
                return {
                    "edge_id": edge_id,
                    "id": edge_id,
                    "source": left_id,
                    "target": right_id,
                    "source_id": left_id,
                    "target_id": right_id,
                    "type": "SHARED_DOMINANT_ELEMENT",
                    "edge_type": "SHARED_DOMINANT_ELEMENT",
                    "weight": len(shared),
                    "confidence": 1.0,
                    "recipe": "overview_cluster_shared_elements",
                    "recipe_name": "overview_cluster_shared_elements",
                    "reason_summary": (
                        f"{left.get('label') or left_id} and {right.get('label') or right_id} "
                        f"share dominant element signals: {', '.join(shared)}."
                    ),
                    "feature_delta": {
                        "shared_elements": shared,
                        "source_material_count": left.get("material_count"),
                        "target_material_count": right.get("material_count"),
                        "source_stable_count": left.get("stable_count"),
                        "target_stable_count": right.get("stable_count"),
                    },
                    "source_release": self.paths.source_release,
                }
        return None

    def export_subgraph(
        self,
        material_ids: list[str],
        include_evidence: bool = True,
        include_edge_details: bool = False,
    ) -> dict[str, Any]:
        return self.export_subgraph_detailed(
            material_ids,
            include_evidence=include_evidence,
            include_edge_details=include_edge_details,
        )

    def export_subgraph_detailed(
        self,
        material_ids: list[str],
        *,
        include_evidence: bool = True,
        include_edge_details: bool = True,
    ) -> dict[str, Any]:
        nodes_by_id: dict[str, dict[str, Any]] = {}
        edges_by_id: dict[str, dict[str, Any]] = {}
        evidence: dict[str, Any] = {}
        edge_details: dict[str, Any] = {}
        for material_id in material_ids:
            graph = self.neighborhood(material_id)
            for node in graph["nodes"]:
                nodes_by_id[node["id"]] = node
            for edge in graph["edges"]:
                edge_id = edge.get("id") or f"{edge.get('source')}:{edge.get('target')}:{edge.get('type')}"
                edges_by_id[edge_id] = edge
                if include_edge_details and edge.get("id"):
                    detail = self.edge(str(edge["id"]))
                    if detail:
                        edge_details[str(edge["id"])] = detail
            if include_evidence:
                evidence[material_id] = self.evidence(material_id)
        return {
            "export_id": f"exp_{uuid4().hex[:16]}",
            "source_release": self.paths.source_release,
            "requested_material_ids": material_ids,
            "nodes": list(nodes_by_id.values()),
            "edges": list(edges_by_id.values()),
            "evidence": evidence if include_evidence else {},
            "edge_details": edge_details if include_edge_details else {},
        }

    def compare_materials(
        self,
        material_ids: list[str],
        *,
        include_evidence: bool = True,
        include_edges: bool = True,
    ) -> dict[str, Any]:
        rows = []
        evidence_payload: dict[str, Any] = {}
        relation_summaries = []
        for material_id in material_ids:
            material = self.get_material(material_id)
            if not material:
                continue
            workspace = self.workspace(material_id) or {}
            row = {
                "material_id": workspace.get("resolved_material_id") or material.get("material_id"),
                "formula_pretty": material.get("formula_pretty"),
                "chemsys": material.get("chemsys"),
                "is_stable": material.get("is_stable"),
                "energy_above_hull": material.get("energy_above_hull"),
                "energy_per_atom": material.get("energy_per_atom"),
                "uncorrected_energy_per_atom": material.get("uncorrected_energy_per_atom"),
                "formation_energy_per_atom": material.get("formation_energy_per_atom"),
                "equilibrium_reaction_energy_per_atom": material.get("equilibrium_reaction_energy_per_atom"),
                "decomposes_to": material.get("decomposes_to"),
                "band_gap": material.get("band_gap"),
                "is_gap_direct": material.get("is_gap_direct"),
                "cbm": material.get("cbm"),
                "vbm": material.get("vbm"),
                "efermi": material.get("efermi"),
                "density": material.get("density"),
                "volume": material.get("volume"),
                "nsites": material.get("nsites"),
                "symmetry": material.get("symmetry"),
                "is_metal": material.get("is_metal"),
                "is_magnetic": material.get("is_magnetic"),
                "ordering": material.get("ordering"),
                "total_magnetization": material.get("total_magnetization"),
                "total_magnetization_normalized_vol": material.get("total_magnetization_normalized_vol"),
                "total_magnetization_normalized_formula_units": material.get(
                    "total_magnetization_normalized_formula_units"
                ),
                "num_magnetic_sites": material.get("num_magnetic_sites"),
                "num_unique_magnetic_sites": material.get("num_unique_magnetic_sites"),
                "types_of_magnetic_species": material.get("types_of_magnetic_species"),
                "bulk_modulus_vrh": material.get("bulk_modulus_vrh"),
                "shear_modulus_vrh": material.get("shear_modulus_vrh"),
                "universal_anisotropy": material.get("universal_anisotropy"),
                "homogeneous_poisson": material.get("homogeneous_poisson"),
                "e_total": material.get("e_total"),
                "e_ionic": material.get("e_ionic"),
                "e_electronic": material.get("e_electronic"),
                "n_refractive": material.get("n_refractive"),
                "e_ij_max": material.get("e_ij_max"),
                "weighted_surface_energy": material.get("weighted_surface_energy"),
                "weighted_surface_energy_ev_per_ang2": material.get("weighted_surface_energy_ev_per_ang2"),
                "weighted_work_function": material.get("weighted_work_function"),
                "surface_anisotropy": material.get("surface_anisotropy"),
                "shape_factor": material.get("shape_factor"),
                "has_reconstructed": material.get("has_reconstructed"),
                "evidence_sections": len((workspace.get("evidence") or {}).get("sections", [])),
                "relation_count": workspace.get("relation_count", 0),
                "source_release": material.get("source_release"),
            }
            detail_payload = self.material_details(
                str(row["material_id"]),
                sections=[
                    "thermo",
                    "electronic_structure",
                    "magnetism",
                    "elasticity",
                    "dielectric",
                    "piezoelectric",
                    "phonons",
                    "eos",
                    "surfaces",
                    "bonds",
                    "spectra",
                    "absorption",
                    "tasks",
                    "auxiliary",
                ],
                limit=3,
                downsample=True,
            )
            if detail_payload:
                row["detail_availability"] = {
                    key: value.get("count", 0) for key, value in detail_payload.get("details", {}).items()
                }
                row["property_groups"] = detail_payload.get("property_groups", [])
            rows.append(to_jsonable(row))
            if include_evidence:
                evidence_payload[str(row["material_id"])] = workspace.get("evidence") or self.evidence(material_id)
            if include_edges:
                graph = workspace.get("graph") or self.neighborhood(material_id)
                relation_summaries.extend(
                    {
                        "material_id": row["material_id"],
                        "edge_id": edge.get("id"),
                        "source": edge.get("source"),
                        "target": edge.get("target"),
                        "type": edge.get("type"),
                        "weight": edge.get("weight"),
                        "recipe_name": edge.get("recipe_name"),
                        "reason_summary": edge.get("reason_summary"),
                    }
                    for edge in graph.get("edges", [])
                    if edge.get("recipe_name")
                )
        return {
            "materials": rows,
            "columns": [
                {"key": "formula_pretty", "label": "Formula"},
                {"key": "chemsys", "label": "Chemical system"},
                {"key": "is_stable", "label": "Stable"},
                {"key": "energy_above_hull", "label": "Energy above hull"},
                {"key": "formation_energy_per_atom", "label": "Formation energy"},
                {"key": "equilibrium_reaction_energy_per_atom", "label": "Equilibrium rxn energy"},
                {"key": "band_gap", "label": "Band gap"},
                {"key": "is_gap_direct", "label": "Direct gap"},
                {"key": "is_metal", "label": "Metal"},
                {"key": "cbm", "label": "CBM"},
                {"key": "vbm", "label": "VBM"},
                {"key": "efermi", "label": "Fermi energy"},
                {"key": "density", "label": "Density"},
                {"key": "ordering", "label": "Magnetic ordering"},
                {"key": "is_magnetic", "label": "Magnetic"},
                {"key": "total_magnetization", "label": "Total magnetization"},
                {"key": "bulk_modulus_vrh", "label": "Bulk modulus VRH"},
                {"key": "shear_modulus_vrh", "label": "Shear modulus VRH"},
                {"key": "universal_anisotropy", "label": "Universal anisotropy"},
                {"key": "homogeneous_poisson", "label": "Poisson ratio"},
                {"key": "e_total", "label": "Total dielectric"},
                {"key": "n_refractive", "label": "Refractive index"},
                {"key": "weighted_surface_energy", "label": "Surface energy"},
                {"key": "weighted_work_function", "label": "Work function"},
                {"key": "evidence_sections", "label": "Evidence sections"},
                {"key": "relation_count", "label": "Relations"},
            ],
            "groups": [
                {"key": "key", "label": "Key properties"},
                {"key": "thermodynamic", "label": "Thermodynamic"},
                {"key": "electronic", "label": "Electronic"},
                {"key": "magnetic", "label": "Magnetic"},
                {"key": "mechanical", "label": "Mechanical"},
                {"key": "dielectric", "label": "Dielectric / optical"},
                {"key": "surface", "label": "Surface / interfaces"},
                {"key": "bonds", "label": "Bonds / coordination"},
                {"key": "spectra", "label": "Spectra / evidence"},
            ],
            "evidence": evidence_payload,
            "relation_summaries": relation_summaries[:100],
        }

    def _derive_target_edges(self, material: dict[str, Any]) -> list[dict[str, Any]]:
        composition = material.get("composition") or material.get("composition_reduced")
        if not composition and material.get("formula_pretty"):
            composition = material["formula_pretty"]
        if not composition:
            return []
        comp = Composition(composition)
        reduced = comp.reduced_composition
        total = float(comp.num_atoms)
        edges = []
        for element, amount in comp.items():
            reduced_amount = float(reduced[element]) if element in reduced else float(amount)
            edges.append(
                {
                    "material_id": material["material_id"],
                    "element_symbol": element.symbol,
                    "edge_type": "CONTAINS_ELEMENT",
                    "stoich_amount": float(amount),
                    "stoich_amount_reduced": reduced_amount,
                    "atomic_fraction": float(amount) / total if total else 0.0,
                    "normalized_fraction": float(comp.get_atomic_fraction(element)),
                    "source_release": self.paths.source_release,
                }
            )
        return edges
