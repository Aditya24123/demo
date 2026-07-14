from __future__ import annotations

from typing import Any

from catalyst.local_store.helpers import _decode_row

class LocalStoreGraphNodesMixin:
    def graph_overview(self, limit_clusters: int = 250) -> dict[str, Any]:
        rows = self.query_df(
            """
            SELECT *
            FROM graph_overview_clusters
            ORDER BY material_count DESC, stable_count DESC
            LIMIT ?
            """,
            [limit_clusters],
        )
        clusters = [_decode_row(row) for row in rows.to_dict(orient="records")]
        nodes = []
        cluster_elements: dict[str, set[str]] = {}
        for row in clusters:
            elements = set(row.get("dominant_elements_json") or [])
            cluster_elements[row["cluster_id"]] = elements
            nodes.append(
                {
                    "id": row["cluster_id"],
                    "label": row["label"],
                    "type": "cluster",
                    "cluster_type": row["cluster_type"],
                    "material_count": row["material_count"],
                    "stable_count": row["stable_count"],
                    "avg_band_gap": row["avg_band_gap"],
                    "avg_energy_above_hull": row["avg_energy_above_hull"],
                    "representative_material_id": row["representative_material_id"],
                    "representative_formula": row["representative_formula"],
                    "dominant_elements": sorted(elements),
                }
            )
        edges = []
        for idx, left in enumerate(nodes):
            for right in nodes[idx + 1 :]:
                shared = cluster_elements[left["id"]].intersection(cluster_elements[right["id"]])
                if not shared:
                    continue
                weight = len(shared)
                if weight >= 1 and (left["material_count"] >= 10 or right["material_count"] >= 10):
                    edges.append(
                        {
                            "id": f"cluster:{left['id']}:{right['id']}",
                            "source": left["id"],
                            "target": right["id"],
                            "type": "SHARED_DOMINANT_ELEMENT",
                            "weight": weight,
                            "shared_elements": sorted(shared),
                        }
                    )
        return {
            "nodes": nodes,
            "edges": edges[: max(limit_clusters * 3, 100)],
            "meta": {"source_release": self.paths.source_release, "cluster_count": len(nodes)},
        }

    def graph_node(self, node_id: str) -> dict[str, Any] | None:
        material = self.get_material(node_id)
        if material:
            evidence = self.evidence(node_id)
            relation_rows = self.query_df(
                """
                SELECT COUNT(*) AS relation_count
                FROM material_material_edges
                WHERE source_id = ? OR target_id = ?
                """,
                [material["material_id"], material["material_id"]],
            )
            element_rows = self.query_df(
                """
                SELECT element_symbol, stoich_amount, atomic_fraction, normalized_fraction, oxidation_state
                FROM material_element_edges
                WHERE material_id = ?
                ORDER BY atomic_fraction DESC NULLS LAST, element_symbol ASC
                """,
                [material["material_id"]],
            )
            return {
                "id": material["material_id"],
                "node_id": node_id,
                "type": "material",
                "label": material.get("formula_pretty") or material["material_id"],
                "title": material.get("formula_pretty") or material["material_id"],
                "subtitle": material.get("chemsys"),
                "source_release": material.get("source_release") or self.paths.source_release,
                "summary": {
                    "material_id": material["material_id"],
                    "formula_pretty": material.get("formula_pretty"),
                    "chemsys": material.get("chemsys"),
                    "is_stable": material.get("is_stable"),
                    "is_metal": material.get("is_metal"),
                    "band_gap": material.get("band_gap"),
                    "energy_above_hull": material.get("energy_above_hull"),
                    "formation_energy_per_atom": material.get("formation_energy_per_atom"),
                    "density": material.get("density"),
                    "crystal_system": (material.get("symmetry") or {}).get("crystal_system")
                    if isinstance(material.get("symmetry"), dict)
                    else None,
                },
                "metrics": {
                    "relation_count": int(relation_rows.iloc[0]["relation_count"]) if not relation_rows.empty else 0,
                    "evidence_sections": evidence.get("total_sections", 0),
                    "evidence_records": evidence.get("total_records", 0),
                },
                "elements": [_decode_row(row) for row in element_rows.to_dict(orient="records")],
                "actions": [
                    {"id": "open_workspace", "label": "Open material workspace"},
                    {"id": "expand_neighborhood", "label": "Expand neighborhood"},
                    {"id": "add_candidate", "label": "Add to candidates"},
                    {"id": "export_subgraph", "label": "Export local subgraph"},
                ],
            }

        cluster = self._cluster_node(node_id)
        if cluster:
            return cluster

        element = self._element_node(node_id)
        if element:
            return element

        return None

    def _cluster_node(self, node_id: str) -> dict[str, Any] | None:
        rows = self.query_df(
            """
            SELECT *
            FROM graph_overview_clusters
            WHERE cluster_id = ?
            LIMIT 1
            """,
            [node_id],
        )
        if rows.empty:
            return None
        row = _decode_row(rows.iloc[0].to_dict())
        elements = row.get("dominant_elements_json") or []
        return {
            "id": row["cluster_id"],
            "node_id": node_id,
            "type": "cluster",
            "label": row.get("label") or row["cluster_id"],
            "title": row.get("label") or row["cluster_id"],
            "subtitle": row.get("cluster_type"),
            "source_release": self.paths.source_release,
            "summary": {
                "cluster_id": row["cluster_id"],
                "cluster_type": row.get("cluster_type"),
                "material_count": row.get("material_count"),
                "stable_count": row.get("stable_count"),
                "metal_count": row.get("metal_count"),
                "avg_band_gap": row.get("avg_band_gap"),
                "avg_energy_above_hull": row.get("avg_energy_above_hull"),
                "dominant_elements": elements,
                "representative_material_id": row.get("representative_material_id"),
                "representative_formula": row.get("representative_formula"),
            },
            "metrics": {
                "stability_ratio": (
                    float(row["stable_count"]) / float(row["material_count"])
                    if row.get("material_count")
                    else None
                ),
                "metal_ratio": (
                    float(row["metal_count"]) / float(row["material_count"])
                    if row.get("material_count")
                    else None
                ),
            },
            "actions": [
                {"id": "open_representative", "label": "Open representative material"},
                {"id": "filter_cluster", "label": "Filter graph to cluster"},
                {"id": "export_cluster", "label": "Export cluster subgraph"},
            ],
        }

    def _element_node(self, node_id: str) -> dict[str, Any] | None:
        rows = self.query_df(
            """
            SELECT *
            FROM elements
            WHERE symbol = ?
            LIMIT 1
            """,
            [node_id],
        )
        if rows.empty:
            return None
        row = _decode_row(rows.iloc[0].to_dict())
        stats = self.query_df(
            """
            SELECT
                COUNT(*) AS material_count,
                AVG(atomic_fraction) AS avg_atomic_fraction,
                MAX(atomic_fraction) AS max_atomic_fraction
            FROM material_element_edges
            WHERE element_symbol = ?
            """,
            [node_id],
        )
        examples = self.query_df(
            """
            SELECT e.material_id, m.formula_pretty, m.chemsys, e.atomic_fraction, m.is_stable, m.band_gap
            FROM material_element_edges e
            LEFT JOIN materials m ON e.material_id = m.material_id
            WHERE e.element_symbol = ?
            ORDER BY e.atomic_fraction DESC NULLS LAST
            LIMIT 12
            """,
            [node_id],
        )
        stat = _decode_row(stats.iloc[0].to_dict()) if not stats.empty else {}
        return {
            "id": row["symbol"],
            "node_id": node_id,
            "type": "element",
            "label": row.get("symbol"),
            "title": row.get("name") or row.get("symbol"),
            "subtitle": row.get("symbol"),
            "source_release": self.paths.source_release,
            "summary": {
                "symbol": row.get("symbol"),
                "name": row.get("name"),
                "atomic_number": row.get("atomic_number"),
                "atomic_mass": row.get("atomic_mass"),
                "group": row.get("group"),
                "period": row.get("period"),
                "block": row.get("block"),
                "electronegativity": row.get("electronegativity"),
                "electron_configuration": row.get("electron_configuration"),
                "common_oxidation_states": row.get("common_oxidation_states"),
            },
            "metrics": {
                "material_count": int(stat.get("material_count") or 0),
                "avg_atomic_fraction": stat.get("avg_atomic_fraction"),
                "max_atomic_fraction": stat.get("max_atomic_fraction"),
            },
            "examples": [_decode_row(example) for example in examples.to_dict(orient="records")],
            "actions": [
                {"id": "filter_element", "label": "Filter graph to element"},
                {"id": "search_materials", "label": "Search materials containing element"},
            ],
        }

