from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

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
                    "x_id": "R-HSA-1",
                    "x_type": "pathway",
                    "y_id": "EFO:1",
                    "y_type": "disease",
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
    assert evidence.loc[0, "edge_key"] == "disease_involves_pathway|R-HSA-1|EFO:1"
    assert evidence.loc[0, "source"] == "OpenTargets"
    assert evidence.loc[0, "source_dataset"] == "reactome"
    assert evidence.loc[0, "source_record_id"] == "OpenTargets/reactome:disease_involves_pathway:R-HSA-1:EFO:1"
    assert evidence.loc[0, "evidence_score"] == 0.71
    assert evidence.loc[0, "predicate"] == "disease_involves_pathway"

    audit = audit_edge_evidence(tmp_path / "kg", relations=["disease_involves_pathway"])
    assert audit.ok


def test_backfill_pathway_contains_gene_preserves_go_and_legacy_source_metadata(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_edge_evidence import backfill_edge_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(
        root,
        "pathway_contains_gene",
        pd.DataFrame(
            [
                {
                    "x_id": "GO:0005737",
                    "x_type": "pathway",
                    "y_id": "ENSG000001",
                    "y_type": "gene",
                    "relation": "pathway_contains_gene",
                    "display_relation": "contains gene",
                    "source": "OpenTargets/GO",
                    "credibility": 3,
                    "go_evidence": "IDA",
                    "go_aspect": "C",
                    "release": "26.03",
                },
                {
                    "x_id": "R-HSA-109704",
                    "x_type": "pathway",
                    "y_id": "NCBI:5295",
                    "y_type": "gene",
                    "relation": "pathway_contains_gene",
                    "display_relation": "contains gene",
                    "source": "TxGNN",
                    "credibility": 3,
                },
            ]
        ),
    )

    assert backfill_edge_evidence(tmp_path / "kg", ["pathway_contains_gene"]) == {
        "pathway_contains_gene": 2
    }
    evidence = read_evidence(root, "pathway_contains_gene").sort_values("source").reset_index(drop=True)
    assert set(evidence["edge_key"]) == {
        "pathway_contains_gene|GO:0005737|ENSG000001",
        "pathway_contains_gene|R-HSA-109704|NCBI:5295",
    }

    ot = evidence[evidence["source"] == "OpenTargets"].iloc[0]
    assert ot["source_dataset"] == "go"
    assert ot["predicate"] == "IDA"
    assert ot["direction"] == "gene_product_annotation"
    assert ot["release"] == "26.03"
    assert "GO:0005737" in ot["source_record_id"]
    assert '"go_aspect":"C"' in ot["text_span"]
    assert '"edge_derived_legacy_fallback":false' in ot["text_span"]

    tx = evidence[evidence["source"] == "TxGNN"].iloc[0]
    assert tx["source_dataset"] == "txgnn_legacy_reactome"
    assert tx["predicate"] == "pathway_membership"
    assert tx["direction"] == "pathway_contains_gene"
    assert "R-HSA-109704" in tx["source_record_id"]
    assert '"edge_derived_legacy_fallback":true' in tx["text_span"]
    assert "no gene-to-protein projection" in tx["text_span"]

    assert audit_edge_evidence(tmp_path / "kg", relations=["pathway_contains_gene"]).ok


def test_pathway_contains_gene_backfill_rejects_protein_projection(tmp_path: Path) -> None:
    from manage_db.backfill_edge_evidence import _pathway_contains_gene_evidence_from_edges

    with pytest.raises(ValueError, match="refuses non-gene endpoints"):
        _pathway_contains_gene_evidence_from_edges(
            pd.DataFrame(
                [
                    {
                        "x_id": "R-HSA-1",
                        "x_type": "pathway",
                        "y_id": "P12345",
                        "y_type": "protein",
                        "relation": "pathway_contains_gene",
                        "source": "TxGNN",
                    }
                ]
            )
        )



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


def test_backfill_molecule_targets_gene_accepts_legacy_gene_moa_rows(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_edge_evidence import backfill_edge_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(
        root,
        "molecule_targets_gene",
        pd.DataFrame(
            [
                {
                    "x_id": "CHEMBL1",
                    "x_type": "molecule",
                    "y_id": "ENSG000001",
                    "y_type": "gene",
                    "relation": "molecule_targets_gene",
                    "display_relation": "receptor antagonist",
                    "source": "OpenTargets",
                    "credibility": 3,
                    "action_type": "ANTAGONIST",
                    "target_class": "receptor",
                    "release": "26.03",
                }
            ]
        ),
    )

    assert backfill_edge_evidence(tmp_path / "kg", ["molecule_targets_gene"]) == {
        "molecule_targets_gene": 1
    }

    evidence = read_evidence(root, "molecule_targets_gene")
    assert len(evidence) == 1
    assert evidence.loc[0, "edge_key"] == "molecule_targets_gene|CHEMBL1|ENSG000001"
    assert evidence.loc[0, "y_type"] == "gene"
    assert evidence.loc[0, "source"] == "OpenTargets"
    assert evidence.loc[0, "source_dataset"] == "drug_mechanism_of_action"
    assert evidence.loc[0, "predicate"] == "ANTAGONIST"
    assert evidence.loc[0, "direction"] == "ANTAGONIST"
    assert evidence.loc[0, "source_record_id"] == (
        "OpenTargets:drug_mechanism_of_action:molecule_targets_gene:CHEMBL1:ENSG000001:ANTAGONIST"
    )
    assert evidence.loc[0, "release"] == "26.03"
    text_span = json.loads(evidence.loc[0, "text_span"])
    assert text_span["mechanism_of_action"] == "receptor antagonist"
    assert text_span["action_type"] == "ANTAGONIST"
    assert text_span["target_class"] == "receptor"
    assert text_span["target_id_namespace"] == "ENSG"
    assert "no gene-to-protein projection" in text_span["endpoint_policy"]
    assert audit_edge_evidence(tmp_path / "kg", relations=["molecule_targets_gene"]).ok



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



def test_build_molecule_treats_disease_clinical_evidence_maps_chembl_drugbank(tmp_path: Path) -> None:
    from manage_db.backfill_edge_evidence import build_molecule_treats_disease_clinical_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    edge_dir = tmp_path / "kg" / "edges"
    evidence_dir = tmp_path / "kg" / "evidence"
    edge_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "x_id": "DB001",
                "x_type": "molecule",
                "y_id": "MONDO:1",
                "y_type": "disease",
                "relation": "molecule_treats_disease",
                "display_relation": "indication",
                "source": "TxGNN",
                "credibility": 3,
            }
        ]
    ).to_parquet(edge_dir / "molecule_treats_disease.parquet", index=False)

    clinical = tmp_path / "clinical_indication.parquet"
    pd.DataFrame(
        [
            {
                "id": "clinical-row-1",
                "maxClinicalStage": "APPROVAL",
                "clinicalReportIds": ["nct123", "emea/h/c/1"],
                "diseaseId": "MONDO_1",
                "drugId": "CHEMBL1",
            },
            {
                "id": "clinical-row-unmatched",
                "maxClinicalStage": "PHASE_2",
                "clinicalReportIds": ["nct999"],
                "diseaseId": "MONDO_2",
                "drugId": "CHEMBL1",
            },
        ]
    ).to_parquet(clinical, index=False)

    drug_dir = tmp_path / "drug_molecule"
    drug_dir.mkdir()
    pd.DataFrame(
        [
            {
                "id": "CHEMBL1",
                "crossReferences": [{"source": "drugbank", "ids": ["DB001"]}],
            }
        ]
    ).to_parquet(drug_dir / "part-000.parquet", index=False)

    out = evidence_dir / "molecule_treats_disease.parquet"
    counts = build_molecule_treats_disease_clinical_evidence(
        edge_dir / "molecule_treats_disease.parquet",
        clinical,
        drug_dir,
        out,
    )
    assert counts == {"molecule_treats_disease": 1}

    evidence = read_evidence(root, "molecule_treats_disease")
    assert len(evidence) == 1
    row = evidence.iloc[0]
    assert row["edge_key"] == "molecule_treats_disease|DB001|MONDO:1"
    assert row["source"] == "OpenTargets"
    assert row["source_dataset"] == "clinical_indication"
    assert row["source_record_id"] == "clinical-row-1"
    assert row["predicate"] == "APPROVAL"
    assert row["direction"] == "indication"
    assert row["study_id"] == "nct123;emea/h/c/1"


