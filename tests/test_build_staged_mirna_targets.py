from __future__ import annotations

from pathlib import Path
import json

import pandas as pd


def test_staged_mirna_builder_aliases_nodes_and_target_policy(tmp_path: Path) -> None:
    from manage_db.build_staged_mirna_targets import build_staged_mirna_targets

    transcript_nodes = tmp_path / "transcript.parquet"
    pd.DataFrame(
        [
            {"id": "ENST00000000001", "name": "ENST00000000001", "ensembl_gene_id": "ENSG00000000001"},
            {"id": "ENST00000000002", "name": "ENST00000000002", "ensembl_gene_id": "ENSG00000000002"},
        ]
    ).to_parquet(transcript_nodes, index=False)

    gene_nodes = tmp_path / "gene.parquet"
    pd.DataFrame(
        [
            {"id": "ENSG00000999999", "name": "SOURCEBACKED1"},
            {"id": "ENSG00000000002", "name": "SOURCEBACKED2"},
        ]
    ).to_parquet(gene_nodes, index=False)

    source_audit = tmp_path / "source_audit.json"
    source_audit.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "miRBase/RNAcentral mapping sample",
                        "approval_status": "approved",
                        "license_checked": True,
                        "schema_checked": True,
                        "release": "miRBase-test22/RNAcentral-test",
                    },
                    {
                        "name": "miRTarBase target sample",
                        "approval_status": "recommended",
                        "license_checked": True,
                        "schema_checked": True,
                        "release": "miRTarBase-test",
                    },
                    {
                        "name": "DIANA-TarBase target sample",
                        "approval_status": "defer",
                        "license_checked": False,
                        "schema_checked": False,
                        "release": "TarBase-test",
                    },
                ]
            }
        )
    )

    mapping = tmp_path / "mapping.parquet"
    pd.DataFrame(
        [
            {
                "ensembl_transcript_id": "ENST00000000001",
                "ensembl_gene_id": "ENSG00000000001",
                "mirbase_accession": "MI0000001",
                "mirbase_name": "hsa-mir-test-1",
                "mirbase_entity_type": "precursor_hairpin",
                "rnacentral_id": "URS000001",
                "mapping_method": "source_xref",
                "mapping_confidence": "exact",
                "source_dataset": "miRBase",
                "source_release": "test22",
                "source_record_id": "xref-1",
                "species_id": "NCBITaxon:9606",
                "is_same_entity_as_transcript": True,
            },
            {
                "ensembl_transcript_id": "ENST00000000001",
                "ensembl_gene_id": "ENSG00000000001",
                "mirbase_accession": "MIMAT0000001",
                "mirbase_name": "hsa-miR-test-1-5p",
                "mirbase_entity_type": "mature",
                "mirbase_mature_accession": "MIMAT0000001",
                "mirbase_mature_name": "hsa-miR-test-1-5p",
                "mirbase_precursor_accession": "MI0000001",
                "mirbase_precursor_name": "hsa-mir-test-1",
                "mapping_method": "source_record",
                "mapping_confidence": "exact",
                "source_dataset": "miRBase",
                "source_release": "test22",
                "source_record_id": "mature-1",
                "species_id": "NCBITaxon:9606",
                "is_same_entity_as_transcript": False,
            },
            {
                "ensembl_transcript_id": "ENST_DOES_NOT_EXIST",
                "mirbase_accession": "MI9999999",
                "mirbase_name": "hsa-mir-reject",
                "mirbase_entity_type": "precursor_hairpin",
                "mapping_confidence": "exact",
                "is_same_entity_as_transcript": True,
            },
        ]
    ).to_parquet(mapping, index=False)

    targets = tmp_path / "targets.parquet"
    pd.DataFrame(
        [
            {
                "source": "miRTarBase",
                "source_dataset": "miRTarBase-test",
                "source_record_id": "mirtarbase-mti-gene",
                "mirna_id": "MIMAT0000001",
                "mirna_name": "hsa-miR-test-1-5p",
                "target_endpoint_level": "gene",
                "target_gene_id": "ENSG00000999999",
                "original_target_name": "GENE1",
                "assay": "reporter assay",
                "support_type": "functional_mti",
                "evidence_type": "experimental_validated",
                "license_checked": True,
                "pmid": "PMID:1",
                "species_id": "NCBITaxon:9606",
            },
            {
                "source": "DIANA-TarBase",
                "source_dataset": "DIANA-TarBase-test",
                "source_record_id": "tarbase-overlap-gene",
                "mirna_id": "MIMAT0000001",
                "mirna_name": "hsa-miR-test-1-5p",
                "target_endpoint_level": "gene",
                "target_gene_id": "ENSG00000999999",
                "original_target_name": "GENE1",
                "assay": "qPCR",
                "support_type": "functional_mti",
                "evidence_type": "experimental_validated",
                "pmid": "PMID:2",
                "species_id": "NCBITaxon:9606",
                "license_checked": True,
            },
            {
                "source": "miRTarBase",
                "source_dataset": "miRTarBase-test",
                "source_record_id": "missing-gene",
                "mirna_id": "MIMAT0000001",
                "target_endpoint_level": "gene",
                "target_gene_id": "ENSG_DOES_NOT_EXIST",
                "original_target_name": "MISSING",
                "license_checked": True,
            },
            {
                "source": "CustomTranscriptMTI",
                "source_dataset": "custom-transcript-sites",
                "source_record_id": "mti-tx",
                "mirna_id": "MIMAT0000001",
                "mirna_name": "hsa-miR-test-1-5p",
                "target_endpoint_level": "transcript",
                "target_transcript_id": "ENST00000000002",
                "target_region": "3UTR",
                "target_site_id": "site-1",
                "target_mapping_method": "source_native_endpoint",
                "target_mapping_confidence": "exact",
            },
            {
                "source": "BadProjection",
                "source_dataset": "bad-gene-to-transcript",
                "source_record_id": "bad-1",
                "mirna_id": "MIMAT0000001",
                "target_endpoint_level": "gene",
                "target_gene_id": "ENSG00000000002",
                "target_transcript_id": "ENST00000000002",
            },
        ]
    ).to_parquet(targets, index=False)

    out_dir = tmp_path / "staging"
    counts = build_staged_mirna_targets(
        transcript_nodes_path=transcript_nodes,
        transcript_mirbase_mapping_path=mapping,
        target_source_paths=[targets],
        output_dir=out_dir,
        gene_nodes_path=gene_nodes,
        source_audit_path=source_audit,
    )

    assert counts["alias_rows"] == 1
    assert counts["mirna_node_rows"] == 1
    assert counts["processing_edge_rows"] == 0
    assert counts["mirna_targets_gene_edges"] == 2  # overlapping TarBase row dedupes to one graph edge
    assert counts["mirna_targets_gene_evidence"] == 3
    assert counts["missing_gene_targets"] == 1
    assert counts["mirna_targets_transcript_edges"] == 1

    aliases = pd.read_parquet(out_dir / "mappings" / "transcript_mirbase_aliases.parquet")
    assert aliases.to_dict("records") == [
        {
            "ensembl_transcript_id": "ENST00000000001",
            "ensembl_gene_id": "ENSG00000000001",
            "mirbase_accession": "MI0000001",
            "mirbase_name": "hsa-mir-test-1",
            "mirbase_entity_type": "precursor_hairpin",
            "rnacentral_id": "URS000001",
            "mapping_method": "source_xref",
            "mapping_confidence": "exact",
            "source_dataset": "miRBase",
            "source_release": "test22",
            "source_record_id": "xref-1",
            "species_id": "NCBITaxon:9606",
            "notes_json": None,
        }
    ]

    nodes = pd.read_parquet(out_dir / "nodes" / "mirna.parquet")
    assert set(nodes["id"]) == {"MIMAT0000001"}
    assert nodes.iloc[0]["mirna_product_type"] == "mature"
    assert nodes.iloc[0]["mirbase_precursor_accession"] == "MI0000001"

    processing = pd.read_parquet(out_dir / "edges" / "mirna_precursor_produces_mature_mirna.parquet")
    assert processing.empty

    gene_edges = pd.read_parquet(out_dir / "edges" / "mirna_targets_gene.parquet")
    tx_edges = pd.read_parquet(out_dir / "edges" / "mirna_targets_transcript.parquet")
    assert set(gene_edges["y_type"]) == {"gene"}
    assert set(gene_edges["y_id"]) == {"ENSG00000999999", "ENSG00000000002"}
    assert set(tx_edges["y_type"]) == {"transcript"}
    assert set(tx_edges["y_id"]) == {"ENST00000000002"}

    gene_evidence = pd.read_parquet(out_dir / "evidence" / "mirna_targets_gene.parquet")
    assert "assay" in gene_evidence.columns
    assert gene_evidence.loc[gene_evidence["source_record_id"].eq("mirtarbase-mti-gene"), "assay"].iloc[0] == "reporter assay"
    assert gene_evidence.loc[gene_evidence["source_record_id"].eq("mirtarbase-mti-gene"), "pmid"].iloc[0] == "PMID:1"
    assert set(gene_evidence["source"]) >= {"miRTarBase", "DIANA-TarBase"}
    report = json.loads((out_dir / "reports" / "build_summary.json").read_text())
    assert report["source_gate"]["approved_for_staged_source_backed_sample"] is True
    assert report["source_gate"]["status"] == "approved"
    assert [src["name"] for src in report["source_gate"]["deferred_sources"]] == ["DIANA-TarBase target sample"]
    assert {src["name"] for src in report["source_gate"]["sources"]} == {
        "miRBase/RNAcentral mapping sample",
        "miRTarBase target sample",
    }
    assert report["endpoint_anti_joins"] == {
        "gene_targets_missing_from_gene_nodes": 1,
        "transcript_targets_missing_from_transcript_nodes": 0,
        "processing_edges_missing_x_mirna_nodes": 0,
        "processing_edges_missing_y_mirna_nodes": 0,
        "gene_nodes_checked": True,
        "transcript_nodes_checked": True,
        "mirna_nodes_checked": True,
    }


