"""Cached, deterministic public-demo scenarios.

Only exact normalized trigger strings enter this module. All other prompts stay
on Catalyst's normal agent routing path. The timeline emits the same SSE event
shapes as chat plus incremental ``checkpoint`` events carrying safe UI actions.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any, Iterator


CANONICAL_SUNLIGHT_PROMPT = (
    "Catalyst, investigate how science protects us from harmful sunlight. "
    "Inspect a UV-blocking sunscreen material, show its atomic structure and evidence, "
    "then open BRCA1, highlight the displayed DNA variant, and produce a simple "
    "sun-protection science brief."
)
BACKUP_SUNLIGHT_PROMPT = "/demo sunlight"


def normalize_demo_trigger(value: str) -> str:
    """Normalize only case, outer whitespace, and repeated whitespace."""
    return " ".join(str(value or "").strip().lower().split())


@dataclass(frozen=True)
class DemoStep:
    key: str
    label: str
    at_seconds: float
    status: str
    narration: str
    ui_actions: tuple[dict[str, Any], ...]
    hold_status: str
    narration_delay_seconds: float = 0.0


@dataclass(frozen=True)
class DemoScenario:
    scenario_id: str
    title: str
    duration_seconds: float
    triggers: tuple[str, ...]
    steps: tuple[DemoStep, ...]
    final_brief: str

    @property
    def mission(self) -> list[dict[str, str]]:
        return [{"id": step.key, "label": step.label} for step in self.steps if step.key not in {"variant-focus", "spectra-scan"}]


SUNLIGHT_BRIEF = """## Sunlight Protection Science Brief

