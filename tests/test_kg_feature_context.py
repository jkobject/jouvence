from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from manage_db import kg_feature_context, kg_storage


FEATURE_TABLE = "gene_gene_expression_correlation"


def _sample_feature_context_df() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "feature_table": [FEATURE_TABLE],
            "x_id": ["ENSG00000141510"],
            "x_type": ["gene"],
            "y_id": ["ENSG00000171862"],
            "y_type": ["gene"],
            "evidence_type": ["correlative"],
            "source": ["fixture"],
            "source_dataset": ["expression_correlation_fixture_v1"],
            "source_record_id": ["fixture:tp53-pten-liver"],
            "context_type": ["tissue"],
            "context_id": ["UBERON:0002107"],
            "context_name": ["liver"],
            "correlation_coefficient": [0.73],
            "effect_size": [pd.NA],
            "p_value": [0.001],
            "q_value": [0.01],
            "method": ["spearman"],
            "sample_count": [120],
            "score": [pd.NA],
            "predicate": ["coexpression/correlation only; not regulation"],
            "license": ["test-fixture"],
            "release": ["v1"],
            "created_at": ["2026-06-22T00:00:00Z"],
        }
    )
    return df.convert_dtypes(dtype_backend="pyarrow")


def test_feature_context_roundtrip_under_features_directory(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    df = _sample_feature_context_df()

    count = kg_feature_context.write_feature_context(root, FEATURE_TABLE, df)

    assert count == 1
    assert (tmp_path / "kg" / "features" / f"{FEATURE_TABLE}.parquet").exists()
    assert kg_feature_context.list_feature_context_tables(root) == [FEATURE_TABLE]
    result = kg_feature_context.read_feature_context(root, FEATURE_TABLE).convert_dtypes(
        dtype_backend="pyarrow"
    )
    assert result.loc[0, "feature_key"] == (
        "gene_gene_expression_correlation|ENSG00000141510|ENSG00000171862|"
        "fixture|fixture:tp53-pten-liver|tissue|UBERON:0002107"
    )
    assert result.loc[0, "evidence_type"] == "correlative"
    assert result.loc[0, "context_id"] == "UBERON:0002107"
    assert float(result.loc[0, "correlation_coefficient"]) == pytest.approx(0.73)


def test_feature_context_validates_endpoint_types(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    bad = _sample_feature_context_df()
    bad.loc[0, "y_type"] = "protein"

    with pytest.raises(ValueError, match="invalid y_type"):
        kg_feature_context.write_feature_context(root, FEATURE_TABLE, bad)


def test_feature_context_requires_explicit_non_causal_evidence_type(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    bad = _sample_feature_context_df()
    bad.loc[0, "evidence_type"] = "mechanistic"

    with pytest.raises(ValueError, match="causal/mechanistic evidence_type"):
        kg_feature_context.write_feature_context(root, FEATURE_TABLE, bad)


def test_feature_context_rejects_ambiguous_evidence_type(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    bad = _sample_feature_context_df()
    bad.loc[0, "evidence_type"] = "coexpression"

    with pytest.raises(ValueError, match="explicitly non-causal"):
        kg_feature_context.write_feature_context(root, FEATURE_TABLE, bad)


def test_feature_context_append_deduplicates_by_source_and_context(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    base = _sample_feature_context_df()
    updated = base.copy()
    updated.loc[0, "q_value"] = 0.02

    kg_feature_context.write_feature_context(root, FEATURE_TABLE, base)
    count = kg_feature_context.write_feature_context(root, FEATURE_TABLE, updated, mode="append")

    result = kg_feature_context.read_feature_context(root, FEATURE_TABLE)
    assert count == 1
    assert len(result) == 1
    assert result.loc[0, "q_value"] == pytest.approx(0.02)


def test_allowed_feature_context_tables_document_endpoint_contracts() -> None:
    tables = kg_feature_context.allowed_feature_context_tables()

    assert tables["gene_gene_expression_correlation"] == ("gene", "gene")
    assert tables["rna_gene_expression_correlation"] == ("transcript", "gene")
    assert tables["gene_disease_association_score"] == ("gene", "disease")
