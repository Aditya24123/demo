# Codex-as-core agent plan

**Baseline backup:** `backup/pre-codex-core-20260713-120450` / tag `backup-pre-codex-core-20260713-120450` / commit `8e3d054`  
**Work branch:** `wip/codex-core-agent`  
**Zip:** `backups/catalyst-pre-codex-core-20260713-120450.zip`

## Architecture target

```text
UI (workspace state)
  -> RunContext builder (compact live JSON/markdown)
  -> Codex harness (core agent loop: plan, tools, web, multi-step)
       tools:
         - Catalyst materials/graph/UI tools (local truth)
         - Catalyst project tools (files, notebook)
         - research/web (Codex network and/or our adapters)
         - shell/files in project sandbox via Codex
  -> action ledger + UI receipts
  -> stream status/tokens to AgentChatBody
```

**Principle:** Codex is the **agentic core**. Catalyst is the **scientific OS** (data, tools, UI, receipts).  
Codex never invents material properties when a Catalyst tool can answer.

## Phases

### Phase 0 ? Safety net (done)
- Git branch + annotated tag + zip + manifest

### Phase 1 ? Agent package + RunContext (editability)
- Add `agents/catalyst/AGENTS.md` + `skills/materials|project|research/SKILL.md`
- `context_schema.json` + `build_run_context()` in memory
- Load identity+skills+RunContext into every turn
- Live viewport always wins over chat history

### Phase 2 ? Canonical tools
- Single typed registry in Python generating Gemini decls, OpenAI tool JSON, `/agent/tools`, tool markdown
- Remove duplicate incomplete catalogs

### Phase 3 ? Codex as core harness
- Extend `codex-service` / gateway: inject RunContext + AGENTS.md, register Catalyst tools (HTTP or in-process bridge)
- Chat path: session ? Codex thread (materials uses synthetic or active project workspace)
- Stream progress into existing SSE (`status` / `token` / `done`)
- Enable web search when Codex config allows; surface capability in RunContext

### Phase 4 ? Kill dual brain
- Remove silent deterministic pre/post LLM fallback when Codex/provider available
- Explicit degraded mode only

### Phase 5 ? UI action receipts
- action_id on ui_actions; client confirm with resulting state
- Agent claims only after receipt

### Phase 6 ? Tests + polish
- select material, structure, notebook write, Codex artifact return
- Provider sweep later; settings UI later; bio as skill later

## Immediate build slice (next coding session)
1. Phase 1 scaffold (AGENTS.md, skills, RunContext)
2. Wire chat to use RunContext in prompt (even before full Codex)
3. Phase 3 spike: one turn through Codex with RunContext + one Catalyst tool (e.g. get_material_workspace)
4. Smoke: open Re2O7, say ?what am I looking at?? ? correct material

## Restore
```bash
git checkout backup/pre-codex-core-20260713-120450
# or
git checkout backup-pre-codex-core-20260713-120450
```
