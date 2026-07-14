from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import os

from catalyst.agent.antigravity_core import antigravity_core_available, run_antigravity_agent_loop
from catalyst.agent.codex_core import codex_core_available, run_codex_agent_loop
from catalyst.agent.helpers import _empty_aggregate
from catalyst.agent.tool_exec import _assistant_response, _execute_tool
from catalyst.agent_loop import run_llm_agent_loop, run_local_agent_fallback
from catalyst.demo_scenarios import DemoScenario, iter_demo_events, scenario_for_prompt
from catalyst.session_store import compact_session_context


def _merge_live_workspace_context(
    existing: dict[str, Any],
    current_workspace: dict[str, Any],
) -> dict[str, Any]:
    """Merge UI live workspace into session context; live material wins over stale ids."""
    workspace_context = dict(existing or {})
    workspace_context.update(dict(current_workspace))
    mid = current_workspace.get("material_id") or current_workspace.get("resolved_material_id")
    if mid:
        workspace_context["current_material_id"] = mid
        workspace_context["last_focus_material_id"] = mid
        workspace_context["last_referenced_material_id"] = mid
        if current_workspace.get("formula_pretty"):
            workspace_context["formula_pretty"] = current_workspace["formula_pretty"]
    if current_workspace.get("project_id"):
        workspace_context["project_id"] = current_workspace["project_id"]
    if current_workspace.get("agent_surface"):
        workspace_context["agent_surface"] = current_workspace["agent_surface"]
    if current_workspace.get("rail_mode"):
        workspace_context["rail_mode"] = current_workspace["rail_mode"]
    return workspace_context


