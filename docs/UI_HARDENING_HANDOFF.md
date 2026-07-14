# Catalyst UI Hardening Handoff

## Mission

Standardize Catalyst into a professional scientific workspace UI before expanding feature depth. The immediate goal is not to add more backend capability. The goal is to settle the product surface: a calm, high-density, science-native workspace where search, graph exploration, material inspection, evidence, and agent work feel like one coherent system.

## Current Context

Inspected:

- Reference screenshot: `Claude Science / Cloud for Science` style workspace with a left project rail, central scientific artifact canvas, right code/review panel, and a floating message composer over the artifact.
- Jarvis reference: `E:\Coding\jarvis_v2\docs\Product & Surfaces\UI Design Spec.md`
- Jarvis active frontend shell: `E:\Coding\jarvis_v2\frontend\src\App.jsx`, `InputBar`, `Sidebar`, `VoiceMode`, `Settings`, and global tokens.
- Catalyst current shell: [SubmissionShell.tsx](../code/frontend/src/components/submission/SubmissionShell.tsx), [index.css](../code/frontend/src/index.css), layout stores, bridge hooks, and existing side sheets.
- Live Catalyst backend/UI is hosted from `mini`. Local frontend should keep using the server backend while UI work happens.

Observed Catalyst pain points:

- The current home workspace is doing too much in one row: results panel, material canvas, right material inspector, and bottom composer all compete for vertical and horizontal space.
- The properties section for thermodynamic, electronic, magnetic, mechanical, spectra, evidence, etc. is cramped inside the right inspector.
- The composer currently owns a fixed bottom band. It should behave more like an overlay that floats above the working surface.
- There are multiple panel concepts: submission shell inspector, separate sheets, older layout sidebar, graph mode, agent sheet. The UI needs one canonical shell model.
- The current UI already has useful primitives: graph canvas, structure viewer, agent sheet, candidate compare, research panel, settings, sessions, API bridge, and layout store.

## Design Direction

Catalyst should become a "scientific workspace shell":

- Cloud Science screenshot gives the base spatial model: project rail + artifact canvas + contextual inspector.
- Jarvis gives the product discipline: one coherent shell, durable sidebar, contextual right rail, floating composer, runtime visibility, and no disconnected duplicate surfaces.
- Catalyst adds its own domain language: material workspace, candidate screening, graph neighborhood, evidence, structure, spectra, and research provenance.

The UI should feel:

- calm and research-grade,
- professional enough for demo/review,
- dense but not cramped,
- artifact-first,
- agent-assisted but not chat-only,
- extensible beyond materials into other science domains later.

## Product Principles

- The center is the artifact. Graphs, structures, spectra, tables, maps, and candidate sets should occupy the main canvas.
- The right side explains the artifact. Properties, evidence, code/logs, review notes, and agent reasoning live in a contextual inspector.
- The left side orients the workspace. Navigation, sessions, datasets, candidate sets, research runs, and settings belong there.
- The composer floats. User intent should be available everywhere without permanently consuming layout height.
- Panels should be contextual and collapsible. Nothing should be permanently forced open unless it is core to the current task.
- Generative UI should extend the workspace. It should render forms, tables, approval cards, comparisons, charts, and inspectors inside known zones, not replace the shell.

## Non-Goals For This Pass

- Do not redesign the backend.
- Do not rerun or move the processed data snapshot locally.
- Do not add new science domains yet.
- Do not rebuild the entire app from scratch.
- Do not chase marketing/landing-page polish.
- Do not implement a full generative UI runtime yet. Define slots and contracts first.

## V1 Target

Build a standardized workspace shell that makes the current Catalyst features look intentional and easier to use.

V1 should include:

- a canonical app shell,
- a Cloud Science inspired three-zone layout,
- a Jarvis-like floating composer,
- a less cramped material properties model,
- a cleaner left workspace rail,
- a contextual right inspector with tabs,
- a clear visual token system,
- responsive behavior for desktop and laptop first, with mobile fallback.

## Layout Model

### Desktop

```text
left rail       main workspace canvas                 right inspector
52-280px        flexible, dominant                    360-440px

                floating composer overlay
                bottom center, max 760-840px
```

Left rail:

- collapsed icon rail by default,
- expandable workspace navigator,
- sections for Home, Graph, Candidates, Sessions, Research, Settings,
- optional explorer tree for candidate sets, elements, clusters, research runs, and recent materials.

