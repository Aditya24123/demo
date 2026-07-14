# Catalyst Hardening Plan

**Status:** Active  
**Created:** 2026-07-13  
**Context:** Hackathon-bound materials demo. Biochemistry deferred.  
**Pre-edit snapshot:** see `docs/HARDENING_BACKUP.md` for backup location.

This document captures the full brain dump, diagnosis, agreed strategy, and phased work plan discussed before Phase 1 implementation.

---

## 1. Product stance (agreed)

- **Harden materials Catalyst first.** Do not bolt on DNA/protein/folding until the materials loop is truthful and demo-ready.
- Teammate may **research** biochemistry/APIs in parallel; that is not the active implementation track.
- Prefer **one flawless judge chain** over breadth (many models, full MP clone, full bio suite).
- Foundation is usable (local snapshot, agent tools, structure data, projects, Codex lane). This is **interaction hardening + product model**, not a rewrite.

### Demo chain (target story)

```text
Ask Catalyst
  ? select a real material (UI updates)
  ? open structure viewer (sites render)
  ? inspect only real properties
  ? switch / create chats reliably
  ? (optional) project notebook: save + agent context
  ? cite local/MP provenance where shown
```

---

## 2. Diagnosis (second opinion)

Prior agent analysis is **mostly correct**. Key points confirmed against code + screenshots:

| Finding | Verdict |
|---|---|
| Agent claims CdS selected; canvas stays on **NO / mp-cpdzm** | Confirmed (end-to-end action/state bug) |
| Split-brain UI: `activeSheet`/`openSheet` vs `inspectorOpen`/`workspaceTab`/`railMode` | Confirmed |
| Agent backend success ? user-visible success | Confirmed; no client acknowledgement |
| Structure is a fragile double hop (tool result not placed in viewer cache) | Confirmed |
| Notebook/Codex isolated from main agent | Confirmed |
| Sessions partially wired (backend richer than UI) | Confirmed |
| MP is snapshot/ingest-heavy; not live FastAPI fallback | Confirmed as product gap |
| Empty property/spectra shells should hide | Correct for demo bar |
| Model services framework empty | Correct; do not advertise as ready |
| Do not integrate ten bio models first | Strongly agree |

### Sharpening notes

1. Fixing only `openSheet('inspector')` is necessary but may not be sufficient. Need one **material-focus path**: home rail + select material + optional structure tab + inspector open + structure load.
2. ?Projects contain chats/notebooks? is product-model work, not only a bugfix.
3. MP live API + MP-quality 3D are high value but **secondary to truthfulness**.
4. Settings need reliability/clarity more than a full Jarvis clone for hackathon.

### Root technical sketch

- Live shell: `layoutStore` (`inspectorOpen`, `workspaceTab`, `railMode`) + `appStore` workspace.
- Agent `ui_actions` still call legacy `openSheet('inspector')` in places.
- `select_node` does call `selectNode`, but structure load depends on tab effects and ordering; no hard verify that the canvas moved.
- Neighbors graph is seeded from `workspace.resolvedMaterialId` ? if selection fails, UI stays on previous material (e.g. NO).

---

## 3. Full brain dump inventory

### A. Live bugs / broken UX

1. Agent says material selected; UI does not select  
2. Agent says structure loaded; viewer does not show it  
3. Agent cannot reliably control the workspace  
4. Save button not working (notebook)  
5. Notebook chat / workspace agent (Codex) not working  
6. New chat button does not work  
7. Session switching does not work  
8. Property prediction models not available / over-advertised  
9. Agent tools feel broken end-to-end  
10. Too many separator lines (keep sidebar boundary only)

### B. Agent / copilot requirements

11. Workspace-aware AI (material, project, notebook, selection)  
12. Agent must drive workspace actions  
13. Truthful agent copy (only claim verified UI outcomes)  
14. Codex / Codex SDK available beyond notebook (main chat, research, files)  
15. One agent system with modes, not two disconnected chats  
16. Better providers/models settings (Jarvis-quality direction)  
17. Hosted OpenAI-compatible multi-model API available ? test before depending  
18. Voice-mode bug reports count as product truth  

### C. Sessions, chats, projects

