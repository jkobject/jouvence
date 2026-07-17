from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from manage_db import kg_edge_pilot, kg_queries


def _write_pilot_fixture(root: Path) -> None:
    (root / "nodes").mkdir(parents=True)
    (root / "edges").mkdir(parents=True)
    (root / "evidence").mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "id": "NCBI:672",
                "ncbi_gene_id": "672",
                "hgnc_id": None,
                "uniprot_id": None,
                "gene_name": "BRCA1",
                "name": "BRCA1",
                "description": "BRCA1 DNA repair associated",
                "source": "NCBI",
            }
        ]
    ).to_parquet(root / "nodes" / "gene.parquet", index=False)

    pd.DataFrame(
        [
            {
                "id": "EFO:0000305",
                "name": "breast carcinoma",
                "description": None,
                "mondo_id": None,
                "efo_id": "EFO:0000305",
                "mesh_id": None,
                "hp_id": None,
                "omim_id": None,
                "doid_id": None,
                "icd10_code": None,
                "source": "EFO",
            },
            {
                "id": "MONDO:0019391",
                "name": "Fanconi anemia",
                "description": "fallback-only disease node",
                "mondo_id": "MONDO:0019391",
                "efo_id": None,
                "mesh_id": None,
                "hp_id": None,
                "omim_id": None,
                "doid_id": None,
                "icd10_code": None,
                "source": "MONDO",
            },
        ]
    ).to_parquet(root / "nodes" / "disease.parquet", index=False)

    pd.DataFrame(
        [
            {
                "x_id": "NCBI:672",
                "x_type": "gene",
                "y_id": "EFO:0000305",
                "y_type": "disease",
                "relation": "disease_associated_gene",
                "display_relation": "associated gene",
                "source": "OpenTargets",
                "credibility": 3,
                "score": 0.88,
            },
            {
                "x_id": "NCBI:672",
                "x_type": "gene",
                "y_id": "MONDO:0019391",
                "y_type": "disease",
                "relation": "disease_associated_gene",
                "display_relation": "associated gene",
                "source": "TxGNN",
                "credibility": 1,
                "score": None,
            },
        ]
    ).to_parquet(root / "edges" / "disease_associated_gene.parquet", index=False)

    pd.DataFrame(
        [
            {
                "edge_key": "legacy-key-is-recomputed",
                "relation": "disease_associated_gene",
                "x_id": "NCBI:672",
                "x_type": "gene",
                "y_id": "EFO:0000305",
                "y_type": "disease",
                "evidence_type": "database_record",
                "source": "OpenTargets",
                "source_dataset": "reactome",
                "source_record_id": "fixture-record",
                "paper_id": None,
                "dataset_id": None,
                "study_id": None,
                "evidence_score": 0.88,
                "effect_size": None,
                "p_value": None,
                "direction": "forward",
                "confidence_interval": None,
                "predicate": "disease_associated_gene",
                "text_span": None,
                "section": None,
                "extraction_method": None,
                "license": None,
                "release": "fixture",
                "created_at": "2026-06-23",
            }
        ]
    ).to_parquet(root / "evidence" / "disease_associated_gene.parquet", index=False)

    pd.DataFrame(
        [
            {
                "x_id": "OpenTargets:target_essentiality:26.03",
                "x_type": "dataset",
                "y_id": "UBERON:0003975",
                "y_type": "tissue",
                "relation": "dataset_contains_tissue",
                "display_relation": "contains tissue",
                "source": "OpenTargets/target_essentiality",
                "credibility": 3,
            }
        ]
    ).to_parquet(root / "edges" / "dataset_contains_tissue.parquet", index=False)


def test_edge_key_is_deterministic_and_preserves_exact_ids() -> None:
    key1 = kg_edge_pilot.edge_key_for(
        relation="disease_associated_gene",
        x_type="gene",
        x_id="NCBI:672",
        y_type="disease",
        y_id="EFO:0000305",
    )
    key2 = kg_edge_pilot.edge_key_for(
        relation="disease_associated_gene",
        x_type="gene",
        x_id="NCBI:672",
        y_type="disease",
        y_id="EFO:0000305",
    )
    assert key1 == key2
    assert len(key1) == 64
    assert key1 != kg_edge_pilot.edge_key_for(
        relation="disease_associated_gene",
        x_type="gene",
        x_id="672",
        y_type="disease",
        y_id="EFO:0000305",
    )


def test_dry_run_counts_relation_with_and_without_evidence(tmp_path: Path) -> None:
    root = tmp_path / "kg"
    _write_pilot_fixture(root)

    with_evidence = kg_edge_pilot.dry_run_relation(
        root=root,
        relation="disease_associated_gene",
        edge_limit=1,
        evidence_limit=10,
    )
    without_evidence = kg_edge_pilot.dry_run_relation(
        root=root,
        relation="dataset_contains_tissue",
        edge_limit=10,
        evidence_limit=10,
    )

    assert with_evidence.edge_rows_available == 2
    assert with_evidence.edge_rows_selected == 1
    assert with_evidence.evidence_rows_available == 1
    assert with_evidence.evidence_rows_selected == 1
    assert without_evidence.edge_rows_available == 1
    assert without_evidence.edge_rows_selected == 1
    assert without_evidence.evidence_rows_available == 0
    assert without_evidence.evidence_rows_selected == 0


def test_sqlite_sync_is_idempotent_and_query_helper_uses_pilot(tmp_path: Path) -> None:
    root = tmp_path / "kg"
    _write_pilot_fixture(root)
    sqlite_path = tmp_path / "pilot.sqlite"

    for _ in range(2):
        kg_edge_pilot.sync_relation_to_sqlite(
            root=root,
            sqlite_path=sqlite_path,
            relation="disease_associated_gene",
            edge_limit=1,
            evidence_limit=10,
        )
        kg_edge_pilot.sync_relation_to_sqlite(
            root=root,
            sqlite_path=sqlite_path,
            relation="dataset_contains_tissue",
            edge_limit=10,
            evidence_limit=10,
        )

    with sqlite3.connect(sqlite_path) as con:
        edge_count = con.execute("select count(*) from kg_edge").fetchone()[0]
        evidence_count = con.execute("select count(*) from kg_edge_evidence").fetchone()[0]
    assert edge_count == 2
    assert evidence_count == 1

    result = kg_queries.diseases_for_gene(gene_name="BRCA1", kg_root=root, pilot_db=sqlite_path)

    assert list(result["disease_id"]) == ["EFO:0000305"]
    assert result.loc[0, "edge_source"] == "OpenTargets"
    assert result.loc[0, "score"] == 0.88
    assert result.loc[0, "evidence_count"] == 1
    assert result.loc[0, "evidence_sources"] == "OpenTargets"


def test_query_helper_falls_back_to_parquet_when_pilot_unpopulated(tmp_path: Path) -> None:
    root = tmp_path / "kg"
    _write_pilot_fixture(root)
    empty_pilot = tmp_path / "empty.sqlite"

    result = kg_queries.diseases_for_gene(gene_name="BRCA1", kg_root=root, pilot_db=empty_pilot)

    assert set(result["disease_id"]) == {"EFO:0000305", "MONDO:0019391"}
