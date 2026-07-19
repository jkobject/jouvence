from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from manage_db.build_depmap_repair_candidate import build_depmap_repair_candidate
from manage_db.kg_evidence import evidence_schema
from manage_db.kg_storage import edge_schema


def _write_endpoint_nodes(tmp_path: Path, *, genes: list[str] | None = None) -> tuple[Path, Path]:
    cell_lines = tmp_path / "cell_line.parquet"
    gene_nodes = tmp_path / "gene.parquet"
    pd.DataFrame({"id": ["ACH-000001", "ACH-000002"]}).to_parquet(cell_lines, index=False)
    pd.DataFrame({"id": genes or ["ENSG000001", "ENSG000002"]}).to_parquet(
        gene_nodes,
        index=False,
    )
    return cell_lines, gene_nodes


def test_build_depmap_repair_candidate_splits_topology_and_evidence_idempotently(
    tmp_path: Path,
) -> None:
    source = tmp_path / "cell_line_expresses_gene.parquet"
    pd.DataFrame(
        [
            {
                "x_id": "ACH-000001",
                "x_type": "cell_line",
                "y_id": "ENSG000001",
                "y_type": "gene",
                "relation": "cell_line_expresses_gene",
                "display_relation": "expresses gene",
                "source": "OpenTargets/DepMap",
                "credibility": 3,
                "gene_effect": 0.0,
                "expression": None,
                "is_essential": False,
            },
            {
                "x_id": "ACH-000001",
                "x_type": "cell_line",
                "y_id": "ENSG000002",
                "y_type": "gene",
                "relation": "cell_line_expresses_gene",
                "display_relation": "expresses gene",
                "source": "OpenTargets/DepMap",
                "credibility": 3,
                "gene_effect": -1.2,
                "expression": 0.0,
                "is_essential": True,
            },
            {
                "x_id": "ACH-000002",
                "x_type": "cell_line",
                "y_id": "ENSG000001",
                "y_type": "gene",
                "relation": "cell_line_expresses_gene",
                "display_relation": "expresses gene",
                "source": "OpenTargets/DepMap",
                "credibility": 3,
                "gene_effect": -0.3,
                "expression": 4.5,
                "is_essential": False,
            },
        ]
    ).to_parquet(source, index=False)
    cell_line_nodes, gene_nodes = _write_endpoint_nodes(tmp_path)

    created_at = "2026-07-18T08:00:00+00:00"
    first = build_depmap_repair_candidate(
        source,
        tmp_path / "first",
        source_generation="123456789",
        created_at=created_at,
        cell_line_nodes_path=cell_line_nodes,
        gene_nodes_path=gene_nodes,
    )
    second = build_depmap_repair_candidate(
        source,
        tmp_path / "second",
        source_generation="123456789",
        created_at=created_at,
        cell_line_nodes_path=cell_line_nodes,
        gene_nodes_path=gene_nodes,
    )

    assert first["relations"]["cell_line_gene_essentiality"]["edge_rows"] == 3
    assert first["relations"]["cell_line_gene_essentiality"]["evidence_rows"] == 3
    assert first["relations"]["cell_line_expresses_gene"]["edge_rows"] == 2
    assert first["relations"]["cell_line_expresses_gene"]["evidence_rows"] == 2
    assert first["content_hashes"] == second["content_hashes"]
    expression_object = first["objects"]["edges/cell_line_expresses_gene.parquet"]
    assert expression_object["rows"] == 2
    assert expression_object["size_bytes"] > 0
    assert expression_object["sha256"] == first["content_hashes"][
        "edges/cell_line_expresses_gene.parquet"
    ]
    assert [field["name"] for field in expression_object["schema"]] == [
        "x_id",
        "x_type",
        "y_id",
        "y_type",
        "relation",
        "display_relation",
        "source",
        "credibility",
    ]
    for relation in ("cell_line_gene_essentiality", "cell_line_expresses_gene"):
        validation = first["relations"][relation]
        assert validation["duplicate_edge_identities"] == 0
        assert validation["duplicate_evidence_identities"] == 0
        assert validation["missing_cell_line_endpoints"] == 0
        assert validation["missing_gene_endpoints"] == 0
        assert validation["edges_without_evidence"] == 0
        assert validation["evidence_without_edge"] == 0

    expression_edges = pd.read_parquet(
        tmp_path / "first" / "edges" / "cell_line_expresses_gene.parquet"
    )
    assert list(expression_edges.columns) == [
        "x_id",
        "x_type",
        "y_id",
        "y_type",
        "relation",
        "display_relation",
        "source",
        "credibility",
    ]
    assert expression_edges["y_id"].tolist() == ["ENSG000002", "ENSG000001"]

    essentiality_evidence = pd.read_parquet(
        tmp_path / "first" / "evidence" / "cell_line_gene_essentiality.parquet"
    )
    assert essentiality_evidence["effect_size"].tolist() == [0.0, -1.2, -0.3]
    assert essentiality_evidence["direction"].tolist() == [
        "not_essential",
        "essential",
        "not_essential",
    ]

    expression_evidence = pd.read_parquet(
        tmp_path / "first" / "evidence" / "cell_line_expresses_gene.parquet"
    )
    assert expression_evidence["evidence_score"].tolist() == [0.0, 4.5]
    assert not (tmp_path / "first" / "edges" / "cell_line_expresses_protein.parquet").exists()
    assert not (tmp_path / "first" / "evidence" / "cell_line_expresses_protein.parquet").exists()


