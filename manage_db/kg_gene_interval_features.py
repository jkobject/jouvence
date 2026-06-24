"""Helpers for staged gene genomic interval feature tables.

Gene intervals are feature-layer coordinate precursors for future genomic
sequence extraction. They are not biological edges/evidence and they intentionally
carry no raw sequence payload.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from typing import Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .kg_schema import NodeType
from .kg_storage import KGRoot, _atomic_write

GENE_INTERVAL_TABLE = "gene_genomic_interval"

GENE_INTERVAL_PARQUET_COLUMNS: list[tuple[str, pa.DataType, str]] = [
    ("feature_key", pa.string(), "stable key table|node_id|source|source_record_id|reference_build"),
    ("feature_table", pa.string(), "gene_genomic_interval"),
    ("node_id", pa.string(), "canonical KG gene node id"),
    ("node_type", pa.string(), "gene"),
    ("sequence_kind", pa.string(), "genomic_locus_coordinates_only"),
    ("chromosome", pa.string(), "source chromosome/contig name"),
    ("start_1based", pa.int64(), "inclusive 1-based source coordinate"),
    ("end_1based", pa.int64(), "inclusive 1-based source coordinate"),
    ("strand", pa.string(), "+, -, or . if source unknown"),
    ("length", pa.int64(), "interval length in bases"),
    ("reference_build", pa.string(), "reference assembly/build label"),
    ("source", pa.string(), "source system, e.g. Ensembl or GENCODE"),
    ("source_dataset", pa.string(), "exact GTF/GFF3 coordinate dataset"),
    ("source_record_id", pa.string(), "stable source gene id, e.g. ENSG without version"),
    ("source_release", pa.string(), "source release/version/date"),
    ("provenance", pa.string(), "local/remote source path and extraction details"),
    ("license", pa.string(), "source license/terms label"),
    ("citation", pa.string(), "source citation/attribution text"),
    ("created_at", pa.string(), "ingestion timestamp"),
]

_REQUIRED_COLUMNS = [
    "feature_table",
    "node_id",
    "node_type",
    "sequence_kind",
    "chromosome",
    "start_1based",
    "end_1based",
    "strand",
    "reference_build",
    "source",
    "source_dataset",
    "source_record_id",
    "source_release",
    "provenance",
    "license",
    "citation",
    "created_at",
]
_STRING_COLUMNS = {name for name, typ, _ in GENE_INTERVAL_PARQUET_COLUMNS if pa.types.is_string(typ)}
_DEDUP_COLUMNS = ["feature_table", "node_id", "source", "source_dataset", "source_record_id", "reference_build"]

SOURCE_POLICY: dict[str, dict[str, str]] = {
    "Ensembl": {
        "decision": "allow_with_attribution",
        "license": "EMBL-EBI open data / attribution",
        "reason": "Ensembl GTF/GFF gene coordinates are open for reuse with attribution; preserve release and reference build.",
    },
    "GENCODE": {
        "decision": "allow_with_attribution",
        "license": "EMBL-EBI open data / attribution",
        "reason": "GENCODE gene annotations are distributed through EMBL-EBI/Gencode terms; preserve release and reference build.",
    },
}


@dataclass(frozen=True)
class GeneIntervalValidation:
    rows: int
    unique_nodes: int
    duplicate_rows_removed: int
    invalid_coordinate_rows: int
    invalid_strand_rows: int
    nodes_not_in_endpoint: int
    endpoint_nodes: int | None
    coverage_fraction: float | None
    min_length: int | None
    max_length: int | None

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "rows": self.rows,
            "unique_nodes": self.unique_nodes,
            "duplicate_rows_removed": self.duplicate_rows_removed,
            "invalid_coordinate_rows": self.invalid_coordinate_rows,
            "invalid_strand_rows": self.invalid_strand_rows,
            "nodes_not_in_endpoint": self.nodes_not_in_endpoint,
            "endpoint_nodes": self.endpoint_nodes,
            "coverage_fraction": self.coverage_fraction,
            "min_length": self.min_length,
            "max_length": self.max_length,
        }


def gene_interval_schema() -> pa.Schema:
    return pa.schema([pa.field(name, typ, nullable=True) for name, typ, _ in GENE_INTERVAL_PARQUET_COLUMNS])


def gene_interval_path(root: KGRoot) -> str:
    return root._as_public("features", f"{GENE_INTERVAL_TABLE}.parquet")


def _gene_interval_internal(root: KGRoot) -> str:
    return root._join("features", f"{GENE_INTERVAL_TABLE}.parquet")


def source_policy_audit() -> pd.DataFrame:
    rows = []
    for source, values in sorted(SOURCE_POLICY.items()):
        row = {"source": source}
        row.update(values)
        rows.append(row)
    return pd.DataFrame(rows)


def _coerce_frame(table: pa.Table | pd.DataFrame) -> pd.DataFrame:
    if isinstance(table, pa.Table):
        df = table.to_pandas()
    else:
        df = table.copy()
    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"features/{GENE_INTERVAL_TABLE} missing required columns: {missing}")
    if not df.empty and set(df["feature_table"].astype(str)) != {GENE_INTERVAL_TABLE}:
        raise ValueError(f"features/{GENE_INTERVAL_TABLE} contains rows for another feature table")
    if not df.empty:
        bad_type = sorted(set(df.loc[df["node_type"].astype(str) != NodeType.GENE.value, "node_type"].astype(str)))
        if bad_type:
            raise ValueError(f"features/{GENE_INTERVAL_TABLE} has invalid node_type values: {bad_type}")
    for name, typ, _ in GENE_INTERVAL_PARQUET_COLUMNS:
        if name not in df.columns:
            df[name] = 0 if pa.types.is_integer(typ) else ""
    df = df[[name for name, _, _ in GENE_INTERVAL_PARQUET_COLUMNS]].reset_index(drop=True)
    for col in _STRING_COLUMNS:
        df[col] = df[col].fillna("").astype(str).str.strip()
    for col in ["start_1based", "end_1based", "length"]:
        df[col] = pd.to_numeric(df[col], errors="raise").astype("int64")
    df["length"] = df["end_1based"] - df["start_1based"] + 1
    key_parts = [
        df["feature_table"].astype(str),
        df["node_id"].astype(str),
        df["source"].astype(str),
        df["source_record_id"].astype(str),
        df["reference_build"].astype(str),
    ]
    df["feature_key"] = key_parts[0]
    for part in key_parts[1:]:
        df["feature_key"] = df["feature_key"] + "|" + part
    return df


def validate_gene_intervals(
    table: pa.Table | pd.DataFrame,
    *,
    endpoint_node_ids: set[str] | None = None,
) -> tuple[pd.DataFrame, GeneIntervalValidation]:
    df = _coerce_frame(table)
    before = len(df)
    df = df.drop_duplicates(subset=_DEDUP_COLUMNS, keep="last").reset_index(drop=True)
    invalid_coord = int((df["start_1based"].lt(1) | df["end_1based"].lt(df["start_1based"])).sum())
    if invalid_coord:
        examples = df.loc[df["start_1based"].lt(1) | df["end_1based"].lt(df["start_1based"])].head(3).to_dict("records")
        raise ValueError(f"features/{GENE_INTERVAL_TABLE} contains {invalid_coord} invalid coordinate rows: {examples}")
    invalid_strand_mask = ~df["strand"].isin(["+", "-", "."])
    invalid_strand = int(invalid_strand_mask.sum()) if len(df) else 0
    if invalid_strand:
        bad = sorted(set(df.loc[invalid_strand_mask, "strand"].astype(str)))
        raise ValueError(f"features/{GENE_INTERVAL_TABLE} has invalid strand values: {bad}")
    nodes_not_in_endpoint = 0
    endpoint_nodes = None
    coverage_fraction = None
    if endpoint_node_ids is not None:
        endpoint_nodes = len(endpoint_node_ids)
        node_ids = set(df["node_id"].astype(str))
        nodes_not_in_endpoint = len(node_ids - endpoint_node_ids)
        if nodes_not_in_endpoint:
            examples = sorted(node_ids - endpoint_node_ids)[:5]
            raise ValueError(f"features/{GENE_INTERVAL_TABLE} has node_ids not present in endpoint nodes: {examples}")
        coverage_fraction = (len(node_ids) / endpoint_nodes) if endpoint_nodes else 0.0
    validation = GeneIntervalValidation(
        rows=len(df),
        unique_nodes=int(df["node_id"].nunique()),
        duplicate_rows_removed=before - len(df),
        invalid_coordinate_rows=invalid_coord,
        invalid_strand_rows=invalid_strand,
        nodes_not_in_endpoint=nodes_not_in_endpoint,
        endpoint_nodes=endpoint_nodes,
        coverage_fraction=coverage_fraction,
        min_length=int(df["length"].min()) if len(df) else None,
        max_length=int(df["length"].max()) if len(df) else None,
    )
    return df, validation


def write_gene_intervals(
    root: KGRoot,
    table: pa.Table | pd.DataFrame,
    *,
    mode: Literal["overwrite", "append"] = "overwrite",
    endpoint_node_ids: set[str] | None = None,
) -> GeneIntervalValidation:
    df, validation = validate_gene_intervals(table, endpoint_node_ids=endpoint_node_ids)
    combined = df
    internal = _gene_interval_internal(root)
    if mode == "append" and root.fs.exists(internal):
        existing = read_gene_intervals(root)
        combined, validation = validate_gene_intervals(
            pd.concat([existing, df], ignore_index=True), endpoint_node_ids=endpoint_node_ids
        )
    arrow_table = pa.Table.from_pandas(combined, schema=gene_interval_schema(), preserve_index=False)
    _atomic_write(root, internal, arrow_table)
    return validation


def read_gene_intervals(root: KGRoot, columns: list[str] | None = None) -> pd.DataFrame:
    table = pq.read_table(_gene_interval_internal(root), columns=columns, filesystem=root.fs)
    return table.to_pandas()


def list_gene_interval_tables(root: KGRoot) -> list[str]:
    directory = root._join("features")
    if not directory or not root.fs.exists(directory):
        return []
    stems: list[str] = []
    for entry in root.fs.ls(directory, detail=True):
        if entry.get("type") != "file":
            continue
        name = entry.get("name") or ""
        stem = posixpath.splitext(posixpath.basename(name))[0]
        if name.endswith(".parquet") and stem == GENE_INTERVAL_TABLE:
            stems.append(stem)
    return sorted(stems)
