from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from manage_db.build_reactome_pathway_protein_membership import (
    RELATION,
    build_from_reactome_mapping,
    build_staged_reactome_pathway_proteins,
)


def _mapping_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "uniprot_id": "P12345",
                "reactome_id": "R-HSA-1",
                "url": "https://reactome.org/PathwayBrowser/#/R-HSA-1",
                "pathway_name": "Accepted pathway",
                "evidence_code": "TAS",
                "species": "Homo sapiens",
            },
            {
                "uniprot_id": "P99999",
                "reactome_id": "R-HSA-1",
                "url": "https://reactome.org/PathwayBrowser/#/R-HSA-1",
                "pathway_name": "Ambiguous protein mapping",
                "evidence_code": "IEA",
                "species": "Homo sapiens",
            },
            {
                "uniprot_id": "Q00000",
                "reactome_id": "R-HSA-MISSING",
                "url": "https://reactome.org/PathwayBrowser/#/R-HSA-MISSING",
                "pathway_name": "Missing pathway node",
                "evidence_code": "IEA",
                "species": "Homo sapiens",
            },
            {
                "uniprot_id": "P12345",
                "reactome_id": "R-MMU-1",
                "url": "https://reactome.org/PathwayBrowser/#/R-MMU-1",
                "pathway_name": "Mouse row ignored",
                "evidence_code": "IEA",
                "species": "Mus musculus",
            },
        ]
    )


def test_build_from_reactome_mapping_accepts_only_source_native_unambiguous_protein_rows() -> None:
    result = build_from_reactome_mapping(
        _mapping_fixture(),
        uniprot_to_protein={"P12345": "ENSP000001"},
        ambiguous_uniprot={"P99999": ["ENSP9", "ENSP10"]},
        pathway_ids={"R-HSA-1"},
        release="2026-03-23",
        created_at="2026-06-22T00:00:00+00:00",
    )

    assert result.validation["ok"] is True
    assert len(result.edges) == 1
    assert result.edges.loc[0, "relation"] == RELATION
    assert result.edges.loc[0, "x_id"] == "R-HSA-1"
    assert result.edges.loc[0, "x_type"] == "pathway"
    assert result.edges.loc[0, "y_id"] == "ENSP000001"
    assert result.edges.loc[0, "y_type"] == "protein"

    assert len(result.evidence) == 1
    ev = result.evidence.loc[0]
    assert ev["source"] == "Reactome"
    assert ev["source_dataset"] == "UniProt2Reactome_All_Levels"
    assert ev["source_protein_id"] == "P12345"
    assert ev["reactome_evidence_code"] == "TAS"
    assert ev["mapping_confidence"] == "exact_unambiguous_uniprot_xref"
    payload = json.loads(ev["text_span"])
    assert payload["endpoint_policy"].startswith("Reactome UniProt protein endpoint")
    assert "gene" not in ev["y_id"].lower()

    assert result.rejected["reason"].value_counts().to_dict() == {
        "ambiguous_uniprot_to_protein": 1,
        "missing_pathway_node": 1,
    }


def test_build_from_reactome_mapping_does_not_emit_gene_endpoint_rows() -> None:
    result = build_from_reactome_mapping(
        pd.DataFrame(
            [
                {
                    "uniprot_id": "ENSG000001",
                    "reactome_id": "R-HSA-1",
                    "url": "",
                    "pathway_name": "Gene-looking source token is not mapped through genes",
                    "evidence_code": "IEA",
                    "species": "Homo sapiens",
                }
            ]
        ),
        uniprot_to_protein={},
        ambiguous_uniprot={},
        pathway_ids={"R-HSA-1"},
        release="test",
        created_at="2026-06-22T00:00:00+00:00",
    )

    assert result.edges.empty
    assert result.rejected.loc[0, "reason"] == "unmapped_uniprot_to_protein"
    assert result.validation["ok"] is False


def test_build_staged_reactome_pathway_proteins_writes_edges_evidence_rejects(tmp_path: Path) -> None:
    mapping_path = tmp_path / "UniProt2Reactome_All_Levels.txt"
    mapping_path.write_text(
        "P12345\tR-HSA-1\thttps://reactome.org/PathwayBrowser/#/R-HSA-1\tAccepted pathway\tTAS\tHomo sapiens\n"
        "P99999\tR-HSA-1\thttps://reactome.org/PathwayBrowser/#/R-HSA-1\tAmbiguous protein mapping\tIEA\tHomo sapiens\n"
    )
    protein_nodes = tmp_path / "protein.parquet"
    pd.DataFrame(
        [
            {"id": "ENSP000001", "uniprot_id": "P12345"},
            {"id": "ENSP000009", "uniprot_id": "P99999"},
            {"id": "ENSP000010", "uniprot_id": "P99999"},
        ]
    ).to_parquet(protein_nodes, index=False)
    pathway_nodes = tmp_path / "pathway.parquet"
    pd.DataFrame([{"id": "R-HSA-1"}]).to_parquet(pathway_nodes, index=False)

    report = build_staged_reactome_pathway_proteins(
        input_path=mapping_path,
        protein_nodes_path=protein_nodes,
        pathway_nodes_path=pathway_nodes,
        output_dir=tmp_path / "out",
    )

    assert report["ok"] is True
    assert report["counts"]["pathway_contains_protein_edges"] == 1
    edges = pd.read_parquet(report["artifacts"]["edges"])
    evidence = pd.read_parquet(report["artifacts"]["evidence"])
    canonical_evidence = pd.read_parquet(report["artifacts"]["canonical_evidence"])
    rejected = pd.read_parquet(report["artifacts"]["rejected"])
    assert edges.loc[0, "y_id"] == "ENSP000001"
    assert evidence.loc[0, "source_pathway_id"] == "R-HSA-1"
    assert canonical_evidence.loc[0, "edge_key"] == "pathway_contains_protein|R-HSA-1|ENSP000001"
    assert rejected.loc[0, "reason"] == "ambiguous_uniprot_to_protein"
