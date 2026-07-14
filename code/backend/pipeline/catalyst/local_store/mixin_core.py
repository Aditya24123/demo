from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from catalyst.elements import build_element_nodes
from catalyst.graph_artifacts import build_graph_artifacts
from catalyst.local_store.helpers import LocalPaths, _decode_row, _jsonl_count
from catalyst.resolver import build_material_id_resolver
from catalyst.util import read_jsonl, to_jsonable
from catalyst.build_processed import material_from_records

class LocalStoreCoreMixin:
    def __init__(self, repo_root: Path, source_release: str = "v2025.09.25") -> None:
        self.paths = LocalPaths(repo_root=repo_root, source_release=source_release)
        if not self.paths.resolver_path.exists():
            build_material_id_resolver(repo_root, source_release)
        if not self.paths.graph_manifest_path.exists():
            build_graph_artifacts(repo_root, source_release)
        self._lock = threading.Lock()
        self.conn = duckdb.connect(database=":memory:")
        self._register_views()
        self._elements_by_symbol = {
            element.symbol: to_jsonable(element.model_dump(mode="json")) for element in build_element_nodes()
        }
        # Avoid re-scanning multi-hundred-MB JSONL files on every inspector open.
        self._details_memo: dict[str, dict[str, Any]] = {}
        self._details_memo_lock = threading.Lock()
        self._evidence_index_cache: dict[str, dict[str, int]] = {}

    def _register_views(self) -> None:
        with self._lock:
            processed = self.paths.processed_root
            self.conn.execute(f"CREATE VIEW materials AS SELECT * FROM read_parquet('{processed / 'materials.parquet'}')")
            self.conn.execute(f"CREATE VIEW elements AS SELECT * FROM read_parquet('{processed / 'elements.parquet'}')")
            self.conn.execute(f"CREATE VIEW material_element_edges AS SELECT * FROM read_parquet('{processed / 'material_element_edges.parquet'}')")
            self.conn.execute(f"CREATE VIEW material_edges AS SELECT * FROM read_parquet('{processed / 'material_edges.parquet'}')")
            self.conn.execute(f"CREATE VIEW resolver AS SELECT * FROM read_parquet('{self.paths.resolver_path}')")
            self.conn.execute(f"CREATE VIEW evidence_index AS SELECT * FROM read_parquet('{self.paths.graph_root / 'evidence_index.parquet'}')")
            self.conn.execute(f"CREATE VIEW material_material_edges AS SELECT * FROM read_parquet('{self.paths.graph_root / 'material_material_edges.parquet'}')")
            self.conn.execute(f"CREATE VIEW material_workspace_index AS SELECT * FROM read_parquet('{self.paths.graph_root / 'material_workspace_index.parquet'}')")
            self.conn.execute(f"CREATE VIEW graph_overview_clusters AS SELECT * FROM read_parquet('{self.paths.graph_root / 'graph_overview_clusters.parquet'}')")

    def query_df(self, query: str, parameters: list[Any] | None = None) -> pd.DataFrame:
        with self._lock:
            cursor = self.conn.cursor()
            try:
                if parameters is not None:
                    return cursor.execute(query, parameters).fetchdf()
                return cursor.execute(query).fetchdf()
            finally:
                cursor.close()

    def resolver_row(self, material_id: str) -> dict[str, Any] | None:
        rows = self.query_df(
            "SELECT * FROM resolver WHERE input_material_id = ? OR resolved_material_id = ? ORDER BY resolution_method DESC LIMIT 1",
            [material_id, material_id],
        )
        if rows.empty:
            return None
        return _decode_row(rows.iloc[0].to_dict())

    def _target_dir(self, material_id: str) -> Path:
        return self.paths.raw_root / "targets" / material_id

    def _target_record(self, material_id: str) -> dict[str, Any] | None:
        target_dir = self._target_dir(material_id)
        if not target_dir.exists():
            return None
        core_rows = read_jsonl(target_dir / "materials_core.jsonl") if (target_dir / "materials_core.jsonl").exists() else []
        summary_rows = read_jsonl(target_dir / "materials_summary.jsonl") if (target_dir / "materials_summary.jsonl").exists() else []
        if not core_rows and not summary_rows:
            return None
        oxidation = read_jsonl(target_dir / "oxidation_states.jsonl")[0] if (target_dir / "oxidation_states.jsonl").exists() and _jsonl_count(target_dir / "oxidation_states.jsonl") else None
        chemenv = read_jsonl(target_dir / "chemenv.jsonl")[0] if (target_dir / "chemenv.jsonl").exists() and _jsonl_count(target_dir / "chemenv.jsonl") else None
        core = core_rows[0] if core_rows else summary_rows[0]
        summary = summary_rows[0] if summary_rows else {}
        material = material_from_records(core, summary, self.paths.source_release, oxidation_states=oxidation, chemenv=chemenv)
        row = to_jsonable(material.model_dump(mode="json"))
        row["demo_pack_only"] = True
        return row

    def get_material(self, material_id: str) -> dict[str, Any] | None:
        resolved = self.resolver_row(material_id)
        lookup_id = resolved.get("resolved_material_id") if resolved else material_id
        rows = self.query_df("SELECT * FROM materials WHERE material_id = ? LIMIT 1", [lookup_id])
        if not rows.empty:
            material = _decode_row(rows.iloc[0].to_dict())
        else:
            material = self._target_record(str(lookup_id)) or self._target_record(material_id)
        if not material:
            return None
        material["resolver"] = resolved or {
            "input_material_id": material_id,
            "resolved_material_id": None,
            "resolution_status": "not_found",
            "resolution_method": "not_found",
        }
        return material

    def search(
        self,
        query: str = "",
        limit: int = 25,
        *,
        elements: list[str] | None = None,
        chemsys: str | None = None,
        stable: bool | None = None,
        metal: bool | None = None,
        magnetic: bool | None = None,
        band_gap_min: float | None = None,
        band_gap_max: float | None = None,
        density_min: float | None = None,
        density_max: float | None = None,
        evidence: str | None = None,
    ) -> list[dict[str, Any]]:
        q = query.strip()
        clauses = []
        params: list[Any] = []
        if q:
            like = f"%{q}%"
            clauses.append("(material_id ILIKE ? OR formula_pretty ILIKE ? OR chemsys ILIKE ?)")
            params.extend([like, like, like])
        if chemsys:
            clauses.append("chemsys = ?")
            params.append(chemsys)
        if stable is not None:
            clauses.append("is_stable = ?")
            params.append(stable)
        if metal is not None:
            clauses.append("is_metal = ?")
            params.append(metal)
        if magnetic is not None:
            clauses.append("is_magnetic = ?")
            params.append(magnetic)
        if band_gap_min is not None:
            clauses.append("band_gap >= ?")
            params.append(band_gap_min)
        if band_gap_max is not None:
            clauses.append("band_gap <= ?")
            params.append(band_gap_max)
        if density_min is not None:
            clauses.append("density >= ?")
            params.append(density_min)
        if density_max is not None:
            clauses.append("density <= ?")
            params.append(density_max)
        for element in elements or []:
            clauses.append("CAST(elements AS VARCHAR) ILIKE ?")
            params.append(f"%{element}%")
        if evidence:
            clauses.append("material_id IN (SELECT material_id FROM evidence_index WHERE section = ?)")
            params.append(evidence)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self.query_df(
            f"""
            SELECT material_id, formula_pretty, chemsys, band_gap, energy_above_hull,
                   formation_energy_per_atom, density, is_stable, is_metal, is_magnetic,
                   source_release, 'processed' AS source
            FROM materials
            {where}
            ORDER BY is_stable DESC, energy_above_hull ASC
            LIMIT ?
            """,
            params,
        )
        results = [_decode_row(row) for row in rows.to_dict(orient="records")]

        if not q:
            return results[:limit]
        like = f"%{q}%"
        resolver_rows = self.query_df(
            """
            SELECT input_material_id AS material_id, formula_pretty, chemsys, source_release, resolution_method AS source
            FROM resolver
            WHERE input_material_id ILIKE ? OR formula_pretty ILIKE ? OR chemsys ILIKE ?
            LIMIT ?
            """,
            [like, like, like, limit],
        )
        seen = {row["material_id"] for row in results}
        for row in resolver_rows.to_dict(orient="records"):
            if row["material_id"] not in seen:
                results.append(_decode_row(row))
                seen.add(row["material_id"])
        return results[:limit]

    def catalog(self) -> dict[str, Any]:
        counts = {
            "materials": int(self.query_df("SELECT COUNT(*) AS n FROM materials").iloc[0]["n"]),
            "elements": int(self.query_df("SELECT COUNT(*) AS n FROM elements").iloc[0]["n"]),
            "material_element_edges": int(
                self.query_df("SELECT COUNT(*) AS n FROM material_element_edges").iloc[0]["n"]
            ),
            "material_material_edges": int(
                self.query_df("SELECT COUNT(*) AS n FROM material_material_edges").iloc[0]["n"]
            ),
            "evidence_rows": int(self.query_df("SELECT COUNT(*) AS n FROM evidence_index").iloc[0]["n"]),
            "overview_clusters": int(self.query_df("SELECT COUNT(*) AS n FROM graph_overview_clusters").iloc[0]["n"]),
            "curated_start_materials": self._curated_count(),
            "research_candidates": 0,
        }
        return {
            "product": "Catalyst",
            "source": {
                "name": "Materials Project",
                "source_release": self.paths.source_release,
                "snapshot_label": "10,000 selected Materials Project materials",
            },
            "counts": counts,
            "capabilities": {
                "local_search": True,
                "graph_overview": True,
                "material_workspace": True,
                "candidate_compare": True,
                "export_json": True,
                "export_csv": True,
                "agent": True,
                "research_mode": False,
                "pdf_ingest": False,
                "url_ingest": False,
                "multimodal_inputs": False,
            },
        }

    def _curated_count(self) -> int:
        rows = self.query_df("SELECT COUNT(*) AS n FROM material_workspace_index WHERE curated_score >= 20")
        return int(rows.iloc[0]["n"])

    def evidence(self, material_id: str) -> dict[str, Any]:
        material = self.get_material(material_id)
        resolved_id = (material or {}).get("material_id", material_id)
        rows = self.query_df(
            """
            SELECT section AS name, records, source, file
            FROM evidence_index
            WHERE material_id = ?
            ORDER BY source DESC, section ASC
            """,
            [str(resolved_id)],
        )
        sections = [_decode_row(row) for row in rows.to_dict(orient="records")]
        return {"material_id": material_id, "resolved_material_id": resolved_id, "sections": sections}

    def _material_relation_rows(self, material_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
        rows = self.query_df(
            """
            SELECT edge_id, source_id, target_id, edge_type, weight, confidence, recipe_name, reason_summary
            FROM material_material_edges
            WHERE source_id = ? OR target_id = ?
            ORDER BY weight DESC
            LIMIT ?
            """,
            [material_id, material_id, int(limit)],
        )
        return [_decode_row(row) for row in rows.to_dict(orient="records")]

    def _material_node_payload(self, material_id: str, material: dict[str, Any] | None = None) -> dict[str, Any]:
        mat = material or self.get_material(material_id) or {"material_id": material_id}
        mid = str(mat.get("material_id") or material_id)
        return {
            "id": mid,
            "label": mat.get("formula_pretty") or mid,
            "type": "material",
            "material_id": mid,
            "formula_pretty": mat.get("formula_pretty"),
            "chemsys": mat.get("chemsys"),
            "band_gap": mat.get("band_gap"),
            "is_stable": mat.get("is_stable"),
        }

    def _element_node_payload(self, symbol: str) -> dict[str, Any]:
        element = self._elements_by_symbol.get(symbol, {"symbol": symbol, "name": symbol, "atomic_number": None})
        return {"id": symbol, "label": symbol, "type": "element", **element}

    def _element_edges_for_material(self, material_id: str, material: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        edge_rows = self.query_df("SELECT * FROM material_element_edges WHERE material_id = ?", [material_id])
        if edge_rows.empty and material is not None:
            return self._derive_target_edges(material)
        return [_decode_row(row) for row in edge_rows.to_dict(orient="records")]

    def _materials_for_element(self, symbol: str, *, limit: int = 16, exclude_ids: set[str] | None = None) -> list[dict[str, Any]]:
        """Materials that contain an element ? used as hop bridges when relation cliques stall."""
        exclude = exclude_ids or set()
        # Pull a bit extra so excludes don't leave the hop empty.
        fetch_limit = max(limit + len(exclude), limit * 2)
        rows = self.query_df(
            """
            SELECT
                e.material_id,
                e.atomic_fraction,
                e.stoich_amount,
                e.edge_type,
                m.formula_pretty,
                m.chemsys,
                m.band_gap,
                m.is_stable,
                m.energy_above_hull
            FROM material_element_edges e
            LEFT JOIN materials m ON e.material_id = m.material_id
            WHERE e.element_symbol = ?
            ORDER BY
                COALESCE(m.is_stable, FALSE) DESC,
                e.atomic_fraction DESC NULLS LAST,
                m.energy_above_hull ASC NULLS LAST,
                e.material_id ASC
            LIMIT ?
            """,
            [symbol, int(fetch_limit)],
        )
        out: list[dict[str, Any]] = []
        for row in rows.to_dict(orient="records"):
            rec = _decode_row(row)
            mid = str(rec.get("material_id") or "")
            if not mid or mid in exclude:
                continue
            out.append(rec)
            if len(out) >= limit:
                break
        return out

    def curated_random_material(self) -> dict[str, Any] | None:
        rows = self.query_df(
            """
            SELECT material_id
            FROM material_workspace_index
            WHERE curated_score >= 20
            ORDER BY random()
            LIMIT 1
            """
        )
        if rows.empty:
            return None
        return self.get_material(str(rows.iloc[0]["material_id"]))

