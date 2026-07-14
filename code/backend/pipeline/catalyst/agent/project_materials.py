"""Project material artifacts (*.catalyst.json) ? link materials into notebook workspace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from catalyst.agent.helpers import _material_focus_ui_actions, _project_tool_args, _resolve_arg_material


def _artifact_payload(material_id: str, formula: str | None = None, note: str | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "type": "catalyst_material",
        "version": 1,
        "material_id": material_id,
        "formula_pretty": formula,
        "note": note,
        "draft": extra.get("draft") or None,
    }


def is_catalyst_material_file(path: str, content: str | None = None) -> bool:
    p = str(path or "").lower()
    if p.endswith(".catalyst.json"):
        return True
    if content and content.lstrip().startswith("{"):
        try:
            data = json.loads(content)
            return isinstance(data, dict) and data.get("type") == "catalyst_material" and data.get("material_id")
        except json.JSONDecodeError:
            return False
    return False


def parse_material_artifact(content: str) -> dict[str, Any] | None:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("type") != "catalyst_material":
        return None
    mid = str(data.get("material_id") or "").strip()
    if not mid:
        return None
    return data


def save_project_material(
    controller: Any,
    *,
    session_id: str,
    args: dict[str, Any],
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    payload = _project_tool_args(controller, session_id, args)
    project_id = payload.get("project_id")
    material_id = _resolve_arg_material(controller, payload.get("material_id")) or str(payload.get("material_id") or "").strip()
    if not project_id:
        return {"ok": False, "error": "project_id required (open a project / notebook surface)"}
    if not material_id:
        return {"ok": False, "error": "material_id required"}
    formula = None
    try:
        mat = controller.store.get_material(material_id)
        if mat:
            formula = mat.get("formula_pretty")
            material_id = str(mat.get("material_id") or material_id)
    except Exception:
        pass
    path = f"files/materials/{material_id}.catalyst.json"
    body = _artifact_payload(material_id, formula=formula, note=payload.get("note"))
    try:
        written = controller.projects.write_text_file(str(project_id), path, json.dumps(body, indent=2))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": path}
    aggregate["ui_actions"].append({"type": "refresh_project", "project_id": project_id})
    return {"ok": True, "path": written.get("path") or path, "material_id": material_id, "artifact": body}


def open_project_material(
    controller: Any,
    *,
    session_id: str,
    args: dict[str, Any],
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    payload = _project_tool_args(controller, session_id, args)
    project_id = payload.get("project_id")
    path = str(payload.get("path") or "").strip()
    material_id = str(payload.get("material_id") or "").strip()

    if path and project_id:
        try:
            file_payload = controller.projects.read_text_file(str(project_id), path)
            content = str(file_payload.get("content") or "")
            art = parse_material_artifact(content)
            if art:
                material_id = str(art.get("material_id") or material_id)
        except Exception as exc:
            return {"ok": False, "error": f"Could not read artifact: {exc}", "path": path}

    material_id = _resolve_arg_material(controller, material_id) or material_id
    if not material_id:
        return {"ok": False, "error": "No material_id in path or args"}

    workspace = controller.store.workspace(material_id) if hasattr(controller, "store") else None
    if not workspace:
        return {"ok": False, "error": f"Material not in local snapshot: {material_id}"}

    mid = str(workspace.get("resolved_material_id") or material_id)
    formula = (workspace.get("summary") or {}).get("formula_pretty")
    aggregate["ui_actions"].extend(_material_focus_ui_actions(mid, open_inspector=True))
    aggregate["ui_actions"].append({"type": "set_workspace_tab", "tab": "structure"})
    # Ensure materials home rail for main viewer.
    aggregate["ui_actions"].append({"type": "set_rail_mode", "mode": "home"})
    aggregate["context_updates"]["current_material_id"] = mid
    aggregate["context_updates"]["last_focus_material_id"] = mid
    if formula:
        aggregate["context_updates"]["formula_pretty"] = formula
    return {
        "ok": True,
        "material_id": mid,
        "formula_pretty": formula,
        "path": path or None,
        "workspace_tab": "structure",
    }
