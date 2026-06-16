from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_eva_hp_pathogenic_filter_normalizes_only_hpo_causal_rows() -> None:
    from manage_db.build_mutation_causes_phenotype import build_rows_from_eva_frame

    source = pd.DataFrame(
        [
            {
                "id": "eva-row-1",
                "variantId": "1_100_A_T",
                "diseaseId": "HP_0001250",
                "clinicalSignificances": ["pathogenic"],
                "studyId": "RCV0001",
                "score": 0.9,
                "literature": ["12345", "PMID:67890"],
                "alleleOrigins": ["germline"],
                "datasourceId": "eva",
                "datasourceVersion": "26.03",
                "variantFunctionalConsequenceId": "SO_0001583",
            },
            {
                "id": "eva-row-2",
                "variantId": "1_101_G_C",
                "diseaseId": "HP:0004322",
                "clinicalSignificances": ["Likely pathogenic"],
                "studyId": "RCV0002",
                "score": 0.8,
                "literature": [],
                "alleleOrigins": ["germline"],
            },
            {
                "id": "eva-row-benign",
                "variantId": "1_102_A_C",
                "diseaseId": "HP_0000001",
                "clinicalSignificances": ["benign"],
            },
            {
                "id": "eva-row-disease",
                "variantId": "1_103_A_C",
                "diseaseId": "MONDO_0000001",
                "clinicalSignificances": ["pathogenic"],
            },
            {
                "id": "eva-row-uncertain",
                "variantId": "1_104_A_C",
                "diseaseId": "HP_0000002",
                "clinicalSignificances": ["uncertain significance"],
            },
        ]
    )

    edges, evidence = build_rows_from_eva_frame(source)

    assert list(edges["x_id"]) == ["1_100_A_T", "1_101_G_C"]
    assert list(edges["y_id"]) == ["HP:0001250", "HP:0004322"]
    assert set(edges["relation"]) == {"mutation_causes_phenotype"}
    assert set(edges["x_type"]) == {"mutation"}
    assert set(edges["y_type"]) == {"phenotype"}
    assert set(edges["credibility"]) == {3}

    assert len(evidence) == 4  # one database row for each edge, plus two PMID support rows
    assert set(evidence["edge_key"]) == {
        "mutation_causes_phenotype|1_100_A_T|HP:0001250",
        "mutation_causes_phenotype|1_101_G_C|HP:0004322",
    }
    db_record = evidence[evidence["source_record_id"] == "eva-row-1"].iloc[0]
    assert db_record["evidence_type"] == "database_record"
    assert db_record["source"] == "OpenTargets"
    assert db_record["source_dataset"] == "evidence_eva"
    assert db_record["study_id"] == "RCV0001"
    assert db_record["evidence_score"] == 0.9
    assert db_record["predicate"] == "pathogenic"
    assert db_record["release"] == "26.03"
    assert set(evidence["paper_id"]) == {"", "PMID:12345", "PMID:67890"}


def test_local_builder_writes_valid_edge_and_evidence_parquets(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.build_mutation_causes_phenotype import build_local_mutation_causes_phenotype
    from manage_db.kg_evidence import read_evidence
    from manage_db.kg_storage import open_kg_root, read_edges, write_nodes

    kg_root = tmp_path / "kg"
    root = open_kg_root(str(kg_root))
    write_nodes(
        root,
        "mutation",
        pd.DataFrame(
            [
                {"id": "1_100_A_T", "hgvs": "", "clinvar_id": "", "gnomad_id": ""},
                {"id": "1_101_G_C", "hgvs": "", "clinvar_id": "", "gnomad_id": ""},
            ]
        ),
    )
    write_nodes(
        root,
        "phenotype",
        pd.DataFrame(
            [
                {"id": "HP:0001250", "mondo_id": "", "efo_id": "", "mp_id": "", "mesh_id": ""},
                {"id": "HP:0004322", "mondo_id": "", "efo_id": "", "mp_id": "", "mesh_id": ""},
            ]
        ),
    )

    source_dir = tmp_path / "evidence_eva"
    source_dir.mkdir()
    pd.DataFrame(
        [
            {
                "id": "eva-row-1",
                "variantId": "1_100_A_T",
                "diseaseId": "HP_0001250",
                "clinicalSignificances": ["pathogenic"],
                "score": 0.9,
            },
            {
                "id": "eva-row-2",
                "variantId": "1_101_G_C",
                "diseaseId": "HP_0004322",
                "clinicalSignificances": ["likely_pathogenic"],
                "score": 0.7,
            },
        ]
    ).to_parquet(source_dir / "part-000.parquet", index=False)

    counts = build_local_mutation_causes_phenotype(source_dir, kg_root)

    assert counts["source_rows"] == 2
    assert counts["hp_rows"] == 2
    assert counts["pathogenic_hp_rows"] == 2
    assert counts["edge_rows"] == 2
    assert counts["evidence_rows"] == 2
    assert counts["missing_mutation_endpoints"] == 0
    assert counts["missing_phenotype_endpoints"] == 0
    assert len(read_edges(root, "mutation_causes_phenotype")) == 2
    assert len(read_evidence(root, "mutation_causes_phenotype")) == 2
    assert audit_edge_evidence(kg_root, relations=["mutation_causes_phenotype"]).ok
