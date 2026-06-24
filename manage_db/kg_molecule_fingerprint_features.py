"""Helpers for staged molecule fingerprint feature tables.

Molecule fingerprints are model/input features, not KG assertions. They live
under ``features/`` and must carry deterministic fingerprint parameters plus
source/provenance metadata so canonical promotion can be reviewed separately.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
from dataclasses import dataclass
from typing import Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .kg_schema import NodeType
from .kg_storage import KGRoot, _atomic_write

MOLECULE_FINGERPRINT_TABLE = "molecule_fingerprint"

MOLECULE_FINGERPRINT_PARQUET_COLUMNS: list[tuple[str, pa.DataType, str]] = [
    ("feature_key", pa.string(), "stable key table|node_id|source|source_record_id|fingerprint_kind|radius|n_bits|use_chirality"),
    ("feature_table", pa.string(), "molecule_fingerprint"),
    ("node_id", pa.string(), "canonical KG molecule node id"),
    ("node_type", pa.string(), "molecule"),
    ("fingerprint_kind", pa.string(), "morgan_binary / ECFP-like Morgan bit fingerprint"),
    ("fingerprint_format", pa.string(), "sparse_on_bits_uint16_list"),
    ("on_bits", pa.list_(pa.int32()), "sorted on-bit indices, each 0 <= bit < n_bits"),
    ("n_bits", pa.int64(), "fingerprint bit vector size"),
    ("radius", pa.int64(), "Morgan fingerprint radius"),
    ("use_chirality", pa.bool_(), "whether chirality is included"),
    ("use_bond_types", pa.bool_(), "whether bond types are included"),
    ("input_smiles", pa.string(), "input SMILES from the molecule node table"),
    ("canonical_smiles_rdkit", pa.string(), "RDKit canonical SMILES after parse/sanitize"),
    ("input_smiles_field", pa.string(), "source node column, e.g. nodes/molecule.parquet.smiles"),
    ("inchikey", pa.string(), "molecule node InChIKey when present"),
    ("source", pa.string(), "source system / node metadata source"),
    ("source_dataset", pa.string(), "source table/dataset used for structures"),
    ("source_record_id", pa.string(), "stable source record id, usually molecule node id"),
    ("source_release", pa.string(), "KG/source release used to read molecule nodes"),
    ("rdkit_version", pa.string(), "RDKit version used for canonicalization/fingerprinting"),
    ("invalid_smiles_policy", pa.string(), "skip_with_report"),
    ("salt_mixture_policy", pa.string(), "fingerprint_input_as_is_record_component_count"),
    ("component_count", pa.int64(), "number of disconnected molecule components parsed by RDKit"),
    ("provenance", pa.string(), "node path, builder command/context, and structure-field provenance"),
    ("license", pa.string(), "source license/terms label"),
    ("citation", pa.string(), "source citation/attribution text"),
    ("created_at", pa.string(), "ingestion timestamp"),
    ("fingerprint_sha256", pa.string(), "SHA-256 of deterministic serialized sparse indices and parameters"),
]

_STRING_COLUMNS = {name for name, typ, _ in MOLECULE_FINGERPRINT_PARQUET_COLUMNS if pa.types.is_string(typ)}
_REQUIRED_COLUMNS = [
    "feature_table",
    "node_id",
    "node_type",
    "fingerprint_kind",
    "fingerprint_format",
    "on_bits",
    "n_bits",
    "radius",
    "use_chirality",
    "use_bond_types",
    "input_smiles",
    "canonical_smiles_rdkit",
    "input_smiles_field",
    "source",
    "source_dataset",
    "source_record_id",
    "source_release",
    "rdkit_version",
    "invalid_smiles_policy",
    "salt_mixture_policy",
    "provenance",
    "license",
    "citation",
    "created_at",
]
_DEDUP_COLUMNS = [
    "feature_table",
    "node_id",
    "source",
    "source_dataset",
    "source_record_id",
    "fingerprint_kind",
    "radius",
    "n_bits",
    "use_chirality",
]

SOURCE_POLICY: dict[str, dict[str, str]] = {
    "ChEMBL": {
        "decision": "allow_with_attribution",
        "license": "CC BY-SA 3.0",
        "reason": "ChEMBL structures are open with attribution/share-alike; preserve molecule ID/release and upstream source context.",
    },
    "OpenTargets": {
        "decision": "allow_with_attribution_if_upstream_source_clear",
        "license": "CC BY 4.0 / upstream source attribution",
        "reason": "Open Targets drug molecule metadata is open; retain upstream ChEMBL/OpenTargets attribution.",
    },
}


@dataclass(frozen=True)
class MoleculeFingerprintValidation:
    rows: int
    unique_nodes: int
    duplicate_rows_removed: int
    empty_fingerprint_rows: int
    invalid_on_bit_rows: int
    nodes_not_in_endpoint: int
    endpoint_nodes: int | None
    coverage_fraction: float | None
    multi_component_rows: int
    min_on_bits: int | None
    max_on_bits: int | None

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "rows": self.rows,
            "unique_nodes": self.unique_nodes,
            "duplicate_rows_removed": self.duplicate_rows_removed,
            "empty_fingerprint_rows": self.empty_fingerprint_rows,
            "invalid_on_bit_rows": self.invalid_on_bit_rows,
            "nodes_not_in_endpoint": self.nodes_not_in_endpoint,
            "endpoint_nodes": self.endpoint_nodes,
            "coverage_fraction": self.coverage_fraction,
            "multi_component_rows": self.multi_component_rows,
            "min_on_bits": self.min_on_bits,
            "max_on_bits": self.max_on_bits,
        }


def molecule_fingerprint_schema() -> pa.Schema:
    return pa.schema([pa.field(name, typ, nullable=True) for name, typ, _ in MOLECULE_FINGERPRINT_PARQUET_COLUMNS])


def molecule_fingerprint_path(root: KGRoot) -> str:
    return root._as_public("features", f"{MOLECULE_FINGERPRINT_TABLE}.parquet")


def _molecule_fingerprint_internal(root: KGRoot) -> str:
    return root._join("features", f"{MOLECULE_FINGERPRINT_TABLE}.parquet")


def source_policy_audit() -> pd.DataFrame:
    rows = []
    for source, values in sorted(SOURCE_POLICY.items()):
        row = {"source": source}
        row.update(values)
        rows.append(row)
    return pd.DataFrame(rows)


def fingerprint_sha256(
    on_bits: list[int],
    *,
    fingerprint_kind: str,
    radius: int,
    n_bits: int,
    use_chirality: bool,
    use_bond_types: bool,
) -> str:
    payload = {
        "fingerprint_kind": fingerprint_kind,
        "fingerprint_format": "sparse_on_bits_uint16_list",
        "on_bits": sorted(int(bit) for bit in on_bits),
        "radius": int(radius),
        "n_bits": int(n_bits),
        "use_chirality": bool(use_chirality),
        "use_bond_types": bool(use_bond_types),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _coerce_frame(table: pa.Table | pd.DataFrame) -> pd.DataFrame:
    if isinstance(table, pa.Table):
        df = table.to_pandas()
    else:
        df = table.copy()
    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"features/{MOLECULE_FINGERPRINT_TABLE} missing required columns: {missing}")
    if not df.empty and set(df["feature_table"].astype(str)) != {MOLECULE_FINGERPRINT_TABLE}:
        raise ValueError(f"features/{MOLECULE_FINGERPRINT_TABLE} contains rows for another feature table")
    if not df.empty:
        bad_type = sorted(set(df.loc[df["node_type"].astype(str) != NodeType.MOLECULE.value, "node_type"].astype(str)))
        if bad_type:
            raise ValueError(f"features/{MOLECULE_FINGERPRINT_TABLE} has invalid node_type values: {bad_type}")
    for name, typ, _ in MOLECULE_FINGERPRINT_PARQUET_COLUMNS:
        if name not in df.columns:
            if pa.types.is_integer(typ):
                df[name] = 0
            elif pa.types.is_boolean(typ):
                df[name] = False
            elif pa.types.is_list(typ):
                df[name] = [[] for _ in range(len(df))]
            else:
                df[name] = ""
    df = df[[name for name, _, _ in MOLECULE_FINGERPRINT_PARQUET_COLUMNS]].reset_index(drop=True)
    for col in _STRING_COLUMNS:
        df[col] = df[col].fillna("").astype(str).str.strip()
    for col in ["n_bits", "radius", "component_count"]:
        df[col] = pd.to_numeric(df[col], errors="raise").astype("int64")
    for col in ["use_chirality", "use_bond_types"]:
        df[col] = df[col].astype(bool)
    df["on_bits"] = df["on_bits"].map(lambda bits: sorted(int(bit) for bit in (bits or [])))
    df["fingerprint_sha256"] = df.apply(
        lambda row: fingerprint_sha256(
            row["on_bits"],
            fingerprint_kind=str(row["fingerprint_kind"]),
            radius=int(row["radius"]),
            n_bits=int(row["n_bits"]),
            use_chirality=bool(row["use_chirality"]),
            use_bond_types=bool(row["use_bond_types"]),
        ),
        axis=1,
    )
    key_parts = [
        df["feature_table"].astype(str),
        df["node_id"].astype(str),
        df["source"].astype(str),
        df["source_record_id"].astype(str),
        df["fingerprint_kind"].astype(str),
        df["radius"].astype(str),
        df["n_bits"].astype(str),
        df["use_chirality"].astype(str),
    ]
    df["feature_key"] = key_parts[0]
    for part in key_parts[1:]:
        df["feature_key"] = df["feature_key"] + "|" + part
    return df


def validate_molecule_fingerprints(
    table: pa.Table | pd.DataFrame,
    *,
    endpoint_node_ids: set[str] | None = None,
) -> tuple[pd.DataFrame, MoleculeFingerprintValidation]:
    df = _coerce_frame(table)
    before = len(df)
    df = df.drop_duplicates(subset=_DEDUP_COLUMNS, keep="last").reset_index(drop=True)
    empty = int(df["on_bits"].map(len).eq(0).sum())
    if empty:
        raise ValueError(f"features/{MOLECULE_FINGERPRINT_TABLE} contains {empty} rows with empty/all-zero fingerprints")
    invalid = int(
        df.apply(lambda row: any(bit < 0 or bit >= int(row["n_bits"]) for bit in row["on_bits"]), axis=1).sum()
    )
    if invalid:
        raise ValueError(f"features/{MOLECULE_FINGERPRINT_TABLE} contains {invalid} rows with on_bits outside [0, n_bits)")
    nodes_not_in_endpoint = 0
    endpoint_nodes = None
    coverage_fraction = None
    if endpoint_node_ids is not None:
        endpoint_nodes = len(endpoint_node_ids)
        node_ids = set(df["node_id"].astype(str))
        nodes_not_in_endpoint = len(node_ids - endpoint_node_ids)
        if nodes_not_in_endpoint:
            examples = sorted(node_ids - endpoint_node_ids)[:5]
            raise ValueError(f"features/{MOLECULE_FINGERPRINT_TABLE} has node_ids not present in endpoint nodes: {examples}")
        coverage_fraction = (len(node_ids) / endpoint_nodes) if endpoint_nodes else 0.0
    on_bit_counts = df["on_bits"].map(len)
    validation = MoleculeFingerprintValidation(
        rows=len(df),
        unique_nodes=int(df["node_id"].nunique()),
        duplicate_rows_removed=before - len(df),
        empty_fingerprint_rows=empty,
        invalid_on_bit_rows=invalid,
        nodes_not_in_endpoint=nodes_not_in_endpoint,
        endpoint_nodes=endpoint_nodes,
        coverage_fraction=coverage_fraction,
        multi_component_rows=int(df["component_count"].gt(1).sum()),
        min_on_bits=int(on_bit_counts.min()) if len(df) else None,
        max_on_bits=int(on_bit_counts.max()) if len(df) else None,
    )
    return df, validation


def write_molecule_fingerprints(
    root: KGRoot,
    table: pa.Table | pd.DataFrame,
    *,
    mode: Literal["overwrite", "append"] = "overwrite",
    endpoint_node_ids: set[str] | None = None,
) -> MoleculeFingerprintValidation:
    df, validation = validate_molecule_fingerprints(table, endpoint_node_ids=endpoint_node_ids)
    combined = df
    internal = _molecule_fingerprint_internal(root)
    if mode == "append" and root.fs.exists(internal):
        existing = read_molecule_fingerprints(root)
        combined, validation = validate_molecule_fingerprints(
            pd.concat([existing, df], ignore_index=True), endpoint_node_ids=endpoint_node_ids
        )
    arrow_table = pa.Table.from_pandas(combined, schema=molecule_fingerprint_schema(), preserve_index=False)
    _atomic_write(root, internal, arrow_table)
    return validation


def read_molecule_fingerprints(root: KGRoot, columns: list[str] | None = None) -> pd.DataFrame:
    table = pq.read_table(_molecule_fingerprint_internal(root), columns=columns, filesystem=root.fs)
    return table.to_pandas()


def list_molecule_fingerprint_tables(root: KGRoot) -> list[str]:
    directory = root._join("features")
    if not directory or not root.fs.exists(directory):
        return []
    stems: list[str] = []
    for entry in root.fs.ls(directory, detail=True):
        if entry.get("type") != "file":
            continue
        name = entry.get("name") or ""
        stem = posixpath.splitext(posixpath.basename(name))[0]
        if name.endswith(".parquet") and stem == MOLECULE_FINGERPRINT_TABLE:
            stems.append(stem)
    return sorted(stems)
