"""Backfill TxGNN edge evidence records from existing canonical edge files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from manage_db import kg_evidence, kg_storage


def _split_source(source: str) -> tuple[str, str]:
    if "/" in source:
        head, tail = source.split("/", 1)
        return head or source, tail or ""
    return source, ""


def _evidence_from_edges(edges: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for _, row in edges.iterrows():
        relation = str(row["relation"])
        x_id = str(row["x_id"])
        y_id = str(row["y_id"])
        source_raw = str(row.get("source") or "")
        source, source_dataset = _split_source(source_raw)
        rows.append(
            {
                "relation": relation,
                "x_id": x_id,
                "x_type": str(row["x_type"]),
                "y_id": y_id,
                "y_type": str(row["y_type"]),
                "evidence_type": "database_record",
                "source": source,
                "source_dataset": source_dataset,
                "source_record_id": f"{source_raw}:{relation}:{x_id}:{y_id}",
                "paper_id": "",
                "dataset_id": "",
                "study_id": "",
                "evidence_score": row.get("score"),
                "direction": str(row.get("direction") or ""),
                "predicate": relation,
            }
        )
    return pd.DataFrame(rows)


def backfill_edge_evidence(kg_path: str | Path, relations: list[str]) -> dict[str, int]:
    """Create evidence Parquets from existing edge rows for selected relations."""

    root = kg_storage.open_kg_root(str(kg_path))
    counts: dict[str, int] = {}
    for relation in relations:
        if relation not in root.list_edges():
            counts[relation] = 0
            continue
        edges = kg_storage.read_edges(root, relation)
        evidence = _evidence_from_edges(edges)
        counts[relation] = kg_evidence.write_evidence(root, relation, evidence, mode="overwrite")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill TxGNN edge evidence from existing edge Parquets.")
    parser.add_argument("kg_path", help="Path or gs:// URI to a KG root.")
    parser.add_argument("relations", nargs="+", help="Relation names to backfill evidence for.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    counts = backfill_edge_evidence(args.kg_path, args.relations)
    if args.json:
        print(json.dumps(counts, indent=2, sort_keys=True))
    else:
        for relation, count in counts.items():
            print(f"{relation}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
