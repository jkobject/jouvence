"""Deterministic fixture data for the Phase 1 Jouvence-Graph viewer.

The values are deliberately small and source-like.  They are never presented as
live canonical KG data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SNAPSHOT_ID = "fixture-v1"
DATA_MODE = "fixture"
BUNDLE_VERSION = "viewer-fixture-schema-v1"


@dataclass(frozen=True)
class Node:
    node_type: str
    node_id: str
    display_name: str
    description: str
    source: str
    aliases: tuple[dict[str, str], ...]
    attributes: dict[str, str]


NODES: dict[tuple[str, str], Node] = {
    ("gene", "ENSG00000012048"): Node(
        "gene",
        "ENSG00000012048",
        "BRCA1",
        "DNA repair associated protein 1; a tumor suppressor involved in homologous recombination and genome integrity.",
        "Ensembl fixture",
        (
            {"kind": "symbol", "value": "BRCA1", "source": "HGNC fixture"},
            {"kind": "external_id", "value": "HGNC:1100", "source": "HGNC fixture"},
            {"kind": "external_id", "value": "672", "source": "NCBI Gene fixture"},
            {"kind": "external_id", "value": "P38398", "source": "UniProt fixture"},
        ),
        {"biotype": "protein_coding", "chromosome": "17q21.31"},
    ),
    ("gene", "ENSG00000139618"): Node(
        "gene",
        "ENSG00000139618",
        "BRCA2",
        "DNA repair associated protein 2; a mediator of homologous recombination.",
        "Ensembl fixture",
        (
            {"kind": "symbol", "value": "BRCA2", "source": "HGNC fixture"},
            {"kind": "external_id", "value": "HGNC:1101", "source": "HGNC fixture"},
            {"kind": "external_id", "value": "675", "source": "NCBI Gene fixture"},
            {"kind": "external_id", "value": "P51587", "source": "UniProt fixture"},
        ),
        {"biotype": "protein_coding", "chromosome": "13q13.1"},
    ),
    ("gene", "ENSG00000141510"): Node(
        "gene",
        "ENSG00000141510",
        "TP53",
        "Tumor protein p53; a transcription factor coordinating DNA-damage responses, cell-cycle arrest and apoptosis.",
        "Ensembl fixture",
        (
            {"kind": "symbol", "value": "TP53", "source": "HGNC fixture"},
            {"kind": "external_id", "value": "HGNC:11998", "source": "HGNC fixture"},
            {"kind": "external_id", "value": "7157", "source": "NCBI Gene fixture"},
            {"kind": "external_id", "value": "P04637", "source": "UniProt fixture"},
        ),
        {"biotype": "protein_coding", "chromosome": "17p13.1"},
    ),
    ("gene", "ENSG00000146648"): Node(
        "gene",
        "ENSG00000146648",
        "EGFR",
        "Epidermal growth factor receptor; a receptor tyrosine kinase involved in proliferation and survival signaling.",
        "Ensembl fixture",
        (
            {"kind": "symbol", "value": "EGFR", "source": "HGNC fixture"},
            {"kind": "external_id", "value": "HGNC:3236", "source": "HGNC fixture"},
            {"kind": "external_id", "value": "1956", "source": "NCBI Gene fixture"},
            {"kind": "external_id", "value": "P00533", "source": "UniProt fixture"},
        ),
        {"biotype": "protein_coding", "chromosome": "7p11.2"},
    ),
    ("disease", "EFO:0000305"): Node(
        "disease",
        "EFO:0000305",
        "breast carcinoma",
        "A malignant neoplasm arising from breast tissue.",
        "OpenTargets fixture",
        (
            {"kind": "name", "value": "breast cancer", "source": "EFO fixture"},
            {"kind": "external_id", "value": "MONDO:0007254", "source": "MONDO fixture"},
            {"kind": "external_id", "value": "D001943", "source": "MeSH fixture"},
            {"kind": "external_id", "value": "C50", "source": "ICD10 fixture"},
        ),
        {"ontology": "EFO", "disease_group": "neoplasm"},
    ),
    ("disease", "EFO:0000616"): Node(
        "disease",
        "EFO:0000616",
        "lung carcinoma",
        "A malignant neoplasm originating in lung tissue.",
        "OpenTargets fixture",
        (
            {"kind": "name", "value": "lung cancer", "source": "EFO fixture"},
            {"kind": "external_id", "value": "MONDO:0004992", "source": "MONDO fixture"},
            {"kind": "external_id", "value": "D008545", "source": "MeSH fixture"},
        ),
        {"ontology": "EFO", "disease_group": "neoplasm"},
    ),
    ("molecule", "CHEMBL1201585"): Node(
        "molecule",
        "CHEMBL1201585",
        "gefitinib",
        "A small-molecule EGFR tyrosine kinase inhibitor.",
        "ChEMBL fixture",
        (
            {"kind": "name", "value": "IRESSA", "source": "ChEMBL fixture"},
            {"kind": "external_id", "value": "DB00317", "source": "DrugBank fixture"},
            {"kind": "external_id", "value": "123631", "source": "PubChem fixture"},
        ),
        {"canonical_smiles": "COC1=NC=NC2=C1C=CN2", "chembl_phase": "4"},
    ),
    ("molecule", "CHEMBL25"): Node(
        "molecule",
        "CHEMBL25",
        "aspirin",
        "Acetylsalicylic acid; a cyclooxygenase inhibitor.",
        "ChEMBL fixture",
        (
            {"kind": "name", "value": "acetylsalicylic acid", "source": "ChEMBL fixture"},
            {"kind": "external_id", "value": "DB00945", "source": "DrugBank fixture"},
            {"kind": "external_id", "value": "2244", "source": "PubChem fixture"},
        ),
        {"canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "chembl_phase": "4"},
    ),
    ("phenotype", "HP:0003011"): Node(
        "phenotype",
        "HP:0003011",
        "Abnormal cell proliferation",
        "A phenotype involving altered regulation or rate of cellular proliferation.",
        "HPO fixture",
        ({"kind": "name", "value": "abnormal proliferation", "source": "HPO fixture"},),
        {"ontology": "HPO"},
    ),
}

EDGE_ROWS: list[dict[str, Any]] = [
    {"edge_key": "fixture:edge:1", "relation": "disease_associated_gene", "x_type": "gene", "x_id": "ENSG00000012048", "y_type": "disease", "y_id": "EFO:0000305", "display_relation": "disease associated gene", "source": "OpenTargets fixture", "credibility": 3, "score": 0.92, "effect_direction": "risk", "kind": "observed"},
    {"edge_key": "fixture:edge:2", "relation": "disease_associated_gene", "x_type": "gene", "x_id": "ENSG00000139618", "y_type": "disease", "y_id": "EFO:0000305", "display_relation": "disease associated gene", "source": "OpenTargets fixture", "credibility": 3, "score": 0.89, "effect_direction": "risk", "kind": "observed"},
    {"edge_key": "fixture:edge:3", "relation": "disease_associated_gene", "x_type": "gene", "x_id": "ENSG00000141510", "y_type": "disease", "y_id": "EFO:0000305", "display_relation": "disease associated gene", "source": "OpenTargets fixture", "credibility": 2, "score": 0.86, "effect_direction": "risk", "kind": "observed"},
    {"edge_key": "fixture:edge:4", "relation": "disease_associated_gene", "x_type": "gene", "x_id": "ENSG00000141510", "y_type": "disease", "y_id": "EFO:0000616", "display_relation": "disease associated gene", "source": "OpenTargets fixture", "credibility": 2, "score": 0.81, "effect_direction": "risk", "kind": "observed"},
    {"edge_key": "fixture:edge:5", "relation": "disease_associated_gene", "x_type": "gene", "x_id": "ENSG00000146648", "y_type": "disease", "y_id": "EFO:0000616", "display_relation": "disease associated gene", "source": "OpenTargets fixture", "credibility": 3, "score": 0.74, "effect_direction": "risk", "kind": "observed"},
    {"edge_key": "fixture:edge:6", "relation": "molecule_targets_gene", "x_type": "molecule", "x_id": "CHEMBL1201585", "y_type": "gene", "y_id": "ENSG00000146648", "display_relation": "molecule targets gene", "source": "ChEMBL fixture", "credibility": 3, "score": 0.94, "pharmacological_action": "inhibitor", "kind": "observed"},
    {"edge_key": "fixture:edge:7", "relation": "molecule_targets_gene", "x_type": "molecule", "x_id": "CHEMBL1201585", "y_type": "gene", "y_id": "ENSG00000141510", "display_relation": "molecule targets gene", "source": "ChEMBL fixture", "credibility": 1, "score": 0.54, "pharmacological_action": "binding evidence only", "kind": "observed"},
    {"edge_key": "fixture:edge:8", "relation": "molecule_targets_gene", "x_type": "molecule", "x_id": "CHEMBL25", "y_type": "gene", "y_id": "ENSG00000141510", "display_relation": "molecule targets gene", "source": "ChEMBL fixture", "credibility": 1, "score": 0.46, "pharmacological_action": "weak fixture support", "kind": "observed"},
    {"edge_key": "fixture:edge:9", "relation": "gene_interacts_gene", "x_type": "gene", "x_id": "ENSG00000012048", "y_type": "gene", "y_id": "ENSG00000141510", "display_relation": "gene interacts gene", "source": "BioGRID fixture", "credibility": 2, "score": 0.79, "interaction_kind": "physical_interaction", "kind": "observed"},
]

EVIDENCE_ROWS: list[dict[str, Any]] = [
    {"edge_key": "fixture:edge:1", "relation": "disease_associated_gene", "x_type": "gene", "x_id": "ENSG00000012048", "y_type": "disease", "y_id": "EFO:0000305", "source": "OpenTargets fixture", "source_dataset": "associationByDatasourceDirect", "source_record_id": "fixture:ot:brca1-breast", "predicate": "associated_with", "evidence_score": 0.92, "paper_id": "PMID:0000001", "license": "CC BY 4.0 fixture metadata", "release": SNAPSHOT_ID, "row_kind": "observed"},
    {"edge_key": "fixture:edge:1", "relation": "disease_associated_gene", "x_type": "gene", "x_id": "ENSG00000012048", "y_type": "disease", "y_id": "EFO:0000305", "source": "ClinGen fixture", "source_dataset": "gene_validity", "source_record_id": "fixture:cg:brca1", "predicate": "germline_role", "evidence_score": 0.88, "paper_id": "PMID:0000002", "license": "fixture only", "release": SNAPSHOT_ID, "row_kind": "observed"},
    {"edge_key": "fixture:edge:2", "relation": "disease_associated_gene", "x_type": "gene", "x_id": "ENSG00000139618", "y_type": "disease", "y_id": "EFO:0000305", "source": "OpenTargets fixture", "source_dataset": "associationByDatasourceDirect", "source_record_id": "fixture:ot:brca2-breast", "predicate": "associated_with", "evidence_score": 0.89, "paper_id": "PMID:0000003", "license": "CC BY 4.0 fixture metadata", "release": SNAPSHOT_ID, "row_kind": "observed"},
    {"edge_key": "fixture:edge:4", "relation": "disease_associated_gene", "x_type": "gene", "x_id": "ENSG00000141510", "y_type": "disease", "y_id": "EFO:0000616", "source": "OpenTargets fixture", "source_dataset": "associationByDatasourceDirect", "source_record_id": "fixture:ot:tp53-lung", "predicate": "associated_with", "evidence_score": 0.81, "paper_id": "PMID:0000004", "license": "CC BY 4.0 fixture metadata", "release": SNAPSHOT_ID, "row_kind": "observed"},
    {"edge_key": "fixture:edge:6", "relation": "molecule_targets_gene", "x_type": "molecule", "x_id": "CHEMBL1201585", "y_type": "gene", "y_id": "ENSG00000146648", "source": "ChEMBL fixture", "source_dataset": "mechanism", "source_record_id": "fixture:chembl:gefitinib-egfr", "predicate": "inhibits", "evidence_score": 0.94, "paper_id": "CHEMBL-ACT:fixture:1", "license": "fixture only", "release": SNAPSHOT_ID, "row_kind": "observed"},
    {"edge_key": "fixture:edge:7", "relation": "molecule_targets_gene", "x_type": "molecule", "x_id": "CHEMBL1201585", "y_type": "gene", "y_id": "ENSG00000141510", "source": "ChEMBL fixture", "source_dataset": "activity", "source_record_id": "fixture:chembl:gefitinib-tp53", "predicate": "binding_support", "evidence_score": 0.54, "paper_id": "CHEMBL-ACT:fixture:2", "license": "fixture only", "release": SNAPSHOT_ID, "row_kind": "observed"},
    {"edge_key": "fixture:edge:9", "relation": "gene_interacts_gene", "x_type": "gene", "x_id": "ENSG00000012048", "y_type": "gene", "y_id": "ENSG00000141510", "source": "BioGRID fixture", "source_dataset": "physical_interactions", "source_record_id": "fixture:biogrid:brca1-tp53", "predicate": "physical_interaction", "evidence_score": 0.79, "paper_id": "BIOGRID:fixture:12", "license": "fixture only", "release": SNAPSHOT_ID, "row_kind": "observed"},
]

FEATURE_ROWS: list[dict[str, Any]] = [
    {"node_type": node.node_type, "node_id": node.node_id, "feature_kind": "identity_summary", "feature_key": "description", "value": node.description, "source": node.source, "release": SNAPSHOT_ID, "epistemic_kind": "source-backed"}
    for node in NODES.values()
]
FEATURE_ROWS.extend(
    [
        {"node_type": "gene", "node_id": "ENSG00000012048", "feature_kind": "genomic_context", "feature_key": "chromosome", "value": "17q21.31", "source": "Ensembl fixture", "release": SNAPSHOT_ID, "epistemic_kind": "source-backed"},
        {"node_type": "gene", "node_id": "ENSG00000012048", "feature_kind": "model_context", "feature_key": "fixture_embedding_family", "value": "text-neighborhood-demo", "source": "fixture ranker", "release": SNAPSHOT_ID, "epistemic_kind": "model/fallback"},
        {"node_type": "molecule", "node_id": "CHEMBL1201585", "feature_kind": "chemical", "feature_key": "action", "value": "EGFR inhibitor in fixture mechanism row", "source": "ChEMBL fixture", "release": SNAPSHOT_ID, "epistemic_kind": "source-backed"},
    ]
)

LONG_RANGE_ROWS: list[dict[str, Any]] = [
    {"anchor_type": "gene", "anchor_id": "ENSG00000012048", "target_type": "disease", "target_id": "EFO:0000305", "target_name": "breast carcinoma", "score": 0.94, "rank": 1, "ranker_id": "fixture_path_ranker", "ranker_version": "v1", "path_length": 1, "support_path": "BRCA1 → breast carcinoma", "support_relations": ["disease_associated_gene"], "observed_overlap": True, "caveats": "Observed row shown in ranked context; not a causal claim.", "row_kind": "ranked"},
    {"anchor_type": "gene", "anchor_id": "ENSG00000012048", "target_type": "gene", "target_id": "ENSG00000141510", "target_name": "TP53", "score": 0.79, "rank": 1, "ranker_id": "fixture_path_ranker", "ranker_version": "v1", "path_length": 2, "support_path": "BRCA1 → breast carcinoma → TP53", "support_relations": ["disease_associated_gene"], "observed_overlap": False, "caveats": "Shared disease context; not physical interaction evidence.", "row_kind": "ranked"},
    {"anchor_type": "gene", "anchor_id": "ENSG00000012048", "target_type": "molecule", "target_id": "CHEMBL1201585", "target_name": "gefitinib", "score": 0.65, "rank": 1, "ranker_id": "fixture_path_ranker", "ranker_version": "v1", "path_length": 3, "support_path": "BRCA1 → TP53 → EGFR → gefitinib", "support_relations": ["disease_associated_gene", "molecule_targets_gene"], "observed_overlap": False, "caveats": "Ranked retrieval only; treatment direction is not inferred.", "row_kind": "ranked"},
    {"anchor_type": "gene", "anchor_id": "ENSG00000012048", "target_type": "phenotype", "target_id": "HP:0003011", "target_name": "Abnormal cell proliferation", "score": 0.61, "rank": 1, "ranker_id": "fixture_path_ranker", "ranker_version": "v1", "path_length": 2, "support_path": "BRCA1 → cancer ontology context → proliferation", "support_relations": ["disease_has_phenotype"], "observed_overlap": False, "caveats": "Ontology-like context, not observed gene phenotype evidence.", "row_kind": "ranked"},
]

PUTATIVE_ROWS: list[dict[str, Any]] = [
    {"anchor_type": "gene", "anchor_id": "ENSG00000012048", "target_type": "disease", "target_id": "EFO:0000616", "target_name": "lung carcinoma", "policy_class": "inferred_weak", "template_id": "gene_disease_path_v1", "template_version": "v1", "support_path": "BRCA1 → TP53 → lung carcinoma", "support_edge_hashes": ["fixture:edge:1", "fixture:edge:4"], "observed_overlap": False, "leakage_caveat": "Association path is not a causal disease assertion.", "row_kind": "inferred"},
    {"anchor_type": "gene", "anchor_id": "ENSG00000012048", "target_type": "molecule", "target_id": "CHEMBL1201585", "target_name": "gefitinib", "policy_class": "inferred_weak", "template_id": "molecule_gene_disease_v1", "template_version": "v1", "support_path": "gefitinib → EGFR → lung carcinoma; BRCA1 shares cancer context", "support_edge_hashes": ["fixture:edge:6", "fixture:edge:5"], "observed_overlap": False, "leakage_caveat": "Drug action and disease mechanism are incomplete.", "row_kind": "inferred"},
]


def node_key(node_type: str, node_id: str) -> tuple[str, str]:
    return (node_type.strip().lower(), node_id.strip())
