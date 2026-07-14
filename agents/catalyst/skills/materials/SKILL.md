# Skill: Materials workspace

## When enabled

`agent_surface` is `materials` (home / graph / candidates / research rail, not notebook).

## Prefer tools

- `resolve_material`, `search_materials`
- `get_material_workspace`, `get_material_details`, `get_material_structure`
- `get_neighborhood`, `inspect_edge`, `inspect_graph_node`
- `screen_candidates`, `compare_materials`, `select_material`
- `export_subgraph` when asked to export

## Live viewport

- For ?this / it / current / open material?, use `RunContext.viewport.material_id`.
- If viewport is empty, resolve or search before asserting a formula.

## Style

- Ground property claims in tool output.
- When selecting or showing structure, emit the proper tools / UI actions; do not bluff.
