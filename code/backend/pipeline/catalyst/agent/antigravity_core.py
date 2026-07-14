"""Antigravity as Catalyst chat core.

Primary: AGY CLI (Google OAuth / subscription models) with Catalyst tools via
TOOL_CALL protocol. Secondary: Interactions API (GEMINI_API_KEY) with native
function tools. Caller still falls back to Gemini LLM loop if both miss.
"""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import uuid4

from catalyst.agent.events import _emit, _friendly_tool_status, _short_error
from catalyst.agent.helpers import (
    _empty_aggregate,
    _is_select_or_open_command,
    _open_material_id,
)
from catalyst.agent.package import build_system_instruction, maybe_write_turn_trace
from catalyst.agent.tool_exec import _assistant_response, _compact_tool_result, _execute_tool
from catalyst.agent.tools_decl import MODEL_TOOL_DECLARATIONS

EventCallback = Any

# Tools exposed to Antigravity. Full registry minus nothing critical; shell is allowlisted.
# Exclude nothing from CORE ? P2 uses almost all decls; skip only if empty name.
CORE_TOOL_NAMES: set[str] | None = None  # None => all provider-visible declarations

DEFAULT_AGENT = "antigravity-preview-05-2026"
MAX_TOOL_ROUNDS = 8

# AGY subscription-style profiles (UI model picker). Effort is instruction-side ?
# managed agent API does not accept model+generation_config together.
AGY_PROFILE_EFFORT = {
    "agy/3.5-flash-low": "low",
    "agy/3.5-flash-medium": "medium",
    "agy/3.5-flash-high": "high",
    "agy/3.1-pro-low": "low",
    "agy/3.1-pro-high": "high",
    "agy/claude-sonnet-thinking": "high",
    "agy/claude-opus-thinking": "high",
}


def antigravity_core_available() -> bool:
    """True when Interactions API key works and/or local `agy` CLI is available."""
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if key:
        try:
            from google import genai  # noqa: F401

            client = _client()
            if getattr(client, "interactions", None):
                return True
        except Exception:
            pass
    try:
        from catalyst.agent.agy_cli_transport import agy_cli_available

        return agy_cli_available()
    except Exception:
        return False


def _client():
    from google import genai

    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    return genai.Client(api_key=key)


def _agent_name() -> str:
    return (os.getenv("CATALYST_ANTIGRAVITY_AGENT") or DEFAULT_AGENT).strip() or DEFAULT_AGENT


