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



def test_backfill_variant_protein_change_evidence_uses_edge_payload(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_edge_evidence import backfill_edge_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(
        root,
        "mutation_causes_protein_change",
        pd.DataFrame(
            [
                {
                    "x_id": "1_12345_A_G",
                    "x_type": "mutation",
                    "y_id": "ENSP00000123456",
                    "y_type": "protein",
                    "relation": "mutation_causes_protein_change",
                    "display_relation": "causes protein change",
                    "source": "OpenTargets",
                    "credibility": 3,
                    "amino_acid_change": "A1G",
                    "uniprot_id": "P12345",
                }
            ]
        ),
    )

    assert backfill_edge_evidence(tmp_path / "kg", ["mutation_causes_protein_change"]) == {
        "mutation_causes_protein_change": 1
    }

    evidence = read_evidence(root, "mutation_causes_protein_change")
    assert len(evidence) == 1
    record = evidence.iloc[0]
    assert record["edge_key"] == "mutation_causes_protein_change|1_12345_A_G|ENSP00000123456"
    assert record["relation"] == "mutation_causes_protein_change"
    assert record["evidence_type"] == "database_record"
    assert record["source"] == "OpenTargets"
    assert record["source_dataset"] == "variant"
    assert record["predicate"] == "amino_acid_change"
    assert record["paper_id"] == ""
    assert record["source_record_id"] == (
        "OpenTargets/variant:mutation_causes_protein_change:"
        "1_12345_A_G:ENSP00000123456:P12345:A1G"
    )
    assert audit_edge_evidence(tmp_path / "kg", relations=["mutation_causes_protein_change"]).ok


def test_backfill_mutation_associated_gene_preserves_l2g_study_locus_support_rows(
    tmp_path: Path,
) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_edge_evidence import backfill_edge_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    edge_dir = tmp_path / "kg" / "edges"
    edge_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "x_id": "1_100_A_T",
                "x_type": "mutation",
                "y_id": "ENSG000001",
                "y_type": "gene",
                "relation": "mutation_associated_gene",
                "display_relation": "associated with",
                "source": "OpenTargets/l2g",
                "credibility": 2,
                "score": 0.91,
                "datatype": "genetic_association",
                "studyLocusId": "GCST1_1_100_A_T",
            },
            {
                "x_id": "1_100_A_T",
                "x_type": "mutation",
                "y_id": "ENSG000001",
                "y_type": "gene",
                "relation": "mutation_associated_gene",
                "display_relation": "associated with",
                "source": "OpenTargets/l2g",
                "credibility": 2,
                "score": 0.42,
                "datatype": "l2g",
                "studyLocusId": "GCST2_1_100_A_T",
            },
        ]
    ).to_parquet(edge_dir / "mutation_associated_gene.parquet", index=False)

    assert backfill_edge_evidence(tmp_path / "kg", ["mutation_associated_gene"]) == {
        "mutation_associated_gene": 2
    }

    evidence = read_evidence(root, "mutation_associated_gene").sort_values("study_id").reset_index(drop=True)
    assert len(evidence) == 2
    assert set(evidence["edge_key"]) == {"mutation_associated_gene|1_100_A_T|ENSG000001"}
    assert list(evidence["study_id"]) == ["GCST1_1_100_A_T", "GCST2_1_100_A_T"]
    assert list(evidence["evidence_score"]) == [0.91, 0.42]
    assert set(evidence["evidence_type"]) == {"genetic_association", "model_prediction"}
    assert set(evidence["source"]) == {"OpenTargets"}
    assert set(evidence["source_dataset"]) == {"l2g"}
    assert set(evidence["predicate"]) == {"genetic_association", "l2g"}
    assert set(evidence["extraction_method"]) == {"OpenTargets L2G"}
    assert evidence["source_record_id"].nunique() == 2
    for record_id in evidence["source_record_id"]:
        assert "OpenTargets/l2g" in record_id
        assert "mutation_associated_gene" in record_id
        assert "1_100_A_T" in record_id
        assert "ENSG000001" in record_id
        assert "GCST" in record_id

    assert audit_edge_evidence(tmp_path / "kg", relations=["mutation_associated_gene"]).ok


