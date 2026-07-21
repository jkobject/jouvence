import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

import manage_db.relation_composition_allowlist as composition
from manage_db.relation_composition_allowlist import (
    POLICY_REVISION,
    REJECTED_MOTIFS,
    TEMPLATES,
    TEMPLATE_BY_ID,
    BuildConfig,
    build_composition_allowlist,
)


def edge(relation: str, x: str, xt: str, y: str, yt: str, **extra: object) -> dict:
    return {
        "relation": relation,
        "x_id": x,
        "x_type": xt,
        "y_id": y,
        "y_type": yt,
        "edge_key": f"{relation}|{x}|{y}",
        "source": extra.pop("source", "source-a"),
        **extra,
    }


def write(root: Path, relation: str, rows: list[dict], layer: str = "edges") -> None:
    path = root / layer / f"{relation}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def inventory_key_sha256(keys: set[str]) -> str:
    payload = json.dumps(sorted(keys), separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def write_inventory_receipt(
    root: Path,
    relation: str,
    *,
    snapshot_id: str = "immutable-fixture-v1",
    source_identity: str = "canonical-fixture-source-v1",
) -> Path:
    edge_path = root / "edges" / f"{relation}.parquet"
    evidence_path = root / "evidence" / f"{relation}.parquet"
    edges = pd.read_parquet(edge_path)
    evidence = pd.read_parquet(evidence_path)
    edge_keys = set(edges.edge_key.astype(str))
    evidence_keys = set(evidence.edge_key.astype(str))
    receipt = {
        "receipt_version": "canonical-target-inventory-v1",
        "accepted": True,
        "relation": relation,
        "snapshot_id": snapshot_id,
        "source_identity": source_identity,
        "edges": {
            "path": f"edges/{relation}.parquet",
            "file_sha256": hashlib.sha256(edge_path.read_bytes()).hexdigest(),
            "edge_key_count": len(edge_keys),
            "edge_key_set_sha256": inventory_key_sha256(edge_keys),
        },
        "evidence": {
            "path": f"evidence/{relation}.parquet",
            "file_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            "edge_key_count": len(evidence_keys),
            "edge_key_set_sha256": inventory_key_sha256(evidence_keys),
        },
        "coverage": {
            "supported_edge_key_count": len(edge_keys & evidence_keys),
            "orphan_evidence_edge_key_count": len(evidence_keys - edge_keys),
            "gap_edge_key_count": len(edge_keys - evidence_keys),
        },
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = root / "manifest" / "canonical_target_inventory" / f"{relation}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return path


def config(
    kg: Path, out: Path, *templates: str, staged: tuple[Path, ...] = ()
) -> BuildConfig:
    return BuildConfig(
        input_root=kg,
        staged_input_roots=staged,
        output_root=out,
        snapshot_id="immutable-fixture-v1",
        producer_revision=POLICY_REVISION,
        template_ids=templates,
        max_rows_per_file=1000,
        max_paths_per_template=1000,
        require_canonical_target_inventory=False,
        canonical_target_inventory_source_identity="canonical-fixture-source-v1",
    )


def read_output(
    out: Path, target: str, template: str, layer: str = "edges_inferred"
) -> pd.DataFrame:
    return pd.read_parquet(out / layer / target / f"{template}.parquet")


def test_registry_maps_every_approved_motif_and_rejects_forbidden_directions() -> None:
    assert len(TEMPLATES) == 24
    assert len(TEMPLATE_BY_ID) == 24
    assert all(
        template.required_fields and template.expected_zero for template in TEMPLATES
    )
    assert {template.output_class for template in TEMPLATES} == {
        "inferred_edge",
        "derived_view",
    }
    ids = set(TEMPLATE_BY_ID)
    assert "mutation_transcript_gene_attribution_v2" in ids
    assert "mutation_protein_gene_attribution_v2" in ids
    assert "cell_type_tissue_gene_existential_v2" in ids
    assert "protein_disease_to_gene_disease_v2" in ids
    assert "gene_disease_to_protein_disease_strict_v2" in ids
    assert "pathway_associated_member_feature_v2" in ids
    assert "disease_phenotype_tissue_triangle_v2" in ids
    assert "allelic_triangulation_treatment_v2" in ids
    assert "pharmacogenomic_efficacy_treatment_v2" in ids
    assert "signed_gene_target_contraindication_v2" in ids
    assert "signed_protein_target_contraindication_v2" in ids
    assert all("enhancer" not in template.template_id for template in TEMPLATES)
    assert "rna_gene_to_protein_expression" in REJECTED_MOTIFS
    assert "generic_cell_response_phenotype" in REJECTED_MOTIFS


def test_exact_mutation_mapping_accepts_transcript_and_protein_but_not_containment(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "mutation_affects_transcript",
        [
            edge(
                "mutation_affects_transcript",
                "V1",
                "mutation",
                "TX1",
                "transcript",
                assembly="GRCh38",
            )
        ],
    )
    write(
        kg,
        "mutation_causes_protein_change",
        [
            edge(
                "mutation_causes_protein_change",
                "V2",
                "mutation",
                "P1",
                "protein",
                assembly="GRCh38",
                isoform_id="P1",
            ),
            edge(
                "mutation_causes_protein_change",
                "V3",
                "mutation",
                "P2",
                "protein",
                assembly="GRCh37",
                isoform_id="P2",
            ),
        ],
    )
    write(
        kg,
        "gene_has_transcript",
        [
            edge(
                "gene_has_transcript",
                "G1",
                "gene",
                "TX1",
                "transcript",
                assembly="GRCh38",
            ),
            edge(
                "gene_has_transcript",
                "G2",
                "gene",
                "TX2",
                "transcript",
                assembly="GRCh38",
            ),
        ],
    )
    write(
        kg,
        "transcript_encodes_protein",
        [
            edge(
                "transcript_encodes_protein",
                "TX1",
                "transcript",
                "P1",
                "protein",
                assembly="GRCh38",
                isoform_id="P1",
            ),
            edge(
                "transcript_encodes_protein",
                "TX2",
                "transcript",
                "P2",
                "protein",
                assembly="GRCh38",
                isoform_id="P2",
            ),
        ],
    )
    write(
        kg,
        "mutation_in_gene",
        [edge("mutation_in_gene", "V4", "mutation", "G4", "gene")],
    )

    report = build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "mutation_transcript_gene_attribution_v2",
            "mutation_protein_gene_attribution_v2",
        )
    )
    tx = read_output(
        tmp_path / "out",
        "mutation_associated_gene",
        "mutation_transcript_gene_attribution_v2",
    )
    protein = read_output(
        tmp_path / "out",
        "mutation_associated_gene",
        "mutation_protein_gene_attribution_v2",
    )
    assert set(zip(tx.x_id, tx.y_id, tx.attribution_mode)) == {
        ("V1", "G1", "exact_transcript_consequence")
    }
    assert "typed_path" not in tx.columns
    tx_evidence = read_output(
        tmp_path / "out",
        "mutation_associated_gene",
        "mutation_transcript_gene_attribution_v2",
        "evidence_inferred",
    )
    assert "typed_path" in tx_evidence.columns
    assert tx_evidence.loc[0, "support_evidence_ids_or_hashes"]
    assert set(zip(protein.x_id, protein.y_id, protein.attribution_mode)) == {
        ("V2", "G1", "exact_protein_consequence")
    }
    assert "V4" not in set(tx.x_id) | set(protein.x_id)
    assert (
        report["rejection_reason_counts"]["mutation_protein_gene_attribution_v2"][
            "isoform_or_assembly_mismatch"
        ]
        == 1
    )


