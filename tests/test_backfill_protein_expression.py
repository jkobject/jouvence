from __future__ import annotations

from pathlib import Path

import pandas as pd

from manage_db.kg_storage import open_kg_root, read_edges, write_edges, write_nodes


def _edge(x_id: str, x_type: str, y_id: str, y_type: str, relation: str, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "x_id": x_id,
        "x_type": x_type,
        "y_id": y_id,
        "y_type": y_type,
        "relation": relation,
        "display_relation": relation.replace("_", " "),
        "source": "test",
        "credibility": 3,
    }
    row.update(extra)
    return row


def test_project_cell_type_gene_expression_to_protein_edges_preserves_gene_metadata(tmp_path: Path) -> None:
    from manage_db.backfill_protein_expression import project_expression_to_protein

    source = open_kg_root(str(tmp_path / "source"))
    dest = open_kg_root(str(tmp_path / "dest"))
    write_nodes(
        source,
        "protein",
        pd.DataFrame(
            [
                {"id": "ENSP1", "ensembl_gene_id": "ENSG1", "uniprot_id": None, "refseq_protein": None, "pdb_ids": None, "name": "p1", "source": "test"},
                {"id": "ENSP2", "ensembl_gene_id": "ENSG1", "uniprot_id": None, "refseq_protein": None, "pdb_ids": None, "name": "p2", "source": "test"},
                {"id": "ENSP3", "ensembl_gene_id": "ENSG2", "uniprot_id": None, "refseq_protein": None, "pdb_ids": None, "name": "p3", "source": "test"},
            ]
        ),
    )
    write_edges(
        source,
        "cell_type_expresses_gene",
        pd.DataFrame(
            [
                _edge("CL:1", "cell_type", "ENSG1", "gene", "cell_type_expresses_gene", tpm="8.5", expression_level="high"),
                _edge("CL:1", "cell_type", "ENSG1", "gene", "cell_type_expresses_gene", tpm="8.5", expression_level="high"),
                _edge("CL:2", "cell_type", "ENSG2", "gene", "cell_type_expresses_gene", tpm="2.0", expression_level="medium"),
                _edge("CL:3", "cell_type", "ENSG_MISSING", "gene", "cell_type_expresses_gene", tpm="1.0", expression_level="low"),
            ]
        ),
    )

    result = project_expression_to_protein(
        source_root=source,
        dest_root=dest,
        source_relation="cell_type_expresses_gene",
        dest_relation="cell_type_expresses_protein",
        source_x_type="cell_type",
        max_output_rows=10,
    )

    assert result.input_rows == 3
    assert result.output_rows == 3
    assert result.mapped_gene_rows == 2
    assert result.unmapped_gene_rows == 1
    assert result.distinct_pairs == 3

    edges = read_edges(dest, "cell_type_expresses_protein").sort_values(["x_id", "y_id"]).reset_index(drop=True)
    assert edges[["x_id", "x_type", "y_id", "y_type", "relation"]].to_dict("records") == [
        {"x_id": "CL:1", "x_type": "cell_type", "y_id": "ENSP1", "y_type": "protein", "relation": "cell_type_expresses_protein"},
        {"x_id": "CL:1", "x_type": "cell_type", "y_id": "ENSP2", "y_type": "protein", "relation": "cell_type_expresses_protein"},
        {"x_id": "CL:2", "x_type": "cell_type", "y_id": "ENSP3", "y_type": "protein", "relation": "cell_type_expresses_protein"},
    ]
    assert set(edges["gene_id"]) == {"ENSG1", "ENSG2"}
    assert set(edges["source"]) == {"test;projected_via_protein_node_xref"}
    assert "tpm" in edges.columns
    assert "expression_level" in edges.columns


def test_project_expression_to_protein_respects_max_output_rows(tmp_path: Path) -> None:
    from manage_db.backfill_protein_expression import ProjectionTooLargeError, project_expression_to_protein

    source = open_kg_root(str(tmp_path / "source"))
    dest = open_kg_root(str(tmp_path / "dest"))
    write_nodes(
        source,
        "protein",
        pd.DataFrame(
            [
                {"id": "ENSP1", "ensembl_gene_id": "ENSG1", "uniprot_id": None, "refseq_protein": None, "pdb_ids": None, "name": "p1", "source": "test"},
                {"id": "ENSP2", "ensembl_gene_id": "ENSG1", "uniprot_id": None, "refseq_protein": None, "pdb_ids": None, "name": "p2", "source": "test"},
            ]
        ),
    )
    write_edges(
        source,
        "cell_type_expresses_gene",
        pd.DataFrame([_edge("CL:1", "cell_type", "ENSG1", "gene", "cell_type_expresses_gene")]),
    )

    try:
        project_expression_to_protein(
            source_root=source,
            dest_root=dest,
            source_relation="cell_type_expresses_gene",
            dest_relation="cell_type_expresses_protein",
            source_x_type="cell_type",
            max_output_rows=1,
        )
    except ProjectionTooLargeError as exc:
        assert exc.estimated_output_rows == 2
    else:  # pragma: no cover
        raise AssertionError("ProjectionTooLargeError not raised")

    assert not (tmp_path / "dest" / "edges" / "cell_type_expresses_protein.parquet").exists()



