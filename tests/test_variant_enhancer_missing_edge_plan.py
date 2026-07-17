from pathlib import Path

from manage_db.kg_schema import NodeType, RELATION_BY_NAME, RelationStatus


PLAN_DOC = Path(__file__).resolve().parents[1] / "docs" / "variant_transcript_enhancer_missing_edges.md"
POLICY_DOC = Path(__file__).resolve().parents[1] / "docs" / "mutation_genomic_relations_promotion_policy.md"

STALE_POLICY_PHRASES = [
    "not canonical until bounded source-specific evidence and endpoint policy are selected",
    "only for variants that also have downstream disease/phenotype/drug-response evidence",
    "Existing disease/phenotype/drug-response support is only a triage gate",
]


FOCUSED_RELATIONS = {
    "mutation_in_gene": (NodeType.MUTATION, NodeType.GENE, True),
    "mutation_affects_transcript": (NodeType.MUTATION, NodeType.TRANSCRIPT, True),
    "mutation_overlaps_enhancer": (NodeType.MUTATION, NodeType.ENHANCER, False),
    "mutation_associated_phenotype": (NodeType.MUTATION, NodeType.PHENOTYPE, False),
    "enhancer_regulates_transcript": (NodeType.ENHANCER, NodeType.TRANSCRIPT, True),
}


def test_variant_transcript_enhancer_schema_semantics_are_locked() -> None:
    for relation_name, (source, target, direct) in FOCUSED_RELATIONS.items():
        relation = RELATION_BY_NAME[relation_name]
        assert relation.source is source
        assert relation.target is target
        assert relation.direct is direct
        assert relation.status is RelationStatus.ACTIVE
        assert relation.notes

    assert "Physical/genomic containment only" in RELATION_BY_NAME["mutation_in_gene"].notes
    assert "do not use for L2G/GWAS association" in RELATION_BY_NAME["mutation_in_gene"].notes
    assert "Transcript-level consequence" in RELATION_BY_NAME["mutation_affects_transcript"].notes
    assert "canonical promoted/review-accepted" in RELATION_BY_NAME["mutation_affects_transcript"].notes
    for stale_phrase in STALE_POLICY_PHRASES:
        assert stale_phrase not in RELATION_BY_NAME["mutation_affects_transcript"].notes
        assert stale_phrase not in RELATION_BY_NAME["mutation_overlaps_enhancer"].notes
    assert "coordinate overlap alone remains context/support-only" in RELATION_BY_NAME["mutation_overlaps_enhancer"].notes
    assert "canonical promoted/review-required by t_00551bc3" in RELATION_BY_NAME["mutation_overlaps_enhancer"].notes
    assert "stronger allele-specific regulatory or enhancer-activity evidence" in RELATION_BY_NAME["mutation_overlaps_enhancer"].notes
    assert "all clinical-significance classes" in RELATION_BY_NAME["mutation_associated_phenotype"].notes
    assert "transcript-specific" in RELATION_BY_NAME["enhancer_regulates_transcript"].notes
    assert "not inferred by expanding enhancer→gene to all transcripts" in RELATION_BY_NAME["enhancer_regulates_transcript"].notes


def test_variant_transcript_enhancer_plan_documents_safe_sources_and_blockers() -> None:
    text = PLAN_DOC.read_text()
    for relation_name in FOCUSED_RELATIONS:
        assert f"`{relation_name}`" in text

    required_phrases = [
        "Build locally, validate locally, then let the parent perform any",
        "OpenTargets `variant/transcriptConsequences`",
        "OpenTargets EVA/ClinVar-style known-variant evidence with `HP:` endpoints",
        "all clinical-significance classes",
        "Do not promote coordinate-overlap rows as canonical edges",
        "stronger allele-specific regulatory/enhancer-activity evidence",
        "No current OpenTargets E2G transcript endpoint",
        "Do not infer `enhancer_regulates_transcript` from `enhancer_regulates_gene`",
        "Do not create empty placeholder Parquets",
        "endpoint anti-join validation reports zero missing endpoints",
    ]
    for phrase in required_phrases:
        assert phrase in text


def test_mutation_genomic_policy_doc_records_current_canonical_and_context_only_status() -> None:
    text = POLICY_DOC.read_text()

    for stale_phrase in STALE_POLICY_PHRASES:
        assert stale_phrase not in text

    required_phrases = [
        "`mutation_affects_transcript` | `mutation -> transcript` | yes | Transcript-level consequence",
        "canonical promoted/review-accepted from the full OpenTargets 26.03 VEP transcript consequence candidate",
        "accepted canonical relation is the bounded transcript-local consequence graph",
        "Variant-enhancer coordinate overlap alone remains context/support-only",
        "canonical promoted/review-required by `t_00551bc3`",
        "Coordinate overlap alone remains context/support-only and is not observed regulatory evidence",
        "wrote `mutation_overlaps_enhancer` canonical edge/evidence objects for the reviewed non-context-support-gated `t_73c67c1b` candidate only",
        "Coordinate overlap alone is contextual and dense",
    ]
    for phrase in required_phrases:
        assert phrase in text


def test_mutation_associated_phenotype_promotion_is_recorded() -> None:
    text = PLAN_DOC.read_text()
    promoted_line = next(
        line for line in text.splitlines() if line.startswith("Promoted first candidate:")
    )
    assert "`mutation_associated_phenotype`" in promoted_line
    assert "all clinical-significance classes" in promoted_line
    assert "HP:" in promoted_line
    assert "25,545" in text
    assert "26,980" in text