def test_protein_observation_projects_to_gene_with_no_rna_claim_and_reverse_is_absent(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "gene_has_transcript",
        [
            edge(
                "gene_has_transcript",
                "G",
                "gene",
                "TX",
                "transcript",
                assembly="GRCh38",
            )
        ],
    )
    write(
        kg,
        "transcript_encodes_protein",
        [
            edge(
                "transcript_encodes_protein",
                "TX",
                "transcript",
                "P",
                "protein",
                assembly="GRCh38",
                mapping_version="ensembl-1",
            )
        ],
    )
    write(
        kg,
        "tissue_expresses_protein",
        [
            edge(
                "tissue_expresses_protein",
                "T",
                "tissue",
                "P",
                "protein",
                measurement_modality="proteomics",
            )
        ],
    )
    write(
        kg,
        "cell_type_expresses_protein",
        [
            edge(
                "cell_type_expresses_protein",
                "CT",
                "cell_type",
                "P",
                "protein",
                measurement_modality="antibody",
            )
        ],
    )
    write(
        kg,
        "cell_line_expresses_protein",
        [
            edge(
                "cell_line_expresses_protein",
                "CL",
                "cell_line",
                "P",
                "protein",
                measurement_modality="mass_spectrometry",
            )
        ],
    )
    write(
        kg,
        "tissue_expresses_gene",
        [
            edge(
                "tissue_expresses_gene",
                "T2",
                "tissue",
                "G",
                "gene",
                measurement_modality="rna",
            )
        ],
    )

    build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "tissue_protein_to_gene_expression_v2",
            "cell_type_protein_to_gene_expression_v2",
            "cell_line_protein_to_gene_expression_v2",
        )
    )
    for template, target, x in [
        ("tissue_protein_to_gene_expression_v2", "tissue_expresses_gene", "T"),
        ("cell_type_protein_to_gene_expression_v2", "cell_type_expresses_gene", "CT"),
        ("cell_line_protein_to_gene_expression_v2", "cell_line_expresses_gene", "CL"),
    ]:
        row = read_output(tmp_path / "out", target, template).iloc[0]
        evidence_row = read_output(
            tmp_path / "out", target, template, "evidence_inferred"
        ).iloc[0]
        assert row.x_id == x and row.y_id == "G"
        assert row.support_mode == "protein_product_observed"
        assert not bool(row.rna_measured)
        assert "supporting_protein_id" not in row.index
        assert evidence_row.supporting_protein_id == "P"
    assert all(
        "gene_to_protein_expression" not in template.template_id
        for template in TEMPLATES
    )


def test_protein_disease_projection_direction_and_strict_reverse(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "gene_has_transcript",
        [edge("gene_has_transcript", "G", "gene", "TX", "transcript")],
    )
    write(
        kg,
        "transcript_encodes_protein",
        [edge("transcript_encodes_protein", "TX", "transcript", "P", "protein")],
    )
    write(
        kg,
        "disease_associated_protein",
        [
            edge(
                "disease_associated_protein",
                "P",
                "protein",
                "D1",
                "disease",
                source="uniprot",
            )
        ],
    )
    write(
        kg,
        "disease_associated_gene",
        [
            edge("disease_associated_gene", "G", "gene", "D2", "disease"),
            edge(
                "disease_associated_gene", "G", "gene", "D3", "disease", protein_id="P"
            ),
        ],
    )
    report = build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "protein_disease_to_gene_disease_v2",
            "gene_disease_to_protein_disease_strict_v2",
        )
    )
    forward = read_output(
        tmp_path / "out",
        "disease_associated_gene",
        "protein_disease_to_gene_disease_v2",
    )
    reverse = read_output(
        tmp_path / "out",
        "disease_associated_protein",
        "gene_disease_to_protein_disease_strict_v2",
    )
    assert set(zip(forward.x_id, forward.y_id)) == {("G", "D1")}
    assert set(zip(reverse.x_id, reverse.y_id)) == {("P", "D3")}
    assert (
        report["rejection_reason_counts"]["gene_disease_to_protein_disease_strict_v2"][
            "missing_isoform_support"
        ]
        == 1
    )


def test_mutation_disease_phenotype_candidate_and_coherence_preserve_disease_anchor(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "mutation_associated_disease",
        [
            edge(
                "mutation_associated_disease",
                "V",
                "mutation",
                "D",
                "disease",
                source="gwas",
            ),
            edge(
                "mutation_associated_disease",
                "V2",
                "mutation",
                "D2",
                "disease",
                source="",
            ),
        ],
    )
    write(
        kg,
        "disease_has_phenotype",
        [
            edge(
                "disease_has_phenotype",
                "D",
                "disease",
                "HP1",
                "phenotype",
                source="hpo",
            ),
            edge(
                "disease_has_phenotype",
                "OTHER",
                "disease",
                "HP2",
                "phenotype",
                source="hpo",
            ),
            edge(
                "disease_has_phenotype",
                "D2",
                "disease",
                "HP3",
                "phenotype",
                source="",
            ),
        ],
    )
    write(
        kg,
        "mutation_associated_phenotype",
        [
            edge(
                "mutation_associated_phenotype",
                "V",
                "mutation",
                "HP1",
                "phenotype",
                source="clinvar",
            )
        ],
    )
    report = build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "mutation_disease_phenotype_candidate_v2",
            "mutation_disease_phenotype_triangle_v2",
        )
    )
    triangle = read_output(
        tmp_path / "out",
        "mutation_disease_phenotype_coherence",
        "mutation_disease_phenotype_triangle_v2",
        "derived_views",
    )
    # The conditional candidate is generated, then removed by the required
    # observed-target anti-join.  The complete triangle remains a derived view.
    assert not list(
        (tmp_path / "out" / "edges_inferred").rglob(
            "mutation_disease_phenotype_candidate_v2.parquet"
        )
    )
    assert (
        report["rejection_reason_counts"]["mutation_disease_phenotype_candidate_v2"][
            "canonical_observed_overlap"
        ]
        == 1
    )
    assert (
        report["rejection_reason_counts"]["mutation_disease_phenotype_candidate_v2"][
            "context_or_source_circularity"
        ]
        == 1
    )
    assert set(zip(triangle.x_id, triangle.y_id)) == {("V", "HP1")}
    assert bool(triangle.coherence_only.iloc[0])


def test_cell_type_existential_support_is_context_compatible_and_not_bulk_claim(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "cell_type_found_in_tissue",
        [
            edge(
                "cell_type_found_in_tissue",
                "CT1",
                "cell_type",
                "T1",
                "tissue",
                organism="human",
            ),
            edge(
                "cell_type_found_in_tissue",
                "CT2",
                "cell_type",
                "T2",
                "tissue",
                organism="human",
            ),
        ],
    )
    write(
        kg,
        "cell_type_expresses_gene",
        [
            edge(
                "cell_type_expresses_gene",
                "CT1",
                "cell_type",
                "G1",
                "gene",
                organism="human",
            ),
            edge(
                "cell_type_expresses_gene",
                "CT2",
                "cell_type",
                "G2",
                "gene",
                organism="mouse",
            ),
        ],
    )
    report = build_composition_allowlist(
        config(kg, tmp_path / "out", "cell_type_tissue_gene_existential_v2")
    )
    rows = read_output(
        tmp_path / "out",
        "tissue_expresses_gene",
        "cell_type_tissue_gene_existential_v2",
    )
    assert set(zip(rows.x_id, rows.y_id)) == {("T1", "G1")}
    assert "supporting_cell_type_id" not in rows.columns
    evidence_rows = read_output(
        tmp_path / "out",
        "tissue_expresses_gene",
        "cell_type_tissue_gene_existential_v2",
        "evidence_inferred",
    )
    assert evidence_rows.supporting_cell_type_id.tolist() == ["CT1"]
    assert rows.loc[0, "quantifier"] == "exists_supporting_cell_population"
    assert (
        report["rejection_reason_counts"]["cell_type_tissue_gene_existential_v2"][
            "context_mismatch"
        ]
        == 1
    )


