"""Independently validate a staged disease causal operand candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


CONTRACT_VERSION = "disease-causal-operands-v1"
EXPECTED_TASK_IDS = {
    "t_causal_disease_operands",
    "t_causal_disease_operands_run1",
}
EXPECTED_STAGING_ROOT = (Path(__file__).resolve().parents[1] / "artifacts" / "staged").resolve()
ACCEPTED_SOURCE_REVISION = "69caf8d9cd75ae547c832a670e523339e78e4e6c"
ACCEPTED_INPUT_SHA256 = {
    "disease_edges": "1371f0e627e0cc7db32714864aeaeabbd7b7f2e7ba3aa30b0723ee1ef33eec3d",
    "disease_evidence": "6a3cb7a53fd0a0ab55071f5e806ad92ede52b2e6c25926ac99d3cbdfe3a6d352",
    "molecule_edges": "08b5b4f2abdd4f92c4512f889fb18abe1dedc6a024147b99df09b7da447ced91",
}
STATES = {"single", "consensus", "conflicting", "unknown"}
MECHANISM_OPERANDS = {"", "gain_of_function"}
DISEASE_DIRECTION_OPERANDS = {"", "risk"}
EXPECTED_PROVENANCE = {
    "reviewed_human_disease_comments": (
        "UniProtKB",
        "UniProtKB_reviewed_disease_comment",
    ),
    "humsavar_missense_variants": ("UniProtKB/humsavar", "UniProtKB_humsavar"),
}
EXPECTED_INVENTORY_SEMANTICS = {
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
    },
}
EXACT_MAPPING = {
    "exact_uniprot_accession_to_existing_protein_node",
    "exact_disease_xref_to_existing_disease_node",
}
UNIPROT_GOF_CAUSAL_PHRASE = re.compile(
    r"\b(?:disorder|disease)\s+due\s+to\s+(?:an?\s+)?gain[ -]of[ -]function\s+defect\b",
    re.IGNORECASE,
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _truthy(value: Any) -> bool:
    return _clean(value).lower() in {"1", "true", "yes"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_hash(frame: pd.DataFrame) -> str:
    payload = frame.to_json(orient="records", date_format="iso", double_precision=15)
    return hashlib.sha256(payload.encode()).hexdigest()


def _aggregate(
    group: pd.DataFrame, value_column: str, conflict_column: str
) -> tuple[list[str], str]:
    values = sorted({_clean(value) for value in group[value_column] if _clean(value)})
    inherited = group.get(
        "materialization_assertion_conflict", pd.Series(False, index=group.index)
    ).map(_truthy)
    explicit = group[conflict_column].map(_truthy)
    if inherited.any() or explicit.any() or len(values) > 1:
        return values, "conflicting"
    usable = group.loc[
        group[value_column].map(_clean) != "", "materialization_assertion_id"
    ].map(_clean)
    assertion_count = usable[usable != ""].nunique()
    if not values or assertion_count == 0:
        return [], "unknown"
    return values, "single" if assertion_count == 1 else "consensus"


def _status_counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    counts = frame[column].value_counts().to_dict()
    return {state: int(counts.get(state, 0)) for state in sorted(STATES)}


def _collapsed_coverage(frame: pd.DataFrame, column: str) -> dict[str, int]:
    counts = _status_counts(frame, column)
    return {
        "known": counts["single"] + counts["consensus"],
        "unknown": counts["unknown"],
        "conflicting": counts["conflicting"],
    }


def _has_signed_action(value: Any) -> bool:
    try:
        parsed = json.loads(_clean(value))
    except (json.JSONDecodeError, TypeError):
        parsed = [_clean(value)]
    values = parsed if isinstance(parsed, list) else [parsed]
    return bool({_clean(item) for item in values} & {"negative", "positive"})


def _append(errors: list[str], condition: bool, message: str) -> None:
    if condition and message not in errors:
        errors.append(message)


def _unusable(reason: str) -> dict[str, str]:
    return {
        "mechanism_operand": "",
        "disease_direction_operand": "",
        "operand_support_class": "unusable",
        "operand_confidence": "unknown",
        "operand_reject_reason": reason,
    }


def _expected_assertion(row: pd.Series) -> dict[str, str]:
    dataset = _clean(row.get("source_dataset"))
    expected = EXPECTED_PROVENANCE.get(dataset)
    if expected is None:
        return _unusable("unsupported_source_family_or_mapping")
    if not all(
        _clean(row.get(column)) for column in ("source", "source_record_id", "release")
    ):
        return _unusable("missing_source_provenance")
    if _clean(row.get("source")) != expected[0]:
        return _unusable("source_family_mismatch")
    if not _clean(row.get("disease_source_id")) or not _clean(row.get("y_id")):
        return _unusable("missing_disease_context")
    variant = _clean(row.get("variant_ft_id"))
    if dataset == "humsavar_missense_variants" and (
        not variant or not _clean(row.get("source_record_id"))
    ):
        return _unusable("missing_exact_variant_identity")
    if _clean(row.get("isoform")) != "canonical":
        return _unusable("mixed_or_noncanonical_isoform")
    mapping = set(_clean(row.get("mapping_confidence")).split(";"))
    if not EXACT_MAPPING.issubset(mapping):
        return _unusable("ambiguous_or_inexact_mapping")
    if not _clean(row.get("x_id")) or not _clean(row.get("uniprot_accession")):
        return _unusable("ambiguous_or_inexact_mapping")
    if dataset == "humsavar_missense_variants" and variant != _clean(
        row.get("source_record_id")
    ):
        return _unusable("variant_source_record_mismatch")
    if dataset == "reviewed_human_disease_comments":
        if UNIPROT_GOF_CAUSAL_PHRASE.search(_clean(row.get("disease_description"))):
            return {
                "mechanism_operand": "gain_of_function",
                "disease_direction_operand": "risk",
                "operand_support_class": "explicit_uniprot_disease_causal_phrase",
                "operand_confidence": "direct_explicit",
                "operand_reject_reason": "",
            }
        return _unusable("no_eligible_explicit_operand")
    if _clean(row.get("variant_category")).upper() == "LP/P":
        return {
            "mechanism_operand": "",
            "disease_direction_operand": "risk",
            "operand_support_class": "explicit_humsavar_pathogenic_variant_disease",
            "operand_confidence": "direct_explicit",
            "operand_reject_reason": "",
        }
    return _unusable("no_eligible_explicit_operand")


def _expected_mapping_path(row: pd.Series) -> str:
    return json.dumps(
        {
            "mapping_confidence": _clean(row.get("mapping_confidence")),
            "mapping_method": _clean(row.get("mapping_method")),
            "protein_id": _clean(row.get("x_id")),
            "source_disease_id": _clean(row.get("disease_source_id")),
            "source_protein_id": _clean(row.get("uniprot_accession")),
            "target_disease_id": _clean(row.get("y_id")),
            "variant_id": _clean(row.get("variant_ft_id")),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _expected_inventory_facts(
    evidence: pd.DataFrame, source_revision: str
) -> dict[str, dict[str, Any]]:
    assertions = evidence.drop_duplicates(
        subset=["operand_source_family", "materialization_assertion_id"], keep="first"
    )
    facts: dict[str, dict[str, Any]] = {}
    for family in ("UniProtKB_reviewed_disease_comment", "UniProtKB_humsavar"):
        rows = assertions[assertions["operand_source_family"] == family]
        usable = (rows["mechanism_operand"].map(_clean) != "") | (
            rows["disease_direction_operand"].map(_clean) != ""
        )
        rejects = Counter(rows.loc[~usable, "operand_reject_reason"].map(_clean))
        licenses = rows.get("license", pd.Series(dtype=str)).map(_clean)
        facts[family] = {
            **EXPECTED_INVENTORY_SEMANTICS[family],
            "denominator": int(len(rows)),
            "evidence_rows": int((evidence["operand_source_family"] == family).sum()),
            "eligible_assertions": int(usable.sum()),
            "mapped_assertions": int(usable.sum()),
            "rejects_by_reason": {
                reason: int(count) for reason, count in sorted(rejects.items()) if reason
            },
            "license": sorted(set(licenses) - {""}),
            "release": sorted(set(rows["operand_source_release"].map(_clean)) - {""}),
            "snapshot": source_revision,
        }
    facts["ClinVar_OpenTargets_local"] = {
        **EXPECTED_INVENTORY_SEMANTICS["ClinVar_OpenTargets_local"],
        "denominator": 0,
        "evidence_rows": 0,
        "eligible_assertions": 0,
        "mapped_assertions": 0,
        "rejects_by_reason": {"missing_local_source_snapshot": 1},
        "license": [],
        "release": [],
        "snapshot": source_revision,
    }
    return facts


def validate_staged_candidate(
    root: Path,
    *,
    enforce_accepted_inputs: bool = True,
    expected_task_id: str | None = None,
    expected_staging_root: Path = EXPECTED_STAGING_ROOT,
) -> dict[str, Any]:
    root = Path(root).resolve()
    expected_staging_root = Path(expected_staging_root).resolve()
    edge_path = root / "edges/disease_associated_protein.parquet"
    evidence_path = root / "evidence/disease_associated_protein.parquet"
    coverage_path = root / "reports/coverage_before_after.json"
    inventory_path = root / "reports/source_operand_inventory.json"
    manifest_path = root / "reports/materialization_manifest.json"
    required_paths = (edge_path, evidence_path, coverage_path, inventory_path, manifest_path)
    missing = [str(path) for path in required_paths if not path.is_file()]
    if missing:
        return {
            "errors": [f"missing required artifact: {path}" for path in missing],
            "ok": False,
        }

    edges = pd.read_parquet(edge_path)
    evidence = pd.read_parquet(evidence_path)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    edge_keys = (
        edges["relation"].map(_clean)
        + "|"
        + edges["x_id"].map(_clean)
        + "|"
        + edges["y_id"].map(_clean)
    )
    reconstructed = (
        evidence["relation"].map(_clean)
        + "|"
        + evidence["x_id"].map(_clean)
        + "|"
        + evidence["y_id"].map(_clean)
    )
    _append(errors, bool(edge_keys.duplicated().any()), "duplicate edge identities")
    _append(
        errors,
        not reconstructed.equals(evidence["edge_key"].map(_clean)),
        "evidence edge_key does not match relation|x_id|y_id",
    )
    _append(
        errors,
        bool(set(reconstructed) - set(edge_keys)),
        "evidence key lacks exact edge membership",
    )
    invalid_endpoints = any(
        (
            set(edges["relation"].map(_clean)) != {"disease_associated_protein"},
            set(evidence["relation"].map(_clean)) != {"disease_associated_protein"},
            set(edges["x_type"].map(_clean)) != {"protein"},
            set(evidence["x_type"].map(_clean)) != {"protein"},
            set(edges["y_type"].map(_clean)) != {"disease"},
            set(evidence["y_type"].map(_clean)) != {"disease"},
        )
    )
    _append(errors, invalid_endpoints, "invalid relation or endpoint types")
    unsupported_operands = bool(
        set(evidence["mechanism_operand"].map(_clean)) - MECHANISM_OPERANDS
        or set(evidence["disease_direction_operand"].map(_clean))
        - DISEASE_DIRECTION_OPERANDS
    )
    _append(errors, unsupported_operands, "unsupported operand semantics")
    expected_assertions = [_expected_assertion(row) for _, row in evidence.iterrows()]
    normalized_mismatch = any(
        (
            _clean(row.get("mechanism_operand")),
            _clean(row.get("disease_direction_operand")),
        )
        != (
            expected["mechanism_operand"],
            expected["disease_direction_operand"],
        )
        for (_, row), expected in zip(evidence.iterrows(), expected_assertions, strict=True)
    )
    _append(
        errors,
        normalized_mismatch,
        "normalized operands do not match raw source assertions",
    )
    metadata_mismatch = any(
        any(
            _clean(row.get(column)) != expected[column]
            for column in (
                "operand_support_class",
                "operand_confidence",
                "operand_reject_reason",
            )
        )
        or _clean(row.get("operand_source_family"))
        != EXPECTED_PROVENANCE.get(_clean(row.get("source_dataset")), ("", "unsupported"))[1]
        or _clean(row.get("operand_source_record_id"))
        != _clean(row.get("source_record_id"))
        or _clean(row.get("operand_source_release")) != _clean(row.get("release"))
        or _clean(row.get("operand_mapping_path")) != _expected_mapping_path(row)
        or _clean(row.get("normalized_causal_mechanism"))
        != _clean(row.get("mechanism_operand"))
        or _clean(row.get("normalized_effect_direction"))
        != _clean(row.get("disease_direction_operand"))
        or _clean(row.get("disease_operand_contract_version")) != CONTRACT_VERSION
        for (_, row), expected in zip(evidence.iterrows(), expected_assertions, strict=True)
    )
    _append(
        errors,
        metadata_mismatch,
        "assertion metadata does not match raw source assertions",
    )

    inherited = evidence.get(
        "materialization_assertion_conflict", pd.Series(False, index=evidence.index)
    ).map(_truthy)
    preserved = evidence["mechanism_operand_conflict"].map(_truthy) & evidence[
        "disease_direction_operand_conflict"
    ].map(_truthy)
    _append(
        errors,
        bool((inherited & ~preserved).any()),
        "inherited assertion conflict is not preserved",
    )

    usable = (evidence["mechanism_operand"].map(_clean) != "") | (
        evidence["disease_direction_operand"].map(_clean) != ""
    )
    provenance_bad = pd.Series(False, index=evidence.index)
    for index in evidence.index[usable]:
        row = evidence.loc[index]
        dataset = _clean(row.get("source_dataset"))
        expected = EXPECTED_PROVENANCE.get(dataset)
        complete = all(
            _clean(row.get(column))
            for column in (
                "source",
                "source_record_id",
                "release",
                "operand_source_record_id",
                "operand_source_release",
            )
        )
        consistent = bool(expected) and (
            _clean(row.get("source")),
            _clean(row.get("operand_source_family")),
        ) == expected
        copied = (
            _clean(row.get("source_record_id"))
            == _clean(row.get("operand_source_record_id"))
            and _clean(row.get("release"))
            == _clean(row.get("operand_source_release"))
        )
        variant_consistent = dataset != "humsavar_missense_variants" or (
            _clean(row.get("source_record_id")) == _clean(row.get("variant_ft_id"))
        )
        provenance_bad.loc[index] = not (
            complete and consistent and copied and variant_consistent
        )
    _append(
        errors,
        bool(provenance_bad.any()),
        "usable operand lacks complete consistent provenance",
    )

    groups = {key: group for key, group in evidence.groupby("edge_key", sort=False)}
    aggregate_mismatch = False
    empty = evidence.iloc[0:0]
    for index, edge_key in edge_keys.items():
        group = groups.get(edge_key, empty)
        mechanisms, mechanism_status = _aggregate(
            group, "mechanism_operand", "mechanism_operand_conflict"
        )
        directions, direction_status = _aggregate(
            group, "disease_direction_operand", "disease_direction_operand_conflict"
        )
        row = edges.loc[index]
        expected_both = mechanism_status in {"single", "consensus"} and direction_status in {
            "single",
            "consensus",
        }
        aggregate_mismatch |= any(
            (
                _clean(row["causal_mechanisms"])
                != json.dumps(mechanisms, separators=(",", ":")),
                _clean(row["mechanism_status"]) != mechanism_status,
                _clean(row["effect_directions"])
                != json.dumps(directions, separators=(",", ":")),
                _clean(row["effect_direction_status"]) != direction_status,
                _truthy(row["both_operands_known"]) != expected_both,
            )
        )
    _append(
        errors,
        aggregate_mismatch,
        "edge aggregates do not match evidence assertions",
    )

    outputs = manifest.get("outputs", {})
    expected_outputs = {
        "disease_edges": (edge_path, semantic_hash(edges)),
        "disease_evidence": (evidence_path, semantic_hash(evidence)),
        "coverage_before_after": (coverage_path, None),
        "source_operand_inventory": (inventory_path, None),
    }
    output_inventory_mismatch = set(outputs) != set(expected_outputs)
    hash_mismatch = False
    for label, (path, semantic) in expected_outputs.items():
        receipt = outputs.get(label, {})
        output_inventory_mismatch |= receipt.get("path") != str(path)
        hash_mismatch |= receipt.get("sha256") != sha256(path)
        if semantic is not None:
            hash_mismatch |= receipt.get("semantic_sha256") != semantic
    _append(errors, output_inventory_mismatch, "manifest output inventory mismatch")
    _append(errors, hash_mismatch, "manifest output hash mismatch")

    _append(
        errors,
        bool(
            root.parent != expected_staging_root
            or root.name not in ({expected_task_id} if expected_task_id else EXPECTED_TASK_IDS)
            or manifest.get("task_id") != root.name
            or manifest.get("staging_only") is not True
            or manifest.get("canonical_write") is not False
        ),
        "manifest staging identity mismatch",
    )

    source_revision = _clean(manifest.get("source_revision"))
    inventory_mismatch = (
        inventory.get("contract_version") != CONTRACT_VERSION
        or inventory.get("source_revision") != source_revision
    )
    expected_inventory = _expected_inventory_facts(evidence, source_revision)
    reported_families = inventory.get("source_families", {})
    inventory_mismatch |= set(reported_families) != set(expected_inventory)
    for family, expected_facts in expected_inventory.items():
        reported = reported_families.get(family, {})
        inventory_mismatch |= any(
            reported.get(field) != expected for field, expected in expected_facts.items()
        )
    _append(
        errors,
        bool(inventory_mismatch),
        "source inventory does not match staged evidence",
    )

    coverage_mismatch = manifest.get("coverage") != coverage
    conservation = coverage.get("conservation", {})
    coverage_mismatch |= conservation.get("edge_rows", {}).get("after") != len(edges)
    coverage_mismatch |= conservation.get("evidence_rows", {}).get("after") != len(
        evidence
    )
    coverage_mismatch |= coverage.get("both_operands_known", {}).get("after") != int(
        edges["both_operands_known"].map(_truthy).sum()
    )
    coverage_mismatch |= coverage.get("mechanism_status", {}).get(
        "after"
    ) != _status_counts(edges, "mechanism_status")
    coverage_mismatch |= coverage.get("effect_direction_status", {}).get(
        "after"
    ) != _status_counts(edges, "effect_direction_status")
    _append(
        errors,
        coverage_mismatch,
        "coverage report does not match staged outputs",
    )

    input_receipts = manifest.get("inputs", {})
    required_inputs = {"disease_edges", "disease_evidence", "molecule_edges"}
    _append(
        errors,
        set(input_receipts) != required_inputs,
        "required input receipts are missing",
    )
    if enforce_accepted_inputs:
        accepted_input_mismatch = (
            manifest.get("source_revision") != ACCEPTED_SOURCE_REVISION
            or any(
                input_receipts.get(label, {}).get("sha256") != expected_hash
                for label, expected_hash in ACCEPTED_INPUT_SHA256.items()
            )
        )
        _append(
            errors,
            accepted_input_mismatch,
            "accepted input identity mismatch",
        )
    for label, receipt in input_receipts.items():
        path = Path(receipt.get("path", ""))
        _append(
            errors,
            not path.is_file() or receipt.get("sha256") != sha256(path),
            f"input receipt mismatch: {label}",
        )
    if "disease_edges" in input_receipts:
        before_path = Path(input_receipts["disease_edges"].get("path", ""))
        if before_path.is_file():
            before_edges = pd.read_parquet(before_path)
            identity = ["x_id", "x_type", "y_id", "y_type", "relation"]
            _append(
                errors,
                len(before_edges) != len(edges)
                or not before_edges[identity].equals(edges[identity]),
                "edge conservation mismatch",
            )
    if "disease_evidence" in input_receipts:
        before_path = Path(input_receipts["disease_evidence"].get("path", ""))
        if before_path.is_file():
            before_evidence = pd.read_parquet(before_path)
            raw_columns = [
                column
                for column in before_evidence
                if not column.startswith("normalized_")
            ]
            _append(
                errors,
                len(before_evidence) != len(evidence)
                or not before_evidence[raw_columns].equals(evidence[raw_columns]),
                "evidence conservation mismatch",
            )
    input_paths = {
        label: Path(input_receipts.get(label, {}).get("path", ""))
        for label in required_inputs
    }
    if all(path.is_file() for path in input_paths.values()):
        before_edges = pd.read_parquet(input_paths["disease_edges"])
        molecule_edges = pd.read_parquet(input_paths["molecule_edges"])
        required_molecule_columns = {
            "x_id",
            "x_type",
            "y_id",
            "y_type",
            "relation",
            "action_direction",
            "action_status",
        }
        molecule_invalid = not required_molecule_columns.issubset(molecule_edges.columns)
        if not molecule_invalid:
            molecule_invalid = (
                set(molecule_edges["relation"].map(_clean))
                != {"molecule_targets_protein"}
                or set(molecule_edges["x_type"].map(_clean)) != {"molecule"}
                or set(molecule_edges["y_type"].map(_clean)) != {"protein"}
                or molecule_edges[["relation", "x_id", "y_id"]].astype(str).duplicated().any()
            )
        _append(errors, molecule_invalid, "molecule input semantics are invalid")
        if not molecule_invalid:
            joined_before = molecule_edges.merge(
                before_edges,
                left_on="y_id",
                right_on="x_id",
                suffixes=("_drug", "_disease"),
            )
            joined_after = molecule_edges.merge(
                edges,
                left_on="y_id",
                right_on="x_id",
                suffixes=("_drug", "_disease"),
            )
            action_known_before = joined_before["action_status"].isin(
                {"single", "consensus"}
            ) & joined_before["action_direction"].map(_has_signed_action)
            action_known_after = joined_after["action_status"].isin(
                {"single", "consensus"}
            ) & joined_after["action_direction"].map(_has_signed_action)
            disease_known_before = joined_before["mechanism_status"].isin(
                {"single", "consensus"}
            ) & joined_before["effect_direction_status"].isin({"single", "consensus"})
            disease_known_after = joined_after["mechanism_status"].isin(
                {"single", "consensus"}
            ) & joined_after["effect_direction_status"].isin({"single", "consensus"})
            joined_expected = {
                "total": int(len(joined_after)),
                "drug_action_known": int(action_known_after.sum()),
                "fully_signed_before": int(
                    (action_known_before & disease_known_before).sum()
                ),
                "fully_signed_after": int((action_known_after & disease_known_after).sum()),
            }
            coverage_mismatch |= coverage.get("joined_paths") != joined_expected
            for column, section in (
                ("mechanism_status", "mechanism_coverage"),
                ("effect_direction_status", "effect_direction_coverage"),
            ):
                coverage_mismatch |= coverage.get(column, {}).get("before") != _status_counts(
                    before_edges, column
                )
                coverage_mismatch |= coverage.get(section, {}).get(
                    "before"
                ) != _collapsed_coverage(before_edges, column)
                coverage_mismatch |= coverage.get(section, {}).get(
                    "after"
                ) != _collapsed_coverage(edges, column)
            _append(
                errors,
                coverage_mismatch,
                "coverage report does not match staged outputs",
            )

    _append(
        errors,
        bool(
            manifest.get("contract_version") != CONTRACT_VERSION
            or set(edges["mechanism_status"]) - STATES
            or set(edges["effect_direction_status"]) - STATES
        ),
        "contract or aggregation state mismatch",
    )
    return {"errors": errors, "ok": not errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args(argv)
    result = validate_staged_candidate(args.root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
