from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from manage_db.kg_schema import EDGE_PARQUET_COLUMNS, NODE_TYPES, NodeType
from manage_db.kg_storage import open_kg_root, write_edges, write_nodes


def _node_frame(node_type: NodeType, ids: list[str]) -> pd.DataFrame:
    cols = ["id", *NODE_TYPES[node_type].xref_columns]
    rows = []
    for node_id in ids:
        row = {col: None for col in cols}
        row["id"] = node_id
        rows.append(row)
    return pd.DataFrame(rows)


def _edge_frame(rows: list[tuple[str, str]]) -> pd.DataFrame:
    data = []
    for x_id, y_id in rows:
        row = {name: "qa" for name, _ in EDGE_PARQUET_COLUMNS}
        row.update(
            {
                "x_id": x_id,
                "x_type": "disease",
                "y_id": y_id,
                "y_type": "gene",
                "relation": "disease_associated_gene",
                "display_relation": "disease associated gene",
                "source": "qa",
                "credibility": 3,
            }
        )
        data.append(row)
    return pd.DataFrame(data)


def _write_small_kg(path: Path) -> None:
    root = open_kg_root(str(path / "kg"))
    write_nodes(root, "disease", _node_frame(NodeType.DISEASE, ["EFO:1", "EFO:2"]))
    write_nodes(root, "gene", _node_frame(NodeType.GENE, ["ENSG1", "ENSG2"]))
    write_edges(root, "disease_associated_gene", _edge_frame([("EFO:1", "ENSG1"), ("EFO:2", "ENSG2")]))


def test_txgnn_import_exposes_kg_loader_without_dgl() -> None:
    import txgnn

    assert txgnn.KGLoader.__name__ == "KGLoader"


def test_kg_loader_scans_nodes_edges_and_validates(tmp_path: Path) -> None:
    _write_small_kg(tmp_path)

    from txgnn import KGLoader

    loader = KGLoader(tmp_path)
    assert loader.node_types == ["disease", "gene"]
    assert loader.relations == ["disease_associated_gene"]
    assert loader.node_id_maps["disease"] == {"EFO:1": 0, "EFO:2": 1}

    report = loader.validate()
    assert report.ok
    assert report.total_nodes == 4
    assert report.total_edges == 2
    assert report.dangling_edges == {"disease_associated_gene": 0}


def test_kg_loader_builds_edge_index_frames(tmp_path: Path) -> None:
    _write_small_kg(tmp_path)

    from txgnn import KGLoader

    frames = KGLoader(tmp_path / "kg").edge_index_frames()
    frame = frames[("disease", "disease_associated_gene", "gene")]
    assert frame.to_dict(orient="list") == {"src": [0, 1], "dst": [0, 1]}


def test_kg_loader_detects_dangling_edges(tmp_path: Path) -> None:
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(root, "disease", _node_frame(NodeType.DISEASE, ["EFO:1"]))
    write_nodes(root, "gene", _node_frame(NodeType.GENE, ["ENSG1"]))
    write_edges(root, "disease_associated_gene", _edge_frame([("EFO:1", "ENSG_MISSING")]))

    from txgnn import KGLoader

    loader = KGLoader(tmp_path)
    report = loader.validate()
    assert not report.ok
    assert report.dangling_edges == {"disease_associated_gene": 1}

    with pytest.raises(ValueError, match="dangling edges"):
        loader.edge_index_frames(strict=True)

    frame = loader.edge_index_frames(strict=False)[("disease", "disease_associated_gene", "gene")]
    assert frame.empty
