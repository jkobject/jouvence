"""Audit parity between KG node Parquets and LaminDB/bionty registries.

This is intentionally read-only. It answers the project-level completion
question: which node rows are present in a KG parquet root but not represented
in the corresponding LaminDB registry?
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from . import kg_storage
from .kg_ids import normalize_disease_id

try:
    from django.db.utils import OperationalError
except Exception:  # pragma: no cover - django is available in LaminDB runtime
    OperationalError = Exception  # type: ignore[assignment]


@dataclass
class NodeParity:
    node_type: str
    parquet_rows: int
    parquet_unique_ids: int
    registry: str | None
    registry_key_fields: list[str]
    lamindb_key_values: int
    matched_ids: int
    missing_ids: int
    sample_missing: list[str]
    status: str


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _id_variants(value: str) -> set[str]:
    variants = {value}
    normalized = normalize_disease_id(value)
    if normalized:
        variants.add(normalized)
    if ":" in value:
        variants.add(value.replace(":", "_"))
    if "_" in value:
        variants.add(value.replace("_", ":"))
    if value.startswith("PMID:"):
        variants.add(value.removeprefix("PMID:"))
    return variants


def _registry_value_tokens(raw: object) -> Iterable[str]:
    value = _clean(raw)
    if not value:
        return
    # Some xref columns, notably Protein.pdb_ids, store pipe-separated IDs.
    for token in value.split("|"):
        cleaned = _clean(token)
        if cleaned:
            yield cleaned


def _all_registry_values(registry, fields: Iterable[str]) -> set[str]:
    values: set[str] = set()
    for field in fields:
        if not any(f.name == field for f in registry._meta.fields):
            continue
        for raw in registry.objects.exclude(**{f"{field}__isnull": True}).values_list(field, flat=True).iterator():
            for value in _registry_value_tokens(raw):
                values.update(_id_variants(value))
    return values



def _registry_table_name(registry) -> str | None:
    meta = getattr(registry, "_meta", None)
    return getattr(meta, "db_table", None)


def _is_missing_registry_table_error(registry, exc: BaseException) -> bool:
    """Return True only for DB errors caused by an absent registry table."""

    text = str(exc).lower()
    if not any(marker in text for marker in ("no such table", "does not exist")):
        return False

    table = _registry_table_name(registry)
    if table:
        return table.lower() in text

    # Test doubles may not expose Django's db_table. In that case, accept the
    # narrow database-level missing-table wording but still do not catch generic
    # OperationalErrors such as syntax, lock, or connection failures.
    return "no such table" in text

def _registry_spec(node_type: str):
    import bionty as bt
    import pertdb as pt
    import lnschema_txgnn as txs

    return {
        "gene": (txs.Gene, ["ensembl_gene_id"]),
        "disease": (txs.Disease, ["ontology_id", "name", "mondo_id", "hp_id"]),
        "phenotype": (bt.Phenotype, ["ontology_id", "name"]),
        "pathway": (txs.Pathway, ["ontology_id"]),
        "tissue": (txs.Tissue, ["ontology_id"]),
        "cell_type": (txs.CellType, ["ontology_id"]),
        "organism": (bt.Organism, ["ontology_id", "name"]),
        "cell_line": (bt.CellLine, ["ontology_id", "name"]),
        "molecule": (txs.Molecule, ["chembl_id"]),
        "paper": (txs.Paper, ["pmid", "doi", "pmc_id", "arxiv_id"]),
        "transcript": (txs.Transcript, ["ensembl_transcript_id"]),
        # TxGNN protein nodes are Ensembl Protein translation products (ENSP).
        # Keep UniProt and other identifiers as xrefs on lnschema_txgnn.Protein;
        # do not audit KG protein node parity through bionty/bt.Protein or
        # xref-only matches.
        "protein": (txs.Protein, ["ensembl_protein_id"]),
        "mutation": (txs.Mutation, ["rsid", "gnomad_id", "hgvs", "clinvar_id"]),
        "enhancer": (txs.Enhancer, ["encode_id", "ensembl_regulatory_id"]),
        "dataset": (txs.Dataset, ["doi", "name"]),
    }.get(node_type)


def audit_node_type(
    root: kg_storage.KGRoot,
    node_type: str,
    *,
    sample_size: int = 10,
) -> NodeParity:
    node_df = kg_storage.read_nodes(root, node_type, columns=["id"])
    ids = sorted({
        (normalize_disease_id(cleaned) if node_type == "disease" else cleaned)
        for cleaned in (_clean(value) for value in node_df["id"].tolist())
        if cleaned
    })
    id_variant_map = {node_id: _id_variants(node_id) for node_id in ids}

    spec = _registry_spec(node_type)
    if spec is None:
        return NodeParity(
            node_type=node_type,
            parquet_rows=len(node_df),
            parquet_unique_ids=len(ids),
            registry=None,
            registry_key_fields=[],
            lamindb_key_values=0,
            matched_ids=0,
            missing_ids=len(ids),
            sample_missing=ids[:sample_size],
            status="unsupported_node_type",
        )

    registry, fields = spec
    registry_name = f"{registry.__module__}.{registry.__name__}"
    try:
        registry_values = _all_registry_values(registry, fields)
    except OperationalError as exc:
        if not _is_missing_registry_table_error(registry, exc):
            raise
        return NodeParity(
            node_type=node_type,
            parquet_rows=len(node_df),
            parquet_unique_ids=len(ids),
            registry=registry_name,
            registry_key_fields=fields,
            lamindb_key_values=0,
            matched_ids=0,
            missing_ids=len(ids),
            sample_missing=ids[:sample_size],
            status="schema_pending",
        )

    missing = [
        node_id
        for node_id, variants in id_variant_map.items()
        if variants.isdisjoint(registry_values)
    ]
    return NodeParity(
        node_type=node_type,
        parquet_rows=len(node_df),
        parquet_unique_ids=len(ids),
        registry=registry_name,
        registry_key_fields=fields,
        lamindb_key_values=len(registry_values),
        matched_ids=len(ids) - len(missing),
        missing_ids=len(missing),
        sample_missing=missing[:sample_size],
        status="ok" if not missing else "missing",
    )


def audit_kg_nodes(
    kg_path: str | Path,
    *,
    node_types: list[str] | None = None,
    sample_size: int = 10,
) -> list[NodeParity]:
    root = kg_storage.open_kg_root(str(kg_path))
    available = sorted(root.list_nodes())
    selected = node_types or available
    return [
        audit_node_type(root, node_type, sample_size=sample_size)
        for node_type in selected
        if node_type in available
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kg_path", help="Local or gs:// KG root")
    parser.add_argument("--node-types", nargs="+", default=None)
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = audit_kg_nodes(
        args.kg_path,
        node_types=args.node_types,
        sample_size=args.sample_size,
    )
    if args.json:
        print(json.dumps([asdict(item) for item in report], indent=2, sort_keys=True))
        return 0

    print(f"LaminDB parity audit: {args.kg_path}")
    for item in report:
        print(
            f"  {item.node_type:<12} rows={item.parquet_rows:,} "
            f"unique={item.parquet_unique_ids:,} matched={item.matched_ids:,} "
            f"missing={item.missing_ids:,} status={item.status}"
        )
        if item.sample_missing:
            print(f"    sample_missing: {', '.join(item.sample_missing)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
