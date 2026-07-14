# Catalyst agent package

Editable identity and skills for the workspace agent.

| File | Role |
|---|---|
| `AGENTS.md` | Static identity, honesty, voice |
| `skills/*/SKILL.md` | Domain workflows (materials, project, research) |
| `context_schema.json` | Which UI fields feed RunContext |

Runtime loader: `catalyst.agent.package` (in-memory system instruction + RunContext).

Do not rely on `data/local/agent/compiled_context.md` as the live channel ? that path is legacy/debug.
