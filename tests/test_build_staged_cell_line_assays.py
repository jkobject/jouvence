from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from manage_db.build_staged_cell_line_assays import BuildConfig, build_all


def _write_nodes(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"id": "ACH-000001", "name": "A", "ccle_name": "A", "cosmic_id": "", "efo_id": "", "source": "test"},
        {"id": "ACH-000002", "name": "B", "ccle_name": "B", "cosmic_id": "", "efo_id": "", "source": "test"},
    ]).to_parquet(root / "cell_line.parquet", index=False)
    pd.DataFrame([
        {"id": "ENSG000001", "ncbi_gene_id": "1", "name": "G1", "gene_name": "G1"},
        {"id": "ENSG000002", "ncbi_gene_id": "2", "name": "G2", "gene_name": "G2"},
    ]).to_parquet(root / "gene.parquet", index=False)
    pd.DataFrame([
        {"id": "P11111", "uniprot_id": "P11111", "ensembl_gene_id": "ENSG000001", "name": "P1"},
        {"id": "P22222", "uniprot_id": "P22222", "ensembl_gene_id": "ENSG000002", "name": "P2"},
    ]).to_parquet(root / "protein.parquet", index=False)
    pd.DataFrame([
        {"id": "CHEMBL1", "name": "DrugA", "legacy_id": "", "pubchem_cid": "", "inchikey": ""},
        {"id": "CHEMBL2", "name": "Ambiguous", "legacy_id": "", "pubchem_cid": "", "inchikey": ""},
        {"id": "CHEMBL3", "name": "Ambiguous", "legacy_id": "", "pubchem_cid": "", "inchikey": ""},
    ]).to_parquet(root / "molecule.parquet", index=False)


def _write_raw(raw: Path) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"ModelID": "ACH-000001", "CellLineName": "A", "StrippedCellLineName": "A", "COSMICID": 111, "SangerModelID": "SIDM1"},
        {"ModelID": "ACH-000002", "CellLineName": "B", "StrippedCellLineName": "B", "COSMICID": 222, "SangerModelID": "SIDM2"},
        {"ModelID": "ACH-999999", "CellLineName": "X", "StrippedCellLineName": "X", "COSMICID": 999, "SangerModelID": "SIDM9"},
    ]).to_csv(raw / "Model.csv", index=False)
    pd.DataFrame([
        {"Unnamed: 0": "ACH-000001", "G1 (1)": 0.95, "G2 (2)": 0.20, "BAD (999)": 0.99},
        {"Unnamed: 0": "ACH-999999", "G1 (1)": 0.99, "G2 (2)": 0.99, "BAD (999)": 0.99},
    ]).to_csv(raw / "CRISPRGeneDependency.csv", index=False)
    pd.DataFrame([
        {"DATASET": "GDSC1", "COSMIC_ID": 111, "DRUG_ID": 1, "DRUG_NAME": "DrugA", "BROAD_ID": "BRD-X", "IC50_PUBLISHED": 0.1, "AUC_PUBLISHED": 0.3, "auc": 0.4, "log2.ic50": -3.0, "R2": 0.9},
        {"DATASET": "GDSC1", "COSMIC_ID": 222, "DRUG_ID": 2, "DRUG_NAME": "DrugA", "BROAD_ID": "BRD-X", "IC50_PUBLISHED": 0.1, "AUC_PUBLISHED": 0.9, "auc": 0.9, "log2.ic50": -1.0, "R2": 0.9},
        {"DATASET": "GDSC1", "COSMIC_ID": 111, "DRUG_ID": 3, "DRUG_NAME": "Ambiguous", "BROAD_ID": "BRD-Y", "IC50_PUBLISHED": 0.1, "AUC_PUBLISHED": 0.3, "auc": 0.4, "log2.ic50": -3.0, "R2": 0.9},
    ]).to_csv(raw / "sanger-dose-response.csv", index=False)
    pd.DataFrame([
        {"Unnamed: 0": "ACH-000001", "P11111": 3.0, "P22222-2": 2.0, "BAD": 9.0},
        {"Unnamed: 0": "ACH-999999", "P11111": 8.0, "P22222-2": 7.0, "BAD": 9.0},
    ]).to_csv(raw / "harmonized_MS_CCLE_Gygi.csv", index=False)
    pd.DataFrame([{"UniprotID": "P11111", "Symbol": "P1", "EntrezID": 1, "Label": "P11111 (P1)"}]).to_csv(raw / "uniprot_hugo_entrez_id_mapping.csv", index=False)
    (raw / "manifest.json").write_text(json.dumps([]))


def test_build_staged_cell_line_assays_toy(tmp_path: Path) -> None:
    nodes = tmp_path / "nodes"
    raw = tmp_path / "raw"
    out = tmp_path / "out"
    _write_nodes(nodes)
    _write_raw(raw)

    class Args:
        output_dir = str(out)
        node_root = str(nodes)
        cell_line_nodes = str(nodes / "cell_line.parquet")
        gene_nodes = str(nodes / "gene.parquet")
        protein_nodes = str(nodes / "protein.parquet")
        molecule_nodes = str(nodes / "molecule.parquet")
        model = str(raw / "Model.csv")
        crispr_dependency = str(raw / "CRISPRGeneDependency.csv")
        gdsc_dose_response = str(raw / "sanger-dose-response.csv")
        proteomics = str(raw / "harmonized_MS_CCLE_Gygi.csv")
        uniprot_mapping = str(raw / "uniprot_hugo_entrez_id_mapping.csv")
        source_manifest = str(raw / "manifest.json")
        essentiality_threshold = 0.9
        gdsc_auc_threshold = 0.7
        gdsc_min_r2 = 0.8
        proteomics_top_n_per_cell_line = 2
        overwrite = True

    result = build_all(Args())
    assert result["validation"]["all_passed"] is True

    ess_edges = pd.read_parquet(out / "edges" / "cell_line_gene_essentiality.parquet")
    ess_ev = pd.read_parquet(out / "evidence" / "cell_line_gene_essentiality.parquet")
    assert len(ess_edges) == 1
    assert ess_edges.iloc[0].to_dict()["x_id"] == "ACH-000001"
    assert ess_edges.iloc[0].to_dict()["y_id"] == "ENSG000001"
    assert ess_ev.iloc[0].to_dict()["dependency_probability"] == 0.95

    response_edges = pd.read_parquet(out / "edges" / "cell_line_responds_to_molecule.parquet")
    response_ev = pd.read_parquet(out / "evidence" / "cell_line_responds_to_molecule.parquet")
    assert len(response_edges) == 1
    assert response_edges.iloc[0].to_dict()["y_id"] == "CHEMBL1"
    assert response_ev.iloc[0].to_dict()["auc"] == 0.4
    assert response_ev.iloc[0].to_dict()["ic50"] == -3.0

    protein_edges = pd.read_parquet(out / "edges" / "cell_line_expresses_protein.parquet")
    protein_ev = pd.read_parquet(out / "evidence" / "cell_line_expresses_protein.parquet")
    assert set(protein_edges["y_id"]) == {"P11111", "P22222"}
    assert set(protein_ev["protein_abundance"]) == {3.0, 2.0}
    assert "RNA" in (out / "source_audit.json").read_text()
