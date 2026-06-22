from __future__ import annotations

import pandas as pd

from manage_db.kg_migrate import migrate_edges, migrate_nodes


def test_migrate_nodes_emits_storage_schema_columns() -> None:
    nodes = pd.DataFrame(
        [
            {
                "node_index": 1,
                "node_id": "7157",
                "node_type": "gene/protein",
                "node_name": "TP53",
                "node_source": "NCBI",
            }
        ]
    )

    migrated, index_to_id = migrate_nodes(nodes)

    assert index_to_id == {1: "NCBI:7157"}
    row = migrated.iloc[0]
    assert row["id"] == "NCBI:7157"
    assert row["node_type"] == "gene"
    assert row["ncbi_gene_id"] == "7157"
    assert row["gene_name"] == "TP53"


def test_migrate_edges_canonicalizes_bidirectional_txdata_relations() -> None:
    nodes = pd.DataFrame(
        [
            {"node_index": 1, "node_id": "1", "node_type": "drug", "node_name": "D", "node_source": "DrugBank"},
            {"node_index": 2, "node_id": "2", "node_type": "disease", "node_name": "A", "node_source": "MONDO"},
        ]
    )
    migrated_nodes, index_to_id = migrate_nodes(nodes)

    edges = pd.DataFrame(
        [
            {"x_index": 1, "y_index": 2, "relation": "indication", "display_relation": "indication"},
            {"x_index": 2, "y_index": 1, "relation": "drug_disease", "display_relation": "drug disease"},
        ]
    )

    migrated_edges, unmapped = migrate_edges(edges, nodes, index_to_id)

    assert unmapped == []
    assert set(migrated_edges["relation"]) == {"molecule_treats_disease"}
    assert set(migrated_edges["x_type"]) == {"molecule"}
    assert set(migrated_edges["y_type"]) == {"disease"}
    assert set(migrated_edges["x_id"]) == {migrated_nodes[migrated_nodes["node_type"] == "molecule"].iloc[0]["id"]}
    assert set(migrated_edges["y_id"]) == {migrated_nodes[migrated_nodes["node_type"] == "disease"].iloc[0]["id"]}
