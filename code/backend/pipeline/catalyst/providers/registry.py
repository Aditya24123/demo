from __future__ import annotations

import os
from typing import Any

from catalyst.providers.base import ProviderCapabilities
from catalyst.settings import CatalystSettings, provider_env_key


DEFAULT_MODELS = {
    # Antigravity / AGY profiles first. Direct Gemini API ids also valid.
    "gemini": "agy/3.5-flash-medium",
    "groq": "llama-3.3-70b-versatile",
    "mistral": "mistral-large-latest",
    "nvidia": "meta/llama-3.1-405b-instruct",
    "ollama": "llama3.1",
    "ollama_cloud": "gpt-oss:120b",
    # Optional OpenAI-compatible micro gateway (not demo default; no Minimax/Omni routing).
    "micro": "auto/best-chat",
}

# Optional micro gateway labels only ? never injected into Gemini picker.
MICRO_MODEL_COMBOS = (
    "auto/best-chat",
    "auto/best-reasoning",
    "auto/best-fast",
    "auto/best-coding",
)


OPENAI_COMPATIBLE_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "ollama_cloud": "https://ollama.com/v1",
    # Override via settings.providers.base_urls.micro or MICRO_BASE_URL.
}


def provider_capabilities(settings: CatalystSettings) -> list[ProviderCapabilities]:
    capabilities = []
    for provider in settings.providers.provider_order:
        env_key = provider_env_key(settings, provider)
        base = provider_base_url(settings, provider)
        if provider == "ollama":
            configured = True
        elif provider == "micro":
            # Self-host: need base URL; key optional if gateway is open/local.
            configured = bool(base)
        else:
            configured = bool(env_key and os.getenv(env_key))
        model = settings.providers.models.get(provider) or DEFAULT_MODELS.get(provider)
        capabilities.append(
            ProviderCapabilities(
                provider=provider,
                configured=configured,
                model=model,
                # ollama uses the JSON tool loop (not native function calling) via OpenAI-compat.
                supports_tools=provider in {"gemini", "groq", "mistral", "nvidia", "ollama_cloud", "ollama", "micro"},
                supports_streaming=True,
                supports_json_schema=provider in {"gemini", "groq", "mistral", "nvidia", "ollama_cloud", "ollama", "micro"},
                supports_images=provider in {"gemini"},
                base_url=base,
            )
        )
    return capabilities


def resolve_active_provider(settings: CatalystSettings) -> str | None:
    """Return the configured active provider, or the first available one.

    Settings often leave ``active_provider`` null; status UIs already fall back,
    but the agent loop must resolve the same way or it never runs.
    """
    caps = provider_capabilities(settings)
    by_name = {cap.provider: cap for cap in caps}
    active = (settings.providers.active_provider or "").strip() or None
    if active and active in by_name and by_name[active].configured:
        return active
    for cap in caps:
        if cap.configured:
            return cap.provider
    return None


def provider_status(settings: CatalystSettings) -> dict[str, Any]:
    caps = provider_capabilities(settings)
    active = resolve_active_provider(settings)
    active_capability = next((cap for cap in caps if cap.provider == active), None)
    return {
        "active_provider": active,
        "llm_configured": bool(active_capability and active_capability.configured),
        "providers": {cap.provider: cap.__dict__ for cap in caps},
    }


def provider_base_url(settings: CatalystSettings, provider: str) -> str | None:
    configured = str(settings.providers.base_urls.get(provider) or "").strip().rstrip("/")
    if configured:
        return configured
    if provider == "ollama":
        # OpenAI-compatible surface is /v1; raw Ollama API is :11434 without /v1.
        raw = (os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434/v1").strip().rstrip("/")
        if raw.endswith("/v1"):
            return raw
        return f"{raw}/v1"
    if provider == "micro":
        return (
            os.getenv("MICRO_BASE_URL")
            or os.getenv("SPACEXAI_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or ""
        ).strip().rstrip("/") or None
    return OPENAI_COMPATIBLE_BASE_URLS.get(provider)
