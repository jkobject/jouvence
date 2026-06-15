from __future__ import annotations

from pathlib import Path

import pandas as pd

from manage_db.audit_node_ontology_coverage import (
    audit_node_ontology_coverage,
    infer_namespace,
    main,
)
from manage_db.kg_schema import NODE_TYPES, NodeType
from manage_db.kg_storage import open_kg_root, write_nodes


def _node_frame(node_type: NodeType, rows: list[dict[str, object]]) -> pd.DataFrame:
    columns = ["id", *NODE_TYPES[node_type].xref_columns]
    normalized = []
    for row in rows:
        normalized.append({column: row.get(column) for column in columns})
    return pd.DataFrame(normalized)


def test_infer_namespace_covers_common_txgnn_ids() -> None:
    assert infer_namespace("ENSG00000139618") == "Ensembl Gene"
    assert infer_namespace("ENST00000380152") == "Ensembl Transcript"
    assert infer_namespace("ENSP00000369497") == "Ensembl Protein"
    assert infer_namespace("PMID:123") == "PMID"
    assert infer_namespace("CHEMBL941") == "ChEMBL"
    assert infer_namespace("DB09130") == "DrugBank"
    assert infer_namespace("rs7412") == "dbSNP"
    assert infer_namespace("1_100_A_T") == "gnomAD-like"
    assert infer_namespace("EFO:0000305") == "EFO"
    assert infer_namespace("EFO_0000305") == "EFO_underscore"
    assert infer_namespace("CL_0000576") == "CL_underscore"


def test_audit_node_ontology_coverage_reports_namespaces_and_xrefs(tmp_path: Path) -> None:
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(
        root,
        "disease",
        _node_frame(
            NodeType.DISEASE,
            [
                {"id": "EFO:0000305", "mondo_id": "MONDO:0000001"},
                {"id": "MONDO:0005148"},
            ],
        ),
    )
    write_nodes(
        root,
        "mutation",
        _node_frame(
            NodeType.MUTATION,
            [
                {"id": "rs7412"},
                {"id": "1_100_A_T", "gnomad_id": "1_100_A_T"},
            ],
        ),
    )

    audit = audit_node_ontology_coverage(tmp_path / "kg")

    assert audit.total_rows == 4
    assert audit.nodes["disease"].namespaces == {"EFO": 1, "MONDO": 1}
    assert audit.nodes["disease"].xref_non_null["mondo_id"] == 1
    assert audit.nodes["mutation"].namespaces == {"dbSNP": 1, "gnomAD-like": 1}
    assert audit.nodes["mutation"].xref_non_null["gnomad_id"] == 1
    assert "protein" in audit.missing_nodes


def test_cli_node_ontology_coverage_is_informational(tmp_path: Path) -> None:
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(root, "gene", _node_frame(NodeType.GENE, [{"id": "ENSG1"}]))

    assert main([str(tmp_path / "kg")]) == 0
    assert main([str(tmp_path / "kg"), "--json"]) == 0
