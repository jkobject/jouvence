from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from manage_db import kg_gene_interval_features as gif
from manage_db import kg_molecule_fingerprint_features as mff
from manage_db import kg_storage
from manage_db.build_node_missing_features import stage_node_missing_features


def _sample_fingerprint_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "feature_table": [mff.MOLECULE_FINGERPRINT_TABLE],
            "node_id": ["CHEMBL25"],
            "node_type": ["molecule"],
            "fingerprint_kind": ["morgan_binary"],
            "fingerprint_format": ["sparse_on_bits_uint16_list"],
            "on_bits": [[1, 7, 1024]],
            "n_bits": [2048],
            "radius": [2],
            "use_chirality": [True],
            "use_bond_types": [True],
            "input_smiles": ["CC(=O)Oc1ccccc1C(=O)O"],
            "canonical_smiles_rdkit": ["CC(=O)Oc1ccccc1C(=O)O"],
            "input_smiles_field": ["nodes/molecule.parquet.smiles"],
            "inchikey": ["BSYNRYMUTXBXSQ-UHFFFAOYSA-N"],
            "source": ["ChEMBL/OpenTargets"],
            "source_dataset": ["fixture molecule nodes"],
            "source_record_id": ["CHEMBL25"],
            "source_release": ["fixture"],
            "rdkit_version": ["fixture-rdkit"],
            "invalid_smiles_policy": ["skip_with_report"],
            "salt_mixture_policy": ["fingerprint_input_as_is_record_component_count"],
            "component_count": [1],
            "provenance": ["fixture nodes/molecule.parquet::smiles"],
            "license": ["fixture license"],
            "citation": ["fixture citation"],
            "created_at": ["2026-06-23T00:00:00+00:00"],
        }
    )


def _sample_interval_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "feature_table": [gif.GENE_INTERVAL_TABLE],
            "node_id": ["NCBI:7157"],
            "node_type": ["gene"],
            "sequence_kind": ["genomic_locus_coordinates_only"],
            "chromosome": ["17"],
            "start_1based": [7661779],
            "end_1based": [7687550],
            "strand": ["-"],
            "reference_build": ["GRCh38"],
            "source": ["Ensembl"],
            "source_dataset": ["fixture.gtf"],
            "source_record_id": ["ENSG00000141510"],
            "source_release": ["fixture"],
            "provenance": ["fixture.gtf::gene"],
            "license": ["EMBL-EBI open data / attribution"],
            "citation": ["fixture citation"],
            "created_at": ["2026-06-23T00:00:00+00:00"],
        }
    )