19. Chats renamable (sidebar + click title in heading)  
20. Context menu: rename / delete / archive  
21. Sessions deletable and archivable  
22. Projects hold chats  
23. Chats movable to project or general/no-project  
24. Projects encompass notebooks (notebook not independent)  
25. Project has own folder, notebooks/, chats, artifacts  
26. Opening a project enables full work in it  
27. Default agent-first + workspace-first (not filesystem-first)  

### D. Notebook / files UI

28. Files section collapsible  
29. File system toggle off by default  
30. When on: open/edit/choose files  
31. Notebook chat works  
32. Save trustworthy  
33. Codex ready path when runtime available  

### E. Materials presentation / data

34. Materials Project?like structure viewer  
35. Better crystal structure (not naive preview only)  
36. Optionally pull structure from MP API  
37. Integrate MP API: enrichment, auto summary, spectra, missing fields  
38. Summary above key properties (MP-style description)  
39. Capability-driven UI: hide missing props/sections/tabs  
40. Filter properties/relations; less ?blob?  
41. Local snapshot first; MP as fallback/enrich  
42. Provenance for demo trust  

### F. Scientific services / models (later; teammate research)

43. OpenFold 3 (NVIDIA NIM)  
44. Boltz 2  
45. MSA search  
46. GenMol  
47. AlphaFold 2 Multimer  
48. ProteinMPNN  
49. DiffDock (noted as ?Diffrock?)  
50. MolMIM  
51. Materials property prediction models  
52. DNA / biomolecules UI + file types + agent workflows  
53. Document free API options when not available  

### G. Settings / providers

54. Settings quality like Jarvis  
55. Usable API keys / model selection  
56. Clear provider status (ready / missing key)  
57. Hosted OpenAI-compatible gateway as candidate  
58. Smoke-test before leaning on hosted API  

### H. UI polish

59. Fewer separators  
60. Some left-sidebar icons change  
61. Hackathon-flawless polish  
62. MP reference UI (structure + properties layout)  

### I. Architecture work items

63. Unify UI state; retire live legacy sheet path for workspace actions  
64. Typed UI action contract + client acknowledgements  
65. Integration/smoke tests: select, structure, session, save, new chat  
66. Project ownership first-class  
67. MP second-tier live source + cache-on-read  
68. Material capability manifest  
69. Structure viewer upgrades (PBC, supercell, bonds, controls)  
70. Model services: configure real ones later; never fake readiness  
71. Notebook model: reverse default to workspace/agent-first  

### J. Sequencing freezes

72. No biochem implementation right now  
73. Harden materials first  
74. Then models / bio  
75. Flawless demo chain over breadth  

---

## 4. Phased approach (agreed strategy)

### Phase 0 ? Freeze product story

- One judge path (see ?1).  
- Bio frozen for implementation.  
- Full project?chat taxonomy optional unless pitch requires it.  

### Phase 1 ? Interaction truth (active after snapshot)

**Goal:** agent and canvas tell the same story.

1. Single **UI action executor** against live layout store  
2. **Select material** always updates title/id/workspace  
3. **Show structure** always switches tab + loads + renders  
4. Client **ack or fail** (toast / clear failure if focus failed)  
5. Prefer not claiming success when UI did not land (client-side honesty path)  
6. Smoke checks: select material, show structure  

**Done when:** select + structure either work visibly or clearly fail.

### Phase 2 ? Sessions + agent reliability

- New chat, switch session, rename, delete (archive if easy)  
- Settings: provider/model/base URL + ready vs missing key  
- Optional smoke of hosted OpenAI-compatible API  

### Phase 3 ? Materials page intentional

- Hide empty tabs/sections  
- Summary + key properties  
- Structure viewer ?good enough?  
- MP live only if demo needs missing data  

### Phase 4 ? Project / notebook minimum

- Open project, save notebook, files collapsed by default  
- Only if notebook is in the pitch  

### Phase 5 ? Unify agent modes

- Materials mode vs project mode; shared context  

### Phase 6 ? Enrichment & power

- MP fallback/cache, better crystal viewer, one materials predictor, polish, then bio as second workspace type  

### Explicit defer list (hackathon)

| Defer | Why |
|---|---|
| Full bio stack | Dilutes demo; teammate research |
| Full project?chat taxonomy | Good product, not critical path |
| Perfect MP clone UI | Reference, not requirement |
| Many prediction services | Empty breadth worse than one honest path |
| Total UI redesign | Hardening ? redesign |

