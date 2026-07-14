from __future__ import annotations

from catalyst.local_store.mixin_core import LocalStoreCoreMixin
from catalyst.local_store.mixin_edges_export import LocalStoreEdgesExportMixin
from catalyst.local_store.mixin_graph_materials import LocalStoreGraphMaterialsMixin
from catalyst.local_store.mixin_graph_nodes import LocalStoreGraphNodesMixin
from catalyst.local_store.mixin_neighborhood import LocalStoreNeighborhoodMixin
from catalyst.local_store.mixin_workspace_core import LocalStoreWorkspaceCoreMixin
from catalyst.local_store.mixin_workspace_details import LocalStoreWorkspaceDetailsMixin


class LocalCatalystStore(
    LocalStoreCoreMixin,
    LocalStoreNeighborhoodMixin,
    LocalStoreGraphMaterialsMixin,
    LocalStoreGraphNodesMixin,
    LocalStoreWorkspaceCoreMixin,
    LocalStoreWorkspaceDetailsMixin,
    LocalStoreEdgesExportMixin,
):
    """Local materials store backed by DuckDB + processed JSONL artifacts."""


from catalyst.local_store.helpers import (  # noqa: E402
    EVIDENCE_FILES,
    TARGET_EVIDENCE_FILES,
    LocalPaths,
)
