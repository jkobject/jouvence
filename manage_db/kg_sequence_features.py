"""Helpers for staged node sequence feature tables.

Sequence features are model/input features, not KG assertions. They live under
``features/`` and carry per-row source/provenance/license metadata so canonical
promotion can be reviewed independently from the core KG graph.
"""

from __future__ import annotations

import hashlib
import posixpath
from dataclasses import dataclass
from typing import Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .kg_schema import NodeType
from .kg_storage import KGRoot, _atomic_write

SEQUENCE_PARQUET_COLUMNS: list[tuple[str, pa.DataType, str]] = [
    ("feature_key", pa.string(), "stable key table|node_id|source|source_record_id|sequence_kind"),
    ("feature_table", pa.string(), "sequence feature table name, e.g. protein_sequence"),
    ("node_id", pa.string(), "canonical KG node id"),
    ("node_type", pa.string(), "KG NodeType value"),
    ("sequence_kind", pa.string(), "amino_acid, cdna, genomic_interval, mature_mirna, precursor_mirna, etc."),
    ("sequence", pa.string(), "plain sequence payload, uppercase, no whitespace"),
    ("length", pa.int64(), "sequence length in residues/bases"),
    ("alphabet", pa.string(), "validated alphabet label: protein_iupac or dna_iupac"),
    ("source", pa.string(), "source system, e.g. Ensembl, UniProtKB, GENCODE"),
    ("source_dataset", pa.string(), "source FASTA/table/API"),
    ("source_record_id", pa.string(), "stable source FASTA/API record id"),
    ("source_release", pa.string(), "source release/version/date"),
    ("provenance", pa.string(), "source URL/path and extraction details"),
    ("license", pa.string(), "source license/terms label"),
    ("citation", pa.string(), "source citation or attribution text"),
    ("created_at", pa.string(), "ingestion timestamp"),
    ("checksum_sha256", pa.string(), "SHA-256 checksum of uppercase sequence"),
]

_SEQUENCE_TABLE_TYPES: dict[str, NodeType] = {
    "protein_sequence": NodeType.PROTEIN,
    "transcript_sequence": NodeType.TRANSCRIPT,
}

_SEQUENCE_KIND_BY_TABLE: dict[str, str] = {
    "protein_sequence": "amino_acid",
    "transcript_sequence": "cdna",
}

_REQUIRED_COLUMNS = [
    "feature_table",
    "node_id",
    "node_type",
    "sequence_kind",
    "sequence",
    "alphabet",
    "source",
    "source_dataset",
    "source_record_id",
    "source_release",
    "provenance",
    "license",
    "citation",
    "created_at",
]
_STRING_COLUMNS = {name for name, typ, _ in SEQUENCE_PARQUET_COLUMNS if pa.types.is_string(typ)}
_DEDUP_COLUMNS = ["feature_table", "node_id", "source", "source_dataset", "source_record_id", "sequence_kind"]
_ALPHABETS: dict[str, set[str]] = {
    # Conservative: no stop codon '*' in feature rows; ambiguous X/U/O/B/Z/J allowed for real protein FASTA records.
    "protein_iupac": set("ACDEFGHIKLMNPQRSTVWYXBZUOJ"),
    # IUPAC DNA ambiguity symbols; U is intentionally excluded for cDNA DNA FASTA.
    "dna_iupac": set("ACGTRYSWKMBDHVN"),
}

SOURCE_POLICY: dict[str, dict[str, str]] = {
    "Ensembl": {
        "decision": "allow_with_attribution",
        "license": "EMBL-EBI open data / attribution",
        "reason": "Ensembl FASTA downloads are open for reuse with attribution; preserve release and FASTA provenance.",
    },
    "GENCODE": {
        "decision": "allow_with_attribution",
        "license": "EMBL-EBI open data / attribution",
        "reason": "GENCODE sequence FASTA is distributed through EMBL-EBI/Gencode terms; preserve release and source URL/path.",
    },
    "UniProtKB": {
        "decision": "allow_with_attribution",
        "license": "CC BY 4.0",
        "reason": "UniProtKB sequences are reusable under CC BY 4.0; preserve accession, release and attribution.",
    },
    "miRBase": {
        "decision": "defer_until_node_ids_and_terms_reviewed",
        "license": "open academic resource / exact redistribution terms require review",
        "reason": "Use only after canonical/staged miRNA node identifiers and exact mature/precursor mapping policy are reviewed.",
    },
}


