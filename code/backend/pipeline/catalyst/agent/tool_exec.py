from __future__ import annotations

from typing import Any
from uuid import uuid4

from catalyst.agent.events import _emit, _friendly_tool_status
from catalyst.agent.helpers import (
    _capture_material_result,
    _compact_tool_result,
    _dedupe_actions,
    _dedupe_dicts,
    _empty_aggregate,
    _material_focus_ui_actions,
    _open_material_action,
    _project_tool_args,
    _resolve_arg_material,
    _tool_summary,
    _update_material_context,
)
from catalyst.session_store import compact_session_context

EventCallback = Any

def _execute_tool(controller: Any, session_id: str, name: str | None, args: dict[str, Any], aggregate: dict[str, Any]) -> dict[str, Any]:
    if not name:
        return {"ok": False, "error": "missing tool name"}
    args = args or {}
    result: dict[str, Any]
    if name == "control_genome_view":
        action = str(args.get("action") or "").strip()
        gene = str(args.get("gene") or "BRCA1").upper()
        if gene != "BRCA1" or action not in {"highlight", "zoom", "showSequence"}:
            result = {"ok": False, "error": "Supported genomic view actions are highlight, zoom, or showSequence for BRCA1."}
        elif action == "highlight":
            try:
                position = int(args.get("position"))
            except (TypeError, ValueError):
                position = 0
            result = {"ok": position > 0, "action": action, "gene": gene, "position": position}
            if result["ok"]:
                aggregate["ui_actions"].append({"type": "genome_highlight", "action": "highlight", "gene": gene, "position": position})
        elif action == "zoom":
            try:
                start, end = int(args.get("start")), int(args.get("end"))
            except (TypeError, ValueError):
                start, end = 0, 0
            result = {"ok": start > 0 and end >= start, "action": action, "gene": gene, "start": start, "end": end}
            if result["ok"]:
                aggregate["ui_actions"].append({"type": "genome_zoom", "action": "zoom", "gene": gene, "start": start, "end": end})
        else:
            result = {"ok": True, "action": action, "gene": gene}
            aggregate["ui_actions"].append({"type": "genome_show_sequence", "action": "showSequence", "gene": gene})
    elif name == "inspect_genomics_case":
        from catalyst.genomics_demo import tool_result

        case_id = str(args.get("case_id") or "").strip().lower()
        raw_repeat = args.get("repeat_count")
        try:
            repeat_count = max(0, min(100, int(raw_repeat))) if raw_repeat is not None else None
        except (TypeError, ValueError):
            repeat_count = None
        result = tool_result(case_id, repeat_count=repeat_count)
        if result.get("ok"):
            case = result["case"]
            aggregate["citations"].append({"type": "genomics_demo", "case_id": case_id, "source": case.get("source_label")})
            aggregate["ui_actions"].append({"type": "open_genomics_case", "case_id": case_id})
            aggregate["ui_actions"].append({"type": "focus_genomics_variant", "index": case.get("highlighted_index", 0)})
            if case_id == "brca1":
                aggregate["ui_actions"].extend([
                    {"type": "genome_zoom", "action": "zoom", "gene": "BRCA1", "start": 12755, "end": 12786},
                    {"type": "genome_highlight", "action": "highlight", "gene": "BRCA1", "position": 12770},
                ])
            if case_id == "ctg":
                aggregate["ui_actions"].append({"type": "set_genomics_repeat_count", "repeat_count": (case.get("repeat") or {}).get("repeat_count", 55)})
            if bool(args.get("reset_camera")):
                aggregate["ui_actions"].append({"type": "reset_genomics_camera"})
            aggregate["context_updates"]["last_genomics_case_id"] = case_id
    elif name == "resolve_material":
        query = str(args.get("query") or args.get("material_id") or "")
        material_id = controller._resolve_material_reference(query)
        result = {"ok": bool(material_id), "material_id": material_id, "query": query}
    elif name == "search_materials":
        result = controller.search_materials(args)
        results = result.get("results") or []
        if results:
            aggregate["candidate_results"] = results
            aggregate["actions"].append(
                {
                    "id": "show_search_results",
                    "type": "show_candidates",
                    "label": "Show matching materials",
                    "payload": {"candidates": results},
                }
            )
    elif name == "get_material_workspace":
        material_id = _resolve_arg_material(controller, args.get("material_id"))
        workspace = controller.store.workspace(material_id) if material_id else None
        result = {"ok": bool(workspace), "workspace": workspace}
        if not workspace:
            result["error"] = f"Material not found in the local snapshot: {args.get('material_id')}"
        if workspace:
            _capture_material_result(controller, session_id, workspace, aggregate)
    elif name == "get_neighborhood":
        material_id = _resolve_arg_material(controller, args.get("material_id"))
        result = controller.get_neighborhood({"material_id": material_id}) if material_id else {"nodes": [], "edges": []}
        result["ok"] = bool(result.get("nodes"))
        if not result["ok"]:
            result["error"] = f"No local graph neighborhood found for: {args.get('material_id')}"
        if material_id:
            aggregate["citations"].append({"type": "local_graph", "material_id": material_id})
            _update_material_context(controller, session_id, material_id, "graph_neighborhood")
            # Drive the live shell: select material + switch Structure ? Neighbors tab.
            # Without these, chat says "graph opened" while the canvas stays on structure.
            hop = args.get("depth") or args.get("hop_depth") or args.get("hops")
            try:
                hop_i = max(1, min(5, int(hop))) if hop is not None else None
            except (TypeError, ValueError):
                hop_i = None
            aggregate["ui_actions"].extend(
                _material_focus_ui_actions(material_id, open_inspector=bool(args.get("open_inspector", False)))
            )
            aggregate["ui_actions"].append({"type": "set_workspace_tab", "tab": "neighbors"})
            if hop_i is not None:
                aggregate["ui_actions"].append({"type": "set_hop_depth", "depth": hop_i})
            aggregate["ui_actions"].append(
                {
                    "type": "expand_neighborhood",
                    "material_id": material_id,
                    "depth": hop_i or 1,
                }
            )
    elif name == "get_material_details":
        material_id = _resolve_arg_material(controller, args.get("material_id"))
        result = controller.get_material_details({**args, "material_id": material_id}) if material_id else {"ok": False, "error": "Material not found"}
        if result.get("ok") and material_id:
            aggregate["citations"].append({"type": "local_material_details", "material_id": material_id})
            _update_material_context(controller, session_id, material_id, "material_details")
    elif name == "get_material_structure":
        material_id = _resolve_arg_material(controller, args.get("material_id"))
        result = controller.get_material_structure({"material_id": material_id}) if material_id else {"ok": False, "error": "Material not found"}
        if result.get("ok") and material_id:
            aggregate["citations"].append({"type": "local_structure", "material_id": material_id})
            aggregate["ui_actions"].extend(_material_focus_ui_actions(material_id, open_inspector=False))
            aggregate["ui_actions"].append({"type": "set_workspace_tab", "tab": "structure"})
            _update_material_context(controller, session_id, material_id, "structure")
    elif name == "get_graph_overview":
        result = controller.get_graph_overview(args)
        if result.get("ok"):
            aggregate["ui_actions"].append({"type": "open_graph"})
    elif name == "inspect_graph_node":
        result = controller.inspect_graph_node(args)
    elif name == "inspect_edge":
        result = controller.inspect_edge({"edge_id": str(args.get("edge_id") or "")})
        if result.get("edge"):
            aggregate["citations"].append({"type": "local_graph_edge", "edge_id": args.get("edge_id")})
    elif name == "screen_candidates":
        requirement = str(args.get("requirement") or "")
        result = controller.screen_candidates(
            {
                "requirement": requirement,
                "limit": int(args.get("limit") or 8),
                "include_research_candidates": bool(args.get("include_research_candidates", False)),
            }
        )
        candidates = result.get("candidates") or []
        aggregate["candidate_results"] = candidates
        if candidates:
            aggregate["actions"].append(
                {
                    "id": "show_screened_candidates",
                    "type": "show_candidates",
                    "label": "Show ranked candidates",
                    "payload": {"candidates": candidates},
                }
            )
            aggregate["context_updates"]["last_candidate_material_ids"] = [item.get("material_id") for item in candidates[:8]]
            aggregate["context_updates"]["last_screen_requirement"] = requirement
    elif name == "compare_materials":
        material_ids = [_resolve_arg_material(controller, item) or str(item) for item in args.get("material_ids") or []]
        result = controller.compare_materials(
            {
                "material_ids": material_ids,
                "include_evidence": bool(args.get("include_evidence", True)),
                "include_edges": bool(args.get("include_edges", True)),
            }
        )
    elif name == "create_candidate_set":
        result = controller.create_candidate_set({**args, "session_id": session_id})
        candidate_set = result.get("candidate_set") or {}
        candidates = candidate_set.get("candidates") or []
        if result.get("ok"):
            aggregate["context_updates"]["candidate_set_id"] = candidate_set.get("candidate_set_id")
            aggregate["candidate_results"] = candidates
            aggregate["actions"].append({
                "id": "show_candidate_set",
                "type": "show_candidates",
                "label": "Open candidate set",
                "payload": {"candidate_set": candidate_set, "candidates": candidates},
            })
    elif name == "list_candidate_sets":
        result = controller.list_candidate_sets({**args, "session_id": args.get("session_id") or session_id})
    elif name == "get_candidate_set":
        result = controller.get_candidate_set(args)
    elif name == "select_material":
        material_id = _resolve_arg_material(controller, args.get("material_id"))
        workspace = controller.store.workspace(material_id) if material_id else None
        open_inspector = bool(args.get("open_inspector", True))
        result = {"ok": bool(workspace), "workspace": workspace, "selected_material_id": material_id}
        if not workspace:
            result["error"] = f"Material cannot be selected because it is absent from the local snapshot: {args.get('material_id')}"
        if workspace and material_id:
            summary = workspace.get("summary") or {}
            title = summary.get("formula_pretty") or material_id
            aggregate["citations"].append({"type": "local_material", "material_id": workspace["resolved_material_id"]})
            aggregate["actions"].append(_open_material_action(workspace["resolved_material_id"], f"Open {title}"))
            aggregate["ui_actions"].extend(_material_focus_ui_actions(workspace["resolved_material_id"], open_inspector=open_inspector))
            _update_material_context(controller, session_id, workspace["resolved_material_id"], "material_workspace")
    elif name == "export_subgraph":
        material_ids = [_resolve_arg_material(controller, item) or str(item) for item in args.get("material_ids") or []]
        result = controller.export_subgraph(
            {
                "material_ids": material_ids,
                "include_evidence": bool(args.get("include_evidence", True)),
                "include_edge_details": bool(args.get("include_edge_details", True)),
            }
        )
        aggregate["actions"].append({"id": "export_subgraph", "type": "export", "label": "Open export", "payload": result})
    elif name == "start_research":
        payload = dict(args)
        payload["session_id"] = session_id
        result = controller.start_research(payload)
        aggregate["actions"].append(
            {
                "id": "start_research",
                "type": "start_research",
                "label": "Open research run",
                "payload": result,
            }
        )
    elif name == "get_research_run":
        result = controller.get_research_run(args)
    elif name == "ingest_url":
        payload = dict(args)
        payload["session_id"] = session_id
        result = controller.ingest_url(payload)
    elif name == "list_project_files":
        result = controller.list_project_files(_project_tool_args(controller, session_id, args))
    elif name == "read_project_file":
        result = controller.read_project_file(_project_tool_args(controller, session_id, args))
    elif name == "write_project_file":
        payload = _project_tool_args(controller, session_id, args)
        result = controller.write_project_file(payload)
        if result.get("ok"):
            aggregate["ui_actions"].append({"type": "refresh_project", "project_id": result.get("project_id")})
    elif name == "read_project_notebook":
        result = controller.read_project_notebook(_project_tool_args(controller, session_id, args))
    elif name == "update_project_notebook":
        payload = _project_tool_args(controller, session_id, args)
        result = controller.update_project_notebook(payload)
        if result.get("ok"):
            aggregate["ui_actions"].append({"type": "refresh_project", "project_id": result.get("project_id")})
    elif name == "run_workspace_agent":
        payload = _project_tool_args(controller, session_id, args)
        result = controller.run_workspace_agent(payload)
        if result.get("ok"):
            aggregate["actions"].append({
                "id": "open_project_run",
                "type": "open_project_run",
                "label": "Open workspace run",
                "payload": {"project_id": result.get("project_id"), "run": result.get("run")},
            })
            aggregate["ui_actions"].append({"type": "refresh_project", "project_id": result.get("project_id")})
            aggregate["ui_actions"].append({"type": "open_project_run", "project_id": result.get("project_id")})
    elif name == "list_project_runs":
        result = controller.list_project_runs(_project_tool_args(controller, session_id, args))
    elif name == "list_model_services":
        result = controller.list_model_services(args)
    elif name == "run_model_service":
        payload = _project_tool_args(controller, session_id, args)
        result = controller.run_model_service(payload)
        if result.get("ok") and result.get("project_id"):
            aggregate["ui_actions"].append({"type": "refresh_project", "project_id": result.get("project_id")})
    elif name == "run_allowlisted_shell":
        from catalyst.agent.shell_allowlist import run_allowlisted_shell

        result = run_allowlisted_shell(
            controller,
            session_id=session_id,
            command=str(args.get("command") or ""),
            project_id=args.get("project_id"),
        )
    elif name == "open_project_material":
        from catalyst.agent.project_materials import open_project_material

        result = open_project_material(controller, session_id=session_id, args=args, aggregate=aggregate)
    elif name == "save_project_material":
        from catalyst.agent.project_materials import save_project_material

        result = save_project_material(controller, session_id=session_id, args=args, aggregate=aggregate)
    else:
        result = {"ok": False, "error": f"Unknown tool: {name}"}

    trace = {
        "id": f"tool_{uuid4().hex[:16]}",
        "tool": name,
        "args": args,
        "summary": _tool_summary(name, result),
    }
    aggregate["tool_calls"].append({"name": name, "args": args})
    aggregate["tool_results"].append({"tool": name, "result": _compact_tool_result(result)})
    controller.sessions.append_tool_trace(session_id, trace)
    return result


