#!/usr/bin/env python3
"""Catalyst one-shot bootstrap for demo / friend laptop.

Usage (from repo root):
  python init.py              # install + PATH shim + check secrets
  python init.py --yes        # non-interactive installs
  python init.py --run        # install then start (same as `catalyst`)
  python init.py --check      # verify only

After init, type:  catalyst
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import venv
from pathlib import Path

REQUIRED_PYTHON = (3, 11)
REQUIRED_MODULES = (
    "duckdb",
    "fastapi",
    "uvicorn",
    "pandas",
    "pyarrow",
    "pymatgen",
    "pydantic",
    "websockets",
    "google.genai",
)

SECRET_KEYS = (
    ("GEMINI_API_KEY", "Gemini / Live voice API key (AI Studio)"),
    ("MP_API_KEY", "Materials Project API key (spectra / enrich)"),
)


def root() -> Path:
    return Path(__file__).resolve().parent


def is_win() -> bool:
    return os.name == "nt"


def status(label: str, state: str, detail: str = "") -> None:
    extra = f"  {detail}" if detail else ""
    print(f"  {label:<26} {state:<10}{extra}")


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=check)


def venv_python(repo: Path) -> Path:
    if is_win():
        return repo / ".venv" / "Scripts" / "python.exe"
    return repo / ".venv" / "bin" / "python"


def load_dotenv(repo: Path) -> dict[str, str]:
    path = repo / ".env"
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def write_dotenv(repo: Path, values: dict[str, str]) -> None:
    path = repo / ".env"
    example = repo / ".env.example"
    lines: list[str] = []
    if example.exists():
        lines = example.read_text(encoding="utf-8-sig").splitlines()
    else:
        lines = [f"{k}=" for k in values]
    existing = load_dotenv(repo)
    existing.update({k: v for k, v in values.items() if v})
    # Rebuild from example keys + extras
    seen: set[str] = set()
    out_lines: list[str] = []
    for line in lines:
        if line.strip().startswith("#") or "=" not in line or line.strip().startswith("# "):
            out_lines.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if k.startswith("#"):
            out_lines.append(line)
            continue
        seen.add(k)
        out_lines.append(f"{k}={existing.get(k, '')}")
    for k, v in existing.items():
        if k not in seen:
            out_lines.append(f"{k}={v}")
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def ensure_python() -> None:
    if sys.version_info < REQUIRED_PYTHON:
        raise SystemExit(
            f"Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ required (found {platform.python_version()})."
        )
    status("python", "ok", platform.python_version())


def ensure_node() -> None:
    node = which("node")
    npm = which("npm.cmd" if is_win() else "npm")
    if not node or not npm:
        raise SystemExit("Node.js 20+ and npm required. Install from https://nodejs.org then re-run init.py")
    status("node", "ok", node)
    status("npm", "ok", npm)


def ensure_venv(repo: Path, yes: bool) -> Path:
    py = venv_python(repo)
    if py.exists():
        status("venv", "ok", str(py))
        return py
    if not yes:
        ans = input("  Create .venv? [Y/n] ").strip().lower()
        if ans in {"n", "no"}:
            raise SystemExit("Need .venv to continue.")
    status("venv", "create", str(repo / ".venv"))
    venv.EnvBuilder(with_pip=True).create(str(repo / ".venv"))
    return venv_python(repo)


def modules_missing(py: Path) -> list[str]:
    code = (
        "import importlib.util\n"
        f"mods={list(REQUIRED_MODULES)!r}\n"
        "missing=[]\n"
        "for m in mods:\n"
        "    name=m.split('.')[0]\n"
        "    if importlib.util.find_spec(name) is None: missing.append(m)\n"
        "print('\\n'.join(missing))\n"
    )
    r = subprocess.run([str(py), "-c", code], capture_output=True, text=True)
    return [x.strip() for x in r.stdout.splitlines() if x.strip()]


def ensure_python_deps(repo: Path, py: Path, yes: bool) -> None:
    missing = modules_missing(py)
    if not missing:
        status("python packages", "ok")
        return
    status("python packages", "missing", ", ".join(missing))
    if not yes:
        ans = input("  Install backend requirements? [Y/n] ").strip().lower()
        if ans in {"n", "no"}:
            raise SystemExit("Backend packages required.")
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"], cwd=repo)
    req = repo / "code" / "backend" / "pipeline" / "requirements-runtime.txt"
    if req.exists():
        run([str(py), "-m", "pip", "install", "-r", str(req)], cwd=repo)
    run([str(py), "-m", "pip", "install", "-e", str(repo / "code" / "backend" / "pipeline")], cwd=repo)
    still = modules_missing(py)
    if still:
        raise SystemExit(f"Still missing: {', '.join(still)}")
    status("python packages", "ok")


def ensure_frontend(repo: Path, yes: bool) -> None:
    fe = repo / "code" / "frontend"
    nm = fe / "node_modules"
    if nm.exists() and any(nm.iterdir()):
        status("frontend packages", "ok")
        return
    status("frontend packages", "missing")
    if not yes:
        ans = input("  Run npm install? [Y/n] ").strip().lower()
        if ans in {"n", "no"}:
            raise SystemExit("Frontend packages required.")
    npm = "npm.cmd" if is_win() else "npm"
    run([npm, "install"], cwd=fe)
    status("frontend packages", "ok")


def ensure_env_secrets(repo: Path, yes: bool) -> None:
    env_path = repo / ".env"
    example = repo / ".env.example"
    if not env_path.exists() and example.exists():
        shutil.copy(example, env_path)
        status(".env", "created", "from .env.example")
    vals = load_dotenv(repo)
    # Defaults for demo
    defaults = {
        "CATALYST_AGENT_CORE": "antigravity",
        "CATALYST_AGY_CLI": "1",
        "CATALYST_PREFER_AGY_CLI": "1",
        "CATALYST_REPO_ROOT": str(repo),
        "CATALYST_GEMINI_LIVE_MODEL": "gemini-2.5-flash-native-audio-preview-12-2025",
    }
    for k, v in defaults.items():
        if not vals.get(k):
            vals[k] = v

    # Locate agy
    agy = which("agy") or which("agy.exe")
    win_agy = Path.home() / "AppData" / "Local" / "agy" / "bin" / "agy.exe"
    if not agy and win_agy.is_file():
        agy = str(win_agy)
    if agy and not vals.get("CATALYST_AGY_BIN"):
        vals["CATALYST_AGY_BIN"] = agy

    missing = [k for k, _ in SECRET_KEYS if not vals.get(k)]
    if missing and not yes:
        print()
        print("  Secrets needed (paste then Enter; leave blank to skip):")
        for key, desc in SECRET_KEYS:
            if vals.get(key):
                status(key, "ok", "(set)")
                continue
            try:
                pasted = input(f"  {desc}\n  {key}= ").strip()
            except EOFError:
                pasted = ""
            if pasted:
                vals[key] = pasted
                status(key, "set")
            else:
                status(key, "missing", "demo may degrade")
    elif missing and yes:
        for key, _ in SECRET_KEYS:
            if not vals.get(key):
                status(key, "missing", "set later in .env")
    else:
        for key, _ in SECRET_KEYS:
            status(key, "ok" if vals.get(key) else "missing")

    write_dotenv(repo, vals)
    status(".env", "ok", str(env_path))


def ensure_data_layout(repo: Path) -> None:
    processed = repo / "data" / "processed" / "catalyst" / "v2025.09.25"
    local = repo / "data" / "local"
    for name in ("logs", "sessions", "exports", "mp_cache", "candidate_sets"):
        (local / name).mkdir(parents=True, exist_ok=True)
    settings_ex = local / "settings.example.json"
    settings = local / "settings.json"
    if not settings.exists() and settings_ex.exists():
        shutil.copy(settings_ex, settings)
    if processed.exists() and any(processed.iterdir()):
        status("materials snapshot", "ok", str(processed))
    else:
        status(
            "materials snapshot",
            "MISSING",
            "data/processed/.../v2025.09.25 not found ? copy from mini/USB data pack for full demo",
        )


def ensure_runtime_config(repo: Path) -> None:
    cfg = repo / "code" / "frontend" / "public" / "runtime-config.json"
    dist_cfg = repo / "code" / "frontend" / "dist" / "runtime-config.json"
    payload = {"apiBaseUrl": "http://127.0.0.1:8766"}
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if dist_cfg.parent.exists():
        dist_cfg.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    status("runtime-config", "ok", "http://127.0.0.1:8766")


def ensure_settings_demo(repo: Path) -> None:
    settings_path = repo / "data" / "local" / "settings.json"
    if not settings_path.exists():
        return
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return
    prov = data.setdefault("providers", {})
    prov["active_provider"] = "gemini"
    models = prov.setdefault("models", {})
    models["gemini"] = models.get("gemini") or "agy/3.5-flash-medium"
    # Clean provider order: gemini first only essentials
    prov["provider_order"] = ["gemini"]
    prov["fallback_models"] = {"gemini": ["gemini-3.1-flash-lite", "gemini-2.5-flash"]}
    # Drop micro base urls from demo defaults
    prov["base_urls"] = {}
    settings_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status("settings", "ok", "gemini / Balanced profile")


def check_agy(yes: bool) -> None:
    agy = which("agy") or which("agy.exe")
    win = Path.home() / "AppData" / "Local" / "agy" / "bin" / "agy.exe"
    if not agy and win.is_file():
        agy = str(win)
    if not agy:
        status("agy CLI", "missing", "optional ? install Antigravity CLI for OAuth models")
        print("    Download: https://antigravity.google/  then re-run init.py")
        return
    status("agy CLI", "ok", agy)
    # Probe login (models list)
    try:
        r = subprocess.run([agy, "models"], capture_output=True, text=True, timeout=45, stdin=subprocess.DEVNULL)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0 and "Flash" in out:
            status("agy auth", "ok", "models listed")
            return
        if "sign in" in out.lower() or "not logged" in out.lower() or "Authentication" in out:
            status("agy auth", "needed", "login required")
            if yes:
                print("    Run in a real terminal: agy")
                print("    Complete Google sign-in / paste code there, then re-run init.")
                return
            ans = input("  Open interactive AGY login now? [Y/n] ").strip().lower()
            if ans in {"n", "no"}:
                return
            # Open new console for interactive login
            if is_win():
                subprocess.Popen(
                    ["cmd", "/c", "start", "Catalyst AGY Login", "cmd", "/k", f'"{agy}"'],
                    shell=False,
                )
                print("    Complete login in the new window, then press Enter here.")
                input("  Press Enter when login is done? ")
            else:
                print(f"    Run: {agy}")
                input("  Press Enter when login is done? ")
        else:
            status("agy auth", "unknown", out[:120].replace("\n", " "))
    except Exception as exc:
        status("agy auth", "error", str(exc)[:120])


def install_shim(repo: Path) -> None:
    """Install `catalyst` on user PATH ? scripts/catalyst.py run."""
    bin_dir = repo / "code" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = repo / "scripts" / "catalyst.py"
    if is_win():
        cmd = bin_dir / "catalyst.cmd"
        # Call venv python if present
        body = f"""@echo off