def test_staged_mirna_builder_rejects_non_one_to_one_aliases(tmp_path: Path) -> None:
    from manage_db.build_staged_mirna_targets import build_staged_mirna_targets

    transcript_nodes = tmp_path / "transcript.parquet"
    pd.DataFrame([{"id": "ENST1"}, {"id": "ENST2"}]).to_parquet(transcript_nodes, index=False)
    mapping = tmp_path / "mapping.parquet"
    pd.DataFrame(
        [
            {
                "ensembl_transcript_id": "ENST1",
                "mirbase_accession": "MI-DUP",
                "mirbase_name": "hsa-mir-dup",
                "mirbase_entity_type": "precursor_hairpin",
                "mapping_confidence": "exact",
                "is_same_entity_as_transcript": True,
            },
            {
                "ensembl_transcript_id": "ENST2",
                "mirbase_accession": "MI-DUP",
                "mirbase_name": "hsa-mir-dup",
                "mirbase_entity_type": "precursor_hairpin",
                "mapping_confidence": "exact",
                "is_same_entity_as_transcript": True,
            },
        ]
    ).to_parquet(mapping, index=False)
    counts = build_staged_mirna_targets(
        transcript_nodes_path=transcript_nodes,
        transcript_mirbase_mapping_path=mapping,
        output_dir=tmp_path / "staging",
    )
    assert counts["alias_rows"] == 0
    assert counts["rejected_alias_rows"] == 2
    rejected = pd.read_parquet(tmp_path / "staging" / "mappings" / "transcript_mirbase_aliases_rejected.parquet")
    assert len(rejected) == 2