Main canvas:

- large artifact-first surface,
- current material or graph view as the primary object,
- tabs or mode switch for Graph, Structure, Spectra, Compare, Research,
- no nested card-on-card framing,
- graph and structure should feel like working canvases, not previews.

Right inspector:

- contextual and collapsible,
- shows summary first,
- then dedicated tabs for Overview, Properties, Evidence, Agent, Review,
- properties must be grouped into spacious sections instead of one cramped scroll box.

Floating composer:

- bottom-center overlay,
- does not reserve a full row in the layout,
- mode chips for Search, Ask, Screen, Research,
- supports filters and attachments through popovers,
- can collapse to a command pill when focus is elsewhere.

## Properties Redesign

Current issue:

The material inspector tries to pack key properties, tab controls, detailed property rows, evidence, spectra, and metadata into a narrow column.

New model:

- Right inspector top: compact identity summary.
- Main canvas or inspector tab: property groups get real space.
- Key property strip: 4 to 6 high-value metrics visible at a glance.
- Property groups: Thermo, Electronic, Magnetism, Mechanical, Dielectric, Surfaces, Bonds, Spectra, Evidence.
- Each group should use a consistent record pattern: label, value, unit, confidence/provenance, source count, open detail action.
- Overflow details open in a drill-down section or sheet, not in the same cramped card.

Recommended hierarchy:

```text
Material identity
Key metrics strip
Properties tab group
Evidence/provenance summary
Deep detail drawer or expanded panel
```

## Visual System

Keep Catalyst's science palette, but reduce the "heavy dark dashboard" feel.

Recommended tokens:

- background: neutral workspace gray or very soft scientific blue-gray,
- surface: white or near-black depending theme, with very subtle borders,
- accent: Catalyst green reserved for primary success/selection,
- blue: information and graph relations,
- amber: warning/uncertain/research-needed,
- red: errors only,
- violet: clusters only, avoid making it a dominant theme.

Typography:

- Use one sober interface font and one mono font for IDs/data.
- Do not use oversized headings inside panels.
- Material formula and artifact title can be prominent.
- Dense tables and property grids need smaller type, stronger spacing, and aligned numeric columns.

Shape and spacing:

- Cards radius: 8px or less unless preserving existing component behavior.
- Canvas containers can have subtle rounded corners, but avoid card nesting.
- Icon buttons for panel actions.
- Text buttons only for semantic commands like "Apply filters" or "Download script".

## Component Targets

Primary files likely involved:

- [SubmissionShell.tsx](../code/frontend/src/components/submission/SubmissionShell.tsx)
- [index.css](../code/frontend/src/index.css)
- [layoutStore.ts](../code/frontend/src/catalyst/ui-state/layoutStore.ts)
- [hooks.ts](../code/frontend/src/catalyst/bridge/hooks.ts)
- [viewModels.ts](../code/frontend/src/catalyst/bridge/viewModels.ts)
- [normalizers.ts](../code/frontend/src/catalyst/bridge/normalizers.ts)
- [GraphCanvas.tsx](../code/frontend/src/components/graph/GraphCanvas.tsx)
- [CrystalStructurePanel.tsx](../code/frontend/src/components/structure/CrystalStructurePanel.tsx)
- [AgentSheet.tsx](../code/frontend/src/components/agent/AgentSheet.tsx)
- [SettingsSheet.tsx](../code/frontend/src/components/settings/SettingsSheet.tsx)
- [SessionSheet.tsx](../code/frontend/src/components/sessions/SessionSheet.tsx)

Recommended new or extracted components:

- `WorkspaceShell`
- `WorkspaceRail`
- `WorkspaceCanvas`
- `ContextInspector`
- `FloatingComposer`
- `PropertyOverview`
- `PropertyGroupPanel`
- `EvidenceProvenancePanel`
- `WorkspaceModeTabs`

## Generative UI Slots

Do not build a free-form generative UI engine in V1. Define safe slots:

- Composer suggestions: query chips, screening presets, research prompts.
- Agent messages: candidate result cards, comparison mini tables, citation groups.
- Inspector blocks: generated property summary, evidence synthesis, next action card.
- Canvas overlays: labels, notes, selection popovers, review comments.
- Research mode: source cards, extraction tables, promote candidate action.

Every generated block must have:

