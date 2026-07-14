from __future__ import annotations

import os
import subprocess
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import json

from catalyst.agent_tools import CatalystAgentTools, tool_catalog
from catalyst.candidate_sets import CandidateSetStore
from catalyst.codex_gateway import CodexGateway
from catalyst.contracts import (
    AgentChatResponse,
    AgentToolCatalogResponse,
    CandidateExportResponse,
    CatalogResponse,
    CompareResponse,
    FlexibleResponse,
    HealthResponse,
    ProjectListResponse,
    ProjectRecord,
    ResearchQueryResponse,
    ResearchStatusResponse,
    ScreenResponse,
    SearchResponse,
    SessionListResponse,
    SettingsResponse,
)
from catalyst.exporters import write_candidate_csv, write_json_export
from catalyst.genome_sequences import GenomeSequenceRepository
from catalyst.genomics_demo import get_case as get_genomics_case, list_cases as list_genomics_cases
from catalyst.demo_scenarios import scenario_catalog
from catalyst.local_store import LocalCatalystStore
from catalyst.project_store import ProjectStore
from catalyst.research_mode import ResearchStore, research_status
from catalyst.screening import screen_candidates
from catalyst.session_store import SessionStore
from catalyst.settings import (
    CatalystSettings,
    configured_provider_status,
    load_settings,
    research_source_status,
    save_settings,
    settings_schema,
)
from catalyst.util import find_repo_root
from catalyst.voice_live import catalyst_voice_live
from catalyst.api_models import (  # noqa: F401
    AgentChatRequest,
    CandidateExportRequest,
    CandidateSetCreateRequest,
    CandidateSetPatchRequest,
    CodexRunRequest,
    CompareRequest,
    IngestPdfRequest,
    IngestUrlRequest,
    NotebookUpdateRequest,
    ProjectCreateRequest,
    ProjectFileUpdateRequest,
    ProjectUpdateRequest,
    ResearchQueryRequest,
    ScreenRequest,
    SessionCreateRequest,
    SessionPatchRequest,
    SettingsPatchRequest,
    SubgraphExportRequest,
    _deep_merge,
    _split_csv,
)


def _repo_root() -> Path:
    configured = os.getenv("CATALYST_REPO_ROOT")
    if configured:
        return Path(configured)

    return find_repo_root(Path(__file__).resolve())


@lru_cache(maxsize=1)
def get_store() -> LocalCatalystStore:
    return LocalCatalystStore(_repo_root(), os.getenv("CATALYST_SOURCE_RELEASE", "v2025.09.25"))


@lru_cache(maxsize=1)
def cached_store_catalog() -> dict:
    return get_store().catalog()


@lru_cache(maxsize=64)
def cached_graph_overview(limit_clusters: int) -> dict:
    return get_store().graph_overview(limit_clusters=limit_clusters)


@lru_cache(maxsize=64)
def cached_graph_view(mode: str, limit_nodes: int, include_elements: bool, include_clusters: bool) -> dict:
    return get_store().graph_view(
        limit_nodes=limit_nodes,
        mode=mode,
        include_elements=include_elements,
        include_clusters=include_clusters,
    )


@lru_cache(maxsize=32)
def cached_graph_materials(limit_materials: int, include_elements: bool, include_clusters: bool) -> dict:
    return get_store().graph_materials(
        limit_materials=limit_materials,
        include_elements=include_elements,
        include_clusters=include_clusters,
    )


@lru_cache(maxsize=2048)
def cached_material(material_id: str) -> dict | None:
    return get_store().get_material(material_id)


@lru_cache(maxsize=1024)
def cached_evidence(material_id: str) -> dict:
    return get_store().evidence(material_id)


@lru_cache(maxsize=1024)
def cached_neighborhood(material_id: str, depth: int, limit_nodes: int) -> dict:
    return get_store().neighborhood(material_id, depth=depth, limit_nodes=limit_nodes)


@lru_cache(maxsize=1024)
def cached_structure(material_id: str) -> dict | None:
    return get_store().structure(material_id)


@lru_cache(maxsize=1024)
def cached_material_details(material_id: str, sections_key: str, limit: int, downsample: bool) -> dict | None:
    sections = _split_csv(sections_key) or None
    return get_store().material_details(material_id, sections=sections, limit=limit, downsample=downsample)


