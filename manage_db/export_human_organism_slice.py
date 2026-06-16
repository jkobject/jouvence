"""Export the canonical human organism node and direct organism edges.

This is a bounded schema-completion slice for the TxGNN KG. The current
expanded graph is human-only, so this exporter adds the NCBI Taxonomy human
node plus direct provenance-style edges from human to every canonical gene and
tissue node, and from every canonical human cell line to human.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from . import kg_storage
from .kg_schema import Credibility


HUMAN_ORGANISM_ID = "NCBITaxon:9606"


@dataclass(frozen=True)
class HumanOrganismExportSummary:
    output_root: str
    organism_rows: int
    organism_has_gene_edges: int
    organism_has_tissue_edges: int
    cell_line_from_organism_edges: int
    gene_nodes_seen: int
    tissue_nodes_seen: int
    cell_line_nodes_seen: int


def _edge_frame(target_ids: pd.Series, *, relation: str, y_type: str, display_relation: str) -> pd.DataFrame:
    ids = (
        target_ids.dropna()
        .astype("string")
        .drop_duplicates()
        .sort_values(kind="mergesort")
        .reset_index(drop=True)
    )
    return pd.DataFrame(
        {
            "x_id": HUMAN_ORGANISM_ID,
            "x_type": "organism",
            "y_id": ids,
            "y_type": y_type,
            "relation": relation,
            "display_relation": display_relation,
            "source": "NCBI Taxonomy / TxGNN human-only KG",
            "credibility": int(Credibility.ESTABLISHED_FACT),
        }
    )


def _cell_line_from_organism_frame(cell_line_ids: pd.Series) -> pd.DataFrame:
    ids = (
        cell_line_ids.dropna()
        .astype("string")
        .drop_duplicates()
        .sort_values(kind="mergesort")
        .reset_index(drop=True)
    )
    return pd.DataFrame(
        {
            "x_id": ids,
            "x_type": "cell_line",
            "y_id": HUMAN_ORGANISM_ID,
            "y_type": "organism",
            "relation": "cell_line_from_organism",
            "display_relation": "from organism",
            "source": "NCBI Taxonomy / DepMap human cell-line metadata",
            "credibility": int(Credibility.ESTABLISHED_FACT),
        }
    )


def _read_optional_node_ids(source: kg_storage.KGRoot, node_type: str) -> pd.DataFrame:
    try:
        return kg_storage.read_nodes(source, node_type, columns=["id"])
    except FileNotFoundError:
        return pd.DataFrame({"id": []})


def export_human_organism_slice(input_root: str | Path, output_root: str | Path) -> HumanOrganismExportSummary:
    """Write organism node and human organism edges into ``output_root``.

    ``input_root`` supplies the current canonical gene/tissue/cell-line node IDs.
    Existing files in ``output_root`` are not otherwise modified.
    """

    source = kg_storage.open_kg_root(str(input_root))
    target = kg_storage.open_kg_root(str(output_root))

    gene_nodes = kg_storage.read_nodes(source, "gene")
    tissue_nodes = kg_storage.read_nodes(source, "tissue", columns=["id"])
    cell_line_nodes = _read_optional_node_ids(source, "cell_line")

    organism_nodes = pd.DataFrame(
        {
            "id": [HUMAN_ORGANISM_ID],
            "taxonomy_id": ["9606"],
            "gbif_id": ["2436436"],
            "name": ["human"],
            "scientific_name": ["Homo sapiens"],
            "source": ["NCBI Taxonomy"],
        }
    )
    organism_count = kg_storage.write_nodes(target, "organism", organism_nodes)

    gene_source = (
        gene_nodes["source"].astype(str)
        if "source" in gene_nodes.columns
        else pd.Series([""] * len(gene_nodes), index=gene_nodes.index)
    )
    is_orthology_nonhuman_stub = (
        gene_source.eq("OpenTargets/target.homologues")
        & ~gene_nodes["id"].astype(str).str.startswith("ENSG")
    )
    human_gene_ids = gene_nodes.loc[~is_orthology_nonhuman_stub, "id"]
    gene_edges = _edge_frame(
        human_gene_ids,
        relation="organism_has_gene",
        y_type="gene",
        display_relation="has gene",
    )
    gene_edge_count = kg_storage.write_edges(target, "organism_has_gene", gene_edges)

    tissue_edges = _edge_frame(
        tissue_nodes["id"],
        relation="organism_has_tissue",
        y_type="tissue",
        display_relation="has tissue",
    )
    tissue_edge_count = kg_storage.write_edges(target, "organism_has_tissue", tissue_edges)

    cell_line_edges = _cell_line_from_organism_frame(cell_line_nodes["id"])
    cell_line_edge_count = kg_storage.write_edges(target, "cell_line_from_organism", cell_line_edges)

    return HumanOrganismExportSummary(
        output_root=str(output_root),
        organism_rows=organism_count,
        organism_has_gene_edges=gene_edge_count,
        organism_has_tissue_edges=tissue_edge_count,
        cell_line_from_organism_edges=cell_line_edge_count,
        gene_nodes_seen=len(gene_nodes),
        tissue_nodes_seen=len(tissue_nodes),
        cell_line_nodes_seen=len(cell_line_nodes),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_root", help="KG root containing canonical gene/tissue/cell-line nodes")
    parser.add_argument("output_root", help="KG root to receive organism Parquets")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    summary = export_human_organism_slice(args.input_root, args.output_root)
    if args.json:
        print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    else:
        print(
            "wrote organism slice: "
            f"organism={summary.organism_rows}, "
            f"organism_has_gene={summary.organism_has_gene_edges}, "
            f"organism_has_tissue={summary.organism_has_tissue_edges}, "
            f"cell_line_from_organism={summary.cell_line_from_organism_edges}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
