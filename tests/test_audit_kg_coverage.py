from __future__ import annotations

from pathlib import Path

import pandas as pd

from manage_db.audit_kg_coverage import audit_coverage, main
from manage_db.kg_schema import NODE_TYPES, RELATIONS, NodeType
from manage_db.kg_storage import open_kg_root, write_edges, write_nodes


def _node_frame(node_type: NodeType, ids: list[str]) -> pd.DataFrame:
    cols = ["id", *NODE_TYPES[node_type].xref_columns]
    return pd.DataFrame([{**{col: None for col in cols}, "id": node_id} for node_id in ids])


def test_audit_coverage_reports_present_counts_and_missing_schema_files(tmp_path: Path) -> None:
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(root, "disease", _node_frame(NodeType.DISEASE, ["EFO:1"]))
    write_nodes(root, "gene", _node_frame(NodeType.GENE, ["ENSG1", "ENSG2"]))
    write_edges(
        root,
        "disease_associated_gene",
        pd.DataFrame(
            [
                {
                    "x_id": "EFO:1",
                    "x_type": "disease",
                    "y_id": "ENSG1",
                    "y_type": "gene",
                    "relation": "disease_associated_gene",
                    "display_relation": "disease associated gene",
                    "source": "qa",
                    "credibility": 3,
                }
            ]
        ),
    )

    audit = audit_coverage(tmp_path / "kg")

    assert audit.node_counts == {"disease": 1, "gene": 2}
    assert audit.edge_counts == {"disease_associated_gene": 1}
    assert "transcript" in audit.missing_nodes
    assert "gene_has_transcript" in audit.missing_edges
    assert len(audit.missing_nodes) == len(NODE_TYPES) - 2
    assert len(audit.missing_edges) == len(RELATIONS) - 1
    assert not audit.ok


def test_cli_audit_is_informational_by_default(tmp_path: Path) -> None:
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(root, "gene", _node_frame(NodeType.GENE, ["ENSG1"]))

    assert main([str(tmp_path / "kg")]) == 0


def test_cli_can_fail_on_missing_schema_files(tmp_path: Path) -> None:
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(root, "gene", _node_frame(NodeType.GENE, ["ENSG1"]))

    assert main([str(tmp_path / "kg"), "--fail-on-missing"]) == 1
