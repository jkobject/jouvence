from manage_db.kg_schema import (
    TXDATA_RELATION_FLIP,
    TXDATA_RELATION_MAP,
    NodeType,
    RELATION_BY_NAME,
    RELATIONS,
    CANDIDATE_RELATIONS,
    CANDIDATE_RELATION_BY_NAME,
    RelationStatus,
)


def test_cleanup_removed_stale_or_inverted_relation_names() -> None:
    removed = {
        "phenotype_caused_by_mutation",
        "phenotype_associated_gene",
        "phenotype_associated_molecule",
        "phenotype_associated_protein",
        "phenotype_associated_cell_type",
        "mutation_associated_cell_type",
        "cell_line_associated_disease",
        "organism_models_disease",
        "enhancer_active_in_cell_type",
        "enhancer_active_in_tissue",
        "enhancer_associated_disease",
        "paper_mentions_gene",
        "paper_mentions_disease",
        "paper_mentions_protein",
        "paper_mentions_molecule",
        "paper_mentions_mutation",
        "paper_mentions_pathway",
        "dataset_contains_gene",
        "molecule_interacts_molecule",
        "gene_encodes_protein",
        "mutation_causes_phenotype",
    }
    assert removed.isdisjoint(RELATION_BY_NAME)


def test_no_relation_is_marked_deprecated_or_txdata_index() -> None:
    for relation in RELATIONS:
        assert relation.status is RelationStatus.ACTIVE or relation.status is RelationStatus.DERIVED
        assert "TODEL" not in relation.notes
        assert "deprecated" not in relation.notes.lower()
        assert "legacy" not in relation.notes.lower()


def test_variant_cleanup_relations_are_directional_and_active() -> None:
    active_variant_relations = {
        "mutation_in_gene",
        "mutation_associated_gene",
        "mutation_affects_transcript",
        "mutation_overlaps_enhancer",
        "mutation_associated_phenotype",
        "mutation_causes_protein_change",
        "mutation_associated_disease",
    }
    for relation_name in active_variant_relations:
        relation = RELATION_BY_NAME[relation_name]
        assert relation.status is RelationStatus.ACTIVE
        assert relation.notes

    assert RELATION_BY_NAME["mutation_in_gene"].direct is True
    assert RELATION_BY_NAME["mutation_associated_gene"].direct is False
    assert RELATION_BY_NAME["mutation_overlaps_enhancer"].direct is False
    enhancer_notes = RELATION_BY_NAME["mutation_overlaps_enhancer"].notes
    assert "staged/context/feature" in enhancer_notes
    assert "not a standalone causal edge" in enhancer_notes
    assert "all clinical-significance classes" in RELATION_BY_NAME["mutation_associated_phenotype"].notes


def test_clean_gene_and_protein_relations_are_separate() -> None:
    expected = {
        "molecule_targets_gene": (NodeType.MOLECULE, NodeType.GENE),
        "molecule_targets_protein": (NodeType.MOLECULE, NodeType.PROTEIN),
        "gene_interacts_gene": (NodeType.GENE, NodeType.GENE),
        "tf_regulates_gene": (NodeType.GENE, NodeType.GENE),
        "tf_binds_enhancer": (NodeType.GENE, NodeType.ENHANCER),
        "transcript_interacts_protein": (NodeType.TRANSCRIPT, NodeType.PROTEIN),
        "transcript_interacts_gene": (NodeType.TRANSCRIPT, NodeType.GENE),
        "protein_interacts_protein": (NodeType.PROTEIN, NodeType.PROTEIN),
        "pathway_contains_gene": (NodeType.PATHWAY, NodeType.GENE),
        "pathway_contains_protein": (NodeType.PATHWAY, NodeType.PROTEIN),
        "disease_associated_gene": (NodeType.GENE, NodeType.DISEASE),
        "disease_associated_protein": (NodeType.PROTEIN, NodeType.DISEASE),
        "tissue_expresses_gene": (NodeType.TISSUE, NodeType.GENE),
        "tissue_expresses_protein": (NodeType.TISSUE, NodeType.PROTEIN),
        "cell_type_expresses_gene": (NodeType.CELL_TYPE, NodeType.GENE),
        "cell_type_expresses_protein": (NodeType.CELL_TYPE, NodeType.PROTEIN),
        "cell_line_expresses_gene": (NodeType.CELL_LINE, NodeType.GENE),
        "cell_line_expresses_protein": (NodeType.CELL_LINE, NodeType.PROTEIN),
        "gene_associated_phenotype": (NodeType.GENE, NodeType.PHENOTYPE),
        "molecule_associated_phenotype": (NodeType.MOLECULE, NodeType.PHENOTYPE),
        "disease_involves_pathway": (NodeType.PATHWAY, NodeType.DISEASE),
        "phenotype_observed_in_tissue": (NodeType.TISSUE, NodeType.PHENOTYPE),
    }
    for relation_name, (source_type, target_type) in expected.items():
        relation = RELATION_BY_NAME[relation_name]
        assert relation.source is source_type
        assert relation.target is target_type
        assert relation.status is RelationStatus.ACTIVE

    assert RELATION_BY_NAME["disease_associated_gene"].direct is True
    assert RELATION_BY_NAME["disease_associated_protein"].direct is True
    assert RELATION_BY_NAME["disease_involves_pathway"].direct is True
    assert RELATION_BY_NAME["phenotype_observed_in_tissue"].direct is True


