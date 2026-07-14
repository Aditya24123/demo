"""Antigravity CLI (`agy`) transport ? Google OAuth / subscription models.

Primary Catalyst agent path when `agy` is installed and logged in.
Multi-round tool loop via structured TOOL_CALL JSON lines; Catalyst executes
tools locally (same tool_exec as Interactions API / Live voice).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

# Prefer balanced braces when models wrap TOOL_CALL in prose.
_TOOL_CALL_RE = re.compile(
    r"TOOL_CALL:\s*(\{.*?\})(?:\s*$|\n)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
_TOOL_CALL_FENCE_RE = re.compile(
    r"```(?:json)?\s*(\{\s*\"name\"\s*:.*?\})\s*```",
    re.IGNORECASE | re.DOTALL,
)
_TOOL_CALL_LOOSE_RE = re.compile(
    r"\{\s*\"name\"\s*:\s*\"([a-zA-Z0-9_]+)\"\s*,\s*\"args\"\s*:\s*(\{.*?\})\s*\}",
    re.DOTALL,
)

# UI profile ? CLI --model string (internal; never show these in product UI)
PROFILE_TO_AGY_MODEL = {
    "agy/3.5-flash-low": "Gemini 3.5 Flash (Low)",
    "agy/3.5-flash-medium": "Gemini 3.5 Flash (Medium)",
    "agy/3.5-flash-high": "Gemini 3.5 Flash (High)",
    "agy/3.1-pro-low": "Gemini 3.1 Pro (Low)",
    "agy/3.1-pro-high": "Gemini 3.1 Pro (High)",
    "agy/claude-sonnet-thinking": "Claude Sonnet 4.6 (Thinking)",
    "agy/claude-opus-thinking": "Claude Opus 4.6 (Thinking)",
    "agy/gpt-oss-120b": "GPT-OSS 120B (Medium)",
}

# Hackathon-safe labels for status lines / citations (no vendor names)
PROFILE_DISPLAY_LABEL = {
    "agy/3.5-flash-low": "Fast",
    "agy/3.5-flash-medium": "Balanced",
    "agy/3.5-flash-high": "Deep",
    "agy/3.1-pro-low": "Pro ? Fast",
    "agy/3.1-pro-high": "Pro ? Deep",
    "agy/claude-sonnet-thinking": "Reasoning ? A",
    "agy/claude-opus-thinking": "Reasoning ? B",
    "agy/gpt-oss-120b": "Open ? 120B",
    "gemini-3.1-flash-lite": "Lite",
    "gemini-2.5-flash": "Standard",
    "gemini-2.5-pro": "Pro",
}


def display_model_label(profile: str | None, effort: str | None = None) -> str:
    profile = (profile or "").strip()
    if profile in PROFILE_DISPLAY_LABEL:
        return PROFILE_DISPLAY_LABEL[profile]
    # Map CLI display names that may leak through
    raw = resolve_agy_model(profile, effort) if profile else ""
    for key, label in (
        ("Flash (Low)", "Fast"),
        ("Flash (Medium)", "Balanced"),
        ("Flash (High)", "Deep"),
        ("Pro (Low)", "Pro ? Fast"),
        ("Pro (High)", "Pro ? Deep"),
        ("Sonnet", "Reasoning ? A"),
        ("Opus", "Reasoning ? B"),
        ("120B", "Open ? 120B"),
    ):
        if key in (raw or profile or ""):
            return label
    if effort == "high":
        return "Deep"
    if effort in {"low", "minimal"}:
        return "Fast"
    return "Balanced"


def agy_cli_available() -> bool:
    if (os.getenv("CATALYST_AGY_CLI") or "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    return bool(_agy_bin())


def _agy_bin() -> str | None:
    configured = (os.getenv("CATALYST_AGY_BIN") or "").strip()
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("agy")
    if found:
        return found
    win = Path.home() / "AppData" / "Local" / "agy" / "bin" / "agy.exe"
    if win.is_file():
        return str(win)
    return None


def resolve_agy_model(profile: str | None, effort: str | None = None) -> str:
    profile = (profile or "").strip()
    if profile in PROFILE_TO_AGY_MODEL:
        return PROFILE_TO_AGY_MODEL[profile]
    # Direct display names from `agy models`
    if profile and not profile.startswith("gemini-") and (
        "Flash" in profile or "Pro" in profile or "Claude" in profile or "GPT-OSS" in profile
    ):
        return profile
    effort = (effort or "medium").strip().lower()
    if effort == "high":
        return "Gemini 3.5 Flash (High)"
    if effort in {"low", "minimal"}:
        return "Gemini 3.5 Flash (Low)"
    return "Gemini 3.5 Flash (Medium)"


def build_tool_protocol_block(tool_declarations: list[dict[str, Any]], *, max_tools: int = 40) -> str:
    """Compact JSON schemas for OAuth CLI models (no native function-calling)."""
    lines: list[str] = [
        "## Catalyst tools (mandatory protocol)",
        "You do NOT have shell/file access to Catalyst data. Use TOOL_CALL lines only.",
        "When you need a tool, emit one or more lines in this exact form (no markdown fences):",
        'TOOL_CALL: {"name":"<tool_name>","args":{...}}',
        "After tool results arrive, either emit more TOOL_CALL lines or give the final answer in markdown.",
        "Never invent material ids ? use resolve_material / search_materials / get_material_workspace.",
        "For open/select materials: resolve_material then select_material or open_project_material.",
        "For neighbors: get_neighborhood (opens Neighbors tab).",
        "Allowed tools:",
    ]
    for decl in tool_declarations[:max_tools]:
        name = str(decl.get("name") or "").strip()
        if not name:
            continue
        desc = str(decl.get("description") or "").strip().replace("\n", " ")[:180]
        params = decl.get("parameters") or {}
        props = list((params.get("properties") or {}).keys())[:12]
        req = params.get("required") or []
        lines.append(f"- {name}: {desc}")
        if props:
            lines.append(f"  args keys: {', '.join(props)}" + (f" (required: {', '.join(req)})" if req else ""))
    lines.append("Do not call tools that are not listed.")
    return "\n".join(lines)


def known_tool_names(tool_declarations: list[dict[str, Any]] | None = None) -> set[str]:
    if tool_declarations is None:
        try:
            from catalyst.agent.tools_decl import TOOL_DECLARATIONS

            tool_declarations = TOOL_DECLARATIONS
        except Exception:
            return set()
    return {str(d.get("name") or "") for d in tool_declarations if d.get("name")}


def parse_tool_calls(text: str, *, allowed: set[str] | None = None) -> list[dict[str, Any]]:
    """Extract TOOL_CALL payloads; filter to known tool names when provided."""
    calls: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(parsed: dict[str, Any]) -> None:
        name = str(parsed.get("name") or "").strip()
        if not name:
            return
        if allowed is not None and name not in allowed:
            return
        args = parsed.get("args")
        if args is None and isinstance(parsed.get("arguments"), dict):
            args = parsed["arguments"]
        if not isinstance(args, dict):
            args = {}
        key = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
        if key in seen:
            return
        seen.add(key)
        calls.append({"name": name, "args": args})

    for match in _TOOL_CALL_RE.finditer(text or ""):
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            _add(parsed)

    if not calls:
        for match in _TOOL_CALL_FENCE_RE.finditer(text or ""):
            try:
                parsed = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                _add(parsed)

    if not calls:
        for match in _TOOL_CALL_LOOSE_RE.finditer(text or ""):
            try:
                args = json.loads(match.group(2))
            except json.JSONDecodeError:
                continue
            _add({"name": match.group(1), "args": args if isinstance(args, dict) else {}})

    return calls


def strip_tool_call_noise(text: str) -> str:
    cleaned = _TOOL_CALL_RE.sub("", text or "")
    cleaned = _TOOL_CALL_FENCE_RE.sub("", cleaned)
    return cleaned.strip()


_AUTH_MARKERS = (
    "authentication required",
    "paste the authorization code",
    "not logged into antigravity",
    "you are not logged into",
    "silent auth failed",
    "triggering oauth",
    "waiting for authentication",
    "please sign in",
    "please visit the url to log in",
    "unauthorized",
    "keyringauth: timed out",
)


def _looks_like_auth_failure(blob: str) -> bool:
    low = (blob or "").lower()
    return any(m in low for m in _AUTH_MARKERS)


def run_agy_print(
    prompt: str,
    *,
    model: str,
    cwd: Path | None = None,
    continue_conversation: bool = False,
    timeout_sec: int = 180,
) -> dict[str, Any]:
    """Run ``agy -p`` non-interactively.

    Important: never feed stdin. If AGY is logged out it opens a browser OAuth
    flow and asks to paste a code ? that cannot work under Catalyst (no TTY).
    We fail fast with ``auth_error`` so the agent falls through to the API path.
    """
    binary = _agy_bin()
    if not binary:
        return {"ok": False, "error": "agy binary not found", "text": "", "auth_error": False}
    cmd = [
        binary,
        "-p",
        prompt,
        "--model",
        model,
        "--print-timeout",
        f"{max(30, timeout_sec)}s",
        "--dangerously-skip-permissions",
    ]
    if continue_conversation:
        cmd.append("-c")
    # Ensure HOME/USERPROFILE so Windows Credential Manager / keyring can resolve.
    env = os.environ.copy()
    home = str(Path.home())
    env.setdefault("USERPROFILE", home)
    env.setdefault("HOME", home)
    # Discourage interactive OAuth wait in print mode (if supported by newer builds).
    env.setdefault("AGY_NO_BROWSER", "1")
    env.setdefault("CI", "1")
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout_sec + 30,
            shell=False,
            stdin=subprocess.DEVNULL,  # never hang on "paste code here"
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "agy timeout (often OAuth/keyring ? re-login in a real terminal with `agy`)",
            "text": "",
            "auth_error": True,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "text": "", "auth_error": False}
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    combined = f"{stdout}\n{stderr}"
    err_snip = stderr[:2000]
    auth_fail = _looks_like_auth_failure(combined)
    # Prefer real model answer on stdout; ignore OAuth spam as "text"
    text = stdout
    if auth_fail and not (text and not _looks_like_auth_failure(text)):
        text = ""
    elif not text and stderr and not auth_fail:
        text = stderr
    return {
        "ok": completed.returncode == 0 and bool(text) and not auth_fail,
        "returncode": completed.returncode,
        "text": text,
        "stderr": err_snip,
        "model": model,
        "auth_error": auth_fail,
        "error": (
            "AGY desktop login missing/expired. Open a normal terminal, run `agy` once, "
            "complete Google sign-in there (paste the code into THAT terminal), then retry. "
            "Or set CATALYST_PREFER_AGY_CLI=0 to use API key path."
            if auth_fail
            else ""
        ),
    }