@dataclass(frozen=True)
class SequenceValidation:
    rows: int
    unique_nodes: int
    duplicate_rows_removed: int
    missing_sequence_rows: int
    invalid_alphabet_rows: int
    over_max_length_rows: int
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
            "missing_sequence_rows": self.missing_sequence_rows,
            "invalid_alphabet_rows": self.invalid_alphabet_rows,
            "over_max_length_rows": self.over_max_length_rows,
            "nodes_not_in_endpoint": self.nodes_not_in_endpoint,
            "endpoint_nodes": self.endpoint_nodes,
            "coverage_fraction": self.coverage_fraction,
            "min_length": self.min_length,
            "max_length": self.max_length,
        }


def sequence_schema() -> pa.Schema:
    return pa.schema([pa.field(name, typ, nullable=True) for name, typ, _ in SEQUENCE_PARQUET_COLUMNS])


def sequence_path(root: KGRoot, feature_table: str) -> str:
    return root._as_public("features", f"{feature_table}.parquet")


def _sequence_internal(root: KGRoot, feature_table: str) -> str:
    return root._join("features", f"{feature_table}.parquet")


def allowed_sequence_tables() -> dict[str, str]:
    return {name: node_type.value for name, node_type in _SEQUENCE_TABLE_TYPES.items()}


def source_policy_audit() -> pd.DataFrame:
    rows = []
    for source, values in sorted(SOURCE_POLICY.items()):
        row = {"source": source}
        row.update(values)
        rows.append(row)
    return pd.DataFrame(rows)


def _coerce_sequence_frame(table: pa.Table | pd.DataFrame, feature_table: str) -> pd.DataFrame:
    if isinstance(table, pa.Table):
        df = table.to_pandas()
    else:
        df = table.copy()

    if feature_table not in _SEQUENCE_TABLE_TYPES:
        raise ValueError(f"unknown sequence feature table: {feature_table}")
    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"features/{feature_table} missing required columns: {missing}")
    if not df.empty and set(df["feature_table"].astype(str)) != {feature_table}:
        raise ValueError(f"features/{feature_table} contains rows for another feature table")

    expected_type = _SEQUENCE_TABLE_TYPES[feature_table].value
    if not df.empty:
        bad_type = sorted(set(df.loc[df["node_type"].astype(str) != expected_type, "node_type"].astype(str)))
        if bad_type:
            raise ValueError(f"features/{feature_table} has invalid node_type values: {bad_type}")

    for name, typ, _ in SEQUENCE_PARQUET_COLUMNS:
        if name not in df.columns:
            df[name] = 0 if pa.types.is_integer(typ) else ""

    df = df[[name for name, _, _ in SEQUENCE_PARQUET_COLUMNS]].reset_index(drop=True)
    for col in _STRING_COLUMNS:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["sequence"] = df["sequence"].str.upper().str.replace(r"\s+", "", regex=True)
    df["length"] = df["sequence"].str.len().astype("int64")
    df["checksum_sha256"] = df["sequence"].map(lambda seq: hashlib.sha256(seq.encode("ascii")).hexdigest())

    key_parts = [
        df["feature_table"].astype(str),
        df["node_id"].astype(str),
        df["source"].astype(str),
        df["source_record_id"].astype(str),
        df["sequence_kind"].astype(str),
    ]
    df["feature_key"] = key_parts[0]
    for part in key_parts[1:]:
        df["feature_key"] = df["feature_key"] + "|" + part

    return df


def _invalid_alphabet_mask(df: pd.DataFrame) -> pd.Series:
    invalid = []
    for _, row in df.iterrows():
        alphabet = str(row["alphabet"])
        allowed = _ALPHABETS.get(alphabet)
        if allowed is None:
            invalid.append(True)
            continue
        invalid.append(bool(set(str(row["sequence"])) - allowed))
    return pd.Series(invalid, index=df.index, dtype=bool)


