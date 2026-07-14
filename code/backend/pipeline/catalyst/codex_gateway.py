from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class CodexGateway:
    """Invoke the official TypeScript Codex SDK inside one bounded project root."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.service_root = self.repo_root / "code" / "backend" / "codex-service"
        self.runner = self.service_root / "runner.mjs"

    def status(self) -> dict[str, Any]:
        node = shutil.which("node")
        sdk = self.service_root / "node_modules" / "@openai" / "codex-sdk"
        return {
            "available": bool(node and self.runner.is_file() and sdk.is_dir()),
            "node": bool(node),
            "sdk_installed": sdk.is_dir(),
            "runner": self.runner.is_file(),
        }

    def run(
        self,
        *,
        project_path: Path,
        prompt: str,
        thread_id: str | None = None,
        model: str | None = None,
        reasoning_effort: str = "high",
    ) -> dict[str, Any]:
        status = self.status()
        if not status["available"]:
            raise RuntimeError("Codex SDK service is not installed")
        clean_prompt = str(prompt or "").strip()
        if not clean_prompt:
            raise ValueError("prompt is required")
        if len(clean_prompt) > 50_000:
            raise ValueError("prompt must be 50000 characters or fewer")
        payload = {
            "projectPath": str(Path(project_path).resolve()),
            "prompt": clean_prompt,
            "threadId": thread_id,
            "model": model,
            "reasoningEffort": reasoning_effort,
        }
        try:
            completed = subprocess.run(
                ["node", str(self.runner)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                cwd=self.service_root,
                timeout=900,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Codex SDK run timed out after 900 seconds") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip()[-4000:] or "Codex SDK runner failed"
            raise RuntimeError(detail)
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Codex SDK returned invalid JSON") from exc
        if not isinstance(result, dict) or not result.get("threadId"):
            raise RuntimeError("Codex SDK did not return a thread id")
        return result