### Priority ranking

| Order | Workstream |
|---|---|
| 1 | Agent ? UI select/structure truth |
| 2 | New chat + session switch |
| 3 | Hide empty props/spectra |
| 4 | Settings/provider clarity |
| 5 | Notebook save + collapsible files (if in pitch) |
| 6 | Viewer quality / MP enrich |
| 7 | Codex everywhere / project-owned chats |
| 8 | Bio + many model APIs |

---

## 5. One-sentence strategy

**Make the copilot and the materials canvas inseparable and truthful; then make the page look intentional; then deepen data and services; bio last.**

---

## 6. Clarifications still useful (from user when ready)

1. Is notebook/Codex in the live demo script?  
2. Project-scoped chats required for pitch, or flat chats OK short-term?  
3. MP API key available and required for demo?  
4. Hosted LLM API ready to test now?  
5. Days until freeze?  

---

## 7. Execution log

| Date | Event |
|---|---|
| 2026-07-13 | Plan written; pre-Phase-1 backup created |
| 2026-07-13 | **Phase 1 implemented** ? live UI action executor, select/structure focus, client fail toasts, voice ui_actions, silent auto-neighborhood, agent honesty rules |
| 2026-07-13 | **Phase 2 implemented** ? sessions new/switch/rename/archive/delete; micro OpenAI-compatible provider on mini (`auto/best-chat`); settings Models UX + endpoint test; `stream:false` for OpenAI-compatible gateways |
| 2026-07-13 | **Phase 3 implemented** ? selected-material MP enrich + disk cache; prefetch on select; capability-driven Spectra/property tabs; MP-style description summary; structure viewer polish (periodic bonds + gizmo) |
| 2026-07-13 | **Phase 4 implemented** ? open project (rail + empty-state create/open list); save notebook via dedicated `/notebook` API + Ctrl/Cmd+S + toast; files rail **collapsed by default** (persisted); folders collapsible (start closed); `open_project` ui_action |
| 2026-07-13 | **Phase 5 implemented** ? unified agent: rail-driven materials/project surface; shared `current_workspace` context; single session chat path (no Auto/Workspace split); backend mode_guidance + project_id hydration; surface-aware starters |

### Phase 1 ? what shipped

| Item | Status |
|---|---|
| Single UI action executor (`uiActions.ts` + `appStore.applyUiActions`) | Implemented |
| Select material ? home rail + workspace load + inspector | Implemented |
| Structure tab ? set tab + force load structure cache | Implemented |
| Client ack/fail toasts when select/structure does not land | Implemented |
| Legacy `openSheet('inspector')` no longer the only path for agent focus | Implemented |
| Command executor / graph click use live inspector flags | Implemented |
| Voice turn/tool results apply the same ui_actions path | Implemented |
| Auto neighborhood expand silent (no toast spam) | Implemented |
| Agent persona: no fake model ads; careful about UI claims | Implemented |
| Full browser smoke of CdS select/structure | **Not verified here** ? needs manual check on running app |

### Phase 1 ? files touched

- `code/frontend/src/catalyst/ui-state/uiActions.ts` (new)
- `code/frontend/src/catalyst/ui-state/appStore.ts`
- `code/frontend/src/catalyst/bridge/hooks.ts`
- `code/frontend/src/components/workspace/WorkspaceShell.tsx`
- `code/frontend/src/components/graph/GraphCanvas.tsx`
- `code/frontend/src/lib/voiceLive.ts`
- `code/backend/pipeline/catalyst/agent_runtime.py`
- `docs/HARDENING_PLAN.md`, `docs/HARDENING_BACKUP.md`

### Manual smoke (do next)

1. Ask: ?find a good non-metal and select it? (or select CdS) ? title/id must change on canvas  
2. Ask: ?show the structure? ? Structure tab + atoms render  
3. If select fails ? error toast, not silent stay on previous material

---

## Related docs

- [UI_HARDENING_HANDOFF.md](./UI_HARDENING_HANDOFF.md) ? earlier UI shell hardening notes  
- [API_CONTRACT.md](./API_CONTRACT.md) ? backend surface  
- [RUNBOOK.md](./RUNBOOK.md) ? run/deploy  
- [HARDENING_BACKUP.md](./HARDENING_BACKUP.md) ? snapshot location and restore notes  