def _tools_payload() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    allowed = CORE_TOOL_NAMES
    for decl in MODEL_TOOL_DECLARATIONS:
        name = str(decl.get("name") or "")
        if not name:
            continue
        if allowed is not None and name not in allowed:
            continue
        tools.append(
            {
                "type": "function",
                "name": name,
                "description": decl.get("description") or name,
                "parameters": decl.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    # Built-in Google search helps literature-ish questions without replacing local tools.
    tools.append({"type": "google_search"})
    tools.append({"type": "url_context"})
    return tools


def _effort_from_workspace(current_workspace: dict[str, Any] | None, settings: Any) -> str:
    ws = current_workspace or {}
    effort = str(ws.get("agent_effort") or ws.get("effort") or "").strip().lower()
    if effort in {"minimal", "low", "medium", "high"}:
        return effort
    # Model profile from settings (agy/3.5-flash-high etc.)
    try:
        models = getattr(getattr(settings, "providers", None), "models", None) or {}
        profile = str(models.get("gemini") or models.get("antigravity") or "")
    except Exception:
        profile = ""
    if profile in AGY_PROFILE_EFFORT:
        return AGY_PROFILE_EFFORT[profile]
    if "high" in profile:
        return "high"
    if "low" in profile or "minimal" in profile:
        return "low"
    return (os.getenv("CATALYST_AGENT_EFFORT") or "medium").strip().lower() or "medium"


def _step_type(step: Any) -> str:
    return str(getattr(step, "type", None) or (step.get("type") if isinstance(step, dict) else "") or "")


def _step_get(step: Any, key: str, default: Any = None) -> Any:
    if isinstance(step, dict):
        return step.get(key, default)
    return getattr(step, key, default)


def _pending_function_calls(interaction: Any) -> list[Any]:
    steps = list(getattr(interaction, "steps", None) or [])
    executed: set[str] = set()
    for step in steps:
        if _step_type(step) == "function_result":
            cid = _step_get(step, "call_id") or _step_get(step, "id")
            if cid:
                executed.add(str(cid))
    pending: list[Any] = []
    for step in steps:
        if _step_type(step) != "function_call":
            continue
        cid = str(_step_get(step, "id") or "")
        if cid and cid in executed:
            continue
        pending.append(step)
    return pending


def _args_dict(step: Any) -> dict[str, Any]:
    raw = _step_get(step, "arguments") or _step_get(step, "args") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    return dict(raw) if isinstance(raw, dict) else {}


def _normalize_tool_args(name: str, args: dict[str, Any], message: str, controller: Any) -> dict[str, Any]:
    """Ground select/open commands on local resolve ? block hallucinated mp-ids."""
    payload = dict(args or {})
    if name in {"select_material", "get_material_workspace", "get_neighborhood", "get_material_structure", "get_material_details"}:
        if _is_select_or_open_command(message) or not payload.get("material_id"):
            try:
                grounded = controller._resolve_material_reference(message)
            except Exception:
                grounded = None
            if not grounded and payload.get("material_id"):
                try:
                    grounded = controller._resolve_material_reference(str(payload.get("material_id")))
                except Exception:
                    grounded = None
            if grounded:
                payload["material_id"] = grounded
                if name == "select_material":
                    payload.setdefault("open_inspector", True)
    if name == "resolve_material" and not payload.get("query"):
        payload["query"] = message
    return payload


def _compact_for_model(result: Any) -> Any:
    try:
        return _compact_tool_result(result)
    except Exception:
        if isinstance(result, dict):
            return {k: v for k, v in result.items() if k not in {"material", "graph"}}
        return result


def run_antigravity_agent_loop(
    controller: Any,
    *,
    session_id: str,
    message: str,
    current_workspace: dict[str, Any] | None,
    attachments: list[dict[str, Any]] | None = None,
    event_cb: EventCallback = None,
) -> dict[str, Any] | None:
    """Run Antigravity managed agent with Catalyst tools. Return None to fall back."""
    if not antigravity_core_available():
        return None

    session = controller.sessions.get_session(session_id)
    if not session:
        _emit(event_cb, {"type": "status", "text": "Session missing?"})
        return None

    live_mid = _open_material_id(current_workspace)
    if live_mid:
        controller.sessions.update_session(
            session_id,
            {
                "context": {
                    "current_material_id": live_mid,
                    "last_focus_material_id": live_mid,
                    "last_referenced_material_id": live_mid,
                    "last_focus_mode": "live_viewport",
                    "formula_pretty": (current_workspace or {}).get("formula_pretty"),
                }
            },
        )
        session = controller.sessions.get_session(session_id) or session

    packaged = build_system_instruction(
        controller.repo_root,
        session=session,
        current_workspace=current_workspace,
        capabilities={
            "local_materials": True,
            "codex": False,
            "antigravity": True,
            "web_search": True,
            "research_literature": bool(getattr(controller.settings.research, "enabled", False)),
        },
    )
    system_instruction = packaged["system_instruction"]
    turn_id = uuid4().hex[:12]
    maybe_write_turn_trace(
        controller.repo_root,
        turn_id=turn_id,
        system_instruction=system_instruction,
        run_context=packaged["run_context"],
    )

    effort = _effort_from_workspace(current_workspace, getattr(controller, "settings", None))
    effort_line = {
        "minimal": "Operate at MINIMAL effort: few tools, shortest answer.",
        "low": "Operate at LOW effort: prefer 1?2 tools, be concise.",
        "medium": "Operate at MEDIUM effort: thorough but efficient tool use.",
        "high": "Operate at HIGH effort: multi-step tools, careful verification, complete UI actions.",
    }.get(effort, "Operate at MEDIUM effort.")

    # Interactions agents take system guidance in the user input envelope for now.
    user_blob = (
        f"{system_instruction}\n\n"
        "You are the Catalyst workspace agent. "
        f"{effort_line} "
        "Use Catalyst tools for local materials facts and UI actions. "
        "Never invent material ids. Prefer LIVE RunContext for the open material. "
        "For neighborhood questions call get_neighborhood (switches Neighbors tab). "
        "For open/select call select_material after resolve_material. "
        "You may use run_allowlisted_shell only for safe listed commands.\n\n"
        f"User message:\n{message}"
    )

    tools = _tools_payload()
    aggregate = _empty_aggregate()

    profile = str((current_workspace or {}).get("agent_model_profile") or "")
    # OAuth AGY CLI is primary (subscription quota + models). API is secondary.
    transport_pref = (os.getenv("CATALYST_AGENT_TRANSPORT") or "").strip().lower()
    force_cli = transport_pref in {"agy_cli", "cli", "oauth"}
    force_api = transport_pref in {"api", "interactions", "antigravity_api", "gemini_api"}
    prefer_cli_raw = (os.getenv("CATALYST_PREFER_AGY_CLI") or "1").strip().lower()
    prefer_cli = prefer_cli_raw not in {"0", "false", "no", "off"}

    try:
        from catalyst.agent.agy_cli_transport import agy_cli_available

        cli_ok = agy_cli_available()
    except Exception:
        cli_ok = False

    from catalyst.agent.agy_cli_transport import display_model_label as _display_model_label

    oauth_display = _display_model_label(profile, effort)

    use_cli_first = cli_ok and not force_api and (force_cli or prefer_cli)
    if use_cli_first:
        text = _run_agy_cli_tool_loop(
            controller,
            session_id=session_id,
            message=message,
            user_blob=user_blob,
            aggregate=aggregate,
            current_workspace=current_workspace,
            event_cb=event_cb,
            effort=effort,
        )
        if text:
            return _finish(
                controller,
                session_id,
                text,
                aggregate,
                current_workspace,
                event_cb,
                transport="subscription",
                agent=oauth_display,
            )
        _emit(event_cb, {"type": "status", "text": "Primary model miss ? trying backup path?"})

    client_ok = bool((os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip())
    if not client_ok:
        # Last chance CLI if we skipped it (force_api) or it wasn't first
        if cli_ok and not use_cli_first:
            text = _run_agy_cli_tool_loop(
                controller,
                session_id=session_id,
                message=message,
                user_blob=user_blob,
                aggregate=aggregate,
                current_workspace=current_workspace,
                event_cb=event_cb,
                effort=effort,
            )
            if text:
                return _finish(
                    controller,
                    session_id,
                    text,
                    aggregate,
                    current_workspace,
                    event_cb,
                    transport="subscription",
                    agent=oauth_display,
                )
        return None

    client = _client()
    agent = _agent_name()

    try:
        _emit(event_cb, {"type": "status", "text": "Agent?"})
        interaction = client.interactions.create(
            agent=agent,
            input=user_blob,
            tools=tools,
            environment="remote",
        )
    except Exception as exc:
        _emit(event_cb, {"type": "status", "text": f"Agent path unavailable: {_short_error(exc)}"})
        if cli_ok and not use_cli_first:
            text = _run_agy_cli_tool_loop(
                controller,
                session_id=session_id,
                message=message,
                user_blob=user_blob,
                aggregate=aggregate,
                current_workspace=current_workspace,
                event_cb=event_cb,
                effort=effort,
            )
            if text:
                return _finish(
                    controller,
                    session_id,
                    text,
                    aggregate,
                    current_workspace,
                    event_cb,
                    transport="subscription",
                    agent=oauth_display,
                )
        return None

    # Multi-step tool loop (Interactions API)
    for _round in range(MAX_TOOL_ROUNDS):
        status = str(getattr(interaction, "status", "") or "")
        interaction_id = getattr(interaction, "id", None)
        environment_id = getattr(interaction, "environment_id", None)

        if interaction_id or environment_id:
            controller.sessions.update_session(
                session_id,
                {
                    "context": {
                        "antigravity_interaction_id": interaction_id,
                        "antigravity_environment_id": environment_id,
                    }
                },
            )

        if status in {"completed", "done", "complete"}:
            break
        if status not in {"requires_action", "in_progress"}:
            break

        pending = _pending_function_calls(interaction)
        if not pending:
            break

        result_inputs: list[dict[str, Any]] = []
        for step in pending:
            name = str(_step_get(step, "name") or "")
            call_id = str(_step_get(step, "id") or "")
            args = _normalize_tool_args(name, _args_dict(step), message, controller)
            _emit(event_cb, {"type": "status", "text": _friendly_tool_status(name, args)})
            try:
                result = _execute_tool(controller, session_id, name, args, aggregate)
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
            result_inputs.append(
                {
                    "type": "function_result",
                    "name": name,
                    "call_id": call_id,
                    "result": _compact_for_model(result),
                }
            )

        try:
            interaction = client.interactions.create(
                agent=agent,
                previous_interaction_id=str(interaction_id),
                environment=str(environment_id or "remote"),
                tools=tools,
                input=result_inputs,
            )
        except Exception as exc:
            _emit(event_cb, {"type": "status", "text": f"Tool round failed: {_short_error(exc)}"})
            break

    text = str(getattr(interaction, "output_text", None) or "").strip()
    if not text and aggregate["tool_results"]:
        last = aggregate["tool_results"][-1]
        text = f"Completed tool `{last.get('tool')}` with local Catalyst data."
    if not text:
        return None

    return _finish(
        controller,
        session_id,
        text,
        aggregate,
        current_workspace,
        event_cb,
        transport="api",
        agent=_display_model_label(profile, effort),
        interaction=interaction,
    )


def _finish(
    controller: Any,
    session_id: str,
    text: str,
    aggregate: dict[str, Any],
    current_workspace: dict[str, Any] | None,
    event_cb: EventCallback,
    *,
    transport: str,
    agent: str | None = None,
    interaction: Any = None,
) -> dict[str, Any]:
    _emit(event_cb, {"type": "status", "text": "Writing answer?"})
    chunk = 40
    for i in range(0, len(text), chunk):
        _emit(event_cb, {"type": "token", "text": text[i : i + chunk]})
    provider = {
        "provider": "catalyst",
        "transport": transport,
        "model": agent or "Agent",
        "interaction_id": getattr(interaction, "id", None) if interaction is not None else None,
        "environment_id": getattr(interaction, "environment_id", None) if interaction is not None else None,
    }
    return _assistant_response(
        controller,
        session_id=session_id,
        text=text,
        aggregate=aggregate,
        current_workspace=current_workspace,
        confidence="grounded" if aggregate["tool_calls"] else "partial",
        provider=provider,
    )


def _run_agy_cli_tool_loop(
    controller: Any,
    *,
    session_id: str,
    message: str,
    user_blob: str,
    aggregate: dict[str, Any],
    current_workspace: dict[str, Any] | None,
    event_cb: EventCallback,
    effort: str,
) -> str | None:
    """OAuth subscription path via local `agy` (Google desktop login). Primary transport."""
    from catalyst.agent.agy_cli_transport import (
        build_tool_protocol_block,
        known_tool_names,
        parse_tool_calls,
        resolve_agy_model,
        run_agy_print,
        strip_tool_call_noise,
    )

    profile = str((current_workspace or {}).get("agent_model_profile") or "")
    from catalyst.agent.agy_cli_transport import display_model_label

    model = resolve_agy_model(profile, effort)
    display = display_model_label(profile, effort)
    _emit(event_cb, {"type": "status", "text": f"Agent ? {display}?"})

    allowed = known_tool_names(MODEL_TOOL_DECLARATIONS)
    protocol = build_tool_protocol_block(MODEL_TOOL_DECLARATIONS)
    prompt = f"{user_blob}\n\n{protocol}\n\nUser request again for focus:\n{message}"
    cont = False
    final_text = ""

    for _round_i in range(MAX_TOOL_ROUNDS):
        result = run_agy_print(prompt, model=model, continue_conversation=cont, timeout_sec=180)
        cont = True
        if result.get("auth_error"):
            _emit(
                event_cb,
                {
                    "type": "status",
                    "text": "Desktop agent login expired ? open a terminal, run `agy`, sign in there?",
                },
            )
            return None
        if not result.get("ok") and not result.get("text"):
            _emit(event_cb, {"type": "status", "text": f"Agent failed: {result.get('error') or 'no output'}"})
            return None
        text = str(result.get("text") or "")
        calls = parse_tool_calls(text, allowed=allowed)
        if not calls:
            final_text = strip_tool_call_noise(text) or text.strip()
            return final_text or None

        tool_blocks: list[str] = []
        for call in calls:
            name = str(call.get("name") or "")
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            args = _normalize_tool_args(name, args, message, controller)
            _emit(event_cb, {"type": "status", "text": _friendly_tool_status(name, args)})
            try:
                tool_result = _execute_tool(controller, session_id, name, args, aggregate)
            except Exception as exc:
                tool_result = {"ok": False, "error": str(exc)}
            tool_blocks.append(
                f"TOOL_RESULT {name}:\n{json.dumps(_compact_for_model(tool_result), indent=2, default=str)[:8000]}"
            )
        prompt = (
            "Tool results for your previous TOOL_CALL(s):\n\n"
            + "\n\n".join(tool_blocks)
            + "\n\n"
            + protocol
            + "\n\nContinue: emit more TOOL_CALL lines if needed, else final markdown answer only (no TOOL_CALL)."
        )

    return final_text or None
