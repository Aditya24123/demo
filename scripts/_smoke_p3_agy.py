"""One-shot smoke: identity + open_project_material (P3)."""
from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8766"


def post(path: str, payload: dict, timeout: int = 180) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main() -> None:
    r = post(
        "/agent/chat",
        {
            "message": "What material is currently open? Reply with only material id and formula.",
            "current_workspace": {
                "agent_model_profile": "agy/3.5-flash-medium",
                "agent_effort": "low",
                "current_material_id": "mp-zw",
                "formula_pretty": "CdS",
            },
        },
    )
    am = r.get("assistant_message") or {}
    text = am.get("text") or r.get("reply") or ""
    print("=== IDENTITY ===")
    print("top_keys", sorted(r.keys()))
    print("text", (text or "")[:500])
    print("ui", r.get("ui_actions") or am.get("ui_actions"))
    meta = am.get("metadata") if isinstance(am.get("metadata"), dict) else {}
    print("metadata", {k: meta.get(k) for k in list(meta)[:12]} if meta else am)

    r2 = post(
        "/agent/chat",
        {
            "message": (
                "Use the open_project_material tool with path "
                "files/materials/mp-zw.catalyst.json for project phase4-demo. "
                "Then confirm what material opened."
            ),
            "current_workspace": {
                "agent_model_profile": "agy/3.5-flash-medium",
                "agent_effort": "medium",
                "project_id": "phase4-demo",
                "active_project_id": "phase4-demo",
            },
        },
    )
    am2 = r2.get("assistant_message") or {}
    text2 = am2.get("text") or ""
    print("=== P3 OPEN ===")
    print("text", (text2 or "")[:700])
    ui = r2.get("ui_actions") or am2.get("ui_actions") or []
    print("ui", json.dumps(ui, indent=2)[:1200])
    print("actions", (r2.get("actions") or am2.get("actions") or [])[:8])


if __name__ == "__main__":
    main()
