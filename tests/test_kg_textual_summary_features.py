from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from manage_db import kg_storage, kg_textual_summary_features as tsf

FEATURE_TABLE = "protein_textual_summary"


def _sample_summary_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "feature_table": [FEATURE_TABLE],
            "node_id": ["ENSP00000354587"],
            "node_type": ["protein"],
            "summary_kind": ["function"],
            "summary_text": ["Tumor suppressor that acts as a transcription factor in stress responses."],
            "source": ["UniProtKB"],
            "source_dataset": ["UniProtKB comments FUNCTION/SUBCELLULAR_LOCATION/PTM"],
            "source_record_id": ["P04637"],
            "provenance": ["https://rest.uniprot.org/uniprotkb/P04637.json"],
            "license": ["CC BY 4.0"],
            "citation": ["UniProt Consortium"],
            "release": ["2026_02"],
            "created_at": ["2026-06-22T00:00:00+00:00"],
        }
    ).convert_dtypes(dtype_backend="pyarrow")


def test_textual_summary_roundtrip_under_features_directory(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    df = _sample_summary_df()

    validation = tsf.write_textual_summaries(root, FEATURE_TABLE, df, endpoint_node_ids={"ENSP00000354587"})

    assert validation.rows == 1
    assert validation.unique_nodes == 1
    assert validation.nodes_not_in_endpoint == 0
    assert validation.endpoint_nodes == 1
    assert validation.coverage_fraction == pytest.approx(1.0)
    assert (tmp_path / "kg" / "features" / f"{FEATURE_TABLE}.parquet").exists()
    assert tsf.list_textual_summary_tables(root) == [FEATURE_TABLE]
    result = tsf.read_textual_summaries(root, FEATURE_TABLE).convert_dtypes(dtype_backend="pyarrow")
    assert result.loc[0, "feature_key"] == "protein_textual_summary|ENSP00000354587|UniProtKB|P04637|function"
    assert result.loc[0, "summary_text"].startswith("Tumor suppressor")


def test_textual_summary_validates_node_type() -> None:
    bad = _sample_summary_df()
    bad.loc[0, "node_type"] = "gene"

    with pytest.raises(ValueError, match="invalid node_type"):
        tsf.validate_textual_summaries(bad, FEATURE_TABLE)


def test_textual_summary_rejects_endpoint_misses() -> None:
    df = _sample_summary_df()

    with pytest.raises(ValueError, match="node_ids not present"):
        tsf.validate_textual_summaries(df, FEATURE_TABLE, endpoint_node_ids={"ENSP00000000000"})


def test_textual_summary_rejects_empty_and_oversized_text() -> None:
    empty = _sample_summary_df()
    empty.loc[0, "summary_text"] = ""
    with pytest.raises(ValueError, match="empty summary_text"):
        tsf.validate_textual_summaries(empty, FEATURE_TABLE)

    large = _sample_summary_df()
    large.loc[0, "summary_text"] = "x" * 12
    with pytest.raises(ValueError, match="over max_text_chars"):
        tsf.validate_textual_summaries(large, FEATURE_TABLE, max_text_chars=10)


def test_textual_summary_append_deduplicates_by_source_record(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    base = _sample_summary_df()
    updated = base.copy()
    updated.loc[0, "summary_text"] = "Updated function summary."

    tsf.write_textual_summaries(root, FEATURE_TABLE, base)
    validation = tsf.write_textual_summaries(root, FEATURE_TABLE, updated, mode="append")

    result = tsf.read_textual_summaries(root, FEATURE_TABLE)
    assert validation.rows == 1
    assert validation.duplicate_rows_removed == 1
    assert len(result) == 1
    assert result.loc[0, "summary_text"] == "Updated function summary."


def test_source_policy_audit_rejects_incompatible_scraping_sources() -> None:
    audit = tsf.source_policy_audit().set_index("source")

    assert audit.loc["GeneCards", "decision"] == "reject"
    assert "proprietary" in audit.loc["GeneCards", "license"]
    assert audit.loc["DrugBank", "decision"] == "reject_scraping"
    assert audit.loc["UniProtKB", "decision"] == "allow_with_attribution"
    assert audit.loc["Reactome", "license"] == "CC BY 4.0"


def test_allowed_textual_summary_tables_document_node_contracts() -> None:
    tables = tsf.allowed_textual_summary_tables()

    assert tables["gene_textual_summary"] == "gene"
    assert tables["protein_textual_summary"] == "protein"
    assert tables["disease_textual_summary"] == "disease"
    assert tables["tissue_textual_summary"] == "tissue"
    assert tables["molecule_textual_summary"] == "molecule"
    assert tables["pathway_textual_summary"] == "pathway"