set "REPO={repo}"
set "VENV_PY=%REPO%\\.venv\\Scripts\\python.exe"
if exist "%VENV_PY%" (
  "%VENV_PY%" "%REPO%\\scripts\\catalyst.py" %*
) else (
  python "%REPO%\\scripts\\catalyst.py" %*
)
"""
        cmd.write_text(body, encoding="ascii")
        status("shim", "ok", str(cmd))
        # User PATH
        user_path = os.environ.get("PATH", "")
        try:
            import winreg

            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE)
            try:
                current, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current = ""
            parts = [p for p in current.split(";") if p]
            if str(bin_dir) not in parts:
                parts.append(str(bin_dir))
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(parts))
                status("PATH", "updated", str(bin_dir))
                print("    Open a NEW terminal, then type: catalyst")
            else:
                status("PATH", "ok", str(bin_dir))
            winreg.CloseKey(key)
        except Exception as exc:
            status("PATH", "manual", f"add {bin_dir} to user PATH ({exc})")
    else:
        shim = bin_dir / "catalyst"
        shim.write_text(
            f"""#!/usr/bin/env bash
REPO="{repo}"
if [[ -x "$REPO/.venv/bin/python" ]]; then
  exec "$REPO/.venv/bin/python" "$REPO/scripts/catalyst.py" "$@"
