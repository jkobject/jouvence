"""Backfill protein-expression edges by projecting gene expression through proteins.

This module is intentionally local-root oriented: it reads from a source KG root
and writes the derived relation to a caller-supplied destination KG root.  It
never writes to the source root unless the caller explicitly passes the same
path.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import kg_storage
from .kg_schema import Credibility, NodeType


@dataclass(frozen=True)
class ProjectionResult:
    source_relation: str
    dest_relation: str
    input_rows: int
    mapped_gene_rows: int
    unmapped_gene_rows: int
    estimated_output_rows: int
    output_rows: int
    distinct_pairs: int


class ProjectionTooLargeError(RuntimeError):
    """Raised when the projected relation exceeds the caller's row cap."""

    def __init__(self, estimated_output_rows: int, max_output_rows: int) -> None:
        super().__init__(
            f"projected output has {estimated_output_rows:,} rows, above cap {max_output_rows:,}"
        )
        self.estimated_output_rows = estimated_output_rows
        self.max_output_rows = max_output_rows


def _read_gene_protein_edges(root: kg_storage.KGRoot) -> pd.DataFrame:
    """Return distinct ENSG→ENSP rows, preferring canonical gene_encodes_protein."""

    try:
        edges = kg_storage.read_edges(
            root,
            "gene_encodes_protein",
            columns=["x_id", "x_type", "y_id", "y_type"],
        )
    except Exception:
        edges = pd.DataFrame()

    if not edges.empty:
        mapping = edges[
            (edges["x_type"].astype(str) == NodeType.GENE.value)
            & (edges["y_type"].astype(str) == NodeType.PROTEIN.value)
            & edges["x_id"].astype(str).str.startswith("ENSG")
            & edges["y_id"].astype(str).str.startswith("ENSP")
        ][["x_id", "y_id"]].rename(columns={"x_id": "gene_id", "y_id": "protein_id"})
        mapping = mapping.drop_duplicates().reset_index(drop=True)
        if not mapping.empty:
            return mapping

    proteins = kg_storage.read_nodes(
        root,
        NodeType.PROTEIN.value,
        columns=["id", "ensembl_gene_id"],
    )
    if proteins.empty or not {"id", "ensembl_gene_id"} <= set(proteins.columns):
        return pd.DataFrame(columns=["gene_id", "protein_id"])
    mapping = proteins[["ensembl_gene_id", "id"]].dropna()
    mapping = mapping[
        mapping["ensembl_gene_id"].astype(str).str.startswith("ENSG")
        & mapping["id"].astype(str).str.startswith("ENSP")
    ].rename(columns={"ensembl_gene_id": "gene_id", "id": "protein_id"})
    return mapping.drop_duplicates().reset_index(drop=True)


def estimate_expression_to_protein_rows(
    *,
    source_root: kg_storage.KGRoot,
    source_relation: str,
    source_x_type: str,
) -> tuple[int, int, int, int]:
    """Estimate projection size without materializing protein-expression rows.

    Returns ``(input_rows, mapped_gene_rows, unmapped_gene_rows,
    estimated_output_rows)``. Duplicate source edge rows are counted in
    ``input_rows`` but deduplicated before estimating the final edge count.
    """

    expr = kg_storage.read_edges(source_root, source_relation, columns=["x_id", "x_type", "y_id", "y_type"])
    input_rows = len(expr)
    expr = expr[
        (expr["x_type"].astype(str) == source_x_type)
        & (expr["y_type"].astype(str) == NodeType.GENE.value)
        & expr["y_id"].astype(str).str.startswith("ENSG")
    ][["x_id", "y_id"]].drop_duplicates()

    mapping = _read_gene_protein_edges(source_root)
    if mapping.empty or expr.empty:
        return input_rows, 0, len(expr), 0

    per_gene = mapping.groupby("gene_id", dropna=False).size().rename("protein_count").reset_index()
    joined = expr.rename(columns={"y_id": "gene_id"}).merge(per_gene, on="gene_id", how="left")
    mapped = joined["protein_count"].notna()
    mapped_gene_rows = int(mapped.sum())
    unmapped_gene_rows = int((~mapped).sum())
    estimated_output_rows = int(joined.loc[mapped, "protein_count"].sum())
    return input_rows, mapped_gene_rows, unmapped_gene_rows, estimated_output_rows


