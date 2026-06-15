from manage_db.kg_schema import (
    CANDIDATE_RELATION_BY_NAME,
    RELATION_BY_NAME,
    RELATIONS,
    CANDIDATE_RELATIONS,
    RelationStatus,
)


def test_schema_cleanup_status_metadata_is_explicit() -> None:
    expected_statuses = {
        "gene_encodes_protein": RelationStatus.DERIVED,
        "mutation_associated_cell_type": RelationStatus.DEPRECATED,
        "cell_line_associated_disease": RelationStatus.DEPRECATED,
        "organism_models_disease": RelationStatus.DEPRECATED,
        "phenotype_caused_by_mutation": RelationStatus.DEPRECATED,
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
    assert "containment" in in_gene.notes
    assert "locus-to-gene" in associated_gene.notes


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