def test_build_depmap_repair_candidate_uses_authoritative_arrow_schemas(tmp_path: Path) -> None:
    source = tmp_path / "source.parquet"
    pd.DataFrame(
        [
            {
                "x_id": "ACH-000001",
                "x_type": "cell_line",
                "y_id": "ENSG000001",
                "y_type": "gene",
                "source": "OpenTargets/DepMap",
                "credibility": 3,
                "gene_effect": -1.0,
                "expression": 0.0,
                "is_essential": True,
            }
        ]
    ).to_parquet(source, index=False)

    output = tmp_path / "out"
    build_depmap_repair_candidate(
        source,
        output,
        source_generation="123456789",
        created_at="2026-07-18T08:00:00+00:00",
    )

    for relation in ("cell_line_gene_essentiality", "cell_line_expresses_gene"):
        assert pq.read_schema(output / "edges" / f"{relation}.parquet") == edge_schema()
        assert pq.read_schema(output / "evidence" / f"{relation}.parquet") == evidence_schema()


def test_build_depmap_repair_candidate_fails_closed_on_changed_source_counts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.parquet"
    pd.DataFrame(
        [
            {
                "x_id": "ACH-000001",
                "x_type": "cell_line",
                "y_id": "ENSG000001",
                "y_type": "gene",
                "source": "OpenTargets/DepMap",
                "credibility": 3,
                "gene_effect": -1.0,
                "expression": 2.0,
                "is_essential": True,
            }
        ]
    ).to_parquet(source, index=False)

    with pytest.raises(ValueError, match="pinned count contract changed"):
        build_depmap_repair_candidate(
            source,
            tmp_path / "out",
            source_generation="123456789",
            created_at="2026-07-18T08:00:00+00:00",
            expected_source_rows=2,
            expected_expression_rows=1,
        )

    assert not (tmp_path / "out").exists()


def test_build_depmap_repair_candidate_fails_closed_on_missing_endpoint(tmp_path: Path) -> None:
    source = tmp_path / "source.parquet"
    pd.DataFrame(
        [
            {
                "x_id": "ACH-000001",
                "x_type": "cell_line",
                "y_id": "ENSG_MISSING",
                "y_type": "gene",
                "source": "OpenTargets/DepMap",
                "credibility": 3,
                "gene_effect": -1.0,
                "expression": 0.0,
                "is_essential": True,
            }
        ]
    ).to_parquet(source, index=False)
    cell_line_nodes, gene_nodes = _write_endpoint_nodes(tmp_path, genes=["ENSG000001"])

    with pytest.raises(ValueError, match="source endpoint validation failed"):
        build_depmap_repair_candidate(
            source,
            tmp_path / "out",
            source_generation="123456789",
            created_at="2026-07-18T08:00:00+00:00",
            cell_line_nodes_path=cell_line_nodes,
            gene_nodes_path=gene_nodes,
        )

    assert not (tmp_path / "out").exists()
