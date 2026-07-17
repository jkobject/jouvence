from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import pandas as pd

from manage_db import kg_storage
from manage_db.build_gene_genomic_sequence_features import build_gene_genomic_features


def _gzip_write(path: Path, text: str) -> None:
    with gzip.open(path, "wt") as handle:
        handle.write(text)


def test_gene_genomic_build_emits_interval_and_strand_oriented_sequence(tmp_path: Path) -> None:
    kg_root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    kg_storage.write_nodes(
        kg_root,
        "gene",
        pd.DataFrame(
            {
                "id": ["ENSG000001", "ENSG000002"],
                "ncbi_gene_id": ["1", "2"],
                "hgnc_id": ["HGNC:1", "HGNC:2"],
                "uniprot_id": ["", ""],
                "gene_name": ["GENE1", "GENE2"],
            }
        ),
    )
    gtf = tmp_path / "fixture.gtf.gz"
    _gzip_write(
        gtf,
        "\n".join(
            [
                '1\tEnsembl\tgene\t2\t6\t.\t+\t.\tgene_id "ENSG000001.7"; gene_version "7"; gene_name "GENE1"; gene_biotype "protein_coding";',
                '1\tEnsembl\tgene\t8\t11\t.\t-\t.\tgene_id "ENSG000002.3"; gene_version "3"; gene_name "GENE2"; gene_biotype "lncRNA";',
                '1\tEnsembl\tgene\t1\t4\t.\t+\t.\tgene_id "ENSG999999.1"; gene_name "UNMAPPED"; gene_biotype "protein_coding";',
            ]
        )
        + "\n",
    )
    fasta = tmp_path / "fixture.fa.gz"
    _gzip_write(fasta, ">1 dna:chromosome chromosome:GRCh38:1:1:12:1 REF\nAACCGGTTAACC\n")

    out = tmp_path / "staged"
    report = build_gene_genomic_features(
        kg_root_uri=str(tmp_path / "kg"),
        output_root_uri=str(out),
        gtf_path=gtf,
        fasta_path=fasta,
        source_release="Ensembl release fixture",
        created_at="2026-06-25T00:00:00+00:00",
    )

    assert report["mapped_interval_rows"] == 2
    assert report["gtf_gene_rows_unmapped_to_endpoint"] == 1
    assert report["sequence_rows_written"] == 2
    intervals = pd.read_parquet(out / "features" / "gene_genomic_interval.parquet")
    seqs = pd.read_parquet(out / "features" / "gene_genomic_sequence.parquet")
    assert intervals["feature_table"].unique().tolist() == ["gene_genomic_interval"]
    assert seqs.loc[seqs["node_id"] == "ENSG000001", "sequence"].item() == "ACCGG"
    # Minus-strand interval 8..11 is TAAC on reference; emitted in gene orientation as GTTA.
    assert seqs.loc[seqs["node_id"] == "ENSG000002", "sequence"].item() == "GTTA"
    assert seqs.loc[seqs["node_id"] == "ENSG000001", "checksum_sha256"].item() == hashlib.sha256(b"ACCGG").hexdigest()
    assert seqs.loc[seqs["node_id"] == "ENSG000001", "feature_key"].item().startswith(
        "gene_genomic_sequence|ENSG000001|Ensembl|Ensembl gene GTF + GRCh38 primary assembly FASTA|ENSG000001|GRCh38.primary_assembly|genomic_locus"
    )


def test_gene_genomic_build_skips_overlength_without_truncating(tmp_path: Path) -> None:
    kg_root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    kg_storage.write_nodes(
        kg_root,
        "gene",
        pd.DataFrame(
            {
                "id": ["ENSG000001"],
                "ncbi_gene_id": ["1"],
                "hgnc_id": ["HGNC:1"],
                "uniprot_id": [""],
                "gene_name": ["GENE1"],
            }
        ),
    )
    gtf = tmp_path / "fixture.gtf"
    gtf.write_text('1\tEnsembl\tgene\t1\t12\t.\t+\t.\tgene_id "ENSG000001.1"; gene_name "GENE1"; gene_biotype "protein_coding";\n')
    fasta = tmp_path / "fixture.fa"
    fasta.write_text(">1\nAACCGGTTAACC\n")

    out = tmp_path / "staged"
    report = build_gene_genomic_features(
        kg_root_uri=str(tmp_path / "kg"),
        output_root_uri=str(out),
        gtf_path=gtf,
        fasta_path=fasta,
        source_release="Ensembl release fixture",
        max_sequence_length=5,
        created_at="2026-06-25T00:00:00+00:00",
    )

    assert report["interval_rows_written"] == 1
    assert report["sequence_rows_written"] == 0
    assert report["sequence_rows_over_max_length_skipped"] == 1
    assert pd.read_parquet(out / "features" / "gene_genomic_sequence.parquet").empty