- **Material shield:** Zinc oxide (ZnO, local record `mp-deb`) is a mineral UV-blocking sunscreen material. Its atomic structure is assembled here from stored coordinates.
- **Evidence trail:** Catalyst follows the ZnO record through its two-hop graph neighborhood and spectra panel, connecting structure to supporting material evidence.
- **DNA context:** BRCA1 supports DNA-repair biology. The bounded display shows positions **12755–12786**, with position **12770** selected and the displayed variant **c.68_69delAG**—an **AG deletion**.
- **Takeaway:** Protection begins at the surface: UV-blocking materials help reduce exposure, while DNA-repair systems such as BRCA1 help maintain genomic integrity.
"""


SUNLIGHT_SCENARIO = DemoScenario(
    scenario_id="sunlight-dna",
    title="From Sunscreen to DNA",
    duration_seconds=86.0,
    triggers=(CANONICAL_SUNLIGHT_PROMPT, BACKUP_SUNLIGHT_PROMPT),
    steps=(
        DemoStep(
            key="understand",
            label="Understand",
            at_seconds=0,
            status="Mission 1/6 · Understanding harmful sunlight",
            narration=(
                "# From Sunscreen to DNA\n\n"
                "Let’s follow two layers of protection: a material that helps block ultraviolet radiation, "
                "and a DNA-repair gene we can inspect safely in a bounded sequence window.\n\n"
            ),
            ui_actions=(
                {
                    "type": "demo_start",
                    "scenario_id": "sunlight-dna",
                    "title": "From Sunscreen to DNA",
                    "total_ms": 160_000,
                    "mission": [
                        {"id": "understand", "label": "Understand"},
                        {"id": "find-material", "label": "Find material"},
                        {"id": "assemble-atoms", "label": "Assemble atoms"},
                        {"id": "evidence-graph", "label": "Evidence graph"},
                        {"id": "dna-repair", "label": "DNA repair"},
                        {"id": "final-brief", "label": "Final brief"},
                    ],
                },
                {"type": "demo_checkpoint", "step_id": "understand"},
                {"type": "set_inspector", "open": True, "tab": "agent"},
            ),
            hold_status="Catalyst is reading the mission…",
            narration_delay_seconds=4.0,
        ),
        DemoStep(
            key="find-material",
            label="Find material",
            at_seconds=2,
            status="Mission 2/6 · Opening the cached ZnO record",
            narration="",
            ui_actions=(
                {"type": "demo_checkpoint", "step_id": "find-material"},
                {"type": "select_node", "material_id": "mp-deb"},
                {"type": "set_workspace_tab", "tab": "structure"},
            ),
            hold_status="Resolving ZnO structure coordinates…",
        ),
        DemoStep(
            key="assemble-atoms",
            label="Assemble atoms",
            at_seconds=3,
            status="Mission 3/6 · Assembling the stored atomic structure",
            narration=(
                "I’m opening **zinc oxide, ZnO** (`mp-deb`) from Catalyst’s local materials snapshot. "
                "The atoms begin scattered for orientation, then move into the **real stored coordinates**; "
                "bonds and the lattice frame appear as they settle.\n\n"
            ),
            ui_actions=(
                {"type": "demo_checkpoint", "step_id": "assemble-atoms"},
                {"type": "set_workspace_tab", "tab": "structure"},
                {"type": "demo_material_assemble", "duration_ms": 7_500, "nonce": 1},
            ),
            hold_status="Atoms are aligning in real time…",
            narration_delay_seconds=1.8,
        ),
        DemoStep(
            key="evidence-graph",
            label="Evidence graph",
            at_seconds=16,
            status="Mission 4/6 · Following the local evidence graph",
            narration=(
                "Catalyst is now tracing the **two-hop neighborhood** around ZnO. This evidence view connects "
                "the local record to its connected graph context.\n\n"
            ),
            ui_actions=(
                {"type": "demo_checkpoint", "step_id": "evidence-graph"},
                {"type": "set_hop_depth", "depth": 2},
                {"type": "expand_neighborhood", "material_id": "mp-deb", "depth": 2},
                {"type": "set_workspace_tab", "tab": "neighbors"},
            ),
            hold_status="Tracing the two-hop material neighborhood…",
        ),
        DemoStep(
            key="spectra-scan",
            label="Evidence graph",
            at_seconds=27,
            status="Mission 4/6 · Inspecting the stored spectra panel",
            narration=(
                "For a second evidence angle, Catalyst opens the **spectra** panel for the same cached ZnO "
                "record, adding a direct signal-level view to the material story.\n\n"
            ),
            ui_actions=({"type": "set_workspace_tab", "tab": "spectra"},),
            hold_status="Bringing the cached spectra into view…",
        ),
        DemoStep(
            key="dna-repair",
            label="DNA repair",
            at_seconds=35,
            status="Mission 5/6 · Moving to the bounded BRCA1 view",
            narration=(
                "We’re switching scales—from a protective material to **BRCA1**, a gene associated with DNA "
                "repair. The visible DNA window enters as four fragments, spirals into alignment from several "
                "angles, and connects into the existing helix.\n\n"
            ),
            ui_actions=(
                {"type": "demo_checkpoint", "step_id": "dna-repair"},
                {"type": "open_genomics_case", "case_id": "brca1"},
                {"type": "genome_zoom", "action": "zoom", "gene": "BRCA1", "start": 12755, "end": 12786},
                {"type": "demo_dna_assemble", "duration_ms": 9_000, "nonce": 1},
            ),
            hold_status="DNA fragments are spiraling into alignment…",
            narration_delay_seconds=1.2,
        ),
        DemoStep(
            key="variant-focus",
            label="DNA repair",
            at_seconds=48,
            status="Mission 5/6 · Focusing the displayed BRCA1 variant",
            narration=(
                "The camera now focuses the selected display position **12770**. The visible interval is "
                "**12755–12786**, and the displayed HGVS notation is **c.68_69delAG**, an **AG deletion**. "
                "Catalyst keeps the sequence, position, and variant context together in one inspectable view.\n\n"
            ),
            ui_actions=(
                {"type": "demo_dna_focus", "duration_ms": 5_500, "nonce": 2},
                {"type": "genome_highlight", "action": "highlight", "gene": "BRCA1", "position": 12770},
                {"type": "genome_show_sequence", "action": "showSequence", "gene": "BRCA1"},
            ),
            hold_status="Holding the selected variant in view…",
        ),
        DemoStep(
            key="final-brief",
            label="Final brief",
            at_seconds=62,
            status="Mission 6/6 · Writing the science brief",
            narration=SUNLIGHT_BRIEF,
            ui_actions=(
                {"type": "demo_checkpoint", "step_id": "final-brief"},
                {"type": "demo_final_brief", "title": "Sunlight Protection Science Brief"},
            ),
            hold_status="Completing the cached science brief…",
        ),
    ),
    final_brief=SUNLIGHT_BRIEF,
)


DEMO_SCENARIOS: dict[str, DemoScenario] = {SUNLIGHT_SCENARIO.scenario_id: SUNLIGHT_SCENARIO}
_TRIGGERS: dict[str, DemoScenario] = {
    normalize_demo_trigger(trigger): scenario
    for scenario in DEMO_SCENARIOS.values()
    for trigger in scenario.triggers
}


def scenario_for_prompt(message: str) -> DemoScenario | None:
    return _TRIGGERS.get(normalize_demo_trigger(message))


def get_demo_scenario(scenario_id: str) -> DemoScenario | None:
    return DEMO_SCENARIOS.get(str(scenario_id or "").strip().lower())


def scenario_catalog() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": scenario.scenario_id,
            "title": scenario.title,
            "duration_seconds": scenario.duration_seconds,
            "ready": True,
            "mission": scenario.mission,
        }
        for scenario in DEMO_SCENARIOS.values()
    ]


def ordered_action_types(scenario: DemoScenario) -> list[str]:
    return [str(action.get("type") or "") for step in scenario.steps for action in step.ui_actions]


def _chunks(text: str, size: int = 22) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]


def iter_demo_events(
    scenario: DemoScenario,
    *,
    time_scale: float | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield deterministic timed SSE events; ``time_scale=0`` is test-fast."""
    if time_scale is None:
        try:
            time_scale = max(0.0, float(os.getenv("CATALYST_DEMO_TIME_SCALE", "1")))
        except ValueError:
            time_scale = 1.0
    scale = max(0.0, float(time_scale))
    started = time.monotonic()

    def wait_until(target_seconds: float, hold_status: str) -> Iterator[dict[str, Any]]:
        target = started + target_seconds * scale
        while scale > 0:
            remaining = target - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(4.0 * scale, remaining))
            if target - time.monotonic() > 0.05:
                yield {"type": "status", "text": hold_status}

    for step in scenario.steps:
        yield from wait_until(step.at_seconds, step.hold_status)
        yield {"type": "status", "text": step.status}
        yield {
            "type": "checkpoint",
            "checkpoint": step.key,
            "action_id": f"{scenario.scenario_id}:{step.key}",
            "ui_actions": [dict(action) for action in step.ui_actions],
        }
        if step.narration_delay_seconds:
            yield from wait_until(step.at_seconds + step.narration_delay_seconds, "Catalyst is composing the next explanation…")
        for chunk in _chunks(step.narration):
            yield {"type": "token", "text": chunk}
            if scale > 0:
                time.sleep(0.055 * scale)

    yield from wait_until(scenario.duration_seconds, "Finishing the guided investigation…")
    yield {
        "type": "checkpoint",
        "checkpoint": "complete",
        "action_id": f"{scenario.scenario_id}:complete",
        "ui_actions": [{"type": "demo_complete", "scenario_id": scenario.scenario_id}],
    }
