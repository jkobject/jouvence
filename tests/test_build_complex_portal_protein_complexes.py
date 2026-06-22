from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def complex_row(**overrides: str) -> dict[str, str]:
    row = {
        "#Complex ac": "CPX-TEST",
        "Recommended name": "test protein complex",
        "Aliases for complex": "alias-1|alias-2",
        "Taxonomy identifier": "9606",
        "Identifiers (and stoichiometry) of molecules in complex": "P11111(2)|Q22222(1)|Q33333(1)|NOHIT1(1)|CPX-999999(1)",
        "Evidence Code": "ECO:0005547(manual assertion)",
        "Experimental evidence": "pubmed:12345678",
        "Go Annotations": "GO:0000001(fake term)",
        "Cross references": "complex portal:CPX-TEST(complex-primary)|pubmed:87654321(see-also)",
        "Description": "A test complex.",
        "Complex properties": "property",
        "Complex assembly": "Heteropentamer",
        "Ligand": "CHEBI:1(fake ligand)",
        "Disease": "MONDO:1(fake disease)",
        "Agonist": "-",
        "Antagonist": "-",
        "Comment": "-",
        "Source": "psi-mi:\"MI:0469\"(IntAct)",
        "Expanded participant list": "P11111(2)|Q22222(1)|Q33333(1)|NOHIT1(1)|CPX-CHILD(1)",
    }
    row.update(overrides)
    return row


def test_complex_portal_builder_nodes_edges_rejects_and_nested(tmp_path: Path) -> None:
    from manage_db.build_complex_portal_protein_complexes import build_staged_complex_portal

    protein_nodes = tmp_path / "protein.parquet"
    pd.DataFrame(
        [
            {"id": "ENSP00000111111", "uniprot_id": "P11111"},
            {"id": "ENSP00000222222", "uniprot_id": "Q22222"},
            {"id": "ENSP00000333333", "uniprot_id": "Q33333"},
            {"id": "ENSP00000333334", "uniprot_id": "Q33333"},
        ]
    ).to_parquet(protein_nodes, index=False)

    complextab = tmp_path / "9606.tsv"
    pd.DataFrame(
        [
            complex_row(),
            complex_row(**{"#Complex ac": "CPX-999999", "Recommended name": "child complex", "Identifiers (and stoichiometry) of molecules in complex": "P11111(1)"}),
            complex_row(**{"#Complex ac": "CPX-MOUSE", "Taxonomy identifier": "10090"}),
        ]
    ).to_csv(complextab, sep="\t", index=False)

    out_dir = tmp_path / "staging"
    report = build_staged_complex_portal(
        input_path=complextab,
        protein_nodes_path=protein_nodes,
        output_dir=out_dir,
    )

    assert report["ok"]
    assert report["counts"]["protein_complex_nodes"] == 2
    assert report["counts"]["protein_part_of_protein_complex_edges"] == 3
    assert report["counts"]["protein_part_of_protein_complex_evidence"] == 3
    assert report["counts"]["nested_complex_edges"] == 1
    assert report["counts"]["rejected_participants"] == 2
    assert report["source_counts"]["rejected_non_human_complex"] == 1

    nodes = pd.read_parquet(out_dir / "nodes" / "protein_complex.parquet")
    assert set(nodes["id"]) == {"CPX-TEST", "CPX-999999"}
    parent = nodes[nodes["id"].eq("CPX-TEST")].iloc[0]
    assert parent["disease_xrefs"] == "MONDO:1(fake disease)"
    assert json.loads(parent["stoichiometry_json"])[0] == {"id": "P11111", "namespace": "uniprotkb", "stoichiometry": "2"}

    edges = pd.read_parquet(out_dir / "edges" / "protein_part_of_protein_complex.parquet")
    assert set(edges["x_id"]) == {"ENSP00000111111", "ENSP00000222222"}
    assert set(edges["y_id"]) == {"CPX-TEST", "CPX-999999"}
    assert set(edges["relation"]) == {"protein_part_of_protein_complex"}

    evidence = pd.read_parquet(out_dir / "evidence" / "protein_part_of_protein_complex.parquet")
    test_evidence = evidence[evidence["y_id"].eq("CPX-TEST") & evidence["x_id"].eq("ENSP00000111111")].iloc[0]
    assert test_evidence["stoichiometry"] == "2"
    assert test_evidence["mapping_confidence"] == "exact_unique_uniprot_xref"
    assert test_evidence["pmids"] == "PMID:87654321|PMID:12345678"

    nested = pd.read_parquet(out_dir / "edges" / "protein_complex_part_of_protein_complex.parquet")
    assert nested.to_dict("records") == [
        {
            "x_id": "CPX-999999",
            "x_type": "protein_complex",
            "y_id": "CPX-TEST",
            "y_type": "protein_complex",
            "relation": "protein_complex_part_of_protein_complex",
            "display_relation": "complex part of complex",
            "source": "complex_portal",
            "credibility": 3,
        }
    ]

    rejected = pd.read_parquet(out_dir / "mappings" / "complex_portal_participants_rejected.parquet")
    assert set(rejected["reason"]) == {"uniprot_maps_to_multiple_protein_nodes", "uniprot_unmapped_to_protein_node"}
    ambiguous = rejected[rejected["reason"].eq("uniprot_maps_to_multiple_protein_nodes")].iloc[0]
    assert ambiguous["source_participant_id"] == "Q33333"
    assert ambiguous["candidate_protein_ids"] == "ENSP00000333333|ENSP00000333334"

    build_report = json.loads((out_dir / "validation" / "complex_portal_build_report.json").read_text())
    assert build_report["checks"]["no_member_disease_projection"]["ok"]
    assert build_report["canonical_promotion"] is False
