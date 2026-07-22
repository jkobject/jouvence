from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from manage_db.build_gene_genomic_sequence_features import (
    GENE_SEQUENCE_TABLE,
    SEQUENCE_COLUMNS,
    GeneCoordinate,
    _feature_key,
    _schema,
    extract_bounded_gene_strand_sequences,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_recovered_sequence_source(
    *,
    original_sequence_path: Path,
    interval_path: Path,
    fasta_path: Path,
    output_path: Path,
    window_size: int = 1000,
) -> dict[str, Any]:
    original = pq.read_table(original_sequence_path)
    original_ids = {str(value) for value in original["node_id"].to_pylist()}
    interval = pq.read_table(interval_path)
    recovery_rows = [
        row
        for row in interval.to_pylist()
        if str(row["node_id"]) not in original_ids
    ]
    recovery_rows.sort(key=lambda row: str(row["node_id"]))
    coordinates = [
        GeneCoordinate(
            node_id=str(row["node_id"]),
            chromosome=str(row["chromosome"]),
            start_1based=int(row["start_1based"]),
            end_1based=int(row["end_1based"]),
            strand=str(row["strand"]),
            source_record_id=str(row["source_record_id"]),
            source_record_version=str(row.get("source_record_version") or ""),
            gene_name=str(row.get("gene_name") or ""),
            gene_biotype=str(row.get("gene_biotype") or ""),
        )
        for row in recovery_rows
    ]
    sequences = extract_bounded_gene_strand_sequences(
        fasta_path, coordinates, window_size=window_size
    )
    recovered: list[dict[str, Any]] = []
    for row, coordinate in zip(recovery_rows, coordinates, strict=True):
        sequence = sequences[coordinate.node_id]
        recovered.append(
            {
                "feature_key": _feature_key(
                    GENE_SEQUENCE_TABLE,
                    coordinate.node_id,
                    str(row["source"]),
                    str(row["source_dataset"]),
                    coordinate.source_record_id,
                    str(row["reference_build"]),
                    "genomic_locus",
                ),
                "feature_table": GENE_SEQUENCE_TABLE,
                "node_id": coordinate.node_id,
                "node_type": "gene",
                "sequence_kind": "genomic_locus",
                "sequence": sequence,
                "length": len(sequence),
                "alphabet": "dna_iupac",
                "chromosome": coordinate.chromosome,
                "start_1based": coordinate.start_1based,
                "end_1based": coordinate.end_1based,
                "strand": coordinate.strand,
                "reference_build": row["reference_build"],
                "source": row["source"],
                "source_dataset": row["source_dataset"],
                "source_record_id": coordinate.source_record_id,
                "source_record_version": coordinate.source_record_version,
                "source_release": row["source_release"],
                "gene_name": coordinate.gene_name,
                "gene_biotype": coordinate.gene_biotype,
                "provenance": str(row["provenance"]) + f";bounded_gene_strand_prefix={window_size}",
                "license": row["license"],
                "citation": row["citation"],
                "created_at": row["created_at"],
                "checksum_sha256": hashlib.sha256(sequence.encode("ascii")).hexdigest(),
            }
        )
    recovered_table = pa.Table.from_pylist(recovered, schema=_schema(SEQUENCE_COLUMNS))
    merged = pa.concat_tables([original, recovered_table])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(merged, output_path, compression="zstd")
    return {
        "original_rows": original.num_rows,
        "recovered_rows": len(recovered),
        "merged_rows": merged.num_rows,
        "recovered_node_ids": [row["node_id"] for row in recovered],
        "window_size": window_size,
        "original_sha256": _sha256(original_sequence_path),
        "interval_sha256": _sha256(interval_path),
        "fasta_sha256": _sha256(fasta_path),
        "output_sha256": _sha256(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-sequence", type=Path, required=True)
    parser.add_argument("--interval", type=Path, required=True)
    parser.add_argument("--fasta", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--window-size", type=int, default=1000)
    args = parser.parse_args()
    report = build_recovered_sequence_source(
        original_sequence_path=args.original_sequence,
        interval_path=args.interval,
        fasta_path=args.fasta,
        output_path=args.output,
        window_size=args.window_size,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