def test_backfill_molecule_targets_gene_cleans_txgnn_stale_protein_metadata(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_edge_evidence import backfill_edge_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(
        root,
        "molecule_targets_gene",
        pd.DataFrame(
            [
                {
                    "x_id": "DB0001",
                    "x_type": "molecule",
                    "y_id": "NCBI:7157",
                    "y_type": "gene",
                    "relation": "molecule_targets_gene",
                    "display_relation": "targets",
                    "source": "TxGNN/molecule_targets_protein",
                    "credibility": 3,
                    "direction": "molecule_targets_protein",
                },
                {
                    "x_id": "CTD:C000228",
                    "x_type": "molecule",
                    "y_id": "NCBI:1017",
                    "y_type": "gene",
                    "relation": "molecule_targets_gene",
                    "display_relation": "targets",
                    "source": "TxGNN",
                    "credibility": 3,
                },
            ]
        ),
    )

    assert backfill_edge_evidence(tmp_path / "kg", ["molecule_targets_gene"]) == {
        "molecule_targets_gene": 2
    }
    evidence = read_evidence(root, "molecule_targets_gene").sort_values("x_id").reset_index(drop=True)

    assert set(evidence["source"]) == {"TxGNN"}
    assert set(evidence["y_type"]) == {"gene"}
    assert set(evidence["direction"]) == {""}
    assert "molecule_targets_protein" not in set(evidence["predicate"])
    assert "molecule_targets_protein" not in ";".join(evidence["source_record_id"].tolist())
    assert evidence.loc[evidence["x_id"] == "DB0001", "source_dataset"].iloc[0] == "drug_protein"
    assert evidence.loc[evidence["x_id"] == "DB0001", "predicate"].iloc[0] == "drug_protein"
    assert evidence.loc[evidence["x_id"] == "CTD:C000228", "source_dataset"].iloc[0] == "ctd_chemical_gene"
    assert evidence.loc[evidence["x_id"] == "CTD:C000228", "predicate"].iloc[0] == "chemical_gene_target"
    text_span = json.loads(evidence.loc[evidence["x_id"] == "DB0001", "text_span"].iloc[0])
    assert text_span["legacy_relation"] == "molecule_targets_protein"
    assert "no gene-to-protein projection" in text_span["endpoint_policy"]
    assert audit_edge_evidence(tmp_path / "kg", relations=["molecule_targets_gene"]).ok


def test_build_molecule_targets_protein_staged_accepts_only_native_protein_rows(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_edge_evidence import build_molecule_targets_protein_staged
    from manage_db.kg_evidence import read_evidence
    from manage_db.kg_storage import read_edges

    root = open_kg_root(str(tmp_path / "kg"))
    counts = build_molecule_targets_protein_staged(
        tmp_path / "kg",
        pd.DataFrame(
            [
                {
                    "x_id": "CHEMBL1",
                    "y_id": "ENSP00000369497",
                    "y_type": "protein",
                    "source": "CuratedDB",
                    "source_dataset": "protein_binding",
                    "source_record_id": "CuratedDB:row1",
                    "action_type": "INHIBITOR",
                    "mechanism": "Example kinase inhibitor",
                    "target_class": "kinase",
                    "target_chembl_id": "CHEMBLT1",
                    "target_uniprot_id": "P11111",
                    "target_component_id": 11,
                    "target_confidence": '{"direct_interaction":1}',
                    "release": "2026-06",
                }
            ]
        ),
    )

    assert counts == {"molecule_targets_protein": 1}
    edge = read_edges(root, "molecule_targets_protein").iloc[0]
    assert edge["x_type"] == "molecule"
    assert edge["y_type"] == "protein"
    assert edge["relation"] == "molecule_targets_protein"
    evidence = read_evidence(root, "molecule_targets_protein")
    assert evidence.loc[0, "edge_key"] == "molecule_targets_protein|CHEMBL1|ENSP00000369497"
    assert evidence.loc[0, "predicate"] == "INHIBITOR"
    assert evidence.loc[0, "source_record_id"] == "CuratedDB:row1"
    assert evidence.loc[0, "release"] == "2026-06"
    text_span = json.loads(evidence.loc[0, "text_span"])
    assert text_span["target_id_namespace"] == "ENSP"
    assert text_span["source_database"] == "CuratedDB"
    assert text_span["source_dataset"] == "protein_binding"
    assert text_span["target_chembl_id"] == "CHEMBLT1"
    assert text_span["target_uniprot_id"] == "P11111"
    assert text_span["target_component_id"] == "11"
    assert text_span["target_confidence"] == '{"direct_interaction":1}'
    assert "not projected from gene endpoint" in text_span["endpoint_policy"]
    assert audit_edge_evidence(tmp_path / "kg", relations=["molecule_targets_protein"]).ok

    with pytest.raises(ValueError, match="source-native protein endpoints"):
        build_molecule_targets_protein_staged(
            tmp_path / "kg2",
            pd.DataFrame(
                [
                    {
                        "x_id": "CHEMBL1",
                        "y_id": "ENSG000001",
                        "y_type": "gene",
                        "source": "OpenTargets",
                        "source_dataset": "drug_mechanism_of_action",
                    }
                ]
            ),
        )