@lru_cache(maxsize=1024)
def cached_workspace(material_id: str) -> dict | None:
    return get_store().workspace(material_id)


@lru_cache(maxsize=2048)
def cached_edge(edge_id: str) -> dict | None:
    return get_store().edge(edge_id)


def clear_read_caches() -> None:
    cached_store_catalog.cache_clear()
    cached_graph_overview.cache_clear()
    cached_graph_view.cache_clear()
    cached_graph_materials.cache_clear()
    cached_material.cache_clear()
    cached_evidence.cache_clear()
    cached_neighborhood.cache_clear()
    cached_structure.cache_clear()
    cached_material_details.cache_clear()
    cached_workspace.cache_clear()
    cached_edge.cache_clear()


@lru_cache(maxsize=1)
def get_settings():
    return load_settings(_repo_root())


def get_sessions() -> SessionStore:
    return SessionStore(_repo_root())


@lru_cache(maxsize=1)
def get_projects() -> ProjectStore:
    return ProjectStore(_repo_root())


def get_codex() -> CodexGateway:
    return CodexGateway(_repo_root())


def get_candidate_sets() -> CandidateSetStore:
    return CandidateSetStore(_repo_root())


def get_research_store() -> ResearchStore:
    return ResearchStore(_repo_root())


def get_agent_tools() -> CatalystAgentTools:
    return CatalystAgentTools(_repo_root(), get_store(), get_settings())


@lru_cache(maxsize=1)
def get_genome_sequences() -> GenomeSequenceRepository:
    return GenomeSequenceRepository(_repo_root())


app = FastAPI(title="Catalyst Local API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _frontend_dist() -> Path:
    return _repo_root() / "code" / "frontend" / "dist"


def mount_frontend_if_present() -> None:
    dist = _frontend_dist()
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")


@app.exception_handler(HTTPException)
def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": f"http_{exc.status_code}", "message": str(exc.detail)}},
    )


@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok", "backend": "local-files-duckdb", "version": app.version}


@app.get("/catalog", response_model=CatalogResponse)
def catalog() -> dict:
    settings = get_settings()
    payload = deepcopy(cached_store_catalog())
    provider_status = configured_provider_status(settings)
    payload["provider_status"] = {
        "llm_configured": provider_status["llm_configured"],
        "active_provider": provider_status["active_provider"],
        "providers": provider_status["providers"],
        "literature_sources": research_source_status(settings),
    }
    payload["capabilities"]["agent"] = True
    payload["capabilities"]["research_mode"] = settings.research.enabled
    payload["capabilities"]["pdf_ingest"] = settings.research.enabled and settings.research.allow_pdf_ingest
    payload["capabilities"]["url_ingest"] = settings.research.enabled and settings.research.allow_url_ingest
    payload["capabilities"]["multimodal_inputs"] = False
    return payload


@app.get("/settings/schema")
def get_settings_schema() -> dict:
    return settings_schema()


@app.get("/settings", response_model=SettingsResponse)
def get_runtime_settings() -> dict:
    settings = get_settings()
    return {
        "settings": settings.model_dump(mode="json"),
        "provider_status": configured_provider_status(settings),
        "research_sources": research_source_status(settings),
    }


@app.get("/genomics/cases", response_model=FlexibleResponse)
def genomics_cases() -> dict:
    """Curated, offline-safe records used by the bounded Genes demo rail."""
    return {"cases": list_genomics_cases(), "scope": "educational demo; not diagnostic or clinical advice"}


@app.get("/genomics/cases/{case_id}", response_model=FlexibleResponse)
def genomics_case(case_id: str, repeat_count: int | None = Query(None, ge=0, le=100)) -> dict:
    payload = get_genomics_case(case_id, repeat_count=repeat_count)
    if not payload:
        raise HTTPException(status_code=404, detail="Unknown genomics demo case. Use brca1, hbb, or ctg.")
    return payload


