from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from manage_db.build_depmap_repair_candidate import build_depmap_repair_candidate


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

    created_at = "2026-07-18T08:00:00+00:00"
    first = build_depmap_repair_candidate(
        source,
        tmp_path / "first",
        source_generation="123456789",
        created_at=created_at,
    )
    second = build_depmap_repair_candidate(
        source,
        tmp_path / "second",
        source_generation="123456789",
        created_at=created_at,
    )

    assert first["relations"]["cell_line_gene_essentiality"]["edge_rows"] == 3
    assert first["relations"]["cell_line_gene_essentiality"]["evidence_rows"] == 3
    assert first["relations"]["cell_line_expresses_gene"]["edge_rows"] == 2
    assert first["relations"]["cell_line_expresses_gene"]["evidence_rows"] == 2
    assert first["content_hashes"] == second["content_hashes"]

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
