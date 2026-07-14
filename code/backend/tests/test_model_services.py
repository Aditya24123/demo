from __future__ import annotations

import json

import pytest

from catalyst.model_services import ModelServiceRunner
from catalyst.settings import CatalystSettings


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit: int) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _settings() -> CatalystSettings:
    return CatalystSettings.model_validate({
        "model_services": {
            "protein-fold": {
                "endpoint": "https://models.example/predict",
                "task": "protein-structure-prediction",
                "model": "fold-v1",
                "api_key_env": "MODEL_API_KEY",
                "timeout_seconds": 45,
            }
        }
    })


def test_model_service_run_is_preconfigured_and_authenticated(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "test-secret")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["authorization"] = req.headers.get("Authorization")
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _Response({"confidence": 0.94, "artifact": "prediction.pdb"})

    monkeypatch.setattr("catalyst.model_services.request.urlopen", fake_urlopen)
    runner = ModelServiceRunner(_settings())

    assert runner.list_services()[0]["configured"] is True
    result = runner.run("protein-fold", {"sequence": "MSTN"})

    assert result["ok"] is True
    assert result["result"]["artifact"] == "prediction.pdb"
    assert captured == {
        "url": "https://models.example/predict",
        "authorization": "Bearer test-secret",
        "payload": {
            "model": "fold-v1",
            "task": "protein-structure-prediction",
            "inputs": {"sequence": "MSTN"},
        },
        "timeout": 45,
    }


def test_model_service_rejects_unknown_service() -> None:
    with pytest.raises(ValueError, match="Unknown model service"):
        ModelServiceRunner(_settings()).run("other-service", {})


def test_model_service_requires_configured_secret(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    runner = ModelServiceRunner(_settings())
    assert runner.list_services()[0]["configured"] is False
    with pytest.raises(ValueError, match="Missing environment variable"):
        runner.run("protein-fold", {"sequence": "MSTN"})
