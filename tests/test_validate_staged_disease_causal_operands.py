from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _validator_module():
    name = "scripts.validate_staged_disease_causal_operands"
    assert importlib.util.find_spec(name) is not None, "independent staged validator is missing"
    return importlib.import_module(name)


def _validate_fixture(root: Path) -> dict[str, Any]:
    return _validator_module().validate_staged_candidate(
        root,
        enforce_accepted_inputs=False,
        expected_task_id=root.name,
        expected_staging_root=root.parent,
    )


def _write_candidate(root: Path) -> tuple[Path, Path]:
    (root / "edges").mkdir(parents=True)
    (root / "evidence").mkdir()
    (root / "reports").mkdir()
    edge_path = root / "edges/disease_associated_protein.parquet"
    evidence_path = root / "evidence/disease_associated_protein.parquet"
    edges = pd.DataFrame(
        [
            {
                "x_id": "ENSP1",
                "x_type": "protein",
                "y_id": "MONDO:1",
                "y_type": "disease",
                "relation": "disease_associated_protein",
                "causal_mechanisms": '["gain_of_function"]',
                "mechanism_status": "single",
                "effect_directions": '["risk"]',
                "effect_direction_status": "single",
                "both_operands_known": True,
                "disease_operand_contract_version": "disease-causal-operands-v1",
            }
        ]
    )
    evidence = pd.DataFrame(
        [
            {
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
                "operand_source_family": "UniProtKB_reviewed_disease_comment",
                "operand_source_record_id": "P1:DISEASE:OMIM:1",
                "operand_source_release": "2026_02",
                "operand_mapping_path": json.dumps(
                    {
                        "mapping_confidence": (
                            "exact_uniprot_accession_to_existing_protein_node;"
                            "exact_disease_xref_to_existing_disease_node"
                        ),
                        "mapping_method": "exact local xrefs",
                        "protein_id": "ENSP1",
                        "source_disease_id": "OMIM:1",
                        "source_protein_id": "P1",
                        "target_disease_id": "MONDO:1",
                        "variant_id": "",
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "mechanism_operand": "gain_of_function",
                "disease_direction_operand": "risk",
                "operand_support_class": "explicit_uniprot_disease_causal_phrase",
                "operand_confidence": "direct_explicit",
                "mechanism_operand_conflict": False,
                "disease_direction_operand_conflict": False,
                "operand_reject_reason": "",
                "license": "CC BY 4.0",
                "disease_operand_contract_version": "disease-causal-operands-v1",
                "normalized_causal_mechanism": "gain_of_function",
                "normalized_effect_direction": "risk",
            }
        ]
    )
    edges.to_parquet(edge_path, index=False)
    evidence.to_parquet(evidence_path, index=False)
    coverage = {
        "conservation": {
            "edge_rows": {"before": 1, "after": 1},
            "evidence_rows": {"before": 1, "after": 1},
        },
        "both_operands_known": {"before": 0, "after": 1},
        "mechanism_status": {
            "before": {"conflicting": 0, "consensus": 0, "single": 0, "unknown": 1},
            "after": {"conflicting": 0, "consensus": 0, "single": 1, "unknown": 0}
        },
        "effect_direction_status": {
            "before": {"conflicting": 0, "consensus": 0, "single": 0, "unknown": 1},
            "after": {"conflicting": 0, "consensus": 0, "single": 1, "unknown": 0}
        },
        "mechanism_coverage": {
            "before": {"known": 0, "unknown": 1, "conflicting": 0},
            "after": {"known": 1, "unknown": 0, "conflicting": 0},
        },
        "effect_direction_coverage": {
            "before": {"known": 0, "unknown": 1, "conflicting": 0},
            "after": {"known": 1, "unknown": 0, "conflicting": 0},
        },
        "joined_paths": {
            "total": 1,
            "drug_action_known": 1,
            "fully_signed_before": 0,
            "fully_signed_after": 1,
        },
    }
    coverage_path = root / "reports/coverage_before_after.json"
    coverage_path.write_text(json.dumps(coverage, sort_keys=True) + "\n")
    inventory = {
        "contract_version": "disease-causal-operands-v1",
        "source_revision": "accepted-parent-sha",
        "source_families": {
            "UniProtKB_reviewed_disease_comment": {
                "raw_fields": [
                    "disease_description",
                    "disease_source_id",
                    "mapping_confidence",
                    "source_record_id",
                ],
                "accepted_values": {
                    "disease_description": (
                        "strict disease/disorder due to gain-of-function defect phrase"
                    )
                },
                "mechanism_semantics": "gain_of_function",
                "disease_direction_semantics": (
                    "risk from the same explicit causal disease phrase"
                ),
                "denominator": 1,
                "evidence_rows": 1,
                "eligible_assertions": 1,
                "mapped_assertions": 1,
                "rejects_by_reason": {},
                "license": ["CC BY 4.0"],
                "release": ["2026_02"],
                "snapshot": "accepted-parent-sha",
            },
            "UniProtKB_humsavar": {
                "raw_fields": [
                    "variant_category",
                    "variant_ft_id",
                    "disease_source_id",
                    "mapping_confidence",
                ],
                "accepted_values": {"variant_category": ["LP/P"]},
                "mechanism_semantics": (
                    "none; missense/consequence/pathogenicity never implies GoF/LoF"
                ),
                "disease_direction_semantics": "risk/pathogenic",
                "denominator": 0,
                "evidence_rows": 0,
                "eligible_assertions": 0,
                "mapped_assertions": 0,
                "rejects_by_reason": {},
                "license": [],
                "release": [],
                "snapshot": "accepted-parent-sha",
            },
            "ClinVar_OpenTargets_local": {
                "raw_fields": [
                    "clinicalSignificances",
                    "variantFunctionalConsequenceId",
                    "variantId",
                    "diseaseId",
                    "studyLocusId",
                    "geneId",
                    "score",
                ],
                "accepted_values": {},
                "mechanism_semantics": (
                    "not materialized; consequence, L2G, LD, and proximity are not mechanism"
                ),
                "disease_direction_semantics": (
                    "not materialized without a local exact protein/variant/disease snapshot"
                ),
                "denominator": 0,
                "evidence_rows": 0,
                "eligible_assertions": 0,
                "mapped_assertions": 0,
                "rejects_by_reason": {"missing_local_source_snapshot": 1},
                "license": [],
                "release": [],
                "snapshot": "accepted-parent-sha",
            },
        },
    }
    inventory_path = root / "reports/source_operand_inventory.json"
    inventory_path.write_text(json.dumps(inventory, sort_keys=True) + "\n")
    module = _validator_module()
    input_root = root / "inputs"
    input_root.mkdir()
    input_edges = input_root / "disease_edges.parquet"
    input_evidence = input_root / "disease_evidence.parquet"
    input_molecules = input_root / "molecule_edges.parquet"
    before_edges = edges.copy()
    before_edges["mechanism_status"] = "unknown"
    before_edges["effect_direction_status"] = "unknown"
    before_edges.to_parquet(input_edges, index=False)
    evidence.to_parquet(input_evidence, index=False)
    pd.DataFrame(
        [
            {
                "x_id": "CHEMBL1",
                "x_type": "molecule",
                "y_id": "ENSP1",
                "y_type": "protein",
                "relation": "molecule_targets_protein",
                "action_direction": '["negative"]',
                "action_status": "single",
            }
        ]
    ).to_parquet(input_molecules, index=False)
    manifest = {
        "task_id": root.name,
        "contract_version": "disease-causal-operands-v1",
        "source_revision": "accepted-parent-sha",
        "staging_only": True,
        "canonical_write": False,
        "coverage": coverage,
        "inputs": {
            "disease_edges": {"path": str(input_edges), "sha256": module.sha256(input_edges)},
            "disease_evidence": {
                "path": str(input_evidence),
                "sha256": module.sha256(input_evidence),
            },
            "molecule_edges": {
                "path": str(input_molecules),
                "sha256": module.sha256(input_molecules),
            },
        },
        "outputs": {
            "disease_edges": {
                "path": str(edge_path),
                "sha256": module.sha256(edge_path),
                "semantic_sha256": module.semantic_hash(edges),
            },
            "disease_evidence": {
                "path": str(evidence_path),
                "sha256": module.sha256(evidence_path),
                "semantic_sha256": module.semantic_hash(evidence),
            },
            "coverage_before_after": {
                "path": str(coverage_path),
                "sha256": module.sha256(coverage_path),
            },
            "source_operand_inventory": {
                "path": str(inventory_path),
                "sha256": module.sha256(inventory_path),
            },
        },
    }
    (root / "reports/materialization_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n"
    )
    return edge_path, evidence_path


def test_independent_validator_accepts_consistent_candidate(tmp_path: Path) -> None:
    _write_candidate(tmp_path)

    result = _validate_fixture(tmp_path)

    assert result == {"errors": [], "ok": True}


def test_independent_validator_detects_endpoint_key_and_inherited_conflict(
    tmp_path: Path,
) -> None:
    _, evidence_path = _write_candidate(tmp_path)
    evidence = pd.read_parquet(evidence_path)
    evidence.loc[0, "x_id"] = "ENSP_WRONG"
    evidence.loc[0, "materialization_assertion_conflict"] = True
    evidence.to_parquet(evidence_path, index=False)

    errors = _validate_fixture(tmp_path)["errors"]

    assert "evidence edge_key does not match relation|x_id|y_id" in errors
    assert "inherited assertion conflict is not preserved" in errors


def test_independent_validator_detects_provenance_aggregate_and_receipt_corruption(
    tmp_path: Path,
) -> None:
    edge_path, evidence_path = _write_candidate(tmp_path)
    edges = pd.read_parquet(edge_path)
    evidence = pd.read_parquet(evidence_path)
    edges.loc[0, "mechanism_status"] = "unknown"
    evidence.loc[0, "operand_source_record_id"] = ""
    edges.to_parquet(edge_path, index=False)
    evidence.to_parquet(evidence_path, index=False)

    errors = _validate_fixture(tmp_path)["errors"]

    assert "usable operand lacks complete consistent provenance" in errors
    assert "edge aggregates do not match evidence assertions" in errors
    assert "manifest output hash mismatch" in errors
    assert "coverage report does not match staged outputs" in errors


def test_independent_validator_detects_unsupported_operand_semantics(tmp_path: Path) -> None:
    _, evidence_path = _write_candidate(tmp_path)
    evidence = pd.read_parquet(evidence_path)
    evidence.loc[0, "mechanism_operand"] = "gain_of_magical_function"
    evidence.to_parquet(evidence_path, index=False)

    errors = _validate_fixture(tmp_path)["errors"]

    assert "unsupported operand semantics" in errors


def test_independent_validator_detects_wrong_endpoint_types(tmp_path: Path) -> None:
    edge_path, evidence_path = _write_candidate(tmp_path)
    edges = pd.read_parquet(edge_path)
    evidence = pd.read_parquet(evidence_path)
    edges.loc[0, "x_type"] = "gene"
    evidence.loc[0, "x_type"] = "gene"
    edges.to_parquet(edge_path, index=False)
    evidence.to_parquet(evidence_path, index=False)

    errors = _validate_fixture(tmp_path)["errors"]

    assert "invalid relation or endpoint types" in errors


def test_independent_validator_recomputes_operands_from_raw_assertion(tmp_path: Path) -> None:
    _, evidence_path = _write_candidate(tmp_path)
    evidence = pd.read_parquet(evidence_path)
    evidence["uniprot_accession"] = "P1"
    evidence["isoform"] = "canonical"
    evidence["disease_source_id"] = "OMIM:1"
    evidence["variant_ft_id"] = ""
    evidence["mapping_confidence"] = (
        "exact_uniprot_accession_to_existing_protein_node;"
        "exact_disease_xref_to_existing_disease_node"
    )
    evidence["disease_description"] = "Generic association without a causal phrase."
    evidence.to_parquet(evidence_path, index=False)

    errors = _validate_fixture(tmp_path)["errors"]

    assert "normalized operands do not match raw source assertions" in errors


def test_independent_validator_recomputes_source_inventory(tmp_path: Path) -> None:
    _write_candidate(tmp_path)
    inventory_path = tmp_path / "reports/source_operand_inventory.json"
    manifest_path = tmp_path / "reports/materialization_manifest.json"
    inventory = json.loads(inventory_path.read_text())
    inventory["source_families"]["UniProtKB_reviewed_disease_comment"][
        "mapped_assertions"
    ] = 0
    inventory_path.write_text(json.dumps(inventory, sort_keys=True) + "\n")
    manifest = json.loads(manifest_path.read_text())
    manifest["outputs"]["source_operand_inventory"]["sha256"] = _validator_module().sha256(
        inventory_path
    )
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    errors = _validate_fixture(tmp_path)["errors"]

    assert "source inventory does not match staged evidence" in errors


def test_independent_validator_rejects_forged_manifest_metadata(tmp_path: Path) -> None:
    _write_candidate(tmp_path)
    manifest_path = tmp_path / "reports/materialization_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["task_id"] = "t_forged"
    manifest["staging_only"] = False
    manifest["canonical_write"] = True
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    errors = _validate_fixture(tmp_path)["errors"]

    assert "manifest staging identity mismatch" in errors


def test_independent_validator_rejects_self_consistent_forged_task_root(
    tmp_path: Path,
) -> None:
    forged_root = tmp_path / "t_forged"
    _write_candidate(forged_root)

    errors = _validator_module().validate_staged_candidate(
        forged_root, enforce_accepted_inputs=False
    )["errors"]

    assert "manifest staging identity mismatch" in errors


def test_independent_validator_rejects_relocated_expected_task_root(
    tmp_path: Path,
) -> None:
    relocated_root = tmp_path / "t_causal_disease_operands"
    _write_candidate(relocated_root)

    errors = _validator_module().validate_staged_candidate(
        relocated_root, enforce_accepted_inputs=False
    )["errors"]

    assert "manifest staging identity mismatch" in errors


def test_independent_validator_requires_exact_output_receipts_and_paths(
    tmp_path: Path,
) -> None:
    _write_candidate(tmp_path)
    manifest_path = tmp_path / "reports/materialization_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["outputs"].pop("source_operand_inventory")
    manifest["outputs"]["disease_edges"]["path"] = str(tmp_path / "forged.parquet")
    manifest["outputs"]["unexpected"] = {"path": "elsewhere", "sha256": "0" * 64}
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    errors = _validate_fixture(tmp_path)["errors"]

    assert "manifest output inventory mismatch" in errors


def test_independent_validator_recomputes_source_inventory_semantics(
    tmp_path: Path,
) -> None:
    _write_candidate(tmp_path)
    inventory_path = tmp_path / "reports/source_operand_inventory.json"
    manifest_path = tmp_path / "reports/materialization_manifest.json"
    inventory = json.loads(inventory_path.read_text())
    family = inventory["source_families"]["UniProtKB_humsavar"]
    family["raw_fields"] = ["nearest_gene"]
    family["accepted_values"] = {"variant_category": ["anything"]}
    family["mechanism_semantics"] = "missense implies loss_of_function"
    family["disease_direction_semantics"] = "unknown"
    inventory_path.write_text(json.dumps(inventory, sort_keys=True) + "\n")
    manifest = json.loads(manifest_path.read_text())
    manifest["outputs"]["source_operand_inventory"]["sha256"] = _validator_module().sha256(
        inventory_path
    )
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    errors = _validate_fixture(tmp_path)["errors"]

    assert "source inventory does not match staged evidence" in errors


def test_independent_validator_requires_all_input_receipts(tmp_path: Path) -> None:
    _write_candidate(tmp_path)
    manifest_path = tmp_path / "reports/materialization_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["inputs"].pop("molecule_edges")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    errors = _validate_fixture(tmp_path)["errors"]

    assert "required input receipts are missing" in errors


def test_independent_validator_recomputes_assertion_metadata(tmp_path: Path) -> None:
    _, evidence_path = _write_candidate(tmp_path)
    evidence = pd.read_parquet(evidence_path)
    evidence["operand_mapping_path"] = "{}"
    evidence["operand_support_class"] = "fabricated_support"
    evidence["operand_confidence"] = "fabricated_confidence"
    evidence["normalized_causal_mechanism"] = "gain_of_function"
    evidence["normalized_effect_direction"] = "risk"
    evidence.to_parquet(evidence_path, index=False)

    errors = _validate_fixture(tmp_path)["errors"]

    assert "assertion metadata does not match raw source assertions" in errors


def test_independent_validator_rejects_invalid_molecule_input_semantics(tmp_path: Path) -> None:
    _write_candidate(tmp_path)
    manifest_path = tmp_path / "reports/materialization_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    molecule_path = Path(manifest["inputs"]["molecule_edges"]["path"])
    molecules = pd.read_parquet(molecule_path)
    molecules["x_type"] = "disease"
    molecules.to_parquet(molecule_path, index=False)
    manifest["inputs"]["molecule_edges"]["sha256"] = _validator_module().sha256(
        molecule_path
    )
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    errors = _validate_fixture(tmp_path)["errors"]

    assert "molecule input semantics are invalid" in errors


def test_independent_validator_pins_accepted_input_identity(tmp_path: Path) -> None:
    _write_candidate(tmp_path)

    errors = _validator_module().validate_staged_candidate(tmp_path)["errors"]

    assert "accepted input identity mismatch" in errors