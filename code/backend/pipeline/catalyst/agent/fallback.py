from __future__ import annotations

from typing import Any

from catalyst.agent.events import _emit
from catalyst.agent.helpers import (
    _dedupe_actions,
    _dedupe_dicts,
    _empty_aggregate,
    _fallback_requirement,
    _fallback_screen_text,
    _is_identity_or_viewport_query,
    _is_select_or_open_command,
    _material_focus_ui_actions,
    _message_requires_tool,
    _open_material_action,
    _open_material_id,
    _refers_to_open_material,
)
from catalyst.agent.tool_exec import _assistant_response, _execute_tool
from catalyst.session_store import compact_session_context

EventCallback = Any


def _answer_open_material(
    controller: Any,
    *,
    session_id: str,
    message: str,
    current_workspace: dict[str, Any],
    material_id: str,
) -> dict[str, Any]:
    """Ground identity / open-material answers on live viewport ? never candidate screening."""
    aggregate = _empty_aggregate()
    formula = str(current_workspace.get("formula_pretty") or "").strip()
    chemsys = str(current_workspace.get("chemsys") or "").strip()
    identity = _is_identity_or_viewport_query(message)

    # Always load workspace when possible so density/spacegroup answers are grounded.
    _execute_tool(
        controller,
        session_id,
        "get_material_workspace",
        {"material_id": material_id},
        aggregate,
    )
    workspace = {}
    if aggregate["tool_results"]:
        workspace = (aggregate["tool_results"][0].get("result") or {}).get("workspace") or {}
    summary = workspace.get("summary") or {}
    structure = workspace.get("structure") or {}
    symmetry = structure.get("symmetry") if isinstance(structure.get("symmetry"), dict) else {}
    formula = str(summary.get("formula_pretty") or formula or material_id)
    density = structure.get("density") or summary.get("density")
    spacegroup = (
        symmetry.get("symbol")
        or symmetry.get("space_group_symbol")
        or summary.get("spacegroup")
        or summary.get("space_group")
    )
    band_gap = summary.get("band_gap")

    if identity:
        bits = [f"You are looking at **{formula}** (`{material_id}`)"]
        if chemsys:
            bits.append(f"chemsys {chemsys}")
        text = ". ".join(bits) + " (live viewport)."
    else:
        facts = []
        if density is not None:
            try:
                facts.append(f"density {float(density):.2f} g/cm?")
            except (TypeError, ValueError):
                facts.append(f"density {density}")
        if spacegroup:
            facts.append(f"space group {spacegroup}")
        if band_gap is not None:
            try:
                facts.append(f"band gap {float(band_gap):.2f} eV")
            except (TypeError, ValueError):
                facts.append(f"band gap {band_gap}")
        if facts:
            text = f"**{formula}** (`{material_id}`): " + "; ".join(facts) + "."
        else:
            text = f"Loaded open material **{formula}** (`{material_id}`) from the local snapshot."

    return _assistant_response(
        controller,
        session_id=session_id,
        text=text,
        aggregate=aggregate,
        current_workspace=current_workspace,
        confidence="grounded",
    )


