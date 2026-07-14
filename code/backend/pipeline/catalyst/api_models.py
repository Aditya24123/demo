from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

class SubgraphExportRequest(BaseModel):
    material_ids: list[str] = Field(default_factory=list)
    include_evidence: bool = True
    include_edge_details: bool = False
    format: str = "json"


class ScreenRequest(BaseModel):
    requirement: str
    context: dict[str, Any] | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class CompareRequest(BaseModel):
    material_ids: list[str] = Field(default_factory=list)
    include_evidence: bool = True
    include_edges: bool = True


class CandidateSetCreateRequest(BaseModel):
    session_id: str | None = None
    title: str | None = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    requirement: str | None = None


class CandidateSetPatchRequest(BaseModel):
    title: str | None = None
    session_id: str | None = None
    candidates: list[dict[str, Any]] | None = None
    requirement: str | None = None


class CandidateExportRequest(BaseModel):
    candidate_set_id: str | None = None
    material_ids: list[str] | None = None
    format: str = Field("json", pattern="^(json|csv)$")


class SessionCreateRequest(BaseModel):
    title: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class SessionPatchRequest(BaseModel):
    title: str | None = None
    context: dict[str, Any] | None = None
    summary: str | None = None


class ProjectCreateRequest(BaseModel):
    name: str
    project_id: str | None = None
    description: str | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class NotebookUpdateRequest(BaseModel):
    content: str


class ProjectFileUpdateRequest(BaseModel):
    content: str


class CodexRunRequest(BaseModel):
    prompt: str
    model: str | None = None
    reasoning_effort: str = Field("high", pattern="^(minimal|low|medium|high|xhigh)$")


class AgentChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    current_workspace: dict[str, Any] | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    stream: bool = False


class SettingsPatchRequest(BaseModel):
    runtime: dict[str, Any] | None = None
    providers: dict[str, Any] | None = None
    research: dict[str, Any] | None = None
    sessions: dict[str, Any] | None = None
    model_services: dict[str, Any] | None = None


class ResearchQueryRequest(BaseModel):
    session_id: str | None = None
    query: str
    context: dict[str, Any] = Field(default_factory=dict)
    sources: list[str] | None = None


class IngestUrlRequest(BaseModel):
    session_id: str | None = None
    url: str
    purpose: str | None = None


class IngestPdfRequest(BaseModel):
    session_id: str | None = None
    file_ref: str
    purpose: str | None = None


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


