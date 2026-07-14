# Catalyst Research Workspace Spec

## Mission

Catalyst will become an AI-native research workspace where a researcher can create a project, work with scientific data and files, converse with an agent that can operate inside that project, run domain tools and models, and preserve the resulting notes, artifacts, provenance, and decisions in a durable notebook.

The first goal is a coherent product shell and interaction system. New scientific domains and model integrations must fit into that system without creating separate dashboards.

## Current Context

### Inspected

- Catalyst React entry path: `App -> SubmissionShell re-export -> WorkspaceShell`.
- Current workspace components under `code/frontend/src/components/workspace/`.
- Catalyst sessions, local agent loop, tool registry, research endpoints, settings, voice websocket, and mini runtime configuration.
- Jarvis sidebar, input bar, user menu, settings modal, model selector, message rendering, thinking UI, voice store, and voice timer.
- Get It project model, provider router, per-document workspace, append-only journal, renderer system, and local filesystem persistence.
- T3 Code architecture: React client, typed WebSocket boundary, Node orchestration server, and `codex app-server` over JSON-RPC/stdio.
- OpenChamber architecture and its project/session/file/tool UI patterns.
- OpenAI Codex TypeScript SDK and `codex app-server` documentation.

### Verified

- The Catalyst frontend builds successfully.
- The local frontend points to the backend on `mini`.
- Catalyst currently has persistent sessions and domain-specific tools, but no real project entity or project filesystem contract.
- Current sidebar projects, recents, alerts, and jobs are static prototype data.
- The current agent is a custom Gemini-first planning/tool/final-answer loop, not a general workspace agent.
- The Codex TypeScript SDK can start and resume threads, stream structured events, attach images, set a working directory, and accept configuration overrides.
- Codex custom provider configuration supports a base URL and provider metadata. Compatibility still depends on the upstream implementing the API behavior Codex expects.

### Open

- Final Catalyst brand SVG. Until supplied, use the Catalyst wordmark without a third-party logo.
- Exact first production model catalog and provider capabilities.
- Whether projects will eventually be collaborative. V1 is single-user.
- Which protein, sequence, and chemistry services enter the first domain expansion.

## Product Definition

Catalyst is not a chat app with scientific cards and not a collection of domain dashboards.

It has five durable concepts:

1. **Project**: a named research workspace backed by a server-side folder.
2. **Session**: an agent conversation within one project.
3. **Artifact**: a file or structured scientific result created, imported, or generated in a project.
4. **Notebook entry**: a chronological record connecting notes, prompts, runs, artifacts, citations, and decisions.
5. **Capability pack**: tools and renderers for a scientific domain, such as materials, molecules, proteins, sequences, or environment.

The shell remains stable as capability packs change.

## Product Principles

- The center is a working artifact, not a dashboard summary.
- The agent acts inside a bounded project workspace and can manipulate files and artifacts.
- Every scientific claim can carry provenance.
- Chat, voice, tools, files, and notebook entries share one session and project context.
- Provider and model differences are represented as capabilities, not scattered conditionals.
- Prototype-only controls are hidden until they have real behavior.
- The mini server owns data, workspaces, agent processes, and model credentials. The local machine runs only the frontend during development.

## Shell Contract

### Left Sidebar

Port the Jarvis behavior and measurements, while replacing Jarvis content with Catalyst entities.

Expanded width: `260px`.
Collapsed width: `52px`.

Top:

- Catalyst SVG/wordmark.
- Collapse/expand control.
- New session.
- Search projects, sessions, files, and materials.

Projects:

- Section header with an add button.
- Render only projects returned by the backend.
- Empty state when there are no projects.
- No hard-coded Solid Oxides, Battery Materials, 2D Materials, Thermoelectrics, or High Entropy entries.
- Active project expands to show recent sessions and pinned artifacts.

Navigation:

- Workspace.
- Notebook, once its real project-scoped view exists.
- Candidates when the active capability pack supports them.
- Files when the project filesystem API exists.
- Apps is hidden in V1. It returns later as the capability-pack manager.

Bottom:

- User/profile button only.
- Profile popover contains Settings and relevant account actions.
- Remove prototype Alerts, Jobs, and standalone Settings rows.

Brand rule:

- Remove the OpenAI logo immediately.
- Do not replace it with another guessed logo.
- Use the supplied Catalyst SVG when available.

### Main Workspace

- Boots directly into the current scientific workspace and graph, without a marketing or chat home screen.
- If no project exists, the graph can run in an unlisted scratch workspace.
- A scratch workspace can be promoted to a named project.
- Canvas remains the dominant region.
- Graph, structure, spectra, comparison, document, notebook, table, code, and generated visualization are artifact views within the same canvas contract.
- The canvas exposes a stable location for agent-created artifacts and workspace patches.

