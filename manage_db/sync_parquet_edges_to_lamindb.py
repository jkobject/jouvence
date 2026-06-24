"""Bounded live sync of canonical KG edge/evidence Parquets into LaminDB.

Production-safety defaults:
- dry-run unless ``--write`` is passed;
- bounded by explicit per-relation edge/evidence limits by default;
- uses deterministic exact-ID keys from :mod:`manage_db.kg_edge_pilot`;
- writes through the live ``lnschema_txgnn.KGEdge`` and
  ``lnschema_txgnn.KGEdgeEvidence`` ORM models, never through local pilot SQLite.

This module is intentionally separate from ``kg_edge_pilot`` so reviewers can
see whether a run touched the live LaminDB instance or only the local review
fixture.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
import pyarrow.parquet as pq

from . import kg_edge_pilot, kg_storage
from .sync_parquet_nodes_to_lamindb import _configure_sqlite_timeout, _connect_lamin, _db_retry

DEFAULT_KG_ROOT = kg_edge_pilot.DEFAULT_KG_ROOT
DEFAULT_RELATIONS = kg_edge_pilot.DEFAULT_RELATIONS
DEFAULT_EDGE_LIMIT = 25
DEFAULT_EVIDENCE_LIMIT = 25


@dataclass
class LiveEdgeSyncSummary:
    relation: str
    edge_rows_available: int
    edge_rows_selected: int
    evidence_rows_available: int
    evidence_rows_selected: int
    edge_existing_before: int | None = None
    evidence_existing_before: int | None = None
    edge_count_after: int | None = None
    evidence_count_after: int | None = None
    edge_upserts: int = 0
    evidence_upserts: int = 0
    status: str = "dry_run"
    status_detail: str | None = None


def _registry_models() -> tuple[Any, Any]:
    import lnschema_txgnn as txs

    return txs.KGEdge, txs.KGEdgeEvidence


def _clean_value(value: object) -> object:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _metadata_dict(value: object) -> dict[str, Any] | None:
    value = _clean_value(value)
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    text = str(value)
    if not text:
        return None
    payload = json.loads(text)
    if isinstance(payload, dict):
        payload.pop("edge_key", None)
        payload.pop("evidence_key", None)
        return payload or None
    return {"value": payload}


def _row_dict(row: Mapping[str, Any], *, base_columns: Iterable[str], metadata_column: str = "metadata_json") -> dict[str, Any]:
    base = list(base_columns)
    out = {column: _clean_value(row.get(column)) for column in base}
    out["metadata"] = _metadata_dict(row.get(metadata_column))
    return out


def _edge_defaults(row: Mapping[str, Any]) -> dict[str, Any]:
    return _row_dict(row, base_columns=kg_edge_pilot.EDGE_BASE_COLUMNS)


def _evidence_defaults(row: Mapping[str, Any]) -> dict[str, Any]:
    return _row_dict(row, base_columns=kg_edge_pilot.EVIDENCE_BASE_COLUMNS)


def _read_limited_parquet(kg_root: str | Path, subdir: str, name: str, limit: int) -> tuple[pd.DataFrame, int]:
    root = kg_storage.open_kg_root(str(kg_root))
    path = root._join(subdir, f"{name}.parquet")
    if not root.fs.exists(path):
        return pd.DataFrame(), 0
    with root.fs.open(path, "rb") as handle:
        parquet_file = pq.ParquetFile(handle)
        table = parquet_file.read()
        selected = table.slice(0, int(limit)) if limit else table
        return selected.to_pandas(), parquet_file.metadata.num_rows


def build_edge_frame(kg_root: str | Path, relation: str, *, limit: int) -> tuple[pd.DataFrame, int]:
    frame, total = _read_limited_parquet(kg_root, "edges", relation, limit)
    if frame.empty:
        return pd.DataFrame(columns=[*kg_edge_pilot.EDGE_BASE_COLUMNS, "edge_key", "metadata_json"]), total
    missing = [col for col in ["x_id", "x_type", "y_id", "y_type", "relation"] if col not in frame.columns]
    if missing:
        raise ValueError(f"edges/{relation}.parquet missing required edge columns: {missing}")
    frame = frame.copy()
    frame["edge_key"] = [
        kg_edge_pilot.edge_key_for(
            relation=str(row["relation"]),
            x_type=str(row["x_type"]),
            x_id=str(row["x_id"]),
            y_type=str(row["y_type"]),
            y_id=str(row["y_id"]),
        )
        for _, row in frame.iterrows()
    ]
    for col in kg_edge_pilot.EDGE_BASE_COLUMNS:
        if col not in frame.columns:
            frame[col] = None
    frame["metadata_json"] = [kg_edge_pilot._metadata_json(row, [*kg_edge_pilot.EDGE_BASE_COLUMNS, "edge_key"]) for _, row in frame.iterrows()]
    return frame[["edge_key", *kg_edge_pilot.EDGE_BASE_COLUMNS, "metadata_json"]], total


def build_evidence_frame(kg_root: str | Path, relation: str, *, limit: int) -> tuple[pd.DataFrame, int]:
    frame, total = _read_limited_parquet(kg_root, "evidence", relation, limit)
    if frame.empty:
        return pd.DataFrame(columns=["evidence_key", *kg_edge_pilot.EVIDENCE_BASE_COLUMNS, "metadata_json"]), total
    frame = frame.copy()
    for col in kg_edge_pilot.EVIDENCE_BASE_COLUMNS:
        if col not in frame.columns:
            frame[col] = None
    frame["edge_key"] = [
        kg_edge_pilot.edge_key_for(
            relation=str(row["relation"]),
            x_type=str(row["x_type"]),
            x_id=str(row["x_id"]),
            y_type=str(row["y_type"]),
            y_id=str(row["y_id"]),
        )
        for _, row in frame.iterrows()
    ]
    frame["evidence_key"] = [kg_edge_pilot.evidence_key_for(row, ordinal=i) for i, (_, row) in enumerate(frame.iterrows())]
    frame["metadata_json"] = [kg_edge_pilot._metadata_json(row, kg_edge_pilot.EVIDENCE_BASE_COLUMNS) for _, row in frame.iterrows()]
    return frame[["evidence_key", *kg_edge_pilot.EVIDENCE_BASE_COLUMNS, "metadata_json"]], total


def _upsert_rows(model: Any, key_field: str, rows: Sequence[Mapping[str, Any]], defaults_fn) -> int:
    count = 0
    for row in rows:
        key = _clean_value(row.get(key_field))
        if key is None:
            continue
        defaults = defaults_fn(row)
        _db_retry(
            f"upsert {model.__module__}.{model.__name__} {key}",
            lambda model=model, key_field=key_field, key=key, defaults=defaults: model.objects.update_or_create(
                **{key_field: key}, defaults=defaults
            ),
        )
        count += 1
    return count


def _relation_count(model: Any, relation: str) -> int:
    value = _db_retry(
        f"count {model.__module__}.{model.__name__} {relation}",
        lambda model=model, relation=relation: model.objects.filter(relation=relation).count(),
    )
    return int(value or 0)


def sync_relation_to_lamindb(
    *,
    kg_root: str | Path,
    relation: str,
    edge_limit: int = DEFAULT_EDGE_LIMIT,
    evidence_limit: int = DEFAULT_EVIDENCE_LIMIT,
    write: bool = False,
) -> LiveEdgeSyncSummary:
    """Sync one relation from canonical KG Parquets to live LaminDB models.

    ``write=False`` is a dry-run that reads the source Parquets and reports the
    selected row counts. ``write=True`` performs idempotent ORM upserts keyed by
    ``edge_key``/``evidence_key``.
    """

    edge_frame, edge_total = build_edge_frame(kg_root, relation, limit=edge_limit)
    evidence_frame, evidence_total = build_evidence_frame(kg_root, relation, limit=evidence_limit)
    summary = LiveEdgeSyncSummary(
        relation=relation,
        edge_rows_available=edge_total,
        edge_rows_selected=len(edge_frame),
        evidence_rows_available=evidence_total,
        evidence_rows_selected=len(evidence_frame),
    )
    if not write:
        return summary

    KGEdge, KGEdgeEvidence = _registry_models()
    summary.edge_existing_before = _relation_count(KGEdge, relation)
    summary.evidence_existing_before = _relation_count(KGEdgeEvidence, relation)

    edge_rows = edge_frame.where(pd.notna(edge_frame), None).to_dict(orient="records")
    evidence_rows = evidence_frame.where(pd.notna(evidence_frame), None).to_dict(orient="records")
    summary.edge_upserts = _upsert_rows(KGEdge, "edge_key", edge_rows, _edge_defaults)
    summary.evidence_upserts = _upsert_rows(KGEdgeEvidence, "evidence_key", evidence_rows, _evidence_defaults)
    summary.edge_count_after = _relation_count(KGEdge, relation)
    summary.evidence_count_after = _relation_count(KGEdgeEvidence, relation)
    summary.status = "bounded live sync accepted"
    return summary


def sync_parquet_edges_to_lamindb(
    kg_root: str | Path = DEFAULT_KG_ROOT,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    edge_limit: int = DEFAULT_EDGE_LIMIT,
    evidence_limit: int = DEFAULT_EVIDENCE_LIMIT,
    lamin_instance: str | None = "jkobject/jouvencekb",
    write: bool = False,
) -> list[LiveEdgeSyncSummary]:
    _connect_lamin(lamin_instance)
    _configure_sqlite_timeout()
    summaries = []
    for relation in relations:
        summaries.append(
            sync_relation_to_lamindb(
                kg_root=kg_root,
                relation=relation,
                edge_limit=edge_limit,
                evidence_limit=evidence_limit,
                write=write,
            )
        )
    return summaries


def summaries_to_json(summaries: Sequence[LiveEdgeSyncSummary]) -> str:
    return json.dumps([asdict(item) for item in summaries], indent=2, sort_keys=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded live lnschema_txgnn KGEdge/KGEdgeEvidence sync")
    parser.add_argument("kg_root", nargs="?", default=str(DEFAULT_KG_ROOT), help="Canonical KG root; read-only")
    parser.add_argument("--relation", action="append", dest="relations", help="Relation to sync; may be repeated")
    parser.add_argument("--edge-limit", type=int, default=DEFAULT_EDGE_LIMIT, help="Maximum edge rows per relation; use 0 for all rows")
    parser.add_argument("--evidence-limit", type=int, default=DEFAULT_EVIDENCE_LIMIT, help="Maximum evidence rows per relation; use 0 for all rows")
    parser.add_argument("--lamin-instance", default="jkobject/jouvencekb", help="LaminDB instance slug")
    parser.add_argument("--write", action="store_true", help="Perform live ORM upserts; default is dry-run")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summaries = sync_parquet_edges_to_lamindb(
        args.kg_root,
        relations=args.relations or list(DEFAULT_RELATIONS),
        edge_limit=args.edge_limit,
        evidence_limit=args.evidence_limit,
        lamin_instance=args.lamin_instance,
        write=args.write,
    )
    if args.json:
        print(summaries_to_json(summaries))
    else:
        print(pd.DataFrame([asdict(item) for item in summaries]).to_string(index=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