def project_expression_to_protein(
    *,
    source_root: kg_storage.KGRoot,
    dest_root: kg_storage.KGRoot,
    source_relation: str,
    dest_relation: str,
    source_x_type: str,
    max_output_rows: int = 10_000_000,
) -> ProjectionResult:
    """Build a bounded local protein-expression relation in ``dest_root``."""

    input_rows, mapped_gene_rows, unmapped_gene_rows, estimated_output_rows = estimate_expression_to_protein_rows(
        source_root=source_root,
        source_relation=source_relation,
        source_x_type=source_x_type,
    )
    if estimated_output_rows > max_output_rows:
        raise ProjectionTooLargeError(estimated_output_rows, max_output_rows)

    expr = kg_storage.read_edges(source_root, source_relation)
    expr = expr[
        (expr["x_type"].astype(str) == source_x_type)
        & (expr["y_type"].astype(str) == NodeType.GENE.value)
        & expr["y_id"].astype(str).str.startswith("ENSG")
    ].drop_duplicates(subset=["x_id", "y_id", "relation"])

    mapping = _read_gene_protein_edges(source_root)
    if expr.empty or mapping.empty:
        out = pd.DataFrame(columns=list(expr.columns) + ["gene_id"])
    else:
        out = expr.rename(columns={"y_id": "gene_id"}).merge(mapping, on="gene_id", how="inner")
        out = out.drop(columns=["y_type", "relation", "display_relation"], errors="ignore")
        out = out.rename(columns={"protein_id": "y_id"})
        out["y_type"] = NodeType.PROTEIN.value
        out["relation"] = dest_relation
        out["display_relation"] = "expresses protein"
        out["source"] = out["source"].astype(str).str.replace(
            ";projected_via_gene_encodes_protein", "", regex=False
        ) + ";projected_via_gene_encodes_protein"
        out["credibility"] = int(Credibility.ESTABLISHED_FACT)
        preferred = [
            "x_id",
            "x_type",
            "y_id",
            "y_type",
            "relation",
            "display_relation",
            "source",
            "credibility",
            "gene_id",
        ]
        out = out[[*preferred, *[c for c in out.columns if c not in preferred]]]
        out = out.drop_duplicates(subset=["x_id", "y_id", "relation", "source"]).reset_index(drop=True)

    output_rows = kg_storage.write_edges(dest_root, dest_relation, out, mode="overwrite")
    return ProjectionResult(
        source_relation=source_relation,
        dest_relation=dest_relation,
        input_rows=input_rows,
        mapped_gene_rows=mapped_gene_rows,
        unmapped_gene_rows=unmapped_gene_rows,
        estimated_output_rows=estimated_output_rows,
        output_rows=output_rows,
        distinct_pairs=output_rows,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-kg-root", required=True, help="Read-only KG root to project from")
    parser.add_argument("--dest-kg-root", required=True, help="Local/temp KG root to write derived edge into")
    parser.add_argument("--max-output-rows", type=int, default=10_000_000)
    parser.add_argument("--estimate-only", action="store_true")
    parser.add_argument(
        "--allow-cell-line-build",
        action="store_true",
        help="Opt-in escape hatch; by default cell_line_expresses_protein is estimate-only.",
    )
    parser.add_argument(
        "--relation",
        choices=["cell_type_expresses_protein", "cell_line_expresses_protein"],
        default="cell_type_expresses_protein",
    )
    args = parser.parse_args(argv)

    if args.relation == "cell_type_expresses_protein":
        source_relation = "cell_type_expresses_gene"
        source_x_type = NodeType.CELL_TYPE.value
    else:
        source_relation = "cell_line_expresses_gene"
        source_x_type = NodeType.CELL_LINE.value

    if args.relation == "cell_line_expresses_protein" and not args.estimate_only and not args.allow_cell_line_build:
        parser.error(
            "cell_line_expresses_protein is potentially very large; run --estimate-only first "
            "or pass --allow-cell-line-build explicitly for a bounded local build"
        )

    source_root = kg_storage.open_kg_root(args.source_kg_root)
    dest_root = kg_storage.open_kg_root(args.dest_kg_root)

    if args.estimate_only:
        counts = estimate_expression_to_protein_rows(
            source_root=source_root,
            source_relation=source_relation,
            source_x_type=source_x_type,
        )
        print(
            "\t".join(
                [
                    "source_relation",
                    "dest_relation",
                    "input_rows",
                    "mapped_gene_rows",
                    "unmapped_gene_rows",
                    "estimated_output_rows",
                ]
            )
        )
        print("\t".join(map(str, [source_relation, args.relation, *counts])))
        return 0

    result = project_expression_to_protein(
        source_root=source_root,
        dest_root=dest_root,
        source_relation=source_relation,
        dest_relation=args.relation,
        source_x_type=source_x_type,
        max_output_rows=args.max_output_rows,
    )
    print(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