def test_pathway_features_do_not_project_every_member_and_candidate_has_strict_gates(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    members = [
        edge("pathway_contains_gene", "PW", "pathway", f"G{i}", "gene")
        for i in range(1, 4)
    ]
    members += [
        edge("pathway_contains_gene", "SAME", "pathway", "G4", "gene"),
        edge("pathway_contains_gene", "SAME", "pathway", "G5", "gene"),
    ]
    members += [
        edge("pathway_contains_gene", "FANOUT", "pathway", f"X{i}", "gene")
        for i in range(501)
    ]
    write(kg, "pathway_contains_gene", members)
    write(
        kg,
        "disease_associated_gene",
        [
            edge(
                "disease_associated_gene",
                "G1",
                "gene",
                "D",
                "disease",
                source="source-1",
            ),
            edge(
                "disease_associated_gene",
                "G2",
                "gene",
                "D",
                "disease",
                source="source-2",
            ),
            edge(
                "disease_associated_gene",
                "G4",
                "gene",
                "D-SAME",
                "disease",
                source="one-circular-source",
            ),
            edge(
                "disease_associated_gene",
                "G5",
                "gene",
                "D-SAME",
                "disease",
                source="one-circular-source",
            ),
            edge(
                "disease_associated_gene",
                "X0",
                "gene",
                "D2",
                "disease",
                source="source-3",
            ),
            edge(
                "disease_associated_gene",
                "X1",
                "gene",
                "D2",
                "disease",
                source="source-4",
            ),
        ],
    )
    report = build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "pathway_associated_member_feature_v2",
            "pathway_disease_candidate_v2",
        )
    )
    features = read_output(
        tmp_path / "out",
        "pathway_associated_member",
        "pathway_associated_member_feature_v2",
        "derived_views",
    )
    candidate = read_output(
        tmp_path / "out", "disease_involves_pathway", "pathway_disease_candidate_v2"
    )
    assert set(features.associated_member_id) >= {"G1", "G2"}
    assert "G3" not in set(features.associated_member_id)
    assert set(
        zip(candidate.x_id, candidate.y_id, candidate.associated_member_count)
    ) == {("PW", "D", 2)}
    assert (
        report["rejection_reason_counts"]["pathway_disease_candidate_v2"][
            "pathway_fanout"
        ]
        == 1
    )
    assert (
        report["rejection_reason_counts"]["pathway_disease_candidate_v2"][
            "source_commonality_or_circularity"
        ]
        == 1
    )


def test_disease_phenotype_tissue_never_cartesian_products_unrelated_diseases(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "disease_has_phenotype",
        [
            edge(
                "disease_has_phenotype",
                "D1",
                "disease",
                "HP1",
                "phenotype",
                source="hpo-1",
            ),
            edge(
                "disease_has_phenotype",
                "D2",
                "disease",
                "HP2",
                "phenotype",
                source="hpo-2",
            ),
        ],
    )
    write(
        kg,
        "disease_manifests_in_tissue",
        [
            edge(
                "disease_manifests_in_tissue",
                "D1",
                "disease",
                "T1",
                "tissue",
                source="hpa-1",
            ),
            edge(
                "disease_manifests_in_tissue",
                "D2",
                "disease",
                "T2",
                "tissue",
                source="hpa-2",
            ),
        ],
    )
    write(
        kg,
        "phenotype_observed_in_tissue",
        [
            edge(
                "phenotype_observed_in_tissue",
                "T1",
                "tissue",
                "HP1",
                "phenotype",
                source="direct",
            )
        ],
    )
    build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "disease_phenotype_tissue_localization_v2",
            "disease_phenotype_tissue_triangle_v2",
        )
    )
    candidates = read_output(
        tmp_path / "out",
        "phenotype_observed_in_tissue",
        "disease_phenotype_tissue_localization_v2",
    )
    triangle = read_output(
        tmp_path / "out",
        "disease_phenotype_tissue_coherence",
        "disease_phenotype_tissue_triangle_v2",
        "derived_views",
    )
    # T1→HP1 is already observed and therefore absent from inferred output.
    assert set(zip(candidates.x_id, candidates.y_id)) == {("T2", "HP2")}
    assert "anchor_disease_id" not in candidates.columns
    candidate_evidence = read_output(
        tmp_path / "out",
        "phenotype_observed_in_tissue",
        "disease_phenotype_tissue_localization_v2",
        "evidence_inferred",
    )
    assert candidate_evidence.anchor_disease_id.tolist() == ["D2"]
    assert set(zip(triangle.x_id, triangle.y_id)) == {("T1", "HP1")}
    assert ("T1", "HP2") not in set(zip(candidates.x_id, candidates.y_id))
    assert ("T2", "HP1") not in set(zip(candidates.x_id, candidates.y_id))


def test_signed_pharmacology_and_strict_pgx_fail_closed(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "molecule_targets_gene",
        [
            edge(
                "molecule_targets_gene",
                "M1",
                "molecule",
                "G1",
                "gene",
                action_direction="inhibit",
                population="EUR",
            ),
            edge(
                "molecule_targets_gene",
                "M2",
                "molecule",
                "G2",
                "gene",
                action_direction="inhibit",
                population="EUR",
            ),
            edge(
                "molecule_targets_gene",
                "M3",
                "molecule",
                "G3",
                "gene",
                action_direction="conflicting",
                population="EUR",
            ),
            edge(
                "molecule_targets_gene",
                "M7",
                "molecule",
                "G7",
                "gene",
                action_direction="inhibit",
                population="EUR",
            ),
            edge(
                "molecule_targets_gene",
                "M8",
                "molecule",
                "G8",
                "gene",
                action_direction="inhibit",
            ),
        ],
    )
    write(
        kg,
        "disease_associated_gene",
        [
            edge(
                "disease_associated_gene",
                "G1",
                "gene",
                "D1",
                "disease",
                causal_mechanism="gain_of_function",
                effect_direction="risk",
                causal_support_level="causal",
                population="EUR",
            ),
            edge(
                "disease_associated_gene",
                "G2",
                "gene",
                "D2",
                "disease",
                causal_mechanism="loss_of_function",
                effect_direction="risk",
                causal_support_level="causal",
                population="EUR",
            ),
            edge(
                "disease_associated_gene",
                "G3",
                "gene",
                "D3",
                "disease",
                causal_mechanism="gain_of_function",
                effect_direction="risk",
                causal_support_level="causal",
                population="EUR",
            ),
            edge(
                "disease_associated_gene",
                "G7",
                "gene",
                "D7",
                "disease",
                causal_mechanism="gain_of_function",
                effect_direction="risk",
                causal_support_level="associative",
                population="EUR",
            ),
            edge(
                "disease_associated_gene",
                "G8",
                "gene",
                "D8",
                "disease",
                causal_mechanism="gain_of_function",
                effect_direction="risk",
                causal_support_level="causal",
            ),
        ],
    )
    write(
        kg,
        "mutation_associated_disease",
        [
            edge(
                "mutation_associated_disease",
                "V1",
                "mutation",
                "D4",
                "disease",
                population="EUR",
            ),
            edge(
                "mutation_associated_disease",
                "V2",
                "mutation",
                "D5",
                "disease",
                population="EUR",
            ),
            edge(
                "mutation_associated_disease",
                "V3",
                "mutation",
                "D6",
                "disease",
                population="EUR",
            ),
        ],
    )
    write(
        kg,
        "mutation_affects_molecule_response",
        [
            edge(
                "mutation_affects_molecule_response",
                "V1",
                "mutation",
                "M4",
                "molecule",
                response_category="efficacy",
                response_direction="sensitive",
                disease_context="D4",
                population="EUR",
            ),
            edge(
                "mutation_affects_molecule_response",
                "V2",
                "mutation",
                "M5",
                "molecule",
                response_category="toxicity",
                response_direction="sensitive",
                disease_context="D5",
                population="EUR",
            ),
            edge(
                "mutation_affects_molecule_response",
                "V3",
                "mutation",
                "M6",
                "molecule",
                response_category="efficacy",
                response_direction="conflicting",
                disease_context="D6",
                population="EUR",
            ),
        ],
    )
    report = build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "signed_gene_target_treatment_v2",
            "pharmacogenomic_efficacy_treatment_v2",
        )
    )
    signed = read_output(
        tmp_path / "out", "molecule_treats_disease", "signed_gene_target_treatment_v2"
    )
    pgx = read_output(
        tmp_path / "out",
        "molecule_treats_disease",
        "pharmacogenomic_efficacy_treatment_v2",
    )
    assert set(zip(signed.x_id, signed.y_id)) == {("M1", "D1")}
    assert set(zip(pgx.x_id, pgx.y_id)) == {("M4", "D4")}
    assert report["rejection_reason_counts"]["signed_gene_target_treatment_v2"] == {
        "conflicting_sign": 1,
        "missing_shared_context": 1,
        "noncausal_support": 1,
        "nontherapeutic_sign_product": 1,
    }
    assert (
        report["rejection_reason_counts"]["pharmacogenomic_efficacy_treatment_v2"][
            "toxicity"
        ]
        == 1
    )
    assert (
        report["rejection_reason_counts"]["pharmacogenomic_efficacy_treatment_v2"][
            "conflicting_direction_or_context"
        ]
        == 1
    )


