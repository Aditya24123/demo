"""Smoke: OAuth AGY primary + tool protocol parse."""
from __future__ import annotations

import json
import os
import sys
import urllib.request

# Ensure local imports for unit bits
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code", "backend", "pipeline"))

from catalyst.agent.agy_cli_transport import (  # noqa: E402
    agy_cli_available,
    parse_tool_calls,
    resolve_agy_model,
)


def unit_parse() -> None:
    sample = """
Looking up...
TOOL_CALL: {"name":"resolve_material","args":{"query":"CdS"}}
TOOL_CALL: {"name":"get_neighborhood","args":{"material_id":"mp-zw","depth":2}}
Done.
"""
    calls = parse_tool_calls(sample, allowed={"resolve_material", "get_neighborhood", "select_material"})
    assert len(calls) == 2, calls
    assert calls[0]["name"] == "resolve_material"
    print("parse_ok", calls)


def chat_smoke() -> None:
    base = "http://127.0.0.1:8766"
    payload = {
        "message": "What material is currently open? Reply with only id and formula.",
        "current_workspace": {
            "agent_model_profile": "agy/3.5-flash-medium",
            "agent_effort": "low",
            "current_material_id": "mp-zw",
            "formula_pretty": "CdS",
        },
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base}/agent/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as r:
        body = json.loads(r.read().decode())
    am = body.get("assistant_message") or {}
    text = am.get("text") or ""
    cites = am.get("citations") or []
    print("text", text[:300])
    print("citations", cites[:3])
    # Transport often lives in citation provider metadata
    print("agy_cli_available", agy_cli_available())
    print("model", resolve_agy_model("agy/3.5-flash-medium", "low"))


if __name__ == "__main__":
    unit_parse()
    chat_smoke()
