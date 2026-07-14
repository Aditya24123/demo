from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib import error, parse, request

from catalyst.settings import CatalystSettings


SERVICE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class ModelServiceRunner:
    """Execute preconfigured scientific inference services without agent-controlled URLs."""

    def __init__(self, settings: CatalystSettings) -> None:
        self.settings = settings

    def list_services(self) -> list[dict[str, Any]]:
        return [
            {
                "service_id": service_id,
                "task": service.task,
                "model": service.model,
                "endpoint": service.endpoint,
                "enabled": service.enabled,
                "configured": service.enabled and (not service.api_key_env or bool(os.getenv(service.api_key_env))),
            }
            for service_id, service in sorted(self.settings.model_services.items())
        ]

    def run(self, service_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        if not SERVICE_ID_PATTERN.fullmatch(str(service_id or "")):
            raise ValueError("invalid model service id")
        service = self.settings.model_services.get(service_id)
        if service is None:
            raise ValueError(f"Unknown model service: {service_id}")
        if not service.enabled:
            raise ValueError(f"Model service is disabled: {service_id}")
        parsed = parse.urlparse(service.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("model service endpoint must be an absolute HTTP(S) URL")
        api_key = os.getenv(service.api_key_env) if service.api_key_env else None
        if service.api_key_env and not api_key:
            raise ValueError(f"Missing environment variable: {service.api_key_env}")
        body = json.dumps({"model": service.model, "task": service.task, "inputs": inputs}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = request.Request(service.endpoint, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=service.timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[-4000:]
            raise RuntimeError(f"Model service returned HTTP {exc.code}: {detail}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Model service request failed: {exc}") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("Model service response exceeded 5 MB")
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Model service returned invalid JSON") from exc
        return {
            "ok": True,
            "service_id": service_id,
            "task": service.task,
            "model": service.model,
            "result": result,
        }
