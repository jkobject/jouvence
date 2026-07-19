import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from manage_db.inferred_relation_algebra import (
    BuildConfig,
    EXCLUDED_MOTIFS,
    INFERRED_RELATION_BY_NAME,
    RULES_BY_ID,
    EpistemicClass,
    SignStatus,
    build_inferred_edges,
)


def _write_relation(root: Path, relation: str, rows: list[dict], *, layer: str = "edges") -> None:
    path = root / layer / f"{relation}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _edge(relation: str, x_id: str, x_type: str, y_id: str, y_type: str, **metadata: object) -> dict:
    return {
        "x_id": x_id,
        "x_type": x_type,
        "y_id": y_id,
        "y_type": y_type,
        "relation": relation,
        "edge_key": f"{relation}|{x_id}|{y_id}",
        "source": "unit",
        **metadata,
    }


def _config(kg: Path, output: Path, *rule_ids: str) -> BuildConfig:
    return BuildConfig(
        kg_root=kg,
        output_root=output,
        kg_snapshot_id="sha256:immutable-unit-snapshot",
        kg_generations={"fixture": "1"},
        producer_revision="test-revision",
        rule_ids=tuple(rule_ids),
        max_anchors=100,
        sample_limit=5,
    )


def test_v1_registry_is_typed_versioned_and_excludes_unapproved_generators() -> None:
    priority_rules = {
        "variant_protein_disease_v1",
        "variant_gene_disease_v1",
        "pharmacogenomic_variant_drug_disease_v1",
        "signed_target_mechanism_gene_drug_disease_v1",
        "signed_target_mechanism_protein_drug_disease_v1",
    }
    removed_structural_rules = {
        "disease_is_a_closure_v1",
        "phenotype_is_a_closure_v1",
        "tissue_is_a_closure_v1",
        "cell_type_is_a_closure_v1",
        "positive_phenotype_generalization_v1",
        "gene_transcript_protein_product_v1",
    }

    assert set(RULES_BY_ID) == priority_rules
    assert removed_structural_rules.isdisjoint(RULES_BY_ID)
    assert RULES_BY_ID["variant_gene_disease_v1"].version == "1.1.0"
    assert {
        rule.version
        for rule_id, rule in RULES_BY_ID.items()
        if rule_id != "variant_gene_disease_v1"
    } == {"1.0.0"}
    assert {rule.epistemic_class for rule in RULES_BY_ID.values()} == {
        EpistemicClass.CONDITIONAL,
        EpistemicClass.ABDUCTIVE,
    }
    for rule in RULES_BY_ID.values():
        assert rule.premises
        assert rule.conclusion.source_type
        assert rule.conclusion.target_type
        assert rule.required_evidence
        assert rule.forbidden_evidence
        assert rule.context_join_keys
        assert rule.quantifier
        assert rule.fail_closed_conditions

    assert set(EXCLUDED_MOTIFS) == {
        "c3_variant_enhancer_gene_disease",
        "c4_tf_enhancer_gene",
        "h3_cell_line_response_disease",
        "h4_synthetic_rescue_interaction",
        "reactome_pathway_closure",
        "prism_cell_line_molecule",
        "d1_ontology_closure",
        "d2_hpo_generalization",
        "d3_gene_protein_product",
    }
    assert all(
        excluded not in rule.rule_id
        for excluded in ("tf_enhancer", "cell_line", "synthetic", "pathway", "prism")
        for rule in RULES_BY_ID.values()
    )
    assert "gene_has_protein_product" not in INFERRED_RELATION_BY_NAME
    assert SignStatus.KNOWN.value == "known"
    assert SignStatus.CONFLICTING.value == "conflicting"
    assert SignStatus.UNKNOWN.value == "unknown"


