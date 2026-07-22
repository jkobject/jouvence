from __future__ import annotations

import importlib
import importlib.util
import json
import os
from pathlib import Path

import pandas as pd
import pytest


def _operand_module():
    name = "manage_db.materialize_disease_causal_operands"
    assert importlib.util.find_spec(name) is not None, "disease operand materializer is not implemented"
    return importlib.import_module(name)


def test_uniprot_explicit_gain_of_function_causal_phrase_emits_separate_operands() -> None:
    operands = _operand_module().normalize_disease_operand_assertion(
        {
            "source": "UniProtKB",
            "source_dataset": "reviewed_human_disease_comments",
            "source_record_id": "P00749:DISEASE:OMIM:601709",
            "release": "2026_02",
            "x_id": "ENSP00000361850",
            "y_id": "MONDO:0011136",
            "uniprot_accession": "P00749",
            "isoform": "canonical",
            "disease_source_id": "OMIM:601709",
            "disease_description": (
                "An autosomal dominant bleeding disorder due to a gain-of-function "
                "defect in fibrinolysis."
            ),
            "mapping_confidence": (
                "exact_uniprot_accession_to_existing_protein_node;"
                "exact_disease_xref_to_existing_disease_node"
            ),
            "mapping_method": "nodes/protein.uniprot_id and nodes/disease xref columns",
        }
    )

    assert operands["mechanism_operand"] == "gain_of_function"
    assert operands["disease_direction_operand"] == "risk"
    assert operands["operand_support_class"] == "explicit_uniprot_disease_causal_phrase"
    assert operands["operand_confidence"] == "direct_explicit"


def test_humsavar_pathogenic_variant_emits_risk_but_not_mechanism() -> None:
    operands = _operand_module().normalize_disease_operand_assertion(
        {
            "source": "UniProtKB/humsavar",
            "source_dataset": "humsavar_missense_variants",
            "source_record_id": "VAR_000001",
            "release": "2026_02 of 10-Jun-2026",
            "x_id": "ENSP00000000001",
            "y_id": "MONDO:0000001",
            "uniprot_accession": "P00001",
            "isoform": "canonical",
            "disease_source_id": "OMIM:000001",
            "variant_ft_id": "VAR_000001",
            "variant_category": "LP/P",
            "aa_change": "p.Gly1Arg",
            "mapping_confidence": (
                "exact_uniprot_accession_to_existing_protein_node;"
                "exact_disease_xref_to_existing_disease_node"
            ),
        }
    )

    assert operands["mechanism_operand"] == ""
    assert operands["disease_direction_operand"] == "risk"
    assert operands["operand_support_class"] == "explicit_humsavar_pathogenic_variant_disease"
    assert operands["operand_confidence"] == "direct_explicit"


def test_humsavar_uncertain_or_benign_categories_do_not_become_protective_or_mechanistic() -> None:
    normalize = _operand_module().normalize_disease_operand_assertion
    base = {
        "source": "UniProtKB/humsavar",
        "source_dataset": "humsavar_missense_variants",
        "source_record_id": "VAR_000001",
        "release": "2026_02",
        "x_id": "ENSP1",
        "y_id": "MONDO:1",
        "uniprot_accession": "P1",
        "isoform": "canonical",
        "disease_source_id": "OMIM:1",
        "variant_ft_id": "VAR_000001",
        "aa_change": "p.Gly1Arg",
        "mapping_confidence": (
            "exact_uniprot_accession_to_existing_protein_node;"
            "exact_disease_xref_to_existing_disease_node"
        ),
    }

    for category in ("US", "LB/B"):
        operands = normalize({**base, "variant_category": category})
        assert operands["mechanism_operand"] == ""
        assert operands["disease_direction_operand"] == ""
        assert operands["operand_support_class"] == "unusable"


