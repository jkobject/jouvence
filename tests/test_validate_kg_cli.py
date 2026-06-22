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


def test_validate_kg_cli_progress_heartbeats_go_to_stderr(tmp_path: Path, capsys) -> None:
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(root, "gene", _node_frame(NodeType.GENE, ["ENSG1"]))

    assert main([str(tmp_path / "kg"), "--progress-every-relations", "1"]) == 0

    captured = capsys.readouterr()
    assert "total_nodes: 1" in captured.out
    assert "[validate_kg] counted nodes/gene.parquet rows=1" in captured.err


def test_validate_kg_cli_streams_edges_and_reports_dangling(tmp_path: Path, capsys) -> None:
    from manage_db.kg_storage import write_edges

    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(root, "transcript", _node_frame(NodeType.TRANSCRIPT, ["ENST1"]))
    write_nodes(root, "protein", _node_frame(NodeType.PROTEIN, ["ENSP1"]))
    write_edges(
        root,
        "transcript_encodes_protein",
        pd.DataFrame(
            [
                {
                    "x_id": "ENST1",
                    "x_type": "transcript",
                    "y_id": "ENSP1",
                    "y_type": "protein",
                    "relation": "transcript_encodes_protein",
                    "display_relation": "encodes protein",
                    "source": "test",
                    "credibility": 3,
                },
                {
                    "x_id": "ENST_MISSING",
                    "x_type": "transcript",
                    "y_id": "ENSP1",
                    "y_type": "protein",
                    "relation": "transcript_encodes_protein",
                    "display_relation": "encodes protein",
                    "source": "test",
                    "credibility": 3,
                },
            ]
        ),
    )

    assert main([str(tmp_path / "kg"), "--batch-size", "1"]) == 1

    out = capsys.readouterr().out
    assert "total_dangling_edges: 1" in out
    assert "transcript_encodes_protein: 1" in out

def test_validate_kg_cli_pyarrow_streaming_mode(tmp_path: Path, capsys) -> None:
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(root, "gene", _node_frame(NodeType.GENE, ["ENSG1"]))

    assert main([str(tmp_path / "kg"), "--pyarrow-streaming"]) == 0

    out = capsys.readouterr().out
    assert "total_nodes: 1" in out
    assert "PASS: KG has no dangling edges" in out