def run_local_agent_fallback(
    controller: Any,
    *,
    session_id: str,
    message: str,
    current_workspace: dict[str, Any] | None,
) -> dict[str, Any] | None:
    text = message.strip()
    lowered = text.lower()
    open_mid = _open_material_id(current_workspace)
    aggregate = _empty_aggregate()
    wants_select = any(term in lowered for term in {"select", "open", "show", "highlight", "locate", "zoom", "load", "view"})
    # Do NOT treat bare "material" as find ? that stole identity answers (CdS screener).
    wants_find = any(term in lowered for term in {"find", "screen", "recommend", "rank", "candidate", "candidates"})
    if "material" in lowered and any(
        t in lowered for t in ("find", "screen", "recommend", "search", "suggest", "pick", "need", "list")
    ):
        wants_find = True
    explicit_material = controller._resolve_material_reference(text)

    # Provider-free answers still honour the exact bounded state supplied by the UI.
    # This path deliberately reads no sequence files and cannot expose a whole gene.
    if str((current_workspace or {}).get("agent_surface") or "").lower() == "genes":
        genome_terms = {"sequence", "nucleotide", "base", "mutation", "variant", "hgvs", "gene", "region", "position", "selected", "highlight", "zoom"}
        if any(term in lowered for term in genome_terms):
            genome = current_workspace or {}
            gene = str(genome.get("genomics_case_id") or "BRCA1").upper()
            start = genome.get("genome_visible_start")
            end = genome.get("genome_visible_end")
            selected = genome.get("genome_selected_position")
            sequence = str(genome.get("genome_sequence") or "")
            variant = genome.get("genome_selected_variant") or {}
            if "show" in lowered and "sequence" in lowered:
                _execute_tool(controller, session_id, "control_genome_view", {"action": "showSequence", "gene": gene}, aggregate)
            elif "zoom" in lowered and start is not None and end is not None:
                _execute_tool(controller, session_id, "control_genome_view", {"action": "zoom", "gene": gene, "start": start, "end": end}, aggregate)
            elif any(term in lowered for term in {"highlight", "selected", "position"}) and selected is not None:
                _execute_tool(controller, session_id, "control_genome_view", {"action": "highlight", "gene": gene, "position": selected}, aggregate)
            if sequence:
                position_label = f"position {selected}" if selected is not None else "the current marker"
                hgvs = variant.get("hgvs") if isinstance(variant, dict) else None
                change = ""
                if isinstance(variant, dict) and (variant.get("reference") or variant.get("alternate")):
                    change = f" ({variant.get('reference', '?')} ? {variant.get('alternate', '?')})"
                text_out = (
                    f"You are viewing **{gene}** positions **{start}?{end}** (gene-relative, one-based). "
                    f"The selected nucleotide is **{position_label}**. "
                    f"Visible sequence: `{sequence}`."
                    + (f" The displayed variant is **{hgvs}**{change}." if hgvs else "")
                )
                return _assistant_response(controller, session_id=session_id, text=text_out, aggregate=aggregate, current_workspace=current_workspace, confidence="grounded")

    # Keep the bounded Genes showcase useful without a configured model provider.
    genomics_case = None
    if any(term in lowered for term in {"brca1", "brca", "rs80357906"}):
        genomics_case = "brca1"
    elif any(term in lowered for term in {"hbb", "rs334", "hemoglobin"}):
        genomics_case = "hbb"
    elif any(term in lowered for term in {"ctg", "myotonic", "repeat expansion", "repeat count"}):
        genomics_case = "ctg"
    if genomics_case:
        repeat_count = None
        if genomics_case == "ctg":
            import re

            match = re.search(r"\b(\d{1,3})\s*(?:ctg|repeat)?\b", lowered)
            if match:
                repeat_count = max(0, min(100, int(match.group(1))))
        _execute_tool(
            controller,
            session_id,
            "inspect_genomics_case",
            {"case_id": genomics_case, **({"repeat_count": repeat_count} if repeat_count is not None else {})},
            aggregate,
        )
        result = (aggregate["tool_results"][-1].get("result") if aggregate["tool_results"] else {}) or {}
        case = result.get("case") or {}
        label = case.get("title") or genomics_case.upper()
        detail = case.get("interpretation") or "Opened the educational genomics demo case."
        if case.get("repeat"):
            repeat = case["repeat"]
            detail = f"{detail} Current demo setting: {repeat.get('repeat_count')} repeats ({repeat.get('label')})."
        return _assistant_response(
            controller,
            session_id=session_id,
            text=f"Opened **{label}** in the DNA Variant Explorer. {detail}",
            aggregate=aggregate,
            current_workspace=current_workspace,
            confidence="grounded",
        )

    # "open cds structure" ? resolve + select BEFORE sticky open-material path.
    if explicit_material and (wants_select or _is_select_or_open_command(text)) and not wants_find:
        _execute_tool(
            controller,
            session_id,
            "select_material",
            {"material_id": explicit_material, "open_inspector": True},
            aggregate,
        )
        workspace = (aggregate["tool_results"][0]["result"].get("workspace") if aggregate["tool_results"] else None) or {}
        summary = (workspace.get("summary") if isinstance(workspace, dict) else None) or {}
        formula = summary.get("formula_pretty") or explicit_material
        return _assistant_response(
            controller,
            session_id=session_id,
            text=f"Opened **{formula}** (`{explicit_material}`) in the structure viewer.",
            aggregate=aggregate,
            current_workspace=current_workspace,
            confidence="grounded",
        )

    # Viewport / identity / "this material" ? answer from open material, never screen.
    if open_mid and current_workspace and (
        _is_identity_or_viewport_query(text) or _refers_to_open_material(text, current_workspace)
    ):
        # Discovery phrasing still wins when user clearly wants candidates.
        discovery = any(t in lowered for t in ("find", "screen", "recommend", "rank", "candidates", "search for"))
        if not discovery and not _is_select_or_open_command(text):
            return _answer_open_material(
                controller,
                session_id=session_id,
                message=text,
                current_workspace=current_workspace,
                material_id=open_mid,
            )

    if not _message_requires_tool(text, current_workspace):
        # Still allow open-material property answers when require_tool was relaxed for identity.
        if open_mid and current_workspace and _is_identity_or_viewport_query(text):
            return _answer_open_material(
                controller,
                session_id=session_id,
                message=text,
                current_workspace=current_workspace,
                material_id=open_mid,
            )
        return None

    if explicit_material and not wants_find:
        _execute_tool(
            controller,
            session_id,
            "select_material" if wants_select else "get_material_workspace",
            {"material_id": explicit_material, "open_inspector": True},
            aggregate,
        )
        workspace = (aggregate["tool_results"][0]["result"].get("workspace") if aggregate["tool_results"] else None) or {}
        summary = workspace.get("summary") or {}
        formula = summary.get("formula_pretty") or explicit_material
        return _assistant_response(
            controller,
            session_id=session_id,
            text=f"Loaded **{formula}** (`{explicit_material}`) from the local snapshot.",
            aggregate=aggregate,
            current_workspace=current_workspace,
            confidence="grounded",
        )

    if wants_find:
        requirement = _fallback_requirement(text)
        _execute_tool(
            controller,
            session_id,
            "screen_candidates",
            {"requirement": requirement, "limit": 8, "include_research_candidates": False},
            aggregate,
        )
        candidates = aggregate["candidate_results"] or []
        selected = candidates[0] if candidates else None
        if selected and wants_select:
            _execute_tool(
                controller,
                session_id,
                "select_material",
                {"material_id": selected.get("material_id"), "open_inspector": True},
                aggregate,
            )
        return _assistant_response(
            controller,
            session_id=session_id,
            text=_fallback_screen_text(text, selected, selected_is_open=bool(selected and wants_select)),
            aggregate=aggregate,
            current_workspace=current_workspace,
            confidence="grounded" if selected else "partial",
        )

    if open_mid and current_workspace and any(
        term in lowered.split() for term in {"it", "this", "that", "current", "selected", "open"}
    ):
        return _answer_open_material(
            controller,
            session_id=session_id,
            message=text,
            current_workspace=current_workspace,
            material_id=open_mid,
        )

    return None


def should_use_local_agent_fast_path(message: str) -> bool:
    text = message.lower()
    application_terms = {"spacecraft", "space craft", "aerospace", "thermal protection"}
    action_terms = {"find", "screen", "recommend", "select", "open", "show", "highlight", "locate"}
    return any(term in text for term in application_terms) and any(term in text for term in action_terms)