def test_backfill_molecule_targets_protein_accepts_legacy_gene_moa_rows(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_edge_evidence import backfill_edge_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(
        root,
        "molecule_targets_protein",
        pd.DataFrame(
            [
                {
                    "x_id": "CHEMBL1",
                    "x_type": "molecule",
                    "y_id": "ENSG000001",
                    "y_type": "gene",
                    "relation": "molecule_targets_protein",
                    "display_relation": "receptor antagonist",
                    "source": "OpenTargets",
                    "credibility": 3,
                    "action_type": "ANTAGONIST",
                }
            ]
        ),
    )

    assert backfill_edge_evidence(tmp_path / "kg", ["molecule_targets_protein"]) == {
        "molecule_targets_protein": 1
    }

    evidence = read_evidence(root, "molecule_targets_protein")
    assert len(evidence) == 1
    assert evidence.loc[0, "edge_key"] == "molecule_targets_protein|CHEMBL1|ENSG000001"
    assert evidence.loc[0, "y_type"] == "gene"
    assert evidence.loc[0, "source"] == "OpenTargets"
    assert evidence.loc[0, "source_dataset"] == "drug_mechanism_of_action"
    assert evidence.loc[0, "predicate"] == "ANTAGONIST"
    assert evidence.loc[0, "direction"] == "ANTAGONIST"
    assert evidence.loc[0, "source_record_id"] == (
        "OpenTargets:drug_mechanism_of_action:molecule_targets_protein:CHEMBL1:ENSG000001:ANTAGONIST"
    )
    assert audit_edge_evidence(tmp_path / "kg", relations=["molecule_targets_protein"]).ok



def test_build_mutation_associated_disease_evidence_streaming(tmp_path: Path) -> None:
    from manage_db.backfill_edge_evidence import build_mutation_associated_disease_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    edge_rows = pd.DataFrame(
        [
            {
                "x_id": "1_100_A_T",
                "x_type": "mutation",
                "y_id": "EFO:1",
                "y_type": "disease",
                "relation": "mutation_associated_disease",
                "display_relation": "associated with",
                "source": "OpenTargets/gwas_credible_sets",
                "credibility": 2,
                "score": 0.73,
                "datatype": "genetic_association",
                "studyLocusId": "SL1",
            },
            {
                "x_id": "1_100_A_T",
                "x_type": "mutation",
                "y_id": "EFO:1",
                "y_type": "disease",
                "relation": "mutation_associated_disease",
                "display_relation": "associated with",
                "source": "OpenTargets/eva",
                "credibility": 1,
                "score": 0.5,
                "datatype": "genetic_association",
                "studyLocusId": None,
            },
        ]
    )
    edge_dir = tmp_path / "kg" / "edges"
    evidence_dir = tmp_path / "kg" / "evidence"
    edge_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    edge_parquet = edge_dir / "mutation_associated_disease.parquet"
    evidence_parquet = evidence_dir / "mutation_associated_disease.parquet"
    edge_rows.to_parquet(edge_parquet, index=False)
    counts = build_mutation_associated_disease_evidence(edge_parquet, evidence_parquet, batch_size=1)
    assert counts == {"mutation_associated_disease": 2}

    evidence = read_evidence(root, "mutation_associated_disease")
    assert len(evidence) == 2
    assert set(evidence["source_dataset"]) == {"gwas_credible_sets", "eva"}
    assert set(evidence["study_id"]) == {"SL1", ""}
    assert set(evidence["predicate"]) == {"genetic_association"}
    assert evidence["source_record_id"].str.contains("row=").all()
    assert evidence.loc[evidence["source_dataset"] == "gwas_credible_sets", "source_record_id"].iloc[0].find("studyLocusId=SL1") > -1
    assert set(evidence["edge_key"]) == {"mutation_associated_disease|1_100_A_T|EFO:1"}
