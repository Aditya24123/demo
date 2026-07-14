from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from catalyst.providers.registry import DEFAULT_MODELS, provider_base_url
from catalyst.settings import CatalystSettings, provider_env_key


class OpenAICompatibleProviderError(RuntimeError):
    pass


def _openai_messages(prompt: str, system_instruction: str | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    return messages


def _openai_request_context(settings: CatalystSettings, provider: str) -> tuple[str, str, str | None]:
    base_url = provider_base_url(settings, provider)
    if not base_url:
        raise OpenAICompatibleProviderError(f"No OpenAI-compatible base URL configured for {provider}")
    env_key = provider_env_key(settings, provider)
    api_key = os.getenv(env_key) if env_key else None
    if provider == "micro" and not api_key:
        api_key = os.getenv("SPACEXAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    # Ollama and some open micro gateways work without a key.
    if provider not in {"ollama", "micro"} and not api_key:
        raise OpenAICompatibleProviderError(f"Missing environment variable: {env_key or 'provider API key'}")
    if provider == "micro" and not api_key:
        api_key = "not-needed"
    model = settings.providers.models.get(provider) or DEFAULT_MODELS.get(provider)
    if not model:
        raise OpenAICompatibleProviderError(f"No model configured for {provider}")
    return base_url, model, api_key


def generate_openai_compatible_text(
    settings: CatalystSettings,
    *,
    provider: str,
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
) -> dict[str, Any]:
    base_url, model, api_key = _openai_request_context(settings, provider)
    payload = {
        "model": model,
        "messages": _openai_messages(prompt, system_instruction),
        "temperature": temperature,
        "max_tokens": max_output_tokens,
        # Some OpenAI-compatible gateways (e.g. micro) default to SSE unless stream=false.
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-4000:]
        raise OpenAICompatibleProviderError(f"{provider} returned HTTP {exc.code}: {detail}") from exc
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OpenAICompatibleProviderError(f"{provider} request failed: {exc}") from exc

    choices = data.get("choices") or []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    text = str((message or {}).get("content") or "").strip()
    if not text:
        raise OpenAICompatibleProviderError(f"{provider} returned no text content")
    return {
        "provider": provider,
        "model": data.get("model") or model,
        "text": text,
        "usage": data.get("usage") or {},
    }


def stream_openai_compatible_text(
    settings: CatalystSettings,
    *,
    provider: str,
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
):
    """Yield text deltas from an OpenAI-compatible SSE chat completion."""
    base_url, model, api_key = _openai_request_context(settings, provider)
    payload = {
        "model": model,
        "messages": _openai_messages(prompt, system_instruction),
        "temperature": temperature,
        "max_tokens": max_output_tokens,
        "stream": True,
    }
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=120) as response:
            while True:
                raw = response.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices or not isinstance(choices[0], dict):
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    yield str(piece)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-4000:]
        raise OpenAICompatibleProviderError(f"{provider} returned HTTP {exc.code}: {detail}") from exc
    except (error.URLError, TimeoutError) as exc:
        raise OpenAICompatibleProviderError(f"{provider} stream failed: {exc}") from exc
