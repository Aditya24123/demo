from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from catalyst.session_store import compact_session_context

def _dynamic_context(session: dict[str, Any], current_workspace: dict[str, Any] | None) -> dict[str, Any]:
    workspace = dict(current_workspace or {})
    surface = str(workspace.get("agent_surface") or "").strip().lower()
    if surface not in {"materials", "project", "genes"}:
        # Infer from rail_mode / project presence for older clients.
        rail = str(workspace.get("rail_mode") or "").strip().lower()
        if rail == "genes":
            surface = "genes"
        elif rail == "notebook" or workspace.get("project_id"):
            surface = "project"
        else:
            surface = "materials"
        workspace["agent_surface"] = surface

    live_material_id = str(
        workspace.get("material_id")
        or workspace.get("resolved_material_id")
        or workspace.get("current_material_id")
        or ""
    ).strip()
    live_formula = str(workspace.get("formula_pretty") or workspace.get("title") or "").strip()
    live_chemsys = str(workspace.get("chemsys") or workspace.get("subtitle") or "").strip()

    # Explicit live viewport block ? must beat stale chat/session memory.
    live_viewport = {
        "material_id": live_material_id or None,
        "formula_pretty": live_formula or None,
        "chemsys": live_chemsys or None,
        "workspace_tab": workspace.get("workspace_tab"),
        "hop_depth": workspace.get("hop_depth"),
        "project_id": workspace.get("project_id"),
        "project_name": workspace.get("project_name"),
        "agent_surface": surface,
        "genomics_case_id": workspace.get("genomics_case_id"),
        "genomics_variant_index": workspace.get("genomics_variant_index"),
        "genomics_repeat_count": workspace.get("genomics_repeat_count"),
        "genome": {
            "gene": workspace.get("genomics_case_id") or "BRCA1",
            "visible_start": workspace.get("genome_visible_start"),
            "visible_end": workspace.get("genome_visible_end"),
            "selected_position": workspace.get("genome_selected_position"),
            "visible_sequence": workspace.get("genome_sequence"),
            "total_gene_length": workspace.get("genome_total_length"),
            "selected_variant": workspace.get("genome_selected_variant"),
        },
    }

    if surface == "genes":
        case_id = str(workspace.get("genomics_case_id") or "brca1")
        marker = workspace.get("genomics_variant_index")
        repeat = workspace.get("genomics_repeat_count")
        mode_guidance = (
            f"You are in GENES demo mode. LIVE VIEWPORT: {case_id} case, marker {marker}. "
            + (f"CTG repeat count is {repeat}. " if repeat is not None else "")
            + "Answer from live_viewport.genome (only its visible_sequence is available). Use control_genome_view "
            "for structured highlight, zoom, and show-sequence UI actions; use inspect_genomics_case for facts. "
            "This is educational, not a complete gene, diagnosis, or clinical advice."
        )
    elif surface == "materials":
        if live_material_id:
            mode_guidance = (
                f"You are in MATERIALS mode. LIVE VIEWPORT (authoritative right now): "
                f"{live_formula or 'material'} ({live_material_id})"
                + (f", chemsys {live_chemsys}" if live_chemsys else "")
                + ". Chat history may mention OTHER materials ? do NOT say the user is 'looking at' a past "
                "material. For this/it/current/open material, use the LIVE VIEWPORT id. "
                "Prefer material search, workspace, structure, neighborhood, screening, compare, and select_material."
            )
        else:
            mode_guidance = (
                "You are in MATERIALS mode. No material is open in the live viewport. "
                "Do not invent a current material from chat history. Prefer search/resolve first."
            )
    else:
        mode_guidance = (
            "You are in PROJECT mode. Prefer list_project_files, read/write_project_file, "
            "read/update_project_notebook, list_project_runs, and run_workspace_agent. "
            "Use the current project_id for project tools when the user omits it. "
            "You may still use materials tools when the user asks about a material in this project. "
            "If a live material_id is present, treat that as the open material ? not older chat mentions."
        )

    return {
        "agent_surface": surface,
        "mode_guidance": mode_guidance,
        "live_viewport": live_viewport,
        "current_workspace": workspace,
        "session": compact_session_context(session),
        "recent_messages": session.get("messages", [])[-12:],
        "tool_traces": session.get("tool_traces", [])[-12:],
    }


