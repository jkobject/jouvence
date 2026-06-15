from __future__ import annotations

from pathlib import Path

import pandas as pd

from manage_db.kg_storage import open_kg_root, write_edges


def test_backfill_edge_evidence_from_existing_edges(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_edge_evidence import backfill_edge_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(
        root,
        "disease_involves_pathway",
        pd.DataFrame(
            [
                {
                    "x_id": "EFO:1",
                    "x_type": "disease",
                    "y_id": "R-HSA-1",
                    "y_type": "pathway",
                    "relation": "disease_involves_pathway",
                    "display_relation": "involves pathway",
                    "source": "OpenTargets/reactome",
                    "credibility": 2,
                    "score": 0.71,
                    "pathway_name": "Example pathway",
                }
            ]
        ),
    )

    assert backfill_edge_evidence(tmp_path / "kg", ["disease_involves_pathway"]) == {
        "disease_involves_pathway": 1
    }

    evidence = read_evidence(root, "disease_involves_pathway")
    assert len(evidence) == 1
    assert evidence.loc[0, "edge_key"] == "disease_involves_pathway|EFO:1|R-HSA-1"
    assert evidence.loc[0, "source"] == "OpenTargets"
    assert evidence.loc[0, "source_dataset"] == "reactome"
    assert evidence.loc[0, "source_record_id"] == "OpenTargets/reactome:disease_involves_pathway:EFO:1:R-HSA-1"
    assert evidence.loc[0, "evidence_score"] == 0.71
    assert evidence.loc[0, "predicate"] == "disease_involves_pathway"

    audit = audit_edge_evidence(tmp_path / "kg", relations=["disease_involves_pathway"])
    assert audit.ok



def test_backfill_pharmacogenomics_evidence_uses_source_records_and_papers(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_edge_evidence import backfill_pharmacogenomics_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(
        root,
        "mutation_affects_molecule_response",
        pd.DataFrame(
            [
                {
                    "x_id": "1_100_A_T",
                    "x_type": "mutation",
                    "y_id": "CHEMBL1",
                    "y_type": "molecule",
                    "relation": "mutation_affects_molecule_response",
                    "display_relation": "affects response to",
                    "source": "OpenTargets/clinpgx",
                    "credibility": 3,
                    "pgx_category": "efficacy",
                }
            ]
        ),
    )
    pgx_dir = tmp_path / "opentargets" / "pharmacogenomics"
    pgx_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "variantId": "1_100_A_T",
                "variantRsId": "rs1",
                "datasourceId": "clinpgx",
                "datasourceVersion": "26.03",
                "datatypeId": "pharmacogenomics",
                "directionality": "increased_response",
                "evidenceLevel": "1A",
                "genotypeAnnotationText": "Example genotype text",
                "pgxCategory": "efficacy",
                "studyId": "PGX-STUDY-1",
                "literature": ["123", "PMID:456"],
                "drugs": [{"drugId": "CHEMBL1", "drugFromSource": "Drug A"}],
            },
            {
                "variantId": "1_100_A_T",
                "variantRsId": "rs1",
                "datasourceId": "clinpgx",
                "datasourceVersion": "26.03",
                "datatypeId": "pharmacogenomics",
                "directionality": "increased_response",
                "evidenceLevel": "1A",
                "genotypeAnnotationText": "Unmatched drug text",
                "pgxCategory": "efficacy",
                "studyId": "PGX-STUDY-2",
                "literature": ["999"],
                "drugs": [{"drugId": "CHEMBL_NOT_CANONICAL"}],
            },
        ]
    ).to_parquet(pgx_dir / "part-000.parquet", index=False)

    assert backfill_pharmacogenomics_evidence(tmp_path / "kg", pgx_dir) == {
        "mutation_affects_molecule_response": 3
    }

    evidence = read_evidence(root, "mutation_affects_molecule_response")
    assert set(evidence["evidence_type"]) == {"database_record", "paper"}
    assert set(evidence["paper_id"]) == {"", "PMID:123", "PMID:456"}
    assert set(evidence["edge_key"]) == {"mutation_affects_molecule_response|1_100_A_T|CHEMBL1"}
    record = evidence[evidence["evidence_type"] == "database_record"].iloc[0]
    assert record["source"] == "OpenTargets"
    assert record["source_dataset"] == "pharmacogenomics"
    assert record["study_id"] == "PGX-STUDY-1"
    assert record["direction"] == "increased_response"
    assert record["predicate"] == "efficacy"
    assert "clinpgx:PGX-STUDY-1:1_100_A_T:CHEMBL1:1A:efficacy" in record["source_record_id"]
    assert audit_edge_evidence(tmp_path / "kg", relations=["mutation_affects_molecule_response"]).ok
