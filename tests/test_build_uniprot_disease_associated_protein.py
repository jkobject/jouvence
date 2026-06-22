from pathlib import Path

import pandas as pd

from manage_db.build_uniprot_disease_associated_protein import (
    RELATION,
    build_rows,
    parse_humsavar_text,
)


def _disease_comment_entry():
    return {
        "primaryAccession": "Q9NRG9",
        "uniProtkbId": "AAAS_HUMAN",
        "comments": [
            {
                "commentType": "DISEASE",
                "disease": {
                    "diseaseId": "Achalasia-addisonianism-alacrima syndrome",
                    "acronym": "AAAS",
                    "description": "An autosomal recessive disorder.",
                    "diseaseCrossReference": {"database": "MIM", "id": "231550"},
                },
                "texts": [
                    {
                        "value": "Defects in AAAS are the cause of achalasia-addisonianism-alacrima syndrome.",
                        "evidences": [
                            {"evidenceCode": "ECO:0000269", "source": "PubMed", "id": "12345678"}
                        ],
                    }
                ],
            }
        ],
    }


def test_parse_humsavar_text_extracts_release_and_fixed_columns() -> None:
    text = """
Release:     2026_02 of 10-Jun-2026
_________   __________ ___________ ______________ ________ ______________ _____________________
AAAS        Q9NRG9     VAR_012804  p.Gln15Lys     LP/P     rs121918549    Achalasia-addisonianism-alacrima syndrome (AAAS) [MIM:231550]
A1BG        P04217     VAR_018369  p.His52Arg     LB/B     rs893184       -
"""
    rows, release = parse_humsavar_text(text)
    assert release == "2026_02 of 10-Jun-2026"
    assert rows[0]["gene"] == "AAAS"
    assert rows[0]["uniprot_accession"] == "Q9NRG9"
    assert rows[0]["variant_ft_id"] == "VAR_012804"
    assert rows[0]["disease_name"].endswith("[MIM:231550]")
    assert rows[1]["disease_name"] == ""


def test_build_rows_materializes_only_source_native_protein_disease_assertions(tmp_path: Path) -> None:
    protein_nodes = pd.DataFrame(
        [
            {"id": "ENSP000001", "uniprot_id": "Q9NRG9"},
            {"id": "ENSP000002", "uniprot_id": "P49588|Q99999"},
        ]
    )
    disease_nodes = pd.DataFrame(
        [
            {"id": "MONDO:0009279", "name": "triple-A syndrome", "mondo_id": "MONDO:0009279", "omim_id": "231550", "mesh_id": "", "efo_id": "", "doid_id": "DOID:0050602", "hp_id": ""},
            {"id": "MONDO:0014488", "name": "CMT2N", "mondo_id": "MONDO:0014488", "omim_id": "613287", "mesh_id": "", "efo_id": "", "doid_id": "", "hp_id": ""},
        ]
    )
    humsavar_rows = [
        {
            "gene": "AARS1",
            "uniprot_accession": "P49588",
            "variant_ft_id": "VAR_063527",
            "aa_change": "p.Arg329His",
            "variant_category": "LP/P",
            "dbsnp_id": "rs267606621",
            "disease_name": "Charcot-Marie-Tooth disease, axonal, type 2N (CMT2N) [MIM:613287]",
        },
        {
            "gene": "GENE",
            "uniprot_accession": "P00000",
            "variant_ft_id": "VAR_X",
            "aa_change": "p.Ala1Val",
            "variant_category": "LP/P",
            "dbsnp_id": "",
            "disease_name": "Known disease [MIM:231550]",
        },
        {
            "gene": "GENE",
            "uniprot_accession": "Q9NRG9",
            "variant_ft_id": "VAR_Y",
            "aa_change": "p.Ala1Val",
            "variant_category": "LP/P",
            "dbsnp_id": "",
            "disease_name": "Disease without MIM",
        },
    ]

    edges, evidence, rejected, stats = build_rows(
        uniprot_entries=[_disease_comment_entry()],
        humsavar_rows=humsavar_rows,
        protein_nodes=protein_nodes,
        disease_nodes=disease_nodes,
        uniprot_release="2026_02",
        humsavar_release="2026_02 of 10-Jun-2026",
        created_at="2026-06-22T00:00:00+00:00",
    )

    assert set(edges["relation"]) == {RELATION}
    assert set(edges["x_type"]) == {"protein"}
    assert set(edges["y_type"]) == {"disease"}
    assert {tuple(r) for r in edges[["x_id", "y_id"]].itertuples(index=False, name=None)} == {
        ("ENSP000001", "MONDO:0009279"),
        ("ENSP000002", "MONDO:0014488"),
    }
    assert "source_native_uniprot_accession_no_gene_projection" in set(evidence["extraction_method"])
    assert evidence["source_native_endpoint_policy"].str.contains("no gene-to-protein projection").all()
    assert stats["validation"]["protein_endpoint_antijoin_pass"] is True
    assert stats["validation"]["disease_endpoint_antijoin_pass"] is True
    assert stats["validation"]["edges_without_evidence"] == 0
    assert stats["validation"]["evidence_without_edge"] == 0
    assert set(rejected["reason"]) == {
        "missing_uniprot_to_protein_node_mapping",
        "missing_mim_or_disease_node_mapping",
    }
