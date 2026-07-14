"""Catalyst live voice bridge ? browser WS ? cloud Live API + local tools."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib.parse import quote

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from catalyst.agent.events import _friendly_tool_status
from catalyst.agent.helpers import _compact_tool_result, _dynamic_context, _empty_aggregate
from catalyst.agent.tool_exec import _execute_tool
from catalyst.agent.tools_decl import TOOL_DECLARATIONS
from catalyst.agent_runtime import write_compiled_agent_context
from catalyst.settings import PROVIDER_ENV_KEYS


# Prefer models known to complete setup on v1beta Live (probe-verified order).
DEFAULT_LIVE_MODELS = (
    "gemini-2.5-flash-native-audio-preview-12-2025",
    "gemini-2.0-flash-live-001",
    "gemini-live-2.5-flash-preview",
    "gemini-3.1-flash-live-preview",
)
GEMINI_LIVE_WS = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)

LIVE_CORE_TOOLS = {
    "resolve_material",
    "search_materials",
    "get_material_workspace",
    "get_neighborhood",
    "inspect_edge",
    "select_material",
    "compare_materials",
    "get_material_details",
    "get_material_structure",
    "open_project_material",
    "save_project_material",
    "list_project_files",
    "read_project_file",
    "screen_candidates",
    "create_candidate_set",
}


def _live_tool_declarations() -> list[dict[str, Any]]:
    decls = [d for d in TOOL_DECLARATIONS if str(d.get("name") or "") in LIVE_CORE_TOOLS]
    return decls or list(TOOL_DECLARATIONS)


def _live_model_candidates(preferred: str | None = None) -> list[str]:
    env_model = (os.environ.get("CATALYST_GEMINI_LIVE_MODEL") or "").strip()
    ordered: list[str] = []
    for m in (preferred, env_model, *DEFAULT_LIVE_MODELS):
        mid = str(m or "").strip().removeprefix("models/")
        if mid and mid not in ordered:
            ordered.append(mid)
    return ordered


def _short_system_instruction(full: str, *, limit: int = 6000) -> str:
    text = (full or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 40] + "\n\n[context truncated for live voice]"


def _is_internal_model_text(text: str) -> bool:
    """True for thoughts / tool dumps that must not reach the chat UI as messages."""
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()
    if low.startswith("tool_call") or low.startswith("thought:"):
        return True
    if "functioncall" in low.replace(" ", "") or '"name"' in t and '"args"' in t:
        return True
    if t.startswith("```") and ("name" in t and "args" in t):
        return True
    if low.startswith("using ") and "?" in t and len(t) < 80:
        return True
    return False


async def _connect_live_upstream(
    api_key: str,
    *,
    model: str,
    system_instruction: str,
    live_tools: list[dict[str, Any]],
) -> Any:
    """Open Live WS and send setup. Raises on connect/setup failure."""
    upstream_url = f"{GEMINI_LIVE_WS}?key={quote(api_key)}"
    # open_timeout: handshake hang was the user-facing failure mode.
    gemini = await websockets.connect(
        upstream_url,
        max_size=16 * 1024 * 1024,
        open_timeout=25,
        close_timeout=5,
        ping_interval=20,
        ping_timeout=20,
    )
    # v1beta Live: responseModalities under generationConfig.
    # input/outputAudioTranscription are REQUIRED for chat UI (otherwise only raw audio + thoughts).
    setup = {
        "setup": {
            "model": f"models/{model.removeprefix('models/')}",
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Puck"}},
                },
            },
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "tools": [{"functionDeclarations": live_tools}] if live_tools else [],
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},
        }
    }
    await gemini.send(json.dumps(setup))
    # Wait briefly for setupComplete when the server sends it.
    try:
        raw = await asyncio.wait_for(gemini.recv(), timeout=12)
        payload = json.loads(raw)
        if "error" in payload:
            await gemini.close()
            raise RuntimeError(str(payload.get("error") or payload)[:300])
        # If first frame isn't setupComplete, still proceed (some builds stream later).
        if "setupComplete" not in payload and "serverContent" not in payload:
            # Push frame back via a simple buffer attribute for the receiver loop.
            gemini._catalyst_prefetch = payload  # type: ignore[attr-defined]
    except asyncio.TimeoutError:
        # Connected but no setup ack ? still usable for some models.
        pass
    except websockets.exceptions.ConnectionClosed as exc:
        raise RuntimeError(f"Live setup rejected ({exc.code}): {exc.reason or 'closed'}") from exc
    return gemini


async def catalyst_voice_live(websocket: WebSocket, controller: Any) -> None:
    await websocket.accept()
    api_key = os.environ.get(PROVIDER_ENV_KEYS["gemini"]) or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        await websocket.send_json(
            {
                "type": "error",
                "message": "Live voice needs a cloud API key on the backend (text chat can use desktop sign-in).",
            }
        )
        await websocket.close(code=1011)
        return

    session_id = "default"
    current_workspace: dict[str, Any] | None = None
    preferred_model: str | None = None

    try:
        first = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": f"Invalid voice setup message: {exc}"})
        await websocket.close(code=1003)
        return

    if isinstance(first, dict) and first.get("type") == "start":
        session_id = str(first.get("session_id") or session_id)
        current_workspace = first.get("current_workspace") if isinstance(first.get("current_workspace"), dict) else None
        if first.get("model"):
            preferred_model = str(first["model"])

    session = controller.sessions.get_session(session_id) or controller.sessions.create_session(
        context=current_workspace or {"id": session_id}
    )
    if current_workspace:
        ctx = dict(session.get("context") or {})
        mid = (
            current_workspace.get("material_id")
            or current_workspace.get("resolved_material_id")
            or current_workspace.get("current_material_id")
        )
        if mid:
            ctx["current_material_id"] = mid
            ctx["last_focus_material_id"] = mid
        if current_workspace.get("formula_pretty"):
            ctx["formula_pretty"] = current_workspace["formula_pretty"]
        if current_workspace.get("project_id"):
            ctx["project_id"] = current_workspace["project_id"]
        if current_workspace.get("rail_mode"):
            ctx["rail_mode"] = current_workspace["rail_mode"]
        if current_workspace.get("workspace_tab"):
            ctx["workspace_tab"] = current_workspace["workspace_tab"]
        controller.sessions.update_session(session_id, {"context": ctx})
        session = controller.sessions.get_session(session_id) or session

    dynamic = _dynamic_context(session, current_workspace)
    compiled = write_compiled_agent_context(controller.repo_root, dynamic)
    system_instruction = _short_system_instruction(
        f"{compiled['markdown']}\n\n"
        "You are running in Catalyst live voice mode. Keep spoken answers short (1?3 sentences). "
        "Use Catalyst tools BEFORE claims about materials, selecting materials, neighbors, or project files. "
        "Never invent material ids. Prefer the LIVE open material from RunContext when the user says 'this' / 'current'. "
        "For neighborhood questions call get_neighborhood. For open/select call select_material after resolve_material. "
        "After a tool call, briefly say what changed in the workspace. "
        "Do not narrate tool names, JSON, or internal reasoning out loud ? only the final user answer. "
        "If the user shares their screen, use the video frames to understand the open UI, graphs, and notebooks."
    )
    live_tools = _live_tool_declarations()

    gemini = None
    last_err: Exception | None = None
    used_model = ""
    for model in _live_model_candidates(preferred_model):
        try:
            gemini = await _connect_live_upstream(
                api_key,
                model=model,
                system_instruction=system_instruction,
                live_tools=live_tools,
            )
            used_model = model
            break
        except Exception as exc:
            last_err = exc
            gemini = None
            continue

    if gemini is None:
        msg = f"Live voice bridge failed: {last_err or 'no live model available'}"
        # Genericize vendor noise for demos
        msg = msg.replace("Gemini", "Live").replace("gemini", "live")
        try:
            await websocket.send_json({"type": "error", "message": msg[:400]})
        finally:
            await websocket.close(code=1011)
        return

    try:
        await websocket.send_json(
            {
                "type": "ready",
                "model": "live",
                "transport": "live",
                "tool_count": len(live_tools),
                "live_model": used_model,
            }
        )
        stop = asyncio.Event()
        aggregate = _empty_aggregate()
        prefetch = getattr(gemini, "_catalyst_prefetch", None)

        async def client_to_gemini() -> None:
            while not stop.is_set():
                try:
                    msg = await websocket.receive_json()
                except WebSocketDisconnect:
                    stop.set()
                    return
                except Exception as exc:
                    await websocket.send_json({"type": "error", "message": f"Bad client voice message: {exc}"})
                    continue

                msg_type = msg.get("type")
                if msg_type == "audio":
                    data = msg.get("data")
                    if not data:
                        continue
                    await gemini.send(
                        json.dumps(
                            {
                                "realtimeInput": {
                                    "audio": {
                                        "data": data,
                                        "mimeType": msg.get("mimeType") or "audio/pcm;rate=16000",
                                    }
                                }
                            }
                        )
                    )
                elif msg_type == "video":
                    # Screen / camera frames (JPEG/PNG base64) for Live vision
                    data = msg.get("data")
                    if not data:
                        continue
                    await gemini.send(
                        json.dumps(
                            {
                                "realtimeInput": {
                                    "video": {
                                        "data": data,
                                        "mimeType": msg.get("mimeType") or "image/jpeg",
                                    }
                                }
                            }
                        )
                    )
                elif msg_type == "text":
                    text = str(msg.get("text") or "").strip()
                    if text:
                        await gemini.send(json.dumps({"realtimeInput": {"text": text}}))
                elif msg_type == "stop":
                    stop.set()
                    try:
                        await gemini.close()
                    except Exception:
                        pass
                    return

        async def gemini_to_client() -> None:
            if prefetch is not None:
                await _handle_gemini_message(websocket, gemini, controller, session_id, prefetch, aggregate)
            async for raw in gemini:
                if stop.is_set():
                    return
                payload = json.loads(raw)
                await _handle_gemini_message(websocket, gemini, controller, session_id, payload, aggregate)

        tasks = [asyncio.create_task(client_to_gemini()), asyncio.create_task(gemini_to_client())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            try:
                task.result()
            except Exception:
                pass
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": f"Live voice bridge failed: {exc}"[:400]})
        finally:
            await websocket.close(code=1011)
    finally:
        try:
            await gemini.close()
        except Exception:
            pass


async def _handle_gemini_message(
    websocket: WebSocket,
    gemini: Any,
    controller: Any,
    session_id: str,
    payload: dict[str, Any],
    aggregate: dict[str, Any],
) -> None:
    if "setupComplete" in payload:
        await websocket.send_json({"type": "setup_complete"})

    if payload.get("error"):
        await websocket.send_json({"type": "error", "message": str(payload.get("error"))[:300]})
        return

    server_content = payload.get("serverContent") or {}
    if server_content.get("inputTranscription"):
        transcript = server_content["inputTranscription"]
        in_text = str(transcript.get("text") or "")
        if in_text.strip():
            message: dict[str, Any] = {
                "type": "input_transcript",
                "text": in_text,
                "finished": bool(transcript.get("finished") or transcript.get("isFinal")),
            }
            segment_id = transcript.get("segmentId") or transcript.get("segment_id")
            if segment_id:
                message["segment_id"] = segment_id
            await websocket.send_json(message)
            await websocket.send_json({"type": "status", "text": "Thinking?"})
    if server_content.get("outputTranscription"):
        transcript = server_content["outputTranscription"]
        out_text = str(transcript.get("text") or "")
        if out_text.strip() and not _is_internal_model_text(out_text):
            message = {
                "type": "output_transcript",
                "text": out_text,
                "finished": bool(transcript.get("finished") or transcript.get("isFinal")),
            }
            segment_id = transcript.get("segmentId") or transcript.get("segment_id")
            if segment_id:
                message["segment_id"] = segment_id
            await websocket.send_json(message)
    if server_content.get("interrupted"):
        await websocket.send_json({"type": "status", "text": "Listening?"})
    if server_content.get("turnComplete") or server_content.get("generationComplete"):
        await websocket.send_json(
            {
                "type": "turn_complete",
                "actions": aggregate.get("actions") or [],
                "ui_actions": aggregate.get("ui_actions") or [],
                "candidate_results": aggregate.get("candidate_results"),
            }
        )
        await websocket.send_json({"type": "status", "text": "Listening?"})

    model_turn = server_content.get("modelTurn") or {}
    for part in model_turn.get("parts") or []:
        # Skip thought / tool-planning text ? chat uses outputTranscription + audio only
        if part.get("thought") is True or part.get("thoughtSignature"):
            await websocket.send_json({"type": "status", "text": "Thinking?"})
            continue
        # Prefer transcription path for text; only forward non-thought prose as fallback
        if part.get("text") and not part.get("thought"):
            raw = str(part.get("text") or "")
            if _is_internal_model_text(raw):
                await websocket.send_json({"type": "status", "text": "Thinking?"})
            # else: skip agent_text when we have outputTranscription enabled (avoids double/thought dump)
        inline = part.get("inlineData") or {}
        if inline.get("data"):
            await websocket.send_json(
                {
                    "type": "audio",
                    "data": inline["data"],
                    "mimeType": inline.get("mimeType") or "audio/pcm;rate=24000",
                }
            )

    tool_call = payload.get("toolCall") or {}
    calls = tool_call.get("functionCalls") or []
    if not calls:
        return

    ui_before = len(aggregate.get("ui_actions") or [])
    responses = []
    for call in calls:
        name = call.get("name")
        args = call.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        status = _friendly_tool_status(str(name or ""), args)
        # status drives shimmer; never dump raw tool JSON into chat
        await websocket.send_json(
            {
                "type": "tool_call",
                "name": name,
                "args": args,
                "status": status,
            }
        )
        await websocket.send_json({"type": "status", "text": status})
        try:
            result = _execute_tool(controller, session_id, name, args, aggregate)
            response_data = {"result": _compact_tool_result(result)}
            new_ui = (aggregate.get("ui_actions") or [])[ui_before:]
            await websocket.send_json(
                {
                    "type": "tool_result",
                    "name": name,
                    "result": response_data["result"],
                    "actions": aggregate.get("actions") or [],
                    "ui_actions": new_ui,
                    "candidate_results": aggregate.get("candidate_results"),
                }
            )
            ui_before = len(aggregate.get("ui_actions") or [])
        except Exception as exc:
            response_data = {"error": str(exc)}
            await websocket.send_json({"type": "tool_error", "name": name, "message": str(exc)})
        item = {"name": name, "response": response_data}
        if call.get("id"):
            item["id"] = call["id"]
        responses.append(item)

    await gemini.send(json.dumps({"toolResponse": {"functionResponses": responses}}))