def test_pathogenicity_consequence_and_generic_text_never_imply_gof_or_lof() -> None:
    operands = _operand_module().normalize_disease_operand_assertion(
        {
            "source": "UniProtKB/humsavar",
            "source_dataset": "humsavar_missense_variants",
            "source_record_id": "VAR_2",
            "release": "2026_02",
            "x_id": "ENSP2",
            "y_id": "MONDO:2",
            "uniprot_accession": "P2",
            "isoform": "canonical",
            "disease_source_id": "OMIM:2",
            "variant_ft_id": "VAR_2",
            "variant_category": "LP/P",
            "aa_change": "p.Trp2Ter",
            "text_span": "pathogenic stop gained loss of protein",
            "mapping_confidence": (
                "exact_uniprot_accession_to_existing_protein_node;"
                "exact_disease_xref_to_existing_disease_node"
            ),
        }
    )

    assert operands["mechanism_operand"] == ""
    assert operands["disease_direction_operand"] == "risk"


def test_ambiguous_or_incomplete_mapping_fails_closed() -> None:
    normalize = _operand_module().normalize_disease_operand_assertion
    valid = {
        "source": "UniProtKB/humsavar",
        "source_dataset": "humsavar_missense_variants",
        "source_record_id": "VAR_3",
        "release": "2026_02",
        "x_id": "ENSP3",
        "y_id": "MONDO:3",
        "uniprot_accession": "P3",
        "isoform": "canonical",
        "disease_source_id": "OMIM:3",
        "variant_ft_id": "VAR_3",
        "variant_category": "LP/P",
        "aa_change": "p.Gly3Arg",
        "mapping_confidence": (
            "exact_uniprot_accession_to_existing_protein_node;"
            "exact_disease_xref_to_existing_disease_node"
        ),
    }
    cases = [
        {**valid, "variant_ft_id": ""},
        {**valid, "disease_source_id": ""},
        {**valid, "isoform": "P3-1|P3-2"},
        {**valid, "mapping_confidence": "nearest_gene_only"},
    ]

    for row in cases:
        operands = normalize(row)
        assert operands["mechanism_operand"] == ""
        assert operands["disease_direction_operand"] == ""
        assert operands["reject_reason"] in {
            "missing_exact_variant_identity",
            "missing_disease_context",
            "mixed_or_noncanonical_isoform",
            "ambiguous_or_inexact_mapping",
        }


def test_opentargets_l2g_or_generic_eva_assertions_are_not_laundered_into_operands() -> None:
    normalize = _operand_module().normalize_disease_operand_assertion
    for dataset in ("l2g", "evidence_eva", "gwas_credible_sets"):
        operands = normalize(
            {
                "source": "OpenTargets",
                "source_dataset": dataset,
                "source_record_id": "ot-1",
                "x_id": "ENSP1",
                "y_id": "MONDO:1",
                "clinical_significance": "pathogenic",
                "variant_consequence": "stop_gained",
                "effect_direction": "risk",
            }
        )
        assert operands["mechanism_operand"] == ""
        assert operands["disease_direction_operand"] == ""
        assert operands["reject_reason"] == "unsupported_source_family_or_mapping"


def test_edge_aggregation_preserves_consensus_conflict_and_unknown() -> None:
    module = _operand_module()
    evidence = pd.DataFrame(
        [
            {"edge_key": "e1", "materialization_assertion_id": "a", "mechanism_operand": "gain_of_function", "disease_direction_operand": "risk"},
            {"edge_key": "e1", "materialization_assertion_id": "b", "mechanism_operand": "gain_of_function", "disease_direction_operand": "risk"},
            {"edge_key": "e2", "materialization_assertion_id": "c", "mechanism_operand": "gain_of_function", "disease_direction_operand": "risk"},
            {"edge_key": "e2", "materialization_assertion_id": "d", "mechanism_operand": "loss_of_function", "disease_direction_operand": "protective"},
            {"edge_key": "e3", "materialization_assertion_id": "e", "mechanism_operand": "", "disease_direction_operand": ""},
        ]
    )

    e1 = module.aggregate_edge_operands(evidence[evidence.edge_key == "e1"])
    e2 = module.aggregate_edge_operands(evidence[evidence.edge_key == "e2"])
    e3 = module.aggregate_edge_operands(evidence[evidence.edge_key == "e3"])

    assert e1["mechanism_status"] == "consensus"
    assert e1["effect_direction_status"] == "consensus"
    assert e2["mechanism_status"] == "conflicting"
    assert e2["effect_direction_status"] == "conflicting"
    assert e3["mechanism_status"] == "unknown"
    assert e3["effect_direction_status"] == "unknown"


