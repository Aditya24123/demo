from __future__ import annotations

from typing import Any

EventCallback = Any  # Callable[[dict[str, Any]], None] | None

def _emit(event_cb: EventCallback, event: dict[str, Any]) -> None:
    if callable(event_cb):
        try:
            event_cb(event)
        except Exception:
            pass


def _short_error(exc: BaseException, *, max_len: int = 96) -> str:
    text = " ".join(str(exc or "unknown error").split()).strip()
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "?"
    return text or "unknown error"


def _short_status_target(value: Any, *, max_len: int = 48) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "?"
    return text


def _friendly_tool_status(name: str | None, args: dict[str, Any] | None = None) -> str:
    """Human activity labels for the streaming shimmer (include the target when known)."""
    args = args or {}
    tool = str(name or "").strip()

    def pick(*keys: str) -> str:
        for key in keys:
            if key in args and args.get(key) not in (None, "", [], {}):
                val = args.get(key)
                if isinstance(val, (list, tuple)):
                    joined = ", ".join(str(item) for item in val[:4] if item not in (None, ""))
                    target = _short_status_target(joined)
                else:
                    target = _short_status_target(val)
                if target:
                    return target
        return ""

    if tool == "resolve_material":
        target = pick("query", "material_id", "formula")
        return f"Resolving {target}?" if target else "Resolving material?"
    if tool == "search_materials":
        target = pick("query", "formula", "elements", "chemsys")
        return f"Searching materials for {target}?" if target else "Searching materials?"
    if tool == "get_material_workspace":
        target = pick("material_id", "query")
        return f"Loading workspace for {target}?" if target else "Loading material workspace?"
    if tool == "get_neighborhood":
        target = pick("material_id", "center_id")
        return f"Expanding neighborhood around {target}?" if target else "Expanding neighborhood?"
    if tool == "get_material_details":
        target = pick("material_id")
        return f"Fetching properties for {target}?" if target else "Fetching properties?"
    if tool == "get_material_structure":
        target = pick("material_id")
        return f"Loading structure for {target}?" if target else "Loading structure?"
    if tool == "screen_candidates":
        target = pick("requirement", "query")
        return f"Screening for {target}?" if target else "Screening candidates?"
    if tool == "compare_materials":
        target = pick("material_ids", "ids", "query")
        return f"Comparing {target}?" if target else "Comparing materials?"
    if tool == "select_material":
        target = pick("material_id", "query")
        return f"Selecting {target}?" if target else "Selecting material?"
    if tool == "list_project_files":
        return "Listing project files?"
    if tool == "read_project_file":
        target = pick("path", "file_path", "name")
        return f"Reading {target}?" if target else "Reading project file?"
    if tool == "write_project_file":
        target = pick("path", "file_path", "name")
        return f"Writing {target}?" if target else "Writing project file?"
    if tool == "read_project_notebook":
        return "Reading notebook?"
    if tool == "update_project_notebook":
        return "Updating notebook?"
    if tool == "run_workspace_agent":
        return "Running workspace agent?"
    if tool == "list_project_runs":
        return "Checking project runs?"
    if tool == "export_subgraph":
        return "Exporting subgraph?"
    if tool == "start_research":
        target = pick("query", "topic", "requirement")
        return f"Researching {target}?" if target else "Starting research?"
    if not tool:
        return "Thinking?"
    return f"Running {tool}?"


