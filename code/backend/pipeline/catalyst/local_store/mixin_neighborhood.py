from __future__ import annotations

from collections import deque
from typing import Any

class LocalStoreNeighborhoodMixin:
    def neighborhood(self, material_id: str, *, depth: int = 1, limit_nodes: int = 80) -> dict[str, Any]:
        """Multi-hop neighborhood around a material.

        Hop semantics (visible growth required ? relation cliques alone often stall at depth 1):
        - hop 1: direct material?material relations + seed elements
        - hop 2+: expand materials further *and* walk through elements as bridges
          (other materials that share Fe/Se/? with the frontier)
        """
        material = self.get_material(material_id)
        if not material:
            return {"nodes": [], "edges": [], "meta": {"depth": depth, "limit_nodes": limit_nodes}}

        depth = max(1, min(int(depth), 5))
        limit_nodes = max(10, min(int(limit_nodes), 800))

        mid = str(material["material_id"])
        nodes_by_id: dict[str, dict[str, Any]] = {mid: self._material_node_payload(mid, material)}
        edges_by_id: dict[str, dict[str, Any]] = {}

        # BFS over materials + elements so hop depth changes node count for real.
        # kind: "material" | "element"
        queue: deque[tuple[str, int, str]] = deque([(mid, 0, "material")])
        visited_material_ids = {mid}
        visited_elements: set[str] = set()

        # Scale fan-out aggressively with depth so hops 2?5 don't look identical.
        relation_limit = 10 if depth <= 1 else min(48, 8 + depth * 10)
        element_material_limit = 6 if depth <= 1 else min(64, 6 + depth * 12)

        def room() -> bool:
            return len(nodes_by_id) < limit_nodes

        def add_material_node(other_id: str, other: dict[str, Any] | None = None) -> bool:
            if other_id in nodes_by_id:
                return True
            if not room():
                return False
            nodes_by_id[other_id] = self._material_node_payload(other_id, other)
            return True

        def add_element_node(symbol: str) -> bool:
            if symbol in nodes_by_id:
                return True
            if not room():
                return False
            nodes_by_id[symbol] = self._element_node_payload(symbol)
            return True

        def add_element_edge(mat_id: str, edge: dict[str, Any]) -> None:
            symbol = str(edge.get("element_symbol") or edge.get("symbol") or "")
            if not symbol or symbol not in nodes_by_id or mat_id not in nodes_by_id:
                return
            edge_id = f"element:{mat_id}:{symbol}"
            edges_by_id[edge_id] = {
                "id": edge_id,
                "source": mat_id,
                "target": symbol,
                "type": edge.get("edge_type", "CONTAINS_ELEMENT"),
                "weight": edge.get("atomic_fraction"),
                "stoich_amount": edge.get("stoich_amount"),
                "atomic_fraction": edge.get("atomic_fraction"),
            }

        def add_relation_edge(relation: dict[str, Any]) -> None:
            edge_id = str(
                relation.get("edge_id")
                or f"{relation['source_id']}:{relation['target_id']}:{relation['edge_type']}"
            )
            edges_by_id[edge_id] = {
                "id": edge_id,
                "source": relation["source_id"],
                "target": relation["target_id"],
                "type": relation["edge_type"],
                "weight": relation.get("weight"),
                "confidence": relation.get("confidence"),
                "recipe_name": relation.get("recipe_name"),
                "reason_summary": relation.get("reason_summary"),
            }

        while queue and room():
            current, hop, kind = queue.popleft()
            if hop >= depth:
                continue
            next_hop = hop + 1

            if kind == "material":
                # Direct material?material relations.
                relation_rows = self._material_relation_rows(current, limit=relation_limit)
                for relation in relation_rows:
                    if not room():
                        break
                    other_id = (
                        str(relation["target_id"])
                        if str(relation["source_id"]) == current
                        else str(relation["source_id"])
                    )
                    if not other_id:
                        continue
                    other = self.get_material(other_id) or {"material_id": other_id}
                    if not add_material_node(other_id, other):
                        continue
                    add_relation_edge(relation)
                    if other_id not in visited_material_ids and next_hop < depth:
                        visited_material_ids.add(other_id)
                        queue.append((other_id, next_hop, "material"))

                # Elements of this material (always at hop ? 1 from a material).
                seed_mat = material if current == mid else self.get_material(current)
                for edge in self._element_edges_for_material(current, seed_mat):
                    if not room():
                        break
                    symbol = str(edge.get("element_symbol") or "")
                    if not symbol:
                        continue
                    if not add_element_node(symbol):
                        continue
                    add_element_edge(current, edge)
                    # Only walk through elements when depth allows another hop beyond them.
                    if symbol not in visited_elements and next_hop < depth:
                        visited_elements.add(symbol)
                        queue.append((symbol, next_hop, "element"))

            elif kind == "element":
                # Bridge: other materials that contain this element (makes hop 2+ grow).
                peers = self._materials_for_element(
                    current,
                    limit=element_material_limit,
                    exclude_ids=visited_material_ids,
                )
                for peer in peers:
                    if not room():
                        break
                    other_id = str(peer.get("material_id") or "")
                    if not other_id:
                        continue
                    if not add_material_node(other_id, peer):
                        continue
                    add_element_edge(
                        other_id,
                        {
                            "element_symbol": current,
                            "edge_type": peer.get("edge_type", "CONTAINS_ELEMENT"),
                            "atomic_fraction": peer.get("atomic_fraction"),
                            "stoich_amount": peer.get("stoich_amount"),
                        },
                    )
                    if other_id not in visited_material_ids and next_hop < depth:
                        visited_material_ids.add(other_id)
                        queue.append((other_id, next_hop, "material"))

        return {
            "nodes": list(nodes_by_id.values()),
            "edges": list(edges_by_id.values()),
            "meta": {
                "depth": depth,
                "limit_nodes": limit_nodes,
                "resolved_material_id": mid,
                "node_count": len(nodes_by_id),
                "edge_count": len(edges_by_id),
                "material_count": sum(1 for n in nodes_by_id.values() if n.get("type") == "material"),
                "element_count": sum(1 for n in nodes_by_id.values() if n.get("type") == "element"),
            },
        }