else
  exec python3 "$REPO/scripts/catalyst.py" "$@"
fi
""",
            encoding="utf-8",
        )
        shim.chmod(0o755)
        status("shim", "ok", str(shim))
        print(f"    Add to PATH: export PATH=\"{bin_dir}:$PATH\"")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Catalyst for demo / friend laptop")
    parser.add_argument("--yes", "-y", action="store_true", help="Non-interactive installs")
    parser.add_argument("--check", action="store_true", help="Check only")
    parser.add_argument("--run", action="store_true", help="After init, start catalyst")
    parser.add_argument("--skip-agy", action="store_true", help="Skip AGY login checks")
    args = parser.parse_args()

    repo = root()
    print()
    print("Catalyst init")
    print("=============")
    print(f"  repo: {repo}")
    print()

    ensure_python()
    ensure_node()
    if args.check:
        py = venv_python(repo)
        if py.exists():
            status("venv", "ok", str(py))
            miss = modules_missing(py)
            status("python packages", "ok" if not miss else "missing", ", ".join(miss))
        else:
            status("venv", "missing")
        ensure_data_layout(repo)
        return 0

    py = ensure_venv(repo, args.yes)
    ensure_python_deps(repo, py, args.yes)
    ensure_frontend(repo, args.yes)
    ensure_env_secrets(repo, args.yes)
    ensure_data_layout(repo)
    ensure_runtime_config(repo)
    ensure_settings_demo(repo)
    if not args.skip_agy:
        check_agy(args.yes)
    install_shim(repo)

    # Light preflight via package if available
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "code" / "backend" / "pipeline")
    env["CATALYST_REPO_ROOT"] = str(repo)
    try:
        r = subprocess.run(
            [
                str(py),
                "-c",
                "from pathlib import Path; from catalyst.preflight import run_preflight, print_preflight; "
                f"r=run_preflight(Path(r'{repo}'), check_ports=False); print_preflight(r); "
                "raise SystemExit(0 if r.get('status')=='ok' else 1)",
            ],
            cwd=str(repo),
            env=env,
            capture_output=True,
            text=True,
        )
        if r.stdout:
            print(r.stdout)
        if r.returncode != 0 and r.stderr:
            print(r.stderr[:500])
        status("preflight", "ok" if r.returncode == 0 else "warn")
    except Exception as exc:
        status("preflight", "skip", str(exc)[:80])

    print()
    print("Init complete.")
    print("  New terminal ? type:  catalyst")
    print("  Or:  python scripts/catalyst.py --yes")
    print("  UI:  http://127.0.0.1:5173")
    print("  API: http://127.0.0.1:8766/health")
    print()

    if args.run:
        launcher = repo / "scripts" / "catalyst.py"
        return subprocess.call([str(py), str(launcher), "--yes"], cwd=str(repo), env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
