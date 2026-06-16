from pathlib import Path

import pandas as pd

from manage_db import kg_storage
from manage_db.export_human_organism_slice import HUMAN_ORGANISM_ID, export_human_organism_slice


def test_export_human_organism_slice_writes_node_and_edges(tmp_path: Path) -> None:
    source = kg_storage.open_kg_root(str(tmp_path / "source"))
    output = kg_storage.open_kg_root(str(tmp_path / "output"))
    kg_storage.write_nodes(
        source,
        "gene",
        pd.DataFrame(
            {
                "id": ["ENSG2", "ENSG1", "ENSG1", "ENSMUSG1", "1234"],
                "ncbi_gene_id": [None, None, None, None, None],
                "hgnc_id": [None, None, None, None, None],
                "uniprot_id": [None, None, None, None, None],
                "gene_name": [None, None, None, None, None],
                "source": [
                    "OpenTargets",
                    "OpenTargets",
                    "OpenTargets",
                    "OpenTargets/target.homologues",
                    "legacy TxGNN",
                ],
            }
        ),
    )
    kg_storage.write_nodes(
        source,
        "tissue",
        pd.DataFrame(
            {
                "id": ["UBERON:2", "UBERON:1"],
                "bto_id": [None, None],
                "mesh_id": [None, None],
                "fma_id": [None, None],
            }
        ),
    )
    kg_storage.write_nodes(
        source,
        "cell_line",
        pd.DataFrame(
            {
                "id": ["ACH-000002", "ACH-000001", "ACH-000001"],
                "ccle_name": ["B", "A", "A"],
                "cosmic_id": [None, None, None],
                "efo_id": [None, None, None],
            }
        ),
    )

    summary = export_human_organism_slice(source.uri, output.uri)

    assert summary.organism_rows == 1
    assert summary.organism_has_gene_edges == 3
    assert summary.organism_has_tissue_edges == 2
    assert summary.cell_line_from_organism_edges == 2

    organism = kg_storage.read_nodes(output, "organism")
    assert organism["id"].tolist() == [HUMAN_ORGANISM_ID]
    assert organism["gbif_id"].tolist() == ["2436436"]

    gene_edges = kg_storage.read_edges(output, "organism_has_gene")
    assert gene_edges["x_id"].unique().tolist() == [HUMAN_ORGANISM_ID]
    assert gene_edges["y_id"].tolist() == ["1234", "ENSG1", "ENSG2"]
    assert set(gene_edges["relation"]) == {"organism_has_gene"}

    tissue_edges = kg_storage.read_edges(output, "organism_has_tissue")
    assert tissue_edges["y_id"].tolist() == ["UBERON:1", "UBERON:2"]
    assert set(tissue_edges["relation"]) == {"organism_has_tissue"}

    cell_line_edges = kg_storage.read_edges(output, "cell_line_from_organism")
    assert cell_line_edges["x_id"].tolist() == ["ACH-000001", "ACH-000002"]
    assert cell_line_edges["x_type"].unique().tolist() == ["cell_line"]
    assert cell_line_edges["y_id"].unique().tolist() == [HUMAN_ORGANISM_ID]
    assert cell_line_edges["y_type"].unique().tolist() == ["organism"]
    assert set(cell_line_edges["relation"]) == {"cell_line_from_organism"}
