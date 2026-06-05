"""Load TxGNN Parquet knowledge graphs into graph backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from manage_db.kg_schema import RELATION_BY_NAME
from manage_db.kg_storage import KGRoot, open_kg_root, read_edges, read_nodes


@dataclass(frozen=True)
class KGValidationReport:
    """Lightweight structural validation summary for a Parquet KG."""

    node_counts: dict[str, int]
    edge_counts: dict[str, int]
    dangling_edges: dict[str, int]

    @property
    def total_nodes(self) -> int:
        return sum(self.node_counts.values())

    @property
    def total_edges(self) -> int:
        return sum(self.edge_counts.values())

    @property
    def total_dangling_edges(self) -> int:
        return sum(self.dangling_edges.values())

    @property
    def ok(self) -> bool:
        return self.total_dangling_edges == 0


class KGLoader:
    """Read a stored TxGNN KG and export it to graph libraries.

    Args:
        data_dir: Either a KG root itself, or a data directory containing a
            ``kg`` child directory. Local paths and ``gs://`` URIs are supported.
    """

    def __init__(self, data_dir: str | Path):
        uri = str(data_dir)
        if "://" not in uri:
            path = Path(uri)
            if (path / "nodes").exists() or (path / "edges").exists():
                uri = str(path)
            else:
                uri = str(path / "kg")
        self.root: KGRoot = open_kg_root(uri)
        self._nodes: dict[str, pd.DataFrame] | None = None
        self._edges: dict[str, pd.DataFrame] | None = None
        self._node_id_maps: dict[str, dict[str, int]] | None = None

    @property
    def node_types(self) -> list[str]:
        return self.root.list_nodes()

    @property
    def relations(self) -> list[str]:
        return self.root.list_edges()

    @property
    def nodes(self) -> dict[str, pd.DataFrame]:
        if self._nodes is None:
            self._nodes = {node_type: read_nodes(self.root, node_type) for node_type in self.node_types}
        return self._nodes

    @property
    def edges(self) -> dict[str, pd.DataFrame]:
        if self._edges is None:
            self._edges = {relation: read_edges(self.root, relation) for relation in self.relations}
        return self._edges

    @property
    def node_id_maps(self) -> dict[str, dict[str, int]]:
        if self._node_id_maps is None:
            self._node_id_maps = {
                node_type: {str(node_id): idx for idx, node_id in enumerate(df["id"].astype(str))}
                for node_type, df in self.nodes.items()
            }
        return self._node_id_maps

    def validate(self) -> KGValidationReport:
        """Return node/edge counts and dangling-edge counts per relation."""

        node_counts = {node_type: len(df) for node_type, df in self.nodes.items()}
        edge_counts: dict[str, int] = {}
        dangling_edges: dict[str, int] = {}
        maps = self.node_id_maps

        for relation, df in self.edges.items():
            edge_counts[relation] = len(df)
            if df.empty:
                dangling_edges[relation] = 0
                continue
            source_type = str(df["x_type"].iloc[0])
            target_type = str(df["y_type"].iloc[0])
            source_ids = maps.get(source_type, {})
            target_ids = maps.get(target_type, {})
            dangling = (~df["x_id"].astype(str).isin(source_ids)) | (~df["y_id"].astype(str).isin(target_ids))
            dangling_edges[relation] = int(dangling.sum())

        return KGValidationReport(
            node_counts=node_counts,
            edge_counts=edge_counts,
            dangling_edges=dangling_edges,
        )

    def edge_index_frames(self, *, strict: bool = True) -> dict[tuple[str, str, str], pd.DataFrame]:
        """Return integer-indexed edge tables keyed by canonical edge type."""

        frames: dict[tuple[str, str, str], pd.DataFrame] = {}
        maps = self.node_id_maps

        for relation, df in self.edges.items():
            if df.empty:
                rel = RELATION_BY_NAME.get(relation)
                if rel is None:
                    continue
                frames[(rel.source.value, relation, rel.target.value)] = pd.DataFrame({"src": [], "dst": []}, dtype="int64")
                continue

            source_type = str(df["x_type"].iloc[0])
            target_type = str(df["y_type"].iloc[0])
            source_ids = maps.get(source_type, {})
            target_ids = maps.get(target_type, {})

            src = df["x_id"].astype(str).map(source_ids)
            dst = df["y_id"].astype(str).map(target_ids)
            missing = src.isna() | dst.isna()
            if strict and bool(missing.any()):
                count = int(missing.sum())
                raise ValueError(f"{relation} has {count} dangling edges")

            indexed = pd.DataFrame(
                {
                    "src": src[~missing].astype("int64"),
                    "dst": dst[~missing].astype("int64"),
                }
            )
            frames[(source_type, relation, target_type)] = indexed.reset_index(drop=True)

        return frames

    def to_pyg(self, *, strict: bool = True):
        """Build a ``torch_geometric.data.HeteroData`` graph.

        ``torch`` and ``torch_geometric`` are optional runtime dependencies and
        are imported only when this method is called.
        """

        try:
            import torch
            from torch_geometric.data import HeteroData
        except ImportError as exc:
            raise ImportError("Install torch and torch_geometric to use KGLoader.to_pyg().") from exc

        data = HeteroData()
        for node_type, df in self.nodes.items():
            data[node_type].num_nodes = len(df)
            data[node_type].node_id = list(df["id"].astype(str))

        for edge_type, frame in self.edge_index_frames(strict=strict).items():
            edge_index = torch.tensor([frame["src"].tolist(), frame["dst"].tolist()], dtype=torch.long)
            data[edge_type].edge_index = edge_index

        return data

    def to_dgl(self, *, strict: bool = True):
        """Build a ``dgl.heterograph`` for backward-compatible training code."""

        try:
            import dgl
            import torch
        except ImportError as exc:
            raise ImportError("Install dgl and torch to use KGLoader.to_dgl().") from exc

        graph_data: dict[tuple[str, str, str], tuple[Any, Any]] = {}
        for edge_type, frame in self.edge_index_frames(strict=strict).items():
            graph_data[edge_type] = (
                torch.tensor(frame["src"].tolist(), dtype=torch.int64),
                torch.tensor(frame["dst"].tolist(), dtype=torch.int64),
            )

        return dgl.heterograph(
            graph_data,
            num_nodes_dict={node_type: len(df) for node_type, df in self.nodes.items()},
        )
