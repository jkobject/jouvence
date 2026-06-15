from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from manage_db.kg_storage import open_kg_root, write_edges


_REQUIRED_EDGE = pd.DataFrame(
    [
        {
            "x_id": "EFO:1",
            "x_type": "disease",
            "y_id": "ENSG1",
            "y_type": "gene",
            "relation": "disease_associated_gene",
            "display_relation": "associated with",
            "source": "OpenTargets/reactome",
            "credibility": 2,
        }
    ]
)


def test_write_read_evidence_deduplicates_support_records(tmp_path: Path) -> None:
    from manage_db.kg_evidence import read_evidence, write_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    evidence = pd.DataFrame(
        [
            {
                "relation": "disease_associated_gene",
                "x_id": "EFO:1",
                "x_type": "disease",
                "y_id": "ENSG1",
                "y_type": "gene",
                "evidence_type": "database_record",
                "source": "OpenTargets",
                "source_dataset": "reactome",
                "source_record_id": "reactome:row-1",
                "paper_id": "PMID:123",
                "dataset_id": "",
                "study_id": "",
                "evidence_score": 0.9,
                "direction": "",
                "predicate": "affected_pathway",
            },
            {
                "relation": "disease_associated_gene",
                "x_id": "EFO:1",
                "x_type": "disease",
                "y_id": "ENSG1",
                "y_type": "gene",
                "evidence_type": "database_record",
                "source": "OpenTargets",
                "source_dataset": "reactome",
                "source_record_id": "reactome:row-1",
                "paper_id": "PMID:123",
                "dataset_id": "",
                "study_id": "",
                "evidence_score": 0.9,
                "direction": "",
                "predicate": "affected_pathway",
            },
        ]
    )

    assert write_evidence(root, "disease_associated_gene", evidence) == 1

    got = read_evidence(root, "disease_associated_gene")
    assert len(got) == 1
    assert got.loc[0, "edge_key"] == "disease_associated_gene|EFO:1|ENSG1"
    assert got.loc[0, "source_record_id"] == "reactome:row-1"
    assert got.loc[0, "evidence_score"] == 0.9


def test_audit_edge_evidence_reports_missing_and_orphan_support(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence, main
    from manage_db.kg_evidence import write_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(root, "disease_associated_gene", _REQUIRED_EDGE)
    write_evidence(
        root,
        "disease_associated_gene",
        pd.DataFrame(
            [
                {
                    "relation": "disease_associated_gene",
                    "x_id": "EFO:2",
                    "x_type": "disease",
                    "y_id": "ENSG2",
                    "y_type": "gene",
                    "evidence_type": "paper",
                    "source": "EuropePMC",
                    "source_dataset": "europepmc",
                    "source_record_id": "PMID:999",
                    "paper_id": "PMID:999",
                    "dataset_id": "",
                    "study_id": "",
                }
            ]
        ),
    )

    audit = audit_edge_evidence(tmp_path / "kg")
    report = audit.relation_reports["disease_associated_gene"]
    assert report.edge_rows == 1
    assert report.evidence_rows == 1
    assert report.edges_without_evidence == 1
    assert report.evidence_without_edge == 1

    assert main([str(tmp_path / "kg"), "--fail-on-missing"]) == 1


def test_audit_edge_evidence_json_cli(tmp_path: Path, capsys) -> None:
    from manage_db.audit_edge_evidence import main
    from manage_db.kg_evidence import write_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(root, "disease_associated_gene", _REQUIRED_EDGE)
    write_evidence(
        root,
        "disease_associated_gene",
        pd.DataFrame(
            [
                {
                    "relation": "disease_associated_gene",
                    "x_id": "EFO:1",
                    "x_type": "disease",
                    "y_id": "ENSG1",
                    "y_type": "gene",
                    "evidence_type": "database_record",
                    "source": "OpenTargets",
                    "source_dataset": "reactome",
                    "source_record_id": "row-1",
                }
            ]
        ),
    )

    assert main([str(tmp_path / "kg"), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["relation_reports"]["disease_associated_gene"]["evidence_rows"] == 1