### Right Panel

Primary tabs:

- Agent.
- Properties or Inspector, based on the active artifact.

The panel is docked on wide screens and overlays the canvas when permanent docking would make the canvas unusable. It must be resizable after the shell foundation is stable.

The Agent tab contains:

- Project/session identity.
- New session control.
- Conversation timeline.
- Thinking/reasoning status.
- Tool activity and artifact creation events.
- Markdown, code, tables, math, citations, and file links.
- Composer with attachment, model/effort control, dictation, and live voice.

### Typography

Adopt the Jarvis stack everywhere:

```css
font-family: -apple-system-body, ui-sans-serif, -apple-system,
  system-ui, "Segoe UI", Helvetica, "Apple Color Emoji", Arial,
  sans-serif, "Segoe UI Emoji", "Segoe UI Symbol";
```

- Remove the global Inter override.
- Inputs, buttons, menus, markdown, and panels inherit the same stack.
- Keep monospace only for IDs, code, file paths, and numeric scientific data where alignment matters.

## Agent Experience Contract

### Conversation Events

The frontend consumes normalized events rather than provider-specific response objects:

```text
session.started
turn.started
reasoning.started
reasoning.delta
reasoning.completed
message.delta
message.completed
tool.started
tool.progress
tool.completed
artifact.created
workspace.changed
turn.completed
turn.failed
```

This event contract powers shimmer, elapsed thinking time, streaming markdown, tool status, and final messages.

### Thinking UI

Port the Jarvis interaction:

- `Thinking` shimmer appears as soon as a turn starts.
- Elapsed time increments while the turn is active.
- Completed state reads `Thought for ...`.
- Reasoning can expand when the runtime exposes a safe summary.
- Raw hidden reasoning is never fabricated from normal answer text.
- Tool activity is displayed separately from reasoning.

### Model Configuration

The composer receives a compact capability-aware selector.

Model record:

```ts
type ModelCapability = {
  providerId: string;
  modelId: string;
  label: string;
  supportsTools: boolean;
  supportsReasoning: boolean;
  reasoningEfforts: Array<'minimal' | 'low' | 'medium' | 'high' | 'xhigh'>;
  supportsImages: boolean;
  supportsAudio: boolean;
  supportsStreaming: boolean;
  contextWindow?: number;
};
```

UI rules:

- Show effort only when the model advertises reasoning support.
- Show image attachment only when the selected model supports images, or explain that Catalyst will route the image through another capable model.
- Store project default and per-session override separately.
- Provider credentials remain on `mini`; the browser receives capability/status metadata only.
- Add a provider compatibility probe before accepting a custom OpenAI-compatible endpoint.

## Voice Contract

Gemini Live remains a specialized realtime voice transport. It does not replace the main project agent.

Required fixes:

- Show a compact `MM:SS` timer while connecting/connected.
- Preserve the timer during mute and reset only when the call ends.
- Merge transcript deltas into the current utterance instead of appending every chunk as a new line.
- Use a stable utterance or segment identifier when the backend provides one.
- Fall back to role plus short time-window coalescing until segment IDs exist.
- Commit completed user utterances into the current agent session.
- Feed final agent/voice responses into the same conversation timeline.
- Surface connecting, listening, thinking, speaking, muted, ended, and failed states.

## Project Workspace Filesystem

Projects live on `mini`, not on the frontend machine.

Proposed layout:

```text
data/workspaces/<project_id>/
  project.json
  README.md
  files/
  artifacts/
  notebook/
    entries.jsonl
  runs/
  exports/
  .catalyst/
    sessions/
    artifact-index.json
    provenance.jsonl
    runtime.json
```

Each project directory is initialized as a Git repository for recoverable agent edits and audit history. Git is an internal implementation detail in V1, not a primary user workflow.

Rules:

- Codex working directory is the selected project root.
- The agent may write only inside that project and designated temporary directories.
- The global scientific dataset is mounted or accessed read-only through tools.
- Imported files are copied into `files/` and indexed.
- Generated outputs are written to `artifacts/` or `exports/`.
- Notebook entries reference artifacts by stable IDs and paths.
- Every model/tool run receives a run ID and records inputs, provider/model, timestamps, outputs, and provenance.

## Notebook Definition

The notebook is not a text editor bolted onto the sidebar. It is the chronological research record of a project.

Entry types:

- Manual note.
- Agent answer.
- Research question.
- Tool/model run.
- Dataset or file import.
- Artifact snapshot.
- Candidate decision.
- Experiment plan.
- Citation/provenance group.

Notebook behavior:

- Entries can be pinned, titled, tagged, and linked to artifacts.
- Agent results are promoted into the notebook explicitly or by project policy.
- Markdown is the human-readable representation.
- Structured metadata remains available for filtering, provenance, and future collaboration.
- Opening an entry restores its associated artifact and session context.

## Domain Expansion

Do not add a new shell for every science domain. Add capability packs.

```ts
type CapabilityPack = {
  id: string;
  label: string;
  tools: ToolDefinition[];
  artifactTypes: ArtifactTypeDefinition[];
  renderers: RendererDefinition[];
  inspectorSections: InspectorSectionDefinition[];
  modelEndpoints?: ModelEndpointDefinition[];
};
```

Initial packs:

- Materials: graph, structures, properties, spectra, screening, comparison.
- Molecules: molecular structures, descriptors, reactions, docking outputs.
- Proteins: sequences, structures, folding runs, confidence plots.
- Genomics: sequences, annotations, variants, alignments.
- Environment: locations, time series, pollutant maps, model forecasts.

The generic shell understands projects, files, artifacts, sessions, runs, and notebook entries. Packs supply domain behavior.

## Runtime Architecture

```text
React frontend
  | HTTP + typed WebSocket events
  v
FastAPI Catalyst control plane on mini
  | project/session/file APIs
  | domain data and scientific tools
  | normalized event gateway
  v
Node agent runtime on mini
  | @openai/codex-sdk or codex app-server over stdio
  | one bounded cwd per project
  | provider/model configuration
  v
Codex CLI + project filesystem + Catalyst MCP/tools
```

Decisions:

- Do not run Codex in the browser.
- Do not expose the Codex process directly to the public network.
- Keep FastAPI as the Catalyst product/data control plane.
- Add a small Node agent-runtime service because the official SDK is TypeScript and already handles threads and streaming events.
- Normalize Codex events before they reach React.
- Keep Gemini Live as a separate realtime voice service, bridged into the same project/session model.
- Expose Catalyst domain actions to Codex as MCP tools or a narrow local tool bridge.

## Proposed V1

V1 proves one complete project loop:

1. Create a real project.
2. Open the existing materials graph inside it.
3. Start a Codex-backed agent session scoped to its server-side folder.
4. Ask the agent to inspect current material data and create a Markdown comparison artifact.
5. Stream thinking/tool/message states into the Jarvis-style right panel.
6. Open the artifact in the central canvas.
7. Promote the result into the notebook.
8. Resume the same project and session after reload.

This is enough to prove the workspace architecture before proteins, genomics, or more model services are added.

## Task Tree

### Workstream 0: Frontend Consolidation

- [ ] Replace the OpenAI mark with the Catalyst wordmark placeholder and add a slot for the supplied SVG.
  - Validation: no OpenAI logo or OpenAI brand asset renders in the shell.
- [ ] Replace Inter with the exact Jarvis system font stack globally.
  - Validation: computed font family matches on sidebar, canvas, agent, menus, and inputs.
- [ ] Remove static projects, recents, Alerts, Jobs, and standalone Settings navigation.
  - Validation: sidebar renders no entity that was not returned by an API or local state contract.
- [ ] Port Jarvis profile popover behavior and route Settings through it.
  - Validation: profile opens one anchored menu; Settings opens from that menu in expanded and collapsed sidebar states.
- [ ] Add a Projects section header with an add button and honest empty state.
  - Validation: zero projects produces an empty state, not sample data.
- [ ] Hide Apps and Notebook until their functional routes exist.
  - Validation: no dead primary navigation items remain.

### Workstream 1: Agent UI Quality

- [ ] Port Jarvis streaming Markdown and message spacing into the right panel.
- [ ] Add normalized thinking state, shimmer, and elapsed/completed duration.
- [ ] Add tool activity rows and artifact-created actions.
- [ ] Add model capability and reasoning-effort placeholders backed by typed local state.
- [ ] Add voice call timer and transcript coalescing.
  - Validation: one spoken sentence does not render as many short message rows.

### Workstream 2: Projects And Filesystem

- [ ] Add project contracts and a `ProjectStore` rooted at `data/workspaces/`.
- [ ] Add create/list/get/update/archive project endpoints.
- [ ] Create the project directory layout atomically.
- [ ] Initialize project Git history and baseline metadata.
- [ ] Add project file listing, upload, read, write, rename, and safe delete APIs.
- [ ] Bind Catalyst sessions to `project_id`.
  - Validation: a project and its files survive backend restart and cannot escape their workspace root.

### Workstream 3: Codex Runtime Spike

