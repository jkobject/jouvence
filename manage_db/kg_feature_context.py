"""Parquet helpers for non-causal KG feature/context records.

These tables intentionally live outside ``edges/`` and ``evidence/``. They are
for predictive, correlative, association-score, or context-specific features
that may be useful to downstream models but must not be confused with
mechanistic KG assertions such as regulation, physical interaction, or PPI.
"""

from __future__ import annotations

import posixpath
from typing import Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .kg_schema import NodeType
from .kg_storage import KGRoot, _atomic_write

FEATURE_CONTEXT_PARQUET_COLUMNS: list[tuple[str, str]] = [
    ("feature_key", "str — stable key table|x_id|y_id|source|source_record_id|context"),
    ("feature_table", "str — non-causal feature table name, e.g. gene_gene_expression_correlation"),
    ("x_id", "str — source entity ID"),
    ("x_type", "str — source NodeType value"),
    ("y_id", "str — target/context entity ID"),
    ("y_type", "str — target NodeType value"),
    ("evidence_type", "str — must be correlative, non_causal, predictive, association_score, or candidate_context"),
    ("source", "str — source system, e.g. STRING, OpenTargets, ENCORI"),
    ("source_dataset", "str — source table/sub-evidence/release"),
    ("source_record_id", "str — stable source row/document ID"),
    ("context_type", "str — tissue, cell_type, disease, cohort, biosample, cell_line, pan_context, etc."),
    ("context_id", "str — ontology/cohort/biosample ID when available"),
    ("context_name", "str — human-readable context label"),
    ("correlation_coefficient", "float — Pearson/Spearman/etc. coefficient when available"),
    ("effect_size", "float — source effect size when available"),
    ("p_value", "float — statistical p-value when available"),
    ("q_value", "float — adjusted p/q/FDR value when available"),
    ("method", "str — correlation/model/assay method"),
    ("sample_count", "int — number of samples/cell lines/cohort members"),
    ("score", "float — source-provided score when not a correlation coefficient"),
    ("predicate", "str — original source predicate/channel before normalization"),
    ("license", "str — source license when available"),
    ("release", "str — source release/version"),
    ("created_at", "str — ingestion timestamp when available"),
]

_REQUIRED_COLUMNS = [
    "feature_table",
    "x_id",
    "x_type",
    "y_id",
    "y_type",
    "evidence_type",
    "source",
    "source_dataset",
    "source_record_id",
]
_FLOAT_COLUMNS = {"correlation_coefficient", "effect_size", "p_value", "q_value", "score"}
_INT_COLUMNS = {"sample_count"}
_NON_CAUSAL_EVIDENCE_TYPES = {
    "correlative",
    "non_causal",
    "predictive",
    "association_score",
    "candidate_context",
}
_FORBIDDEN_EVIDENCE_TYPES = {
    "causal",
    "mechanistic",
    "regulatory",
    "physical_interaction",
    "ppi",
    "direct_binding",
    "direct_regulation",
}
_ALLOWED_ENDPOINTS: dict[str, tuple[NodeType, NodeType]] = {
    "gene_gene_expression_correlation": (NodeType.GENE, NodeType.GENE),
    "rna_gene_expression_correlation": (NodeType.TRANSCRIPT, NodeType.GENE),
    "gene_disease_association_score": (NodeType.GENE, NodeType.DISEASE),
    "molecule_disease_association_score": (NodeType.MOLECULE, NodeType.DISEASE),
    "cell_line_gene_expression_feature": (NodeType.CELL_LINE, NodeType.GENE),
}
_DEDUP_COLUMNS = [
    "feature_table",
    "x_id",
    "y_id",
    "evidence_type",
    "source",
    "source_dataset",
    "source_record_id",
    "context_type",
    "context_id",
    "method",
]


def feature_context_schema() -> pa.Schema:
    fields = []
    for name, _ in FEATURE_CONTEXT_PARQUET_COLUMNS:
        if name in _FLOAT_COLUMNS:
            fields.append(pa.field(name, pa.float64(), nullable=True))
        elif name in _INT_COLUMNS:
            fields.append(pa.field(name, pa.int64(), nullable=True))
        else:
            fields.append(pa.field(name, pa.string(), nullable=True))
    return pa.schema(fields)


def feature_context_path(root: KGRoot, feature_table: str) -> str:
    return root._as_public("features", f"{feature_table}.parquet")


