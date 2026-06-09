from __future__ import annotations

from pathlib import Path

import pandas as pd

from manage_db import kg_storage
from manage_db.ingest_opentargets import ingest_drugs, ingest_evidence, ingest_literature


def test_ingest_literature_writes_schema_valid_nodes_and_edges(tmp_path: Path) -> None:
    ot_dir = tmp_path / "opentargets"
    evidence_dir = ot_dir / "evidence_europepmc"
    evidence_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "targetId": "ENSG00000139618",
                "diseaseId": "EFO:0000305",
                "literature": ["123", "456"],
            },
            {
                "targetId": "ENSG00000139618",
                "diseaseId": "EFO:0000305",
                "literature": ["123"],
            },
        ]
    ).to_parquet(evidence_dir / "part-000.parquet", index=False)

    kg_dir = tmp_path / "kg"
    root = kg_storage.open_kg_root(str(kg_dir))

    n_papers, n_mentions = ingest_literature(ot_dir, kg_dir, root)

    assert n_papers == 2
    assert n_mentions == 4

    papers = kg_storage.read_nodes(root, "paper")
    genes = kg_storage.read_nodes(root, "gene")
    diseases = kg_storage.read_nodes(root, "disease")
    gene_mentions = kg_storage.read_edges(root, "paper_mentions_gene")
    disease_mentions = kg_storage.read_edges(root, "paper_mentions_disease")

    assert set(papers["id"]) == {"PMID:123", "PMID:456"}
    assert {"id", "doi", "pmc_id", "arxiv_id"} <= set(papers.columns)
    assert set(genes["id"]) == {"ENSG00000139618"}
    assert set(diseases["id"]) == {"EFO:0000305"}
    assert len(gene_mentions) == 2
    assert len(disease_mentions) == 2


def test_ingest_evidence_finalizes_chunked_edges(tmp_path: Path) -> None:
    ot_dir = tmp_path / "opentargets"
    evidence_dir = ot_dir / "evidence_genetic_association"
    evidence_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "targetId": "ENSG00000139618",
                "diseaseId": "EFO:0000305",
                "datatypeId": "affected_pathway",
                "datasourceId": "reactome",
                "pathways": [{"id": "R-HSA-12345", "name": "Example pathway"}],
                "reactionId": "R-HSA-67890",
                "reactionName": "Example reaction",
                "score": 0.71,
            }
        ]
    ).to_parquet(evidence_dir / "part-000.parquet", index=False)

    kg_dir = tmp_path / "kg"
    root = kg_storage.open_kg_root(str(kg_dir))

    counts = ingest_evidence(ot_dir, kg_dir, root)

    assert counts == {
        "disease_associated_gene": 1,
        "disease_involves_pathway": 2,
    }
    edges = kg_storage.read_edges(root, "disease_associated_gene")
    assert edges.loc[0, "x_id"] == "EFO:0000305"
    assert edges.loc[0, "y_id"] == "ENSG00000139618"
    pathway_edges = kg_storage.read_edges(root, "disease_involves_pathway")
    assert set(pathway_edges["y_id"]) == {"R-HSA-12345", "R-HSA-67890"}
    genes = kg_storage.read_nodes(root, "gene")
    pathways = kg_storage.read_nodes(root, "pathway")
    assert set(genes["id"]) == {"ENSG00000139618"}
    assert set(pathways["id"]) == {"R-HSA-12345", "R-HSA-67890"}


def test_ingest_drugs_writes_required_molecule_xrefs(tmp_path: Path) -> None:
    ot_dir = tmp_path / "opentargets"
    drug_dir = ot_dir / "drug_molecule"
    drug_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "id": "CHEMBL941",
                "name": "Example",
                "description": "Example molecule",
                "inchiKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                "canonicalSmiles": "CCO",
                "drugType": "Small molecule",
                "maximumClinicalStage": 4,
                "crossReferences": [{"source": "drugbank", "ids": ["DB0001"]}],
            }
        ]
    ).to_parquet(drug_dir / "part-000.parquet", index=False)

    kg_dir = tmp_path / "kg"
    root = kg_storage.open_kg_root(str(kg_dir))

    assert ingest_drugs(ot_dir, kg_dir, root) == 1
    molecules = kg_storage.read_nodes(root, "molecule")
    assert set(["id", "drugbank_id", "pubchem_cid", "cas_rn", "inchikey", "smiles"]) <= set(molecules.columns)
    assert molecules.loc[0, "id"] == "CHEMBL941"
    assert molecules.loc[0, "smiles"] == "CCO"
