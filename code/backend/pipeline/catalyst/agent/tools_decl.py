from __future__ import annotations

from typing import Any

TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "run_demo_scenario",
        "internal_only": True,
        "description": "Load metadata for a registered deterministic Catalyst public-demo scenario. Playback is allowed only through an exact server-registered trigger.",
        "parameters": {
            "type": "object",
            "properties": {"scenario_id": {"type": "string", "enum": ["sunlight-dna"]}},
            "required": ["scenario_id"],
        },
    },
    {
        "name": "inspect_genomics_case",
        "description": "Open a grounded DNA Variant Explorer demo case (brca1, hbb, or ctg). This is educational showcase data, not clinical interpretation.",
        "parameters": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "enum": ["brca1", "hbb", "ctg"]},
                "repeat_count": {"type": "integer", "description": "Optional CTG count from 0 to 100 for the ctg case."},
                "reset_camera": {"type": "boolean"},
            },
            "required": ["case_id"],
        },
    },
    {
        "name": "control_genome_view",
        "description": "Return a safe structured command for the BRCA1 DNA view: highlight a position, zoom a bounded window, or reveal the currently visible sequence. This controls the UI only and never retrieves a full gene sequence.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["highlight", "zoom", "showSequence"]},
                "gene": {"type": "string", "description": "Currently BRCA1; additional genes can be registered later."},
                "position": {"type": "integer", "description": "Gene-relative one-based position for highlight."},
                "start": {"type": "integer", "description": "Gene-relative inclusive start for zoom."},
                "end": {"type": "integer", "description": "Gene-relative inclusive end for zoom."},
            },
            "required": ["action"],
        },
    },
    {
        "name": "resolve_material",
        "description": "Resolve a formula, free-text material mention, or Materials Project id to a local Catalyst material id.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Formula, mp-id, or material mention."}},
            "required": ["query"],
        },
    },
    {
        "name": "search_materials",
        "description": "Search and filter the local Catalyst materials snapshot.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "elements": {"type": "array", "items": {"type": "string"}},
                "chemsys": {"type": "string"},
                "stable": {"type": "boolean"},
                "metal": {"type": "boolean"},
                "magnetic": {"type": "boolean"},
                "band_gap_min": {"type": "number"},
                "band_gap_max": {"type": "number"},
                "density_min": {"type": "number"},
                "density_max": {"type": "number"},
            },
        },
    },
    {
        "name": "get_material_workspace",
        "description": "Load grounded properties, evidence, and graph context for one material id or resolvable formula.",
        "parameters": {
            "type": "object",
            "properties": {"material_id": {"type": "string", "description": "Local material id, mp-id, or formula."}},
            "required": ["material_id"],
        },
    },
    {
        "name": "get_neighborhood",
        "description": (
            "Load graph neighbors for one material and switch the UI to the Neighbors tab "
            "(not the structure viewer). Use when the user asks for neighborhood/neighbours graph."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "material_id": {"type": "string", "description": "Local material id, mp-id, or formula."},
                "depth": {"type": "integer", "description": "Hop depth 1-5 (default 1)."},
                "open_inspector": {"type": "boolean"},
            },
            "required": ["material_id"],
        },
    },
    {
        "name": "inspect_edge",
        "description": "Inspect one graph edge by id and return its grounded relation/evidence detail.",
        "parameters": {
            "type": "object",
            "properties": {"edge_id": {"type": "string", "description": "Graph edge id."}},
            "required": ["edge_id"],
        },
    },
    {
        "name": "screen_candidates",
        "description": "Rank candidate materials for a natural-language requirement. Use for find/recommend/good/best candidate requests.",
        "parameters": {
            "type": "object",
            "properties": {
                "requirement": {"type": "string"},
                "limit": {"type": "integer"},
                "include_research_candidates": {"type": "boolean"},
            },
            "required": ["requirement"],
        },
    },
    {
        "name": "compare_materials",
        "description": "Compare two or more local material ids.",
        "parameters": {
            "type": "object",
            "properties": {
                "material_ids": {"type": "array", "items": {"type": "string"}},
                "include_evidence": {"type": "boolean"},
                "include_edges": {"type": "boolean"},
            },
            "required": ["material_ids"],
        },
    },
    {
        "name": "select_material",
        "description": "Ask the UI to select, highlight, zoom to, and optionally open the inspector for a material.",
        "parameters": {
            "type": "object",
            "properties": {
                "material_id": {"type": "string", "description": "Local material id, mp-id, or formula."},
                "open_inspector": {"type": "boolean"},
            },
            "required": ["material_id"],
        },
    },
    {
        "name": "export_subgraph",
        "description": "Export a grounded subgraph for selected material ids.",
        "parameters": {
            "type": "object",
            "properties": {
                "material_ids": {"type": "array", "items": {"type": "string"}},
                "include_evidence": {"type": "boolean"},
                "include_edge_details": {"type": "boolean"},
            },
            "required": ["material_ids"],
        },
    },
    {
        "name": "start_research",
        "description": "Start literature/research mode when local data is insufficient.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "sources": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ingest_url",
        "description": "Ingest a URL into local research mode when enabled.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "purpose": {"type": "string"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "list_project_files",
        "description": "List files, folders, notebook entries, artifacts, and Codex state for the active Catalyst project.",
        "parameters": {"type": "object", "properties": {"project_id": {"type": "string"}}},
    },
    {
        "name": "read_project_file",
        "description": "Read one UTF-8 text file from files, notebook, or artifacts in the active project.",
        "parameters": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_project_file",
        "description": "Create or replace one UTF-8 project text file inside files, notebook, or artifacts.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_project_notebook",
        "description": "Read the active project's primary Markdown research notebook.",
        "parameters": {"type": "object", "properties": {"project_id": {"type": "string"}}},
    },
    {
        "name": "update_project_notebook",
        "description": "Replace the active project's primary Markdown research notebook with updated content.",
        "parameters": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "content": {"type": "string"}},
            "required": ["content"],
        },
    },
    {
        "name": "run_workspace_agent",
        "description": "Delegate a substantial file, code, analysis, or notebook task to Codex inside the active project folder.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "prompt": {"type": "string"},
                "reasoning_effort": {"type": "string", "enum": ["minimal", "low", "medium", "high", "xhigh"]},
                "model": {"type": "string"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "get_material_details",
        "description": "Load selected property/evidence/spectra detail sections for a material.",
        "parameters": {
            "type": "object",
            "properties": {
                "material_id": {"type": "string"},
                "sections": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer"},
                "downsample": {"type": "boolean"},
            },
            "required": ["material_id"],
        },
    },
    {
        "name": "get_material_structure",
        "description": "Load crystal structure lattice, sites, bonds, and viewer payload for a material.",
        "parameters": {"type": "object", "properties": {"material_id": {"type": "string"}}, "required": ["material_id"]},
    },
    {
        "name": "get_graph_overview",
        "description": "Load the global materials graph overview and cluster summaries.",
        "parameters": {"type": "object", "properties": {"limit_clusters": {"type": "integer"}}},
    },
    {
        "name": "inspect_graph_node",
        "description": "Inspect a material, element, or cluster graph node by node id.",
        "parameters": {"type": "object", "properties": {"node_id": {"type": "string"}}, "required": ["node_id"]},
    },
    {
        "name": "create_candidate_set",
        "description": "Persist a named candidate set from valid local material ids.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "material_ids": {"type": "array", "items": {"type": "string"}},
                "requirement": {"type": "string"},
            },
            "required": ["material_ids"],
        },
    },
    {
        "name": "list_candidate_sets",
        "description": "List persisted candidate sets, optionally for the current session.",
        "parameters": {"type": "object", "properties": {"session_id": {"type": "string"}}},
    },
    {
        "name": "get_candidate_set",
        "description": "Load one persisted candidate set by id.",
        "parameters": {"type": "object", "properties": {"candidate_set_id": {"type": "string"}}, "required": ["candidate_set_id"]},
    },
    {
        "name": "get_research_run",
        "description": "Load one literature research run and its source hits/errors.",
        "parameters": {"type": "object", "properties": {"run_id": {"type": "string"}}, "required": ["run_id"]},
    },
    {
        "name": "list_project_runs",
        "description": "List recent Codex and analysis runs in the active project.",
        "parameters": {"type": "object", "properties": {"project_id": {"type": "string"}, "limit": {"type": "integer"}}},
    },
    {
        "name": "list_model_services",
        "description": "List configured scientific inference services such as protein folding or property predictors.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "run_model_service",
        "description": "Run one preconfigured scientific model service with structured inputs. The service URL is never agent-controlled.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "project_id": {"type": "string"},
                "inputs": {"type": "object"},
            },
            "required": ["service_id", "inputs"],
        },
    },
    {
        "name": "run_allowlisted_shell",
        "description": (
            "Run a short allowlisted shell command in the project or agent workspace "
            "(python -c, pip show, dir/ls, type/cat of project files). Not unrestricted shell."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Full command line (must match allowlist)."},
                "project_id": {"type": "string", "description": "Optional project id for cwd."},
            },
            "required": ["command"],
        },
    },
    {
        "name": "open_project_material",
        "description": (
            "Open a project material artifact (*.catalyst.json) or material id into the main Catalyst "
            "structure viewer. Switches UI to materials home."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "path": {"type": "string", "description": "Project-relative path to .catalyst.json"},
                "material_id": {"type": "string", "description": "Or open by material id directly"},
            },
        },
    },
    {
        "name": "save_project_material",
        "description": "Save/link a material into the project as files/materials/<id>.catalyst.json.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "material_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["material_id"],
        },
    },
]

# Provider-visible tools intentionally exclude exact-trigger internal workflows.
# The full list remains the canonical executor/API catalog.
MODEL_TOOL_DECLARATIONS: list[dict[str, Any]] = [
    declaration for declaration in TOOL_DECLARATIONS if not declaration.get("internal_only")
]
