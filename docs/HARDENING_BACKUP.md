# Hardening pre-edit snapshot

**Created:** 2026-07-13  
**Purpose:** Full working-tree snapshot **before Phase 1 code edits**, so the project can be restored if hardening goes sideways.

## Location

```text
E:\Coding\catalyst_backups\catalyst_pre_phase1_20260713_010220
```

## What was copied

Robocopy of the Catalyst tree with heavy/generated dirs excluded:

| Included | Excluded |
|---|---|
| `code/`, `docs/`, `data/`, `scripts/` | `node_modules` |
| Root config / `AGENTS.md` / skills metadata | `.git` |
| | `dist`, `.vite`, `__pycache__`, `graphify-out`, `.pytest_cache` |

File count in snapshot (approx): **514** files (excludes installed deps).

## Restore notes

1. Prefer restoring specific files/folders from the backup rather than overwriting the whole tree blindly.
2. After restoring frontend source, reinstall deps: `npm install` in `code/frontend`.
3. Backend Python env is not fully snapshotted as a venv; use existing local env or recreate from project requirements.
4. Runtime data under `data/local/` (sessions, etc.) may differ after use ? restore only if you need that exact local state.

## Related

- Plan: [HARDENING_PLAN.md](./HARDENING_PLAN.md)
