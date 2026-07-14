# Skill: Project / notebook

## When enabled

`agent_surface` is `project` (notebook rail) **or** a `project_id` is present in RunContext.

## Prefer tools

- `list_project_files`, `read_project_file`, `write_project_file`
- `read_project_notebook`, `update_project_notebook`
- `list_project_runs`, `run_workspace_agent` (Codex project executor)

## Defaults

- Use `RunContext.project.id` when the user omits project id.
- Materials tools remain valid if the user asks about a material in context of the project.

## Style

- Be concrete about file paths and notebook edits.
- After writes, summarize what changed; do not invent file contents you did not read or write.
