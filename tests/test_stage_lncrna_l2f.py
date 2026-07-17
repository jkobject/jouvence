from __future__ import annotations

import gzip
import importlib.util
from pathlib import Path

import pandas as pd
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stage_lncrna_l2f.py"
if not SCRIPT.exists():
    pytest.skip(
        "historical lncRNA L2F stage implementation is not present in reviewable source",
        allow_module_level=True,
    )
spec = importlib.util.spec_from_file_location("stage_lncrna_l2f", SCRIPT)
stage = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(stage)


def write_gzip(path: Path, text: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(text)


def test_build_lncrna_nodes_from_gencode_gtf_preserves_transcript_evidence(tmp_path: Path) -> None:
    gtf = tmp_path / "tiny.gtf.gz"
    write_gzip(
        gtf,
        "chr1\tHAVANA\tgene\t10\t100\t.\t+\t.\tgene_id \"ENSG000001.7\"; gene_name \"LNC_A\"; gene_type \"lncRNA\";\n"
        "chr1\tHAVANA\ttranscript\t10\t60\t.\t+\t.\tgene_id \"ENSG000001.7\"; transcript_id \"ENST000001.2\"; gene_name \"LNC_A\"; gene_type \"lncRNA\"; transcript_type \"lncRNA\";\n"
        "chr1\tHAVANA\texon\t10\t20\t.\t+\t.\tgene_id \"ENSG000001.7\"; transcript_id \"ENST000001.2\"; gene_name \"LNC_A\";\n",
    )

    nodes, genes = stage.build_lncrna_nodes(gtf)

    assert len(nodes) == 1
    row = nodes.iloc[0]
    assert row["id"] == "ENST000001"
    assert row["ensembl_gene_id"] == "ENSG000001"
    assert row["gene_symbol"] == "LNC_A"
    assert row["source_record_id"] == "ENST000001"
    assert row["sequence_length"] == 51
    assert len(genes) == 1
    assert genes.iloc[0]["ensembl_gene_id"] == "ENSG000001"


def test_lncrnadisease_candidates_are_gated_without_license_review(tmp_path: Path) -> None:
    nodes = pd.DataFrame(
        [
            {
                "id": "ENST000001",
                "gene_symbol": "LNC_A",
                "ensembl_gene_id": "ENSG000001",
            }
        ]
    )
    disease_nodes = tmp_path / "disease.parquet"
    pd.DataFrame(
        [
            {
                "id": "MONDO:0000001",
                "name": "Test Disease",
                "mondo_id": "MONDO:0000001",
                "mesh_id": "",
                "omim_id": "",
                "doid_id": "",
            }
        ]
    ).to_parquet(disease_nodes, index=False)
    causal = tmp_path / "website_causal_data.tsv"
    pd.DataFrame(
        [
            {
                "ncRNA Symbol": "LNC_A",
                "ncRNA Category": "LncRNA",
                "Species": "Homo sapiens",
                "Disease Name": "Test Disease",
                "Sample": "cells",
                "Dysfunction Pattern": "up-regulated",
                "Validated Method": "qRT-PCR",
                "Description": "curated disease association",
                "Clinical Application": "",
                "Causality": "Yes",
                "Causal Description": "knockdown changed phenotype",
                "PubMed ID": "12345",
            }
        ]
    ).to_csv(causal, sep="\t", index=False)

    candidates, edges, rejected, stats = stage.build_disease_candidates(
        causal, nodes, disease_nodes, allow_unreviewed_edges=False
    )

    assert len(candidates) == 1
    assert len(edges) == 0
    assert len(rejected) == 1
    assert stats["active_edge_rows"] == 0
    rec = rejected.iloc[0]
    assert rec["pmid"] == "PMID:12345"
    assert rec["source_record_id"].startswith("LncRNADisease_v3:causal:")
    assert "license_or_source_review_gate_blocks_active_edges" in rec["reject_reasons"]
    assert bool(rec["association_not_regulation"]) is True


def test_lncrnadisease_active_edges_only_when_explicitly_allowed_and_endpoints_resolve(tmp_path: Path) -> None:
    nodes = pd.DataFrame([{"id": "ENST000001", "gene_symbol": "LNC_A"}])
    disease_nodes = tmp_path / "disease.parquet"
    pd.DataFrame([{"id": "MONDO:1", "name": "Disease X", "mondo_id": "MONDO:1"}]).to_parquet(
        disease_nodes, index=False
    )
    causal = tmp_path / "causal.tsv"
    pd.DataFrame(
        [
            {
                "ncRNA Symbol": "LNC_A",
                "ncRNA Category": "LncRNA",
                "Species": "Homo sapiens",
                "Disease Name": "Disease X",
                "Sample": "tissue",
                "Dysfunction Pattern": "down",
                "Validated Method": "RIP",
                "Description": "description",
                "Clinical Application": "",
                "Causality": "Yes",
                "Causal Description": "causal text",
                "PubMed ID": "999",
            }
        ]
    ).to_csv(causal, sep="\t", index=False)

    candidates, edges, rejected, stats = stage.build_disease_candidates(
        causal, nodes, disease_nodes, allow_unreviewed_edges=True
    )

    assert len(candidates) == 1
    assert len(edges) == 1
    assert len(rejected) == 0
    assert stats["active_edge_rows"] == 1
    edge = edges.iloc[0]
    assert edge["relation"] == "lncrna_associated_disease"
    assert edge["x_id"] == "ENST000001"
    assert edge["y_id"] == "MONDO:1"
