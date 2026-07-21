from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "scripts/validate_causal_edge_feature_inventory.py"
INVENTORY_PATH = REPO_ROOT / "docs/causal_edge_feature_inventory.json"

spec = importlib.util.spec_from_file_location("causal_inventory_validator", VALIDATOR_PATH)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


@pytest.fixture
def inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def test_authoritative_inventory_and_doctrine_pass(inventory: dict) -> None:
    assert validator.validate_inventory(inventory) == []
    assert validator.validate_doctrine(REPO_ROOT) == []


@pytest.mark.parametrize(
    ("assertions", "expected"),
    [
        ([], "unknown"),
        ([None, "", "unknown", "not_available"], "unknown"),
        (["risk"], "single"),
        (["risk", None, "unknown"], "single"),
        (["risk", "RISK"], "consensus"),
        (["risk", "protection"], "conflicting"),
    ],
)
def test_aggregate_status_has_exact_four_state_semantics(
    assertions: list[str | None], expected: str
) -> None:
    assert validator.aggregate_status(assertions) == expected


def test_rejects_fifth_aggregation_state(inventory: dict) -> None:
    invalid = copy.deepcopy(inventory)
    invalid["aggregation"]["states"].append("not_available")
    errors = validator.validate_inventory(invalid)
    assert any("aggregation.states must be exactly" in error for error in errors)
    assert any("not_available is forbidden" in error for error in errors)


def test_rejects_stale_or_contradictory_counts(inventory: dict) -> None:
    invalid = copy.deepcopy(inventory)
    invalid["inventories"][0]["edge_count"] = 805
    errors = validator.validate_inventory(invalid)
    assert "chembl_target.edge_count must equal 2119" in errors


def test_rejects_duplicate_authoritative_lane(inventory: dict) -> None:
    invalid = copy.deepcopy(inventory)
    invalid["inventories"].append(copy.deepcopy(invalid["inventories"][0]))
    errors = validator.validate_inventory(invalid)
    assert "inventories must contain exactly one row per authoritative lane" in errors


def test_rejects_relation_drift_within_lane(inventory: dict) -> None:
    invalid = copy.deepcopy(inventory)
    invalid["inventories"][0]["relation"] = "molecule_targets_gene"
    errors = validator.validate_inventory(invalid)
    assert "chembl_target.relation must equal molecule_targets_protein" in errors


def test_rejects_containment_as_c2_causal_support(inventory: dict) -> None:
    invalid = copy.deepcopy(inventory)
    invalid["inference_policy"]["c2"]["containment_supplies_eligibility"] = True
    errors = validator.validate_inventory(invalid)
    assert any("containment_supplies_eligibility must be false" in error for error in errors)


def test_rejects_active_c3_template(inventory: dict) -> None:
    invalid = copy.deepcopy(inventory)
    invalid["inference_policy"]["c3"]["v1_included"] = True
    errors = validator.validate_inventory(invalid)
    assert "Template F/C3 must be do_not_infer and excluded from v1" in errors


def test_rejects_relation_name_variants(inventory: dict) -> None:
    invalid = copy.deepcopy(inventory)
    invalid["inventories"][0]["relation"] = "molecule_inhibits_gene"
    errors = validator.validate_inventory(invalid)
    assert any("forbidden relation-name variants" in error for error in errors)
