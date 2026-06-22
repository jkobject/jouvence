from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from manage_db.kg_storage import open_kg_root, write_nodes


MITAB_COLUMNS = [
    "ID(s) interactor A",
    "ID(s) interactor B",
    "Alt. ID(s) interactor A",
    "Alt. ID(s) interactor B",
    "Alias(es) interactor A",
    "Alias(es) interactor B",
    "Interaction detection method(s)",
    "Publication 1st author(s)",
    "Publication Identifier(s)",
    "Taxid interactor A",
    "Taxid interactor B",
    "Interaction type(s)",
    "Source database(s)",
    "Interaction identifier(s)",
    "Confidence value(s)",
    "Expansion method(s)",
    "Biological role(s) interactor A",
    "Biological role(s) interactor B",
    "Experimental role(s) interactor A",
    "Experimental role(s) interactor B",
    "Type(s) interactor A",
    "Type(s) interactor B",
    "Xref(s) interactor A",
    "Xref(s) interactor B",
    "Interaction Xref(s)",
    "Annotation(s) interactor A",
    "Annotation(s) interactor B",
    "Interaction annotation(s)",
    "Host organism(s)",
    "Interaction parameter(s)",
    "Creation date",
    "Update date",
    "Checksum(s) interactor A",
    "Checksum(s) interactor B",
    "Interaction Checksum(s)",
    "Negative",
    "Feature(s) interactor A",
    "Feature(s) interactor B",
    "Stoichiometry(s) interactor A",
    "Stoichiometry(s) interactor B",
    "Identification method participant A",
    "Identification method participant B",
]


def mitab_row(**overrides: str) -> dict[str, str]:
    row = {col: "-" for col in MITAB_COLUMNS}
    row.update(
        {
            "ID(s) interactor A": "uniprotkb:P11111",
            "ID(s) interactor B": "uniprotkb:Q22222",
            "Alt. ID(s) interactor A": "ensembl:ENSP00000111111",
            "Alt. ID(s) interactor B": "ensembl:ENSP00000222222",
            "Alias(es) interactor A": "uniprotkb:A(gene name)",
            "Alias(es) interactor B": "uniprotkb:B(gene name)",
            "Interaction detection method(s)": 'psi-mi:"MI:0019"(coimmunoprecipitation)',
            "Publication 1st author(s)": "Curator et al. (2026)",
            "Publication Identifier(s)": "pubmed:12345678|imex:IM-1",
            "Taxid interactor A": "taxid:9606(human)",
            "Taxid interactor B": "taxid:9606(human)",
            "Interaction type(s)": 'psi-mi:"MI:0407"(direct interaction)',
            "Source database(s)": 'psi-mi:"MI:0469"(IntAct)',
            "Interaction identifier(s)": "intact:EBI-1|imex:IM-1",
            "Confidence value(s)": "intact-miscore:0.67",
            "Expansion method(s)": 'psi-mi:"MI:1060"(spoke expansion)',
            "Biological role(s) interactor A": 'psi-mi:"MI:0499"(unspecified role)',
            "Biological role(s) interactor B": 'psi-mi:"MI:0499"(unspecified role)',
            "Experimental role(s) interactor A": 'psi-mi:"MI:0496"(bait)',
            "Experimental role(s) interactor B": 'psi-mi:"MI:0498"(prey)',
            "Type(s) interactor A": 'psi-mi:"MI:0326"(protein)',
            "Type(s) interactor B": 'psi-mi:"MI:0326"(protein)',
            "Negative": "false",
            "Feature(s) interactor A": "binding-associated region:1-10",
            "Feature(s) interactor B": "-",
            "Stoichiometry(s) interactor A": "1",
            "Stoichiometry(s) interactor B": "1",
            "Identification method participant A": 'psi-mi:"MI:0705"(anti tag western blot)',
            "Identification method participant B": 'psi-mi:"MI:0705"(anti tag western blot)',
        }
    )
    row.update(overrides)
    return row


