"""Audit namespace coverage for node IDs in a TxGNN KG parquet root."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from manage_db import kg_storage
from manage_db.kg_schema import NODE_TYPES, NodeType

_ENSEMBL_RE = re.compile(r"^ENS([GTP])")
_GNOMAD_LIKE_RE = re.compile(r"^(?:chr)?[0-9XYM]+[_:-][0-9]+[_:-][ACGTN]+[_:-][ACGTN]+$", re.I)
_UNDERSCORE_ONTOLOGY_RE = re.compile(r"^(EFO|DOID|CL|HP|GO|MONDO|UBERON|OBA|NCIT|GSSO|MP)_")


@dataclass(frozen=True)
class NodeOntologyCoverage:
    """Namespace and xref coverage for one node parquet file."""

    node_type: str
    primary_ontology: str
    total_rows: int
    namespaces: dict[str, int]
    xref_non_null: dict[str, int]
    sample_ids_by_namespace: dict[str, list[str]]


@dataclass(frozen=True)
class NodeOntologyCoverageAudit:
    """Node ontology coverage report for a KG root."""

    kg_uri: str
    nodes: dict[str, NodeOntologyCoverage]
    missing_nodes: list[str]

    @property
    def total_rows(self) -> int:
        return sum(node.total_rows for node in self.nodes.values())


def infer_namespace(node_id: object) -> str:
    """Return a stable namespace label for a stored node ID."""

    text = str(node_id or "").strip()
    if not text:
        return "<blank>"
    if text.startswith("PMID:"):
        return "PMID"
    if text.startswith("CHEMBL"):
        return "ChEMBL"
    if text.startswith("DB") and text[2:].isdigit():
        return "DrugBank"
    if text.startswith("CVCL_"):
        return "Cellosaurus"
    if text.startswith("EH38E"):
        return "ENCODE"
    if text.startswith("R-HSA-"):
        return "Reactome"
    if text.startswith("rs") and text[2:].isdigit():
        return "dbSNP"
    if _GNOMAD_LIKE_RE.match(text):
        return "gnomAD-like"
    underscore_match = _UNDERSCORE_ONTOLOGY_RE.match(text)
    if underscore_match:
        return f"{underscore_match.group(1)}_underscore"
    ensembl = _ENSEMBL_RE.match(text)
    if ensembl:
        suffix = {"G": "Gene", "T": "Transcript", "P": "Protein"}[ensembl.group(1)]
        return f"Ensembl {suffix}"
    if ":" in text:
        return text.split(":", 1)[0]
    if text.isdigit():
        return "numeric"
    return "unprefixed"


def _coverage_for_node(root: kg_storage.KGRoot, node_type: str) -> NodeOntologyCoverage:
    info = NODE_TYPES[NodeType(node_type)]
    path = root._join("nodes", f"{node_type}.parquet")
    parquet_file = pq.ParquetFile(path, filesystem=root.fs)

    namespace_counts: Counter[str] = Counter()
    xref_counts: Counter[str] = Counter({column: 0 for column in info.xref_columns})
    samples: dict[str, list[str]] = {}
    columns = ["id", *info.xref_columns]

    for batch in parquet_file.iter_batches(batch_size=250_000, columns=columns):
        frame = batch.to_pandas()
        for node_id in frame["id"]:
            namespace = infer_namespace(node_id)
            namespace_counts[namespace] += 1
            bucket = samples.setdefault(namespace, [])
            if len(bucket) < 3:
                bucket.append(str(node_id))
        for column in info.xref_columns:
            xref_counts[column] += int(frame[column].notna().sum())

    return NodeOntologyCoverage(
        node_type=node_type,
        primary_ontology=info.primary_ontology,
        total_rows=parquet_file.metadata.num_rows,
        namespaces=dict(sorted(namespace_counts.items(), key=lambda item: (-item[1], item[0]))),
        xref_non_null=dict(xref_counts),
        sample_ids_by_namespace={key: samples[key] for key in sorted(samples)},
    )


def audit_node_ontology_coverage(kg_path: str | Path) -> NodeOntologyCoverageAudit:
    """Return namespace/xref coverage for all present node parquet files."""

    root = kg_storage.open_kg_root(str(kg_path))
    present_nodes = root.list_nodes()
    node_reports = {
        node_type: _coverage_for_node(root, node_type)
        for node_type in present_nodes
        if node_type in {nt.value for nt in NODE_TYPES}
    }
    expected_nodes = [node_type.value for node_type in NODE_TYPES]
    return NodeOntologyCoverageAudit(
        kg_uri=root.uri,
        nodes=dict(sorted(node_reports.items())),
        missing_nodes=[node_type for node_type in expected_nodes if node_type not in node_reports],
    )


def _to_jsonable(audit: NodeOntologyCoverageAudit) -> dict[str, Any]:
    payload = asdict(audit)
    payload["total_rows"] = audit.total_rows
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit namespace and xref coverage for KG node parquet IDs."
    )
    parser.add_argument("kg_path", help="Path or gs:// URI to a KG root.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    audit = audit_node_ontology_coverage(args.kg_path)
    if args.json:
        print(json.dumps(_to_jsonable(audit), indent=2, sort_keys=True))
        return 0

    print(f"Node ontology coverage audit: {audit.kg_uri}")
    print(f"  node_files: {len(audit.nodes)} / {len(NODE_TYPES)}")
    print(f"  total_rows: {audit.total_rows:,}")
    for node_type, report in audit.nodes.items():
        namespaces = ", ".join(f"{name}={count:,}" for name, count in report.namespaces.items())
        print(f"\n{node_type} ({report.primary_ontology}): {report.total_rows:,}")
        print(f"  namespaces: {namespaces}")
        populated_xrefs = {
            column: count for column, count in report.xref_non_null.items() if count
        }
        if populated_xrefs:
            xrefs = ", ".join(f"{column}={count:,}" for column, count in populated_xrefs.items())
            print(f"  populated_xrefs: {xrefs}")
    if audit.missing_nodes:
        print("\nMissing node files")
        for node_type in audit.missing_nodes:
            print(f"  {node_type}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
