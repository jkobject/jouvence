from __future__ import annotations

import argparse
import gzip
from pathlib import Path

import pandas as pd

from manage_db.stage_human_ensg_gene_migration import build


def _write_gzip(path: Path, text: str) -> None:
    with gzip.open(path, "wt") as handle:
        handle.write(text)


def test_builds_human_only_candidate_and_quarantines_unmapped_rows(tmp_path: Path) -> None:
    source = tmp_path / "source"
    for directory in ("nodes", "edges", "evidence"):
        (source / directory).mkdir(parents=True)
    pd.DataFrame(
        [
            {"id": "ENSG00000141510", "ncbi_gene_id": None, "gene_name": "TP53", "source": "OpenTargets"},
            {"id": "NCBI:7157", "ncbi_gene_id": "7157", "gene_name": "TP53", "source": "NCBI"},
            {"id": "NCBI:999", "ncbi_gene_id": "999", "gene_name": "OLD", "source": "NCBI"},
            {"id": "ENSMUSG00000059552", "ncbi_gene_id": None, "gene_name": "Trp53", "source": "OpenTargets/target.homologues"},
        ]
    ).to_parquet(source / "nodes" / "gene.parquet", index=False)
    pd.DataFrame([{"id": "MONDO:1"}]).to_parquet(source / "nodes" / "disease.parquet", index=False)
    pd.DataFrame(
        [
            {"x_id": "NCBI:7157", "x_type": "gene", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_gene", "source": "legacy", "credibility": 1},
            {"x_id": "ENSG00000141510", "x_type": "gene", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_gene", "source": "modern", "credibility": 2},
            {"x_id": "NCBI:999", "x_type": "gene", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_gene", "source": "legacy", "credibility": 1},
        ]
    ).to_parquet(source / "edges" / "disease_associated_gene.parquet", index=False)
    pd.DataFrame(
        [
            {"edge_key": "gene_ortholog_gene|ENSG00000141510|ENSMUSG00000059552", "x_id": "ENSG00000141510", "x_type": "gene", "y_id": "ENSMUSG00000059552", "y_type": "gene", "relation": "gene_ortholog_gene"}
        ]
    ).to_parquet(source / "edges" / "gene_ortholog_gene.parquet", index=False)
    pd.DataFrame(
        [
            {"edge_key": "disease_associated_gene|NCBI:7157|MONDO:1", "x_id": "NCBI:7157", "x_type": "gene", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_gene", "source": "NCBI", "source_dataset": "legacy", "source_record_id": "1"},
            {"edge_key": "disease_associated_gene|NCBI:999|MONDO:1", "x_id": "NCBI:999", "x_type": "gene", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_gene", "source": "NCBI", "source_dataset": "legacy", "source_record_id": "2"},
        ]
    ).to_parquet(source / "evidence" / "disease_associated_gene.parquet", index=False)

    gene2ensembl = tmp_path / "gene2ensembl.gz"
    history = tmp_path / "gene_history.gz"
    _write_gzip(gene2ensembl, "9606\t7157\tENSG00000141510\t-\t-\t-\t-\n")
    _write_gzip(history, "9606\t-\t999\tOLD\t20200101\n")
    output = tmp_path / "candidate"
    manifest = build(
        argparse.Namespace(
            source_root=source,
            output_root=output,
            gene2ensembl=gene2ensembl,
            gene_history=history,
        )
    )

    genes = pd.read_parquet(output / "nodes" / "gene.parquet")
    edges = pd.read_parquet(output / "edges" / "disease_associated_gene.parquet")
    evidence = pd.read_parquet(output / "evidence" / "disease_associated_gene.parquet")
    quarantined = pd.read_parquet(output / "quarantine" / "edges" / "disease_associated_gene.parquet")

    assert genes["id"].tolist() == ["ENSG00000141510"]
    assert genes.loc[0, "ncbi_gene_id"] == "7157"
    assert len(edges) == 1
    assert edges.loc[0, "x_id"] == "ENSG00000141510"
    assert edges.loc[0, "source"] == "modern"
    assert evidence.loc[0, "edge_key"] == "disease_associated_gene|ENSG00000141510|MONDO:1"
    assert evidence.loc[0, "canonicalization_source_x_id"] == "NCBI:7157"
    assert quarantined.loc[0, "x_id"] == "NCBI:999"
    assert not (output / "edges" / "gene_ortholog_gene.parquet").exists()
    assert manifest["validation"]["ok"] is True
    assert manifest["mapping"]["status_counts"] == {"accepted_1to1": 1, "retired_unmapped": 1}
