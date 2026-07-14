"""Editable agent package: AGENTS.md, skills, context schema, in-memory RunContext."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from catalyst.session_store import compact_session_context

PACKAGE_REL = Path("agents") / "catalyst"
CONTEXT_SCHEMA = "context_schema.json"
AGENTS_FILE = "AGENTS.md"
SKILLS_DIR = "skills"


def agent_package_root(repo_root: Path) -> Path:
    return Path(repo_root).resolve() / PACKAGE_REL


def load_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_context_schema(repo_root: Path) -> dict[str, Any]:
    path = agent_package_root(repo_root) / CONTEXT_SCHEMA
    if not path.is_file():
        return {"version": 1, "max_recent_turns": 8, "max_visible_materials": 16, "capabilities_defaults": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "max_recent_turns": 8, "max_visible_materials": 16, "capabilities_defaults": {}}


def load_static_instructions(repo_root: Path) -> str:
    root = agent_package_root(repo_root)
    return load_text(root / AGENTS_FILE)


def load_skill_markdown(repo_root: Path, skill_id: str) -> str:
    path = agent_package_root(repo_root) / SKILLS_DIR / skill_id / "SKILL.md"
    return load_text(path)


def enabled_skills(surface: str, *, has_project: bool = False, research_hint: bool = False) -> list[str]:
    skills: list[str] = []
    if surface == "genes":
        skills.append("genomics")
    if surface == "project" or has_project:
        skills.append("project")
    if surface == "materials":
        skills.append("materials")
    if research_hint or surface in {"materials", "project"}:
        # Always attach research skill lightly; model uses when relevant.
        skills.append("research")
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for s in skills:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _first(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return value
    return None


def build_run_context(
    *,
    repo_root: Path,
    session: dict[str, Any] | None,
    current_workspace: dict[str, Any] | None,
    capabilities: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Compact live RunContext from UI workspace + session (in-memory)."""
    schema = load_context_schema(repo_root)
    workspace = dict(current_workspace or {})
    session = session or {}

    surface = str(workspace.get("agent_surface") or "").strip().lower()
    if surface not in {"materials", "project", "genes"}:
        rail = str(workspace.get("rail_mode") or "").strip().lower()
        surface = "genes" if rail == "genes" else ("project" if rail == "notebook" or workspace.get("project_id") else "materials")

    material_id = _first(
        workspace.get("material_id"),
        workspace.get("resolved_material_id"),
        workspace.get("current_material_id"),
        (session.get("context") or {}).get("current_material_id"),
    )
    material_id = str(material_id).strip() if material_id else None
    formula = _first(workspace.get("formula_pretty"), workspace.get("title"), (session.get("context") or {}).get("formula_pretty"))
    chemsys = _first(workspace.get("chemsys"), workspace.get("subtitle"))

    max_vis = int(schema.get("max_visible_materials") or 16)
    visible = workspace.get("visible_material_ids") or []
    if isinstance(visible, list):
        visible = [str(x) for x in visible[:max_vis] if x]
    else:
        visible = []

    max_turns = int(schema.get("max_recent_turns") or 8)
    recent: list[dict[str, str]] = []
    for message in (session.get("messages") or [])[-max_turns:]:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "").strip()
        if content:
            recent.append({"role": role, "text": content[:600]})

    caps = dict(schema.get("capabilities_defaults") or {})
    if capabilities:
        caps.update({k: bool(v) for k, v in capabilities.items()})

    project_id = _first(workspace.get("project_id"), (session.get("context") or {}).get("project_id"))
    run_context: dict[str, Any] = {
        "surface": surface,
        "viewport": {
            "material_id": material_id,
            "formula_pretty": str(formula).strip() if formula else None,
            "chemsys": str(chemsys).strip() if chemsys else None,
            "tab": workspace.get("workspace_tab"),
            "hop_depth": workspace.get("hop_depth"),
            "genomics_case_id": workspace.get("genomics_case_id"),
            "genomics_variant_index": workspace.get("genomics_variant_index"),
            "genomics_repeat_count": workspace.get("genomics_repeat_count"),
            "genome": {
                "gene": workspace.get("genomics_case_id") or "BRCA1",
                "visible_start": workspace.get("genome_visible_start"),
                "visible_end": workspace.get("genome_visible_end"),
                "selected_position": workspace.get("genome_selected_position"),
                # This field is intentionally the visual window, never the full sequence record.
                "visible_sequence": workspace.get("genome_sequence"),
                "total_gene_length": workspace.get("genome_total_length"),
                "selected_variant": workspace.get("genome_selected_variant"),
            },
        },
        "project": {
            "id": str(project_id).strip() if project_id else None,
            "name": workspace.get("project_name"),
        },
        "selection": {
            "visible_material_ids": visible,
            "selected_edge_id": workspace.get("selected_edge_id"),
        },
        "session": {
            "session_id": session.get("session_id"),
            "summary": str(session.get("summary") or "").strip() or None,
            "recent_turns": recent,
            "compact": compact_session_context(session) if session else {},
        },
        "capabilities": caps,
        "mode_guidance": _mode_guidance(surface, material_id, formula, chemsys),
    }
    return run_context


