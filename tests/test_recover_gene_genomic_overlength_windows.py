from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from manage_db.build_gene_genomic_sequence_features import INTERVAL_COLUMNS, SEQUENCE_COLUMNS
from manage_db.recover_gene_genomic_overlength_windows import build_recovered_sequence_source


def _schema(columns):
    return pa.schema([pa.field(name, typ, nullable=True) for name, typ in columns])


def test_recovery_appends_only_missing_interval_ids_with_gene_strand_prefix(tmp_path: Path) -> None:
    interval_rows = [
        {
            "feature_key": "interval|ENSG1",
            "feature_table": "gene_genomic_interval",
            "node_id": "ENSG1",
            "node_type": "gene",
            "sequence_kind": "genomic_locus_interval",
            "chromosome": "1",
            "start_1based": 1,
            "end_1based": 12,
            "strand": "-",
            "length": 12,
            "reference_build": "GRCh38.primary_assembly",
            "source": "Ensembl",
            "source_dataset": "fixture",
            "source_record_id": "ENSG1",
            "source_record_version": "1",
            "source_release": "Ensembl 114",
            "gene_name": "G1",
            "gene_biotype": "protein_coding",
            "provenance": "fixture",
            "license": "open",
            "citation": "fixture",
            "created_at": "2026-07-22T00:00:00Z",
            "coordinate_sha256": "x",
        }
    ]
    interval = tmp_path / "interval.parquet"
    pq.write_table(pa.Table.from_pylist(interval_rows, schema=_schema(INTERVAL_COLUMNS)), interval)
    original = tmp_path / "original.parquet"
    pq.write_table(pa.Table.from_pylist([], schema=_schema(SEQUENCE_COLUMNS)), original)
    fasta = tmp_path / "genome.fa"
    fasta.write_text(">1\nAACCGGTTAACC\n")
    output = tmp_path / "merged.parquet"

    report = build_recovered_sequence_source(
        original_sequence_path=original,
        interval_path=interval,
        fasta_path=fasta,
        output_path=output,
        window_size=4,
    )

    table = pq.read_table(output)
    assert table["node_id"].to_pylist() == ["ENSG1"]
    assert table["sequence"].to_pylist() == ["GGTT"]
    assert table["length"].to_pylist() == [4]
    assert report["recovered_rows"] == 1
    assert report["merged_rows"] == 1
