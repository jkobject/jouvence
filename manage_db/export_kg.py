"""CLI for exporting the local KG layout to the unified Parquet storage."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pyarrow.parquet as pq

try:
    from . import kg_storage
except ImportError:  # pragma: no cover - script fallback
    import kg_storage  # type: ignore


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def export_kg(src: Path, dst_uri: str, version: str) -> None:
    if not src.exists():
        raise FileNotFoundError(src)

    root = kg_storage.open_kg_root(dst_uri)

    node_counts: dict[str, int] = {}
    edge_counts: dict[str, int] = {}
    files_info: dict[str, dict[str, object]] = {}
    aggregate = hashlib.sha256()

    nodes_dir = src / "nodes"
    if nodes_dir.exists():
        for path in sorted(nodes_dir.glob("*.parquet")):
            node_type = path.stem
            table = pq.read_table(path)
            kg_storage.write_nodes(root, node_type, table, mode="overwrite")
            row_count = table.num_rows
            node_counts[node_type] = row_count

            sha = _file_sha256(path)
            size = path.stat().st_size
            rel = f"nodes/{path.name}"
            aggregate.update(rel.encode())
            aggregate.update(bytes.fromhex(sha))
            files_info[rel] = {
                "rows": row_count,
                "size_bytes": size,
                "sha256": sha,
            }

    edges_dir = src / "edges"
    if edges_dir.exists():
        for path in sorted(edges_dir.glob("*.parquet")):
            relation = path.stem
            table = pq.read_table(path)
            kg_storage.write_edges(root, relation, table, mode="overwrite")
            row_count = table.num_rows
            edge_counts[relation] = row_count

            sha = _file_sha256(path)
            size = path.stat().st_size
            rel = f"edges/{path.name}"
            aggregate.update(rel.encode())
            aggregate.update(bytes.fromhex(sha))
            files_info[rel] = {
                "rows": row_count,
                "size_bytes": size,
                "sha256": sha,
            }

    try:
        import subprocess

        code_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(Path(__file__).resolve().parent),
            text=True,
        ).strip()
    except Exception:  # pragma: no cover - git may be unavailable
        code_sha = "unknown"

    sources = {
        "legacy_local": {
            "version": version,
            "uri": str(src.resolve()),
            "sha256": aggregate.hexdigest(),
            "row_counts": {
                "nodes": node_counts,
                "edges": edge_counts,
            },
            "files": files_info,
        }
    }

    kg_storage.finalize_kg_export(
        root,
        sources=sources,
        code_version=version,
        code_sha=code_sha,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export KG parquet layout to unified storage")
    parser.add_argument("--src", default="./data/kg", help="Source KG directory (legacy layout)")
    parser.add_argument("--dst", required=True, help="Destination KG root URI (e.g. gs://…/kg/v2)")
    parser.add_argument(
        "--version",
        default=None,
        help="Semantic version string recorded in provenance (default: txgnn.version)",
    )
    args = parser.parse_args(argv)

    src = Path(args.src)

    version = args.version
    if version is None:
        try:
            from txgnn.version import __version__

            version = __version__
        except Exception:  # pragma: no cover - fallback when package missing
            version = "unknown"

    export_kg(src, args.dst, version)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])

