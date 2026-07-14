# Catalyst ship checkpoint

**One-command friend laptop setup**

```text
1. Unzip catalyst-ship-*.zip
2. Open folder in terminal
3. python init.py
4. New terminal ? catalyst
5. Browser ? http://127.0.0.1:5173
```

## What `init.py` does

- Checks Python 3.11+ and Node/npm  
- Creates `.venv`, installs backend requirements  
- `npm install` for frontend  
- Creates `.env` and prompts for `GEMINI_API_KEY` / `MP_API_KEY`  
- Points UI at local API (`runtime-config.json`)  
- Installs PATH shim so `catalyst` starts API + UI  
- Checks Antigravity CLI (`agy`) and offers login window if needed  

## What is NOT in the zip

- `node_modules`, `.venv` (rebuilt on target)  
- Local sessions / exports / traces / secrets (`.env`)  
- graphify cache  

## What IS in the zip

- Application code (frontend + backend)  
- `data/processed/.../v2025.09.25` materials snapshot (demo corpus)  
- Demo workspace files under `data/workspaces/`  
- `init.py`, `scripts/catalyst.py`, docs  

## Auth

| Need | How |
|---|---|
| Chat API / Live | `GEMINI_API_KEY` in `.env` |
| Spectra enrich | `MP_API_KEY` |
| High-quota models | Install `agy`, run `agy` once, Google sign-in |

## Backups

1. This zip on USB  
2. Private GitHub (`catalystpvt` or ship repo)  
3. Archive copy on mini under `~/catalyst-ship/`  

## Demo smoke

- Open random material ? structure  
- Neighbors hop  
- Agent: ?what material is open??  
- Optional: voice (needs API key + mic)  
