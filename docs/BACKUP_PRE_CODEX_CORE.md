# Catalyst backup ? pre Codex-as-core

Created: 2026-07-13T12:04:51.6396639+05:30
Branch: backup/pre-codex-core-20260713-120450
Tag: backup-pre-codex-core-20260713-120450
Commit: 8e3d054b5de7ed307a709c4c4e59e528669aea39
Zip: E:\Coding\catalyst\backups\catalyst-pre-codex-core-20260713-120450.zip (0.5 MB)

## Restore (git)
```
git checkout backup/pre-codex-core-20260713-120450
# or
git checkout backup-pre-codex-core-20260713-120450
```

## Restore (zip)
Unzip into a clean folder; run frontend npm install and backend deps as usual.
Does NOT include node_modules, data/processed, or mp_cache.

## What this is
Snapshot of the modularized Catalyst tree (store mixins, appStore slices, agent package, streaming UX, live viewport context) before making Codex SDK the core agent harness.
