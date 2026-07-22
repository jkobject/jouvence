from __future__ import annotations

import tomllib
from pathlib import Path

from manage_db.build_gene_genomic_sequence_embeddings import (
    build_denominator_reason_rows,
    select_gene_windows,
)


def test_select_gene_windows_uses_full_short_locus_and_gene_start_for_long_locus() -> None:
    assert select_gene_windows("ACGT", window_size=6) == [(0, 4, "ACGT")]
    assert select_gene_windows("ACGTACGTAA", window_size=6) == [(0, 6, "ACGTAC")]


def test_build_denominator_reason_rows_accounts_for_each_unembedded_ensg() -> None:
    rows = build_denominator_reason_rows(
        denominator_ids={"ENSG1", "ENSG2", "ENSG3", "ENSG4"},
        interval_ids={"ENSG1", "ENSG2", "ENSG3"},
        sequence_ids={"ENSG1", "ENSG2"},
        embedded_ids={"ENSG1"},
        source_absent_ids={"ENSG4"},
        source_excluded_ids=set(),
    )

    reasons = {row["node_id"]: row["reason"] for row in rows}
    assert reasons == {
        "ENSG2": "embedding_missing_or_failed",
        "ENSG3": "source_sequence_overlength",
        "ENSG4": "source_absent_ensembl_release",
    }


def test_build_denominator_reason_rows_requires_measured_absent_and_excluded_classes() -> None:
    rows = build_denominator_reason_rows(
        denominator_ids={"ENSG1", "ENSG2", "ENSG3"},
        interval_ids={"ENSG1"},
        sequence_ids={"ENSG1"},
        embedded_ids={"ENSG1"},
        source_absent_ids={"ENSG2"},
        source_excluded_ids={"ENSG3"},
    )

    assert rows == [
        {"node_id": "ENSG2", "reason": "source_absent_ensembl_release"},
        {"node_id": "ENSG3", "reason": "source_excluded_contig_or_build"},
    ]


def test_build_denominator_reason_rows_rejects_unmeasured_missing_id() -> None:
    import pytest

    with pytest.raises(ValueError, match="unmeasured missing denominator IDs"):
        build_denominator_reason_rows(
            denominator_ids={"ENSG1", "ENSG2"},
            interval_ids={"ENSG1"},
            sequence_ids={"ENSG1"},
            embedded_ids={"ENSG1"},
            source_absent_ids=set(),
            source_excluded_ids=set(),
        )


def test_reason_rows_are_deterministically_sorted() -> None:
    rows = build_denominator_reason_rows(
        denominator_ids={"ENSG3", "ENSG1", "ENSG2"},
        interval_ids={"ENSG1"},
        sequence_ids={"ENSG1"},
        embedded_ids=set(),
        source_absent_ids={"ENSG2", "ENSG3"},
        source_excluded_ids=set(),
    )

    assert [row["node_id"] for row in rows] == ["ENSG1", "ENSG2", "ENSG3"]


def test_nucleotide_runtime_pins_transformers_version_that_loads_checkpoint_weights() -> None:
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())

    assert "transformers==4.55.4" in pyproject["dependency-groups"]["embeddings-nucleotide"]
