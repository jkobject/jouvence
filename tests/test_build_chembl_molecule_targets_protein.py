from __future__ import annotations

import json

import pandas as pd


def test_build_source_rows_keeps_only_unambiguous_human_protein_targets() -> None:
    from manage_db.build_chembl_molecule_targets_protein import build_source_rows

    mechanisms = [
        {
            "molecule_chembl_id": "CHEMBL1",
            "target_chembl_id": "CHEMBLT1",
            "mec_id": 1,
            "record_id": 101,
            "action_type": "INHIBITOR",
            "mechanism_of_action": "Example target inhibitor",
            "direct_interaction": 1,
            "molecular_mechanism": 1,
            "disease_efficacy": 1,
            "max_phase": 4,
            "mechanism_refs": [{"ref_type": "PubMed", "ref_id": "12345"}],
        },
        {
            "molecule_chembl_id": "CHEMBL1",
            "target_chembl_id": "CHEMBLT_AMBIG",
            "mec_id": 2,
            "action_type": "AGONIST",
            "mechanism_of_action": "Ambiguous target agonist",
            "direct_interaction": 1,
        },
        {
            "molecule_chembl_id": "CHEMBL_MISSING",
            "target_chembl_id": "CHEMBLT1",
            "mec_id": 3,
            "action_type": "INHIBITOR",
        },
        {
            "molecule_chembl_id": "CHEMBL1",
            "target_chembl_id": "CHEMBLT_MOUSE",
            "mec_id": 4,
            "action_type": "INHIBITOR",
        },
    ]
    targets = {
        "CHEMBLT1": {
            "target_chembl_id": "CHEMBLT1",
            "pref_name": "Example target",
            "target_type": "SINGLE PROTEIN",
            "organism": "Homo sapiens",
            "target_components": [
                {
                    "accession": "P11111",
                    "component_id": 11,
                    "component_type": "PROTEIN",
                    "relationship": "SINGLE PROTEIN",
                    "component_description": "Example protein",
                }
            ],
        },
        "CHEMBLT_AMBIG": {
            "target_chembl_id": "CHEMBLT_AMBIG",
            "pref_name": "Ambiguous target",
            "target_type": "SINGLE PROTEIN",
            "organism": "Homo sapiens",
            "target_components": [
                {"accession": "P22222", "component_id": 22, "component_type": "PROTEIN"}
            ],
        },
        "CHEMBLT_MOUSE": {
            "target_chembl_id": "CHEMBLT_MOUSE",
            "pref_name": "Mouse target",
            "target_type": "SINGLE PROTEIN",
            "organism": "Mus musculus",
            "target_components": [
                {"accession": "P33333", "component_id": 33, "component_type": "PROTEIN"}
            ],
        },
    }
    protein_nodes = pd.DataFrame(
        [
            {"id": "ENSP000001", "uniprot_id": "P11111"},
            {"id": "ENSP000002A", "uniprot_id": "P22222"},
            {"id": "ENSP000002B", "uniprot_id": "P22222"},
        ]
    )
    molecule_nodes = pd.DataFrame([{"id": "CHEMBL1"}])

    rows, report = build_source_rows(
        mechanisms,
        targets,
        protein_nodes,
        molecule_nodes,
        release="test-release",
    )

    assert len(rows) == 1
    row = rows.iloc[0]
    assert row["x_id"] == "CHEMBL1"
    assert row["y_id"] == "ENSP000001"
    assert row["y_type"] == "protein"
    assert row["source"] == "ChEMBL"
    assert row["source_dataset"] == "mechanism"
    assert row["source_record_id"] == "ChEMBL:mechanism:molecule_targets_protein:mec_id=1:target=CHEMBLT1:uniprot=P11111"
    assert row["paper_id"] == "PMID:12345"
    assert row["release"] == "test-release"
    assert row["target_uniprot_id"] == "P11111"
    assert json.loads(row["target_confidence"]) == {
        "direct_interaction": 1,
        "disease_efficacy": 1,
        "max_phase": 4,
        "molecular_mechanism": 1,
    }
    assert report["rejected"]["missing_molecule_node"] == 1
    assert report["rejected"]["non_human_target"] == 1
    assert report["rejected"]["ambiguous_uniprot_to_protein_nodes"] == 1
    assert "no gene target rows consumed" in report["endpoint_policy"]