def test_staged_mirna_builder_requires_existing_transcript_targets(tmp_path: Path) -> None:
    from manage_db.build_staged_mirna_targets import build_staged_mirna_targets

    transcript_nodes = tmp_path / "transcript.parquet"
    pd.DataFrame([{"id": "ENST1"}]).to_parquet(transcript_nodes, index=False)
    mapping = tmp_path / "mapping.parquet"
    pd.DataFrame(
        [
            {
                "mirbase_accession": "MIMAT1",
                "mirbase_name": "hsa-miR-test",
                "mirbase_entity_type": "mature",
                "mirbase_mature_accession": "MIMAT1",
                "mapping_confidence": "exact",
                "is_same_entity_as_transcript": False,
            }
        ]
    ).to_parquet(mapping, index=False)
    targets = tmp_path / "targets.parquet"
    pd.DataFrame(
        [
            {
                "mirna_id": "MIMAT1",
                "target_endpoint_level": "transcript",
                "target_transcript_id": "ENST_MISSING",
                "source": "Source",
                "source_dataset": "transcript-sites",
                "source_record_id": "missing-tx",
            }
        ]
    ).to_parquet(targets, index=False)

    counts = build_staged_mirna_targets(
        transcript_nodes_path=transcript_nodes,
        transcript_mirbase_mapping_path=mapping,
        target_source_paths=[targets],
        output_dir=tmp_path / "staging",
    )

    assert counts["mirna_targets_transcript_edges"] == 0
    assert counts["missing_transcript_targets"] == 1
    assert pd.read_parquet(tmp_path / "staging" / "edges" / "mirna_targets_transcript.parquet").empty