- [ ] Create `code/agent-runtime/` as a Node service using `@openai/codex-sdk`.
- [ ] Start/resume one Codex thread with the project folder as `workingDirectory`.
- [ ] Stream SDK events into a normalized Catalyst event schema.
- [ ] Add cancellation, timeout, reconnect, and process cleanup.
- [ ] Configure a custom provider compatibility probe.
- [ ] Connect one read-only Catalyst materials tool through MCP or the local tool bridge.
  - Validation: the agent reads current material context and writes one artifact inside the project.

### Workstream 4: Notebook And Artifacts

- [ ] Define artifact metadata and renderer registry contracts.
- [ ] Index Markdown, JSON, CSV, image, plot, structure, and graph artifacts.
- [ ] Add append-only notebook entries with stable artifact/session/run references.
- [ ] Add notebook list/filter/open/promote APIs.
- [ ] Render a project notebook view in the main canvas.
  - Validation: promoting an agent artifact creates a durable entry that restores the artifact and source session.

### Workstream 5: Capability Packs

- [ ] Extract current materials features behind a Materials capability pack contract.
- [ ] Prove one second pack with a narrow protein sequence/structure artifact, without redesigning the shell.
  - Validation: both packs share project, session, files, notebook, and agent surfaces.

## Acceptance Criteria

- [ ] No OpenAI logo, fake project, fake recent, Alerts row, Jobs row, or standalone Settings row remains.
- [ ] Catalyst uses the Jarvis typography stack and sidebar interaction model.
- [ ] Projects shown in the sidebar are real backend entities.
- [ ] The main canvas boots directly into the current workspace.
- [ ] Agent messages stream cleanly with Markdown, thinking state, tool progress, and completion timing.
- [ ] Voice mode shows elapsed time and coalesces transcript chunks correctly.
- [ ] Model and effort controls are capability-aware.
- [ ] Every project has a bounded server-side filesystem on `mini`.
- [ ] A Codex thread runs with that project as its working directory.
- [ ] The agent can create an artifact and the UI can open it.
- [ ] The artifact can become a durable notebook entry.
- [ ] Current materials data remains on `mini`; no processed dataset is moved to the frontend machine.

## Verification Plan

- Frontend build: `rtk npm run build --prefix code/frontend`.
- Backend tests: `rtk test pytest -q code/backend/tests`.
- Agent runtime unit tests for event normalization, path boundaries, cancellation, and provider capability mapping.
- API smoke tests for project lifecycle, project files, session binding, artifact creation, and notebook promotion.
- Manual UI checks after each bulk tranche, not after every small edit.
- Responsive checks at laptop and desktop widths after the shell tranche.
- Voice websocket smoke plus one real microphone/browser check after voice changes are complete.
- Run `graphify update .` after substantive code changes.

## Risks And Decisions

- Risk: treating any OpenAI-compatible endpoint as Codex-compatible.
  - Decision: require a compatibility probe for streaming, tool calls, reasoning configuration, and the expected API endpoint before enabling a model.
- Risk: mixing provider-native events throughout React.
  - Decision: normalize all runtime events at the server boundary.
- Risk: allowing the agent to touch global data or host files.
  - Decision: one bounded project working directory plus explicit read-only domain tools.
- Risk: building a generic plugin system before the core loop works.
  - Decision: extract Materials only after the project-agent-artifact-notebook loop is proven.
- Risk: copying open-source UI without checking licensing or architecture fit.
  - Decision: reuse patterns and MIT/Apache-compatible code selectively, preserve notices when required, and keep Catalyst's product model authoritative.
- Risk: another broad UI rewrite creates more duplicate paths.
  - Decision: keep `WorkspaceShell` canonical and delete or quarantine replaced prototype surfaces as each tranche lands.

## First `$ship` Handoff

Start with the Frontend Consolidation tranche only:

1. Port the exact Jarvis global font stack and profile menu behavior.
2. Remove the OpenAI logo and every hard-coded/prototype sidebar entity.
3. Add real project-empty and add-project UI contracts without inventing backend data.
4. Port thinking/timer/transcript behavior into the existing agent panel without changing the agent backend yet.
5. Build and inspect the UI once at the end of the tranche.

Definition of done: the existing Catalyst graph and mini-backed data still work, while the visible shell contains only honest product surfaces and the agent/voice interactions match Jarvis quality.

## Primary References

- Codex SDK: https://github.com/openai/codex/blob/main/sdk/typescript/README.md
- Codex app-server: https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md
- T3 Code architecture: https://github.com/pingdotgg/t3code/blob/main/docs/architecture/overview.md
- OpenChamber: https://github.com/openchamber/openchamber
- Get It technical writeup: https://github.com/beltromatti/get-it/blob/main/technical-writeup.md