def _feature_context_internal(root: KGRoot, feature_table: str) -> str:
    return root._join("features", f"{feature_table}.parquet")


def list_feature_context_tables(root: KGRoot) -> list[str]:
    directory = root._join("features")
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


def _coerce_feature_context_frame(table: pa.Table | pd.DataFrame, feature_table: str) -> pd.DataFrame:
    if isinstance(table, pa.Table):
        df = table.to_pandas()
    else:
        df = table.copy()

    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"features/{feature_table} missing required columns: {missing}")
    if feature_table not in _ALLOWED_ENDPOINTS:
        raise ValueError(f"unknown feature context table: {feature_table}")
    if not df.empty and set(df["feature_table"].astype(str)) != {feature_table}:
        raise ValueError(f"features/{feature_table} contains rows for another feature table")

    x_type, y_type = _ALLOWED_ENDPOINTS[feature_table]
    if not df.empty:
        types = df[["x_type", "y_type"]].astype(str)
        bad = types.loc[(types["x_type"] != x_type.value) | (types["y_type"] != y_type.value)]
        if not bad.empty:
            bad_x = sorted(bad.loc[bad["x_type"] != x_type.value, "x_type"].unique())
            bad_y = sorted(bad.loc[bad["y_type"] != y_type.value, "y_type"].unique())
            if bad_x:
                raise ValueError(f"features/{feature_table} has invalid x_type values: {bad_x}")
            if bad_y:
                raise ValueError(f"features/{feature_table} has invalid y_type values: {bad_y}")

        evidence_types = set(df["evidence_type"].astype(str).str.lower())
        forbidden = evidence_types & _FORBIDDEN_EVIDENCE_TYPES
        if forbidden:
            raise ValueError(
                f"features/{feature_table} has causal/mechanistic evidence_type values: {sorted(forbidden)}"
            )
        unsupported = evidence_types - _NON_CAUSAL_EVIDENCE_TYPES
        if unsupported:
            raise ValueError(
                f"features/{feature_table} evidence_type must be explicitly non-causal; got {sorted(unsupported)}"
            )

    for name, _ in FEATURE_CONTEXT_PARQUET_COLUMNS:
        if name not in df.columns:
            df[name] = pd.NA
    df = df[[name for name, _ in FEATURE_CONTEXT_PARQUET_COLUMNS]].reset_index(drop=True)

    key_parts = [
        df["feature_table"].astype(str),
        df["x_id"].astype(str),
        df["y_id"].astype(str),
        df["source"].astype(str),
        df["source_record_id"].astype(str),
        df["context_type"].astype(str),
        df["context_id"].astype(str),
    ]
    df["feature_key"] = key_parts[0]
    for part in key_parts[1:]:
        df["feature_key"] = df["feature_key"] + "|" + part

    for col in _FLOAT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for col in _INT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col, _ in FEATURE_CONTEXT_PARQUET_COLUMNS:
        if col not in _FLOAT_COLUMNS and col not in _INT_COLUMNS:
            df[col] = df[col].fillna("").astype("string[pyarrow]")
    return df


def write_feature_context(
    root: KGRoot,
    feature_table: str,
    table: pa.Table | pd.DataFrame,
    *,
    mode: Literal["overwrite", "append"] = "overwrite",
) -> int:
    """Write non-causal feature/context records under ``features/``."""

    df = _coerce_feature_context_frame(table, feature_table)
    combined = df
    internal = _feature_context_internal(root, feature_table)
    if mode == "append" and root.fs.exists(internal):
        existing = read_feature_context(root, feature_table)
        combined = pd.concat([existing, df], ignore_index=True)
    combined = combined.drop_duplicates(subset=_DEDUP_COLUMNS, keep="last").reset_index(drop=True)
    arrow_table = pa.Table.from_pandas(combined, schema=feature_context_schema(), preserve_index=False)
    _atomic_write(root, internal, arrow_table)
    return len(combined)


def read_feature_context(
    root: KGRoot, feature_table: str, columns: list[str] | None = None
) -> pd.DataFrame:
    table = pq.read_table(
        _feature_context_internal(root, feature_table), columns=columns, filesystem=root.fs
    )
    return table.to_pandas()


def allowed_feature_context_tables() -> dict[str, tuple[str, str]]:
    """Return feature table endpoint contracts as ``table -> (x_type, y_type)``."""

    return {name: (x.value, y.value) for name, (x, y) in _ALLOWED_ENDPOINTS.items()}