def _session_contents(session: dict[str, Any] | None, *, limit: int = 20) -> list[dict[str, Any]]:
    if not session:
        return []
    contents: list[dict[str, Any]] = []
    summary = str(session.get("summary") or "").strip()
    if summary:
        contents.append({"role": "user", "parts": [{"text": f"Prior session summary:\n{summary}"}]})
    for message in session.get("messages", [])[-limit:]:
        role = "model" if message.get("role") == "assistant" else "user"
        text = str(message.get("content") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    return contents


def _gemini_attachment_parts(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Image (and optional audio) inline parts for Gemini multimodal turns."""
    parts: list[dict[str, Any]] = []
    for attachment in attachments[:4]:
        mime_type = str(attachment.get("mime_type") or "").strip().lower()
        data = str(attachment.get("data") or "").strip()
        if not data or len(data) > 12_000_000:
            continue
        # Images for vision; short audio clips for multimodal (dictation still preferred in UI).
        if mime_type.startswith("image/") or mime_type.startswith("audio/"):
            parts.append({"inlineData": {"mimeType": mime_type, "data": data}})
    return parts


def _recent_session_text(session: dict[str, Any] | None, *, limit: int = 12) -> str:
    if not session:
        return ""
    lines = []
    if session.get("summary"):
        lines.append(f"summary: {session['summary']}")
    for message in session.get("messages", [])[-limit:]:
        lines.append(f"{message.get('role')}: {str(message.get('content') or '')[:800]}")
    return "\n".join(lines)


def _resolve_arg_material(controller: Any, value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    workspace = controller.store.workspace(text)
    if workspace:
        return workspace.get("resolved_material_id") or text
    return controller._resolve_material_reference(text) or text


def _capture_material_result(controller: Any, session_id: str, workspace: dict[str, Any], aggregate: dict[str, Any]) -> None:
    material_id = workspace.get("resolved_material_id") or workspace.get("material_id")
    if material_id:
        aggregate["citations"].append({"type": "local_material", "material_id": material_id})
        _update_material_context(controller, session_id, material_id, "material_workspace")


def _update_material_context(controller: Any, session_id: str, material_id: str, mode: str) -> None:
    controller.sessions.update_session(
        session_id,
        {
            "context": {
                "last_focus_material_id": material_id,
                "last_referenced_material_id": material_id,
                "current_material_id": material_id,
                "last_focus_mode": mode,
            }
        },
    )


def _material_focus_ui_actions(material_id: str, *, open_inspector: bool = True) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = [
        {"type": "select_node", "material_id": material_id},
        {"type": "highlight_node", "material_id": material_id, "duration_ms": 6500},
        {"type": "zoom_to_node", "material_id": material_id, "scale": 2.6},
    ]
    if open_inspector:
        actions.append({"type": "open_inspector", "material_id": material_id})
    return actions


def _open_material_action(material_id: str, label: str) -> dict[str, Any]:
    return {"id": "open_material", "type": "open_material", "label": label, "payload": {"material_id": material_id}}


def _empty_aggregate() -> dict[str, Any]:
    return {
        "actions": [],
        "ui_actions": [],
        "citations": [],
        "candidate_results": None,
        "tool_calls": [],
        "tool_results": [],
        "context_updates": {},
    }


def _compact_tool_result(result: Any) -> Any:
    if isinstance(result, dict):
        compact = {key: value for key, value in result.items() if key not in {"material", "graph"}}
        if "workspace" in compact and isinstance(compact["workspace"], dict):
            workspace = compact["workspace"]
            summary = dict(workspace.get("summary") or {})
            structure = workspace.get("structure") if isinstance(workspace.get("structure"), dict) else {}
            symmetry = structure.get("symmetry") if isinstance(structure.get("symmetry"), dict) else {}
            # Surface density + space group ? live under structure/symmetry, not summary.
            if structure.get("density") is not None:
                summary.setdefault("density", structure.get("density"))
            sg = symmetry.get("symbol") or symmetry.get("space_group_symbol") or symmetry.get("crystal_system")
            if sg:
                summary.setdefault("space_group", sg)
            if structure.get("volume") is not None:
                summary.setdefault("volume", structure.get("volume"))
            if structure.get("nsites") is not None:
                summary.setdefault("nsites", structure.get("nsites"))
            compact["workspace"] = {
                "material_id": workspace.get("material_id"),
                "resolved_material_id": workspace.get("resolved_material_id"),
                "summary": summary,
                "structure": {
                    "density": structure.get("density"),
                    "volume": structure.get("volume"),
                    "nsites": structure.get("nsites"),
                    "space_group": sg,
                    "symmetry": {
                        "symbol": symmetry.get("symbol"),
                        "space_group_symbol": symmetry.get("space_group_symbol"),
                        "crystal_system": symmetry.get("crystal_system"),
                        "number": symmetry.get("number"),
                    }
                    if symmetry
                    else None,
                },
                "relation_count": workspace.get("relation_count"),
            }
        if "structure" in compact and isinstance(compact["structure"], dict):
            structure = compact["structure"]
            compact["structure"] = {
                "material_id": structure.get("material_id"),
                "formula_pretty": structure.get("formula_pretty"),
                "lattice": structure.get("lattice"),
                "site_count": len(structure.get("sites") or []),
                "bond_count": len(structure.get("bonds") or []),
            }
        if "details" in compact and isinstance(compact["details"], dict):
            details = compact["details"]
            compact["details"] = {
                "material_id": details.get("material_id"),
                "summary": details.get("summary"),
                "property_groups": details.get("property_groups"),
                "sections": list(details.get("sections") or []),
            }
        if "candidate_set" in compact and isinstance(compact["candidate_set"], dict):
            candidate_set = compact["candidate_set"]
            compact["candidate_set"] = {
                "candidate_set_id": candidate_set.get("candidate_set_id"),
                "title": candidate_set.get("title"),
                "requirement": candidate_set.get("requirement"),
                "material_ids": [item.get("material_id") for item in (candidate_set.get("candidates") or [])[:20]],
            }
        if "runs" in compact and isinstance(compact["runs"], list):
            compact["runs"] = [
                {
                    "run_id": item.get("run_id"),
                    "kind": item.get("kind"),
                    "status": item.get("status"),
                    "prompt": str(item.get("prompt") or "")[:300],
                    "updated_at": item.get("updated_at"),
                }
                for item in compact["runs"][:20]
                if isinstance(item, dict)
            ]
        if "candidates" in compact and isinstance(compact["candidates"], list):
            compact["candidates"] = [
                {
                    "material_id": item.get("material_id"),
                    "formula_pretty": item.get("formula_pretty"),
                    "score": item.get("score"),
                    "matched": item.get("matched"),
                    "missing": item.get("missing"),
                    "penalties": item.get("penalties"),
                    "reason_summary": item.get("reason_summary"),
                    "is_metal": (item.get("material") or {}).get("is_metal"),
                }
                for item in compact["candidates"][:8]
                if isinstance(item, dict)
            ]
        for key in ("content", "response"):
            if isinstance(compact.get(key), str) and len(compact[key]) > 20_000:
                compact[key] = compact[key][:20_000] + "\n...[truncated]"
        if "result" in compact:
            serialized_result = json.dumps(compact["result"], default=str)
            if len(serialized_result) > 20_000:
                compact["result"] = serialized_result[:20_000] + "\n...[truncated]"
        return compact
    return result


def _tool_summary(name: str, result: Any) -> str:
    if isinstance(result, dict):
        if name == "screen_candidates":
            return f"{len(result.get('candidates') or [])} candidates"
        if result.get("workspace"):
            summary = result["workspace"].get("summary") or {}
            return f"workspace {summary.get('formula_pretty') or result['workspace'].get('resolved_material_id')}"
        if "nodes" in result and "edges" in result:
            return f"{len(result.get('nodes') or [])} nodes, {len(result.get('edges') or [])} edges"
    return name


def _project_tool_args(controller: Any, session_id: str, args: dict[str, Any]) -> dict[str, Any]:
    payload = dict(args)
    if payload.get("project_id"):
        return payload
    session = controller.sessions.get_session(session_id) or {}
    context = session.get("context") if isinstance(session.get("context"), dict) else {}
    project_id = context.get("project_id")
    if project_id:
        payload["project_id"] = project_id
    return payload


def _extract_text_from_content(content: dict[str, Any]) -> str:
    parts = []
    for part in content.get("parts") or []:
        if isinstance(part.get("text"), str):
            parts.append(part["text"].strip())
    return "\n".join(part for part in parts if part)


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {}
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}


def _open_material_id(current_workspace: dict[str, Any] | None) -> str | None:
    """Authoritative live material id from UI workspace, if any."""
    if not current_workspace:
        return None
    mid = (
        current_workspace.get("material_id")
        or current_workspace.get("resolved_material_id")
        or current_workspace.get("current_material_id")
    )
    mid_s = str(mid or "").strip()
    return mid_s or None


def _is_identity_or_viewport_query(message: str) -> bool:
    """User asking what is open / what they're looking at ? not a screen/find or property request."""
    text = message.lower()
    # Property questions about "the open material" are NOT identity (avoid false match on "open material").
    property_terms = (
        "density",
        "band gap",
        "bandgap",
        "space group",
        "spacegroup",
        "formation",
        "energy above hull",
        "hull",
        "volume",
        "lattice",
        "magnet",
        "bulk modulus",
        "nsites",
        "symmetry",
        "crystal system",
        "properties",
        "property",
    )
    if any(p in text for p in property_terms):
        return False
    markers = (
        "looking at",
        "what material",
        "which material",
        "current material",
        "open material",
        "this material",
        "am i looking",
        "what am i",
        "what's open",
        "whats open",
        "material am i",
        "material id",
        "formula of the open",
        "what's selected",
        "whats selected",
        "what is selected",
    )
    return any(m in text for m in markers)


def _is_select_or_open_command(message: str) -> bool:
    """Imperative open/select/show of a (possibly different) material ? not 'the open material'."""
    text = message.lower().strip()
    if re.search(r"\b(the open material|open material|currently open|current material)\b", text):
        return False
    return bool(re.match(r"^(open|select|show|load|view|go\s*to|focus)\b", text))


def _refers_to_open_material(message: str, current_workspace: dict[str, Any] | None) -> bool:
    """Whether the utterance is about the live open material (vs discovery/screening/select)."""
    if not _open_material_id(current_workspace):
        return False
    text = message.lower()
    # "open cds structure" must NOT stick to the live material ? that is a select command.
    if _is_select_or_open_command(text):
        return False
    if _is_identity_or_viewport_query(text):
        return True
    tokens = set(re.findall(r"[a-z0-9-]+", text))
    # Bare "open" is an imperative verb, not deictic ("the open material" is handled above).
    if tokens & {"it", "this", "that", "current", "selected"}:
        return True
    if re.search(r"\b(the open|open material|currently open)\b", text):
        return True
    formula = str((current_workspace or {}).get("formula_pretty") or "").strip().lower()
    mid = str(_open_material_id(current_workspace) or "").lower()
    if formula and formula.lower() in text:
        return True
    if mid and mid in text:
        return True
    return False


def _message_requires_tool(message: str, current_workspace: dict[str, Any] | None) -> bool:
    text = message.lower()
    # Identity questions with a live open material can be answered from RunContext
    # (or a single get_material_workspace). Do not force hard-fail ? degraded screener.
    if _is_identity_or_viewport_query(text) and _open_material_id(current_workspace):
        return False
    if re.search(r"\bmp-[a-z0-9-]+\b", text):
        return True
    material_terms = {
        "candidate",
        "find",
        "screen",
        "recommend",
        "rank",
        "compare",
        "graph",
        "neighbor",
        "neighbour",
        "relation",
        "edge",
        "export",
        "stable",
        "stability",
        "metal",
        "nonmetal",
        "oxide",
        "nitride",
        "band gap",
        "density",
        "chemsys",
        "formula",
        "workspace",
        "spacecraft",
        "aerospace",
        "thermal protection",
        "refractory",
        "space group",
        "spacegroup",
        "crystal",
        "structure",
        "property",
        "properties",
    }
    # Bare "material" alone used to force tools + degraded screening ("what material am I looking at?").
    # Only treat "material" as tool-required when paired with discovery/action intent.
    if "material" in text and any(
        t in text for t in ("find", "screen", "recommend", "search", "suggest", "pick", "need", "list", "rank")
    ):
        return True
    if any(term in text for term in material_terms):
        return True
    return bool(current_workspace and any(term in text.split() for term in {"it", "this", "that", "current", "selected"}))


def _fallback_requirement(message: str) -> str:
    text = message.lower()
    if any(term in text for term in {"spacecraft", "space craft", "aerospace", "thermal protection"}):
        return f"{message} stable lightweight wide band aerospace high temperature ceramic material"
    if any(term in text for term in {"high temp", "high-temperature", "refractory", "melts", "melting"}):
        return f"{message} stable high temperature refractory material"
    return message


def _fallback_screen_text(message: str, selected: dict[str, Any] | None, *, selected_is_open: bool) -> str:
    if not selected:
        return "I could not find a matching local material candidate for that request."
    material = selected.get("material") or {}
    material_id = selected.get("material_id") or material.get("material_id")
    formula = selected.get("formula_pretty") or material.get("formula_pretty") or material_id
    density = material.get("density")
    band_gap = material.get("band_gap")
    stable = material.get("is_stable")
    facts = []
    if stable is not None:
        facts.append("stable in the local snapshot" if stable else "not marked stable in the local snapshot")
    if density is not None:
        facts.append(f"density {float(density):.2f} g/cm3")
    if band_gap is not None:
        facts.append(f"band gap {float(band_gap):.2f} eV")
    basis = "; ".join(facts) if facts else selected.get("reason_summary") or "ranked by local screening"
    prefix = "Selected" if selected_is_open else "Top local candidate"
    return (
        f"{prefix}: **{formula}** (`{material_id}`).\n\n"
        f"Why: {basis}.\n\n"
        f"Local screening note: application-specific claims from '{message}' still need literature evidence, "
        "but this is the best local-data pick for the demo."
    )


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        key = json.dumps(item, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_actions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        key = (item.get("type"), json.dumps(item.get("payload"), sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