def test_signed_protein_features_emit_treatment_and_contraindication_with_full_provenance(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "molecule_targets_protein",
        [
            edge(
                "molecule_targets_protein",
                "M-TREAT",
                "molecule",
                "P",
                "protein",
                action_direction='["negative"]',
                target_modulation='["decrease"]',
                action_types='["inhibitor", "antagonist"]',
                action_status="single",
                population="EUR",
                release="ChEMBL-35",
            ),
            edge(
                "molecule_targets_protein",
                "M-HARM",
                "molecule",
                "P",
                "protein",
                action_direction='["positive"]',
                target_modulation='["increase"]',
                action_types='["agonist"]',
                action_status="single",
                population="EUR",
                release="ChEMBL-35",
            ),
            edge(
                "molecule_targets_protein",
                "M-CONFLICT",
                "molecule",
                "P-CONFLICT",
                "protein",
                action_direction='["negative"]',
                target_modulation='["decrease"]',
                action_types='["inhibitor"]',
                action_status="single",
                population="EUR",
                release="ChEMBL-35",
            ),
            edge(
                "molecule_targets_protein",
                "M-NEGATIVE-DISEASE",
                "molecule",
                "P-NEGATIVE-DISEASE",
                "protein",
                action_direction='["positive"]',
                action_status="single",
                population="EUR",
                release="ChEMBL-35",
            ),
            edge(
                "molecule_targets_protein",
                "M-DISAGREE",
                "molecule",
                "P-DISAGREE",
                "protein",
                action_direction='["positive"]',
                action_status="single",
                population="EUR",
                release="ChEMBL-35",
            ),
        ],
    )
    write(
        kg,
        "disease_associated_protein",
        [
            edge(
                "disease_associated_protein",
                "P",
                "protein",
                "D",
                "disease",
                causal_mechanisms='["gain_of_function", "activation"]',
                mechanism_status="single",
                effect_directions='["risk", "positive"]',
                effect_direction_status="single",
                causal_support_level="causal",
                population="EUR",
                release_values=["UniProt-2026_03"],
            ),
            edge(
                "disease_associated_protein",
                "P-CONFLICT",
                "protein",
                "D-CONFLICT",
                "disease",
                causal_mechanisms='["gain_of_function"]',
                mechanism_status="conflicting",
                effect_directions='["risk"]',
                effect_direction_status="single",
                causal_support_level="causal",
                population="EUR",
                release_values=["UniProt-2026_03"],
            ),
            edge(
                "disease_associated_protein",
                "P-NEGATIVE-DISEASE",
                "protein",
                "D-NEGATIVE-DISEASE",
                "disease",
                causal_mechanisms='["loss_of_function"]',
                mechanism_status="single",
                effect_directions='["protective"]',
                effect_direction_status="single",
                causal_support_level="causal",
                population="EUR",
                release_values=["UniProt-2026_03"],
            ),
            edge(
                "disease_associated_protein",
                "P-DISAGREE",
                "protein",
                "D-DISAGREE",
                "disease",
                causal_mechanisms='["gain_of_function"]',
                mechanism_status="single",
                effect_directions='["protective"]',
                effect_direction_status="single",
                causal_support_level="causal",
                population="EUR",
                release_values=["UniProt-2026_03"],
            ),
        ],
    )

    report = build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "signed_protein_target_treatment_v2",
            "signed_protein_target_contraindication_v2",
        )
    )

    treatment = read_output(
        tmp_path / "out",
        "molecule_treats_disease",
        "signed_protein_target_treatment_v2",
    )
    contraindication = read_output(
        tmp_path / "out",
        "molecule_contraindicates_disease",
        "signed_protein_target_contraindication_v2",
    )
    assert set(zip(treatment.x_id, treatment.y_id)) == {
        ("M-TREAT", "D"),
        ("M-DISAGREE", "D-DISAGREE"),
    }
    assert set(zip(contraindication.x_id, contraindication.y_id)) == {
        ("M-HARM", "D"),
        ("M-NEGATIVE-DISEASE", "D-NEGATIVE-DISEASE"),
    }
    assert report["rejection_reason_counts"]["signed_protein_target_treatment_v2"][
        "conflicting_sign"
    ] == 1
    assert report["rejection_reason_counts"][
        "signed_protein_target_contraindication_v2"
    ]["conflicting_sign"] == 1
    evidence = read_output(
        tmp_path / "out",
        "molecule_contraindicates_disease",
        "signed_protein_target_contraindication_v2",
        "evidence_inferred",
    ).iloc[0]
    assert json.loads(evidence.source_releases) == ["ChEMBL-35", "UniProt-2026_03"]
    assert evidence.input_snapshot_sha256 == report["input_manifest_sha256"]
    assert evidence.context_compatibility == "compatible"
    assert json.loads(evidence.sign_computation) == {
        "action_sign": 1,
        "disease_mechanism_sign": 1,
        "effect_direction_sign": 1,
        "net_disease_sign": 1,
        "relation": "molecule_contraindicates_disease",
        "sign_product": 1,
    }
    assert evidence.conflict_state == "none"
    assert evidence.epistemic_class == "inferred_weak"
    assert not bool(evidence.canonical_observed_overlap)
    assert not bool(evidence.staged_source_native_overlap)


@pytest.mark.parametrize(
    ("action", "mechanism", "direction", "expected_relation"),
    [
        ("agonist", "gain_of_function", "risk", "molecule_contraindicates_disease"),
        ("agonist", "gain_of_function", "protective", "molecule_treats_disease"),
        ("agonist", "loss_of_function", "risk", "molecule_treats_disease"),
        (
            "agonist",
            "loss_of_function",
            "protective",
            "molecule_contraindicates_disease",
        ),
        ("inhibitor", "gain_of_function", "risk", "molecule_treats_disease"),
        (
            "inhibitor",
            "gain_of_function",
            "protective",
            "molecule_contraindicates_disease",
        ),
        (
            "inhibitor",
            "loss_of_function",
            "risk",
            "molecule_contraindicates_disease",
        ),
        ("inhibitor", "loss_of_function", "protective", "molecule_treats_disease"),
    ],
)
def test_signed_target_truth_table_composes_action_mechanism_and_disease_direction(
    tmp_path: Path,
    action: str,
    mechanism: str,
    direction: str,
    expected_relation: str,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "molecule_targets_gene",
        [
            edge(
                "molecule_targets_gene",
                "M",
                "molecule",
                "G",
                "gene",
                action_types=json.dumps([action]),
                action_status="single",
                population="EUR",
            )
        ],
    )
    write(
        kg,
        "disease_associated_gene",
        [
            edge(
                "disease_associated_gene",
                "G",
                "gene",
                "D",
                "disease",
                causal_mechanisms=json.dumps([mechanism]),
                mechanism_status="single",
                effect_directions=json.dumps([direction]),
                effect_direction_status="single",
                causal_support_level="causal",
                population="EUR",
            )
        ],
    )

    report = build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "signed_gene_target_treatment_v2",
            "signed_gene_target_contraindication_v2",
        )
    )

    expected_template = (
        "signed_gene_target_treatment_v2"
        if expected_relation == "molecule_treats_disease"
        else "signed_gene_target_contraindication_v2"
    )
    other_template = (
        "signed_gene_target_contraindication_v2"
        if expected_template == "signed_gene_target_treatment_v2"
        else "signed_gene_target_treatment_v2"
    )
    assert report["counts_by_template"][expected_template]["output_rows"] == 1
    assert report["counts_by_template"][other_template]["output_rows"] == 0
    evidence = read_output(
        tmp_path / "out", expected_relation, expected_template, "evidence_inferred"
    ).iloc[0]
    sign_computation = json.loads(evidence.sign_computation)
    assert sign_computation["sign_product"] == (
        -1 if expected_relation == "molecule_treats_disease" else 1
    )


