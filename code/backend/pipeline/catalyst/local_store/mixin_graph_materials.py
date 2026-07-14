from __future__ import annotations

from typing import Any

from catalyst.local_store.helpers import _decode_row

class LocalStoreGraphMaterialsMixin:
    def graph_materials(
        self,
        limit_materials: int = 10_000,
        *,
        include_elements: bool = True,
        include_clusters: bool = True,
    ) -> dict[str, Any]:
        """Return the material-first graph used by the interactive workspace.

        The overview graph is intentionally cluster-first. This endpoint is the
        inverse contract: every selected material is a direct node so the UI can
        keep clusters optional without losing access to the material catalog.
        """
        limit_materials = max(1, min(int(limit_materials), 10_000))
        material_rows = self.query_df(
            """
            SELECT
                m.material_id,
                m.formula_pretty,
                m.chemsys,
                m.elements,
                m.nelements,
                m.energy_above_hull,
                m.formation_energy_per_atom,
                m.band_gap,
                m.is_metal,
                m.is_stable,
                m.is_magnetic,
                m.ordering,
                m.density,
                m.volume,
                m.nsites,
                m.symmetry,
                m.source_release,
                m.theoretical,
                COALESCE(w.relation_count, 0) AS relation_count,
                COALESCE(w.evidence_records, 0) AS evidence_records,
                COALESCE(w.curated_score, 0) AS curated_score
            FROM materials m
            LEFT JOIN material_workspace_index w ON m.material_id = w.material_id
            ORDER BY
                COALESCE(w.curated_score, 0) DESC,
                COALESCE(w.relation_count, 0) DESC,
                COALESCE(w.evidence_records, 0) DESC,
                m.is_stable DESC,
                m.energy_above_hull ASC NULLS LAST,
                m.material_id ASC
            LIMIT ?
            """,
            [limit_materials],
        )
        materials = [_decode_row(row) for row in material_rows.to_dict(orient="records")]
        material_ids = {str(row["material_id"]) for row in materials}

        nodes: list[dict[str, Any]] = [
            {
                "id": row["material_id"],
                "label": row.get("formula_pretty") or row["material_id"],
                "type": "material",
                "material_id": row["material_id"],
                "formula_pretty": row.get("formula_pretty"),
                "chemsys": row.get("chemsys"),
                "cluster_id": f"chemsys:{row['chemsys']}" if row.get("chemsys") else None,
                "elements": row.get("elements") or [],
                "nelements": row.get("nelements"),
                "energy_above_hull": row.get("energy_above_hull"),
                "formation_energy_per_atom": row.get("formation_energy_per_atom"),
                "band_gap": row.get("band_gap"),
                "is_metal": row.get("is_metal"),
                "is_stable": row.get("is_stable"),
                "is_magnetic": row.get("is_magnetic"),
                "ordering": row.get("ordering"),
                "density": row.get("density"),
                "volume": row.get("volume"),
                "nsites": row.get("nsites"),
                "symmetry": row.get("symmetry"),
                "source_release": row.get("source_release") or self.paths.source_release,
                "namespace": "materials_project_snapshot",
                "theoretical": row.get("theoretical"),
                "relation_count": row.get("relation_count"),
                "evidence_records": row.get("evidence_records"),
                "curated_score": row.get("curated_score"),
            }
            for row in materials
        ]

        edges: list[dict[str, Any]] = []
        material_edge_rows = self.query_df(
            """
            WITH selected AS (
                SELECT m.material_id
                FROM materials m
                LEFT JOIN material_workspace_index w ON m.material_id = w.material_id
                ORDER BY
                    COALESCE(w.curated_score, 0) DESC,
                    COALESCE(w.relation_count, 0) DESC,
                    COALESCE(w.evidence_records, 0) DESC,
                    m.is_stable DESC,
                    m.energy_above_hull ASC NULLS LAST,
                    m.material_id ASC
                LIMIT ?
            )
            SELECT
                e.edge_id,
                e.source_id,
                e.target_id,
                e.edge_type,
                e.weight,
                e.confidence,
                e.recipe_name,
                e.reason_summary
            FROM material_material_edges e
            JOIN selected s1 ON e.source_id = s1.material_id
            JOIN selected s2 ON e.target_id = s2.material_id
            ORDER BY e.weight DESC, e.confidence DESC NULLS LAST
            """,
            [limit_materials],
        )
        for edge in material_edge_rows.to_dict(orient="records"):
            edge = _decode_row(edge)
            edges.append(
                {
                    "id": edge["edge_id"],
                    "source": edge["source_id"],
                    "target": edge["target_id"],
                    "type": edge["edge_type"],
                    "weight": edge.get("weight"),
                    "confidence": edge.get("confidence"),
                    "recipe_name": edge.get("recipe_name"),
                    "reason_summary": edge.get("reason_summary"),
                }
            )

        element_count = 0
        if include_elements and material_ids:
            element_rows = self.query_df(
                """
                WITH selected AS (
                    SELECT m.material_id
                    FROM materials m
                    LEFT JOIN material_workspace_index w ON m.material_id = w.material_id
                    ORDER BY
                        COALESCE(w.curated_score, 0) DESC,
                        COALESCE(w.relation_count, 0) DESC,
                        COALESCE(w.evidence_records, 0) DESC,
                        m.is_stable DESC,
                        m.energy_above_hull ASC NULLS LAST,
                        m.material_id ASC
                    LIMIT ?
                )
                SELECT DISTINCT el.*
                FROM material_element_edges e
                JOIN selected s ON e.material_id = s.material_id
                LEFT JOIN elements el ON e.element_symbol = el.symbol
                ORDER BY el.atomic_number ASC NULLS LAST, el.symbol ASC
                """,
                [limit_materials],
            )
            element_nodes = []
            for row in element_rows.to_dict(orient="records"):
                element = _decode_row(row)
                symbol = element.get("symbol")
                if not symbol:
                    continue
                element_nodes.append({"id": symbol, "label": symbol, "type": "element", **element})
            element_count = len(element_nodes)
            nodes.extend(element_nodes)

            element_edge_rows = self.query_df(
                """
                WITH selected AS (
                    SELECT m.material_id
                    FROM materials m
                    LEFT JOIN material_workspace_index w ON m.material_id = w.material_id
                    ORDER BY
                        COALESCE(w.curated_score, 0) DESC,
                        COALESCE(w.relation_count, 0) DESC,
                        COALESCE(w.evidence_records, 0) DESC,
                        m.is_stable DESC,
                        m.energy_above_hull ASC NULLS LAST,
                        m.material_id ASC
                    LIMIT ?
                )
                SELECT
                    e.material_id,
                    e.element_symbol,
                    e.edge_type,
                    e.stoich_amount,
                    e.atomic_fraction,
                    e.normalized_fraction,
                    e.oxidation_state
                FROM material_element_edges e
                JOIN selected s ON e.material_id = s.material_id
                ORDER BY e.material_id ASC, e.atomic_fraction DESC NULLS LAST
                """,
                [limit_materials],
            )
            for edge in element_edge_rows.to_dict(orient="records"):
                edge = _decode_row(edge)
                edges.append(
                    {
                        "id": f"element:{edge['material_id']}:{edge['element_symbol']}",
                        "source": edge["material_id"],
                        "target": edge["element_symbol"],
                        "type": edge.get("edge_type", "CONTAINS_ELEMENT"),
                        "weight": edge.get("atomic_fraction"),
                        "stoich_amount": edge.get("stoich_amount"),
                        "atomic_fraction": edge.get("atomic_fraction"),
                        "normalized_fraction": edge.get("normalized_fraction"),
                        "oxidation_state": edge.get("oxidation_state"),
                    }
                )

        cluster_count = 0
        if include_clusters:
            cluster_rows = self.query_df(
                """
                SELECT *
                FROM graph_overview_clusters
                ORDER BY material_count DESC, stable_count DESC
                """
            )
            clusters = [_decode_row(row) for row in cluster_rows.to_dict(orient="records")]
            cluster_count = len(clusters)
            cluster_ids = {row["cluster_id"] for row in clusters}
            for row in clusters:
                elements = row.get("dominant_elements_json") or []
                nodes.append(
                    {
                        "id": row["cluster_id"],
                        "label": row.get("label") or row["cluster_id"],
                        "type": "cluster",
                        "cluster_type": row.get("cluster_type"),
                        "material_count": row.get("material_count"),
                        "stable_count": row.get("stable_count"),
                        "metal_count": row.get("metal_count"),
                        "avg_band_gap": row.get("avg_band_gap"),
                        "avg_energy_above_hull": row.get("avg_energy_above_hull"),
                        "representative_material_id": row.get("representative_material_id"),
                        "representative_formula": row.get("representative_formula"),
                        "dominant_elements": elements,
                    }
                )
            for row in materials:
                cluster_id = f"chemsys:{row['chemsys']}" if row.get("chemsys") else None
                if cluster_id and cluster_id in cluster_ids:
                    edges.append(
                        {
                            "id": f"cluster-material:{cluster_id}:{row['material_id']}",
                            "source": cluster_id,
                            "target": row["material_id"],
                            "type": "BELONGS_TO_CLUSTER",
                            "weight": 0.18,
                        }
                    )

        return {
            "nodes": nodes,
            "edges": edges,
            "meta": {
                "source_release": self.paths.source_release,
                "material_count": len(materials),
                "element_count": element_count,
                "cluster_count": cluster_count,
                "edge_count": len(edges),
                "limit_materials": limit_materials,
            },
        }

    def graph_view(
        self,
        limit_nodes: int = 500,
        *,
        mode: str = "overview",
        include_elements: bool = False,
        include_clusters: bool = False,
    ) -> dict[str, Any]:
        """Return the default UI working slice.

        The backend can expose the full graph, but the browser should only
        simulate the slice a scientist is currently working with.
        """
        limit_nodes = max(50, min(int(limit_nodes), 1_500))
        if include_elements and include_clusters:
            material_budget = max(120, int(limit_nodes * 0.62))
        elif include_elements:
            material_budget = max(120, limit_nodes - 90)
        elif include_clusters:
            material_budget = max(120, int(limit_nodes * 0.72))
        else:
            material_budget = limit_nodes

        graph = self.graph_materials(
            limit_materials=min(material_budget, limit_nodes),
            include_elements=include_elements,
            include_clusters=False,
        )

        material_nodes = [node for node in graph["nodes"] if node.get("type") == "material"]
        element_count = sum(1 for node in graph["nodes"] if node.get("type") == "element")
        cluster_count = 0

        if include_clusters:
            remaining_node_budget = max(0, limit_nodes - len(graph["nodes"]))
            cluster_coverage: dict[str, int] = {}
            material_cluster: dict[str, str] = {}
            for node in material_nodes:
                chemsys = node.get("chemsys")
                if not chemsys:
                    continue
                cluster_id = f"chemsys:{chemsys}"
                material_cluster[str(node["id"])] = cluster_id
                cluster_coverage[cluster_id] = cluster_coverage.get(cluster_id, 0) + 1

            if remaining_node_budget > 0 and cluster_coverage:
                cluster_rows = self.query_df(
                    """
                    SELECT *
                    FROM graph_overview_clusters
                    ORDER BY material_count DESC, stable_count DESC
                    """
                )
                clusters_by_id = {
                    row["cluster_id"]: _decode_row(row)
                    for row in cluster_rows.to_dict(orient="records")
                    if row["cluster_id"] in cluster_coverage
                }
                ranked_cluster_ids = sorted(
                    clusters_by_id,
                    key=lambda cluster_id: (
                        cluster_coverage.get(cluster_id, 0),
                        clusters_by_id[cluster_id].get("material_count") or 0,
                        clusters_by_id[cluster_id].get("stable_count") or 0,
                    ),
                    reverse=True,
                )[:remaining_node_budget]
                kept_cluster_ids = set(ranked_cluster_ids)
                for cluster_id in ranked_cluster_ids:
                    row = clusters_by_id[cluster_id]
                    elements = row.get("dominant_elements_json") or []
                    graph["nodes"].append(
                        {
                            "id": row["cluster_id"],
                            "label": row.get("label") or row["cluster_id"],
                            "type": "cluster",
                            "cluster_type": row.get("cluster_type"),
                            "material_count": row.get("material_count"),
                            "visible_material_count": cluster_coverage.get(cluster_id, 0),
                            "stable_count": row.get("stable_count"),
                            "metal_count": row.get("metal_count"),
                            "avg_band_gap": row.get("avg_band_gap"),
                            "avg_energy_above_hull": row.get("avg_energy_above_hull"),
                            "representative_material_id": row.get("representative_material_id"),
                            "representative_formula": row.get("representative_formula"),
                            "dominant_elements": elements,
                        }
                    )
                cluster_count = len(kept_cluster_ids)
                for material_id, cluster_id in material_cluster.items():
                    if cluster_id not in kept_cluster_ids:
                        continue
                    graph["edges"].append(
                        {
                            "id": f"cluster-material:{cluster_id}:{material_id}",
                            "source": cluster_id,
                            "target": material_id,
                            "type": "BELONGS_TO_CLUSTER",
                            "weight": 0.18,
                        }
                    )

        max_edges = max(limit_nodes, min(limit_nodes * 3, 1_800))
        if len(graph["edges"]) > max_edges:
            structural = [
                edge
                for edge in graph["edges"]
                if edge.get("type") in {"BELONGS_TO_CLUSTER", "CONTAINS_ELEMENT"}
            ]
            similarity = [
                edge
                for edge in graph["edges"]
                if edge.get("type") not in {"BELONGS_TO_CLUSTER", "CONTAINS_ELEMENT"}
            ]
            similarity.sort(
                key=lambda edge: (
                    float(edge.get("weight") or 0),
                    float(edge.get("confidence") or 0),
                ),
                reverse=True,
            )
            graph["edges"] = structural[:max_edges] + similarity[: max(0, max_edges - len(structural))]

        graph["meta"] = {
            **graph.get("meta", {}),
            "view_mode": mode,
            "slice_contract": "working_slice",
            "requested_limit_nodes": limit_nodes,
            "material_count": len(material_nodes),
            "element_count": element_count,
            "cluster_count": cluster_count,
            "edge_count": len(graph["edges"]),
            "visible_node_count": len(graph["nodes"]),
            "visible_edge_count": len(graph["edges"]),
            "visible_material_count": len(material_nodes),
            "visible_element_count": element_count,
            "visible_cluster_count": cluster_count,
            "selection_strategy": "ranked_materials_with_visible_element_and_cluster_budget",
            "full_graph_available": True,
        }
        return graph