def test_build_cell_line_protein_expression_duckdb_filters_and_writes_evidence(tmp_path: Path) -> None:
    from manage_db.backfill_protein_expression import build_cell_line_protein_expression_duckdb
    from manage_db.kg_evidence import read_evidence

    source = open_kg_root(str(tmp_path / "source"))
    write_nodes(
        source,
        "protein",
        pd.DataFrame(
            [
                {"id": "ENSP1", "ensembl_gene_id": "ENSG1", "uniprot_id": None, "refseq_protein": None, "pdb_ids": None, "name": "p1", "source": "test"},
                {"id": "ENSP2", "ensembl_gene_id": "ENSG2", "uniprot_id": None, "refseq_protein": None, "pdb_ids": None, "name": "p2", "source": "test"},
            ]
        ),
    )
    write_edges(
        source,
        "cell_line_expresses_gene",
        pd.DataFrame(
            [
                _edge("SIDM1", "cell_line", "ENSG1", "gene", "cell_line_expresses_gene", source="OpenTargets/DepMap", expression=12.5, gene_effect=-0.1, is_essential=False),
                _edge("SIDM1", "cell_line", "ENSG2", "gene", "cell_line_expresses_gene", source="OpenTargets/DepMap", expression=11.9, gene_effect=-0.2, is_essential=True),
            ]
        ),
    )

    result = build_cell_line_protein_expression_duckdb(
        source_kg_root=tmp_path / "source",
        dest_kg_root=tmp_path / "dest",
        min_expression=12.0,
        duckdb_memory_limit="512MB",
        threads=1,
    )

    assert result.output_rows == 1
    dest = open_kg_root(str(tmp_path / "dest"))
    edges = read_edges(dest, "cell_line_expresses_protein")
    assert edges[["x_id", "y_id", "relation", "gene_id"]].to_dict("records") == [
        {"x_id": "SIDM1", "y_id": "ENSP1", "relation": "cell_line_expresses_protein", "gene_id": "ENSG1"}
    ]
    assert edges.loc[0, "min_expression"] == 12.0
    assert edges.loc[0, "projection_method"] == "high_mrna_expression_projected_to_protein"

    evidence = read_evidence(dest, "cell_line_expresses_protein")
    assert len(evidence) == 1
    assert evidence.loc[0, "edge_key"] == "cell_line_expresses_protein|SIDM1|ENSP1"
    assert evidence.loc[0, "source_dataset"] == "DepMap"
    assert evidence.loc[0, "predicate"] == "high_mrna_expression_projected_to_protein"
    assert evidence.loc[0, "evidence_score"] == 12.5



def test_backfill_existing_cell_type_protein_expression_evidence(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_protein_expression import backfill_protein_expression_evidence_duckdb
    from manage_db.kg_evidence import read_evidence
    from manage_db.kg_storage import open_kg_root, write_edges

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(
        root,
        "cell_type_expresses_protein",
        pd.DataFrame(
            [
                {
                    "x_id": "CL:1",
                    "x_type": "cell_type",
                    "y_id": "ENSP1",
                    "y_type": "protein",
                    "relation": "cell_type_expresses_protein",
                    "display_relation": "expresses protein",
                    "source": "OpenTargets/HPA;projected_via_protein_node_xref",
                    "credibility": 3,
                    "gene_id": "ENSG1",
                    "tpm": 12.5,
                    "expression_level": 2,
                }
            ]
        ),
    )

    assert backfill_protein_expression_evidence_duckdb(
        kg_root=tmp_path / "kg",
        relation="cell_type_expresses_protein",
        source_dataset="HPA/OpenTargets expression",
        predicate="rna_expression_projected_to_protein",
        extraction_method="HPA/OpenTargets RNA expression projected through protein node xref",
        duckdb_memory_limit="256MB",
        threads=1,
    ) == 1

    evidence = read_evidence(root, "cell_type_expresses_protein")
    assert len(evidence) == 1
    assert evidence.loc[0, "edge_key"] == "cell_type_expresses_protein|CL:1|ENSP1"
    assert evidence.loc[0, "source"] == "OpenTargets"
    assert evidence.loc[0, "source_dataset"] == "HPA/OpenTargets expression"
    assert evidence.loc[0, "evidence_score"] == 12.5
    assert evidence.loc[0, "predicate"] == "rna_expression_projected_to_protein"
    assert audit_edge_evidence(tmp_path / "kg", relations=["cell_type_expresses_protein"]).ok