def test_build_intact_filters_maps_edges_and_preserves_evidence_fields() -> None:
    from manage_db.build_intact_protein_interactions import build_from_mitab

    feature_refs = {
        "binding_regions": {
            "EBI-1": [
                {
                    "Feature AC": "EBI-FEAT-1",
                    "Feature type": 'psi-mi:"MI:0442"(sufficient binding region)',
                    "Interaction AC": "EBI-1",
                }
            ]
        }
    }
    rows = [
        (1, mitab_row()),
        (2, mitab_row(**{"ID(s) interactor B": "chebi:CHEBI:1", "Alt. ID(s) interactor B": "-", "Xref(s) interactor B": "-"})),
        (3, mitab_row(**{"Taxid interactor B": "taxid:10090(mouse)"})),
        (4, mitab_row(**{"Interaction type(s)": 'psi-mi:"MI:0208"(genetic interaction)'})),
        (5, mitab_row(**{"Negative": "true"})),
    ]

    result = build_from_mitab(
        rows,
        uniprot_to_protein={"P11111": "ENSP00000111111", "Q22222": "ENSP00000222222"},
        feature_refs_by_interaction=feature_refs,
    )

    assert result.validation["ok"]
    assert len(result.edges) == 1
    edge = result.edges.iloc[0]
    assert edge["x_id"] == "ENSP00000111111"
    assert edge["y_id"] == "ENSP00000222222"
    assert edge["relation"] == "protein_interacts_protein"

    assert len(result.evidence) == 1
    evidence = result.evidence.iloc[0]
    assert evidence["predicate"] == "direct_interaction"
    assert evidence["paper_id"] == "PMID:12345678"
    assert evidence["evidence_score"] == 0.67
    payload = json.loads(evidence["text_span"])
    assert payload["detection_method"] == 'psi-mi:"MI:0019"(coimmunoprecipitation)'
    assert payload["interaction_type_mi_terms"] == ["MI:0407"]
    assert payload["selected_interactor_a_namespace"] == "uniprotkb"
    assert payload["selected_interactor_b_namespace"] == "uniprotkb"
    assert payload["feature_side_table_refs"]["binding_regions"] == ["EBI-FEAT-1"]
    assert payload["negative"] is False

    assert set(result.rejected["reason"]) == {
        "unsupported_endpoint_namespace",
        "non_human_or_cross_species",
        "interaction_type_not_allowlisted",
    }
    assert len(result.negative_evidence) == 1


def test_build_intact_quarantines_mi0914_only_but_keeps_direct_and_physical_association() -> None:
    from manage_db.build_intact_protein_interactions import build_from_mitab

    rows = [
        (
            1,
            mitab_row(
                **{
                    "ID(s) interactor A": "uniprotkb:P11111",
                    "ID(s) interactor B": "uniprotkb:Q22222",
                    "Interaction identifier(s)": "intact:EBI-direct",
                    "Interaction type(s)": 'psi-mi:"MI:0407"(direct interaction)',
                }
            ),
        ),
        (
            2,
            mitab_row(
                **{
                    "ID(s) interactor A": "uniprotkb:P33333",
                    "ID(s) interactor B": "uniprotkb:Q44444",
                    "Alt. ID(s) interactor A": "ensembl:ENSP00000333333",
                    "Alt. ID(s) interactor B": "ensembl:ENSP00000444444",
                    "Interaction identifier(s)": "intact:EBI-physical",
                    "Interaction type(s)": 'psi-mi:"MI:0915"(physical association)',
                }
            ),
        ),
        (
            3,
            mitab_row(
                **{
                    "ID(s) interactor A": "uniprotkb:P55555",
                    "ID(s) interactor B": "uniprotkb:Q66666",
                    "Alt. ID(s) interactor A": "ensembl:ENSP00000555555",
                    "Alt. ID(s) interactor B": "ensembl:ENSP00000666666",
                    "Interaction identifier(s)": "intact:EBI-association",
                    "Interaction type(s)": 'psi-mi:"MI:0914"(association)',
                }
            ),
        ),
    ]

    result = build_from_mitab(rows)

    assert set(result.evidence["predicate"]) == {"direct_interaction", "physical_association"}
    assert len(result.edges) == 2
    assert result.rejected["reason"].tolist() == ["interaction_type_association_too_broad"]
    rejected_payload = json.loads(result.rejected.iloc[0]["source_payload"])
    assert rejected_payload["interaction_type_mi_terms"] == ["MI:0914"]
    assert rejected_payload["raw_mitab"]["Interaction identifier(s)"] == "intact:EBI-association"


def test_build_intact_quarantines_self_loop_without_explicit_homodimer_support() -> None:
    from manage_db.build_intact_protein_interactions import build_from_mitab

    result = build_from_mitab(
        [
            (
                1,
                mitab_row(
                    **{
                        "ID(s) interactor A": "uniprotkb:P11111",
                        "ID(s) interactor B": "uniprotkb:P11111",
                        "Alt. ID(s) interactor A": "ensembl:ENSP00000111111",
                        "Alt. ID(s) interactor B": "ensembl:ENSP00000111111",
                        "Interaction identifier(s)": "intact:EBI-self-loop",
                    }
                ),
            )
        ]
    )

    assert result.edges.empty
    assert result.evidence.empty
    assert result.rejected["reason"].tolist() == ["self_loop_requires_homodimer_support"]
    rejected_payload = json.loads(result.rejected.iloc[0]["source_payload"])
    assert rejected_payload["source_interactor_a_id"] == "uniprotkb:P11111"
    assert rejected_payload["source_interactor_b_id"] == "uniprotkb:P11111"


