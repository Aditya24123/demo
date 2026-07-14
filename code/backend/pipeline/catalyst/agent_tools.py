from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from catalyst.agent.registry import api_tool_catalog, export_tool_registry_json
from catalyst.agent_tools_chat import AgentToolsChatMixin
from catalyst.agent_tools_common import ELEMENT_SYMBOLS
from catalyst.agent_tools_materials import AgentToolsMaterialsMixin
from catalyst.agent_tools_projects import AgentToolsProjectsMixin
from catalyst.providers import provider_status
from catalyst.research_sources import research_sources_payload
from catalyst.settings import CatalystSettings, research_source_status


def tool_catalog(settings: CatalystSettings) -> dict[str, Any]:
    """API catalog derived from the canonical tool registry (Phase 2)."""
    status = provider_status(settings)
    try:
        repo = Path(os.environ.get("CATALYST_REPO_ROOT") or Path.cwd())
        export_tool_registry_json(repo)
    except Exception:
        pass
    return api_tool_catalog(
        llm_configured=bool(status.get("llm_configured")),
        active_provider=status.get("active_provider"),
        providers=status.get("providers") or {},
        research=research_sources_payload(settings),
        research_sources=research_source_status(settings),
        mode="antigravity_with_llm_fallback",
    )


class CatalystAgentTools(AgentToolsMaterialsMixin, AgentToolsProjectsMixin, AgentToolsChatMixin):
    """Local agent tool surface for materials + project + chat."""

def _extract_material_id(text: str) -> str | None:
    match = re.search(r"\bmp-[a-z0-9-]+\b", text, re.IGNORECASE)
    return match.group(0) if match else None


def _extract_formula_like_tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9]{1,31}\b", text)
    candidates: list[str] = []
    for token in raw_tokens:
        if _is_formula_like_token(token):
            candidates.append(token)
    return candidates


def _is_formula_like_token(token: str) -> bool:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,31}", token):
        return False
    index = 0
    groups = 0
    has_digit = any(char.isdigit() for char in token)
    while index < len(token):
        if not token[index].isalpha():
            return False
        matched = None
        for width in (2, 1):
            part = token[index : index + width]
            if len(part) != width or not part.isalpha():
                continue
            symbol = part[0].upper() + part[1:].lower()
            if symbol in ELEMENT_SYMBOLS:
                matched = symbol
                index += width
                break
        if not matched:
            return False
        while index < len(token) and token[index].isdigit():
            index += 1
        groups += 1
    return groups >= 2 or has_digit
