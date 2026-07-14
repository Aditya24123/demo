from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


LOCAL_DIRS = (
    "logs",
    "sessions",
    "candidate_sets",
    "research_candidates",
    "research_runs",
    "research_sources",
    "exports",
    "mp_cache",
)


class ProviderSettings(BaseModel):
    active_provider: str | None = None
    # Demo default: gemini / Antigravity only (other providers optional if configured).
    provider_order: list[str] = Field(default_factory=lambda: ["gemini"])
    models: dict[str, str] = Field(default_factory=dict)
    fallback_models: dict[str, list[str]] = Field(
        default_factory=lambda: {"gemini": ["gemini-3.1-flash-lite", "gemini-2.5-flash"]}
    )
    base_urls: dict[str, str] = Field(default_factory=dict)
    api_key_envs: dict[str, str] = Field(default_factory=dict)


class ResearchSettings(BaseModel):
    enabled: bool = False
    sources: list[str] = Field(
        default_factory=lambda: ["openalex", "semantic_scholar", "arxiv", "crossref", "pubmed", "web"]
    )
    allow_url_ingest: bool = True
    allow_pdf_ingest: bool = True


class SessionSettings(BaseModel):
    restore_last_session: bool = True
    persist_raw_messages: bool = True
    persist_tool_traces: bool = True
    hydrate_tool_traces_into_context: bool = False


class ModelServiceSettings(BaseModel):
    endpoint: str
    task: str
    model: str | None = None
    api_key_env: str | None = None
    enabled: bool = True
    timeout_seconds: int = Field(120, ge=5, le=900)


class RuntimeSettings(BaseModel):
    api_host: str = "127.0.0.1"
    api_port: int = 8766
    ui_host: str = "127.0.0.1"
    ui_port: int = 5173
    source_release: str = "v2025.09.25"


class CatalystSettings(BaseModel):
    version: int = 1
    product_name: str = "Catalyst"
    created_at: str | None = None
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    research: ResearchSettings = Field(default_factory=ResearchSettings)
    sessions: SessionSettings = Field(default_factory=SessionSettings)
    model_services: dict[str, ModelServiceSettings] = Field(default_factory=dict)


PROVIDER_ENV_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "ollama_cloud": "OLLAMA_API_KEY",
    "ollama": "",
    "micro": "MICRO_API_KEY",
}

RESEARCH_ENV_KEYS = {
    "openalex": "OPENALEX_API_KEY",
    "semantic_scholar": "SEMANTIC_SCHOLAR_API_KEY",
    "pubmed": "NCBI_API_KEY",
    "web": "GOOGLE_CUSTOM_SEARCH_API_KEY",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_root(repo_root: Path) -> Path:
    return repo_root / "data" / "local"


def settings_path(repo_root: Path) -> Path:
    return local_root(repo_root) / "settings.json"


def ensure_local_dirs(repo_root: Path) -> None:
    root = local_root(repo_root)
    root.mkdir(parents=True, exist_ok=True)
    for name in LOCAL_DIRS:
        (root / name).mkdir(parents=True, exist_ok=True)


def default_settings() -> CatalystSettings:
    return CatalystSettings(created_at=utc_now())


def load_settings(repo_root: Path, create: bool = True) -> CatalystSettings:
    ensure_local_dirs(repo_root)
    path = settings_path(repo_root)
    if not path.exists():
        settings = default_settings()
        if create:
            save_settings(repo_root, settings)
        return settings
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    settings = CatalystSettings.model_validate(data)
    env_release = os.getenv("CATALYST_SOURCE_RELEASE")
    if env_release:
        settings.runtime.source_release = env_release
    env_api_host = os.getenv("CATALYST_API_HOST")
    if env_api_host:
        settings.runtime.api_host = env_api_host
    env_api_port = os.getenv("CATALYST_API_PORT")
    if env_api_port:
        settings.runtime.api_port = int(env_api_port)
    env_ui_host = os.getenv("CATALYST_UI_HOST")
    if env_ui_host:
        settings.runtime.ui_host = env_ui_host
    env_ui_port = os.getenv("CATALYST_UI_PORT")
    if env_ui_port:
        settings.runtime.ui_port = int(env_ui_port)
    return settings


def save_settings(repo_root: Path, settings: CatalystSettings) -> None:
    ensure_local_dirs(repo_root)
    settings_path(repo_root).write_text(
        json.dumps(settings.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def resolve_active_provider_name(settings: CatalystSettings, statuses: dict[str, str] | None = None) -> str | None:
    """Prefer explicit active_provider; otherwise first available in provider_order."""
    active = (settings.providers.active_provider or "").strip() or None
    if active:
        return active
    if statuses is None:
        # Lightweight availability map (env keys only) ? used by settings status payloads.
        statuses = {}
        for provider in settings.providers.provider_order:
            env_key = provider_env_key(settings, provider)
            if provider == "ollama":
                statuses[provider] = "available"
            elif env_key and os.getenv(env_key):
                statuses[provider] = "available"
            else:
                statuses[provider] = "missing_key"
    return next((name for name, status in statuses.items() if status == "available"), None)


def configured_provider_status(settings: CatalystSettings) -> dict[str, Any]:
    statuses: dict[str, str] = {}
    for provider in settings.providers.provider_order:
        env_key = provider_env_key(settings, provider)
        if provider == "ollama":
            statuses[provider] = "available"
        elif env_key and os.getenv(env_key):
            statuses[provider] = "available"
        else:
            statuses[provider] = "missing_key"
    active = resolve_active_provider_name(settings, statuses)
    return {
        "llm_configured": active is not None,
        "active_provider": active,
        "providers": statuses,
    }


def provider_env_key(settings: CatalystSettings, provider: str) -> str:
    configured = str(settings.providers.api_key_envs.get(provider) or "").strip()
    return configured or PROVIDER_ENV_KEYS.get(provider, "")


def research_source_status(settings: CatalystSettings) -> dict[str, str]:
    statuses: dict[str, str] = {}
    if not settings.research.enabled:
        return {source: "disabled" for source in settings.research.sources}
    for source in settings.research.sources:
        env_key = RESEARCH_ENV_KEYS.get(source)
        if source in {"arxiv", "crossref"}:
            statuses[source] = "available"
        elif source == "web":
            cx = os.getenv("GOOGLE_CUSTOM_SEARCH_CX")
            statuses[source] = "available" if env_key and os.getenv(env_key) and cx else "missing_key"
        elif env_key and os.getenv(env_key):
            statuses[source] = "available"
        elif env_key:
            statuses[source] = "missing_key"
        else:
            statuses[source] = "not_configured"
    return statuses


def settings_schema() -> dict[str, Any]:
    return CatalystSettings.model_json_schema()
