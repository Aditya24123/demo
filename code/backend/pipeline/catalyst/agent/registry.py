"""Canonical tool registry ? single source for model schemas, API catalog, and docs.

``tools_decl.TOOL_DECLARATIONS`` remains the raw schema list (Gemini-style).
Everything else is derived here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from catalyst.agent.tools_decl import MODEL_TOOL_DECLARATIONS, TOOL_DECLARATIONS


def all_tool_declarations() -> list[dict[str, Any]]:
    return list(TOOL_DECLARATIONS)


def tool_names() -> list[str]:
    return [str(t.get("name")) for t in TOOL_DECLARATIONS if t.get("name")]


def gemini_function_declarations() -> list[dict[str, Any]]:
    """Native Gemini functionDeclarations payload."""
    return list(MODEL_TOOL_DECLARATIONS)


def openai_tools_schema() -> list[dict[str, Any]]:
    """OpenAI-compatible tools array for gateways that support tool calling."""
    tools: list[dict[str, Any]] = []
    for decl in MODEL_TOOL_DECLARATIONS:
        name = decl.get("name")
        if not name:
            continue
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": decl.get("description") or name,
                    "parameters": decl.get("parameters") or {"type": "object", "properties": {}},
                },
            }
        )
    return tools


def tools_markdown() -> str:
    lines = ["## Available Catalyst tools", ""]
    for decl in MODEL_TOOL_DECLARATIONS:
        name = decl.get("name") or "unknown"
        desc = decl.get("description") or ""
        params = decl.get("parameters") or {}
        lines.append(f"- `{name}`: {desc}")
        if params:
            lines.append(f"  - parameters: `{json.dumps(params, sort_keys=True)}`")
    lines.extend(
        [
            "",
            "To call a tool in Codex-core mode, emit exactly one line:",
            '`TOOL_CALL: {"name":"<tool>","args":{...}}`',
            "After tool results are provided, continue until you answer the user in markdown.",
        ]
    )
    return "\n".join(lines)


def api_tool_catalog(
    *,
    llm_configured: bool,
    active_provider: str | None,
    providers: dict[str, Any] | None = None,
    research: dict[str, Any] | None = None,
    research_sources: dict[str, Any] | None = None,
    mode: str = "codex_core_with_llm_fallback",
) -> dict[str, Any]:
    return {
        "agent_available": True,
        "llm_configured": llm_configured,
        "active_provider": active_provider,
        "mode": mode,
        "provider_configured": llm_configured,
        "tools": tool_names(),
        "tool_declarations": all_tool_declarations(),
        "providers": providers or {},
        "research": research or {},
        "research_sources": research_sources or {},
    }


def export_tool_registry_json(repo_root: Path) -> Path:
    """Write generated registry for human editing visibility (derived, not source)."""
    path = Path(repo_root) / "data" / "local" / "agent" / "tool_registry.generated.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "source": "catalyst.agent.tools_decl.TOOL_DECLARATIONS",
        "tools": [
            {
                "name": t.get("name"),
                "description": t.get("description"),
                "parameters": t.get("parameters"),
                "ui_safe": str(t.get("name") or "").startswith("select_") or "export" in str(t.get("name") or ""),
            }
            for t in TOOL_DECLARATIONS
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