@pytest.mark.parametrize(
    ("mechanism_status", "effect_status", "mechanisms", "directions"),
    [
        ("unknown", "single", "[]", '["risk"]'),
        ("single", "unknown", '["gain_of_function"]', "[]"),
        ("conflicting", "single", '["gain_of_function"]', '["risk"]'),
        ("single", "conflicting", '["gain_of_function"]', '["risk"]'),
        (
            "single",
            "single",
            '["gain_of_function", "loss_of_function"]',
            '["risk"]',
        ),
        ("single", "single", '["gain_of_function"]', '["risk", "protective"]'),
    ],
)
def test_signed_target_unknown_or_conflicting_operand_emits_no_claim(
    tmp_path: Path,
    mechanism_status: str,
    effect_status: str,
    mechanisms: str,
    directions: str,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "molecule_targets_gene",
        [
            edge(
                "molecule_targets_gene",
                "M",
                "molecule",
                "G",
                "gene",
                action_types='["agonist"]',
                action_status="single",
                population="EUR",
            )
        ],
    )
    write(
        kg,
        "disease_associated_gene",
        [
            edge(
                "disease_associated_gene",
                "G",
                "gene",
                "D",
                "disease",
                causal_mechanisms=mechanisms,
                mechanism_status=mechanism_status,
                effect_directions=directions,
                effect_direction_status=effect_status,
                causal_support_level="causal",
                population="EUR",
            )
        ],
    )

    report = build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "signed_gene_target_treatment_v2",
            "signed_gene_target_contraindication_v2",
        )
    )

    assert all(
        report["counts_by_template"][template]["output_rows"] == 0
        for template in (
            "signed_gene_target_treatment_v2",
            "signed_gene_target_contraindication_v2",
        )
    )


def test_sign_resolution_accepts_synonyms_but_fails_closed_on_unknown_or_opposite_tokens() -> None:
    assert composition._action_sign(
        {"action_types": '["inhibitor", "antagonist"]'}
    ) == ("known", -1)
    assert composition._action_sign(
        {"action_direction": "negative", "action_types": '["unmapped"]'}
    ) == ("unknown", None)
    assert composition._action_sign(
        {"action_types": '["inhibitor", "agonist"]'}
    ) == ("conflicting", None)
    assert composition._action_sign(
        {"action_types": '["inhibitor"]', "action_status": "unknown"}
    ) == ("unknown", None)
    assert composition._action_sign(
        {"action_types": '["inhibitor"]', "action_status": "conflicting"}
    ) == ("conflicting", None)

    status, sign, _ = composition._disease_sign(
        {
            "causal_mechanisms": '["gain_of_function", "unmapped"]',
            "effect_directions": '["risk"]',
        }
    )
    assert (status, sign) == ("unknown", None)
    status, sign, _ = composition._disease_sign(
        {
            "causal_mechanisms": "[]",
            "mechanism_status": "unknown",
            "effect_directions": '["risk"]',
        }
    )
    assert (status, sign) == ("unknown", None)
    status, sign, _ = composition._disease_sign(
        {"causal_mechanisms": '["gain_of_function"]'}
    )
    assert (status, sign) == ("unknown", None)
    status, sign, _ = composition._disease_sign({"effect_directions": '["risk"]'})
    assert (status, sign) == ("unknown", None)


def test_parent_shaped_unknown_disease_sign_reports_ten_rejected_paths(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "molecule_targets_protein",
        [
            edge(
                "molecule_targets_protein",
                f"M{i:02d}",
                "molecule",
                "P",
                "protein",
                action_direction='["negative"]',
                action_status="single",
                release="ChEMBL-35",
            )
            for i in range(10)
        ],
    )
    write(
        kg,
        "disease_associated_protein",
        [
            edge(
                "disease_associated_protein",
                "P",
                "protein",
                "D",
                "disease",
                causal_mechanisms="[]",
                mechanism_status="unknown",
                effect_directions="[]",
                effect_direction_status="unknown",
                causal_support_level="source_backed_disease_assertion",
                release="uniprot-2026_03",
            )
        ],
    )

    report = build_composition_allowlist(
        config(kg, tmp_path / "out", "signed_protein_target_treatment_v2")
    )

    rejected = report["rejected_path_samples"][
        "signed_protein_target_treatment_v2"
    ]
    assert len(rejected) == 10
    assert {row["reason"] for row in rejected} == {"missing_sign_or_causal_support"}
    assert all(row["decision"] == "rejected" for row in rejected)
    assert all(row["classification"] == "plausible hypothesis" for row in rejected)
    assert all("M" in row["human_readable_path"] for row in rejected)
    assert all(json.loads(row["typed_path"]) for row in rejected)
    assert report["counts_by_template"]["signed_protein_target_treatment_v2"][
        "output_rows"
    ] == 0


def test_allelic_triangulation_rejects_containment_and_requires_three_known_signs(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "molecule_targets_gene",
        [
            edge(
                "molecule_targets_gene",
                "M",
                "molecule",
                "G",
                "gene",
                action_direction="inhibit",
            )
        ],
    )
    write(
        kg,
        "mutation_associated_gene",
        [
            edge(
                "mutation_associated_gene",
                "V1",
                "mutation",
                "G",
                "gene",
                functional_mechanism="gain_of_function",
                attribution_mode="exact_protein_consequence",
            ),
            edge(
                "mutation_associated_gene",
                "V2",
                "mutation",
                "G",
                "gene",
                functional_mechanism="gain_of_function",
                attribution_mode="containment",
            ),
        ],
    )
    write(
        kg,
        "mutation_associated_disease",
        [
            edge(
                "mutation_associated_disease",
                "V1",
                "mutation",
                "D1",
                "disease",
                effect_direction="risk",
            ),
            edge(
                "mutation_associated_disease",
                "V2",
                "mutation",
                "D2",
                "disease",
                effect_direction="risk",
            ),
        ],
    )
    report = build_composition_allowlist(
        config(kg, tmp_path / "out", "allelic_triangulation_treatment_v2")
    )
    rows = read_output(
        tmp_path / "out",
        "molecule_treats_disease",
        "allelic_triangulation_treatment_v2",
    )
    assert set(zip(rows.x_id, rows.y_id)) == {("M", "D1")}
    assert "supporting_mutation_id" not in rows.columns
    evidence_rows = read_output(
        tmp_path / "out",
        "molecule_treats_disease",
        "allelic_triangulation_treatment_v2",
        "evidence_inferred",
    )
    assert evidence_rows.supporting_mutation_id.tolist() == ["V1"]
    assert (
        report["rejection_reason_counts"]["allelic_triangulation_treatment_v2"][
            "containment_or_weak_attribution"
        ]
        == 1
    )