def test_build_intact_accepts_self_loop_with_explicit_homodimer_support() -> None:
    from manage_db.build_intact_protein_interactions import build_from_mitab

    result = build_from_mitab(
        [
            (
                1,
                mitab_row(
                    **{
                        "ID(s) interactor A": "uniprotkb:P11111",
                        "ID(s) interactor B": "uniprotkb:P11111",
                        "Alt. ID(s) interactor A": "ensembl:ENSP00000111111",
                        "Alt. ID(s) interactor B": "ensembl:ENSP00000111111",
                        "Interaction identifier(s)": "intact:EBI-homodimer",
                        "Interaction annotation(s)": "comment:explicit homodimer observed",
                    }
                ),
            )
        ]
    )

    assert len(result.edges) == 1
    assert result.edges.iloc[0]["x_id"] == "P11111"
    assert result.edges.iloc[0]["y_id"] == "P11111"
    assert len(result.evidence) == 1
    payload = json.loads(result.evidence.iloc[0]["text_span"])
    assert payload["self_loop_policy"] == "accepted_explicit_homodimer_support"


def test_build_intact_rejects_unmapped_nodes_when_node_mapping_supplied() -> None:
    from manage_db.build_intact_protein_interactions import build_from_mitab

    result = build_from_mitab(
        [(1, mitab_row())],
        uniprot_to_protein={"P11111": "ENSP00000111111"},
    )

    assert result.edges.empty
    assert result.evidence.empty
    assert result.rejected.iloc[0]["reason"] == "protein_node_unmapped"
    assert result.validation["checks"]["node_endpoint_antijoin"]["rejected_unmapped_candidate_rows"] == 1


def test_intact_cli_writes_staged_outputs_without_canonical_promotion(tmp_path: Path) -> None:
    from manage_db.build_intact_protein_interactions import main
    from manage_db.kg_evidence import read_evidence
    from manage_db.kg_storage import read_edges

    node_root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(
        node_root,
        "protein",
        pd.DataFrame(
            [
                {"id": "ENSP00000111111", "ensembl_gene_id": "ENSG1", "uniprot_id": "P11111", "refseq_protein": "", "pdb_ids": ""},
                {"id": "ENSP00000222222", "ensembl_gene_id": "ENSG2", "uniprot_id": "Q22222", "refseq_protein": "", "pdb_ids": ""},
            ]
        ),
    )
    mitab_path = tmp_path / "human.tsv"
    pd.DataFrame([mitab_row()])[MITAB_COLUMNS].to_csv(mitab_path, sep="\t", index=False)
    feature_path = tmp_path / "bindings_regions.tsv"
    pd.DataFrame(
        [
            {
                "Feature AC": "EBI-FEAT-1",
                "Feature short label": "region",
                "Feature range(s)": "1-10",
                "Original sequence": "-",
                "Resulting sequence": "-",
                "Feature type": 'psi-mi:"MI:0442"(sufficient binding region)',
                "Feature annotation(s)": "x" * 200_000,
                "Affected molecule identifier": "uniprotkb:P11111",
                "Affected molecule symbol": "A",
                "Affected molecule full name": "A protein",
                "Affected molecule organism": "taxid:9606(human)",
                "Interaction participants": "P11111|Q22222",
                "PubMed ID": "12345678",
                "Figure legend(s)": "fig 1",
                "Interaction AC": "EBI-1",
                "Xref ID(s)": "-",
            }
        ]
    ).to_csv(feature_path, sep="\t", index=False)

    out = tmp_path / "staging" / "intact-protein-interactions-test"
    assert (
        main(
            [
                "--input",
                str(mitab_path),
                "--node-root",
                str(tmp_path / "kg"),
                "--output-dir",
                str(out),
                "--feature",
                f"binding_regions={feature_path}",
            ]
        )
        == 0
    )

    staged = open_kg_root(str(out))
    edges = read_edges(staged, "protein_interacts_protein")
    evidence = read_evidence(staged, "protein_interacts_protein")
    manifest = json.loads((out / "MANIFEST.json").read_text())
    validation = json.loads((out / "reports" / "validation.json").read_text())

    assert len(edges) == 1
    assert len(evidence) == 1
    assert manifest["staging_only"] is True
    assert manifest["canonical_promotion"] is False
    assert validation["checks"]["evidence_support"]["ok"] is True
    assert (out / "evidence" / "protein_interacts_protein_negative.parquet").exists()
