from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


EMBEDDING_REQUIRED_COLUMNS = {
    "embedding_key",
    "node_id",
    "source_feature_key",
    "source_feature_hash",
    "embedding_dim",
    "embedding",
    "source_row_index",
    "window_count",
}


def read_row_range(path: Path, row_start: int, row_end: int) -> pd.DataFrame:
    """Read [row_start, row_end) from a Parquet file without materializing earlier rows."""
    if row_start < 0 or row_end < row_start:
        raise ValueError(f"invalid row range [{row_start}, {row_end})")
    if row_start == row_end:
        return pd.DataFrame()
    pf = pq.ParquetFile(path)
    batches: list[pa.Table] = []
    absolute = 0
    for batch in pf.iter_batches(batch_size=8192):
        table = pa.Table.from_batches([batch])
        batch_start = absolute
        batch_end = absolute + table.num_rows
        absolute = batch_end
        if batch_end <= row_start:
            continue
        if batch_start >= row_end:
            break
        local_start = max(row_start - batch_start, 0)
        local_end = min(row_end - batch_start, table.num_rows)
        batches.append(table.slice(local_start, local_end - local_start))
    if not batches:
        return pd.DataFrame()
    df = pa.concat_tables(batches).to_pandas()
    df.insert(0, "__source_row_index", range(row_start, row_start + len(df)))
    return df


def part_path(part_dir: Path, row_start: int, row_end: int) -> Path:
    return part_dir / f"part-{row_start:012d}-{row_end:012d}.parquet"


def part_meta_path(part_dir: Path, row_start: int, row_end: int) -> Path:
    return part_dir / f"part-{row_start:012d}-{row_end:012d}.json"


def write_parquet(rows: list[dict[str, Any]], path: Path, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        table = pa.Table.from_pylist(rows)
    else:
        table = pa.Table.from_pandas(pd.DataFrame(columns=columns or []), preserve_index=False)
    pq.write_table(table, path, compression="zstd")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _vectors_ok(df: pd.DataFrame, expected_dim: int) -> dict[str, int]:
    bad_dims = non_finite = all_zero = 0
    if df.empty:
        return {"bad_dims": 0, "non_finite_vectors": 0, "all_zero_vectors": 0}
    for _, row in df.iterrows():
        vector = np.asarray(row["embedding"], dtype=np.float32)
        row_dim = int(row.get("embedding_dim") if row.get("embedding_dim") is not None else expected_dim)
        if len(vector) != expected_dim or row_dim != expected_dim:
            bad_dims += 1
        if not np.isfinite(vector).all():
            non_finite += 1
        if float(np.linalg.norm(vector)) == 0.0:
            all_zero += 1
    return {"bad_dims": bad_dims, "non_finite_vectors": non_finite, "all_zero_vectors": all_zero}


def validate_part_files(
    embedding_path: Path,
    skipped_path: Path,
    meta_path: Path,
    *,
    expected: dict[str, Any],
    expected_dim: int,
    skipped_required_columns: list[str],
) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "embedding_path": str(embedding_path),
        "skipped_path": str(skipped_path),
        "meta_path": str(meta_path),
        "passed": False,
    }
    if not embedding_path.exists() or not skipped_path.exists() or not meta_path.exists():
        checks["missing"] = True
        return checks
    try:
        meta = read_json(meta_path)
        checks["metadata_matches_expected"] = all(meta.get(k) == v for k, v in expected.items())
        df = _read_optional(embedding_path)
        skipped = _read_optional(skipped_path)
        missing_embedding_cols = sorted(EMBEDDING_REQUIRED_COLUMNS - set(df.columns)) if not df.empty else []
        missing_skipped_cols = sorted(set(skipped_required_columns) - set(skipped.columns)) if not skipped.empty else []
        row_start = int(expected["row_start"])
        row_end = int(expected["row_end"])
        covered: list[int] = []
        if "source_row_index" in df.columns:
            covered.extend(int(v) for v in df["source_row_index"].tolist())
        if "row_index" in skipped.columns:
            covered.extend(int(v) for v in skipped["row_index"].tolist())
        expected_rows = list(range(row_start, row_end))
        duplicate_covered_rows = len(covered) - len(set(covered))
        vector_checks = _vectors_ok(df, expected_dim)
        duplicate_embedding_keys = int(df["embedding_key"].duplicated().sum()) if "embedding_key" in df.columns else 0
        duplicate_feature_keys = int(df["source_feature_key"].duplicated().sum()) if "source_feature_key" in df.columns else 0
        checks.update(
            {
                "missing": False,
                "embedding_rows": int(len(df)),
                "skipped_rows": int(len(skipped)),
                "missing_embedding_columns": missing_embedding_cols,
                "missing_skipped_columns": missing_skipped_cols,
                "duplicate_embedding_keys": duplicate_embedding_keys,
                "duplicate_source_feature_keys": duplicate_feature_keys,
                "duplicate_covered_rows": int(duplicate_covered_rows),
                "row_coverage_matches_expected": sorted(covered) == expected_rows,
                **vector_checks,
            }
        )
        checks["passed"] = (
            checks["metadata_matches_expected"]
            and not missing_embedding_cols
            and not missing_skipped_cols
            and duplicate_embedding_keys == 0
            and duplicate_feature_keys == 0
            and duplicate_covered_rows == 0
            and checks["row_coverage_matches_expected"]
            and vector_checks["bad_dims"] == 0
            and vector_checks["non_finite_vectors"] == 0
            and vector_checks["all_zero_vectors"] == 0
        )
    except Exception as exc:  # pragma: no cover - defensive for corrupt part files
        checks["error"] = repr(exc)
    return checks


def can_skip_valid_part(
    embedding_path: Path,
    skipped_path: Path,
    meta_path: Path,
    *,
    expected: dict[str, Any],
    expected_dim: int,
    skipped_required_columns: list[str],
) -> tuple[bool, dict[str, Any]]:
    checks = validate_part_files(
        embedding_path,
        skipped_path,
        meta_path,
        expected=expected,
        expected_dim=expected_dim,
        skipped_required_columns=skipped_required_columns,
    )
    return bool(checks.get("passed")), checks


def concat_parquets(paths: Sequence[str | Path]) -> pd.DataFrame:
    frames = [pd.read_parquet(path) for path in paths if Path(path).exists()]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def validate_manifest_schema_minimal(manifest: dict[str, Any], schema_path: Path) -> dict[str, Any]:
    """Small dependency-free check for the checked-in manifest schema's required/const gates."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    missing = [key for key in schema.get("required", []) if key not in manifest]
    checks: dict[str, Any] = {
        "schema_path": str(schema_path),
        "missing_required_fields": missing,
        "staged_only_const_true": manifest.get("staged_only") is True,
        "canonical_promotion_false": manifest.get("canonical_promotion") is False,
        "validation_has_passed_boolean": isinstance(manifest.get("validation", {}).get("passed"), bool),
    }
    checks["passed"] = not missing and checks["staged_only_const_true"] and checks["canonical_promotion_false"] and checks["validation_has_passed_boolean"]
    return checks
