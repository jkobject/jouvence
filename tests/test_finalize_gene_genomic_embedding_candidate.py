from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from manage_db.finalize_gene_genomic_embedding_candidate import (
    build_canonical_gene_identity,
    classify_gene_denominator,
    embedding_type_matches,
    expected_embedding_type,
    read_canonical_gene_ids,
    replace_embedding_column,
    validate_builder_identity,
    validate_embedding_source_identity,
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


def test_embedding_type_match_accepts_equivalent_child_field_names() -> None:
    runtime_type = pa.list_(pa.field("element", pa.float32()), 512)

    assert embedding_type_matches(runtime_type, expected_dim=512)


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
        source_absent_ids={"ENSG2"},
        source_excluded_ids=set(),
    )

    assert result["eligible_ensg"] == ["ENSG1", "ENSG2"]
    assert result["missing_rows"] == [
        {"node_id": "ENSG2", "reason": "source_absent_ensembl_release"}
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
        source_absent_ids=set(),
        source_excluded_ids=set(),
    )

    assert result["eligible_ensg"] == ["ENSG1"]
    assert {row["node_id"]: row["reason"] for row in result["quarantine_rows"]} == {
        "ENSG_NOT_A_GENE": "non_ensg_namespace",
        "ENSMUSG1": "non_human_ensembl_homologue",
        "NCBI:1": "unmapped_ncbi_alias",
        "OTHER:1": "non_ensg_namespace",
    }


def test_canonical_gene_identity_binds_object_and_exact_ensg_set(tmp_path: Path) -> None:
    import hashlib

    path = tmp_path / "gene.parquet"
    pq.write_table(pa.table({"id": ["ENSG2", "NCBI:1", "ENSG1"]}), path)

    identity = build_canonical_gene_identity(
        path,
        uri="gs://bucket/kg/v2/nodes/gene.parquet",
        object_description={"generation": "123", "size": path.stat().st_size},
    )

    assert identity["uri"] == "gs://bucket/kg/v2/nodes/gene.parquet"
    assert identity["generation"] == "123"
    assert identity["rows"] == 3
    assert identity["unique_ids"] == 3
    assert identity["eligible_ensg_rows"] == 2
    assert identity["sorted_ensg_id_set_sha256"] == hashlib.sha256(
        b"ENSG1\nENSG2\n"
    ).hexdigest()
    assert len(identity["sha256"]) == 64


def _valid_builder_manifest() -> dict:
    return {
        "models": {
            "nucleotide_transformer": {
                "embedding_model": "InstaDeepAI/nucleotide-transformer-v2-50m-multi-species",
                "requested_revision": "81b29e5786726d891dbf929404ef20adca5b36f1",
                "resolved_revision": "81b29e5786726d891dbf929404ef20adca5b36f1",
                "tokenizer_revision": "81b29e5786726d891dbf929404ef20adca5b36f1",
                "embedding_dim": 512,
                "pooling": "attention_masked_mean_pool_last_hidden_state_per_window_then_mean_of_window_vectors",
                "normalization": "l2",
                "encoder_identity": "real_huggingface_remote_code",
            }
        },
        "policy_version": "foundation_embedding_policy_v1+gene_genomic_sequence_nt_window_mean_v1",
        "environment": {"transformers": "4.55.4"},
        "outputs": {
            "gene_genomic_sequence_nt_embeddings": {
                "embedding_dim": 512,
                "max_nucleotides_per_window": 1000,
                "window_stride": 1000,
                "tokenizer_max_length": None,
                "source": {"sha256": "a" * 64, "rows": 78164},
            }
        },
        "validation": {"passed": True},
    }


def test_finalizer_requires_exact_builder_model_runtime_source_and_policy_identity() -> None:
    validate_builder_identity(
        _valid_builder_manifest(), expected_source_sha256="a" * 64, expected_source_rows=78164
    )


def test_finalizer_rejects_builder_identity_drift() -> None:
    import pytest

    manifest = _valid_builder_manifest()
    manifest["models"]["nucleotide_transformer"]["tokenizer_revision"] = "wrong"
    with pytest.raises(RuntimeError, match="tokenizer_revision"):
        validate_builder_identity(
            manifest, expected_source_sha256="a" * 64, expected_source_rows=78164
        )


def test_finalizer_verifies_row_level_model_policy_and_source_identity(tmp_path: Path) -> None:
    source = tmp_path / "source.parquet"
    embedding = tmp_path / "embedding.parquet"
    pq.write_table(
        pa.table({"feature_key": ["f1"], "checksum_sha256": ["s1"]}), source
    )
    pq.write_table(
        pa.table(
            {
                "source_feature_key": ["f1"],
                "source_sequence_sha256": ["s1"],
                "embedding_model": ["InstaDeepAI/nucleotide-transformer-v2-50m-multi-species"],
                "embedding_version": ["InstaDeepAI/nucleotide-transformer-v2-50m-multi-species@81b29e5786726d891dbf929404ef20adca5b36f1+attention_masked_mean_pool_window_mean_l2+policy_v1"],
                "embedding_dim": [512],
                "embedding_dtype": ["float32"],
                "pooling": ["attention_masked_mean_pool_last_hidden_state_per_window_then_mean_of_window_vectors"],
                "normalization": ["l2"],
                "modality": ["gene_genomic_sequence"],
                "source_feature_table": ["features/gene_genomic_sequence.parquet"],
            }
        ),
        embedding,
    )

    checks = validate_embedding_source_identity(embedding, source)
    assert checks["passed"]


def test_finalizer_rejects_row_level_source_hash_mismatch(tmp_path: Path) -> None:
    import pytest

    source = tmp_path / "source.parquet"
    embedding = tmp_path / "embedding.parquet"
    pq.write_table(pa.table({"feature_key": ["f1"], "checksum_sha256": ["s1"]}), source)
    pq.write_table(
        pa.table(
            {
                "source_feature_key": ["f1"], "source_sequence_sha256": ["wrong"],
                "embedding_model": ["InstaDeepAI/nucleotide-transformer-v2-50m-multi-species"],
                "embedding_version": ["InstaDeepAI/nucleotide-transformer-v2-50m-multi-species@81b29e5786726d891dbf929404ef20adca5b36f1+attention_masked_mean_pool_window_mean_l2+policy_v1"],
                "embedding_dim": [512], "embedding_dtype": ["float32"],
                "pooling": ["attention_masked_mean_pool_last_hidden_state_per_window_then_mean_of_window_vectors"],
                "normalization": ["l2"], "modality": ["gene_genomic_sequence"],
                "source_feature_table": ["features/gene_genomic_sequence.parquet"],
            }
        ), embedding,
    )
    with pytest.raises(RuntimeError, match="row-level embedding identity"):
        validate_embedding_source_identity(embedding, source)