def validate_sequences(
    table: pa.Table | pd.DataFrame,
    feature_table: str,
    *,
    endpoint_node_ids: set[str] | None = None,
    max_sequence_length: int = 100_000,
) -> tuple[pd.DataFrame, SequenceValidation]:
    """Validate/coerce sequence rows and return de-duplicated rows + stats."""

    df = _coerce_sequence_frame(table, feature_table)
    before = len(df)
    df = df.drop_duplicates(subset=_DEDUP_COLUMNS, keep="last").reset_index(drop=True)

    missing_sequence = int(df["length"].eq(0).sum())
    if missing_sequence:
        raise ValueError(f"features/{feature_table} contains {missing_sequence} rows with empty sequence")

    expected_kind = _SEQUENCE_KIND_BY_TABLE[feature_table]
    bad_kind = sorted(set(df.loc[df["sequence_kind"].astype(str) != expected_kind, "sequence_kind"].astype(str)))
    if bad_kind:
        raise ValueError(f"features/{feature_table} has invalid sequence_kind values: {bad_kind}")

    invalid_mask = _invalid_alphabet_mask(df)
    invalid_alphabet_rows = int(invalid_mask.sum())
    if invalid_alphabet_rows:
        examples = df.loc[invalid_mask, ["source_record_id", "alphabet", "sequence"]].head(3).to_dict("records")
        alphabet = str(df.loc[invalid_mask, "alphabet"].iloc[0]) if invalid_alphabet_rows else "unknown"
        raise ValueError(f"features/{feature_table} contains {invalid_alphabet_rows} invalid {alphabet} sequence rows: {examples}")

    over_max = int(df["length"].gt(max_sequence_length).sum())
    if over_max:
        raise ValueError(f"features/{feature_table} contains {over_max} rows over max_sequence_length={max_sequence_length}")

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

    validation = SequenceValidation(
        rows=len(df),
        unique_nodes=int(df["node_id"].nunique()),
        duplicate_rows_removed=before - len(df),
        missing_sequence_rows=missing_sequence,
        invalid_alphabet_rows=invalid_alphabet_rows,
        over_max_length_rows=over_max,
        nodes_not_in_endpoint=nodes_not_in_endpoint,
        endpoint_nodes=endpoint_nodes,
        coverage_fraction=coverage_fraction,
        min_length=int(df["length"].min()) if len(df) else None,
        max_length=int(df["length"].max()) if len(df) else None,
    )
    return df, validation


def write_sequences(
    root: KGRoot,
    feature_table: str,
    table: pa.Table | pd.DataFrame,
    *,
    mode: Literal["overwrite", "append"] = "overwrite",
    endpoint_node_ids: set[str] | None = None,
    max_sequence_length: int = 100_000,
) -> SequenceValidation:
    df, validation = validate_sequences(
        table, feature_table, endpoint_node_ids=endpoint_node_ids, max_sequence_length=max_sequence_length
    )
    combined = df
    internal = _sequence_internal(root, feature_table)
    if mode == "append" and root.fs.exists(internal):
        existing = read_sequences(root, feature_table)
        combined, validation = validate_sequences(
            pd.concat([existing, df], ignore_index=True),
            feature_table,
            endpoint_node_ids=endpoint_node_ids,
            max_sequence_length=max_sequence_length,
        )
    arrow_table = pa.Table.from_pandas(combined, schema=sequence_schema(), preserve_index=False)
    _atomic_write(root, internal, arrow_table)
    return validation


def read_sequences(root: KGRoot, feature_table: str, columns: list[str] | None = None) -> pd.DataFrame:
    table = pq.read_table(_sequence_internal(root, feature_table), columns=columns, filesystem=root.fs)
    return table.to_pandas()


def list_sequence_tables(root: KGRoot) -> list[str]:
    directory = root._join("features")
    if not directory or not root.fs.exists(directory):
        return []
    stems: list[str] = []
    for entry in root.fs.ls(directory, detail=True):
        if entry.get("type") != "file":
            continue
        name = entry.get("name") or ""
        stem = posixpath.splitext(posixpath.basename(name))[0]
        if name.endswith(".parquet") and stem in _SEQUENCE_TABLE_TYPES:
            stems.append(stem)
    return sorted(stems)
