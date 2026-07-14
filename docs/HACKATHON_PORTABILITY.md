# Catalyst ? hackathon portability

Goal: develop on desktop PC, present from **mini server** or a **friend?s laptop**, with data optionally staying on the mini, without ?only works on my home PC.?

## Target topologies

### A) Preferred ? one clean URL on mini

```text
Laptop browser  ?  https://mini.tail? or http://mini:PORT
                      ?
                      ?? UI (static or Vite preview)
                      ?? API :8766  (same host)
                           ?
                           ?? data/processed  (local on mini)
                           ?? data/local/*    (sessions, mp_cache, settings)
                           ?? env secrets (GEMINI, MP, MICRO)
```

### B) Laptop UI + mini data/API

```text
Laptop :5173 UI  ?  API_BASE = http://mini:8766
Mini holds DuckDB + processed snapshot + sessions
```

UI must use **runtime-config / VITE_CATALYST_API_BASE**, never hardcode `127.0.0.1` for demos.

### C) Friend laptop full stack (no data copy)

- Clone/copy **code only**
- Point `CATALYST_DATA` / processed paths or mount to mini data if available
- Or use a slim processed subset if offline

## What must NOT be machine-local only

| Asset | Location | Notes |
|---|---|---|
| Code | Git private repo + USB zip | No absolute home-only paths in code |
| Secrets | `.env` (gitignored) | Template: `.env.example` ? copy on each machine |
| Google / AGY auth | Per-machine login or API key | Friend uses **their** Gemini/AGY subscription |
| MP key | `.env` `MP_API_KEY` | Shared project key OK if policy allows |
| Optional micro gateway | Optional | Last-resort OpenAI-compatible only; not demo default |
| Sessions / mp_cache | `data/local/` | Per-host or shared volume |

## Copy layers (safety)

1. **Private GitHub** ? source of truth for code  
2. **USB** ? full repo zip (optional `data/processed` if small enough; else code-only)  
3. **Mini server** ? production-ish runtime  

## Setup scripts (target commands)

Keep these as the only ?setup path? (implement/refine over time):

```bash
# On any machine with code checkout
cp .env.example .env   # fill GEMINI_API_KEY, MP_API_KEY, CATALYST_AGENT_CORE=antigravity

# Backend
export PYTHONPATH=code/backend/pipeline
export CATALYST_REPO_ROOT=$(pwd)
pip install -r code/backend/pipeline/requirements-runtime.txt
python -c "import uvicorn; uvicorn.run('catalyst.local_api:app', host='0.0.0.0', port=8766)"

# Frontend (dev)
cd code/frontend && npm ci && npm run dev -- --host 0.0.0.0 --port 5173

# Frontend (single-host demo)
npm run build && serve dist behind API static mount (already supported when dist present)
```

Windows PowerShell equivalent should live in `scripts/` (see `scripts/start-catalyst-live.sh` and add `scripts/start-demo.ps1` when ready).

## Auth on presentation machine

| Mode | How |
|---|---|
| **Antigravity / Gemini API** | Set `GEMINI_API_KEY` from AI Studio or Google AI for that account |
| **agy subscription models** | Install `agy`, run once to **Google Sign-In**, set model profile `agy/3.5-flash-*` ? Catalyst uses CLI transport |
| **Friend subscription** | They sign into `agy` **or** paste their `GEMINI_API_KEY` into `.env` |

**Important:** AGY desktop OAuth is **not** a portable file you copy from home PC. At the venue, re-login `agy` or use a key.

```text
# Prefer API agent
CATALYST_AGENT_CORE=antigravity

# Prefer subscription CLI models when profile is agy/*
# (default when agy is installed)
# CATALYST_AGY_CLI=1
# CATALYST_AGY_BIN=C:\path\to\agy.exe

# Force CLI only
# CATALYST_AGENT_TRANSPORT=agy_cli
```

## Environment checklist (print before demo)

- [ ] `CATALYST_REPO_ROOT` points at checkout  
- [ ] `CATALYST_AGENT_CORE=antigravity` (or `llm` emergency)  
- [ ] `GEMINI_API_KEY` works (`curl` / smoke)  
- [ ] `MP_API_KEY` for enrich/spectra  
- [ ] `data/processed/.../v2025.09.25` present **or** reachable  
- [ ] API on `0.0.0.0:8766`, UI hits that host  
- [ ] `runtime-config.json` / `VITE_CATALYST_API_BASE` correct for single URL  
- [ ] One smoke: open material, hop, agent ?what am I looking at??, enrich  

## Development rules (ongoing)

1. **No hardcoded desktop paths** in runtime code.  
2. **Secrets only via env / `.env`**.  
3. Prefer **relative repo paths** and `CATALYST_REPO_ROOT`.  
4. Agent core pluggable (`antigravity` / `llm`) so venue can force fallback.  
5. UI API base configurable for mini vs local.  
6. Document any new env var in `.env.example` + this file.

## Emergency fallback at venue

```text
CATALYST_AGENT_CORE=llm
# Gemini native tool loop ? already battle-tested for materials UI
```

Hops, sessions, MP enrich, neighbors ui_actions must keep working without Antigravity.
