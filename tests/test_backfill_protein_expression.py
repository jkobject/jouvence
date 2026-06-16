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
        "gene_encodes_protein",
        pd.DataFrame(
            [
                _edge("ENSG1", "gene", "ENSP1", "protein", "gene_encodes_protein"),
                _edge("ENSG1", "gene", "ENSP2", "protein", "gene_encodes_protein"),
                _edge("ENSG2", "gene", "ENSP3", "protein", "gene_encodes_protein"),
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
    assert set(edges["source"]) == {"test;projected_via_gene_encodes_protein"}
    assert "tpm" in edges.columns
    assert "expression_level" in edges.columns


def test_project_expression_to_protein_respects_max_output_rows(tmp_path: Path) -> None:
    from manage_db.backfill_protein_expression import ProjectionTooLargeError, project_expression_to_protein

    source = open_kg_root(str(tmp_path / "source"))
    dest = open_kg_root(str(tmp_path / "dest"))
    write_edges(
        source,
        "gene_encodes_protein",
        pd.DataFrame(
            [
                _edge("ENSG1", "gene", "ENSP1", "protein", "gene_encodes_protein"),
                _edge("ENSG1", "gene", "ENSP2", "protein", "gene_encodes_protein"),
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