def test_conditional_rules_apply_strong_gates_and_fail_closed_adversarial_cases(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_relation(
        kg,
        "mutation_causes_protein_change",
        [
            _edge("mutation_causes_protein_change", "V1", "mutation", "P1", "protein", consequence="amino_acid_change", isoform_id="I1"),
            _edge("mutation_causes_protein_change", "V2", "mutation", "P2", "protein", consequence="amino_acid_change", isoform_id="I2"),
            _edge("mutation_causes_protein_change", "V9", "mutation", "P9", "protein", consequence="amino_acid_change"),
        ],
    )
    _write_relation(
        kg,
        "mutation_in_gene",
        [
            _edge(
                "mutation_in_gene",
                "V1",
                "mutation",
                "G1",
                "gene",
                consequence="missense_variant",
                transcript_id="ENST1",
            ),
            _edge("mutation_in_gene", "V3", "mutation", "G3", "gene", functional_support="none", association_basis="ld_only"),
        ],
    )
    _write_relation(
        kg,
        "mutation_associated_disease",
        [
            _edge("mutation_associated_disease", "V1", "mutation", "D1", "disease", disease_support="pathogenic", functional_support="clinvar", isoform_id="I1"),
            _edge("mutation_associated_disease", "V2", "mutation", "D2", "disease", disease_support="pathogenic", functional_support="clinvar", isoform_id="OTHER"),
            _edge("mutation_associated_disease", "V3", "mutation", "D3", "disease", disease_support="gwas", functional_support="none", association_basis="ld_only"),
            _edge("mutation_associated_disease", "V6", "mutation", "D6", "disease", disease_support="pathogenic", population="EUR"),
            _edge("mutation_associated_disease", "V7", "mutation", "D7", "disease", disease_support="pathogenic", population="EUR"),
            _edge("mutation_associated_disease", "V9", "mutation", "D9", "disease", disease_support="pathogenic", functional_support="clinvar"),
        ],
    )
    _write_relation(
        kg,
        "mutation_affects_molecule_response",
        [
            _edge("mutation_affects_molecule_response", "V6", "mutation", "M6", "molecule", response_direction="increased_response", response_category="efficacy", population="EUR"),
            _edge("mutation_affects_molecule_response", "V7", "mutation", "M7", "molecule", response_direction="resistance", response_category="efficacy", population="EUR"),
        ],
    )
    _write_relation(kg, "disease_associated_gene", [_edge("disease_associated_gene", "G1", "gene", "D1", "disease")])

    manifest = build_inferred_edges(
        _config(
            kg,
            tmp_path / "out",
            "variant_protein_disease_v1",
            "variant_gene_disease_v1",
            "pharmacogenomic_variant_drug_disease_v1",
        )
    )

    protein = pd.read_parquet(tmp_path / "out" / "edges_inferred" / "disease_associated_protein" / "variant_protein_disease_v1.parquet")
    genes_c2 = pd.read_parquet(tmp_path / "out" / "edges_inferred" / "disease_associated_gene" / "variant_gene_disease_v1.parquet")
    drugs = pd.read_parquet(tmp_path / "out" / "edges_inferred" / "molecule_treats_disease" / "pharmacogenomic_variant_drug_disease_v1.parquet")

    assert set(zip(protein.x_id, protein.y_id, protein.inference_strength)) == {
        ("P1", "D1", "strong"),
        ("P9", "D9", "hypothesis"),
    }
    assert set(zip(genes_c2.x_id, genes_c2.y_id, genes_c2.c2_support_family)) == {
        ("G1", "D1", "coding_pathogenic"),
    }
    assert bool(genes_c2.loc[genes_c2.x_id == "G1", "canonical_observed_overlap"].iloc[0])
    assert set(zip(drugs.x_id, drugs.y_id)) == {("M6", "D6")}
    assert manifest["counts_by_rule"]["pharmacogenomic_variant_drug_disease_v1"]["fail_closed_paths"] == 1


def test_c2_emits_only_typed_coding_pathogenic_splice_colocalized_eqtl_or_l2g_support(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    accepted = [
        _edge(
            "mutation_in_gene",
            "V-CODING",
            "mutation",
            "G-CODING",
            "gene",
            consequence="missense_variant",
            transcript_id="ENST-CODING",
            consequence_source="OpenTargets/VEP",
        ),
        _edge(
            "mutation_in_gene",
            "V-PATH",
            "mutation",
            "G-PATH",
            "gene",
            consequence="intron_variant",
            clinical_significance="likely_pathogenic",
            clinical_source="ClinVar",
        ),
        _edge(
            "mutation_in_gene",
            "V-SPLICE",
            "mutation",
            "G-SPLICE",
            "gene",
            consequence="splice_acceptor_variant",
            transcript_id="ENST-SPLICE",
            consequence_source="OpenTargets/VEP",
        ),
        _edge(
            "mutation_in_gene",
            "V-EQTL",
            "mutation",
            "G-EQTL",
            "gene",
            functional_support="eqtl_colocalization",
            colocalization_method="coloc",
            study_id="GCST-EQTL",
            tissue="liver",
            source="OpenTargets",
        ),
        _edge(
            "mutation_in_gene",
            "V-L2G",
            "mutation",
            "G-L2G",
            "gene",
            attribution_method="opentargets_l2g",
            l2g_model="v2.1",
            l2g_score=0.82,
            study_id="GCST-L2G",
            source="OpenTargets",
            alternative_targets="G-L2G|G-OTHER",
        ),
        _edge(
            "mutation_in_gene",
            "V-JSON",
            "mutation",
            "G-JSON",
            "gene",
        ),
    ]
    accepted[4].pop("source")
    forbidden = [
        _edge("mutation_in_gene", "V-CONTAIN", "mutation", "G-CONTAIN", "gene", association_basis="genomic_containment"),
        _edge(
            "mutation_in_gene",
            "V-GENERIC-TX",
            "mutation",
            "G-GENERIC-TX",
            "gene",
            consequence="intron_variant",
            transcript_id="ENST-INTRON",
            association_basis="genomic_containment",
        ),
        _edge("mutation_in_gene", "V-LD", "mutation", "G-LD", "gene", association_basis="ld_only"),
        _edge(
            "mutation_in_gene",
            "V-NEAREST",
            "mutation",
            "G-NEAREST",
            "gene",
            attribution_method="nearest_gene",
            consequence="missense_variant",
        ),
        _edge(
            "mutation_in_gene",
            "V-AMBIG",
            "mutation",
            "G-AMBIG",
            "gene",
            alternative_targets="G-AMBIG|G-OTHER",
            consequence="missense_variant",
        ),
        _edge(
            "mutation_in_gene",
            "V-ALT-ONE",
            "mutation",
            "G-ALT-ONE",
            "gene",
            alternative_targets="G-OTHER",
            consequence="missense_variant",
        ),
        _edge(
            "mutation_in_gene",
            "V-L2G-NEAREST",
            "mutation",
            "G-L2G-NEAREST",
            "gene",
            attribution_method="opentargets_l2g",
            l2g_model="v2.1",
            l2g_score=0.9,
            predicate="nearest_gene",
            source="OpenTargets",
        ),
        _edge("mutation_in_gene", "V-MISSING", "mutation", "G-MISSING", "gene"),
    ]
    _write_relation(kg, "mutation_in_gene", accepted + forbidden)
    _write_relation(
        kg,
        "mutation_in_gene",
        [
            {
                "edge_key": accepted[0]["edge_key"],
                "evidence_key": "equivalent-so-consequence",
                "consequence_ids": ["SO_0001583"],
                "source": "OpenTargets",
            },
            {
                "edge_key": accepted[3]["edge_key"],
                "evidence_key": "eqtl-source-native-record",
                "predicate": "source_native_variant_gene_attribution",
                "source": "OpenTargets",
            },
            {
                "edge_key": accepted[4]["edge_key"],
                "evidence_key": "l2g-source-record",
                "source_dataset": "OpenTargets/L2G",
            },
            {
                "edge_key": accepted[5]["edge_key"],
                "evidence_key": "structured-consequence-record",
                "consequence_ids": [],
                "source": "OpenTargets",
                "source_record_id": "variant:json:tc:7:gene:G-JSON",
                "text_span": json.dumps(
                    {
                        "consequence_ids": ["SO_0001583"],
                        "transcript_id": "ENST-JSON",
                    }
                ),
            },
        ],
        layer="evidence",
    )
    _write_relation(
        kg,
        "mutation_associated_disease",
        [
            _edge(
                "mutation_associated_disease",
                edge["x_id"],
                "mutation",
                f"D-{edge['x_id']}",
                "disease",
                disease_support="gwas",
            )
            for edge in accepted + forbidden
        ],
    )

    report = build_inferred_edges(_config(kg, tmp_path / "out", "variant_gene_disease_v1"))
    candidates = pd.read_parquet(
        tmp_path / "out" / "edges_inferred" / "disease_associated_gene" / "variant_gene_disease_v1.parquet"
    )

    assert set(zip(candidates.x_id, candidates.c2_support_family)) == {
        ("G-CODING", "coding_pathogenic"),
        ("G-PATH", "coding_pathogenic"),
        ("G-SPLICE", "splice"),
        ("G-EQTL", "colocalized_eqtl"),
        ("G-L2G", "l2g"),
        ("G-JSON", "coding_pathogenic"),
    }
    assert set(candidates.loc[candidates.c2_support_family.isin({"colocalized_eqtl", "l2g"}), "inference_strength"]) == {
        "statistical_conditional"
    }
    assert report["counts_by_rule"]["variant_gene_disease_v1"]["support_family_rows"] == {
        "coding_pathogenic": 3,
        "colocalized_eqtl": 1,
        "l2g": 1,
        "splice": 1,
    }
    assert report["counts_by_rule"]["variant_gene_disease_v1"]["fail_closed_paths"] == len(forbidden)
    assert all(
        sample["c2_support_family"] and sample["full_path"]
        for sample in report["top_candidate_samples"]["variant_gene_disease_v1"]
    )
    details = {row.x_id: json.loads(row.c2_support_details) for row in candidates.itertuples()}
    assert set(details["G-CODING"]["consequence"].split("|")) == {
        "missense_variant",
        "so_0001583",
    }
    assert details["G-CODING"]["transcript_provenance"] == "enst-coding"
    assert details["G-SPLICE"]["transcript_id"] == "enst-splice"
    assert details["G-EQTL"]["colocalization_method"] == "coloc"
    assert details["G-L2G"]["l2g_model"] == "v2.1"
    assert details["G-L2G"]["l2g_score"] == "0.82"
    assert "opentargets" in details["G-L2G"]["source"]
    assert details["G-JSON"]["consequence"] == "so_0001583"
    assert details["G-JSON"]["transcript_id"] == "enst-json"


def test_c2_missing_or_conflicting_attribution_evidence_emits_zero(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    endpoint = _edge(
        "mutation_in_gene",
        "V",
        "mutation",
        "G",
        "gene",
        consequence="missense_variant",
        transcript_id="ENST",
        attribution_method="coding_consequence",
    )
    _write_relation(kg, "mutation_in_gene", [endpoint])
    _write_relation(
        kg,
        "mutation_in_gene",
        [
            {
                "edge_key": endpoint["edge_key"],
                "evidence_key": "contradictory-attribution",
                "attribution_method": "nearest_gene",
                "source": "OpenTargets",
                "source_record_id": "record-1",
            }
        ],
        layer="evidence",
    )
    _write_relation(
        kg,
        "mutation_associated_disease",
        [_edge("mutation_associated_disease", "V", "mutation", "D", "disease", disease_support="pathogenic")],
    )

    report = build_inferred_edges(_config(kg, tmp_path / "out", "variant_gene_disease_v1"))

    assert report["counts_by_rule"]["variant_gene_disease_v1"]["candidate_rows"] == 0
    assert report["counts_by_rule"]["variant_gene_disease_v1"]["fail_closed_paths"] == 1
    assert not list((tmp_path / "out").rglob("variant_gene_disease_v1.parquet"))


def test_h1_requires_opposite_known_signs_and_h2_only_reinforces_existing_candidate(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_relation(
        kg,
        "molecule_targets_gene",
        [
            _edge("molecule_targets_gene", "M1", "molecule", "G1", "gene", action_sign="inhibit"),
            _edge("molecule_targets_gene", "M2", "molecule", "G2", "gene", action_sign="unknown"),
        ],
    )
    _write_relation(
        kg,
        "disease_associated_gene",
        [
            _edge("disease_associated_gene", "G1", "gene", "D1", "disease", mechanism_sign="gain_of_function", causal_support=True),
            _edge("disease_associated_gene", "G2", "gene", "D2", "disease", mechanism_sign="gain_of_function", causal_support=True),
        ],
    )
    _write_relation(kg, "molecule_targets_protein", [_edge("molecule_targets_protein", "M3", "molecule", "P1", "protein", action_sign="inhibit")])
    _write_relation(kg, "disease_associated_protein", [_edge("disease_associated_protein", "P1", "protein", "D1", "disease", mechanism_sign="gain_of_function", causal_support=True)])
    _write_relation(kg, "disease_manifests_in_tissue", [_edge("disease_manifests_in_tissue", "D1", "disease", "T1", "tissue")])
    _write_relation(
        kg,
        "tissue_expresses_gene",
        [
            _edge("tissue_expresses_gene", "T1", "tissue", "G1", "gene", measurement_modality="rna"),
            _edge("tissue_expresses_gene", "T1", "tissue", "G_ONLY", "gene", measurement_modality="rna"),
        ],
    )
    _write_relation(kg, "tissue_expresses_protein", [_edge("tissue_expresses_protein", "T1", "tissue", "P_ONLY", "protein", measurement_modality="protein")])

    build_inferred_edges(
        _config(
            kg,
            tmp_path / "out",
            "signed_target_mechanism_gene_drug_disease_v1",
            "signed_target_mechanism_protein_drug_disease_v1",
        )
    )
    candidates = pd.read_parquet(tmp_path / "out" / "edges_inferred" / "molecule_treats_disease" / "signed_target_mechanism_gene_drug_disease_v1.parquet")
    protein_candidates = pd.read_parquet(tmp_path / "out" / "edges_inferred" / "molecule_treats_disease" / "signed_target_mechanism_protein_drug_disease_v1.parquet")

    assert set(zip(candidates.x_id, candidates.y_id)) == {("M1", "D1")}
    assert candidates.loc[0, "sign_status"] == "known"
    assert candidates.loc[0, "inference_strength"] == "strong_reinforced"
    assert json.loads(candidates.loc[0, "context_intersection"])["h2_tissues"] == ["T1"]
    assert set(zip(protein_candidates.x_id, protein_candidates.y_id)) == {("M3", "D1")}
    assert protein_candidates.loc[0, "inference_strength"] == "strong"
    assert json.loads(protein_candidates.loc[0, "context_intersection"])["h2_tissues"] == []


def test_outputs_have_reproducible_derivation_contract_and_observed_absence_is_not_negation(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_relation(
        kg,
        "mutation_in_gene",
        [_edge("mutation_in_gene", "V", "mutation", "G", "gene", consequence="missense_variant", transcript_id="ENST")],
    )
    _write_relation(kg, "mutation_associated_disease", [_edge("mutation_associated_disease", "V", "mutation", "D", "disease", disease_support="gwas")])

    for name in ("out-a", "out-b"):
        build_inferred_edges(_config(kg, tmp_path / name, "variant_gene_disease_v1"))
    first = pd.read_parquet(tmp_path / "out-a" / "edges_inferred" / "disease_associated_gene" / "variant_gene_disease_v1.parquet")
    second = pd.read_parquet(tmp_path / "out-b" / "edges_inferred" / "disease_associated_gene" / "variant_gene_disease_v1.parquet")
    required = {
        "support_edge_ids_or_hashes",
        "support_evidence_ids_or_hashes",
        "full_path",
        "kg_snapshot_id",
        "kg_generations",
        "context_intersection",
        "sign_status",
        "inference_strength",
        "canonical_observed_overlap",
        "observed_antijoin_status",
        "absence_is_not_biological_negation",
        "derivation_hash",
    }
    assert required <= set(first.columns)
    assert first.loc[0, "derivation_hash"] == second.loc[0, "derivation_hash"]
    assert first.loc[0, "observed_antijoin_status"] == "missing_from_observed_relation"
    assert bool(first.loc[0, "absence_is_not_biological_negation"])
    evidence = pd.read_parquet(tmp_path / "out-a" / "evidence_inferred" / "disease_associated_gene" / "variant_gene_disease_v1.parquet")
    assert set(evidence.derivation_hash) == set(first.derivation_hash)
    assert evidence.loc[0, "c2_support_family"] == "coding_pathogenic"
    assert evidence.loc[0, "c2_support_details"] == first.loc[0, "c2_support_details"]
    report = json.loads(
        (tmp_path / "out-a" / "manifest" / "pilot_report.json").read_text()
    )
    assert report["producer_revision"] == "test-revision"


def test_build_refuses_to_write_inside_immutable_input_snapshot(tmp_path: Path) -> None:
    kg = tmp_path / "immutable-kg"
    _write_relation(kg, "mutation_in_gene", [_edge("mutation_in_gene", "V", "mutation", "G", "gene")])
    _write_relation(kg, "mutation_associated_disease", [_edge("mutation_associated_disease", "V", "mutation", "D", "disease")])

    with pytest.raises(ValueError, match="read-only immutable snapshot"):
        build_inferred_edges(_config(kg, kg, "variant_gene_disease_v1"))

    assert not (kg / "edges_inferred").exists()
    assert not (kg / "evidence_inferred").exists()


def test_excluded_generators_are_rejected_without_creating_placeholder_parquets(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_relation(kg, "tf_binds_enhancer", [_edge("tf_binds_enhancer", "TF", "gene", "E", "enhancer")])
    _write_relation(kg, "enhancer_regulates_gene", [_edge("enhancer_regulates_gene", "E", "enhancer", "G", "gene")])

    with pytest.raises(ValueError, match="Unknown/unapproved rule IDs"):
        build_inferred_edges(_config(kg, tmp_path / "out", "c4_tf_enhancer_gene"))

    assert not list((tmp_path / "out").glob("**/*.parquet"))


def test_removed_c3_is_unregistered_unmaterializable_and_cleaned_from_same_output_root(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    output = tmp_path / "out"
    _write_relation(
        kg,
        "mutation_in_gene",
        [_edge("mutation_in_gene", "V", "mutation", "G", "gene", consequence="missense_variant", transcript_id="ENST")],
    )
    _write_relation(
        kg,
        "mutation_associated_disease",
        [_edge("mutation_associated_disease", "V", "mutation", "D", "disease", disease_support="pathogenic")],
    )
    stale_paths = [
        output
        / layer
        / "disease_associated_gene"
        / "variant_enhancer_gene_disease_v1.parquet"
        for layer in ("edges_inferred", "evidence_inferred")
    ]
    for stale_path in stale_paths:
        stale_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{"stale": True}]).to_parquet(stale_path, index=False)

    with pytest.raises(ValueError, match="Unknown/unapproved rule IDs"):
        build_inferred_edges(
            _config(kg, output, "variant_enhancer_gene_disease_v1")
        )

    report = build_inferred_edges(_config(kg, output, "variant_gene_disease_v1"))

    assert "variant_enhancer_gene_disease_v1" not in RULES_BY_ID
    assert all(not path.exists() for path in stale_paths)
    assert "variant_enhancer_gene_disease_v1" not in json.dumps(report, sort_keys=True)
    assert "variant_enhancer_gene_disease_v1" not in (
        output / "manifest" / "rule_registry_v1.json"
    ).read_text()


def test_fail_closed_gate_fields_can_be_supplied_by_derivation_evidence(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    disease = _edge("mutation_associated_disease", "V", "mutation", "D", "disease", disease_support="pathogenic")
    response = _edge("mutation_affects_molecule_response", "V", "mutation", "M", "molecule", pgx_category="efficacy")
    _write_relation(kg, "mutation_associated_disease", [disease])
    _write_relation(kg, "mutation_affects_molecule_response", [response])
    _write_relation(
        kg,
        "mutation_affects_molecule_response",
        [
            {
                "edge_key": response["edge_key"],
                "relation": "mutation_affects_molecule_response",
                "x_id": "V",
                "y_id": "M",
                "source_record_id": "pgx-record-1",
                "direction": "increased_response",
                "predicate": "efficacy",
            }
        ],
        layer="evidence",
    )

    build_inferred_edges(_config(kg, tmp_path / "out", "pharmacogenomic_variant_drug_disease_v1"))
    candidate = pd.read_parquet(
        tmp_path / "out" / "edges_inferred" / "molecule_treats_disease" / "pharmacogenomic_variant_drug_disease_v1.parquet"
    ).iloc[0]

    assert set(json.loads(candidate.support_evidence_ids_or_hashes)) == {"pgx-record-1"}
    assert candidate.inference_strength == "strong"


def test_direct_values_conflicting_with_single_evidence_fail_closed_for_h1(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    target = _edge(
        "molecule_targets_gene",
        "M-H1",
        "molecule",
        "G-H1",
        "gene",
        action_sign="inhibit",
    )
    _write_relation(kg, "molecule_targets_gene", [target])
    _write_relation(
        kg,
        "disease_associated_gene",
        [
            _edge(
                "disease_associated_gene",
                "G-H1",
                "gene",
                "D-H1",
                "disease",
                mechanism_sign="gain_of_function",
                causal_support=True,
            )
        ],
    )
    _write_relation(
        kg,
        "molecule_targets_gene",
        [{"edge_key": target["edge_key"], "evidence_key": "activate-only", "action_sign": "activate"}],
        layer="evidence",
    )

    manifest = build_inferred_edges(
        _config(kg, tmp_path / "out", "signed_target_mechanism_gene_drug_disease_v1")
    )
    assert manifest["counts_by_rule"]["signed_target_mechanism_gene_drug_disease_v1"]["candidate_rows"] == 0


def test_direct_alias_values_conflicting_with_single_evidence_fail_closed_for_c1_c2_c5(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    protein = _edge(
        "mutation_causes_protein_change",
        "V-C1",
        "mutation",
        "P-C1",
        "protein",
        predicate="protein_change",
        isoform_id="I-C1",
    )
    c2_disease = _edge(
        "mutation_associated_disease",
        "V-C2",
        "mutation",
        "D-C2",
        "disease",
        clinical_significance="pathogenic",
        functional_support="clinvar",
    )
    response = _edge(
        "mutation_affects_molecule_response",
        "V-C5",
        "mutation",
        "M-C5",
        "molecule",
        direction="increased_response",
        response_category="efficacy",
    )
    _write_relation(kg, "mutation_causes_protein_change", [protein])
    _write_relation(
        kg,
        "mutation_in_gene",
        [
            _edge(
                "mutation_in_gene",
                "V-C2",
                "mutation",
                "G-C2",
                "gene",
                consequence="missense_variant",
                transcript_id="ENST-C2",
            )
        ],
    )
    _write_relation(
        kg,
        "mutation_associated_disease",
        [
            _edge(
                "mutation_associated_disease",
                "V-C1",
                "mutation",
                "D-C1",
                "disease",
                disease_support="pathogenic",
                functional_support="clinvar",
                isoform_id="I-C1",
            ),
            c2_disease,
            _edge(
                "mutation_associated_disease",
                "V-C5",
                "mutation",
                "D-C5",
                "disease",
                disease_support="pathogenic",
            ),
        ],
    )
    _write_relation(kg, "mutation_affects_molecule_response", [response])
    _write_relation(
        kg,
        "mutation_causes_protein_change",
        [{"edge_key": protein["edge_key"], "evidence_key": "intronic-only", "predicate": "intronic_variant"}],
        layer="evidence",
    )
    _write_relation(
        kg,
        "mutation_associated_disease",
        [{"edge_key": c2_disease["edge_key"], "evidence_key": "benign-only", "clinical_significance": "benign"}],
        layer="evidence",
    )
    _write_relation(
        kg,
        "mutation_affects_molecule_response",
        [{"edge_key": response["edge_key"], "evidence_key": "resistance-only", "direction": "resistance"}],
        layer="evidence",
    )

    manifest = build_inferred_edges(
        _config(
            kg,
            tmp_path / "out",
            "variant_protein_disease_v1",
            "variant_gene_disease_v1",
            "pharmacogenomic_variant_drug_disease_v1",
        )
    )

    assert manifest["counts_by_rule"]["variant_protein_disease_v1"]["candidate_rows"] == 0
    assert manifest["counts_by_rule"]["variant_gene_disease_v1"]["strong_rows"] == 0
    assert manifest["counts_by_rule"]["pharmacogenomic_variant_drug_disease_v1"]["candidate_rows"] == 0


def test_literal_and_multivalued_conflicts_fail_closed_across_strong_gates(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    target = _edge(
        "molecule_targets_gene",
        "M-H1",
        "molecule",
        "G-H1",
        "gene",
        action_sign="inhibit",
    )
    mechanism_target = _edge(
        "molecule_targets_gene",
        "M-H1-MECH",
        "molecule",
        "G-H1-MECH",
        "gene",
        action_sign="inhibit",
    )
    _write_relation(
        kg,
        "mutation_causes_protein_change",
        [
            _edge(
                "mutation_causes_protein_change",
                "V-C1",
                "mutation",
                "P-C1",
                "protein",
                consequence="protein_change",
                isoform_id="I-C1",
            )
        ],
    )
    _write_relation(
        kg,
        "mutation_in_gene",
        [
            _edge(
                "mutation_in_gene",
                "V-C2",
                "mutation",
                "G-C2",
                "gene",
                consequence="missense_variant",
                transcript_id="ENST-C2",
            )
        ],
    )
    _write_relation(
        kg,
        "mutation_associated_disease",
        [
            _edge(
                "mutation_associated_disease",
                "V-C1",
                "mutation",
                "D-C1",
                "disease",
                disease_support="conflicting",
                clinical_significance="pathogenic",
                functional_support="clinvar",
                isoform_id="I-C1",
            ),
            _edge(
                "mutation_associated_disease",
                "V-C2",
                "mutation",
                "D-C2",
                "disease",
                disease_support="pathogenic",
            ),
            _edge(
                "mutation_associated_disease",
                "V-C5",
                "mutation",
                "D-C5",
                "disease",
                disease_support="pathogenic",
            ),
        ],
    )
    _write_relation(
        kg,
        "mutation_affects_molecule_response",
        [
            _edge(
                "mutation_affects_molecule_response",
                "V-C5",
                "mutation",
                "M-C5",
                "molecule",
                response_direction="conflicting",
                direction="increased_response",
                response_category="efficacy",
            )
        ],
    )
    _write_relation(kg, "molecule_targets_gene", [target, mechanism_target])
    _write_relation(
        kg,
        "molecule_targets_gene",
        [
            {
                "edge_key": target["edge_key"],
                "relation": target["relation"],
                "evidence_key": "action-inhibit",
                "action_sign": "inhibit",
            },
            {
                "edge_key": target["edge_key"],
                "relation": target["relation"],
                "evidence_key": "action-activate",
                "action_sign": "activate",
            },
        ],
        layer="evidence",
    )
    c2_endpoint = _edge(
        "mutation_in_gene",
        "V-C2",
        "mutation",
        "G-C2",
        "gene",
        consequence="missense_variant",
        transcript_id="ENST-C2",
    )
    _write_relation(
        kg,
        "mutation_in_gene",
        [
            {
                "edge_key": c2_endpoint["edge_key"],
                "relation": c2_endpoint["relation"],
                "evidence_key": "coding-missense",
                "consequence": "missense_variant",
            },
            {
                "edge_key": c2_endpoint["edge_key"],
                "relation": c2_endpoint["relation"],
                "evidence_key": "coding-frameshift",
                "consequence": "frameshift_variant",
            },
        ],
        layer="evidence",
    )
    _write_relation(
        kg,
        "disease_associated_gene",
        [
            _edge(
                "disease_associated_gene",
                "G-H1",
                "gene",
                "D-H1",
                "disease",
                mechanism_sign="gain_of_function",
                causal_support=True,
            ),
            _edge(
                "disease_associated_gene",
                "G-H1-MECH",
                "gene",
                "D-H1-MECH",
                "disease",
                mechanism_sign="gain_of_function",
                causal_support=True,
            ),
        ],
    )
    mechanism_edge_key = "disease_associated_gene|G-H1-MECH|D-H1-MECH"
    _write_relation(
        kg,
        "disease_associated_gene",
        [
            {
                "edge_key": mechanism_edge_key,
                "relation": "disease_associated_gene",
                "evidence_key": "mechanism-gain",
                "pathological_mechanism_sign": "gain_of_function",
            },
            {
                "edge_key": mechanism_edge_key,
                "relation": "disease_associated_gene",
                "evidence_key": "mechanism-loss",
                "pathological_mechanism_sign": "loss_of_function",
            },
        ],
        layer="evidence",
    )

    manifest = build_inferred_edges(
        _config(
            kg,
            tmp_path / "out",
            "variant_protein_disease_v1",
            "variant_gene_disease_v1",
            "pharmacogenomic_variant_drug_disease_v1",
            "signed_target_mechanism_gene_drug_disease_v1",
        )
    )
    c1 = pd.read_parquet(
        tmp_path
        / "out"
        / "edges_inferred"
        / "disease_associated_protein"
        / "variant_protein_disease_v1.parquet"
    )
    assert set(c1.inference_strength) == {"hypothesis"}
    assert manifest["counts_by_rule"]["variant_gene_disease_v1"]["candidate_rows"] == 0
    assert not list((tmp_path / "out").rglob("variant_gene_disease_v1.parquet"))
    assert manifest["counts_by_rule"]["pharmacogenomic_variant_drug_disease_v1"]["candidate_rows"] == 0
    assert manifest["counts_by_rule"]["signed_target_mechanism_gene_drug_disease_v1"]["candidate_rows"] == 0
    assert "pharmacogenomic_variant_drug_disease_v1" not in manifest["artifacts"]
    assert "signed_target_mechanism_gene_drug_disease_v1" not in manifest["artifacts"]


def test_zero_candidate_rerun_removes_both_rule_owned_parquets_and_manifest_inventory(
    tmp_path: Path,
) -> None:
    populated = tmp_path / "populated"
    empty = tmp_path / "empty"
    output = tmp_path / "out"
    _write_relation(
        populated,
        "mutation_in_gene",
        [_edge("mutation_in_gene", "V", "mutation", "G", "gene", consequence="missense_variant", transcript_id="ENST")],
    )
    _write_relation(
        populated,
        "mutation_associated_disease",
        [_edge("mutation_associated_disease", "V", "mutation", "D", "disease")],
    )
    _write_relation(
        empty,
        "mutation_in_gene",
        [_edge("mutation_in_gene", "V1", "mutation", "G", "gene")],
    )
    _write_relation(
        empty,
        "mutation_associated_disease",
        [_edge("mutation_associated_disease", "V2", "mutation", "D", "disease")],
    )
    edge_path = (
        output
        / "edges_inferred"
        / "disease_associated_gene"
        / "variant_gene_disease_v1.parquet"
    )
    evidence_path = (
        output
        / "evidence_inferred"
        / "disease_associated_gene"
        / "variant_gene_disease_v1.parquet"
    )

    first = build_inferred_edges(_config(populated, output, "variant_gene_disease_v1"))
    assert first["counts_by_rule"]["variant_gene_disease_v1"]["candidate_rows"] == 1
    assert edge_path.exists()
    assert evidence_path.exists()

    second = build_inferred_edges(_config(empty, output, "variant_gene_disease_v1"))

    assert second["counts_by_rule"]["variant_gene_disease_v1"]["candidate_rows"] == 0
    assert second["artifacts"] == {}
    assert not edge_path.exists()
    assert not evidence_path.exists()
    assert not list((output / "edges_inferred").rglob("variant_gene_disease_v1.parquet"))
    assert not list((output / "evidence_inferred").rglob("variant_gene_disease_v1.parquet"))


def test_build_rejects_unbounded_input_snapshot_before_loading_rows(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_relation(
        kg,
        "mutation_in_gene",
        [
            _edge("mutation_in_gene", "V1", "mutation", "G1", "gene"),
            _edge("mutation_in_gene", "V2", "mutation", "G2", "gene"),
        ],
    )
    _write_relation(kg, "mutation_associated_disease", [_edge("mutation_associated_disease", "V1", "mutation", "D1", "disease")])

    config = replace(_config(kg, tmp_path / "out", "variant_gene_disease_v1"), max_input_rows=1)
    with pytest.raises(ValueError, match="exceeds bounded input limit"):
        build_inferred_edges(config)

    assert not (tmp_path / "out").exists()


def test_cli_builds_only_requested_staged_inferred_rule(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from scripts import build_inferred_relation_algebra

    kg = tmp_path / "kg"
    _write_relation(
        kg,
        "mutation_in_gene",
        [_edge("mutation_in_gene", "V", "mutation", "G", "gene", consequence="missense_variant", transcript_id="ENST")],
    )
    _write_relation(kg, "mutation_associated_disease", [_edge("mutation_associated_disease", "V", "mutation", "D", "disease")])
    output = tmp_path / "staged"

    assert (
        build_inferred_relation_algebra.main(
            [
                "--kg-root",
                str(kg),
                "--output-root",
                str(output),
                "--kg-snapshot-id",
                "sha256:immutable-cli-fixture",
                "--kg-generations-json",
                '{"edges/mutation_in_gene":"9"}',
                "--producer-revision",
                "test-revision",
                "--rule",
                "variant_gene_disease_v1",
                "--max-input-rows",
                "10",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["counts_by_rule"]["variant_gene_disease_v1"]["candidate_rows"] == 1
    assert (output / "edges_inferred" / "disease_associated_gene" / "variant_gene_disease_v1.parquet").exists()