def _prepare_demo_session(
    controller: Any,
    *,
    session_id: str,
    message: str,
    current_workspace: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    session = controller.sessions.get_session(session_id) or controller.sessions.create_session(context=current_workspace or {})
    session_id = session["session_id"]
    if current_workspace:
        merged = _merge_live_workspace_context(session.get("context") or {}, current_workspace)
        controller.sessions.update_session(session_id, {"context": merged})
    controller.sessions.append_message(session_id, "user", message)
    aggregate = _empty_aggregate()
    _execute_tool(
        controller,
        session_id,
        "run_demo_scenario",
        {"scenario_id": "sunlight-dna"},
        aggregate,
    )
    return session_id, aggregate


def _demo_response(
    controller: Any,
    *,
    scenario: DemoScenario,
    session_id: str,
    message: str,
    current_workspace: dict[str, Any] | None,
) -> dict[str, Any]:
    """Non-stream compatibility path; the web client uses timed SSE playback."""
    session_id, aggregate = _prepare_demo_session(
        controller,
        session_id=session_id,
        message=message,
        current_workspace=current_workspace,
    )
    return _assistant_response(
        controller,
        session_id=session_id,
        text=scenario.final_brief,
        aggregate=aggregate,
        current_workspace=current_workspace,
        confidence="grounded",
        provider={"provider": "cached_demo", "model": scenario.scenario_id},
    )


class AgentToolsChatMixin:
    def local_chat(
        self,
        *,
        session_id: str,
        message: str,
        current_workspace: dict[str, Any] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        scenario = scenario_for_prompt(message)
        if scenario:
            return _demo_response(
                self,
                scenario=scenario,
                session_id=session_id,
                message=message,
                current_workspace=current_workspace,
            )
        session = self.sessions.get_session(session_id) or self.sessions.create_session(context=current_workspace or {})
        if session["session_id"] != session_id:
            session_id = session["session_id"]
        if current_workspace:
            workspace_context = _merge_live_workspace_context(session.get("context") or {}, current_workspace)
            self.sessions.update_session(session_id, {"context": workspace_context})
            session = self.sessions.get_session(session_id) or session
        attachment_metadata = [
            {"name": str(item.get("name") or "image"), "mime_type": str(item.get("mime_type") or "")}
            for item in (attachments or [])
        ]
        self.sessions.append_message(session_id, "user", message, {"attachments": attachment_metadata} if attachment_metadata else None)

        # Agent core routing:
        #   antigravity (default when available) ? Gemini native tool loop ? optional Codex ? degraded
        # Never delete the Gemini loop ? it is the reliable demo fallback.
        core_mode = (os.getenv("CATALYST_AGENT_CORE") or "antigravity").strip().lower()

        if core_mode in {"antigravity", "agy", "auto"} and antigravity_core_available():
            agy_response = run_antigravity_agent_loop(
                self,
                session_id=session_id,
                message=message,
                current_workspace=current_workspace,
                attachments=attachments,
                event_cb=None,
            )
            if agy_response:
                return agy_response

        if core_mode == "codex" and codex_core_available(self):
            codex_response = run_codex_agent_loop(
                self,
                session_id=session_id,
                message=message,
                current_workspace=current_workspace,
                event_cb=None,
            )
            if codex_response:
                return codex_response

        llm_response = run_llm_agent_loop(
            self,
            session_id=session_id,
            message=message,
            current_workspace=current_workspace,
            attachments=attachments,
            event_cb=None,
        )
        if llm_response:
            return llm_response

        # Degraded local tools only after all cores miss (set CATALYST_ALLOW_DEGRADED=0 to disable).
        allow_degraded = (os.getenv("CATALYST_ALLOW_DEGRADED") or "1").strip().lower() not in {"0", "false", "no"}
        if allow_degraded:
            fallback_response = run_local_agent_fallback(
                self,
                session_id=session_id,
                message=message,
                current_workspace=current_workspace,
            )
            if fallback_response:
                return fallback_response

        response_text = (
            "The Catalyst agent is unavailable (primary, backup, and offline paths all failed). "
            "Check agent credentials on the backend, or set CATALYST_AGENT_CORE=llm."
        )
        assistant = self.sessions.append_message(
            session_id,
            "assistant",
            response_text,
            {"citations": [], "actions": [], "ui_actions": [], "agent_error": "llm_tool_loop_unavailable"},
        )
        return {
            "session_id": session_id,
            "assistant_message": {
                "id": assistant["id"],
                "text": response_text,
                "citations": [],
                "actions": [],
                "ui_actions": [],
                "confidence": "partial",
            },
            "actions": [],
            "ui_actions": [],
            "candidate_results": None,
            "updated_context": compact_session_context(self.sessions.get_session(session_id)),
        }

    def local_chat_stream(
        self,
        *,
        session_id: str,
        message: str,
        current_workspace: dict[str, Any] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ):
        """Yield SSE-friendly event dicts: status / token / done / error."""
        scenario = scenario_for_prompt(message)
        if scenario:
            sid, aggregate = _prepare_demo_session(
                self,
                session_id=session_id,
                message=message,
                current_workspace=current_workspace,
            )
            try:
                for event in iter_demo_events(scenario):
                    yield event
                response = _assistant_response(
                    self,
                    session_id=sid,
                    text=scenario.final_brief,
                    aggregate=aggregate,
                    current_workspace=current_workspace,
                    confidence="grounded",
                    provider={"provider": "cached_demo", "model": scenario.scenario_id},
                )
                yield {"type": "done", "response": response}
            except GeneratorExit:
                return
            except Exception as exc:  # noqa: BLE001 - SSE boundary
                yield {"type": "error", "message": str(exc)}
            return
        import queue
        import threading

        events: queue.Queue = queue.Queue()

        def emit(event: dict[str, Any]) -> None:
            events.put(event)

        def worker() -> None:
            try:
                emit({"type": "status", "text": "Thinking?"})
                # Mirror local_chat prep without double-running tools when possible.
                session = self.sessions.get_session(session_id) or self.sessions.create_session(context=current_workspace or {})
                sid = session["session_id"]
                if current_workspace:
                    workspace_context = _merge_live_workspace_context(session.get("context") or {}, current_workspace)
                    self.sessions.update_session(sid, {"context": workspace_context})
                attachment_metadata = [
                    {"name": str(item.get("name") or "image"), "mime_type": str(item.get("mime_type") or "")}
                    for item in (attachments or [])
                ]
                self.sessions.append_message(
                    sid, "user", message, {"attachments": attachment_metadata} if attachment_metadata else None
                )

                core_mode = (os.getenv("CATALYST_AGENT_CORE") or "antigravity").strip().lower()
                if core_mode in {"antigravity", "agy", "auto"} and antigravity_core_available():
                    emit({"type": "status", "text": "Agent?"})
                    agy_response = run_antigravity_agent_loop(
                        self,
                        session_id=sid,
                        message=message,
                        current_workspace=current_workspace,
                        attachments=attachments,
                        event_cb=emit,
                    )
                    if agy_response:
                        emit({"type": "done", "response": agy_response})
                        return

                if core_mode == "codex" and codex_core_available(self):
                    emit({"type": "status", "text": "Codex core?"})
                    codex_response = run_codex_agent_loop(
                        self,
                        session_id=sid,
                        message=message,
                        current_workspace=current_workspace,
                        event_cb=emit,
                    )
                    if codex_response:
                        emit({"type": "done", "response": codex_response})
                        return

                emit({"type": "status", "text": "Thinking?"})
                llm_response = run_llm_agent_loop(
                    self,
                    session_id=sid,
                    message=message,
                    current_workspace=current_workspace,
                    attachments=attachments,
                    event_cb=emit,
                )
                if llm_response:
                    emit({"type": "done", "response": llm_response})
                    return

                allow_degraded = (os.getenv("CATALYST_ALLOW_DEGRADED") or "1").strip().lower() not in {"0", "false", "no"}
                if allow_degraded:
                    emit({"type": "status", "text": "Degraded local tools?"})
                    fallback_response = run_local_agent_fallback(
                        self,
                        session_id=sid,
                        message=message,
                        current_workspace=current_workspace,
                    )
                    if fallback_response:
                        text = str((fallback_response.get("assistant_message") or {}).get("text") or "")
                        for i in range(0, len(text), 32):
                            emit({"type": "token", "text": text[i : i + 32]})
                        emit({"type": "done", "response": fallback_response})
                        return

                response_text = (
                    "The Catalyst agent is unavailable (primary and backup paths both failed). "
                    "Check agent credentials on the backend, or set CATALYST_AGENT_CORE=llm."
                )
                assistant = self.sessions.append_message(
                    sid,
                    "assistant",
                    response_text,
                    {"citations": [], "actions": [], "ui_actions": [], "agent_error": "llm_tool_loop_unavailable"},
                )
                emit({"type": "token", "text": response_text})
                emit(
                    {
                        "type": "done",
                        "response": {
                            "session_id": sid,
                            "assistant_message": {
                                "id": assistant["id"],
                                "text": response_text,
                                "citations": [],
                                "actions": [],
                                "ui_actions": [],
                                "confidence": "partial",
                            },
                            "actions": [],
                            "ui_actions": [],
                            "candidate_results": None,
                            "updated_context": compact_session_context(self.sessions.get_session(sid)),
                        },
                    }
                )
            except Exception as exc:  # noqa: BLE001 ? stream boundary
                emit({"type": "error", "message": str(exc)})
            finally:
                events.put(None)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            item = events.get()
            if item is None:
                break
            yield item

