from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from manage_db.finalize_gene_genomic_embedding_candidate import (
    classify_gene_denominator,
    expected_embedding_type,
    read_canonical_gene_ids,
    replace_embedding_column,
)


def test_replace_embedding_column_writes_fixed_size_float32() -> None:
    table = pa.table(
        {
            "node_id": ["ENSG1", "ENSG2"],
            "embedding": [[1.0, 2.0], [3.0, 4.0]],
            "embedding_dtype": ["float64", "float64"],
            "embedding_format": ["list", "list"],
        }
    )

    result = replace_embedding_column(table, expected_dim=2)

    assert result.schema.field("embedding").type == pa.list_(pa.float32(), 2)
    assert result["embedding_dtype"].to_pylist() == ["float32", "float32"]
    assert np.asarray(result["embedding"].to_pylist(), dtype=np.float32).tolist() == [
        [1.0, 2.0],
        [3.0, 4.0],
    ]


def test_expected_embedding_type_matches_runtime_pyarrow_type() -> None:
    assert expected_embedding_type(512) == str(pa.list_(pa.float32(), 512))


def test_read_canonical_gene_ids_uses_canonical_id_column(tmp_path: Path) -> None:
    path = tmp_path / "gene.parquet"
    pq.write_table(pa.table({"id": ["ENSG000001", "NCBI:1"]}), path)

    assert read_canonical_gene_ids(path) == {"ENSG000001", "NCBI:1"}


def test_classify_gene_denominator_accounts_for_exact_ensg_and_quarantine() -> None:
    result = classify_gene_denominator(
        canonical_ids={"ENSG1", "ENSG2", "NCBI:1", "OTHER:1"},
        interval_ids={"ENSG1"},
        sequence_ids={"ENSG1"},
        embedded_ids={"ENSG1"},
    )

    assert result["eligible_ensg"] == ["ENSG1", "ENSG2"]
    assert result["missing_rows"] == [
        {"node_id": "ENSG2", "reason": "source_interval_absent_or_excluded"}
    ]
    assert result["quarantine_rows"] == [
        {"node_id": "NCBI:1", "reason": "unmapped_ncbi_alias"},
        {"node_id": "OTHER:1", "reason": "non_ensg_namespace"},
    ]


def test_classify_gene_denominator_uses_exact_human_ensg_and_source_specific_quarantine_reasons() -> None:
    result = classify_gene_denominator(
        canonical_ids={"ENSG1", "ENSG_NOT_A_GENE", "ENSMUSG1", "NCBI:1", "OTHER:1"},
        interval_ids={"ENSG1"},
        sequence_ids={"ENSG1"},
        embedded_ids={"ENSG1"},
    )

    assert result["eligible_ensg"] == ["ENSG1"]
    assert {row["node_id"]: row["reason"] for row in result["quarantine_rows"]} == {
        "ENSG_NOT_A_GENE": "non_ensg_namespace",
        "ENSMUSG1": "non_human_ensembl_homologue",
        "NCBI:1": "unmapped_ncbi_alias",
        "OTHER:1": "non_ensg_namespace",
    }
