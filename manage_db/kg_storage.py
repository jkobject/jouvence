"""Unified Parquet storage interface for the TxGNN knowledge graph.

This module provides a backend-agnostic read/write layer that supports both
local filesystems and Google Cloud Storage via ``fsspec``.  All schemas are
derived from :mod:`manage_db.kg_schema`, ensuring a single source of truth for
column names and required data types.
"""

from __future__ import annotations

import json
import os
import posixpath
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal

import fsspec
from fsspec.core import url_to_fs
from fsspec.spec import AbstractFileSystem
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .credibility import dedup_edges
from .kg_schema import EDGE_PARQUET_COLUMNS, NODE_TYPES, NodeType


_ROW_GROUP_BYTES = 256 * 1024 * 1024  # 256 MB target row-group size


def _normalize_uri(uri: str) -> str:
    if "://" in uri:
        return uri.rstrip("/")
    return str(posixpath.normpath(os.path.abspath(uri))).rstrip("/")


def _compute_row_group_size(table: pa.Table) -> int | None:
    if table.num_rows == 0:
        return None
    total_bytes = table.nbytes or 0
    if total_bytes <= 0:
        return None
    approx_row_bytes = max(total_bytes / table.num_rows, 1)
    rows = int(_ROW_GROUP_BYTES / approx_row_bytes)
    return max(rows, 1)


def open_kg_root(uri: str) -> "KGRoot":
    """Open a KG root for read/write."""

    canonical = _normalize_uri(uri)
    fs, path = url_to_fs(canonical)
    path = path.rstrip("/")
    if path and not fs.exists(path):
        fs.makedirs(path, exist_ok=True)
    return KGRoot(uri=canonical, fs=fs, _path=path)


@dataclass(slots=True)
class KGRoot:
    """Represents a concrete KG storage root."""

    uri: str
    fs: AbstractFileSystem
    _path: str

    def _join(self, *parts: str) -> str:
        clean = [p.strip("/") for p in parts if p]
        rel = "/".join(clean)
        if not rel:
            return self._path
        if not self._path:
            return rel
        return posixpath.join(self._path, rel)

    def _as_public(self, *parts: str) -> str:
        clean = [p.strip("/") for p in parts if p]
        rel = "/".join(clean)
        if not rel:
            return self.uri
        return f"{self.uri.rstrip('/')}/{rel}"

    def _relative(self, sub: str) -> str:
        candidate = sub.strip("/")
        prefix = self.uri.rstrip("/") + "/"
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix) :]
        return candidate

    def node_path(self, node_type: str) -> str:
        return self._as_public("nodes", f"{node_type}.parquet")

    def edge_path(self, relation: str) -> str:
        return self._as_public("edges", f"{relation}.parquet")

    def metadata_path(self, name: str = "provenance.json") -> str:
        return self._as_public("metadata", name)

    def list_nodes(self) -> list[str]:
        return _list_parquet_stems(self.fs, self._join("nodes"))

    def list_edges(self) -> list[str]:
        return _list_parquet_stems(self.fs, self._join("edges"))

    def exists(self, sub: str) -> bool:
        rel = self._relative(sub)
        return self.fs.exists(self._join(rel))

    # Internal helpers -------------------------------------------------

    def _ensure_dir(self, subdir: str) -> None:
        rel = self._relative(subdir)
        path = self._join(rel)
        if path:
            self.fs.makedirs(path, exist_ok=True)

    def _node_internal(self, node_type: str) -> str:
        return self._join("nodes", f"{node_type}.parquet")

    def _edge_internal(self, relation: str) -> str:
        return self._join("edges", f"{relation}.parquet")

    def _metadata_internal(self, name: str) -> str:
        return self._join("metadata", name)


def _list_parquet_stems(fs: AbstractFileSystem, directory: str) -> list[str]:
    if not directory or not fs.exists(directory):
        return []
    entries = fs.ls(directory, detail=True)
    stems: list[str] = []
    for entry in entries:
        if entry.get("type") != "file":
            continue
        name = entry.get("name") or ""
        if not name.endswith(".parquet"):
            continue
        stems.append(posixpath.splitext(posixpath.basename(name))[0])
    return sorted(stems)


