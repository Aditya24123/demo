"""Allowlisted shell for agent tools ? no unrestricted RCE."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

# First token must be one of these (basename match).
_ALLOWED_BINS = {
    "python",
    "python3",
    "py",
    "pip",
    "pip3",
    "dir",
    "ls",
    "type",
    "cat",
    "echo",
    "where",
    "which",
    "git",
}

# Full-line deny (injection / path escape).
_DENY_PATTERNS = [
    r"[;&|`$]",
    r"\n",
    r"\.\./",
    r"\.\.\\",
    r">\s*",
    r"<\s*",
    r"rm\s+-rf",
    r"del\s+/",
    r"format\s+",
    r"shutdown",
    r"reg\s+",
    r"curl\s+",
    r"wget\s+",
    r"Invoke-",
    r"powershell",
    r"cmd\.exe",
]


def _cwd_for(controller: Any, session_id: str, project_id: str | None) -> Path:
    pid = project_id
    if not pid:
        session = controller.sessions.get_session(session_id) or {}
        ctx = session.get("context") if isinstance(session.get("context"), dict) else {}
        pid = ctx.get("project_id")
    if pid:
        try:
            return Path(controller.projects.project_path(str(pid))).resolve()
        except Exception:
            pass
    path = Path(controller.repo_root).resolve() / "data" / "local" / "agent_workspace" / "default"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_allowlisted_shell(
    controller: Any,
    *,
    session_id: str,
    command: str,
    project_id: str | None = None,
    timeout_sec: int = 45,
) -> dict[str, Any]:
    raw = (command or "").strip()
    if not raw:
        return {"ok": False, "error": "empty command"}
    if len(raw) > 500:
        return {"ok": False, "error": "command too long"}
    for pat in _DENY_PATTERNS:
        if re.search(pat, raw, re.IGNORECASE):
            return {"ok": False, "error": f"command blocked by policy ({pat})"}

    # Tokenize simply (no shell=True).
    parts = raw.split()
    if not parts:
        return {"ok": False, "error": "empty command"}
    bin_name = Path(parts[0]).name.lower()
    if bin_name not in _ALLOWED_BINS:
        return {"ok": False, "error": f"binary not allowlisted: {bin_name}"}

    # python -c must stay short
    if bin_name in {"python", "python3", "py"} and "-c" in parts:
        idx = parts.index("-c")
        if idx + 1 >= len(parts):
            return {"ok": False, "error": "python -c requires code"}
        code = " ".join(parts[idx + 1 :])
        if len(code) > 400:
            return {"ok": False, "error": "python -c payload too long"}

    cwd = _cwd_for(controller, session_id, project_id)
    try:
        completed = subprocess.run(
            parts,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout_sec}s", "cwd": str(cwd)}
    except FileNotFoundError:
        return {"ok": False, "error": f"binary not found: {bin_name}", "cwd": str(cwd)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "cwd": str(cwd)}

    stdout = (completed.stdout or "")[:12_000]
    stderr = (completed.stderr or "")[:4_000]
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "cwd": str(cwd),
        "command": parts,
    }
