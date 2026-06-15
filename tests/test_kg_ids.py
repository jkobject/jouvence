from manage_db.kg_ids import (
    bionty_disease_source_supports_ontology_id,
    normalize_disease_id,
    normalize_ontology_curie,
)


def test_normalize_opentargets_underscore_curies() -> None:
    assert normalize_ontology_curie("EFO_0000094") == "EFO:0000094"
    assert normalize_ontology_curie("MONDO_0005148") == "MONDO:0005148"
    assert normalize_ontology_curie("HP_0001626") == "HP:0001626"
    assert normalize_disease_id("EFO:0000094") == "EFO:0000094"


def test_disease_source_support_is_mondo_only() -> None:
    assert bionty_disease_source_supports_ontology_id("MONDO:0005148") is True
    assert bionty_disease_source_supports_ontology_id("EFO:0000094") is False
    assert bionty_disease_source_supports_ontology_id("HP:0001626") is False