def node_schema(node_type: str) -> pa.Schema:
    nt = NodeType(node_type)
    info = NODE_TYPES[nt]
    fields = [pa.field("id", pa.string(), nullable=False)]
    for col in info.xref_columns:
        fields.append(pa.field(col, pa.string(), nullable=True))
    return pa.schema(fields)


def edge_schema() -> pa.Schema:
    fields = []
    for name, _ in EDGE_PARQUET_COLUMNS:
        if name == "credibility":
            fields.append(pa.field(name, pa.int64(), nullable=False))
        else:
            fields.append(pa.field(name, pa.string(), nullable=False))
    return pa.schema(fields)


def write_nodes(
    root: KGRoot,
    node_type: str,
    table: pa.Table | pd.DataFrame,
    *,
    mode: Literal["overwrite", "append"] = "overwrite",
) -> int:
    nt = NodeType(node_type)
    df = _coerce_dataframe(table)
    df = df.drop(columns=["node_type"], errors="ignore").reset_index(drop=True)

    required = ["id", *NODE_TYPES[nt].xref_columns]
    _ensure_columns(df, required, context=f"nodes/{node_type}")

    for col in required:
        df[col] = df[col].astype("string[pyarrow]")

    if mode == "append" and root.exists(root.node_path(node_type)):
        existing = read_nodes(root, node_type)
        df = pd.concat([existing, df], ignore_index=True)
        df = df.drop_duplicates(subset=["id"], keep="last")

    arrow_table = pa.Table.from_pandas(df, preserve_index=False)
    _atomic_write(root, root._node_internal(node_type), arrow_table)
    return len(df)


def write_edges(
    root: KGRoot,
    relation: str,
    table: pa.Table | pd.DataFrame,
    *,
    mode: Literal["overwrite", "append"] = "overwrite",
) -> int:
    df = _coerce_dataframe(table).reset_index(drop=True)

    required = [name for name, _ in EDGE_PARQUET_COLUMNS]
    _ensure_columns(df, required, context=f"edges/{relation}")

    string_cols = [c for c in required if c != "credibility"]
    for col in string_cols:
        df[col] = df[col].astype("string[pyarrow]")
    df["credibility"] = pd.to_numeric(df["credibility"], errors="raise").astype("int64")

    if mode == "append" and root.exists(root.edge_path(relation)):
        existing = read_edges(root, relation)
        df = pd.concat([existing, df], ignore_index=True)
        df = dedup_edges(df)

    arrow_table = pa.Table.from_pandas(df, preserve_index=False)
    _atomic_write(root, root._edge_internal(relation), arrow_table)
    return len(df)


def read_nodes(root: KGRoot, node_type: str, columns: list[str] | None = None) -> pd.DataFrame:
    path = root._node_internal(node_type)
    table = pq.read_table(path, columns=columns, filesystem=root.fs)
    return table.to_pandas()


def read_edges(root: KGRoot, relation: str, columns: list[str] | None = None) -> pd.DataFrame:
    path = root._edge_internal(relation)
    table = pq.read_table(path, columns=columns, filesystem=root.fs)
    return table.to_pandas()


