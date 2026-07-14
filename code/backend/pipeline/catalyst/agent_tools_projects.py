from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from catalyst.agent_loop import run_local_agent_fallback, run_llm_agent_loop, should_use_local_agent_fast_path
from catalyst.agent_runtime import ensure_agent_runtime_files
from catalyst.candidate_sets import CandidateSetStore
from catalyst.codex_gateway import CodexGateway
from catalyst.model_services import ModelServiceRunner
from catalyst.project_store import ProjectStore
from catalyst.providers import provider_status
from catalyst.research_adapters import search_research_sources
from catalyst.research_mode import ResearchStore
from catalyst.research_sources import research_sources_payload
from catalyst.screening import screen_candidates
from catalyst.session_store import SessionStore, compact_session_context
from catalyst.settings import CatalystSettings, research_source_status
from catalyst.exporters import write_json_export
class AgentToolsProjectsMixin:
    def list_project_files(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            project_id = self._project_id(payload)
            return {"ok": True, **self.projects.workspace_snapshot(project_id)}
        except (ValueError, FileNotFoundError) as exc:
            return {"ok": False, "error": str(exc)}

    def read_project_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            project_id = self._project_id(payload)
            return {"ok": True, **self.projects.read_text_file(project_id, str(payload.get("path") or ""))}
        except (ValueError, FileNotFoundError) as exc:
            return {"ok": False, "error": str(exc)}

    def write_project_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            project_id = self._project_id(payload)
            return {
                "ok": True,
                "project_id": project_id,
                **self.projects.write_text_file(
                    project_id,
                    str(payload.get("path") or ""),
                    str(payload.get("content") or ""),
                ),
            }
        except (ValueError, FileNotFoundError) as exc:
            return {"ok": False, "error": str(exc)}

    def read_project_notebook(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            project_id = self._project_id(payload)
            return {"ok": True, "project_id": project_id, **self.projects.read_notebook(project_id)}
        except (ValueError, FileNotFoundError) as exc:
            return {"ok": False, "error": str(exc)}

    def update_project_notebook(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            project_id = self._project_id(payload)
            return {
                "ok": True,
                "project_id": project_id,
                **self.projects.write_notebook(project_id, str(payload.get("content") or "")),
            }
        except (ValueError, FileNotFoundError) as exc:
            return {"ok": False, "error": str(exc)}

    def run_workspace_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        run: dict[str, Any] | None = None
        try:
            project_id = self._project_id(payload)
            prompt = str(payload.get("prompt") or "").strip()
            effort = str(payload.get("reasoning_effort") or "high")
            run = self.projects.save_run(project_id, {
                "kind": "codex",
                "status": "running",
                "prompt": prompt,
                "reasoning_effort": effort,
                "source": "catalyst_agent_tool",
            })
            result = self.codex.run(
                project_path=self.projects.project_path(project_id),
                prompt=prompt,
                thread_id=self.projects.codex_thread_id(project_id),
                model=str(payload.get("model") or "") or None,
                reasoning_effort=effort,
            )
            response = str(result.get("finalResponse") or "")
            self.projects.save_codex_state(project_id, thread_id=str(result["threadId"]), last_response=response)
            completed = self.projects.save_run(project_id, {
                **run,
                "status": "completed",
                "thread_id": str(result["threadId"]),
                "response": response[-50_000:],
                "usage": result.get("usage"),
            })
            return {
                "ok": True,
                "project_id": project_id,
                "thread_id": result["threadId"],
                "response": response,
                "run": completed,
            }
        except (ValueError, FileNotFoundError, RuntimeError, TimeoutError) as exc:
            if run:
                try:
                    self.projects.save_run(str(payload.get("project_id") or ""), {**run, "status": "failed", "error": str(exc)[-4000:]})
                except (ValueError, FileNotFoundError):
                    pass
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _project_id(payload: dict[str, Any]) -> str:
        project_id = str(payload.get("project_id") or "").strip()
        if not project_id:
            raise ValueError("project_id is required")
        return project_id

