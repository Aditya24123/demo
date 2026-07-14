/**
 * Phase 5 ? shared agent context for materials + project surfaces.
 * Built from live layout/workspace/project state and sent as current_workspace.
 */

export type AgentSurface = 'materials' | 'project' | 'genes';

export type AgentWorkspaceContext = {
  agent_surface: AgentSurface;
  rail_mode: string;
  project_id?: string;
  project_name?: string;
  material_id?: string;
  formula_pretty?: string;
  chemsys?: string;
  workspace_tab?: string | null;
  hop_depth?: number;
  visible_material_ids?: string[];
  selected_edge_id?: string | null;
  /** Composer effort (minimal|low|medium|high) ? agent instruction steering. */
  agent_effort?: string;
  /** Selected model profile id (internal routing key). */
  agent_model_profile?: string;
  genomics_case_id?: 'brca1' | 'hbb' | 'ctg';
  genomics_variant_index?: number;
  genomics_repeat_count?: number;
  /** Only the currently displayed sequence window; never the full gene record. */
  genome_visible_start?: number;
  genome_visible_end?: number;
  genome_selected_position?: number;
  genome_sequence?: string;
  genome_total_length?: number;
  genome_selected_variant?: { hgvs?: string; reference?: string; alternate?: string; id?: string } | null;
};

export function agentSurfaceFromRail(railMode: string | null | undefined): AgentSurface {
  if (railMode === 'genes') return 'genes';
  return railMode === 'notebook' ? 'project' : 'materials';
}

export function buildAgentWorkspaceContext(input: {
  railMode: string;
  hopDepth?: number;
  workspaceTab?: string | null;
  activeProjectId?: string | null;
  projectName?: string | null;
  materialId?: string | null;
  formulaPretty?: string | null;
  chemsys?: string | null;
  visibleMaterialIds?: string[];
  selectedEdgeId?: string | null;
  agentEffort?: string | null;
  agentModelProfile?: string | null;
  genomicsCaseId?: 'brca1' | 'hbb' | 'ctg';
  genomicsVariantIndex?: number;
  genomicsRepeatCount?: number;
  genomeState?: {
    gene: string; visibleStart: number; visibleEnd: number; selectedPosition: number;
    sequence: string; geneLength: number;
    selectedVariant?: { hgvs?: string; reference?: string; alternate?: string; id?: string } | null;
  };
}): AgentWorkspaceContext {
  const surface = agentSurfaceFromRail(input.railMode);
  const ctx: AgentWorkspaceContext = {
    agent_surface: surface,
    rail_mode: input.railMode || 'home',
  };
  if (input.activeProjectId) {
    ctx.project_id = input.activeProjectId;
    if (input.projectName) ctx.project_name = input.projectName;
  }
  if (input.materialId) {
    ctx.material_id = input.materialId;
    if (input.formulaPretty) ctx.formula_pretty = input.formulaPretty;
    if (input.chemsys) ctx.chemsys = input.chemsys;
  }
  if (input.workspaceTab) ctx.workspace_tab = input.workspaceTab;
  if (typeof input.hopDepth === 'number') ctx.hop_depth = input.hopDepth;
  if (input.visibleMaterialIds?.length) ctx.visible_material_ids = input.visibleMaterialIds;
  if (input.selectedEdgeId) ctx.selected_edge_id = input.selectedEdgeId;
  if (input.agentEffort) ctx.agent_effort = input.agentEffort;
  if (input.agentModelProfile) ctx.agent_model_profile = input.agentModelProfile;
  if (input.genomicsCaseId) ctx.genomics_case_id = input.genomicsCaseId;
  if (typeof input.genomicsVariantIndex === 'number') ctx.genomics_variant_index = input.genomicsVariantIndex;
  if (typeof input.genomicsRepeatCount === 'number') ctx.genomics_repeat_count = input.genomicsRepeatCount;
  if (input.genomeState) {
    ctx.genome_visible_start = input.genomeState.visibleStart;
    ctx.genome_visible_end = input.genomeState.visibleEnd;
    ctx.genome_selected_position = input.genomeState.selectedPosition;
    ctx.genome_sequence = input.genomeState.sequence;
    ctx.genome_total_length = input.genomeState.geneLength;
    ctx.genome_selected_variant = input.genomeState.selectedVariant || null;
  }
  return ctx;
}
