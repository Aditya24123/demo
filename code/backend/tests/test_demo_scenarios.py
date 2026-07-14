from __future__ import annotations

from pathlib import Path

from catalyst.agent.registry import gemini_function_declarations, openai_tools_schema, tool_names
from catalyst.demo_scenarios import (
    BACKUP_SUNLIGHT_PROMPT,
    CANONICAL_SUNLIGHT_PROMPT,
    SUNLIGHT_SCENARIO,
    iter_demo_events,
    normalize_demo_trigger,
    ordered_action_types,
    scenario_for_prompt,
)
from catalyst.local_store import LocalCatalystStore


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_trigger_normalization_is_exact_and_intentional() -> None:
    repeated = "  " + CANONICAL_SUNLIGHT_PROMPT.upper().replace(" ", "   ") + "  "
    assert scenario_for_prompt(repeated) is SUNLIGHT_SCENARIO
    assert scenario_for_prompt("  /DEMO    SUNLIGHT  ") is SUNLIGHT_SCENARIO
    assert normalize_demo_trigger(BACKUP_SUNLIGHT_PROMPT) == "/demo sunlight"

    assert scenario_for_prompt("investigate harmful sunlight") is None
    assert scenario_for_prompt(CANONICAL_SUNLIGHT_PROMPT + " please") is None
    assert scenario_for_prompt("/demo sunlight now") is None
    assert scenario_for_prompt("") is None


def test_scenario_duration_and_action_order() -> None:
    assert 80 <= SUNLIGHT_SCENARIO.duration_seconds <= 95
    actions = ordered_action_types(SUNLIGHT_SCENARIO)
    expected = [
        "demo_start",
        "select_node",
        "demo_material_assemble",
        "expand_neighborhood",
        "open_genomics_case",
        "demo_dna_assemble",
        "demo_dna_focus",
        "genome_highlight",
        "genome_show_sequence",
        "demo_final_brief",
    ]
    cursor = -1
    for action in expected:
        cursor = actions.index(action, cursor + 1)


def test_fast_event_stream_interleaves_narration_checkpoints_and_completion() -> None:
    events = list(iter_demo_events(SUNLIGHT_SCENARIO, time_scale=0))
    event_types = [event["type"] for event in events]
    assert "status" in event_types
    assert "token" in event_types
    assert event_types.count("checkpoint") == len(SUNLIGHT_SCENARIO.steps) + 1
    assert events[-1]["checkpoint"] == "complete"
    assert events[-1]["ui_actions"] == [{"type": "demo_complete", "scenario_id": "sunlight-dna"}]

    checkpoints = [event["checkpoint"] for event in events if event["type"] == "checkpoint"]
    assert checkpoints == [step.key for step in SUNLIGHT_SCENARIO.steps] + ["complete"]


def test_demo_is_a_canonical_shared_tool() -> None:
    names = tool_names()
    assert names.count("run_demo_scenario") == 1
    assert "inspect_genomics_case" in names
    assert "control_genome_view" in names
    assert "run_demo_scenario" not in {item["name"] for item in gemini_function_declarations()}
    assert "run_demo_scenario" not in {item["function"]["name"] for item in openai_tools_schema()}


def test_zno_showcase_has_a_cached_spectra_payload() -> None:
    details = LocalCatalystStore(REPO_ROOT).material_details("mp-deb", sections=["spectra"])
    spectra = (details or {}).get("details", {}).get("spectra", {})
    record = (spectra.get("records") or [])[0]
    assert spectra.get("source") == "demo_cache"
    assert record["title"] == "ZnO UV response"
    assert len(record["spectrum"]["energy"]) == len(record["spectrum"]["intensity"])