- a stable type,
- bounded props,
- fallback text,
- loading and error states,
- provenance if it makes a scientific claim.

## Immediate Implementation Plan

1. Freeze the shell contract.
   - Create or extract `WorkspaceShell` around the existing Catalyst bridge/store.
   - Validation: app loads existing Home and Graph flows with no API contract change.

2. Convert the composer to a floating overlay.
   - Move the current bottom command bar out of normal document flow.
   - Keep Search, Ask, Screen behavior.
   - Add collapsed and expanded states.
   - Validation: canvas and inspector keep full height while composer overlays safely.

3. Rework the material inspector.
   - Split identity, key metrics, property groups, evidence, and details.
   - Make property groups breathe: tabs or accordion sections with consistent metric rows.
   - Validation: Thermo, Electronic, Magnetism, Mechanical, Spectra, Evidence are individually readable at 1440px wide.

4. Standardize left rail behavior.
   - Keep collapsed icon rail.
   - Add expandable explorer with sessions, recent materials, candidates, research.
   - Validation: user can navigate without opening multiple conflicting panels.

5. Standardize visual tokens.
   - Keep existing Catalyst tokens but refine usage.
   - Remove one-off large radii and inconsistent panel backgrounds.
   - Validation: no obvious card nesting, no cramped text, no uncontrolled layout shifts.

6. Responsive pass.
   - Desktop: three-zone layout.
   - Tablet: inspector becomes sheet.
   - Mobile: single-pane canvas with rail and inspector as overlays.
   - Validation: no overlapping text or controls at 390px, 768px, 1440px.

## Acceptance Criteria

- The app has one canonical workspace shell for Home/material work.
- The composer is an overlay and no longer consumes a fixed bottom row.
- The material property section is readable without feeling cramped.
- The right inspector can collapse and does not permanently steal too much canvas width.
- The left rail has a clear purpose and does not duplicate unrelated panels.
- The main canvas remains the visual priority.
- Search, Ask, Screen, material open, graph view, structure view, spectra view, candidate add/remove, and settings still work.
- The UI looks credible beside the Cloud Science screenshot and structurally coherent beside Jarvis.
- The design remains extensible to future science domains such as pollution, environment, chemistry, or energy.

## Verification Plan

Run:

```powershell
npm run build --prefix code/frontend
```

Manual browser checks:

- Open local frontend pointed at the `mini` backend.
- Check desktop at 1440x900 and 1920x1080.
- Check laptop at 1366x768.
- Check tablet width near 768px.
- Check mobile width near 390px.
- Verify the composer never blocks critical graph/inspector controls.
- Verify property sections do not overflow their containers.
- Verify graph canvas, structure viewer, and spectra panel still render.
- Verify agent sheet and settings sheet still open.

Optional screenshot checks:

- Capture current Home/material workspace.
- Capture Graph mode.
- Capture property inspector expanded state.
- Capture composer focused and unfocused states.

## Risks And Decisions

Risk: Rebuilding the whole UI at once will stall.
Decision: First standardize the shell, composer, and inspector. Leave backend features intact.

Risk: Copying Jarvis too literally would make Catalyst feel like a chat app.
Decision: Borrow Jarvis's discipline, not its exact chat-first layout.

Risk: The Cloud Science screenshot is artifact/code oriented, while Catalyst is graph/material oriented.
Decision: Translate its spatial model: artifact canvas + contextual right panel + floating prompt.

Risk: Properties can become endless.
Decision: Use progressive disclosure: key metrics first, grouped tabs next, deep details last.

Risk: Future domains may break a material-only UI.
Decision: Name generic shell zones as workspace, artifact, inspector, evidence, and actions. Keep material-specific components inside those zones.

## Frontend Agent Handoff

Start here:

1. Create a `WorkspaceShell` skeleton that preserves existing Catalyst data hooks and renders current material workspace inside a new three-zone layout.
2. Extract the bottom command bar into `FloatingComposer` and make it overlay the canvas.
3. Extract `AboutInspector` into a `ContextInspector` with `PropertyOverview`, grouped property tabs, and an evidence/provenance tab.
4. Keep all existing API calls and data view models unchanged unless a UI component needs a strictly presentational adapter.
5. Run `npm run build --prefix code/frontend`.

Definition of done:

The current Catalyst workflow still works, but the UI reads as one professional scientific workspace: left navigation, central artifact canvas, right contextual inspector, and floating command composer.
