"""Build staged sequence feature tables from conservative FASTA sources.

This builder intentionally writes only under a provided staging root. It never
promotes to the canonical KG root and maps FASTA records by exact node IDs after
stripping common Ensembl version suffixes.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import shutil
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from . import kg_sequence_features as seqf
from .kg_storage import open_kg_root, read_nodes

_FASTA_ID_RE = re.compile(r"^([^\s|]+)")
_ENSEMBL_VERSION_RE = re.compile(r"^(ENS[GPT][0-9]+)(?:\.\d+)?$")
_ALPHABETS: dict[str, set[str]] = {
    "protein_iupac": set("ACDEFGHIKLMNPQRSTVWYXBZUOJ"),
    "dna_iupac": set("ACGTRYSWKMBDHVN"),
}


def _strip_ensembl_version(record_id: str) -> str:
    token = record_id.strip()
    match = _ENSEMBL_VERSION_RE.match(token)
    return match.group(1) if match else token


def _iter_fasta(path: str | os.PathLike[str]) -> Iterator[tuple[str, str, str]]:
    """Yield (record_id_without_version, raw_header, sequence)."""

    fasta_path = Path(path)
    opener = gzip.open if fasta_path.suffix == ".gz" else open
    with opener(fasta_path, "rt") as handle:  # type: ignore[arg-type]
        header: str | None = None
        chunks: list[str] = []
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield _record_id_from_header(header), header, "".join(chunks).upper()
                header = line[1:]
                chunks = []
            else:
                chunks.append(line)
        if header is not None:
            yield _record_id_from_header(header), header, "".join(chunks).upper()


def _record_id_from_header(header: str) -> str:
    match = _FASTA_ID_RE.match(header)
    if not match:
        raise ValueError(f"could not parse FASTA header: {header!r}")
    token = match.group(1)
    # UniProt headers often look like sp|P04637|P53_HUMAN; keep the accession if present.
    if "|" in token:
        parts = token.split("|")
        if len(parts) >= 2 and parts[1]:
            token = parts[1]
    return _strip_ensembl_version(token)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _endpoint_ids(kg_root_uri: str, node_type: str) -> set[str]:
    root = open_kg_root(kg_root_uri)
    nodes = read_nodes(root, node_type, columns=["id"])
    return set(nodes["id"].astype(str))


def _rows_from_fasta(
    *,
    fasta_path: str | os.PathLike[str],
    endpoint_node_ids: set[str],
    feature_table: str,
    node_type: str,
    sequence_kind: str,
    alphabet: str,
    source: str,
    source_dataset: str,
    source_release: str,
    license: str,
    citation: str,
    created_at: str,
    max_sequence_length: int,
) -> tuple[pd.DataFrame, dict[str, int]]:
    rows: list[dict[str, Any]] = []
    records_seen = 0
    records_unmapped = 0
    records_empty = 0
    records_invalid_alphabet = 0
    records_over_max_length = 0
    provenance = str(fasta_path)
    allowed_alphabet = _ALPHABETS[alphabet]
    for record_id, header, sequence in _iter_fasta(fasta_path):
        records_seen += 1
        if not sequence:
            records_empty += 1
            continue
        if set(sequence) - allowed_alphabet:
            records_invalid_alphabet += 1
            continue
        if len(sequence) > max_sequence_length:
            records_over_max_length += 1
            continue
        if record_id not in endpoint_node_ids:
            records_unmapped += 1
            continue
        rows.append(
            {
                "feature_table": feature_table,
                "node_id": record_id,
                "node_type": node_type,
                "sequence_kind": sequence_kind,
                "sequence": sequence,
                "alphabet": alphabet,
                "source": source,
                "source_dataset": source_dataset,
                "source_record_id": record_id,
                "source_release": source_release,
                "provenance": f"{provenance}::{header}",
                "license": license,
                "citation": citation,
                "created_at": created_at,
            }
        )
    stats = {
        "source_records_seen": records_seen,
        "source_records_unmapped": records_unmapped,
        "source_records_empty": records_empty,
        "source_records_invalid_alphabet": records_invalid_alphabet,
        "source_records_over_max_length": records_over_max_length,
    }
    return pd.DataFrame(rows), stats


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


def build_sequence_feature_tables(
    *,
    kg_root_uri: str,
    output_root_uri: str,
    protein_fasta: str | os.PathLike[str] | None = None,
    transcript_fasta: str | os.PathLike[str] | None = None,
    source_release: str,
    created_at: str | None = None,
    remote_output_root_uri: str | None = None,
    max_sequence_length: int = 100_000,
) -> dict[str, dict[str, Any]]:
    """Build accepted immediate sequence feature tables into a staging root."""

    created_at = created_at or _now_iso()
    output_root = open_kg_root(output_root_uri)
    report: dict[str, dict[str, Any]] = {}

    if protein_fasta is not None:
        endpoint = _endpoint_ids(kg_root_uri, "protein")
        rows, stats = _rows_from_fasta(
            fasta_path=protein_fasta,
            endpoint_node_ids=endpoint,
            feature_table="protein_sequence",
            node_type="protein",
            sequence_kind="amino_acid",
            alphabet="protein_iupac",
            source="Ensembl",
            source_dataset="Ensembl protein FASTA",
            source_release=source_release,
            license="EMBL-EBI open data / attribution",
            citation="Ensembl Project",
            created_at=created_at,
            max_sequence_length=max_sequence_length,
        )
        validation = seqf.write_sequences(
            output_root,
            "protein_sequence",
            rows,
            endpoint_node_ids=endpoint,
            max_sequence_length=max_sequence_length,
        )
        report["protein_sequence"] = {**validation.to_dict(), **stats, "path": seqf.sequence_path(output_root, "protein_sequence")}

    if transcript_fasta is not None:
        endpoint = _endpoint_ids(kg_root_uri, "transcript")
        rows, stats = _rows_from_fasta(
            fasta_path=transcript_fasta,
            endpoint_node_ids=endpoint,
            feature_table="transcript_sequence",
            node_type="transcript",
            sequence_kind="cdna",
            alphabet="dna_iupac",
            source="Ensembl",
            source_dataset="Ensembl transcript cDNA FASTA",
            source_release=source_release,
            license="EMBL-EBI open data / attribution",
            citation="Ensembl Project",
            created_at=created_at,
            max_sequence_length=max_sequence_length,
        )
        validation = seqf.write_sequences(
            output_root,
            "transcript_sequence",
            rows,
            endpoint_node_ids=endpoint,
            max_sequence_length=max_sequence_length,
        )
        report["transcript_sequence"] = {
            **validation.to_dict(),
            **stats,
            "path": seqf.sequence_path(output_root, "transcript_sequence"),
        }

    reports_dir = Path(output_root_uri) / "reports" if "://" not in output_root_uri else None
    if reports_dir is not None:
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "sequence_feature_report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
        policy = seqf.source_policy_audit()
        policy.to_csv(reports_dir / "sequence_source_policy.csv", index=False)

    if remote_output_root_uri is not None:
        _copy_local_tree_to_gcs(output_root_uri, remote_output_root_uri)
        report["remote_output_root_uri"] = {"path": remote_output_root_uri}

    return report


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kg-root", required=True, help="Read-only KG root containing nodes/*.parquet")
    parser.add_argument("--output-root", required=True, help="Staging root to write features/*.parquet")
    parser.add_argument("--protein-fasta", help="Ensembl protein FASTA path (.fa or .fa.gz)")
    parser.add_argument("--transcript-fasta", help="Ensembl transcript cDNA FASTA path (.fa or .fa.gz)")
    parser.add_argument("--source-release", required=True, help="Source release label, e.g. Ensembl release 114")
    parser.add_argument("--created-at", help="ISO ingestion timestamp; defaults to now UTC")
    parser.add_argument("--remote-output-root", help="Optional gs:// staging root to mirror local output")
    parser.add_argument("--max-sequence-length", type=int, default=100_000)
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = build_sequence_feature_tables(
        kg_root_uri=args.kg_root,
        output_root_uri=args.output_root,
        protein_fasta=args.protein_fasta,
        transcript_fasta=args.transcript_fasta,
        source_release=args.source_release,
        created_at=args.created_at,
        remote_output_root_uri=args.remote_output_root,
        max_sequence_length=args.max_sequence_length,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
