"""Normalize underscore-form ontology IDs in canonical KG Parquets.

This is intentionally a bounded, explicit utility: it rewrites only selected
node files and only edge endpoint columns whose endpoint type is selected.
Use it scratch-first, validate the scratch output, then promote to canonical.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .kg_ids import normalize_ontology_curie


DEFAULT_NODE_TYPES = ("disease", "cell_type")
DEFAULT_BATCH_SIZE = 250_000


@dataclass(frozen=True)
class FileNormalizationReport:
    kind: str
    name: str
    input_rows: int
    output_rows: int
    changed_values: int
    duplicate_rows_removed: int
    output_path: str | None = None


def normalize_value(value: object) -> str | None:
    """Normalize one ontology-like value to a canonical CURIE if supported."""

    return normalize_ontology_curie(value)


def _normalize_series(series: pd.Series) -> tuple[pd.Series, int]:
    original = series.astype("string")
    normalized = original.map(normalize_value).astype("string")
    changed = int((original.fillna("<NA>") != normalized.fillna("<NA>")).sum())
    return normalized, changed


def _write_frame(df: pd.DataFrame, output_path: Path, *, schema: pa.Schema | None = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if schema is not None:
        schema = pa.schema(
            [
                pa.field(field.name, pa.string() if pa.types.is_null(field.type) else field.type, field.nullable)
                for field in schema
            ],
            metadata=schema.metadata,
        )
    table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
    pq.write_table(table, output_path)


def normalize_node_file(
    input_path: Path,
    output_path: Path,
    *,
    node_type: str,
) -> FileNormalizationReport:
    """Normalize ID-like columns in one node parquet file."""

    parquet_file = pq.ParquetFile(input_path)
    schema = parquet_file.schema_arrow
    df = parquet_file.read().to_pandas()
    input_rows = len(df)
    changed = 0

    for column in df.columns:
        if column == "id" or column.endswith("_id") or column.endswith("_ids"):
            normalized, column_changed = _normalize_series(df[column])
            df[column] = normalized
            changed += column_changed

    # Collisions can occur when a file contains both MONDO:... and MONDO_...
    # forms. Keep the last row, matching kg_storage.write_nodes semantics.
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["id"], keep="last").reset_index(drop=True)
    _write_frame(df, output_path, schema=schema)
    return FileNormalizationReport(
        kind="node",
        name=node_type,
        input_rows=input_rows,
        output_rows=len(df),
        changed_values=changed,
        duplicate_rows_removed=before_dedup - len(df),
        output_path=str(output_path),
    )


def _edge_endpoint_columns_to_normalize(df: pd.DataFrame, node_types: set[str]) -> list[str]:
    columns: list[str] = []
    if "x_type" in df and "x_id" in df and df["x_type"].astype(str).isin(node_types).any():
        columns.append("x_id")
    if "y_type" in df and "y_id" in df and df["y_type"].astype(str).isin(node_types).any():
        columns.append("y_id")
    return columns


def normalize_edge_file(
    input_path: Path,
    output_path: Path,
    *,
    relation: str,
    node_types: set[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> FileNormalizationReport:
    """Normalize selected endpoint IDs in one edge parquet file."""

    parquet_file = pq.ParquetFile(input_path)
    schema = parquet_file.schema_arrow
    frames: list[pd.DataFrame] = []
    changed = 0
    input_rows = parquet_file.metadata.num_rows

    for batch in parquet_file.iter_batches(batch_size=batch_size):
        df = batch.to_pandas()
        for column in _edge_endpoint_columns_to_normalize(df, node_types):
            mask = df[f"{column[0]}_type"].astype(str).isin(node_types)
            normalized, column_changed = _normalize_series(df.loc[mask, column])
            df.loc[mask, column] = normalized
            changed += column_changed
        frames.append(df)

    output = pd.concat(frames, ignore_index=True) if frames else parquet_file.read().to_pandas()
    before_dedup = len(output)
    output = output.drop_duplicates().reset_index(drop=True)
    _write_frame(output, output_path, schema=schema)
    return FileNormalizationReport(
        kind="edge",
        name=relation,
        input_rows=input_rows,
        output_rows=len(output),
        changed_values=changed,
        duplicate_rows_removed=before_dedup - len(output),
        output_path=str(output_path),
    )


def _edge_mentions_node_type(path: Path, node_types: set[str]) -> bool:
    parquet_file = pq.ParquetFile(path)
    if parquet_file.metadata.num_rows == 0:
        return False
    for batch in parquet_file.iter_batches(columns=["x_type", "y_type"], batch_size=DEFAULT_BATCH_SIZE):
        df = batch.to_pandas()
        if df["x_type"].astype(str).isin(node_types).any() or df["y_type"].astype(str).isin(node_types).any():
            return True
    return False


def normalize_kg(
    input_root: Path,
    output_root: Path,
    *,
    node_types: tuple[str, ...] = DEFAULT_NODE_TYPES,
    copy_unchanged: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[FileNormalizationReport]:
    """Normalize affected KG files from *input_root* into *output_root*."""

    selected = set(node_types)
    reports: list[FileNormalizationReport] = []
    output_root.mkdir(parents=True, exist_ok=True)

    if copy_unchanged:
        for subdir in ("nodes", "edges", "metadata"):
            src = input_root / subdir
            dst = output_root / subdir
            if src.exists() and not dst.exists():
                shutil.copytree(src, dst)

    for node_type in node_types:
        input_path = input_root / "nodes" / f"{node_type}.parquet"
        if input_path.exists():
            reports.append(
                normalize_node_file(
                    input_path,
                    output_root / "nodes" / f"{node_type}.parquet",
                    node_type=node_type,
                )
            )

    edge_dir = input_root / "edges"
    for input_path in sorted(edge_dir.glob("*.parquet")):
        relation = input_path.stem
        if _edge_mentions_node_type(input_path, selected):
            reports.append(
                normalize_edge_file(
                    input_path,
                    output_root / "edges" / input_path.name,
                    relation=relation,
                    node_types=selected,
                    batch_size=batch_size,
                )
            )

    return reports


def _to_jsonable(reports: list[FileNormalizationReport]) -> dict[str, Any]:
    return {
        "files": [asdict(report) for report in reports],
        "totals": {
            "files": len(reports),
            "input_rows": sum(report.input_rows for report in reports),
            "output_rows": sum(report.output_rows for report in reports),
            "changed_values": sum(report.changed_values for report in reports),
            "duplicate_rows_removed": sum(report.duplicate_rows_removed for report in reports),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--node-type", action="append", dest="node_types", choices=DEFAULT_NODE_TYPES)
    parser.add_argument("--copy-unchanged", action="store_true")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    reports = normalize_kg(
        args.input_root,
        args.output_root,
        node_types=tuple(args.node_types or DEFAULT_NODE_TYPES),
        copy_unchanged=args.copy_unchanged,
        batch_size=args.batch_size,
    )
    payload = _to_jsonable(reports)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Normalized {payload['totals']['files']} files")
        for report in reports:
            print(
                f"  {report.kind}/{report.name}: rows {report.input_rows:,}->{report.output_rows:,}, "
                f"changed_values={report.changed_values:,}, duplicates_removed={report.duplicate_rows_removed:,}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
