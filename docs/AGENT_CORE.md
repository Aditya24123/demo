# Catalyst agent core

## Routing

`CATALYST_AGENT_CORE` selects the primary chat harness:

| Value | Behavior |
|---|---|
| `antigravity` (default) | AGY OAuth CLI first, then Interactions API, then Gemini tool loop |
| `llm` | Existing Gemini native tool loop (reliable demo fallback) |
| `codex` | Optional Codex core when SDK/keys available (demoted) |

### Transport order (chat)

1. **AGY OAuth CLI** (`agy`) ? subscription quota + models from `agy models`  
   - Default when `agy` is on PATH / `CATALYST_AGY_BIN` and `CATALYST_AGY_CLI` is not off  
   - `CATALYST_PREFER_AGY_CLI=1` (default)  
   - Force: `CATALYST_AGENT_TRANSPORT=agy_cli`
2. **Interactions API** ? `GEMINI_API_KEY` + managed agent + native function tools  
   - Force: `CATALYST_AGENT_TRANSPORT=api`
3. **Gemini LLM tool loop** ? native function calling on Gemini models  
4. **Degraded local tools** ? offline-ish keyword path  

On any Antigravity failure, chat **falls through** the chain above.

## Auth (P0.5 / OAuth-primary)

| Transport | Auth | Models | Tools |
|---|---|---|---|
| **AGY CLI (primary)** | Desktop Google OAuth (`agy` login) | Flash 3.5 L/M/H, Pro 3.1, Claude, GPT-OSS? | Catalyst tools via `TOOL_CALL:` protocol ? `tool_exec` |
| **Interactions API** | `GEMINI_API_KEY` | Managed Antigravity agent | Native function tools ? `tool_exec` |
| **Live voice** | `GEMINI_API_KEY` | Gemini Live (`CATALYST_GEMINI_LIVE_MODEL`) | Same `tool_exec` over Live function calls |

Desktop OAuth tokens are **not** exported as a plain API key. For venue machines:

1. Install `agy`, set `CATALYST_AGY_BIN` if needed, run `agy models` once (Google sign-in), **or**
2. Set `GEMINI_API_KEY` for AI Studio / Interactions fallback.

Optional agent id for API transport: `CATALYST_ANTIGRAVITY_AGENT` (default `antigravity-preview-05-2026`).

## Project materials (P3)

Tools `save_project_material` / `open_project_material` write and open `files/materials/<id>.catalyst.json`.  
Notebook file tree open of `*.catalyst.json` focuses the main structure viewer.

## Voice / dictation (P4)

| Feature | Path |
|---|---|
| **Dictate** | Browser Web Speech API ? composer text ? normal chat (OAuth AGY) |
| **Voice mode** | `/voice/live` WebSocket ? Gemini Live + Catalyst tools + `ui_actions` |
| **Image / short audio attach** | Gemini multimodal parts on LLM fallback path |

Live voice **requires API key** (Gemini Live WebSocket). Text chat is OAuth-primary.

## Model picker (AGY-style)

Composer model list for provider `gemini` includes:

| Profile | Meaning |
|---|---|
| `agy/3.5-flash-low` | OAuth model Flash Low (or effort steering on API) |
| `agy/3.5-flash-medium` | Default balanced |
| `agy/3.5-flash-high` | High effort multi-step |
| `agy/3.1-pro-low` / `high` | Pro tier via OAuth CLI |
| `gemini-3.1-flash-lite` etc. | Direct API models |

Legacy Omnirouter / Minimax / micro gateway model ids are **not** in the Gemini picker.

## Requirements

- `google-genai>=2.0.0` (Interactions `steps` schema).
- Local `agy` for OAuth primary (optional but recommended).
- Local tools always execute in Catalyst backend (`tool_exec.py`); UI actions unchanged.

## Safety

- Full tool registry on chat; Live uses a focused core set for voice latency.
- Allowlisted shell only (`run_allowlisted_shell`).
- Formula grounding and neighbors UI actions still enforced in post-processing.
