from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from catalyst.agent.events import _emit, _friendly_tool_status, _short_error
from catalyst.agent.helpers import (
    _dynamic_context,
    _empty_aggregate,
    _extract_text_from_content,
    _gemini_attachment_parts,
    _is_identity_or_viewport_query,
    _is_select_or_open_command,
    _message_requires_tool,
    _open_material_id,
    _parse_json_object,
    _recent_session_text,
    _refers_to_open_material,
    _session_contents,
)
from catalyst.agent.package import build_system_instruction, maybe_write_turn_trace
from catalyst.agent.tool_exec import _assistant_response, _compact_tool_result, _execute_tool
from catalyst.agent.tools_decl import TOOL_DECLARATIONS
from catalyst.providers.gemini import GeminiProviderError, generate_gemini_agent_turn
from catalyst.providers.openai_compatible import (
    OpenAICompatibleProviderError,
    generate_openai_compatible_text,
    stream_openai_compatible_text,
)
from catalyst.providers.registry import DEFAULT_MODELS, resolve_active_provider

EventCallback = Any

def run_llm_agent_loop(
    controller: Any,
    *,
    session_id: str,
    message: str,
    current_workspace: dict[str, Any] | None,
    attachments: list[dict[str, Any]] | None = None,
    event_cb: EventCallback = None,
) -> dict[str, Any] | None:
    active_provider = resolve_active_provider(controller.settings)
    if not active_provider:
        _emit(event_cb, {"type": "status", "text": "No LLM provider configured?"})
        return None

    # Keep request-scoped resolution even when settings.active_provider is null.
    controller.settings.providers.active_provider = active_provider

    session = controller.sessions.get_session(session_id)
    if not session:
        _emit(event_cb, {"type": "status", "text": "Session missing?"})
        return None

    # Align session focus with UI live material before building RunContext.
    live_mid = str(
        (current_workspace or {}).get("material_id")
        or (current_workspace or {}).get("resolved_material_id")
        or ""
    ).strip()
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

    # Phase 1: editable package + in-memory RunContext (not global compiled_context.md).
    codex_ok = False
    try:
        codex_ok = bool(controller.codex.status().get("available"))
    except Exception:
        codex_ok = False
    packaged = build_system_instruction(
        controller.repo_root,
        session=session,
        current_workspace=current_workspace,
        capabilities={
            "local_materials": True,
            "codex": codex_ok,
            "web_search": False,
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
    # Keep dynamic helper for any code that still expects session-shaped context.
    _ = _dynamic_context(session, current_workspace)

    model = (
        controller.settings.providers.models.get(active_provider)
        or DEFAULT_MODELS.get(active_provider)
        or "gemini-2.5-flash"
    )
    # OpenAI-compatible gateways (micro/self-host) use the JSON tool loop.
    use_native_tools = active_provider == "gemini" and not model.removeprefix("models/").startswith("gemma-")

    try:
        _emit(event_cb, {"type": "status", "text": "Thinking?"})
        if use_native_tools:
            return _run_native_gemini_loop(
                controller,
                session_id=session_id,
                system_instruction=system_instruction,
                current_workspace=current_workspace,
                attachments=attachments,
                event_cb=event_cb,
            )
        return _run_json_tool_loop(
            controller,
            session_id=session_id,
            message=message,
            system_instruction=system_instruction,
            current_workspace=current_workspace,
            event_cb=event_cb,
        )
    except (GeminiProviderError, OpenAICompatibleProviderError) as exc:
        _emit(event_cb, {"type": "status", "text": f"Provider error: {_short_error(exc)}"})
        return None
    except (OSError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        _emit(event_cb, {"type": "status", "text": f"Agent error: {_short_error(exc)}"})
        return None


def _run_native_gemini_loop(
    controller: Any,
    *,
    session_id: str,
    system_instruction: str,
    current_workspace: dict[str, Any] | None,
    attachments: list[dict[str, Any]] | None,
    event_cb: EventCallback = None,
) -> dict[str, Any] | None:
    contents = _session_contents(controller.sessions.get_session(session_id))
    attachment_parts = _gemini_attachment_parts(attachments or [])
    if attachment_parts and contents and contents[-1].get("role") == "user":
        contents[-1].setdefault("parts", []).extend(attachment_parts)
    tools = [{"functionDeclarations": TOOL_DECLARATIONS}]
    aggregate = _empty_aggregate()
    model_content: dict[str, Any] | None = None

    max_turns = int(controller.agent_runtime.get("context", {}).get("runtime", {}).get("max_tool_iterations") or 4)
    for _ in range(max(1, max_turns)):
        _emit(event_cb, {"type": "status", "text": "Thinking?"})
        turn = generate_gemini_agent_turn(
            controller.settings,
            contents=contents,
            system_instruction=system_instruction,
            tools=tools,
            temperature=0.2,
            max_output_tokens=1024,
        )
        model_content = turn.get("content")
        calls = turn.get("function_calls") or []
        if not calls:
            text = turn.get("text") or "I could not produce a grounded answer from the current context."
            _stream_final_text(event_cb, str(text))
            return _assistant_response(
                controller,
                session_id=session_id,
                text=str(text),
                aggregate=aggregate,
                current_workspace=current_workspace,
                confidence="grounded" if aggregate["tool_calls"] else "partial",
                provider={"provider": "gemini", "model": turn.get("model"), "usage": turn.get("usage") or {}},
            )
        if model_content:
            contents.append(model_content)
        response_parts = []
        for call in calls:
            tool_name = call.get("name")
            tool_args = call.get("args") or {}
            _emit(event_cb, {"type": "status", "text": _friendly_tool_status(tool_name, tool_args if isinstance(tool_args, dict) else {})})
            result = _execute_tool(controller, session_id, tool_name, tool_args if isinstance(tool_args, dict) else {}, aggregate)
            response = {"result": _compact_tool_result(result)}
            function_response = {"name": tool_name, "response": response}
            if call.get("id"):
                function_response["id"] = call["id"]
            response_parts.append({"functionResponse": function_response})
        contents.append({"role": "user", "parts": response_parts})

    if model_content:
        text = _extract_text_from_content(model_content)
        if text:
            _stream_final_text(event_cb, text)
            return _assistant_response(
                controller,
                session_id=session_id,
                text=text,
                aggregate=aggregate,
                current_workspace=current_workspace,
                confidence="grounded" if aggregate["tool_calls"] else "partial",
            )
    return None


def _run_json_tool_loop(
    controller: Any,
    *,
    session_id: str,
    message: str,
    system_instruction: str,
    current_workspace: dict[str, Any] | None,
    event_cb: EventCallback = None,
) -> dict[str, Any] | None:
    session = controller.sessions.get_session(session_id)
    aggregate = _empty_aggregate()
    open_mid = _open_material_id(current_workspace)
    plan_prompt = (
        f"{system_instruction}\n\n"
        "You are the Catalyst LLM agent. Decide what tools to call before answering. "
        "Return ONLY JSON with this shape:\n"
        '{"tool_calls":[{"name":"screen_candidates","args":{"requirement":"..."}}],'
        '"respond_directly":{"text":"...","confidence":"partial"}}\n'
        "Use tool_calls for material properties, graph, search, screening, selection, comparison, export, or research. "
        "If LIVE RunContext has an open material and the user asks what they are looking at / identity, "
        "you MAY use respond_directly with formula + material_id from RunContext (do not invent other materials). "
        "For density/spacegroup/band gap of the open material, call get_material_workspace with that material_id. "
        "Never call screen_candidates for identity/viewport questions when an open material is already set.\n\n"
        f"Recent session:\n{_recent_session_text(session, limit=16)}\n\n"
        f"Current user message: {message}"
    )
    _emit(event_cb, {"type": "status", "text": "Planning which tools to use?"})
    plan_turn = _generate_text_turn(
        controller,
        prompt=plan_prompt,
        system_instruction=system_instruction,
        temperature=0.1,
        max_output_tokens=768,
    )
    plan = _parse_json_object(plan_turn.get("text") or "")
    for call in plan.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        tool_name = call.get("name")
        tool_args = call.get("args") if isinstance(call.get("args"), dict) else {}
        # Block screener on identity/viewport when live material is open.
        if (
            tool_name == "screen_candidates"
            and open_mid
            and _is_identity_or_viewport_query(message)
        ):
            continue
        # For open/select commands, force local formula?id resolve (no hallucinated mp-ids).
        if tool_name in {"select_material", "get_material_workspace", "resolve_material"} and _is_select_or_open_command(
            message
        ):
            try:
                grounded = controller._resolve_material_reference(message)
            except Exception:
                grounded = None
            if grounded:
                if tool_name == "resolve_material":
                    tool_args = {**tool_args, "query": grounded, "material_id": grounded}
                else:
                    tool_args = {**tool_args, "material_id": grounded, "open_inspector": True}
        _emit(event_cb, {"type": "status", "text": _friendly_tool_status(tool_name, tool_args)})
        _execute_tool(controller, session_id, tool_name, tool_args, aggregate)

    # Auto-ground open-material property/identity if model forgot tools.
    # Never do this for "open cds" / select-other-material commands.
    if (
        not aggregate["tool_calls"]
        and open_mid
        and not _is_select_or_open_command(message)
        and (
            _is_identity_or_viewport_query(message)
            or (
                _refers_to_open_material(message, current_workspace)
                and _message_requires_tool(message, current_workspace)
            )
        )
    ):
        _emit(event_cb, {"type": "status", "text": _friendly_tool_status("get_material_workspace", {"material_id": open_mid})})
        _execute_tool(
            controller,
            session_id,
            "get_material_workspace",
            {"material_id": open_mid},
            aggregate,
        )

    # Open/select commands: always ground on local resolve ? models invent mp-ids.
    if _is_select_or_open_command(message):
        resolved = None
        try:
            resolved = controller._resolve_material_reference(message)
        except Exception:
            resolved = None
        if not resolved:
            for tr in aggregate.get("tool_results") or []:
                if not isinstance(tr, dict) or tr.get("tool") != "resolve_material":
                    continue
                res = tr.get("result") or {}
                if res.get("ok") and res.get("material_id"):
                    resolved = str(res["material_id"])
                    break
        select_ok = False
        for tr in aggregate.get("tool_results") or []:
            if not isinstance(tr, dict) or tr.get("tool") != "select_material":
                continue
            res = tr.get("result") or {}
            if res.get("ok"):
                select_ok = True
                break
        if resolved and not select_ok:
            _emit(
                event_cb,
                {"type": "status", "text": _friendly_tool_status("select_material", {"material_id": resolved})},
            )
            _execute_tool(
                controller,
                session_id,
                "select_material",
                {"material_id": resolved, "open_inspector": True},
                aggregate,
            )

    if not aggregate["tool_calls"]:
        direct = plan.get("respond_directly") or {}
        text = direct.get("text") if isinstance(direct, dict) else None
        # Accept direct answers for greetings / viewport identity; only hard-fail true tool needs.
        if text and not _message_requires_tool(message, current_workspace):
            _stream_final_text(event_cb, str(text))
            return _assistant_response(
                controller,
                session_id=session_id,
                text=str(text),
                aggregate=aggregate,
                current_workspace=current_workspace,
                confidence="partial",
                provider={"provider": plan_turn.get("provider") or "llm", "model": plan_turn.get("model"), "usage": plan_turn.get("usage") or {}},
            )
        if _message_requires_tool(message, current_workspace):
            return None
        if text:
            _stream_final_text(event_cb, str(text))
            return _assistant_response(
                controller,
                session_id=session_id,
                text=str(text),
                aggregate=aggregate,
                current_workspace=current_workspace,
                confidence="partial",
                provider={"provider": plan_turn.get("provider") or "llm", "model": plan_turn.get("model"), "usage": plan_turn.get("usage") or {}},
            )
        return None

    # Prefer plain markdown when streaming so clients can render live.
    final_prompt = (
        f"{system_instruction}\n\n"
        "You called tools. Now write the final Catalyst answer in markdown only "
        "(no JSON wrapper). Use clear headings when useful. Be concise and cite only tool-grounded facts.\n\n"
        f"User message: {message}\n\nTool results:\n{json.dumps(aggregate['tool_results'], indent=2, sort_keys=True)}"
    )
    _emit(event_cb, {"type": "status", "text": "Writing answer?"})
    text, provider_meta = _generate_or_stream_final(
        controller,
        prompt=final_prompt,
        system_instruction=system_instruction,
        temperature=0.2,
        max_output_tokens=1024,
        event_cb=event_cb,
    )
    if not text:
        return None
    return _assistant_response(
        controller,
        session_id=session_id,
        text=str(text).strip(),
        aggregate=aggregate,
        current_workspace=current_workspace,
        confidence="grounded",
        provider=provider_meta,
    )


def _stream_final_text(event_cb: EventCallback, text: str, *, chunk_size: int = 28) -> None:
    """Progressive token-like emits when true provider streaming isn't available."""
    if not text:
        return
    _emit(event_cb, {"type": "status", "text": "Writing answer?"})
    for i in range(0, len(text), chunk_size):
        _emit(event_cb, {"type": "token", "text": text[i : i + chunk_size]})


def _generate_or_stream_final(
    controller: Any,
    *,
    prompt: str,
    system_instruction: str,
    temperature: float,
    max_output_tokens: int,
    event_cb: EventCallback = None,
) -> tuple[str, dict[str, Any]]:
    provider = resolve_active_provider(controller.settings) or "gemini"
    if provider != "gemini":
        try:
            pieces: list[str] = []
            for delta in stream_openai_compatible_text(
                controller.settings,
                provider=provider,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            ):
                pieces.append(delta)
                _emit(event_cb, {"type": "token", "text": delta})
            text = "".join(pieces).strip()
            if text:
                return text, {
                    "provider": provider,
                    "model": controller.settings.providers.models.get(provider) or DEFAULT_MODELS.get(provider),
                }
        except OpenAICompatibleProviderError:
            pass
    turn = _generate_text_turn(
        controller,
        prompt=prompt,
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    text = str(turn.get("text") or "").strip()
    _stream_final_text(event_cb, text)
    return text, {
        "provider": turn.get("provider") or provider,
        "model": turn.get("model"),
        "usage": turn.get("usage") or {},
    }


def _generate_text_turn(
    controller: Any,
    *,
    prompt: str,
    system_instruction: str,
    temperature: float,
    max_output_tokens: int,
) -> dict[str, Any]:
    provider = resolve_active_provider(controller.settings) or "gemini"
    if provider == "gemini":
        return generate_gemini_agent_turn(
            controller.settings,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    return generate_openai_compatible_text(
        controller.settings,
        provider=provider,
        prompt=prompt,
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


