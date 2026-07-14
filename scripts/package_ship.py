#!/usr/bin/env python3
"""Build a portable Catalyst ship zip (code + processed snapshot, no node_modules/.venv/secrets)."""
from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

EXCLUDE_DIR_NAMES = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".vite",
    "graphify-out",
    ".grok",
    ".claude",
    ".codex",
    ".codex-run",
    "backups",  # never zip ourselves (avoids multi-GB feedback loop)
    "dist",  # rebuild on target; public assets stay via public/
    "traces",
    "sessions",
    "exports",
    "mp_cache",
    "candidate_sets",
    "research_runs",
    "research_sources",
    "research_candidates",
    "logs",
    "crashes",
    "codex-service",  # optional demoted service ? not needed for demo ship
}

EXCLUDE_FILE_GLOBS = {
    ".env",
    "settings.json",  # machine-local; example remains
}

# Keep processed snapshot for offline demo (user needs materials)
INCLUDE_PROCESSED = True


def should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = set(rel.parts)
    if parts & EXCLUDE_DIR_NAMES:
        return True
    name = path.name
    if name in EXCLUDE_FILE_GLOBS:
        return True
    if name.endswith((".pyc", ".pyo", ".log")):
        return True
    if name.startswith(".env") and name != ".env.example":
        return True
    # Skip huge agent traces
    if "data" in rel.parts and "local" in rel.parts and "agent" in rel.parts and "traces" in rel.parts:
        return True
    if not INCLUDE_PROCESSED and "processed" in rel.parts:
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-processed", action="store_true")
    args = ap.parse_args()
    global INCLUDE_PROCESSED
    if args.no_processed:
        INCLUDE_PROCESSED = False

    root = Path(__file__).resolve().parents[1]
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = args.out or (root / "backups" / f"catalyst-ship-{stamp}.zip")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Write to temp file first so a partial zip never lives under the walk root
    tmp = out.with_suffix(".zip.partial")
    if tmp.exists():
        tmp.unlink()

    count = 0
    bytes_ = 0
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dirpath, dirnames, filenames in os.walk(root):
            p = Path(dirpath)
            # prune excluded dirs in-place
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
            if should_skip(p, root) and p != root:
                dirnames[:] = []
                continue
            for fn in filenames:
                fp = p / fn
                if should_skip(fp, root):
                    continue
                if fp.resolve() == tmp.resolve() or fp.resolve() == out.resolve():
                    continue
                arc = fp.relative_to(root).as_posix()
                zf.write(fp, arcname=f"catalyst/{arc}")
                count += 1
                bytes_ += fp.stat().st_size
                if count % 500 == 0:
                    print(f"  ? {count} files, {bytes_ / 1e6:.0f} MB raw", flush=True)
    if out.exists():
        out.unlink()
    tmp.rename(out)
    print(f"Wrote {out}", flush=True)
    print(f"  files={count} raw_bytes={bytes_} zip_bytes={out.stat().st_size}", flush=True)
    print(f"  include_processed={INCLUDE_PROCESSED}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