def _mode_guidance(surface: str, material_id: str | None, formula: Any, chemsys: Any) -> str:
    if surface == "genes":
        return (
            "GENES demo mode. The live DNA Variant Explorer selection is authoritative. "
            "For genomic questions, use viewport.genome as the authoritative current state; it contains only "
            "the visible sequence window. Use control_genome_view for highlight, zoom, or show-sequence actions. "
            "Use inspect_genomics_case for BRCA1, HBB, or CTG case facts. Never request, reveal, or infer a "
            "complete gene sequence unless the user explicitly asks for a larger region. This is educational, "
            "not diagnosis or clinical advice."
        )
    if surface == "project":
        return (
            "PROJECT mode: prefer notebook/files/runs/Codex tools; use project.id from RunContext. "
            "Live viewport material (if any) is still authoritative for 'this material'."
        )
    if material_id:
        label = formula or "material"
        extra = f", chemsys {chemsys}" if chemsys else ""
        return (
            f"MATERIALS mode. LIVE VIEWPORT: {label} ({material_id}){extra}. "
            "Chat history may mention other materials ? do not say the user is looking at a past material."
        )
    return "MATERIALS mode. No open material in viewport; resolve/search before asserting a current formula."


def render_run_context_markdown(run_context: dict[str, Any]) -> str:
    vp = run_context.get("viewport") or {}
    proj = run_context.get("project") or {}
    lines = [
        "## LIVE RunContext (authoritative ? wins over chat history)",
        f"- Surface: **{run_context.get('surface') or 'materials'}**",
    ]
    mid = vp.get("material_id")
    if mid:
        formula = vp.get("formula_pretty") or "unknown"
        lines.append(f"- Open material: **{formula}** (`{mid}`)")
        if vp.get("chemsys"):
            lines.append(f"- Chemsys: {vp['chemsys']}")
        if vp.get("tab"):
            lines.append(f"- Tab: {vp['tab']}")
        if vp.get("hop_depth") is not None:
            lines.append(f"- Graph hops: {vp['hop_depth']}")
    else:
        lines.append("- Open material: *(none)*")
    if proj.get("id"):
        lines.append(f"- Project: {proj.get('name') or proj.get('id')} (`{proj.get('id')}`)")
    else:
        lines.append("- Project: *(none)*")
    caps = run_context.get("capabilities") or {}
    if caps:
        on = [k for k, v in caps.items() if v]
        if on:
            lines.append(f"- Capabilities: {', '.join(on)}")
    guidance = str(run_context.get("mode_guidance") or "").strip()
    if guidance:
        lines.extend(["", f"Mode guidance: {guidance}"])
    lines.extend(
        [
            "",
            "Never claim the user is viewing a different material because earlier messages mentioned one.",
            "",
            "### RunContext JSON",
            "```json",
            json.dumps(
                {
                    "surface": run_context.get("surface"),
                    "viewport": run_context.get("viewport"),
                    "project": run_context.get("project"),
                    "selection": run_context.get("selection"),
                    "capabilities": run_context.get("capabilities"),
                    "session": {
                        "session_id": (run_context.get("session") or {}).get("session_id"),
                        "summary": (run_context.get("session") or {}).get("summary"),
                    },
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
        ]
    )
    return "\n".join(lines)


def build_system_instruction(
    repo_root: Path,
    *,
    session: dict[str, Any] | None,
    current_workspace: dict[str, Any] | None,
    capabilities: dict[str, bool] | None = None,
    tool_markdown: str | None = None,
) -> dict[str, Any]:
    """In-memory system prompt for one turn. Optionally persist a debug trace separately."""
    run_context = build_run_context(
        repo_root=repo_root,
        session=session,
        current_workspace=current_workspace,
        capabilities=capabilities,
    )
    surface = str(run_context.get("surface") or "materials")
    has_project = bool((run_context.get("project") or {}).get("id"))
    skills = enabled_skills(surface, has_project=has_project)

    parts: list[str] = []
    static = load_static_instructions(repo_root)
    if static:
        parts.append(static)
    else:
        parts.append("# Catalyst Workspace Agent\n\nGround answers in tools and LIVE RunContext.")

    skill_blocks: list[str] = []
    for skill_id in skills:
        body = load_skill_markdown(repo_root, skill_id)
        if body:
            skill_blocks.append(body)
    if skill_blocks:
        parts.append("## Active skills\n\n" + "\n\n---\n\n".join(skill_blocks))

    parts.append(render_run_context_markdown(run_context))

    if tool_markdown:
        parts.append(tool_markdown)

    parts.append(
        "Tool results are authoritative. Prefer LIVE RunContext for the open material. "
        "State failures honestly; offer a grounded next action."
    )

    system_instruction = "\n\n".join(parts).strip()
    return {
        "system_instruction": system_instruction,
        "run_context": run_context,
        "skills": skills,
    }


def maybe_write_turn_trace(
    repo_root: Path,
    *,
    turn_id: str,
    system_instruction: str,
    run_context: dict[str, Any],
) -> Path | None:
    """Immutable per-turn debug artifact (not a live shared file)."""
    try:
        root = Path(repo_root).resolve() / "data" / "local" / "agent" / "traces" / turn_id
        root.mkdir(parents=True, exist_ok=True)
        (root / "run_context.json").write_text(json.dumps(run_context, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (root / "system_instruction.md").write_text(system_instruction + "\n", encoding="utf-8")
        return root
    except OSError:
        return None
