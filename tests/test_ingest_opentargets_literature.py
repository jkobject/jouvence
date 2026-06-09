from __future__ import annotations

from pathlib import Path

import pandas as pd

from manage_db import kg_storage
from manage_db.ingest_opentargets import (
    ingest_biosample,
    ingest_disease_phenotype,
    ingest_drugs,
    ingest_evidence,
    ingest_expression,
    ingest_pharmacogenomics,
    ingest_literature,
)


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


def test_ingest_biosample_writes_required_node_xrefs(tmp_path: Path) -> None:
    ot_dir = tmp_path / "opentargets"
    biosample_dir = ot_dir / "biosample"
    biosample_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"biosampleId": "CL_0000540", "biosampleName": "neuron"},
            {"biosampleId": "UBERON_0000955", "biosampleName": "brain"},
        ]
    ).to_parquet(biosample_dir / "part-000.parquet", index=False)

    kg_dir = tmp_path / "kg"
    root = kg_storage.open_kg_root(str(kg_dir))

    assert ingest_biosample(ot_dir, kg_dir, root) == {"cell_type": 1, "tissue": 1}
    cell_types = kg_storage.read_nodes(root, "cell_type")
    tissues = kg_storage.read_nodes(root, "tissue")

    assert set(["id", "uberon_id", "mesh_id"]) <= set(cell_types.columns)
    assert set(["id", "bto_id", "mesh_id", "fma_id"]) <= set(tissues.columns)
    assert cell_types.loc[0, "id"] == "CL_0000540"
    assert tissues.loc[0, "id"] == "UBERON:0000955"


def test_ingest_expression_normalizes_tissue_ids_and_adds_gene_stubs(tmp_path: Path) -> None:
    ot_dir = tmp_path / "opentargets"
    expression_dir = ot_dir / "expression"
    expression_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "id": "ENSG00000123456",
                "tissues": [
                    {"efo_code": "UBERON_0000955", "rna": {"value": 12.5, "level": 4}},
                    {"efo_code": "CL_0000540", "rna": {"value": 3.0, "level": 2}},
                ],
            },
        ]
    ).to_parquet(expression_dir / "part-000.parquet", index=False)

    kg_dir = tmp_path / "kg"
    root = kg_storage.open_kg_root(str(kg_dir))

    assert ingest_expression(ot_dir, kg_dir, root) == {
        "tissue_expresses_gene": 1,
        "cell_type_expresses_gene": 1,
    }

    tissue_edges = kg_storage.read_edges(root, "tissue_expresses_gene")
    cell_type_edges = kg_storage.read_edges(root, "cell_type_expresses_gene")
    genes = kg_storage.read_nodes(root, "gene")

    assert tissue_edges.loc[0, "x_id"] == "UBERON:0000955"
    assert tissue_edges.loc[0, "y_id"] == "ENSG00000123456"
    assert cell_type_edges.loc[0, "x_id"] == "CL_0000540"
    assert set(genes["id"]) == {"ENSG00000123456"}


def test_ingest_disease_phenotype_normalizes_ids_and_adds_stubs(tmp_path: Path) -> None:
    ot_dir = tmp_path / "opentargets"
    dp_dir = ot_dir / "disease_phenotype"
    dp_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "disease": "MONDO_0005148",
                "phenotype": "HP_0001250",
                "evidence": [{"evidenceType": "TAS"}],
            },
            {
                "disease": "MONDO_0005148",
                "phenotype": "HP_0004322",
                "evidence": [{"evidenceType": "IEA", "qualifierNot": True}],
            },
        ]
    ).to_parquet(dp_dir / "part-000.parquet", index=False)

    kg_dir = tmp_path / "kg"
    root = kg_storage.open_kg_root(str(kg_dir))

    assert ingest_disease_phenotype(ot_dir, kg_dir, root) == 1
    edges = kg_storage.read_edges(root, "disease_has_phenotype")
    diseases = kg_storage.read_nodes(root, "disease")
    phenotypes = kg_storage.read_nodes(root, "phenotype")

    assert edges.loc[0, "x_id"] == "MONDO:0005148"
    assert edges.loc[0, "y_id"] == "HP:0001250"
    assert set(diseases["id"]) == {"MONDO:0005148"}
    assert set(phenotypes["id"]) == {"HP:0001250"}


def test_ingest_pharmacogenomics_adds_endpoint_stubs(tmp_path: Path) -> None:
    ot_dir = tmp_path / "opentargets"
    pg_dir = ot_dir / "pharmacogenomics"
    pg_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "variantId": "1_12345_A_G",
                "variantRsId": "rs123",
                "targetFromSourceId": "ENSG00000123456",
                "drugs": [{"drugId": "CHEMBL123", "drugFromSource": "drug"}],
                "evidenceLevel": "1A",
                "pgxCategory": "toxicity",
                "datasourceId": "pharmgkb",
            },
        ]
    ).to_parquet(pg_dir / "part-000.parquet", index=False)

    kg_dir = tmp_path / "kg"
    root = kg_storage.open_kg_root(str(kg_dir))

    assert ingest_pharmacogenomics(ot_dir, kg_dir, root) == 1
    edges = kg_storage.read_edges(root, "mutation_affects_molecule_response")
    mutations = kg_storage.read_nodes(root, "mutation")
    molecules = kg_storage.read_nodes(root, "molecule")

    assert edges.loc[0, "x_id"] == "1_12345_A_G"
    assert edges.loc[0, "y_id"] == "CHEMBL123"
    assert set(mutations["id"]) == {"1_12345_A_G"}
    assert mutations.loc[0, "name"] == "rs123"
    assert set(molecules["id"]) == {"CHEMBL123"}
