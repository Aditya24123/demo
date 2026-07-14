from __future__ import annotations

import json

from catalyst.providers.openai_compatible import generate_openai_compatible_text
from catalyst.providers.registry import provider_status
from catalyst.settings import CatalystSettings


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps({
            "model": "science-model",
            "choices": [{"message": {"content": "grounded response"}}],
            "usage": {"total_tokens": 12},
        }).encode("utf-8")


def test_custom_openai_compatible_provider(monkeypatch) -> None:
    monkeypatch.setenv("SCIENCE_API_KEY", "test-key")
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["authorization"] = req.headers.get("Authorization")
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("catalyst.providers.openai_compatible.request.urlopen", fake_urlopen)
    settings = CatalystSettings.model_validate({
        "providers": {
            "active_provider": "science",
            "provider_order": ["science"],
            "models": {"science": "science-model"},
            "base_urls": {"science": "https://science.example/v1/"},
            "api_key_envs": {"science": "SCIENCE_API_KEY"},
        }
    })

    status = provider_status(settings)
    assert status["active_provider"] == "science"
    assert status["llm_configured"] is True
    result = generate_openai_compatible_text(
        settings,
        provider="science",
        prompt="Inspect a candidate",
        system_instruction="Use tools for facts.",
    )
    assert result["text"] == "grounded response"
    assert captured == {
        "url": "https://science.example/v1/chat/completions",
        "authorization": "Bearer test-key",
        "timeout": 90,
    }
