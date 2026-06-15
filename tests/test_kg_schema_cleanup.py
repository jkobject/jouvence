from manage_db.kg_schema import (
    CANDIDATE_RELATION_BY_NAME,
    LEGACY_RELATION_FLIP,
    LEGACY_RELATION_MAP,
    NodeType,
    RELATION_BY_NAME,
    RELATIONS,
    CANDIDATE_RELATIONS,
    RelationStatus,
)


def test_schema_cleanup_status_metadata_is_explicit() -> None:
    expected_statuses = {
        "gene_encodes_protein": RelationStatus.DERIVED,
        "transcript_alternative_transcript": RelationStatus.DEPRECATED,
        "mutation_associated_cell_type": RelationStatus.DEPRECATED,
        "cell_line_associated_disease": RelationStatus.DEPRECATED,
        "organism_models_disease": RelationStatus.DEPRECATED,
        "phenotype_caused_by_mutation": RelationStatus.DEPRECATED,
        "phenotype_associated_gene": RelationStatus.DEPRECATED,
        "phenotype_associated_molecule": RelationStatus.LEGACY_INDEX,
        "phenotype_associated_protein": RelationStatus.LEGACY_INDEX,
        "paper_mentions_gene": RelationStatus.LEGACY_INDEX,
        "paper_mentions_disease": RelationStatus.LEGACY_INDEX,
    }

    for relation_name, status in expected_statuses.items():
        relation = RELATION_BY_NAME[relation_name]
        assert relation.status is status
        assert relation.notes
        assert relation.replacement or status is RelationStatus.LEGACY_INDEX


def test_mutation_gene_relations_have_distinct_semantics() -> None:
    in_gene = RELATION_BY_NAME["mutation_in_gene"]
    associated_gene = RELATION_BY_NAME["mutation_associated_gene"]

    assert in_gene.direct is True
    assert associated_gene.direct is False
    assert in_gene.status is RelationStatus.ACTIVE
    assert associated_gene.status is RelationStatus.ACTIVE
    assert "containment" in in_gene.notes
    assert "L2G" in in_gene.notes
    assert "locus-to-gene" in associated_gene.notes


def test_variant_cleanup_tranche_statuses_are_explicit() -> None:
    active_variant_relations = {
        "mutation_in_gene",
        "mutation_associated_gene",
        "mutation_affects_transcript",
        "mutation_overlaps_enhancer",
        "mutation_causes_phenotype",
        "mutation_causes_protein_change",
        "mutation_associated_disease",
    }

    for relation_name in active_variant_relations:
        relation = RELATION_BY_NAME[relation_name]
        assert relation.status is RelationStatus.ACTIVE
        assert relation.notes

    todel_relations = {
        "transcript_alternative_transcript",
        "mutation_associated_cell_type",
    }
    for relation_name in todel_relations:
        relation = RELATION_BY_NAME[relation_name]
        assert relation.status is RelationStatus.DEPRECATED
        assert "TODEL" in relation.notes
        assert relation.replacement


def test_phenotype_association_replacements_point_from_entity_to_phenotype() -> None:
    replacements = {
        "gene_associated_phenotype": NodeType.GENE,
        "protein_associated_phenotype": NodeType.PROTEIN,
        "molecule_associated_phenotype": NodeType.MOLECULE,
    }

    for relation_name, source_type in replacements.items():
        relation = RELATION_BY_NAME[relation_name]
        assert relation.source is source_type
        assert relation.target is NodeType.PHENOTYPE
        assert relation.status is RelationStatus.ACTIVE

    legacy_replacements = {
        "phenotype_associated_gene": "gene_associated_phenotype",
        "phenotype_associated_protein": "protein_associated_phenotype",
        "phenotype_associated_molecule": "molecule_associated_phenotype",
    }
    for legacy_name, replacement_name in legacy_replacements.items():
        legacy_relation = RELATION_BY_NAME[legacy_name]
        assert legacy_relation.source is NodeType.PHENOTYPE
        assert legacy_relation.target is not NodeType.PHENOTYPE
        assert legacy_relation.replacement == replacement_name


def test_legacy_txgnn_phenotype_edges_preserve_entity_to_phenotype_direction() -> None:
    assert LEGACY_RELATION_MAP["phenotype_protein"] == "protein_associated_phenotype"
    assert LEGACY_RELATION_MAP["drug_effect"] == "molecule_associated_phenotype"
    assert "phenotype_protein" not in LEGACY_RELATION_FLIP
    assert "drug_effect" not in LEGACY_RELATION_FLIP


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