def test_molecule_molecule_relations_are_not_called_interactions() -> None:
    assert "molecule_interacts_molecule" not in RELATION_BY_NAME
    assert RELATION_BY_NAME["molecule_synergizes_molecule"].source is NodeType.MOLECULE
    assert RELATION_BY_NAME["molecule_synergizes_molecule"].target is NodeType.MOLECULE
    assert RELATION_BY_NAME["molecule_parent_of_molecule"].kind.value == "ontological"


def test_txgnn_relation_map_points_to_clean_relation_names() -> None:
    assert TXDATA_RELATION_MAP["target"] == "molecule_targets_gene"
    assert TXDATA_RELATION_MAP["enzyme"] == "molecule_targets_gene"
    assert TXDATA_RELATION_MAP["transporter"] == "molecule_targets_gene"
    assert TXDATA_RELATION_MAP["carrier"] == "molecule_targets_gene"
    assert TXDATA_RELATION_MAP["drug_protein"] == "molecule_targets_gene"
    assert TXDATA_RELATION_MAP["protein_protein"] == "gene_interacts_gene"
    assert TXDATA_RELATION_MAP["pathway_protein"] == "pathway_contains_gene"
    assert TXDATA_RELATION_MAP["protein_pathway"] == "pathway_contains_gene"
    assert TXDATA_RELATION_MAP["disease_protein"] == "disease_associated_gene"
    assert TXDATA_RELATION_MAP["drug_effect"] == "molecule_associated_phenotype"
    assert TXDATA_RELATION_MAP["drug_drug"] == "molecule_synergizes_molecule"
    assert TXDATA_RELATION_MAP["anatomy_protein_present"] == "tissue_expresses_gene"
    assert TXDATA_RELATION_MAP["anatomy_protein_absent"] == "tissue_expresses_gene"

    assert "drug_effect" not in TXDATA_RELATION_FLIP
    assert "phenotype_protein" not in TXDATA_RELATION_FLIP


def test_candidate_protein_interactions_are_not_canonical_relations() -> None:
    relation_names = {relation.name for relation in RELATIONS}
    candidate_names = {relation.name for relation in CANDIDATE_RELATIONS}

    assert {
        "protein_interacts_with_enhancer",
        "protein_interacts_with_transcript",
    } <= candidate_names
    assert candidate_names.isdisjoint(relation_names)
    assert CANDIDATE_RELATION_BY_NAME[
        "protein_interacts_with_enhancer"
    ].recommendation


def test_block1_split_relations_preserve_source_specific_evidence_policy() -> None:
    for relation_name in {
        "tf_regulates_gene",
        "tf_binds_enhancer",
        "transcript_interacts_protein",
        "transcript_interacts_gene",
        "protein_interacts_protein",
        "pathway_contains_protein",
        "molecule_targets_protein",
    }:
        notes = RELATION_BY_NAME[relation_name].notes.lower()
        assert "source" in notes
        assert "evidence" in notes

    assert "split source-native" in RELATION_BY_NAME["gene_interacts_gene"].notes.lower() or "source-specific" in RELATION_BY_NAME["gene_interacts_gene"].notes.lower()


def test_block1_gene_interacts_gene_no_split_policy_is_explicit() -> None:
    notes = RELATION_BY_NAME["gene_interacts_gene"].notes.lower()
    assert "keep broad" in notes
    assert "current opentargets" in notes
    assert "canonical endpoints are gene-level" in notes
    assert "do not project" in notes

    for relation_name in {
        "tf_regulates_gene",
        "tf_binds_enhancer",
        "transcript_interacts_protein",
        "transcript_interacts_gene",
        "protein_interacts_protein",
    }:
        notes = RELATION_BY_NAME[relation_name].notes.lower()
        assert "source-native" in notes
        assert "not from canonical gene_interacts_gene" in notes
