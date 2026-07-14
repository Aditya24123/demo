import type { ForceGraphMethods, LinkObject, NodeObject } from 'react-force-graph-2d'
import type { GraphEdgeVM, GraphNodeVM, GraphGroupVM, GraphSettingsVM } from '@/catalyst/bridge/viewModels'

export type RenderNode = GraphNodeVM & {
  x?: number
  y?: number
  val?: number
}

export type RenderLink = Omit<GraphEdgeVM, 'source' | 'target'> & {
  source: string | RenderNode
  target: string | RenderNode
}

export type ForceNode = NodeObject<RenderNode>
export type ForceLink = LinkObject<RenderNode, RenderLink>
export type GraphMethods = ForceGraphMethods<ForceNode, ForceLink>
export type GraphCanvasProps = {
  graphOverride?: {
    nodes: GraphNodeVM[]
    edges: GraphEdgeVM[]
    selectedNodeId?: string | null
  }
}

export function idOf(value: unknown): string {
  if (value && typeof value === 'object' && 'id' in value) return String((value as { id: string }).id)
  return String(value)
}

export function nodeMatches(node: GraphNodeVM, search: string): boolean {
  if (!search.trim()) return true
  const haystack = [
    node.id,
    node.name,
    node.formula_pretty,
    node.chemsys,
    node.representative_material_id,
    node.elements?.join(' '),
  ].filter(Boolean).join(' ').toLowerCase()
  return haystack.includes(search.trim().toLowerCase())
}

export function matchesGroup(node: GraphNodeVM, query: string): boolean {
  if (!query.trim()) return false;
  const q = query.trim().toLowerCase();
  
  if (q.startsWith('type:')) {
    return node.type === q.split(':')[1];
  }
  if (q.startsWith('stable:')) {
    const val = q.split(':')[1] === 'true';
    return node.is_stable === val;
  }
  if (q.startsWith('metal:')) {
    const val = q.split(':')[1] === 'true';
    return node.is_metal === val;
  }
  if (q.startsWith('chemsys:')) {
    return (node.chemsys || '').toLowerCase().includes(q.split(':')[1]);
  }
  if (q.startsWith('element:')) {
    return (node.elements || []).map(e => e.toLowerCase()).includes(q.split(':')[1]);
  }
  if (q.startsWith('namespace:')) {
    return (node.namespace || '').toLowerCase() === q.split(':')[1];
  }
  if (q.startsWith('band_gap:>')) {
    const val = parseFloat(q.split('>')[1]);
    return node.band_gap !== undefined && node.band_gap > val;
  }
  if (q.startsWith('energy_above_hull:<')) {
    const val = parseFloat(q.split('<')[1]);
    return node.energy_above_hull !== undefined && node.energy_above_hull < val;
  }
  return false;
}

export const GRAPH_COLORS = {
  cluster: '#8b78d9',
  material: '#d8a15f',
  element: '#7e9bc8',
  external: '#d6c878',
  stable: '#7fc99b',
  metastable: '#d8b45f',
  unstable: '#d87575',
  metal: '#c8a0e8',
  semiconductor: '#7db6ff',
  unknown: '#b6b6ba',
}

export const GET_IT_GRAPH = {
  bg: '#fbfaf8',
  bgDark: '#121214',
  edge: '#d8d6d2',
  edgeDark: 'rgba(205,205,210,0.22)',
  focus: '#4f5ae0',
  ink: '#1a1a1d',
  inkMuted: '#6f7078',
  white: '#ffffff',
}

export function clamp(val: number, min: number, max: number) {
  return Math.min(Math.max(val, min), max);
}

export function getNodeRadius(node: GraphNodeVM, degreeMap: Map<string, number>, settings: GraphSettingsVM) {
  const degree = degreeMap.get(node.id) || 0
  let base = 3
  if (node.type === 'cluster') {
    base = 3.8 + Math.log10((node.material_count || degree || 1) + 1) * 1.8
  } else if (node.type === 'material') {
    base = 4.2 + Math.sqrt(degree) * 0.62
  } else if (node.type === 'element') {
    base = 3.0 + Math.sqrt(degree) * 0.35
  }
  return clamp(base * settings.nodeSize, 3.2, 14)
}

