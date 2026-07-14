"""Smoke-test Catalyst agent via local API with Omnirouter models."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = os.getenv("CATALYST_API", "http://127.0.0.1:8766")


def http_json(method: str, path: str, body: dict | None = None, timeout: int = 180) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def stream_chat(session_id: str, message: str, workspace: dict, timeout: int = 240) -> dict:
    body = {
        "session_id": session_id,
        "message": message,
        "current_workspace": workspace,
    }
    req = urllib.request.Request(
        f"{API}/agent/chat/stream",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    statuses: list[str] = []
    tokens: list[str] = []
    done: dict | None = None
    err: str | None = None
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as res:
        buf = b""
        while True:
            chunk = res.read(256)
            if not chunk:
                break
            buf += chunk
            while b"\n\n" in buf:
                part, buf = buf.split(b"\n\n", 1)
                for line in part.split(b"\n"):
                    line = line.strip()
                    if not line.startswith(b"data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw:
                        continue
                    try:
                        ev = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    et = ev.get("type")
                    if et == "status":
                        statuses.append(str(ev.get("text") or ""))
                    elif et == "token":
                        tokens.append(str(ev.get("text") or ""))
                    elif et == "done":
                        done = ev.get("response") or ev
                    elif et == "error":
                        err = str(ev.get("message") or "error")
    ms = int((time.time() - t0) * 1000)
    text = "".join(tokens)
    if done and not text:
        text = str(((done.get("assistant_message") or {}).get("text")) or "")
    return {
        "ms": ms,
        "statuses": statuses,
        "text": text,
        "done": done,
        "error": err,
        "ui_actions": (done or {}).get("ui_actions") or ((done or {}).get("assistant_message") or {}).get("ui_actions") or [],
    }


def patch_model(model: str) -> None:
    http_json(
        "PATCH",
        "/settings",
        {
            "providers": {
                "active_provider": "micro",
                "models": {"micro": model},
                "base_urls": {"micro": os.environ["MICRO_BASE_URL"]},
                "api_key_envs": {"micro": "MICRO_API_KEY"},
            }
        },
    )


def main() -> int:
    print("health", http_json("GET", "/health"))
    catalog = http_json("GET", "/agent/tools")
    print("agent_mode", catalog.get("mode"), "tools", len(catalog.get("tools") or []), "provider", catalog.get("active_provider"))

    workspace = {
        "agent_surface": "materials",
        "rail_mode": "home",
        "material_id": "mp-cfvcm",
        "formula_pretty": "Re2O7",
        "chemsys": "O-Re",
        "workspace_tab": "structure",
    }

    models = [
        "auto/best-fast",
        "auto/best-coding",
        "auto/best-chat",
        "auto/best-reasoning",
    ]
    report = []
    for model in models:
        print("\n=== MODEL", model, "===")
        try:
            patch_model(model)
        except Exception as exc:
            print("patch fail", exc)
            continue
        sid = f"smoke-{model.replace('/', '-')}-{int(time.time())}"
        # 1) live viewport greeting ? must be Re2O7 / mp-cfvcm, never wrong screener (CdS/MnO2)
        r1 = stream_chat(sid, "What material am I looking at right now? One short sentence with formula and id.", workspace)
        print("viewport", r1["ms"], "ms", "status", r1["statuses"][:6], "err", r1["error"])
        print("  text:", (r1["text"] or "")[:240].replace("\n", " "))
        t1 = r1["text"] or ""
        # Correct identity wins even if Omnirouter 503'd into degraded local path.
        ok_viewport = (
            ("Re2O7" in t1 or "Re?O?" in t1 or "mp-cfvcm" in t1)
            and "MnO2" not in t1
            and "CdS" not in t1
        )
        degraded1 = any("Degraded" in s for s in r1["statuses"])

        # 2) tool-using question on open material
        r2 = stream_chat(
            sid,
            "Use tools. What is the density and space group of the open material? Be brief and grounded.",
            workspace,
        )
        print("tools", r2["ms"], "ms", "status", r2["statuses"][:8], "err", r2["error"])
        print("  text:", (r2["text"] or "")[:300].replace("\n", " "))
        print("  ui_actions", len(r2["ui_actions"] or []))
        t2 = r2["text"] or ""
        degraded2 = any("Degraded" in s for s in r2["statuses"])
        t2l = t2.lower()
        has_density = any(x in t2l for x in ("g/cm", "5.8", "5.84")) or (
            "density" in t2l and any(ch.isdigit() for ch in t2)
        )
        has_sg = any(x in t2 for x in ("P2", "space group", "Space group", "spacegroup", "Pnma", "Fm"))
        ok_tools = (
            bool(t2.strip())
            and not r2["error"]
            and "CdS" not in t2
            and ("Re2O7" in t2 or "Re?O?" in t2 or "mp-cfvcm" in t2)
            and (has_density or has_sg)
        )

        report.append(
            {
                "model": model,
                "viewport_ms": r1["ms"],
                "viewport_ok": ok_viewport,
                "viewport_degraded": degraded1,
                "tools_ms": r2["ms"],
                "tools_ok": ok_tools,
                "tools_degraded": degraded2,
                "sample_vp": t1[:120],
                "sample_tools": t2[:160],
            }
        )

    print("\n===== REPORT =====")
    for row in report:
        print(json.dumps(row))

    # Prefer full pass (viewport+tools), non-degraded, then fastest tools_ms among best-fast/coding
    good = [r for r in report if r["viewport_ok"] and r["tools_ok"] and not r["viewport_degraded"]]
    if not good:
        good = [r for r in report if r["viewport_ok"] and r["tools_ok"]]
    if not good:
        good = [r for r in report if r["tools_ok"]]
    if good:
        preferred_order = ["auto/best-fast", "auto/best-coding", "auto/best-chat", "auto/best-reasoning"]
        preferred = None
        for name in preferred_order:
            hit = next((r for r in good if r["model"] == name and r["tools_ms"] < 60000), None)
            if hit:
                preferred = hit
                break
        best = preferred or sorted(good, key=lambda r: r["tools_ms"])[0]
        print("BEST", best["model"])
        patch_model(best["model"])
        return 0
    print("NO_GOOD_MODEL")
    return 1


if __name__ == "__main__":
    # Keys/endpoint come from env (.env or shell) ? never hardcode secrets here.
    if not os.environ.get("MICRO_BASE_URL"):
        os.environ["MICRO_BASE_URL"] = "https://micro.tail3bfb03.ts.net/v1"
    if not os.environ.get("MICRO_API_KEY"):
        print("MICRO_API_KEY is required (Omnirouter).", file=sys.stderr)
        raise SystemExit(2)
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print("API unreachable", exc, file=sys.stderr)
        raise SystemExit(2)
