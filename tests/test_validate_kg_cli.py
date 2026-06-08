from __future__ import annotations

from pathlib import Path

import pandas as pd

from manage_db.kg_schema import NODE_TYPES, NodeType
from manage_db.kg_storage import open_kg_root, write_nodes
from manage_db.validate_kg import main


def _node_frame(node_type: NodeType, ids: list[str]) -> pd.DataFrame:
    cols = ["id", *NODE_TYPES[node_type].xref_columns]
    return pd.DataFrame([{**{col: None for col in cols}, "id": node_id} for node_id in ids])


def test_validate_kg_cli_accepts_plain_string_paths(tmp_path: Path, capsys) -> None:
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(root, "gene", _node_frame(NodeType.GENE, ["ENSG1"]))

    assert main([str(tmp_path / "kg")]) == 0

    out = capsys.readouterr().out
    assert "total_nodes: 1" in out
    assert "PASS: KG has no dangling edges" in out
