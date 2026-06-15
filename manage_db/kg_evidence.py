"""Parquet storage helpers for TxGNN edge evidence/support records."""

from __future__ import annotations

import posixpath
from typing import Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .kg_schema import RELATION_BY_NAME
from .kg_storage import KGRoot, _atomic_write

EVIDENCE_PARQUET_COLUMNS: list[tuple[str, str]] = [
    ("edge_key", "str — stable key relation|x_id|y_id for the supported edge"),
    ("relation", "str — canonical Relation.name being supported"),
    ("x_id", "str — source node ID of the supported edge"),
    ("x_type", "str — source node type of the supported edge"),
    ("y_id", "str — target node ID of the supported edge"),
    ("y_type", "str — target node type of the supported edge"),
    ("evidence_type", "str — paper | database_record | experiment | etc."),
    ("source", "str — source system, e.g. OpenTargets, EuropePMC"),
    ("source_dataset", "str — source dataset/table/release"),
    ("source_record_id", "str — stable source row/document ID"),
    ("paper_id", "str — PMID:/DOI evidence when available"),
    ("dataset_id", "str — dataset node ID when available"),
    ("study_id", "str — GWAS/clinical/study accession when available"),
    ("evidence_score", "float — source-provided score when available"),
    ("effect_size", "float — quantitative effect size when available"),
    ("p_value", "float — statistical p-value when available"),
    ("direction", "str — up/down/protective/risk/etc. when available"),
    ("confidence_interval", "str — source-provided CI when available"),
    ("predicate", "str — original source predicate before TxGNN normalization"),
    ("text_span", "str — extracted literature span when available"),
    ("section", "str — paper section when available"),
    ("extraction_method", "str — curation/NLP/model method"),
    ("license", "str — source license when available"),
    ("release", "str — source release/version when available"),
    ("created_at", "str — ingestion timestamp when available"),
]

_REQUIRED_COLUMNS = [
    "relation",
    "x_id",
    "x_type",
    "y_id",
    "y_type",
    "evidence_type",
    "source",
    "source_dataset",
    "source_record_id",
]
_FLOAT_COLUMNS = {"evidence_score", "effect_size", "p_value"}
_DEDUP_COLUMNS = [
    "relation",
    "x_id",
    "y_id",
    "evidence_type",
    "source",
    "source_dataset",
    "source_record_id",
    "paper_id",
    "dataset_id",
    "study_id",
    "predicate",
]


def evidence_schema() -> pa.Schema:
    fields = []
    for name, _ in EVIDENCE_PARQUET_COLUMNS:
        if name in _FLOAT_COLUMNS:
            fields.append(pa.field(name, pa.float64(), nullable=True))
        else:
            fields.append(pa.field(name, pa.string(), nullable=True))
    return pa.schema(fields)


def evidence_path(root: KGRoot, relation: str) -> str:
    return root._as_public("evidence", f"{relation}.parquet")


def _evidence_internal(root: KGRoot, relation: str) -> str:
    return root._join("evidence", f"{relation}.parquet")


def list_evidence(root: KGRoot) -> list[str]:
    directory = root._join("evidence")
    if not directory or not root.fs.exists(directory):
        return []
    stems: list[str] = []
    for entry in root.fs.ls(directory, detail=True):
        if entry.get("type") != "file":
            continue
        name = entry.get("name") or ""
        if name.endswith(".parquet"):
            stems.append(posixpath.splitext(posixpath.basename(name))[0])
    return sorted(stems)


def _coerce_evidence_frame(table: pa.Table | pd.DataFrame, relation: str) -> pd.DataFrame:
    if isinstance(table, pa.Table):
        df = table.to_pandas()
    else:
        df = table.copy()
    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"evidence/{relation} missing required columns: {missing}")
    if relation not in RELATION_BY_NAME:
        raise ValueError(f"unknown relation: {relation}")
    if not df.empty and set(df["relation"].astype(str)) != {relation}:
        raise ValueError(f"evidence/{relation} contains rows for another relation")

    spec = RELATION_BY_NAME[relation]
    if not df.empty:
        bad_x = df.loc[df["x_type"].astype(str) != spec.source.value, "x_type"].astype(str).unique()
        bad_y = df.loc[df["y_type"].astype(str) != spec.target.value, "y_type"].astype(str).unique()
        if len(bad_x):
            raise ValueError(f"evidence/{relation} has invalid x_type values: {sorted(bad_x)}")
        if len(bad_y):
            raise ValueError(f"evidence/{relation} has invalid y_type values: {sorted(bad_y)}")

    for name, _ in EVIDENCE_PARQUET_COLUMNS:
        if name not in df.columns:
            df[name] = pd.NA
    df = df[[name for name, _ in EVIDENCE_PARQUET_COLUMNS]].reset_index(drop=True)
    df["edge_key"] = df["relation"].astype(str) + "|" + df["x_id"].astype(str) + "|" + df["y_id"].astype(str)

    for col in _FLOAT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for col, _ in EVIDENCE_PARQUET_COLUMNS:
        if col not in _FLOAT_COLUMNS:
            df[col] = df[col].fillna("").astype("string[pyarrow]")
    return df


def write_evidence(
    root: KGRoot,
    relation: str,
    table: pa.Table | pd.DataFrame,
    *,
    mode: Literal["overwrite", "append"] = "overwrite",
) -> int:
    """Write evidence/support records for a canonical relation."""

    df = _coerce_evidence_frame(table, relation)
    combined = df
    internal = _evidence_internal(root, relation)
    if mode == "append" and root.fs.exists(internal):
        existing = read_evidence(root, relation)
        combined = pd.concat([existing, df], ignore_index=True)
    dedup_cols = [col for col in _DEDUP_COLUMNS if col in combined.columns]
    combined = combined.drop_duplicates(subset=dedup_cols, keep="last").reset_index(drop=True)
    arrow_table = pa.Table.from_pandas(combined, schema=evidence_schema(), preserve_index=False)
    _atomic_write(root, internal, arrow_table)
    return len(combined)


def read_evidence(root: KGRoot, relation: str, columns: list[str] | None = None) -> pd.DataFrame:
    table = pq.read_table(_evidence_internal(root, relation), columns=columns, filesystem=root.fs)
    return table.to_pandas()