def test_materialization_conserves_rows_and_raw_source_columns() -> None:
    module = _operand_module()
    edges = pd.DataFrame(
        [
            {
                "x_id": "ENSP1",
                "x_type": "protein",
                "y_id": "MONDO:1",
                "y_type": "disease",
                "relation": "disease_associated_protein",
                "causal_mechanisms": "[]",
                "mechanism_status": "unknown",
                "effect_directions": "[]",
                "effect_direction_status": "unknown",
            },
            {
                "x_id": "ENSP2",
                "x_type": "protein",
                "y_id": "MONDO:2",
                "y_type": "disease",
                "relation": "disease_associated_protein",
                "causal_mechanisms": "[]",
                "mechanism_status": "unknown",
                "effect_directions": "[]",
                "effect_direction_status": "unknown",
            },
        ]
    )
    common = {
        "relation": "disease_associated_protein",
        "x_type": "protein",
        "y_type": "disease",
        "source": "UniProtKB",
        "isoform": "canonical",
        "mapping_confidence": (
            "exact_uniprot_accession_to_existing_protein_node;"
            "exact_disease_xref_to_existing_disease_node"
        ),
        "mapping_method": "nodes/protein.uniprot_id and nodes/disease xref columns",
        "materialization_assertion_conflict": False,
        "normalized_causal_mechanism": "",
        "normalized_effect_direction": "",
    }
    evidence = pd.DataFrame(
        [
            {
                **common,
                "edge_key": "disease_associated_protein|ENSP1|MONDO:1",
                "x_id": "ENSP1",
                "y_id": "MONDO:1",
                "source_dataset": "reviewed_human_disease_comments",
                "source_record_id": "P1:DISEASE:OMIM:1",
                "materialization_assertion_id": "assertion-1",
                "release": "2026_02",
                "uniprot_accession": "P1",
                "disease_source_id": "OMIM:1",
                "variant_ft_id": "",
                "variant_category": "",
                "disease_description": "A disease due to a gain-of-function defect.",
            },
            {
                **common,
                "edge_key": "disease_associated_protein|ENSP2|MONDO:2",
                "x_id": "ENSP2",
                "y_id": "MONDO:2",
                "source": "UniProtKB/humsavar",
                "source_dataset": "humsavar_missense_variants",
                "source_record_id": "VAR_2",
                "materialization_assertion_id": "assertion-2",
                "release": "2026_02 of 10-Jun-2026",
                "uniprot_accession": "P2",
                "disease_source_id": "OMIM:2",
                "variant_ft_id": "VAR_2",
                "variant_category": "LP/P",
                "disease_description": "",
            },
        ]
    )
    raw_columns = [
        "edge_key",
        "x_id",
        "y_id",
        "source_dataset",
        "source_record_id",
        "release",
        "variant_category",
        "disease_description",
    ]

    enriched_edges, enriched_evidence = module.materialize_disease_operands(edges, evidence)

    assert len(enriched_edges) == len(edges)
    assert len(enriched_evidence) == len(evidence)
    assert enriched_evidence[raw_columns].equals(evidence[raw_columns])
    assert enriched_edges.loc[0, "causal_mechanisms"] == '["gain_of_function"]'
    assert enriched_edges.loc[0, "mechanism_status"] == "single"
    assert enriched_edges.loc[0, "effect_directions"] == '["risk"]'
    assert enriched_edges.loc[1, "causal_mechanisms"] == "[]"
    assert enriched_edges.loc[1, "mechanism_status"] == "unknown"
    assert enriched_edges.loc[1, "effect_direction_status"] == "single"
    assert enriched_evidence.loc[0, "normalized_causal_mechanism"] == "gain_of_function"
    assert enriched_evidence.loc[1, "normalized_effect_direction"] == "risk"
    assert set(module.REQUIRED_ASSERTION_COLUMNS).issubset(enriched_evidence.columns)