def test_observed_and_staged_target_antijoins_remove_candidates(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    staged = tmp_path / "staged"
    write(
        kg,
        "mutation_affects_transcript",
        [
            edge("mutation_affects_transcript", "V1", "mutation", "TX1", "transcript"),
            edge("mutation_affects_transcript", "V2", "mutation", "TX2", "transcript"),
            edge("mutation_affects_transcript", "V3", "mutation", "TX3", "transcript"),
        ],
    )
    write(
        kg,
        "gene_has_transcript",
        [
            edge("gene_has_transcript", "G1", "gene", "TX1", "transcript"),
            edge("gene_has_transcript", "G2", "gene", "TX2", "transcript"),
            edge("gene_has_transcript", "G3", "gene", "TX3", "transcript"),
        ],
    )
    write(
        kg,
        "mutation_associated_gene",
        [edge("mutation_associated_gene", "V1", "mutation", "G1", "gene")],
    )
    write(
        staged,
        "mutation_associated_gene",
        [edge("mutation_associated_gene", "V2", "mutation", "G2", "gene")],
    )
    report = build_composition_allowlist(
        config(
            kg,
            tmp_path / "out",
            "mutation_transcript_gene_attribution_v2",
            staged=(staged,),
        )
    )
    rows = read_output(
        tmp_path / "out",
        "mutation_associated_gene",
        "mutation_transcript_gene_attribution_v2",
    )
    assert set(zip(rows.x_id, rows.y_id)) == {("V3", "G3")}
    rejects = report["rejection_reason_counts"][
        "mutation_transcript_gene_attribution_v2"
    ]
    assert rejects["canonical_observed_overlap"] == 1
    assert rejects["staged_source_native_overlap"] == 1


def test_missing_canonical_target_inventory_fails_closed_but_reports_generated_sample(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "mutation_affects_transcript",
        [edge("mutation_affects_transcript", "V", "mutation", "TX", "transcript")],
    )
    write(
        kg,
        "gene_has_transcript",
        [edge("gene_has_transcript", "G", "gene", "TX", "transcript")],
    )
    strict = replace(
        config(kg, tmp_path / "out", "mutation_transcript_gene_attribution_v2"),
        require_canonical_target_inventory=True,
    )
    report = build_composition_allowlist(strict)
    counts = report["counts_by_template"]["mutation_transcript_gene_attribution_v2"]
    assert counts == {
        "generated_paths_before_antijoin": 1,
        "output_rows": 0,
        "epistemic_class": "inferred_obvious",
        "output_class": "inferred_edge",
    }
    assert (
        report["rejection_reason_counts"]["mutation_transcript_gene_attribution_v2"][
            "canonical_target_inventory_missing"
        ]
        == 1
    )
    assert (
        report["generated_path_samples_before_antijoin"][
            "mutation_transcript_gene_attribution_v2"
        ][0]["x_id"]
        == "V"
    )
    assert not report["generated_path_samples_before_antijoin"][
        "mutation_transcript_gene_attribution_v2"
    ][0]["canonical_target_inventory_available"]
    assert not list((tmp_path / "out" / "edges_inferred").rglob("*.parquet"))


def test_legacy_contraindication_edges_without_evidence_are_not_a_complete_inventory(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "molecule_targets_protein",
        [
            edge(
                "molecule_targets_protein",
                "M",
                "molecule",
                "P",
                "protein",
                action_direction="positive",
                action_status="single",
                population="EUR",
            )
        ],
    )
    write(
        kg,
        "disease_associated_protein",
        [
            edge(
                "disease_associated_protein",
                "P",
                "protein",
                "D",
                "disease",
                causal_mechanisms='["gain_of_function"]',
                mechanism_status="single",
                effect_directions='["risk"]',
                effect_direction_status="single",
                causal_support_level="causal",
                population="EUR",
            )
        ],
    )
    write(
        kg,
        "molecule_contraindicates_disease",
        [
            edge(
                "molecule_contraindicates_disease",
                "LEGACY",
                "molecule",
                "OTHER",
                "disease",
            )
        ],
    )
    strict = replace(
        config(kg, tmp_path / "out", "signed_protein_target_contraindication_v2"),
        require_canonical_target_inventory=True,
    )

    report = build_composition_allowlist(strict)

    assert report["rejection_reason_counts"][
        "signed_protein_target_contraindication_v2"
    ]["canonical_target_inventory_missing"] == 1
    assert report["counts_by_template"][
        "signed_protein_target_contraindication_v2"
    ]["output_rows"] == 0
    assert not list((tmp_path / "out" / "edges_inferred").rglob("*.parquet"))


def _write_signed_contraindication_fixture(kg: Path) -> None:
    write(
        kg,
        "molecule_targets_protein",
        [
            edge(
                "molecule_targets_protein",
                "M-CANDIDATE",
                "molecule",
                "P-CANDIDATE",
                "protein",
                action_direction="positive",
                action_status="single",
                population="EUR",
            )
        ],
    )
    write(
        kg,
        "disease_associated_protein",
        [
            edge(
                "disease_associated_protein",
                "P-CANDIDATE",
                "protein",
                "D-CANDIDATE",
                "disease",
                causal_mechanisms='["gain_of_function"]',
                mechanism_status="single",
                effect_directions='["risk"]',
                effect_direction_status="single",
                causal_support_level="causal",
                population="EUR",
            )
        ],
    )
    write(
        kg,
        "molecule_contraindicates_disease",
        [
            edge(
                "molecule_contraindicates_disease",
                "M-OBSERVED-1",
                "molecule",
                "D-OBSERVED-1",
                "disease",
            ),
            edge(
                "molecule_contraindicates_disease",
                "M-OBSERVED-2",
                "molecule",
                "D-OBSERVED-2",
                "disease",
            ),
        ],
    )


@pytest.mark.parametrize(
    "invalid_inventory",
    [
        "absent_receipt",
        "empty_evidence",
        "unrelated_evidence",
        "partial_evidence",
        "stale_receipt",
        "source_identity_mismatch",
        "malformed_receipt",
        "receipt_hash_mismatch",
        "accepted_hash_mismatch",
        "evidence_hash_mismatch",
    ],
)
def test_strict_contraindication_inventory_receipt_fails_closed(
    tmp_path: Path, invalid_inventory: str
) -> None:
    kg = tmp_path / "kg"
    _write_signed_contraindication_fixture(kg)
    relation = "molecule_contraindicates_disease"
    canonical_rows = [
        edge(relation, "M-OBSERVED-1", "molecule", "D-OBSERVED-1", "disease"),
        edge(relation, "M-OBSERVED-2", "molecule", "D-OBSERVED-2", "disease"),
    ]
    if invalid_inventory == "empty_evidence":
        evidence = pd.DataFrame(columns=canonical_rows[0])
        evidence_path = kg / "evidence" / f"{relation}.parquet"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence.to_parquet(evidence_path, index=False)
        receipt_path = write_inventory_receipt(kg, relation)
    else:
        evidence_rows = canonical_rows
        if invalid_inventory == "unrelated_evidence":
            evidence_rows = [
                edge(relation, "M-OTHER", "molecule", "D-OTHER", "disease")
            ]
        elif invalid_inventory == "partial_evidence":
            evidence_rows = canonical_rows[:1]
        write(kg, relation, evidence_rows, layer="evidence")
        receipt_path = (
            None
            if invalid_inventory == "absent_receipt"
            else write_inventory_receipt(
                kg,
                relation,
                snapshot_id=(
                    "stale-fixture-v0"
                    if invalid_inventory == "stale_receipt"
                    else "immutable-fixture-v1"
                ),
                source_identity=(
                    "stale-source-revision"
                    if invalid_inventory == "source_identity_mismatch"
                    else "canonical-fixture-source-v1"
                ),
            )
        )
    accepted_receipt_sha256 = (
        json.loads(receipt_path.read_text())["receipt_sha256"]
        if receipt_path is not None
        else "0" * 64
    )
    if invalid_inventory == "accepted_hash_mismatch":
        accepted_receipt_sha256 = "0" * 64
    if invalid_inventory == "malformed_receipt":
        assert receipt_path is not None
        receipt_path.write_text("{not-json\n")
    elif invalid_inventory == "receipt_hash_mismatch":
        assert receipt_path is not None
        receipt = json.loads(receipt_path.read_text())
        receipt["receipt_sha256"] = "0" * 64
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    elif invalid_inventory == "evidence_hash_mismatch":
        assert receipt_path is not None
        changed_rows = [{**row, "source": "changed-after-receipt"} for row in canonical_rows]
        write(kg, relation, changed_rows, layer="evidence")

    report = build_composition_allowlist(
        replace(
            config(kg, tmp_path / "out", "signed_protein_target_contraindication_v2"),
            require_canonical_target_inventory=True,
            canonical_target_inventory_receipt_sha256=accepted_receipt_sha256,
        )
    )

    assert report["rejection_reason_counts"][
        "signed_protein_target_contraindication_v2"
    ]["canonical_target_inventory_missing"] == 1
    assert report["counts_by_template"][
        "signed_protein_target_contraindication_v2"
    ]["output_rows"] == 0
    assert not list((tmp_path / "out" / "edges_inferred").rglob("*.parquet"))


def test_strict_contraindication_inventory_accepts_exact_complete_receipt(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    _write_signed_contraindication_fixture(kg)
    relation = "molecule_contraindicates_disease"
    canonical_rows = [
        edge(relation, "M-OBSERVED-1", "molecule", "D-OBSERVED-1", "disease"),
        edge(relation, "M-OBSERVED-2", "molecule", "D-OBSERVED-2", "disease"),
    ]
    write(kg, relation, canonical_rows, layer="evidence")
    receipt_path = write_inventory_receipt(kg, relation)

    report = build_composition_allowlist(
        replace(
            config(kg, tmp_path / "out", "signed_protein_target_contraindication_v2"),
            require_canonical_target_inventory=True,
            canonical_target_inventory_receipt_sha256=json.loads(
                receipt_path.read_text()
            )["receipt_sha256"],
        )
    )

    assert report["rejection_reason_counts"][
        "signed_protein_target_contraindication_v2"
    ].get("canonical_target_inventory_missing", 0) == 0
    rows = read_output(
        tmp_path / "out",
        relation,
        "signed_protein_target_contraindication_v2",
    )
    assert set(zip(rows.x_id, rows.y_id)) == {("M-CANDIDATE", "D-CANDIDATE")}
    evidence = read_output(
        tmp_path / "out",
        relation,
        "signed_protein_target_contraindication_v2",
        "evidence_inferred",
    )
    assert evidence.loc[0, "canonical_target_inventory_receipt_sha256"] == json.loads(
        receipt_path.read_text()
    )["receipt_sha256"]


def test_zero_rerun_removes_stale_pair_and_deterministic_hashes_ignore_wall_clock(
    tmp_path: Path,
) -> None:
    populated = tmp_path / "populated"
    empty = tmp_path / "empty"
    out = tmp_path / "out"
    write(
        populated,
        "mutation_affects_transcript",
        [edge("mutation_affects_transcript", "V", "mutation", "TX", "transcript")],
    )
    write(
        populated,
        "gene_has_transcript",
        [edge("gene_has_transcript", "G", "gene", "TX", "transcript")],
    )
    write(
        empty,
        "mutation_affects_transcript",
        [edge("mutation_affects_transcript", "OTHER", "mutation", "NO", "transcript")],
    )
    write(
        empty,
        "gene_has_transcript",
        [edge("gene_has_transcript", "G", "gene", "TX", "transcript")],
    )
    first = build_composition_allowlist(
        config(populated, out, "mutation_transcript_gene_attribution_v2")
    )
    original = read_output(
        out, "mutation_associated_gene", "mutation_transcript_gene_attribution_v2"
    )
    second_out = tmp_path / "out2"
    build_composition_allowlist(
        config(populated, second_out, "mutation_transcript_gene_attribution_v2")
    )
    first_report = (out / "manifest" / "pilot_report.json").read_bytes()
    repeated_report = (second_out / "manifest" / "pilot_report.json").read_bytes()
    assert b'"created_at"' not in first_report
    first_report_payload = json.loads(first_report)
    repeated_report_payload = json.loads(repeated_report)
    first_report_payload.pop("artifacts")
    repeated_report_payload.pop("artifacts")
    assert first_report_payload == repeated_report_payload
    repeated = read_output(
        second_out,
        "mutation_associated_gene",
        "mutation_transcript_gene_attribution_v2",
    )
    assert original.derivation_hash.tolist() == repeated.derivation_hash.tolist()
    assert (
        first["input_manifest_sha256"]
        == json.loads((out / "manifest" / "input_manifest.json").read_text())[
            "manifest_sha256"
        ]
    )
    second = build_composition_allowlist(
        config(empty, out, "mutation_transcript_gene_attribution_v2")
    )
    assert (
        second["counts_by_template"]["mutation_transcript_gene_attribution_v2"][
            "output_rows"
        ]
        == 0
    )
    assert not list(out.rglob("mutation_transcript_gene_attribution_v2.parquet"))


def test_c3_and_generic_response_stale_artifacts_are_deleted_and_never_registered(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    out = tmp_path / "out"
    stale = [
        out
        / "edges_inferred"
        / "disease_associated_gene"
        / "c3_variant_enhancer_gene_disease.parquet",
        out
        / "evidence_inferred"
        / "disease_associated_gene"
        / "variant_enhancer_gene_disease_v1.parquet",
        out / "derived_views" / "response" / "generic_cell_response_phenotype.parquet",
        out
        / "derived_views_evidence"
        / "response"
        / "generic_cell_response_phenotype.parquet",
    ]
    for path in stale:
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{"stale": True}]).to_parquet(path, index=False)
    report = build_composition_allowlist(
        config(kg, out, "mutation_transcript_gene_attribution_v2")
    )
    assert all(not path.exists() for path in stale)
    assert "c3_variant_enhancer_gene_disease" not in TEMPLATE_BY_ID
    assert "generic_cell_response_phenotype" not in TEMPLATE_BY_ID
    assert (
        report["counts_by_template"]["mutation_transcript_gene_attribution_v2"][
            "output_rows"
        ]
        == 0
    )


def test_manifest_is_fresh_hashed_and_policy_revision_is_pinned(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "mutation_affects_transcript",
        [edge("mutation_affects_transcript", "V", "mutation", "TX", "transcript")],
    )
    write(
        kg,
        "gene_has_transcript",
        [edge("gene_has_transcript", "G", "gene", "TX", "transcript")],
    )
    out = tmp_path / "out"
    build_composition_allowlist(
        config(kg, out, "mutation_transcript_gene_attribution_v2")
    )
    manifest = json.loads((out / "manifest" / "input_manifest.json").read_text())
    assert manifest["snapshot_id"] == "immutable-fixture-v1"
    assert len(manifest["files"]) == 2
    for path, metadata in manifest["files"].items():
        assert metadata["sha256"] == hashlib.sha256(Path(path).read_bytes()).hexdigest()
        assert metadata["rows"] == 1
        assert metadata["columns"]
    bad = config(kg, tmp_path / "bad", "mutation_transcript_gene_attribution_v2")
    bad = BuildConfig(**{**bad.__dict__, "producer_revision": "wrong"})
    with pytest.raises(ValueError, match="approved policy revision"):
        build_composition_allowlist(bad)


def test_cli_and_all_templates_honestly_emit_zero_when_prerequisites_are_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import build_relation_composition_allowlist

    kg = tmp_path / "empty-immutable-snapshot"
    kg.mkdir()
    out = tmp_path / "out"
    assert (
        build_relation_composition_allowlist.main(
            [
                "--input-root",
                str(kg),
                "--output-root",
                str(out),
                "--snapshot-id",
                "immutable-empty",
                "--max-rows-per-file",
                "10",
                "--max-paths-per-template",
                "10",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert len(report["counts_by_template"]) == len(TEMPLATES)
    assert all(
        entry["output_rows"] == 0 for entry in report["counts_by_template"].values()
    )
    assert (
        not list((out / "edges_inferred").rglob("*.parquet"))
        if (out / "edges_inferred").exists()
        else True
    )
    assert (
        not list((out / "derived_views").rglob("*.parquet"))
        if (out / "derived_views").exists()
        else True
    )
    assert report["policy_revision"] == POLICY_REVISION


def test_input_mutation_aborts_before_any_output_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kg = tmp_path / "kg"
    out = tmp_path / "out"
    write(
        kg,
        "mutation_affects_transcript",
        [
            edge(
                "mutation_affects_transcript",
                "V",
                "mutation",
                "TR",
                "transcript",
                consequence="missense_variant",
                assembly="GRCh38",
            )
        ],
    )
    write(
        kg,
        "gene_has_transcript",
        [
            edge(
                "gene_has_transcript",
                "G",
                "gene",
                "TR",
                "transcript",
                assembly="GRCh38",
            )
        ],
    )
    edge_path = (
        out
        / "edges_inferred"
        / "mutation_associated_gene"
        / "mutation_transcript_gene_attribution_v2.parquet"
    )
    evidence_path = (
        out
        / "evidence_inferred"
        / "mutation_associated_gene"
        / "mutation_transcript_gene_attribution_v2.parquet"
    )
    for path, payload in ((edge_path, b"old-edge"), (evidence_path, b"old-evidence")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    original_file_sha = composition._file_sha
    calls: dict[Path, int] = {}

    def mutating_file_sha(path: Path) -> str:
        resolved = path.resolve()
        calls[resolved] = calls.get(resolved, 0) + 1
        digest = original_file_sha(path)
        if calls[resolved] > 1 and path.name == "mutation_affects_transcript.parquet":
            return "0" * 64
        return digest

    monkeypatch.setattr(composition, "_file_sha", mutating_file_sha)
    with pytest.raises(RuntimeError, match="input changed during build"):
        build_composition_allowlist(
            config(kg, out, "mutation_transcript_gene_attribution_v2")
        )
    assert edge_path.read_bytes() == b"old-edge"
    assert evidence_path.read_bytes() == b"old-evidence"


def test_atomic_tree_publication_restores_previous_output_on_swap_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kg = tmp_path / "kg"
    kg.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    marker = out / "previous-output.marker"
    marker.write_text("preserve-me\n")
    original_replace = composition.os.replace
    failed = False

    def fail_new_tree_swap(source: str | Path, destination: str | Path) -> None:
        nonlocal failed
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            not failed
            and source_path.name.startswith(".out.tmp-")
            and destination_path.resolve() == out.resolve()
        ):
            failed = True
            raise OSError("injected output-tree swap failure")
        original_replace(source, destination)

    monkeypatch.setattr(composition.os, "replace", fail_new_tree_swap)
    with pytest.raises(OSError, match="injected output-tree swap failure"):
        build_composition_allowlist(
            config(kg, out, "mutation_transcript_gene_attribution_v2")
        )
    assert marker.read_text() == "preserve-me\n"
    assert not (out / "manifest").exists()


def test_edge_summary_cannot_mask_conflicting_evidence_pathogenicity() -> None:
    summary = edge(
        "mutation_associated_disease",
        "V",
        "mutation",
        "D",
        "disease",
        clinical_significance="pathogenic",
        pathogenicity="pathogenic",
    )
    evidence = [
        edge(
            "mutation_associated_disease",
            "V",
            "mutation",
            "D",
            "disease",
            evidence_key="evidence-1",
            clinical_significance="benign",
            pathogenicity="likely_benign",
        )
    ]

    merged = composition._with_evidence(summary, evidence)

    assert merged["clinical_significance"] == "pathogenic"
    assert merged["clinical_significance_status"] == "conflicting"
    assert merged["clinical_significance_values"] == ["benign", "pathogenic"]
    assert merged["pathogenicity"] == "pathogenic"
    assert merged["pathogenicity_status"] == "conflicting"
    assert merged["pathogenicity_values"] == ["likely_benign", "pathogenic"]


def test_edge_evidence_pathogenicity_conflict_emits_zero_disease_candidates(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    write(
        kg,
        "mutation_causes_protein_change",
        [
            edge(
                "mutation_causes_protein_change",
                "V",
                "mutation",
                "P",
                "protein",
            )
        ],
    )
    write(
        kg,
        "mutation_associated_disease",
        [
            edge(
                "mutation_associated_disease",
                "V",
                "mutation",
                "D",
                "disease",
                clinical_significance="pathogenic",
            )
        ],
    )
    write(
        kg,
        "mutation_associated_disease",
        [
            edge(
                "mutation_associated_disease",
                "V",
                "mutation",
                "D",
                "disease",
                evidence_key="evidence-benign",
                clinical_significance="benign",
            )
        ],
        layer="evidence",
    )

    report = build_composition_allowlist(
        config(kg, tmp_path / "out", "mutation_protein_disease_candidate_v2")
    )

    assert report["counts_by_template"]["mutation_protein_disease_candidate_v2"][
        "output_rows"
    ] == 0
    assert report["rejection_reason_counts"][
        "mutation_protein_disease_candidate_v2"
    ] == {"conflicting_pathogenicity": 1}
    assert not list((tmp_path / "out").rglob("*.parquet"))


def test_mutation_disease_candidates_require_allowlisted_pathogenic_or_reviewed_causal_support(
    tmp_path: Path,
) -> None:
    kg = tmp_path / "kg"
    variants = {
        "PATH": {"clinical_significance": "pathogenic"},
        "LIKELY": {"pathogenicity": "likely-pathogenic"},
        "REVIEWED": {"disease_support": "reviewed_causal"},
        "BENIGN": {"clinical_significance": "benign"},
        "LIKELY_BENIGN": {"pathogenicity": "likely_benign"},
        "ASSOCIATIVE": {"disease_support": "associative"},
        "GENERIC": {"disease_support": "association"},
        "UNREVIEWED_CAUSAL": {"disease_support": "causal"},
        "UNCERTAIN": {"clinical_significance": "uncertain significance"},
        "UNKNOWN": {"clinical_significance": "unknown"},
        "CONFLICT": {
            "clinical_significance": "pathogenic",
            "clinical_significance_status": "conflicting",
        },
    }
    write(
        kg,
        "mutation_causes_protein_change",
        [
            edge(
                "mutation_causes_protein_change",
                variant,
                "mutation",
                f"P-{variant}",
                "protein",
            )
            for variant in variants
        ],
    )
    write(
        kg,
        "mutation_associated_disease",
        [
            edge(
                "mutation_associated_disease",
                variant,
                "mutation",
                f"D-{variant}",
                "disease",
                **support,
            )
            for variant, support in variants.items()
        ],
    )

    report = build_composition_allowlist(
        config(kg, tmp_path / "out", "mutation_protein_disease_candidate_v2")
    )

    rows = read_output(
        tmp_path / "out",
        "disease_associated_protein",
        "mutation_protein_disease_candidate_v2",
    )
    assert set(rows.y_id) == {"D-PATH", "D-LIKELY", "D-REVIEWED"}
    assert report["rejection_reason_counts"][
        "mutation_protein_disease_candidate_v2"
    ] == {
        "conflicting_pathogenicity": 1,
        "non_pathogenic_benign": 1,
        "non_pathogenic_likely_benign": 1,
        "noncausal_associative_support": 1,
        "noncausal_generic_support": 1,
        "nonallowlisted_disease_support_causal": 1,
        "nonallowlisted_disease_support_uncertain_significance": 1,
        "unknown_pathogenicity": 1,
    }


@pytest.mark.parametrize("unsafe_root", ["primary", "staged"])
@pytest.mark.parametrize("layout", ["output_ancestor", "output_descendant"])
def test_overlapping_output_and_immutable_input_fail_before_load_and_preserve_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_root: str,
    layout: str,
) -> None:
    overlap_root = tmp_path / "overlap"
    if layout == "output_ancestor":
        output_root = overlap_root
        unsafe_input = overlap_root / "immutable-input"
    else:
        unsafe_input = overlap_root
        output_root = overlap_root / "output"
    primary = unsafe_input if unsafe_root == "primary" else tmp_path / "primary"
    staged = unsafe_input if unsafe_root == "staged" else tmp_path / "staged"
    snapshot_root = primary if unsafe_root == "primary" else staged
    write(
        snapshot_root,
        "mutation_affects_transcript",
        [edge("mutation_affects_transcript", "V", "mutation", "TX", "transcript")],
    )
    snapshot = {
        path.relative_to(snapshot_root): path.read_bytes()
        for path in snapshot_root.rglob("*")
        if path.is_file()
    }
    load_called = False

    def unexpected_load(*args: object, **kwargs: object) -> None:
        nonlocal load_called
        load_called = True
        raise AssertionError("unsafe layout reached input loading")

    monkeypatch.setattr(composition, "_load", unexpected_load)
    unsafe_staged = (staged,) if unsafe_root == "staged" else ()
    with pytest.raises(ValueError, match="disjoint from immutable input roots"):
        build_composition_allowlist(
            config(
                primary,
                output_root,
                "mutation_transcript_gene_attribution_v2",
                staged=unsafe_staged,
            )
        )

    assert not load_called
    assert {
        path.relative_to(snapshot_root): path.read_bytes()
        for path in snapshot_root.rglob("*")
        if path.is_file()
    } == snapshot