@app.get("/genomics/state/{gene}", response_model=FlexibleResponse)
def genomics_state(
    gene: str,
    visible_start: int | None = Query(None, ge=1),
    visible_end: int | None = Query(None, ge=1),
    selected_position: int | None = Query(None, ge=1),
) -> dict:
    try:
        return get_genome_sequences().state(
            gene,
            visible_start=visible_start,
            visible_end=visible_end,
            selected_position=selected_position,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - report cache/source state at API boundary
        raise HTTPException(status_code=503, detail=f"Genome sequence unavailable: {exc}") from exc


@app.get("/graph/overview", response_model=FlexibleResponse)
def graph_overview(limit_clusters: int = Query(250, ge=10, le=1000)) -> dict:
    return cached_graph_overview(limit_clusters)


@app.get("/graph/view", response_model=FlexibleResponse)
def graph_view(
    mode: str = Query("overview", pattern="^(overview|search|neighborhood|cluster)$"),
    limit_nodes: int = Query(500, ge=50, le=1500),
    include_elements: bool = Query(False),
    include_clusters: bool = Query(False),
) -> dict:
    return cached_graph_view(mode, limit_nodes, include_elements, include_clusters)


@app.get("/graph/materials", response_model=FlexibleResponse)
def graph_materials(
    limit_materials: int = Query(10_000, ge=1, le=10_000),
    include_elements: bool = Query(True),
    include_clusters: bool = Query(True),
) -> dict:
    return cached_graph_materials(limit_materials, include_elements, include_clusters)


@app.get("/graph/nodes/{node_id:path}", response_model=FlexibleResponse)
def graph_node(node_id: str) -> dict:
    node = get_store().graph_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Graph node not found: {node_id}")
    return node


@app.get("/materials/random", response_model=FlexibleResponse)
def random_material(mode: str = Query("curated", pattern="^(curated|any)$")) -> dict:
    store = get_store()
    if mode == "curated":
        material = store.curated_random_material()
    else:
        rows = store.query_df("SELECT material_id FROM materials ORDER BY random() LIMIT 1")
        material = store.get_material(str(rows.iloc[0]["material_id"])) if not rows.empty else None
    if not material:
        raise HTTPException(status_code=404, detail=f"No random material available for mode: {mode}")
    return material


@app.get("/materials/{material_id}", response_model=FlexibleResponse)
def get_material(material_id: str) -> dict:
    material = cached_material(material_id)
    if not material:
        raise HTTPException(status_code=404, detail=f"Material not found: {material_id}")
    return material


@app.get("/materials/{material_id}/evidence", response_model=FlexibleResponse)
def get_evidence(material_id: str) -> dict:
    material = cached_material(material_id)
    if not material:
        raise HTTPException(status_code=404, detail=f"Material not found: {material_id}")
    return cached_evidence(material_id)


@app.get("/materials/{material_id}/neighborhood", response_model=FlexibleResponse)
def get_neighborhood(
    material_id: str,
    depth: int = Query(1, ge=1, le=5),
    # UI hop chip uses up to ~748 nodes at depth 5 (48 + depth*140); keep headroom.
    limit_nodes: int = Query(80, ge=10, le=800),
) -> dict:
    graph = cached_neighborhood(material_id, depth, limit_nodes)
    if not graph["nodes"]:
        raise HTTPException(status_code=404, detail=f"Material not found: {material_id}")
    return graph


@app.get("/materials/{material_id}/structure", response_model=FlexibleResponse)
def get_structure(material_id: str) -> dict:
    structure = cached_structure(material_id)
    if not structure:
        raise HTTPException(status_code=404, detail=f"Material not found: {material_id}")
    return structure


@app.get("/materials/{material_id}/details", response_model=FlexibleResponse)
def get_material_details(
    material_id: str,
    sections: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    downsample: bool = True,
) -> dict:
    sections_list = _split_csv(sections)
    sections_key = ",".join(sections_list)
    payload = cached_material_details(material_id, sections_key, limit, downsample)
    if not payload:
        raise HTTPException(status_code=404, detail=f"Material not found: {material_id}")
    # If local spectra index is empty but MP enrich already pulled XAS, surface it here.
    wants_spectra = not sections_list or any(s.lower() in {"spectra", "xas"} for s in sections_list)
    if wants_spectra:
        try:
            from catalyst.mp_enrich import get_enrichment

            enrich = get_enrichment(_repo_root(), str(payload.get("resolved_material_id") or material_id))
            local_spec = ((payload.get("details") or {}).get("spectra") or {})
            local_count = int(local_spec.get("count") or 0)
            remote_spec = (enrich or {}).get("spectra") if isinstance(enrich, dict) else None
            remote_records = (remote_spec or {}).get("records") if isinstance(remote_spec, dict) else None
            if local_count <= 0 and remote_records:
                details = dict(payload.get("details") or {})
                details["spectra"] = {
                    "records": remote_records[: max(1, min(limit, 25))],
                    "count": len(remote_records),
                    "truncated": len(remote_records) > limit,
                    "source": (remote_spec or {}).get("source") or "materials_project_api",
                }
                payload = {**payload, "details": details}
        except Exception:
            pass
    return payload


@app.get("/materials/{material_id}/workspace", response_model=FlexibleResponse)
def get_workspace(material_id: str) -> dict:
    workspace = cached_workspace(material_id)
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Material not found: {material_id}")
    # Merge MP enrich cache (description / capabilities) so Properties summary is not blank
    # after a successful enrich that never got re-applied client-side.
    try:
        from catalyst.mp_enrich import get_enrichment

        enrich = get_enrichment(_repo_root(), str(workspace.get("resolved_material_id") or material_id))
        if enrich and enrich.get("ok"):
            if enrich.get("description") and not workspace.get("description"):
                workspace = {**workspace, "description": enrich.get("description")}
            caps = dict(workspace.get("capabilities") or {})
            for key, value in (enrich.get("capabilities") or {}).items():
                caps[key] = bool(caps.get(key) or value)
            if enrich.get("description"):
                caps["summary"] = True
            workspace = {
                **workspace,
                "capabilities": caps,
                "mp_material_id": enrich.get("mp_material_id") or workspace.get("mp_material_id"),
            }
            summary = dict(workspace.get("summary") or {})
            remote_summary = enrich.get("summary") if isinstance(enrich.get("summary"), dict) else {}
            for key in (
                "band_gap",
                "formation_energy_per_atom",
                "energy_above_hull",
                "is_stable",
                "is_metal",
                "is_magnetic",
                "ordering",
                "density",
                "volume",
            ):
                if summary.get(key) is None and remote_summary.get(key) is not None:
                    summary[key] = remote_summary.get(key)
            if enrich.get("description"):
                summary["description"] = enrich.get("description")
            workspace["summary"] = summary
    except Exception:
        pass
    return workspace


@app.get("/materials/{material_id}/enrich", response_model=FlexibleResponse)
def get_material_enrich(material_id: str, force: bool = Query(False), refresh: bool = Query(False)) -> dict:
    """Local-first selected-material enrich; optional live Materials Project fill for gaps."""
    from catalyst.mp_enrich import enrich_material

    payload = enrich_material(
        get_store(),
        _repo_root(),
        material_id,
        force=bool(force or refresh),
    )
    if not payload.get("ok") and payload.get("error"):
        raise HTTPException(status_code=404, detail=str(payload.get("error")))
    return payload


@app.post("/materials/{material_id}/enrich", response_model=FlexibleResponse)
def post_material_enrich(material_id: str, force: bool = Query(False), refresh: bool = Query(False)) -> dict:
    """Force refresh enrich (same handler as GET with force/refresh)."""
    return get_material_enrich(material_id, force=True if refresh else force, refresh=refresh)


@app.get("/edges/{edge_id:path}", response_model=FlexibleResponse)
def get_edge(edge_id: str) -> dict:
    edge = cached_edge(edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail=f"Edge not found: {edge_id}")
    return edge


@app.post("/export/subgraph", response_model=FlexibleResponse)
def export_subgraph(request: SubgraphExportRequest) -> dict:
    material_ids = [material_id for material_id in request.material_ids if material_id.strip()]
    if not material_ids:
        raise HTTPException(status_code=400, detail="material_ids must contain at least one material id")
    return get_store().export_subgraph(
        material_ids,
        include_evidence=request.include_evidence,
        include_edge_details=request.include_edge_details,
    )


@app.post("/export/candidates", response_model=CandidateExportResponse)
def export_candidates(request: CandidateExportRequest) -> dict:
    rows: list[dict[str, Any]] = []
    if request.candidate_set_id:
        candidate_set = get_candidate_sets().get_set(request.candidate_set_id)
        if not candidate_set:
            raise HTTPException(status_code=404, detail=f"Candidate set not found: {request.candidate_set_id}")
        rows = candidate_set.get("candidates", [])
    elif request.material_ids:
        compared = get_store().compare_materials(request.material_ids, include_evidence=False, include_edges=False)
        rows = compared["materials"]
    else:
        raise HTTPException(status_code=400, detail="candidate_set_id or material_ids is required")
    if request.format == "csv":
        return write_candidate_csv(_repo_root(), rows)
    return write_json_export(_repo_root(), {"candidates": rows}, prefix="catalyst-candidates")


@app.post("/screen", response_model=ScreenResponse)
def screen(request: ScreenRequest) -> dict:
    options = request.options or {}
    return screen_candidates(
        get_store(),
        request.requirement,
        limit=int(options.get("limit") or 10),
        include_research_candidates=bool(options.get("include_research_candidates", False)),
    )


@app.post("/compare", response_model=CompareResponse)
def compare(request: CompareRequest) -> dict:
    material_ids = [material_id for material_id in request.material_ids if material_id.strip()]
    if not material_ids:
        raise HTTPException(status_code=400, detail="material_ids must contain at least one material id")
    return get_store().compare_materials(
        material_ids,
        include_evidence=request.include_evidence,
        include_edges=request.include_edges,
    )


@app.get("/projects", response_model=ProjectListResponse)
def list_projects(include_archived: bool = False) -> dict:
    return {"projects": get_projects().list_projects(include_archived=include_archived)}


@app.post("/projects", response_model=ProjectRecord, status_code=201)
def create_project(request: ProjectCreateRequest) -> dict:
    try:
        return get_projects().create_project(
            name=request.name,
            project_id=request.project_id,
            description=request.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/projects/{project_id}", response_model=ProjectRecord)
def get_project(project_id: str) -> dict:
    try:
        project = get_projects().get_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return project


@app.patch("/projects/{project_id}", response_model=ProjectRecord)
def update_project(project_id: str, request: ProjectUpdateRequest) -> dict:
    try:
        project = get_projects().update_project(project_id, **request.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return project


@app.post("/projects/{project_id}/archive", response_model=ProjectRecord)
def archive_project(project_id: str) -> dict:
    try:
        project = get_projects().archive_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return project


@app.get("/projects/{project_id}/workspace")
def get_project_workspace(project_id: str) -> dict:
    try:
        snapshot = get_projects().workspace_snapshot(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snapshot["codex"]["runtime"] = get_codex().status()
    return snapshot


@app.get("/projects/{project_id}/notebook")
def get_project_notebook(project_id: str) -> dict:
    try:
        return get_projects().read_notebook(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/projects/{project_id}/notebook")
def put_project_notebook(project_id: str, request: NotebookUpdateRequest) -> dict:
    try:
        return get_projects().write_notebook(project_id, request.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/files/{file_path:path}")
def get_project_file(project_id: str, file_path: str) -> dict:
    try:
        return get_projects().read_text_file(project_id, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/projects/{project_id}/files/{file_path:path}")
def put_project_file(project_id: str, file_path: str, request: ProjectFileUpdateRequest) -> dict:
    try:
        return get_projects().write_text_file(project_id, file_path, request.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/runs")
def list_project_runs(project_id: str, limit: int = Query(50, ge=1, le=200)) -> dict:
    try:
        return {"runs": get_projects().list_runs(project_id, limit=limit)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/codex/run")
def run_project_codex(project_id: str, request: CodexRunRequest) -> dict:
    projects = get_projects()
    run_record: dict[str, Any] | None = None
    try:
        project_path = projects.project_path(project_id)
        run_record = projects.save_run(project_id, {
            "kind": "codex",
            "status": "running",
            "prompt": request.prompt,
            "reasoning_effort": request.reasoning_effort,
            "model": request.model,
        })
        result = get_codex().run(
            project_path=project_path,
            prompt=request.prompt,
            thread_id=projects.codex_thread_id(project_id),
            model=request.model,
            reasoning_effort=request.reasoning_effort,
        )
        projects.save_codex_state(
            project_id,
            thread_id=str(result["threadId"]),
            last_response=str(result.get("finalResponse") or ""),
        )
        completed_run = projects.save_run(project_id, {
            **run_record,
            "status": "completed",
            "thread_id": str(result["threadId"]),
            "response": str(result.get("finalResponse") or "")[-50_000:],
            "usage": result.get("usage"),
        })
        return {**result, "run": completed_run}
    except ValueError as exc:
        if run_record:
            projects.save_run(project_id, {**run_record, "status": "failed", "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        if run_record:
            projects.save_run(project_id, {**run_record, "status": "failed", "error": str(exc)[-4000:]})
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/sessions", response_model=SessionListResponse)
def list_sessions() -> dict:
    return {"sessions": get_sessions().list_sessions()}


@app.post("/sessions")
def create_session(request: SessionCreateRequest) -> dict:
    return get_sessions().create_session(title=request.title, context=request.context)


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    session = get_sessions().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


@app.patch("/sessions/{session_id}")
def patch_session(session_id: str, request: SessionPatchRequest) -> dict:
    patch = request.model_dump(exclude_none=True)
    session = get_sessions().update_session(session_id, patch)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    if get_sessions().delete_session(session_id):
        return {"status": "deleted", "session_id": session_id}
    raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")


@app.patch("/settings", response_model=SettingsResponse)
def patch_runtime_settings(request: SettingsPatchRequest) -> dict:
    current = get_settings().model_dump(mode="json")
    _deep_merge(current, request.model_dump(exclude_none=True))
    settings = CatalystSettings.model_validate(current)
    save_settings(_repo_root(), settings)
    get_settings.cache_clear()
    clear_read_caches()
    settings = get_settings()
    return {
        "settings": settings.model_dump(mode="json"),
        "provider_status": configured_provider_status(settings),
        "research_sources": research_source_status(settings),
    }


@app.post("/candidate-sets", response_model=FlexibleResponse)
def create_candidate_set(request: CandidateSetCreateRequest) -> dict:
    return get_candidate_sets().create_set(
        session_id=request.session_id,
        title=request.title,
        candidates=request.candidates,
        requirement=request.requirement,
    )


@app.get("/candidate-sets/{candidate_set_id}", response_model=FlexibleResponse)
def get_candidate_set(candidate_set_id: str) -> dict:
    candidate_set = get_candidate_sets().get_set(candidate_set_id)
    if not candidate_set:
        raise HTTPException(status_code=404, detail=f"Candidate set not found: {candidate_set_id}")
    return candidate_set


@app.patch("/candidate-sets/{candidate_set_id}", response_model=FlexibleResponse)
def patch_candidate_set(candidate_set_id: str, request: CandidateSetPatchRequest) -> dict:
    candidate_set = get_candidate_sets().update_set(candidate_set_id, request.model_dump(exclude_none=True))
    if not candidate_set:
        raise HTTPException(status_code=404, detail=f"Candidate set not found: {candidate_set_id}")
    return candidate_set


@app.get("/agent/tools", response_model=AgentToolCatalogResponse)
def get_agent_tool_catalog() -> dict:
    return tool_catalog(get_settings())


@app.get("/agent/demo-scenarios", response_model=FlexibleResponse)
def get_agent_demo_scenarios() -> dict:
    """Readiness metadata only; triggers remain intentionally hidden from the response."""
    return {"scenarios": scenario_catalog()}


@app.post("/agent/chat", response_model=AgentChatResponse)
def agent_chat(request: AgentChatRequest) -> dict:
    session_id = request.session_id
    if not session_id:
        session_id = get_sessions().create_session(context=request.current_workspace or {})["session_id"]
    return get_agent_tools().local_chat(
        session_id=session_id,
        message=request.message,
        current_workspace=request.current_workspace,
        attachments=request.attachments,
    )


@app.post("/agent/chat/stream")
def agent_chat_stream(request: AgentChatRequest):
    """SSE stream: status / token / done / error events for live agent UX."""
    session_id = request.session_id
    if not session_id:
        session_id = get_sessions().create_session(context=request.current_workspace or {})["session_id"]

    def event_gen():
        try:
            for event in get_agent_tools().local_chat_stream(
                session_id=session_id,
                message=request.message,
                current_workspace=request.current_workspace,
                attachments=request.attachments,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/agent/actions/{action_id}/confirm")
def confirm_agent_action(action_id: str) -> dict:
    return {"action_id": action_id, "status": "acknowledged"}


@app.websocket("/voice/live")
async def voice_live(websocket: WebSocket) -> None:
    await catalyst_voice_live(websocket, get_agent_tools())


@app.get("/research/status", response_model=ResearchStatusResponse)
def get_research_status() -> dict:
    return research_status(get_settings())


@app.post("/research/query", response_model=ResearchQueryResponse)
def research_query(request: ResearchQueryRequest) -> dict:
    tools = get_agent_tools()
    run = tools.start_research(
        {
            "query": request.query,
            "session_id": request.session_id,
            "sources": request.sources,
            **(request.context or {}),
        }
    )
    return {"run_id": run["run_id"], "status": run["status"], "message": run["message"]}


@app.get("/research/runs/{run_id}", response_model=FlexibleResponse)
def get_research_run(run_id: str) -> dict:
    run = get_research_store().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Research run not found: {run_id}")
    return run


@app.post("/research/ingest-url", response_model=FlexibleResponse)
def ingest_url(request: IngestUrlRequest) -> dict:
    settings = get_settings()
    if not settings.research.enabled or not settings.research.allow_url_ingest:
        return get_research_store().ingest_url_disabled(
            request.url,
            request.session_id,
            "Research URL ingestion is not enabled in this local build.",
        )
    return get_research_store().ingest_url(request.url, request.session_id, request.purpose)


@app.post("/research/ingest-pdf", response_model=FlexibleResponse)
def ingest_pdf(request: IngestPdfRequest) -> dict:
    settings = get_settings()
    if not settings.research.enabled or not settings.research.allow_pdf_ingest:
        return {
            "file_ref": request.file_ref,
            "session_id": request.session_id,
            "status": "disabled",
            "message": "Research PDF ingestion is not enabled in this local build.",
        }
    return {
        "file_ref": request.file_ref,
        "session_id": request.session_id,
        "status": "queued",
        "message": "PDF ingestion scaffold is present; extraction implementation is pending.",
    }


@app.post("/research/candidates/{candidate_id}/promote", response_model=FlexibleResponse)
def promote_research_candidate(candidate_id: str) -> dict:
    candidate = get_research_store().get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Research candidate not found: {candidate_id}")
    return {
        "candidate_id": candidate_id,
        "status": "promoted",
        "namespace": "external_research",
        "node": {
            "id": candidate_id,
            "type": "material",
            "namespace": "external_research",
            "label": candidate.get("formula") or candidate.get("material_name"),
        },
    }


@app.get("/search", response_model=SearchResponse)
def search(
    query: str = Query("", max_length=100),
    limit: int = Query(25, ge=1, le=100),
    elements: Annotated[str | None, Query(description="Comma-separated element symbols")] = None,
    chemsys: str | None = None,
    stable: bool | None = None,
    metal: bool | None = None,
    magnetic: bool | None = None,
    band_gap_min: float | None = None,
    band_gap_max: float | None = None,
    density_min: float | None = None,
    density_max: float | None = None,
    evidence: str | None = None,
    include_research: bool = False,
) -> dict:
    return {
        "query": query,
        "filters": {
            "elements": _split_csv(elements),
            "chemsys": chemsys,
            "stable": stable,
            "metal": metal,
            "magnetic": magnetic,
            "band_gap_min": band_gap_min,
            "band_gap_max": band_gap_max,
            "density_min": density_min,
            "density_max": density_max,
            "evidence": evidence,
            "include_research": include_research,
        },
        "results": get_store().search(
            query,
            limit=limit,
            elements=_split_csv(elements),
            chemsys=chemsys,
            stable=stable,
            metal=metal,
            magnetic=magnetic,
            band_gap_min=band_gap_min,
            band_gap_max=band_gap_max,
            density_min=density_min,
            density_max=density_max,
            evidence=evidence,
        ),
    }


mount_frontend_if_present()


@app.get("/{path:path}", include_in_schema=False)
def frontend_app(path: str) -> FileResponse:
    dist = _frontend_dist()
    index = dist / "index.html"
    requested = (dist / path).resolve()
    try:
        requested.relative_to(dist.resolve())
    except ValueError:
        requested = index
    if requested.is_file():
        return FileResponse(requested)
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend build not found. Run npm run build --prefix code/frontend.")


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("CATALYST_API_PORT", "8766"))
    uvicorn.run("catalyst.local_api:app", host="127.0.0.1", port=port, reload=False)
