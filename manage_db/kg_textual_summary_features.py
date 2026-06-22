"""Helpers for staged textual-summary feature tables.

Text summaries are model features, not biological KG assertions.  They must live
under ``features/`` and carry source/release/provenance/license metadata for each
row so downstream consumers can decide whether a text source is usable.
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

TEXTUAL_SUMMARY_PARQUET_COLUMNS: list[tuple[str, str]] = [
    ("feature_key", "str — stable key table|node_id|source|source_record_id|summary_kind"),
    ("feature_table", "str — textual summary table name, e.g. gene_textual_summary"),
    ("node_id", "str — canonical KG node id"),
    ("node_type", "str — KG NodeType value"),
    ("summary_kind", "str — function, disease_definition, anatomy_definition, drug_summary, pathway_definition, etc."),
    ("summary_text", "str — plain-text summary payload"),
    ("source", "str — source system, e.g. NCBI Gene, UniProtKB, EFO, UBERON, ChEMBL, Reactome, GO"),
    ("source_dataset", "str — source table/API/ontology dump"),
    ("source_record_id", "str — stable source row/document ID"),
    ("provenance", "str — source URL, ontology term, API endpoint, or local raw-file path"),
    ("license", "str — source license/terms label"),
    ("citation", "str — source citation or attribution text"),
    ("release", "str — source release/version/date"),
    ("created_at", "str — ingestion timestamp"),
]

_TEXTUAL_SUMMARY_TABLE_TYPES: dict[str, NodeType] = {
    "gene_textual_summary": NodeType.GENE,
    "protein_textual_summary": NodeType.PROTEIN,
    "disease_textual_summary": NodeType.DISEASE,
    "tissue_textual_summary": NodeType.TISSUE,
    "molecule_textual_summary": NodeType.MOLECULE,
    "pathway_textual_summary": NodeType.PATHWAY,
}

_STRING_COLUMNS = {name for name, _ in TEXTUAL_SUMMARY_PARQUET_COLUMNS}
_REQUIRED_COLUMNS = [
    "feature_table",
    "node_id",
    "node_type",
    "summary_kind",
    "summary_text",
    "source",
    "source_dataset",
    "source_record_id",
    "provenance",
    "license",
    "citation",
    "release",
]
_DEDUP_COLUMNS = ["feature_table", "node_id", "source", "source_dataset", "source_record_id", "summary_kind"]

# Keep this audit conservative.  It documents allowed sources and sources that
# should not be scraped into feature tables without a fresh legal review.
SOURCE_POLICY: dict[str, dict[str, str]] = {
    "GeneCards": {
        "decision": "reject",
        "reason": "GeneCards pages/entries are proprietary; no bulk scraping or redistribution was accepted for this task.",
        "license": "proprietary / terms-restricted",
    },
    "DrugBank": {
        "decision": "reject_scraping",
        "reason": "DrugBank content is license-restricted; only use IDs already present in KG nodes, not scraped textual records.",
        "license": "restricted / requires separate license",
    },
    "NCBI Gene": {
        "decision": "allow_with_attribution",
        "reason": "NCBI/NLM data is usable with attribution; preserve record IDs and release/date.",
        "license": "public domain / NCBI attribution requested",
    },
    "Ensembl": {
        "decision": "allow_with_attribution",
        "reason": "Ensembl data is openly reusable with attribution under EMBL-EBI terms.",
        "license": "EMBL-EBI open data / attribution",
    },
    "UniProtKB": {
        "decision": "allow_with_attribution",
        "reason": "UniProtKB text/comments are openly reusable with attribution under CC BY 4.0.",
        "license": "CC BY 4.0",
    },
    "Alliance Genome Resources": {
        "decision": "allow_with_attribution",
        "reason": "Alliance data is openly reusable with attribution; preserve release and record IDs.",
        "license": "CC BY 4.0 / source attribution",
    },
    "EFO": {
        "decision": "allow_with_attribution",
        "reason": "EFO ontology definitions are open OBO/EMBL-EBI ontology content; preserve ontology term provenance.",
        "license": "CC BY 4.0 / ontology attribution",
    },
    "MONDO": {
        "decision": "allow_with_attribution",
        "reason": "MONDO ontology definitions are open OBO Foundry ontology content; preserve term provenance.",
        "license": "CC BY 4.0 / ontology attribution",
    },
    "Orphanet": {
        "decision": "defer_until_license_review",
        "reason": "Orphanet terms vary by product/API; do not redistribute textual abstracts until the exact source terms are accepted.",
        "license": "terms-dependent",
    },
    "MedGen": {
        "decision": "allow_with_attribution",
        "reason": "MedGen records are usable with NCBI/NLM attribution; preserve CUI/record provenance.",
        "license": "public domain / NCBI attribution requested",
    },
    "UBERON": {
        "decision": "allow_with_attribution",
        "reason": "UBERON ontology definitions are open OBO Foundry ontology content; preserve term provenance.",
        "license": "CC BY 4.0 / ontology attribution",
    },
    "HPA": {
        "decision": "allow_with_attribution_for_allowed_downloads",
        "reason": "Human Protein Atlas downloadable datasets are CC BY-SA 4.0; preserve release, URL and citation.",
        "license": "CC BY-SA 4.0",
    },
    "ChEMBL": {
        "decision": "allow_with_attribution",
        "reason": "ChEMBL is open under CC BY-SA 3.0; preserve molecule ID and release.",
        "license": "CC BY-SA 3.0",
    },
    "Reactome": {
        "decision": "allow_with_attribution",
        "reason": "Reactome content is open under CC BY 4.0; preserve stable ID and release.",
        "license": "CC BY 4.0",
    },
    "GO": {
        "decision": "allow_with_attribution",
        "reason": "Gene Ontology definitions are open under CC BY 4.0; preserve term provenance.",
        "license": "CC BY 4.0",
    },
    "OpenTargets": {
        "decision": "allow_with_attribution_if_upstream_source_clear",
        "reason": "Open Targets data is open/redistributable, but text should retain the underlying ontology/database source where known.",
        "license": "CC BY 4.0 / upstream source attribution",
    },
}

@dataclass(frozen=True)
class TextSummaryValidation:
    rows: int
    unique_nodes: int
    duplicate_rows_removed: int
    missing_summary_text_rows: int
    over_max_text_rows: int
    nodes_not_in_endpoint: int
    endpoint_nodes: int | None
    coverage_fraction: float | None

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "rows": self.rows,
            "unique_nodes": self.unique_nodes,
            "duplicate_rows_removed": self.duplicate_rows_removed,
            "missing_summary_text_rows": self.missing_summary_text_rows,
            "over_max_text_rows": self.over_max_text_rows,
            "nodes_not_in_endpoint": self.nodes_not_in_endpoint,
            "endpoint_nodes": self.endpoint_nodes,
            "coverage_fraction": self.coverage_fraction,
        }


def textual_summary_schema() -> pa.Schema:
    return pa.schema([pa.field(name, pa.string(), nullable=True) for name, _ in TEXTUAL_SUMMARY_PARQUET_COLUMNS])


def textual_summary_path(root: KGRoot, feature_table: str) -> str:
    return root._as_public("features", f"{feature_table}.parquet")


def _textual_summary_internal(root: KGRoot, feature_table: str) -> str:
    return root._join("features", f"{feature_table}.parquet")


def allowed_textual_summary_tables() -> dict[str, str]:
    return {name: node_type.value for name, node_type in _TEXTUAL_SUMMARY_TABLE_TYPES.items()}


def source_policy_audit() -> pd.DataFrame:
    rows = []
    for source, values in sorted(SOURCE_POLICY.items()):
        row = {"source": source}
        row.update(values)
        rows.append(row)
    return pd.DataFrame(rows)


def _coerce_textual_summary_frame(table: pa.Table | pd.DataFrame, feature_table: str) -> pd.DataFrame:
    if isinstance(table, pa.Table):
        df = table.to_pandas()
    else:
        df = table.copy()

    if feature_table not in _TEXTUAL_SUMMARY_TABLE_TYPES:
        raise ValueError(f"unknown textual summary feature table: {feature_table}")
    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"features/{feature_table} missing required columns: {missing}")
    if not df.empty and set(df["feature_table"].astype(str)) != {feature_table}:
        raise ValueError(f"features/{feature_table} contains rows for another feature table")

    expected_type = _TEXTUAL_SUMMARY_TABLE_TYPES[feature_table].value
    if not df.empty:
        bad_type = sorted(set(df.loc[df["node_type"].astype(str) != expected_type, "node_type"].astype(str)))
        if bad_type:
            raise ValueError(f"features/{feature_table} has invalid node_type values: {bad_type}")

    for name, _ in TEXTUAL_SUMMARY_PARQUET_COLUMNS:
        if name not in df.columns:
            df[name] = ""
    df = df[[name for name, _ in TEXTUAL_SUMMARY_PARQUET_COLUMNS]].reset_index(drop=True)
    for col in _STRING_COLUMNS:
        df[col] = df[col].fillna("").astype("string[pyarrow]")

    key_parts = [
        df["feature_table"].astype(str),
        df["node_id"].astype(str),
        df["source"].astype(str),
        df["source_record_id"].astype(str),
        df["summary_kind"].astype(str),
    ]
    df["feature_key"] = key_parts[0]
    for part in key_parts[1:]:
        df["feature_key"] = df["feature_key"] + "|" + part
    return df


def validate_textual_summaries(
    table: pa.Table | pd.DataFrame,
    feature_table: str,
    *,
    endpoint_node_ids: set[str] | None = None,
    max_text_chars: int = 5000,
) -> tuple[pd.DataFrame, TextSummaryValidation]:
    """Validate/coerce textual summaries and return de-duplicated rows + stats."""

    df = _coerce_textual_summary_frame(table, feature_table)
    before = len(df)
    df = df.drop_duplicates(subset=_DEDUP_COLUMNS, keep="last").reset_index(drop=True)
    text_lengths = df["summary_text"].fillna("").astype(str).str.len()
    missing_text = int(text_lengths.eq(0).sum())
    over_max = int(text_lengths.gt(max_text_chars).sum())
    if missing_text:
        raise ValueError(f"features/{feature_table} contains {missing_text} rows with empty summary_text")
    if over_max:
        raise ValueError(f"features/{feature_table} contains {over_max} rows over max_text_chars={max_text_chars}")

    nodes_not_in_endpoint = 0
    endpoint_nodes = None
    coverage_fraction = None
    if endpoint_node_ids is not None:
        endpoint_nodes = len(endpoint_node_ids)
        node_ids = set(df["node_id"].astype(str))
        nodes_not_in_endpoint = len(node_ids - endpoint_node_ids)
        if nodes_not_in_endpoint:
            examples = sorted(node_ids - endpoint_node_ids)[:5]
            raise ValueError(f"features/{feature_table} has node_ids not present in endpoint nodes: {examples}")
        coverage_fraction = (len(node_ids) / endpoint_nodes) if endpoint_nodes else 0.0

    validation = TextSummaryValidation(
        rows=len(df),
        unique_nodes=int(df["node_id"].nunique()),
        duplicate_rows_removed=before - len(df),
        missing_summary_text_rows=missing_text,
        over_max_text_rows=over_max,
        nodes_not_in_endpoint=nodes_not_in_endpoint,
        endpoint_nodes=endpoint_nodes,
        coverage_fraction=coverage_fraction,
    )
    return df, validation


def write_textual_summaries(
    root: KGRoot,
    feature_table: str,
    table: pa.Table | pd.DataFrame,
    *,
    mode: Literal["overwrite", "append"] = "overwrite",
    endpoint_node_ids: set[str] | None = None,
    max_text_chars: int = 5000,
) -> TextSummaryValidation:
    df, validation = validate_textual_summaries(
        table, feature_table, endpoint_node_ids=endpoint_node_ids, max_text_chars=max_text_chars
    )
    combined = df
    internal = _textual_summary_internal(root, feature_table)
    if mode == "append" and root.fs.exists(internal):
        existing = read_textual_summaries(root, feature_table)
        combined, validation = validate_textual_summaries(
            pd.concat([existing, df], ignore_index=True),
            feature_table,
            endpoint_node_ids=endpoint_node_ids,
            max_text_chars=max_text_chars,
        )
    arrow_table = pa.Table.from_pandas(combined, schema=textual_summary_schema(), preserve_index=False)
    _atomic_write(root, internal, arrow_table)
    return validation


def read_textual_summaries(root: KGRoot, feature_table: str, columns: list[str] | None = None) -> pd.DataFrame:
    table = pq.read_table(_textual_summary_internal(root, feature_table), columns=columns, filesystem=root.fs)
    return table.to_pandas()


def list_textual_summary_tables(root: KGRoot) -> list[str]:
    directory = root._join("features")
    if not directory or not root.fs.exists(directory):
        return []
    stems: list[str] = []
    for entry in root.fs.ls(directory, detail=True):
        if entry.get("type") != "file":
            continue
        name = entry.get("name") or ""
        stem = posixpath.splitext(posixpath.basename(name))[0]
        if name.endswith(".parquet") and stem in _TEXTUAL_SUMMARY_TABLE_TYPES:
            stems.append(stem)
    return sorted(stems)