def test_molecule_fingerprint_roundtrip_and_checksum(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    validation = mff.write_molecule_fingerprints(root, _sample_fingerprint_df(), endpoint_node_ids={"CHEMBL25"})

    assert validation.rows == 1
    assert validation.unique_nodes == 1
    assert validation.min_on_bits == 3
    assert (tmp_path / "kg" / "features" / "molecule_fingerprint.parquet").exists()
    result = mff.read_molecule_fingerprints(root)
    assert result.loc[0, "feature_key"] == "molecule_fingerprint|CHEMBL25|ChEMBL/OpenTargets|CHEMBL25|morgan_binary|2|2048|True"
    assert result.loc[0, "fingerprint_sha256"] == mff.fingerprint_sha256(
        [1, 7, 1024],
        fingerprint_kind="morgan_binary",
        radius=2,
        n_bits=2048,
        use_chirality=True,
        use_bond_types=True,
    )


def test_molecule_fingerprint_validation_rejects_empty_out_of_range_and_endpoint() -> None:
    empty = _sample_fingerprint_df()
    empty.at[0, "on_bits"] = []
    with pytest.raises(ValueError, match="empty/all-zero"):
        mff.validate_molecule_fingerprints(empty)

    out_of_range = _sample_fingerprint_df()
    out_of_range.at[0, "on_bits"] = [2048]
    with pytest.raises(ValueError, match="outside"):
        mff.validate_molecule_fingerprints(out_of_range)

    with pytest.raises(ValueError, match="node_ids not present"):
        mff.validate_molecule_fingerprints(_sample_fingerprint_df(), endpoint_node_ids={"CHEMBL999"})


def test_gene_interval_roundtrip_validation_and_rejects_raw_sequence(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    validation = gif.write_gene_intervals(root, _sample_interval_df(), endpoint_node_ids={"NCBI:7157"})

    assert validation.rows == 1
    assert validation.min_length == 25772
    assert validation.max_length == 25772
    result = gif.read_gene_intervals(root)
    assert "sequence" not in result.columns
    assert result.loc[0, "feature_key"] == "gene_genomic_interval|NCBI:7157|Ensembl|ENSG00000141510|GRCh38"

    bad = _sample_interval_df()
    bad.loc[0, "strand"] = "?"
    with pytest.raises(ValueError, match="invalid strand"):
        gif.validate_gene_intervals(bad)


def test_stage_node_missing_features_builds_fingerprints_and_gene_interval_fixture(tmp_path: Path) -> None:
    kg_root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    kg_storage.write_nodes(
        kg_root,
        "molecule",
        pd.DataFrame(
            {
                "id": ["CHEMBL25", "CHEMBL_MISSING", "CHEMBL_BAD", "CHEMBL_SALT"],
                "drugbank_id": ["", "", "", ""],
                "pubchem_cid": ["", "", "", ""],
                "cas_rn": ["", "", "", ""],
                "smiles": ["CC(=O)Oc1ccccc1C(=O)O", "", "not_a_smiles", "CCO.Cl"],
                "inchikey": ["BSYNRYMUTXBXSQ-UHFFFAOYSA-N", "", "", ""],
            }
        ),
    )
    kg_storage.write_nodes(
        kg_root,
        "gene",
        pd.DataFrame(
            {
                "id": ["NCBI:7157", "NCBI:0000"],
                "ncbi_gene_id": ["7157", "0000"],
                "hgnc_id": ["HGNC:11998", ""],
                "uniprot_id": ["P04637", ""],
                "gene_name": ["TP53", "UNMAPPED"],
                "name": ["TP53", "UNMAPPED"],
                "description": ["tumor protein p53", ""],
                "biotype": ["protein_coding", "protein_coding"],
            }
        ),
    )
    gtf = tmp_path / "genes.gtf"
    gtf.write_text(
        '17\tEnsembl\tgene\t7661779\t7687550\t.\t-\t.\tgene_id "ENSG00000141510.19"; gene_name "TP53";\n'
        '1\tEnsembl\tgene\t1\t10\t.\t+\t.\tgene_id "ENSG00000999999.1"; gene_name "MISS";\n',
        encoding="utf-8",
    )
    mapping = tmp_path / "gene_map.csv"
    mapping.write_text("source_gene_id,node_id\nENSG00000141510,NCBI:7157\n", encoding="utf-8")

    output = tmp_path / "staged"
    summary = stage_node_missing_features(
        kg_root_uri=str(tmp_path / "kg"),
        output_root_uri=str(output),
        source_release="fixture_release",
        created_at="2026-06-23T00:00:00+00:00",
        gene_gtf=str(gtf),
        gene_id_map_csv=str(mapping),
        max_rows=None,
    )

    assert summary["staging_only"] is True
    assert summary["canonical_promotion"] is False
    assert summary["edges_written"] is False
    assert summary["evidence_written"] is False
    assert summary["raw_gene_sequence_written"] is False
    assert summary["tables"]["molecule_fingerprint"]["rows"] == 2
    assert summary["tables"]["molecule_fingerprint"]["missing_smiles"] == 1
    assert summary["tables"]["molecule_fingerprint"]["invalid_smiles"] == 1
    assert summary["tables"]["molecule_fingerprint"]["multi_component_rows"] == 1
    assert summary["tables"]["gene_genomic_interval"]["rows"] == 1
    assert summary["tables"]["gene_genomic_interval"]["source_records_unmapped"] == 1
    assert (output / "features" / "molecule_fingerprint.parquet").exists()
    assert (output / "features" / "gene_genomic_interval.parquet").exists()
    assert (output / "reports" / "node_missing_features_summary.json").exists()
    assert (output / "reports" / "molecule_fingerprint_invalid_smiles.csv").exists()

    fingerprints = pd.read_parquet(output / "features" / "molecule_fingerprint.parquet")
    assert set(fingerprints["node_id"]) == {"CHEMBL25", "CHEMBL_SALT"}
    assert all(len(bits) > 0 for bits in fingerprints["on_bits"])
    intervals = pd.read_parquet(output / "features" / "gene_genomic_interval.parquet")
    assert intervals.loc[0, "node_id"] == "NCBI:7157"
    assert intervals.loc[0, "source_record_id"] == "ENSG00000141510"
    report = json.loads((output / "reports" / "node_missing_features_summary.json").read_text())
    assert report["tables"]["molecule_fingerprint"]["fingerprint_parameters"]["use_chirality"] is True


def test_stage_node_missing_features_without_gene_source_defers_interval_without_placeholder(tmp_path: Path) -> None:
    kg_root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    kg_storage.write_nodes(
        kg_root,
        "molecule",
        pd.DataFrame(
            {"id": ["CHEMBL25"], "drugbank_id": [""], "pubchem_cid": [""], "cas_rn": [""], "smiles": ["CCO"], "inchikey": [""]}
        ),
    )
    summary = stage_node_missing_features(
        kg_root_uri=str(tmp_path / "kg"),
        output_root_uri=str(tmp_path / "staged"),
        source_release="fixture_release",
        created_at="2026-06-23T00:00:00+00:00",
    )
    assert summary["tables"]["gene_genomic_interval"]["deferred"] is True
    assert not (tmp_path / "staged" / "features" / "gene_genomic_interval.parquet").exists()
