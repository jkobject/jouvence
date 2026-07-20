#!/usr/bin/env python3
"""Validate the authoritative causal-edge feature inventory and doctrine."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

AGGREGATION_STATES = ("single", "consensus", "conflicting", "unknown")
UNUSABLE_ASSERTIONS = {"", "unknown", "not_available"}
EXPECTED_INVENTORIES: dict[str, dict[str, int]] = {
    "chembl_target": {"edge_count": 2119, "action_bearing_assertion_count": 2132},
    "uniprot_disease": {"edge_count": 3243, "evidence_assertion_count": 35839},
    "transcript_consequence": {"row_count": 2599922},
    "contained_gene": {"row_count": 2599525},
    "legacy_contraindication": {
        "distinct_pair_count": 30675,
        "evidence_assertion_count": 0,
    },
}
EXPECTED_RELATIONS = {
    "chembl_target": "molecule_targets_protein",
    "uniprot_disease": "disease_associated_protein",
    "transcript_consequence": "mutation_affects_transcript",
    "contained_gene": "mutation_in_gene",
    "legacy_contraindication": "molecule_contraindicates_disease",
}
FORBIDDEN_RELATION_VARIANTS = {
    "molecule_inhibits_gene",
    "gene_gof_causes_disease",
    "gene_lof_causes_disease",
    "mutation_confers_drug_resistance",
}


def aggregate_status(assertions: Iterable[str | None]) -> str:
    """Return the four-state aggregation status for normalized assertions."""
    usable = [
        value
        for value in assertions
        if value is not None and value.strip().lower() not in UNUSABLE_ASSERTIONS
    ]
    if not usable:
        return "unknown"
    normalized = {value.strip().lower() for value in usable}
    if len(normalized) > 1:
        return "conflicting"
    return "single" if len(usable) == 1 else "consensus"


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _walk_strings(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            yield from _walk_strings(nested)


def validate_inventory(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    aggregation = data.get("aggregation", {})
    if aggregation.get("states") != list(AGGREGATION_STATES):
        errors.append(f"aggregation.states must be exactly {list(AGGREGATION_STATES)!r}")
    if aggregation.get("zero_usable_assertions") != "unknown":
        errors.append("zero usable assertions must aggregate to unknown")

    if "not_available" in set(_walk_strings(data)):
        errors.append("not_available is forbidden by the four-state contract")

    edge_model = data.get("edge_model", {})
    if edge_model.get("storage") != "typed_features_on_existing_broad_edges":
        errors.append("causal features must remain on existing broad edge tables")
    if edge_model.get("new_relation_name_variants") is not False:
        errors.append("new causal/sign/action relation-name variants must be disabled")

    inventories = data.get("inventories")
    if not isinstance(inventories, list):
        errors.append("inventories must be a list")
        inventories = []
    by_lane = {
        item.get("lane"): item
        for item in inventories
        if isinstance(item, Mapping) and isinstance(item.get("lane"), str)
    }
    if set(by_lane) != set(EXPECTED_INVENTORIES):
        errors.append(
            "inventory lanes must be exactly " + repr(sorted(EXPECTED_INVENTORIES))
        )
    if len(inventories) != len(EXPECTED_INVENTORIES) or len(by_lane) != len(inventories):
        errors.append("inventories must contain exactly one row per authoritative lane")
    for lane, expected_counts in EXPECTED_INVENTORIES.items():
        item = by_lane.get(lane, {})
        if item.get("relation") != EXPECTED_RELATIONS[lane]:
            errors.append(f"{lane}.relation must equal {EXPECTED_RELATIONS[lane]}")
        for field, expected in expected_counts.items():
            if item.get(field) != expected:
                errors.append(f"{lane}.{field} must equal {expected}")

    relations = {
        relation
        for item in inventories
        if isinstance(item, Mapping)
        and isinstance((relation := item.get("relation")), str)
    }
    forbidden = relations & FORBIDDEN_RELATION_VARIANTS
    if forbidden:
        errors.append(f"forbidden relation-name variants present: {sorted(forbidden)!r}")

    c2 = data.get("inference_policy", {}).get("c2", {})
    required_false = (
        "containment_supplies_eligibility",
        "containment_supplies_causal_mechanism",
        "containment_supplies_effect_direction",
        "containment_supplies_sign",
    )
    for field in required_false:
        if c2.get(field) is not False:
            errors.append(f"inference_policy.c2.{field} must be false")
    if c2.get("relation") != "mutation_in_gene":
        errors.append("C2 containment policy must explicitly name mutation_in_gene")

    c3 = data.get("inference_policy", {}).get("c3", {})
    if c3 != {"decision": "do_not_infer", "template": "F", "v1_included": False}:
        errors.append("Template F/C3 must be do_not_infer and excluded from v1")

    legacy = by_lane.get("legacy_contraindication", {})
    if legacy.get("source_backed_causal_eligibility") is not False:
        errors.append("legacy contraindications without evidence must fail closed")
    contained = by_lane.get("contained_gene", {})
    if contained.get("causal_eligibility") is not False:
        errors.append("contained-gene rows must not supply causal eligibility")

    relation_semantics = data.get("relation_semantics", {})
    if relation_semantics.get("source_native_direction_required") is not True:
        errors.append("source-native relation direction must be required")
    if relation_semantics.get("canonical_relation_per_assertion") is not True:
        errors.append("each assertion must normalize to one canonical relation")
    expression = relation_semantics.get("expression", {})
    if expression.get("gene_or_rna_level") != "x_expresses_gene":
        errors.append("gene/RNA expression must use x_expresses_gene")
    if expression.get("direct_protein_measurement") != "x_expresses_protein":
        errors.append("direct protein measurement must use x_expresses_protein")
    if expression.get("protein_to_gene_projection_preserves_modality") is not True:
        errors.append("protein-to-gene projection must preserve measurement modality")
    if relation_semantics.get("response") != [
        "cell_type_responds_to_molecule",
        "cell_line_responds_to_molecule",
    ]:
        errors.append("response relations must preserve canonical endpoint semantics")
    return errors


def validate_doctrine(repo_root: Path) -> list[str]:
    errors: list[str] = []
    paths = {
        "causal": repo_root / "docs/causal_edge_feature_model.md",
        "inferred": repo_root / "docs/inferred_edges_policy.md",
        "source_native": repo_root / "docs/guides/source-native-modeling.md",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    if "`single|consensus|conflicting|unknown`" not in texts["causal"]:
        errors.append("causal doctrine must state the exact four-state contract")
    if "Simple genomic containment (`mutation_in_gene`)" not in texts["inferred"]:
        errors.append("inferred policy must explicitly reject mutation_in_gene for C2")
    if "Default label: `do_not_infer` for v1" not in texts["inferred"]:
        errors.append("inferred policy must keep Template F/C3 do_not_infer")
    if "`cell_type_responds_to_molecule`" not in texts["causal"]:
        errors.append("causal doctrine must preserve cell-type response semantics")
    if "`cell_line_responds_to_molecule`" not in texts["causal"]:
        errors.append("causal doctrine must preserve cell-line response semantics")
    if "not_available" in "\n".join(texts.values()):
        errors.append("not_available must not appear in authoritative doctrine")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inventory",
        nargs="?",
        type=Path,
        default=Path("docs/causal_edge_feature_inventory.json"),
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    data = json.loads(args.inventory.read_text(encoding="utf-8"))
    errors = validate_inventory(data)
    errors.extend(validate_doctrine(args.repo_root))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASS: {args.inventory} satisfies causal-edge-features-v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
