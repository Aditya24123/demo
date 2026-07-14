from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from catalyst.agent_loop import run_local_agent_fallback, run_llm_agent_loop, should_use_local_agent_fast_path
from catalyst.agent_runtime import ensure_agent_runtime_files
from catalyst.candidate_sets import CandidateSetStore
from catalyst.codex_gateway import CodexGateway
from catalyst.model_services import ModelServiceRunner
from catalyst.project_store import ProjectStore
from catalyst.providers import provider_status
from catalyst.research_adapters import search_research_sources
from catalyst.research_mode import ResearchStore
from catalyst.research_sources import research_sources_payload
from catalyst.screening import screen_candidates
from catalyst.session_store import SessionStore, compact_session_context
from catalyst.settings import CatalystSettings, research_source_status
from catalyst.exporters import write_json_export
from catalyst.agent_tools_common import ELEMENT_SYMBOLS
class AgentToolsMaterialsMixin:
    def __init__(self, repo_root: Path, store: Any, settings: CatalystSettings) -> None:
        self.repo_root = repo_root
        self.store = store
        self.settings = settings
        self.sessions = SessionStore(repo_root)
        self.candidate_sets = CandidateSetStore(repo_root)
        self.research = ResearchStore(repo_root)
        self.projects = ProjectStore(repo_root)
        self.codex = CodexGateway(repo_root)
        self.model_services = ModelServiceRunner(settings)
        self.agent_runtime = ensure_agent_runtime_files(repo_root)

    def search_materials(self, payload: dict[str, Any]) -> dict[str, Any]:
        results = self.store.search(
            payload.get("query", ""),
            limit=int(payload.get("limit") or 20),
            elements=payload.get("elements") or [],
            chemsys=payload.get("chemsys"),
            stable=payload.get("stable"),
            metal=payload.get("metal"),
            magnetic=payload.get("magnetic"),
            band_gap_min=payload.get("band_gap_min"),
            band_gap_max=payload.get("band_gap_max"),
            density_min=payload.get("density_min"),
            density_max=payload.get("density_max"),
            evidence=payload.get("evidence"),
        )
        return {"results": results}

    def get_material_workspace(self, payload: dict[str, Any]) -> dict[str, Any]:
        material_id = str(payload["material_id"])
        workspace = self.store.workspace(material_id)
        return {"workspace": workspace}

    def get_neighborhood(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.store.neighborhood(str(payload["material_id"]))

    def get_material_details(self, payload: dict[str, Any]) -> dict[str, Any]:
        details = self.store.material_details(
            str(payload["material_id"]),
            sections=[str(item) for item in payload.get("sections") or []] or None,
            limit=max(1, min(int(payload.get("limit") or 25), 100)),
            downsample=bool(payload.get("downsample", True)),
        )
        return {"ok": bool(details), "details": details, **({} if details else {"error": "Material details not found"})}

    def get_material_structure(self, payload: dict[str, Any]) -> dict[str, Any]:
        structure = self.store.structure(str(payload["material_id"]))
        return {"ok": bool(structure), "structure": structure, **({} if structure else {"error": "Material structure not found"})}

    def get_graph_overview(self, payload: dict[str, Any]) -> dict[str, Any]:
        graph = self.store.graph_overview(limit_clusters=max(10, min(int(payload.get("limit_clusters") or 120), 500)))
        return {"ok": True, "graph": graph}

    def inspect_graph_node(self, payload: dict[str, Any]) -> dict[str, Any]:
        node = self.store.graph_node(str(payload.get("node_id") or ""))
        return {"ok": bool(node), "node": node, **({} if node else {"error": "Graph node not found"})}

    def inspect_edge(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"edge": self.store.edge(str(payload["edge_id"]))}

    def ingest_url(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = str(payload.get("url") or "")
        session_id = payload.get("session_id")
        purpose = payload.get("purpose")
        if not self.settings.research.allow_url_ingest:
            return self.research.ingest_url_disabled(url, session_id, "URL ingest is disabled in this local build.")
        return self.research.ingest_url(url, session_id, purpose)

    def screen_candidates(self, payload: dict[str, Any]) -> dict[str, Any]:
        return screen_candidates(
            self.store,
            str(payload["requirement"]),
            limit=int(payload.get("limit") or 10),
            include_research_candidates=bool(payload.get("include_research_candidates", False)),
        )

    def compare_materials(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.store.compare_materials(
            [str(item) for item in payload.get("material_ids", [])],
            include_evidence=bool(payload.get("include_evidence", True)),
            include_edges=bool(payload.get("include_edges", True)),
        )

    def create_candidate_set(self, payload: dict[str, Any]) -> dict[str, Any]:
        material_ids = [str(item) for item in payload.get("material_ids") or []]
        candidates = []
        for material_id in material_ids[:100]:
            material = self.store.get_material(material_id)
            if material:
                candidates.append({
                    "material_id": material_id,
                    "formula_pretty": material.get("formula_pretty"),
                    "material": material,
                })
        if not candidates:
            return {"ok": False, "error": "No valid local materials were provided"}
        candidate_set = self.candidate_sets.create_set(
            session_id=str(payload.get("session_id") or "") or None,
            title=str(payload.get("title") or "Candidate set"),
            candidates=candidates,
            requirement=str(payload.get("requirement") or "") or None,
        )
        return {"ok": True, "candidate_set": candidate_set}

    def list_candidate_sets(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "candidate_sets": self.candidate_sets.list_sets(payload.get("session_id"))}

    def get_candidate_set(self, payload: dict[str, Any]) -> dict[str, Any]:
        candidate_set = self.candidate_sets.get_set(str(payload.get("candidate_set_id") or ""))
        return {"ok": bool(candidate_set), "candidate_set": candidate_set, **({} if candidate_set else {"error": "Candidate set not found"})}

    def get_research_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        run = self.research.get_run(str(payload.get("run_id") or ""))
        return {"ok": bool(run), "run": run, **({} if run else {"error": "Research run not found"})}

    def list_project_runs(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            project_id = self._project_id(payload)
            return {"ok": True, "runs": self.projects.list_runs(project_id, limit=int(payload.get("limit") or 50))}
        except (ValueError, FileNotFoundError) as exc:
            return {"ok": False, "error": str(exc)}

    def list_model_services(self, _payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "services": self.model_services.list_services()}

    def run_model_service(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = str(payload.get("project_id") or "").strip() or None
        run: dict[str, Any] | None = None
        try:
            if project_id:
                run = self.projects.save_run(project_id, {
                    "kind": "model_service",
                    "status": "running",
                    "service_id": str(payload.get("service_id") or ""),
                    "inputs": payload.get("inputs") or {},
                })
            result = self.model_services.run(
                str(payload.get("service_id") or ""),
                payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {},
            )
            if project_id and run:
                serialized = json.dumps(result.get("result"), default=str)
                self.projects.save_run(project_id, {
                    **run,
                    "status": "completed",
                    "result_preview": serialized[:100_000],
                })
            return {**result, "project_id": project_id}
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            if project_id and run:
                self.projects.save_run(project_id, {**run, "status": "failed", "error": str(exc)[-4000:]})
            return {"ok": False, "error": str(exc), "project_id": project_id}

    def export_subgraph(self, payload: dict[str, Any]) -> dict[str, Any]:
        material_ids = [str(item) for item in payload.get("material_ids", [])]
        return self.store.export_subgraph(
            material_ids,
            include_evidence=bool(payload.get("include_evidence", True)),
            include_edge_details=bool(payload.get("include_edge_details", True)),
        )

    def start_research(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = str(payload.get("query") or "")
        session_id = payload.get("session_id")
        if not self.settings.research.enabled:
            return self.research.create_disabled_run(
                query,
                "Research mode is not enabled in this local build.",
                session_id=session_id,
            )
        requested_sources = payload.get("sources") or self.settings.research.sources
        source_status = research_source_status(self.settings)
        available_sources = [source for source in requested_sources if source_status.get(source) == "available"]
        if not available_sources:
            return self.research.create_stub_run(
                query=query,
                session_id=session_id,
                sources=requested_sources,
                message="Research mode is enabled, but no requested sources are currently configured.",
            )
        searched = search_research_sources(query, available_sources, limit=int(payload.get("limit") or 5))
        return self.research.create_completed_run(
            query=query,
            session_id=session_id,
            sources=available_sources,
            hits=searched["hits"],
            errors=searched["errors"],
        )

    def _resolve_material_reference(self, message: str) -> str | None:
        explicit = _extract_material_id(message)
        if explicit:
            return explicit
        for token in _extract_formula_like_tokens(message):
            # Wider limit: short formulas like "cds" also match id substrings in ranking.
            results = self.store.search(token, limit=12)
            token_l = token.lower()
            exact = None
            for result in results:
                formula = str(result.get("formula_pretty") or "").lower()
                if formula == token_l:
                    exact = str(result["material_id"])
                    break
            if exact:
                return exact
            # Prefer exact formula over fuzzy id hits (mp-cdskh vs CdS).
            for result in results:
                formula = str(result.get("formula_pretty") or "")
                if formula and formula.lower() == token_l:
                    return str(result["material_id"])
        return None

def _extract_material_id(text: str) -> str | None:
    match = re.search(r"\bmp-[a-z0-9-]+\b", text, re.IGNORECASE)
    return match.group(0) if match else None


def _extract_formula_like_tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9]{1,31}\b", text)
    candidates: list[str] = []
    for token in raw_tokens:
        if _is_formula_like_token(token):
            candidates.append(token)
    return candidates


def _is_formula_like_token(token: str) -> bool:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,31}", token):
        return False
    index = 0
    groups = 0
    has_digit = any(char.isdigit() for char in token)
    while index < len(token):
        if not token[index].isalpha():
            return False
        matched = None
        for width in (2, 1):
            part = token[index : index + width]
            if len(part) != width or not part.isalpha():
                continue
            symbol = part[0].upper() + part[1:].lower()
            if symbol in ELEMENT_SYMBOLS:
                matched = symbol
                index += width
                break
        if not matched:
            return False
        while index < len(token) and token[index].isdigit():
            index += 1
        groups += 1
    return groups >= 2 or has_digit
