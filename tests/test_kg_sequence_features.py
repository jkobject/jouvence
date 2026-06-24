from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from manage_db import kg_sequence_features as seqf
from manage_db import kg_storage
from manage_db.build_sequence_features import build_sequence_feature_tables

PROTEIN_TABLE = "protein_sequence"
TRANSCRIPT_TABLE = "transcript_sequence"


def _sample_protein_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "feature_table": [PROTEIN_TABLE],
            "node_id": ["ENSP00000354587"],
            "node_type": ["protein"],
            "sequence_kind": ["amino_acid"],
            "sequence": ["MEEPQSDPSV"],
            "alphabet": ["protein_iupac"],
            "source": ["Ensembl"],
            "source_dataset": ["Ensembl protein FASTA"],
            "source_record_id": ["ENSP00000354587"],
            "source_release": ["release-114"],
            "provenance": ["fixture/Homo_sapiens.GRCh38.pep.all.fa.gz"],
            "license": ["EMBL-EBI open data / attribution"],
            "citation": ["Ensembl release 114"],
            "created_at": ["2026-06-22T00:00:00+00:00"],
        }
    ).convert_dtypes(dtype_backend="pyarrow")


def test_sequence_roundtrip_under_features_directory(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    validation = seqf.write_sequences(root, PROTEIN_TABLE, _sample_protein_df(), endpoint_node_ids={"ENSP00000354587"})

    assert validation.rows == 1
    assert validation.unique_nodes == 1
    assert validation.nodes_not_in_endpoint == 0
    assert validation.min_length == 10
    assert validation.max_length == 10
    assert (tmp_path / "kg" / "features" / "protein_sequence.parquet").exists()
    result = seqf.read_sequences(root, PROTEIN_TABLE).convert_dtypes(dtype_backend="pyarrow")
    assert result.loc[0, "feature_key"] == "protein_sequence|ENSP00000354587|Ensembl|ENSP00000354587|amino_acid"
    assert result.loc[0, "checksum_sha256"] == "dcf379a346fe4470a248ce8a8f7d7bfcd9b305e64bea9851254e579bf294ebf0"
    assert result.loc[0, "length"] == 10


def test_sequence_validation_rejects_node_type_endpoint_miss_and_bad_alphabet() -> None:
    bad_type = _sample_protein_df()
    bad_type.loc[0, "node_type"] = "gene"
    with pytest.raises(ValueError, match="invalid node_type"):
        seqf.validate_sequences(bad_type, PROTEIN_TABLE)

    with pytest.raises(ValueError, match="node_ids not present"):
        seqf.validate_sequences(_sample_protein_df(), PROTEIN_TABLE, endpoint_node_ids={"ENSP00000000000"})

    bad_alphabet = _sample_protein_df()
    bad_alphabet.loc[0, "sequence"] = "MEEPQSDPSV*"
    with pytest.raises(ValueError, match="invalid protein_iupac sequence"):
        seqf.validate_sequences(bad_alphabet, PROTEIN_TABLE)


def test_sequence_validation_rejects_empty_oversized_and_deduplicates(tmp_path: Path) -> None:
    empty = _sample_protein_df()
    empty.loc[0, "sequence"] = ""
    with pytest.raises(ValueError, match="empty sequence"):
        seqf.validate_sequences(empty, PROTEIN_TABLE)

    oversized = _sample_protein_df()
    oversized.loc[0, "sequence"] = "M" * 6
    with pytest.raises(ValueError, match="over max_sequence_length"):
        seqf.validate_sequences(oversized, PROTEIN_TABLE, max_sequence_length=5)

    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    updated = _sample_protein_df()
    updated.loc[0, "sequence"] = "MEEPQSDPSA"
    seqf.write_sequences(root, PROTEIN_TABLE, _sample_protein_df())
    validation = seqf.write_sequences(root, PROTEIN_TABLE, updated, mode="append")
    result = seqf.read_sequences(root, PROTEIN_TABLE)
    assert validation.duplicate_rows_removed == 1
    assert len(result) == 1
    assert result.loc[0, "sequence"] == "MEEPQSDPSA"


def test_fixture_build_maps_fasta_records_to_existing_nodes_and_reports(tmp_path: Path) -> None:
    kg_root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    kg_storage.write_nodes(
        kg_root,
        "protein",
        pd.DataFrame(
            {
                "id": ["ENSP00000354587"],
                "ensembl_gene_id": ["ENSG00000141510"],
                "uniprot_id": ["P04637"],
                "refseq_protein": ["NP_000537"],
                "pdb_ids": [""],
            }
        ),
    )
    kg_storage.write_nodes(
        kg_root,
        "transcript",
        pd.DataFrame(
            {
                "id": ["ENST00000269305"],
                "ensembl_gene_id": ["ENSG00000141510"],
                "protein_id": ["ENSP00000354587"],
                "refseq_mrna": ["NM_000546"],
                "ccds_id": ["CCDS11118"],
            }
        ),
    )

    protein_fasta = tmp_path / "protein.fa"
    protein_fasta.write_text(
        ">ENSP00000354587.4 pep chromosome:GRCh38:17:7661779:7687550:1 gene:ENSG00000141510 transcript:ENST00000269305\nMEEPQSDPSV\n"
        ">ENSP99999999999.1 pep chromosome:GRCh38:1:1:9:1 gene:ENSG99999999999 transcript:ENST99999999999\nMAAAAA\n"
    )
    transcript_fasta = tmp_path / "transcript.fa"
    transcript_fasta.write_text(
        ">ENST00000269305.9 cdna chromosome:GRCh38:17:7661779:7687550:1 gene:ENSG00000141510\nACGTACGTNN\n"
    )

    out_root = tmp_path / "staged"
    report = build_sequence_feature_tables(
        kg_root_uri=str(tmp_path / "kg"),
        output_root_uri=str(out_root),
        protein_fasta=protein_fasta,
        transcript_fasta=transcript_fasta,
        source_release="Ensembl release 114 fixture",
        created_at="2026-06-22T00:00:00+00:00",
    )

    assert report["protein_sequence"]["rows"] == 1
    assert report["protein_sequence"]["source_records_seen"] == 2
    assert report["protein_sequence"]["source_records_unmapped"] == 1
    assert report["transcript_sequence"]["rows"] == 1
    assert (out_root / "features" / "protein_sequence.parquet").exists()
    assert (out_root / "reports" / "sequence_feature_report.json").exists()
    protein = pd.read_parquet(out_root / "features" / "protein_sequence.parquet")
    assert protein.loc[0, "node_id"] == "ENSP00000354587"
    assert protein.loc[0, "sequence_kind"] == "amino_acid"
    transcript = pd.read_parquet(out_root / "features" / "transcript_sequence.parquet")
    assert transcript.loc[0, "alphabet"] == "dna_iupac"
