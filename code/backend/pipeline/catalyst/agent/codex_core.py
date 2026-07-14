"""Codex-as-core agent harness: RunContext + AGENTS + tools, multi-step TOOL_CALL loop."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from catalyst.agent.events import _emit
from catalyst.agent.helpers import _empty_aggregate, _message_requires_tool
from catalyst.agent.package import build_system_instruction, maybe_write_turn_trace
from catalyst.agent.registry import tools_markdown
from catalyst.agent.tool_exec import _assistant_response, _execute_tool

EventCallback = Any

_TOOL_CALL_RE = re.compile(
    r"TOOL_CALL:\s*(\{.*?\})(?:\s*$|\n)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)


def codex_core_available(controller: Any) -> bool:
    """SDK installed and a first-party Codex credential is present."""
    try:
        if not bool(controller.codex.status().get("available")):
            return False
    except Exception:
        return False
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("CATALYST_CODEX_API_KEY"))


def _workdir(controller: Any, current_workspace: dict[str, Any] | None) -> Path:
    workspace = current_workspace or {}
    project_id = workspace.get("project_id") or (workspace.get("context") or {}).get("project_id")
    if project_id:
        try:
            return controller.projects.project_path(str(project_id))
        except Exception:
            pass
    # Synthetic sandbox for materials-only chat so Codex has a cwd.
    path = Path(controller.repo_root).resolve() / "data" / "local" / "agent_workspace" / "default"
    path.mkdir(parents=True, exist_ok=True)
    readme = path / "README.md"
    if not readme.is_file():
        readme.write_text(
            "# Catalyst agent workspace\n\nCodex core working directory for materials chat without a project.\n",
            encoding="utf-8",
        )
    return path


def _session_thread_key(session_id: str) -> str:
    return f"codex_thread:{session_id}"


def _get_thread_id(controller: Any, session_id: str) -> str | None:
    session = controller.sessions.get_session(session_id) or {}
    ctx = session.get("context") or {}
    tid = ctx.get("codex_thread_id")
    return str(tid) if tid else None


def _set_thread_id(controller: Any, session_id: str, thread_id: str) -> None:
    controller.sessions.update_session(session_id, {"context": {"codex_thread_id": thread_id}})


def _parse_tool_calls(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in _TOOL_CALL_RE.finditer(text or ""):
        raw = match.group(1)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        name = payload.get("name") or payload.get("tool")
        args = payload.get("args") or payload.get("arguments") or {}
        if name:
            calls.append({"name": str(name), "args": args if isinstance(args, dict) else {}})
    return calls


def _strip_tool_calls(text: str) -> str:
    cleaned = _TOOL_CALL_RE.sub("", text or "").strip()
    return cleaned


def _build_codex_prompt(
    *,
    system_instruction: str,
    tools_md: str,
    user_message: str,
    tool_feedback: str | None = None,
) -> str:
    parts = [
        system_instruction,
        "",
        tools_md,
        "",
        "## Protocol",
        "You are the Catalyst workspace agent running inside the Codex harness.",
        "Use LIVE RunContext for the open material. Prefer Catalyst tools for local facts.",
        "For a request requiring Catalyst data, search, graph, selection, files, or UI actions, you MUST call a listed Catalyst tool before answering.",
        "Never claim a grounded property or UI change without the corresponding tool result.",
        "When you need a tool, output ONLY a line like:",
        'TOOL_CALL: {"name":"get_material_workspace","args":{"material_id":"mp-xxx"}}',
        "You may chain tools across turns. When finished, answer the user in markdown with no TOOL_CALL lines.",
        "",
        f"## User message\n{user_message}",
    ]
    if tool_feedback:
        parts.extend(["", "## Tool results (this turn)", tool_feedback])
    return "\n".join(parts)


def run_codex_agent_loop(
    controller: Any,
    *,
    session_id: str,
    message: str,
    current_workspace: dict[str, Any] | None,
    event_cb: EventCallback = None,
    max_iterations: int = 4,
) -> dict[str, Any] | None:
    if not codex_core_available(controller):
        return None

    session = controller.sessions.get_session(session_id)
    if not session:
        return None

    live_mid = str((current_workspace or {}).get("material_id") or "").strip()
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
            "codex": True,
            "web_search": bool(os.getenv("CATALYST_CODEX_NETWORK", "").strip() in {"1", "true", "yes"}),
            "research_literature": bool(getattr(controller.settings.research, "enabled", False)),
        },
        tool_markdown=tools_markdown(),
    )
    system_instruction = packaged["system_instruction"]
    turn_id = uuid4().hex[:12]
    maybe_write_turn_trace(
        controller.repo_root,
        turn_id=f"codex-{turn_id}",
        system_instruction=system_instruction,
        run_context=packaged["run_context"],
    )

    workdir = _workdir(controller, current_workspace)
    thread_id = _get_thread_id(controller, session_id)
    tools_md = tools_markdown()
    aggregate = _empty_aggregate()
    requires_tool = _message_requires_tool(message, current_workspace)
    user_message = message
    tool_feedback: str | None = None
    final_text = ""
    model = os.getenv("CATALYST_CODEX_MODEL") or "gpt-5.4-mini"
    effort = os.getenv("CATALYST_CODEX_EFFORT", "medium")

    _emit(event_cb, {"type": "status", "text": "Codex core?"})

    for iteration in range(max(1, max_iterations)):
        prompt = _build_codex_prompt(
            system_instruction=system_instruction,
            tools_md=tools_md,
            user_message=user_message,
            tool_feedback=tool_feedback,
        )
        _emit(event_cb, {"type": "status", "text": f"Codex step {iteration + 1}?"})
        try:
            result = controller.codex.run(
                project_path=workdir,
                prompt=prompt,
                thread_id=thread_id,
                model=model,
                reasoning_effort=effort,
            )
        except Exception as exc:  # noqa: BLE001
            _emit(event_cb, {"type": "status", "text": f"Codex error: {exc}"})
            return None

        thread_id = str(result.get("threadId") or thread_id or "")
        if thread_id:
            _set_thread_id(controller, session_id, thread_id)

        text = str(result.get("finalResponse") or "").strip()
        if not text:
            _emit(event_cb, {"type": "status", "text": "Codex returned no usable response; falling back?"})
            return None
        calls = _parse_tool_calls(text)
        if not calls:
            if requires_tool and not aggregate["tool_calls"]:
                _emit(event_cb, {"type": "status", "text": "Codex skipped a required Catalyst tool; falling back?"})
                return None
            final_text = _strip_tool_calls(text) or text
            break

        # Execute tools and continue
        feedback_parts: list[str] = []
        for call in calls[:6]:
            name = call.get("name")
            args = call.get("args") or {}
            _emit(event_cb, {"type": "status", "text": f"Tool: {name}?"})
            try:
                out = _execute_tool(controller, session_id, name, args, aggregate)
            except Exception as exc:  # noqa: BLE001
                out = {"ok": False, "error": str(exc)}
            compact = json.dumps(out, default=str)[:6000]
            feedback_parts.append(f"### {name}\n```json\n{compact}\n```")
        tool_feedback = "\n\n".join(feedback_parts)
        user_message = message  # keep original ask; tools in feedback
        final_text = _strip_tool_calls(text)

    if not final_text.strip():
        _emit(event_cb, {"type": "status", "text": "Codex did not finish; falling back?"})
        return None

    # Stream-like token emit for SSE clients
    chunk = 48
    for i in range(0, len(final_text), chunk):
        _emit(event_cb, {"type": "token", "text": final_text[i : i + chunk]})

    return _assistant_response(
        controller,
        session_id=session_id,
        text=final_text,
        aggregate=aggregate,
        current_workspace=current_workspace,
        confidence="grounded" if aggregate.get("tool_calls") else "partial",
        provider={"provider": "codex", "model": model or "codex-default", "thread_id": thread_id},
    )
