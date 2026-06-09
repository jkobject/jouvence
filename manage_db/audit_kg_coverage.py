"""Audit stored KG coverage against the canonical TxGNN schema."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from manage_db import kg_storage
from manage_db.kg_schema import NODE_TYPES, RELATIONS


@dataclass(frozen=True)
class CoverageAudit:
    kg_uri: str
    node_counts: dict[str, int]
    edge_counts: dict[str, int]
    missing_nodes: list[str]
    missing_edges: list[str]

    @property
    def total_nodes(self) -> int:
        return sum(self.node_counts.values())

    @property
    def total_edges(self) -> int:
        return sum(self.edge_counts.values())

    @property
    def ok(self) -> bool:
        return not self.missing_nodes and not self.missing_edges


def _parquet_rows(root: kg_storage.KGRoot, subpath: str) -> int:
    table_file = pq.ParquetFile(root._join(subpath), filesystem=root.fs)
    return table_file.metadata.num_rows


def audit_coverage(kg_path: str | Path) -> CoverageAudit:
    """Return present/missing node and edge files for a KG root."""

    root = kg_storage.open_kg_root(str(kg_path))
    node_types = root.list_nodes()
    relations = root.list_edges()

    node_counts = {
        node_type: _parquet_rows(root, f"nodes/{node_type}.parquet")
        for node_type in node_types
    }
    edge_counts = {
        relation: _parquet_rows(root, f"edges/{relation}.parquet")
        for relation in relations
    }

    expected_nodes = [node_type.value for node_type in NODE_TYPES]
    expected_edges = [relation.name for relation in RELATIONS]
    return CoverageAudit(
        kg_uri=root.uri,
        node_counts=dict(sorted(node_counts.items())),
        edge_counts=dict(sorted(edge_counts.items())),
        missing_nodes=[node for node in expected_nodes if node not in node_counts],
        missing_edges=[edge for edge in expected_edges if edge not in edge_counts],
    )


def _to_jsonable(audit: CoverageAudit) -> dict[str, Any]:
    payload = asdict(audit)
    payload["total_nodes"] = audit.total_nodes
    payload["total_edges"] = audit.total_edges
    payload["ok"] = audit.ok
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit TxGNN KG node/edge file coverage against kg_schema.py."
    )
    parser.add_argument("kg_path", help="Path or gs:// URI to a KG root.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit non-zero when expected schema node/edge files are missing.",
    )
    args = parser.parse_args(argv)

    audit = audit_coverage(args.kg_path)
    if args.json:
        print(json.dumps(_to_jsonable(audit), indent=2, sort_keys=True))
    else:
        print(f"KG coverage audit: {audit.kg_uri}")
        print(f"  node_files: {len(audit.node_counts)} / {len(NODE_TYPES)}")
        print(f"  edge_files: {len(audit.edge_counts)} / {len(RELATIONS)}")
        print(f"  total_nodes: {audit.total_nodes:,}")
        print(f"  total_edges: {audit.total_edges:,}")
        if audit.missing_nodes:
            print("\nMissing node files")
            for node_type in audit.missing_nodes:
                print(f"  {node_type}")
        if audit.missing_edges:
            print("\nMissing edge files")
            for relation in audit.missing_edges:
                print(f"  {relation}")
    return 1 if args.fail_on_missing and not audit.ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
