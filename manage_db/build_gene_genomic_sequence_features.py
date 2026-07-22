"""Build staged gene genomic interval and sequence feature tables.

Gene genomic sequence is intentionally separate from transcript/cDNA sequence:
rows represent the reference genomic locus for a gene, including introns, using
pinned gene coordinates and a matching GRCh38 reference FASTA. The builder writes
only to a staging root supplied by the caller; it does not promote canonical KG
features.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .kg_storage import open_kg_root, read_nodes

_GTF_ATTR_RE = re.compile(r'\s*([^\s;]+)\s+"([^"]*)"\s*;?')
_ENSEMBL_GENE_VERSION_RE = re.compile(r"^(ENSG[0-9]+)(?:\.([0-9]+))?$")
_DNA_ALPHABET = set("ACGTRYSWKMBDHVN")
_COMPLEMENT = str.maketrans("ACGTRYSWKMBDHVNacgtryswkmbdhvn", "TGCAYRSWMKVHDBNtgcayrswmkvhdbn")

GENE_INTERVAL_TABLE = "gene_genomic_interval"
GENE_SEQUENCE_TABLE = "gene_genomic_sequence"

INTERVAL_COLUMNS: list[tuple[str, pa.DataType]] = [
    ("feature_key", pa.string()),
    ("feature_table", pa.string()),
    ("node_id", pa.string()),
    ("node_type", pa.string()),
    ("sequence_kind", pa.string()),
    ("chromosome", pa.string()),
    ("start_1based", pa.int64()),
    ("end_1based", pa.int64()),
    ("strand", pa.string()),
    ("length", pa.int64()),
    ("reference_build", pa.string()),
    ("source", pa.string()),
    ("source_dataset", pa.string()),
    ("source_record_id", pa.string()),
    ("source_record_version", pa.string()),
    ("source_release", pa.string()),
    ("gene_name", pa.string()),
    ("gene_biotype", pa.string()),
    ("provenance", pa.string()),
    ("license", pa.string()),
    ("citation", pa.string()),
    ("created_at", pa.string()),
    ("coordinate_sha256", pa.string()),
]

SEQUENCE_COLUMNS: list[tuple[str, pa.DataType]] = [
    ("feature_key", pa.string()),
    ("feature_table", pa.string()),
    ("node_id", pa.string()),
    ("node_type", pa.string()),
    ("sequence_kind", pa.string()),
    ("sequence", pa.string()),
    ("length", pa.int64()),
    ("alphabet", pa.string()),
    ("chromosome", pa.string()),
    ("start_1based", pa.int64()),
    ("end_1based", pa.int64()),
    ("strand", pa.string()),
    ("reference_build", pa.string()),
    ("source", pa.string()),
    ("source_dataset", pa.string()),
    ("source_record_id", pa.string()),
    ("source_record_version", pa.string()),
    ("source_release", pa.string()),
    ("gene_name", pa.string()),
    ("gene_biotype", pa.string()),
    ("provenance", pa.string()),
    ("license", pa.string()),
    ("citation", pa.string()),
    ("created_at", pa.string()),
    ("checksum_sha256", pa.string()),
]


@dataclass(frozen=True)
class GeneCoordinate:
    node_id: str
    chromosome: str
    start_1based: int
    end_1based: int
    strand: str
    source_record_id: str
    source_record_version: str
    gene_name: str
    gene_biotype: str

    @property
    def length(self) -> int:
        return self.end_1based - self.start_1based + 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open_text(path: str | os.PathLike[str]):
    p = Path(path)
    return gzip.open(p, "rt") if p.suffix == ".gz" else open(p, "rt")


def _parse_gtf_attributes(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        match = _GTF_ATTR_RE.match(part + ";")
        if match:
            attrs[match.group(1)] = match.group(2)
    return attrs


def _split_ensembl_gene_id(raw: str) -> tuple[str, str]:
    match = _ENSEMBL_GENE_VERSION_RE.match(raw.strip())
    if not match:
        return raw.strip(), ""
    return match.group(1), match.group(2) or ""


def _normalize_chromosome(chromosome: str) -> str:
    chrom = chromosome.strip()
    return chrom[3:] if chrom.startswith("chr") else chrom


def _feature_key(feature_table: str, node_id: str, source: str, source_dataset: str, source_record_id: str, reference_build: str, sequence_kind: str) -> str:
    return "|".join([feature_table, node_id, source, source_dataset, source_record_id, reference_build, sequence_kind])


def _coordinate_hash(coord: GeneCoordinate, reference_build: str, source_release: str) -> str:
    payload = "|".join(
        [
            coord.node_id,
            coord.chromosome,
            str(coord.start_1based),
            str(coord.end_1based),
            coord.strand,
            reference_build,
            source_release,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha256(path: str | os.PathLike[str], *, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def load_gene_coordinates_from_ensembl_gtf(
    gtf_path: str | os.PathLike[str],
    *,
    endpoint_node_ids: set[str],
    limit_rows: int | None = None,
    include_alt_contigs: bool = False,
) -> tuple[list[GeneCoordinate], dict[str, int]]:
    """Load gene rows from an Ensembl/GENCODE-style GTF and map to KG genes."""

    coords: list[GeneCoordinate] = []
    seen_source_ids: set[str] = set()
    stats = {
        "gtf_gene_rows_seen": 0,
        "gtf_gene_rows_mapped_to_endpoint": 0,
        "gtf_gene_rows_unmapped_to_endpoint": 0,
        "gtf_gene_rows_duplicate_source_id": 0,
        "gtf_gene_rows_alt_contig_skipped": 0,
    }
    with _open_text(gtf_path) as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] != "gene":
                continue
            stats["gtf_gene_rows_seen"] += 1
            chrom = _normalize_chromosome(fields[0])
            if not include_alt_contigs and ("." in chrom or chrom in {"MT"} or chrom.startswith("KI") or chrom.startswith("GL")):
                stats["gtf_gene_rows_alt_contig_skipped"] += 1
                continue
            attrs = _parse_gtf_attributes(fields[8])
            raw_gene_id = attrs.get("gene_id", "")
            gene_id, version = _split_ensembl_gene_id(raw_gene_id)
            if gene_id in seen_source_ids:
                stats["gtf_gene_rows_duplicate_source_id"] += 1
                continue
            seen_source_ids.add(gene_id)
            if gene_id not in endpoint_node_ids:
                stats["gtf_gene_rows_unmapped_to_endpoint"] += 1
                continue
            coord = GeneCoordinate(
                node_id=gene_id,
                chromosome=chrom,
                start_1based=int(fields[3]),
                end_1based=int(fields[4]),
                strand=fields[6],
                source_record_id=gene_id,
                source_record_version=version or attrs.get("gene_version", ""),
                gene_name=attrs.get("gene_name", ""),
                gene_biotype=attrs.get("gene_biotype", attrs.get("gene_type", "")),
            )
            coords.append(coord)
            stats["gtf_gene_rows_mapped_to_endpoint"] += 1
            if limit_rows is not None and len(coords) >= limit_rows:
                break
    return coords, stats


def classify_ensembl_gtf_gene_ids(
    gtf_path: str | os.PathLike[str], *, eligible_ids: set[str]
) -> dict[str, set[str]]:
    """Classify exact eligible IDs by measured Ensembl GTF presence and contig policy."""
    primary_ids: set[str] = set()
    excluded_contig_ids: set[str] = set()
    with _open_text(gtf_path) as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] != "gene":
                continue
            attrs = _parse_gtf_attributes(fields[8])
            gene_id, _version = _split_ensembl_gene_id(attrs.get("gene_id", ""))
            if gene_id not in eligible_ids:
                continue
            chrom = _normalize_chromosome(fields[0])
            if (
                "." in chrom
                or chrom == "MT"
                or chrom.startswith(("KI", "GL", "CHR_"))
            ):
                excluded_contig_ids.add(gene_id)
            else:
                primary_ids.add(gene_id)
    excluded_contig_ids -= primary_ids
    return {
        "primary_ids": primary_ids,
        "excluded_contig_ids": excluded_contig_ids,
        "absent_ids": eligible_ids - primary_ids - excluded_contig_ids,
    }


def extract_bounded_gene_strand_sequences(
    fasta_path: str | os.PathLike[str],
    coordinates: Iterable[GeneCoordinate],
    *,
    window_size: int,
) -> dict[str, str]:
    """Extract only the gene-strand prefix needed by the embedding policy."""
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    by_chrom: dict[str, list[GeneCoordinate]] = defaultdict(list)
    for coordinate in coordinates:
        by_chrom[coordinate.chromosome].append(coordinate)
    result: dict[str, str] = {}
    for chrom, chrom_sequence in _iter_fasta_contigs(fasta_path):
        for coordinate in by_chrom.get(chrom, []):
            width = min(coordinate.length, window_size)
            if coordinate.end_1based > len(chrom_sequence):
                raise ValueError(f"coordinate exceeds FASTA contig for {coordinate.node_id}")
            if coordinate.strand == "-":
                sequence = chrom_sequence[
                    coordinate.end_1based - width : coordinate.end_1based
                ]
                sequence = _reverse_complement(sequence)
            else:
                sequence = chrom_sequence[
                    coordinate.start_1based - 1 : coordinate.start_1based - 1 + width
                ]
            invalid = set(sequence) - _DNA_ALPHABET
            if invalid:
                raise ValueError(
                    f"invalid DNA alphabet for {coordinate.node_id}: {sorted(invalid)}"
                )
            result[coordinate.node_id] = sequence
    requested = {
        coordinate.node_id for values in by_chrom.values() for coordinate in values
    }
    missing = requested - set(result)
    if missing:
        raise ValueError(f"FASTA contig missing for selected genes: {sorted(missing)[:10]}")
    return result


def _interval_row(
    coord: GeneCoordinate,
    *,
    source: str,
    source_dataset: str,
    source_release: str,
    reference_build: str,
    provenance: str,
    license: str,
    citation: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "feature_key": _feature_key(GENE_INTERVAL_TABLE, coord.node_id, source, source_dataset, coord.source_record_id, reference_build, "genomic_locus_interval"),
        "feature_table": GENE_INTERVAL_TABLE,
        "node_id": coord.node_id,
        "node_type": "gene",
        "sequence_kind": "genomic_locus_interval",
        "chromosome": coord.chromosome,
        "start_1based": coord.start_1based,
        "end_1based": coord.end_1based,
        "strand": coord.strand,
        "length": coord.length,
        "reference_build": reference_build,
        "source": source,
        "source_dataset": source_dataset,
        "source_record_id": coord.source_record_id,
        "source_record_version": coord.source_record_version,
        "source_release": source_release,
        "gene_name": coord.gene_name,
        "gene_biotype": coord.gene_biotype,
        "provenance": provenance,
        "license": license,
        "citation": citation,
        "created_at": created_at,
        "coordinate_sha256": _coordinate_hash(coord, reference_build, source_release),
    }


def _sequence_row(
    coord: GeneCoordinate,
    sequence: str,
    *,
    source: str,
    source_dataset: str,
    source_release: str,
    reference_build: str,
    provenance: str,
    license: str,
    citation: str,
    created_at: str,
) -> dict[str, Any]:
    checksum = hashlib.sha256(sequence.encode("ascii")).hexdigest()
    return {
        "feature_key": _feature_key(GENE_SEQUENCE_TABLE, coord.node_id, source, source_dataset, coord.source_record_id, reference_build, "genomic_locus"),
        "feature_table": GENE_SEQUENCE_TABLE,
        "node_id": coord.node_id,
        "node_type": "gene",
        "sequence_kind": "genomic_locus",
        "sequence": sequence,
        "length": len(sequence),
        "alphabet": "dna_iupac",
        "chromosome": coord.chromosome,
        "start_1based": coord.start_1based,
        "end_1based": coord.end_1based,
        "strand": coord.strand,
        "reference_build": reference_build,
        "source": source,
        "source_dataset": source_dataset,
        "source_record_id": coord.source_record_id,
        "source_record_version": coord.source_record_version,
        "source_release": source_release,
        "gene_name": coord.gene_name,
        "gene_biotype": coord.gene_biotype,
        "provenance": provenance,
        "license": license,
        "citation": citation,
        "created_at": created_at,
        "checksum_sha256": checksum,
    }


def _schema(columns: list[tuple[str, pa.DataType]]) -> pa.Schema:
    return pa.schema([pa.field(name, typ, nullable=True) for name, typ in columns])


def _write_rows(path: Path, rows: Iterable[dict[str, Any]], columns: list[tuple[str, pa.DataType]], *, batch_size: int = 500) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = _schema(columns)
    names = [name for name, _ in columns]
    writer: pq.ParquetWriter | None = None
    batch: list[dict[str, Any]] = []
    count = 0
    try:
        for row in rows:
            batch.append({name: row.get(name) for name in names})
            if len(batch) >= batch_size:
                table = pa.Table.from_pylist(batch, schema=schema)
                if writer is None:
                    writer = pq.ParquetWriter(path, schema=schema, compression="zstd")
                writer.write_table(table)
                count += len(batch)
                batch = []
        if batch:
            table = pa.Table.from_pylist(batch, schema=schema)
            if writer is None:
                writer = pq.ParquetWriter(path, schema=schema, compression="zstd")
            writer.write_table(table)
            count += len(batch)
    finally:
        if writer is not None:
            writer.close()
    if writer is None:
        pq.write_table(pa.Table.from_pylist([], schema=schema), path, compression="zstd")
    return count


def _iter_fasta_contigs(fasta_path: str | os.PathLike[str]) -> Iterator[tuple[str, str]]:
    with _open_text(fasta_path) as handle:
        header: str | None = None
        chunks: list[str] = []
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield _normalize_chromosome(header.split()[0]), "".join(chunks).upper()
                header = line[1:]
                chunks = []
            else:
                chunks.append(line)
        if header is not None:
            yield _normalize_chromosome(header.split()[0]), "".join(chunks).upper()


def _reverse_complement(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)[::-1].upper()


def _copy_local_tree_to_gcs(local_root: str | os.PathLike[str], gcs_root_uri: str) -> None:
    if not gcs_root_uri.startswith("gs://"):
        raise ValueError(f"remote_output_root_uri must be gs://..., got {gcs_root_uri}")
    import fsspec

    fs, remote_path = fsspec.core.url_to_fs(gcs_root_uri.rstrip("/"))
    base = Path(local_root)
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        target = f"{remote_path.rstrip('/')}/{rel}"
        parent = os.path.dirname(target)
        if parent:
            fs.makedirs(parent, exist_ok=True)
        with open(path, "rb") as src, fs.open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)


def build_gene_genomic_features(
    *,
    kg_root_uri: str,
    output_root_uri: str,
    gtf_path: str | os.PathLike[str],
    fasta_path: str | os.PathLike[str],
    source_release: str,
    reference_build: str = "GRCh38.primary_assembly",
    source: str = "Ensembl",
    source_dataset: str = "Ensembl gene GTF + GRCh38 primary assembly FASTA",
    max_sequence_length: int = 500_000,
    limit_rows: int | None = None,
    created_at: str | None = None,
    remote_output_root_uri: str | None = None,
) -> dict[str, Any]:
    """Build staged gene interval and genomic-locus sequence feature tables."""

    created_at = created_at or _now_iso()
    output_root = Path(output_root_uri)
    features_dir = output_root / "features"
    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    kg_root = open_kg_root(kg_root_uri)
    endpoint_nodes = set(read_nodes(kg_root, "gene", columns=["id"])["id"].astype(str))
    coords, gtf_stats = load_gene_coordinates_from_ensembl_gtf(
        gtf_path,
        endpoint_node_ids=endpoint_nodes,
        limit_rows=limit_rows,
    )
    coords_by_chrom: dict[str, list[GeneCoordinate]] = defaultdict(list)
    for coord in coords:
        coords_by_chrom[coord.chromosome].append(coord)
    for chrom in coords_by_chrom:
        coords_by_chrom[chrom].sort(key=lambda c: (c.start_1based, c.end_1based, c.node_id))

    gtf_sha256 = _file_sha256(gtf_path)
    fasta_sha256 = _file_sha256(fasta_path)
    provenance = (
        f"gtf={gtf_path};gtf_sha256={gtf_sha256};"
        f"fasta={fasta_path};fasta_sha256={fasta_sha256};"
        "coordinate_system=GTF_1based_inclusive;sequence_orientation=gene_strand_reverse_complement_for_minus"
    )
    license = "EMBL-EBI open data / attribution"
    citation = "Ensembl Project; GRCh38 reference assembly via Ensembl release resources."

    interval_rows = (
        _interval_row(
            coord,
            source=source,
            source_dataset=source_dataset,
            source_release=source_release,
            reference_build=reference_build,
            provenance=provenance,
            license=license,
            citation=citation,
            created_at=created_at,
        )
        for coord in coords
    )
    interval_rows_written = _write_rows(features_dir / f"{GENE_INTERVAL_TABLE}.parquet", interval_rows, INTERVAL_COLUMNS)

    stats: dict[str, Any] = {
        **gtf_stats,
        "endpoint_gene_nodes": len(endpoint_nodes),
        "mapped_interval_rows": len(coords),
        "mapped_interval_unique_nodes": len({c.node_id for c in coords}),
        "interval_endpoint_anti_join_rows": len({c.node_id for c in coords}.difference(endpoint_nodes)),
        "max_sequence_length": max_sequence_length,
        "sequence_rows_over_max_length_skipped": 0,
        "sequence_rows_missing_fasta_contig_skipped": 0,
        "sequence_rows_invalid_alphabet_skipped": 0,
        "sequence_rows_written": 0,
        "sequence_unique_nodes": 0,
        "sequence_min_length": None,
        "sequence_max_length": None,
        "sequence_total_bases": 0,
        "fasta_contigs_seen": 0,
        "fasta_contigs_used": 0,
        "gtf_sha256": gtf_sha256,
        "fasta_sha256": fasta_sha256,
        "source_release": source_release,
        "reference_build": reference_build,
        "sequence_policy": "emit full gene locus including introns in gene-strand orientation; skip loci above max_sequence_length; no truncation",
    }

    sequence_path = features_dir / f"{GENE_SEQUENCE_TABLE}.parquet"
    sequence_schema = _schema(SEQUENCE_COLUMNS)
    writer: pq.ParquetWriter | None = None
    emitted_nodes: set[str] = set()
    batch: list[dict[str, Any]] = []
    try:
        for chrom, chrom_sequence in _iter_fasta_contigs(fasta_path):
            stats["fasta_contigs_seen"] += 1
            chrom_coords = coords_by_chrom.get(chrom, [])
            if not chrom_coords:
                continue
            stats["fasta_contigs_used"] += 1
            for coord in chrom_coords:
                if coord.length > max_sequence_length:
                    stats["sequence_rows_over_max_length_skipped"] += 1
                    continue
                if coord.end_1based > len(chrom_sequence):
                    stats["sequence_rows_missing_fasta_contig_skipped"] += 1
                    continue
                seq = chrom_sequence[coord.start_1based - 1 : coord.end_1based]
                if coord.strand == "-":
                    seq = _reverse_complement(seq)
                if set(seq) - _DNA_ALPHABET:
                    stats["sequence_rows_invalid_alphabet_skipped"] += 1
                    continue
                batch.append(
                    _sequence_row(
                        coord,
                        seq,
                        source=source,
                        source_dataset=source_dataset,
                        source_release=source_release,
                        reference_build=reference_build,
                        provenance=provenance,
                        license=license,
                        citation=citation,
                        created_at=created_at,
                    )
                )
                emitted_nodes.add(coord.node_id)
                stats["sequence_total_bases"] += len(seq)
                stats["sequence_min_length"] = len(seq) if stats["sequence_min_length"] is None else min(stats["sequence_min_length"], len(seq))
                stats["sequence_max_length"] = len(seq) if stats["sequence_max_length"] is None else max(stats["sequence_max_length"], len(seq))
                if len(batch) >= 100:
                    table = pa.Table.from_pylist(batch, schema=sequence_schema)
                    if writer is None:
                        sequence_path.parent.mkdir(parents=True, exist_ok=True)
                        writer = pq.ParquetWriter(sequence_path, schema=sequence_schema, compression="zstd")
                    writer.write_table(table)
                    stats["sequence_rows_written"] += len(batch)
                    batch = []
        if batch:
            table = pa.Table.from_pylist(batch, schema=sequence_schema)
            if writer is None:
                sequence_path.parent.mkdir(parents=True, exist_ok=True)
                writer = pq.ParquetWriter(sequence_path, schema=sequence_schema, compression="zstd")
            writer.write_table(table)
            stats["sequence_rows_written"] += len(batch)
    finally:
        if writer is not None:
            writer.close()
    if writer is None:
        sequence_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist([], schema=sequence_schema), sequence_path, compression="zstd")

    coords_on_missing_contigs = set(coords_by_chrom)
    for chrom, _seq in _iter_fasta_contigs(fasta_path):
        coords_on_missing_contigs.discard(chrom)
    missing_contig_rows = sum(len(coords_by_chrom[chrom]) for chrom in coords_on_missing_contigs)
    stats["sequence_rows_missing_fasta_contig_skipped"] += missing_contig_rows
    stats["missing_fasta_contigs_with_coordinates"] = sorted(coords_on_missing_contigs)
    stats["sequence_unique_nodes"] = len(emitted_nodes)
    stats["sequence_endpoint_anti_join_rows"] = len(emitted_nodes.difference(endpoint_nodes))
    stats["interval_rows_written"] = interval_rows_written
    stats["interval_path"] = str(features_dir / f"{GENE_INTERVAL_TABLE}.parquet")
    stats["sequence_path"] = str(sequence_path)

    if len(coords) > 0:
        lengths = pd.Series([c.length for c in coords], dtype="int64")
        stats["interval_length_summary"] = {
            "min": int(lengths.min()),
            "p50": float(lengths.quantile(0.50)),
            "p90": float(lengths.quantile(0.90)),
            "p95": float(lengths.quantile(0.95)),
            "p99": float(lengths.quantile(0.99)),
            "max": int(lengths.max()),
        }
        stats["interval_rows_by_biotype_top20"] = dict(pd.Series([c.gene_biotype or "" for c in coords]).value_counts().head(20).astype(int))

    report_path = reports_dir / "gene_genomic_sequence_feature_report.json"
    report_path.write_text(json.dumps(stats, indent=2, sort_keys=True, default=_json_default))

    if remote_output_root_uri is not None:
        _copy_local_tree_to_gcs(output_root, remote_output_root_uri)
        stats["remote_output_root_uri"] = remote_output_root_uri
        report_path.write_text(json.dumps(stats, indent=2, sort_keys=True, default=_json_default))

    return stats


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kg-root", required=True, help="Read-only KG root containing nodes/gene.parquet")
    parser.add_argument("--output-root", required=True, help="Staging root to write features/*.parquet and reports/*.json")
    parser.add_argument("--gtf", required=True, help="Ensembl/GENCODE GTF path (.gtf or .gtf.gz)")
    parser.add_argument("--fasta", required=True, help="Matching GRCh38 reference FASTA path (.fa or .fa.gz)")
    parser.add_argument("--source-release", required=True, help="Source release label, e.g. Ensembl release 114")
    parser.add_argument("--reference-build", default="GRCh38.primary_assembly")
    parser.add_argument("--max-sequence-length", type=int, default=500_000)
    parser.add_argument("--limit-rows", type=int, help="Bounded smoke build row limit after endpoint mapping")
    parser.add_argument("--created-at", help="ISO ingestion timestamp; defaults to now UTC")
    parser.add_argument("--remote-output-root", help="Optional gs:// staging root to mirror local output")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = build_gene_genomic_features(
        kg_root_uri=args.kg_root,
        output_root_uri=args.output_root,
        gtf_path=args.gtf,
        fasta_path=args.fasta,
        source_release=args.source_release,
        reference_build=args.reference_build,
        max_sequence_length=args.max_sequence_length,
        limit_rows=args.limit_rows,
        created_at=args.created_at,
        remote_output_root_uri=args.remote_output_root,
    )
    print(json.dumps(report, indent=2, sort_keys=True, default=_json_default))


if __name__ == "__main__":
    main()