def test_staged_build_reports_inventory_conservation_and_joined_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _operand_module()
    edges = pd.DataFrame(
        [
            {"x_id": "ENSP1", "x_type": "protein", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_protein", "causal_mechanisms": "[]", "mechanism_status": "unknown", "effect_directions": "[]", "effect_direction_status": "unknown"},
            {"x_id": "ENSP2", "x_type": "protein", "y_id": "MONDO:2", "y_type": "disease", "relation": "disease_associated_protein", "causal_mechanisms": "[]", "mechanism_status": "unknown", "effect_directions": "[]", "effect_direction_status": "unknown"},
        ]
    )
    exact_mapping = (
        "exact_uniprot_accession_to_existing_protein_node;"
        "exact_disease_xref_to_existing_disease_node"
    )
    evidence = pd.DataFrame(
        [
            {"edge_key": "disease_associated_protein|ENSP1|MONDO:1", "relation": "disease_associated_protein", "x_id": "ENSP1", "x_type": "protein", "y_id": "MONDO:1", "y_type": "disease", "source": "UniProtKB", "source_dataset": "reviewed_human_disease_comments", "source_record_id": "P1:DISEASE:OMIM:1", "release": "2026_02", "uniprot_accession": "P1", "isoform": "canonical", "disease_source_id": "OMIM:1", "variant_ft_id": "", "variant_category": "", "disease_description": "A disease due to a gain-of-function defect.", "mapping_confidence": exact_mapping, "mapping_method": "exact local xrefs", "materialization_assertion_id": "a1", "normalized_causal_mechanism": "", "normalized_effect_direction": ""},
            {"edge_key": "disease_associated_protein|ENSP2|MONDO:2", "relation": "disease_associated_protein", "x_id": "ENSP2", "x_type": "protein", "y_id": "MONDO:2", "y_type": "disease", "source": "UniProtKB/humsavar", "source_dataset": "humsavar_missense_variants", "source_record_id": "VAR_2", "release": "2026_02", "uniprot_accession": "P2", "isoform": "canonical", "disease_source_id": "OMIM:2", "variant_ft_id": "VAR_2", "variant_category": "LP/P", "disease_description": "", "mapping_confidence": exact_mapping, "mapping_method": "exact local xrefs", "materialization_assertion_id": "a2", "normalized_causal_mechanism": "", "normalized_effect_direction": ""},
        ]
    )
    molecule_edges = pd.DataFrame(
        [
            {"x_id": "CHEMBL1", "x_type": "molecule", "y_id": "ENSP1", "y_type": "protein", "relation": "molecule_targets_protein", "action_direction": '["negative"]', "action_status": "single"},
            {"x_id": "CHEMBL2", "x_type": "molecule", "y_id": "ENSP2", "y_type": "protein", "relation": "molecule_targets_protein", "action_direction": '["unknown"]', "action_status": "single"},
        ]
    )
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    edge_path = inputs / "disease_edges.parquet"
    evidence_path = inputs / "disease_evidence.parquet"
    molecule_path = inputs / "molecule_edges.parquet"
    edges.to_parquet(edge_path, index=False)
    evidence.to_parquet(evidence_path, index=False)
    molecule_edges.to_parquet(molecule_path, index=False)
    monkeypatch.setattr(module, "STAGING_ROOT", tmp_path / "staged")
    output = module.STAGING_ROOT / "t_fixture"

    receipt = module.stage_disease_operands(
        disease_edges_path=edge_path,
        disease_evidence_path=evidence_path,
        molecule_edges_path=molecule_path,
        output_root=output,
        source_revision="accepted-parent-sha",
        task_id="t_fixture",
    )

    inventory = json.loads((output / "reports/source_operand_inventory.json").read_text())
    coverage = json.loads((output / "reports/coverage_before_after.json").read_text())
    assert receipt["validation"]["edge_row_conservation"] is True
    assert receipt["validation"]["evidence_row_conservation"] is True
    assert inventory["source_families"]["UniProtKB_humsavar"]["mapped_assertions"] == 1
    assert inventory["source_families"]["UniProtKB_humsavar"]["evidence_rows"] == 1
    assert inventory["source_families"]["ClinVar_OpenTargets_local"]["denominator"] == 0
    assert coverage["both_operands_known"] == {"before": 0, "after": 1}
    assert coverage["mechanism_coverage"]["after"] == {
        "known": 1,
        "unknown": 1,
        "conflicting": 0,
    }
    assert coverage["effect_direction_coverage"]["after"] == {
        "known": 2,
        "unknown": 0,
        "conflicting": 0,
    }
    assert coverage["joined_paths"] == {
        "total": 2,
        "drug_action_known": 1,
        "fully_signed_before": 0,
        "fully_signed_after": 1,
    }
    assert (output / "edges/disease_associated_protein.parquet").exists()
    assert (output / "evidence/disease_associated_protein.parquet").exists()


def _valid_comment_assertion(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "edge_key": "disease_associated_protein|ENSP1|MONDO:1",
        "relation": "disease_associated_protein",
        "x_id": "ENSP1",
        "x_type": "protein",
        "y_id": "MONDO:1",
        "y_type": "disease",
        "source": "UniProtKB",
        "source_dataset": "reviewed_human_disease_comments",
        "source_record_id": "P1:DISEASE:OMIM:1",
        "release": "2026_02",
        "uniprot_accession": "P1",
        "isoform": "canonical",
        "disease_source_id": "OMIM:1",
        "variant_ft_id": "",
        "variant_category": "",
        "disease_description": "A disease due to a gain-of-function defect.",
        "mapping_confidence": (
            "exact_uniprot_accession_to_existing_protein_node;"
            "exact_disease_xref_to_existing_disease_node"
        ),
        "mapping_method": "exact local xrefs",
        "materialization_assertion_id": "a1",
        "materialization_assertion_conflict": False,
        "normalized_causal_mechanism": "",
        "normalized_effect_direction": "",
    }
    row.update(overrides)
    return row


def _single_disease_edge() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "x_id": "ENSP1",
                "x_type": "protein",
                "y_id": "MONDO:1",
                "y_type": "disease",
                "relation": "disease_associated_protein",
                "causal_mechanisms": "[]",
                "mechanism_status": "unknown",
                "effect_directions": "[]",
                "effect_direction_status": "unknown",
            }
        ]
    )