export function getNodeRepelStrength(node: GraphNodeVM, degreeMap: Map<string, number>, settings: GraphSettingsVM) {
  const degree = degreeMap.get(node.id) || 0
  const base = settings.repelForce
  const localBoost = 1 + Math.min(Math.sqrt(degree) / 6, settings.localRepelBoost)
  const clusterBoost = node.type === 'cluster' ? settings.clusterSpread : 1
  return base * localBoost * clusterBoost
}

export function getLinkDistance(link: RenderLink, settings: GraphSettingsVM) {
  if (link.type === 'CONTAINS_ELEMENT') return settings.linkDistance * 0.82
  if (link.type === 'SHARED_DOMINANT_ELEMENT') return settings.linkDistance * 1.35
  if (link.type === 'BELONGS_TO_CLUSTER') return settings.linkDistance * 1.55
  return settings.linkDistance
}

export function getLinkStrength(link: RenderLink, settings: GraphSettingsVM) {
  if (link.type === 'BELONGS_TO_CLUSTER') return Math.min(settings.linkForce * 0.18, 0.08)
  if (link.type === 'CONTAINS_ELEMENT') return Math.min(settings.linkForce * 0.55, 0.25)
  return settings.linkForce
}

export function nodeColor(node: GraphNodeVM, groups: GraphGroupVM[], colorMode: string): string {
  for (const group of groups) {
    if (matchesGroup(node, group.query)) return group.color;
  }
  if (node.namespace === 'external_research') return GRAPH_COLORS.external;
  if (colorMode === 'stability') {
    if (node.is_stable === true) return GRAPH_COLORS.stable;
    if (node.is_stable === false) {
       if (node.energy_above_hull && node.energy_above_hull > 0.1) return GRAPH_COLORS.unstable;
       return GRAPH_COLORS.metastable;
    }
  } else if (colorMode === 'band_gap') {
    if (node.is_metal) return GRAPH_COLORS.metal;
    if (node.band_gap !== undefined && node.band_gap > 0) return GRAPH_COLORS.semiconductor;
  } else if (colorMode === 'element') {
    if (node.type === 'element') return GRAPH_COLORS.element;
    return GRAPH_COLORS.unknown;
  } else if (colorMode === 'namespace') {
    return GRAPH_COLORS.cluster;
  }
  if (node.type === 'cluster') return GRAPH_COLORS.cluster;
  if (node.type === 'material') return GRAPH_COLORS.material;
  if (node.type === 'element') return GRAPH_COLORS.element;
  return GRAPH_COLORS.unknown;
}

export function wrapLabel(label: string, maxChars = 18, maxLines = 2): string[] {
  const clean = label.replace(/\s+/g, ' ').trim()
  if (!clean) return ['']
  const words = clean.split(' ')
  const lines: string[] = []
  let current = ''
  for (const word of words) {
    const next = current ? `${current} ${word}` : word
    if (next.length <= maxChars) {
      current = next
      continue
    }
    if (current) lines.push(current)
    current = word
    if (lines.length === maxLines - 1) break
  }
  if (current && lines.length < maxLines) lines.push(current)
  const joinedLength = lines.join(' ').length
  if (joinedLength < clean.length && lines.length > 0) {
    lines[lines.length - 1] = `${lines[lines.length - 1].replace(/[. ]+$/, '')}...`
  }
  return lines
}

export function nodeTier(node: GraphNodeVM, degreeMap: Map<string, number>): 0 | 1 | 2 {
  const degree = degreeMap.get(node.id) || 0
  if (node.type === 'cluster' || degree >= 10) return 0
  if (node.type === 'material' || degree >= 4) return 1
  return 2
}