def write_provenance(
    root: KGRoot,
    *,
    sources: dict,
    code_sha: str,
    code_version: str,
    extra: dict | None = None,
) -> str:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "code_sha": code_sha,
        "code_version": code_version,
        "sources": sources,
    }
    if extra:
        payload.update(extra)

    metadata_dir = root._metadata_internal("")
    if metadata_dir:
        root.fs.makedirs(metadata_dir, exist_ok=True)
    path = root._metadata_internal("provenance.json")
    tmp_path = f"{path}.tmp.{os.getpid()}_{uuid.uuid4().hex}"
    with root.fs.open(tmp_path, "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    _rename(root.fs, tmp_path, path)
    return root.metadata_path()


def read_provenance(root: KGRoot) -> dict:
    path = root._metadata_internal("provenance.json")
    with root.fs.open(path, "r") as fh:
        return json.load(fh)


def finalize_kg_export(
    root: KGRoot,
    *,
    sources: dict,
    code_version: str,
    code_sha: str | None = None,
) -> None:
    node_counts, node_sizes = _collect_counts(root.list_nodes(), root._node_internal, root.fs)
    edge_counts, edge_sizes = _collect_counts(root.list_edges(), root._edge_internal, root.fs)

    row_counts = {
        "nodes": node_counts,
        "edges": edge_counts,
        "total_rows": sum(node_counts.values()) + sum(edge_counts.values()),
        "total_bytes": sum(node_sizes.values()) + sum(edge_sizes.values()),
    }

    extra = {"row_counts": row_counts}
    write_provenance(
        root,
        sources=sources,
        code_sha=code_sha or "unknown",
        code_version=code_version,
        extra=extra,
    )

    summary_lines = [
        "# KG Export Summary",
        f"Root: {root.uri}",
        f"Code version: {code_version}",
        f"Code SHA: {code_sha or 'unknown'}",
        "",
        "## Node files",
    ]
    for name in sorted(node_counts):
        summary_lines.append(
            f"- {name}: {node_counts[name]} rows ({_format_bytes(node_sizes[name])})"
        )
    summary_lines.append("")
    summary_lines.append("## Edge files")
    for name in sorted(edge_counts):
        summary_lines.append(
            f"- {name}: {edge_counts[name]} rows ({_format_bytes(edge_sizes[name])})"
        )
    summary_lines.append("")
    summary_lines.append(
        f"Total rows: {row_counts['total_rows']} ({_format_bytes(row_counts['total_bytes'])})"
    )

    metadata_dir = root._metadata_internal("")
    if metadata_dir:
        root.fs.makedirs(metadata_dir, exist_ok=True)
    summary_path = root._metadata_internal("SUMMARY.md")
    tmp_path = f"{summary_path}.tmp.{os.getpid()}_{uuid.uuid4().hex}"
    with root.fs.open(tmp_path, "w") as fh:
        fh.write("\n".join(summary_lines) + "\n")
    _rename(root.fs, tmp_path, summary_path)


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _coerce_dataframe(table: pa.Table | pd.DataFrame) -> pd.DataFrame:
    if isinstance(table, pd.DataFrame):
        return table.copy()
    return table.to_pandas()


def _ensure_columns(df: pd.DataFrame, required: Iterable[str], *, context: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        pretty = ", ".join(sorted(missing))
        raise ValueError(f"{context} missing required columns: {pretty}")


def _atomic_write(root: KGRoot, internal_path: str, table: pa.Table) -> None:
    parent = posixpath.dirname(internal_path)
    if parent:
        root.fs.makedirs(parent, exist_ok=True)

    tmp_path = f"{internal_path}.tmp.{os.getpid()}_{uuid.uuid4().hex}"
    row_group_size = _compute_row_group_size(table)
    try:
        with root.fs.open(tmp_path, "wb") as fh:
            pq.write_table(
                table,
                fh,
                compression="snappy",
                write_statistics=True,
                row_group_size=row_group_size,
            )
        _rename(root.fs, tmp_path, internal_path)
    finally:
        if root.fs.exists(tmp_path):
            root.fs.rm(tmp_path)


def _rename(fs: AbstractFileSystem, src: str, dst: str) -> None:
    if fs.exists(dst):
        fs.rm(dst)
    try:
        fs.rename(src, dst)
    except AttributeError:
        fs.mv(src, dst)


def _collect_counts(names: list[str], resolver, fs: AbstractFileSystem) -> tuple[dict[str, int], dict[str, int]]:
    counts: dict[str, int] = {}
    sizes: dict[str, int] = {}
    for name in names:
        internal = resolver(name)
        with fs.open(internal, "rb") as fh:
            parquet_file = pq.ParquetFile(fh)
            counts[name] = parquet_file.metadata.num_rows
        info = fs.info(internal)
        sizes[name] = int(info.get("size", 0))
    return counts, sizes


def _format_bytes(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return f"{size:.2f} TB"