def _assistant_response(
    controller: Any,
    *,
    session_id: str,
    text: str,
    aggregate: dict[str, Any],
    current_workspace: dict[str, Any] | None,
    confidence: str,
    provider: dict[str, Any] | None = None,
) -> dict[str, Any]:
    citations = _dedupe_dicts(aggregate["citations"])
    actions = _dedupe_actions(aggregate["actions"])
    ui_actions = _dedupe_dicts(aggregate["ui_actions"])
    if provider:
        cite = {
            "type": "llm_provider",
            "provider": provider.get("provider"),
            "model": provider.get("model"),
        }
        if provider.get("transport"):
            cite["transport"] = provider.get("transport")
        citations.append(cite)
    if aggregate["context_updates"]:
        controller.sessions.update_session(session_id, {"context": aggregate["context_updates"]})
    assistant = controller.sessions.append_message(
        session_id,
        "assistant",
        text,
        {
            "citations": citations,
            "actions": actions,
            "ui_actions": ui_actions,
            "tool_calls": aggregate["tool_calls"],
        },
    )
    return {
        "session_id": session_id,
        "assistant_message": {
            "id": assistant["id"],
            "text": text,
            "citations": citations,
            "actions": actions,
            "ui_actions": ui_actions,
            "confidence": confidence if confidence in {"grounded", "partial", "research_required"} else "partial",
        },
        "actions": actions,
        "ui_actions": ui_actions,
        "candidate_results": aggregate["candidate_results"],
        "updated_context": compact_session_context(controller.sessions.get_session(session_id)),
    }


