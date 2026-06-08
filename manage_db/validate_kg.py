"""Validate a stored TxGNN Parquet knowledge graph."""

from __future__ import annotations

import argparse
import sys
from txgnn import KGLoader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a TxGNN Parquet KG with KGLoader."
    )
    parser.add_argument(
        "kg_path",
        help="Path to a KG root, or a data directory containing kg/.",
    )
    args = parser.parse_args(argv)

    report = KGLoader(args.kg_path).validate()

    print("KG validation summary")
    print(f"  node_types: {len(report.node_counts)}")
    print(f"  edge_types: {len(report.edge_counts)}")
    print(f"  total_nodes: {report.total_nodes}")
    print(f"  total_edges: {report.total_edges}")
    print(f"  total_dangling_edges: {report.total_dangling_edges}")

    if report.dangling_edges:
        print("\nDangling edges by relation")
        for relation, count in sorted(report.dangling_edges.items()):
            if count:
                print(f"  {relation}: {count}")

    if not report.ok:
        print("\nFAIL: KG contains dangling edges", file=sys.stderr)
        return 1

    print("\nPASS: KG has no dangling edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