def test_evidence_endpoint_identity_must_reconstruct_its_edge_key() -> None:
    module = _operand_module()
    evidence = pd.DataFrame([_valid_comment_assertion(x_id="ENSP_WRONG")])

    with pytest.raises(ValueError, match="reconstructed edge key"):
        module.materialize_disease_operands(_single_disease_edge(), evidence)


def test_duplicate_edge_identity_fails_closed() -> None:
    module = _operand_module()
    edges = pd.concat([_single_disease_edge(), _single_disease_edge()], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate edge identities"):
        module.materialize_disease_operands(edges, pd.DataFrame([_valid_comment_assertion()]))


def test_inherited_materialization_conflict_cannot_become_known() -> None:
    module = _operand_module()
    evidence = pd.DataFrame(
        [_valid_comment_assertion(materialization_assertion_conflict=True)]
    )

    enriched_edges, enriched_evidence = module.materialize_disease_operands(
        _single_disease_edge(), evidence
    )

    assert bool(enriched_evidence.loc[0, "mechanism_operand_conflict"])
    assert bool(enriched_evidence.loc[0, "disease_direction_operand_conflict"])
    assert enriched_edges.loc[0, "mechanism_status"] == "conflicting"
    assert enriched_edges.loc[0, "effect_direction_status"] == "conflicting"
    assert not bool(enriched_edges.loc[0, "both_operands_known"])


@pytest.mark.parametrize(
    ("overrides", "reject_reason"),
    [
        ({"source": ""}, "missing_source_provenance"),
        ({"source_record_id": ""}, "missing_source_provenance"),
        ({"release": ""}, "missing_source_provenance"),
        ({"source": "OpenTargets"}, "source_family_mismatch"),
    ],
)
def test_reviewed_comment_requires_complete_consistent_provenance(
    overrides: dict[str, str], reject_reason: str
) -> None:
    operands = _operand_module().normalize_disease_operand_assertion(
        _valid_comment_assertion(**overrides)
    )

    assert operands["mechanism_operand"] == ""
    assert operands["disease_direction_operand"] == ""
    assert operands["reject_reason"] == reject_reason


def test_humsavar_source_record_must_equal_variant_ft_id() -> None:
    row = _valid_comment_assertion(
        source="UniProtKB/humsavar",
        source_dataset="humsavar_missense_variants",
        source_record_id="VAR_A",
        variant_ft_id="VAR_B",
        variant_category="LP/P",
    )

    operands = _operand_module().normalize_disease_operand_assertion(row)

    assert operands["mechanism_operand"] == ""
    assert operands["disease_direction_operand"] == ""
    assert operands["reject_reason"] == "variant_source_record_mismatch"


def test_endpoint_types_must_be_protein_to_disease() -> None:
    module = _operand_module()
    wrong_edge = _single_disease_edge()
    wrong_edge.loc[0, "x_type"] = "gene"

    with pytest.raises(ValueError, match="endpoint types"):
        module.materialize_disease_operands(
            wrong_edge, pd.DataFrame([_valid_comment_assertion()])
        )


def test_task_id_cannot_escape_staging_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _operand_module()
    monkeypatch.setattr(module, "STAGING_ROOT", tmp_path / "staged")
    escaped = (module.STAGING_ROOT / "../../escaped").resolve()

    with pytest.raises(ValueError, match="task id"):
        module.stage_disease_operands(
            disease_edges_path=tmp_path / "missing-edges.parquet",
            disease_evidence_path=tmp_path / "missing-evidence.parquet",
            molecule_edges_path=tmp_path / "missing-molecules.parquet",
            output_root=escaped,
            source_revision="69caf8d9cd75ae547c832a670e523339e78e4e6c",
            task_id="../../escaped",
        )


def test_staging_root_symlink_cannot_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _operand_module()
    staging = tmp_path / "staged"
    outside = tmp_path / "outside"
    staging.mkdir()
    outside.mkdir()
    (staging / "t_fixture").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(module, "STAGING_ROOT", staging)

    with pytest.raises(ValueError, match="symlink"):
        module.stage_disease_operands(
            disease_edges_path=tmp_path / "missing-edges.parquet",
            disease_evidence_path=tmp_path / "missing-evidence.parquet",
            molecule_edges_path=tmp_path / "missing-molecules.parquet",
            output_root=staging / "t_fixture",
            source_revision="69caf8d9cd75ae547c832a670e523339e78e4e6c",
            task_id="t_fixture",
        )


def test_joined_coverage_rejects_non_molecule_to_protein_inputs() -> None:
    module = _operand_module()
    edges = _single_disease_edge()
    edges["both_operands_known"] = False
    molecule_edges = pd.DataFrame(
        [
            {
                "x_id": "CHEMBL1",
                "x_type": "disease",
                "y_id": "ENSP1",
                "y_type": "protein",
                "relation": "molecule_targets_protein",
                "action_direction": '["negative"]',
                "action_status": "single",
            }
        ]
    )

    with pytest.raises(ValueError, match="molecule edge endpoint types"):
        module._coverage_report(edges, pd.DataFrame(), edges, pd.DataFrame(), molecule_edges)


def test_descriptor_relative_writer_keeps_open_directory_inode(tmp_path: Path) -> None:
    module = _operand_module()
    opened = tmp_path / "opened"
    moved = tmp_path / "moved"
    redirected = tmp_path / "redirected"
    opened.mkdir()
    redirected.mkdir()
    directory_fd = os.open(opened, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        opened.rename(moved)
        opened.symlink_to(redirected, target_is_directory=True)
        module._write_exclusive(directory_fd, "payload", b"safe")
    finally:
        os.close(directory_fd)

    assert (moved / "payload").read_bytes() == b"safe"
    assert not (redirected / "payload").exists()
