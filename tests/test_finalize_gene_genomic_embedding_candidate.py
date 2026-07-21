from __future__ import annotations

import numpy as np
import pyarrow as pa

from manage_db.finalize_gene_genomic_embedding_candidate import (
    classify_gene_denominator,
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


def test_classify_gene_denominator_accounts_for_exact_ensg_and_quarantine() -> None:
    result = classify_gene_denominator(
        canonical_ids={"ENSG1", "ENSG2", "NCBIGene:1", "OTHER:1"},
        interval_ids={"ENSG1"},
        sequence_ids={"ENSG1"},
        embedded_ids={"ENSG1"},
    )

    assert result["eligible_ensg"] == ["ENSG1", "ENSG2"]
    assert result["missing_rows"] == [
        {"node_id": "ENSG2", "reason": "source_interval_absent_or_excluded"}
    ]
    assert result["quarantine_rows"] == [
        {"node_id": "NCBIGene:1", "reason": "ncbi_gene_namespace"},
        {"node_id": "OTHER:1", "reason": "non_human_ensg_namespace"},
    ]
