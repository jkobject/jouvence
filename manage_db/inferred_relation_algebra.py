"""Typed, fail-closed Jouvence inferred biological relation algebra.

This module defines and executes graph-derived candidates only. Outputs belong in
``edges_inferred`` / ``evidence_inferred`` and are never canonical observations.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
import pyarrow.parquet as pq


class EpistemicClass(str, Enum):
    LOGICALLY_DERIVED = "logically_derived"
    CONDITIONAL = "conditional"
    ABDUCTIVE = "abductive"


class SignStatus(str, Enum):
    KNOWN = "known"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"


class EvidenceValueStatus(str, Enum):
    MISSING = "missing"
    SINGLE = "single"
    CONFLICTING = "conflicting"


@dataclass(frozen=True)
class EvidenceValue:
    """Normalized gate value that cannot conflate missing and conflicting data."""

    status: EvidenceValueStatus
    values: tuple[str, ...] = ()

    @property
    def value(self) -> str:
        return self.values[0] if self.status is EvidenceValueStatus.SINGLE else ""


@dataclass(frozen=True)
class TypedRelation:
    relation: str
    source_type: str
    target_type: str


@dataclass(frozen=True)
class InferenceRule:
    rule_id: str
    version: str
    premises: tuple[TypedRelation, ...]
    conclusion: TypedRelation
    epistemic_class: EpistemicClass
    required_evidence: tuple[str, ...]
    forbidden_evidence: tuple[str, ...]
    context_join_keys: tuple[str, ...]
    sign_algebra: str
    quantifier: str
    fail_closed_conditions: tuple[str, ...]


EXCLUDED_MOTIFS: Mapping[str, str] = {
    "c3_variant_enhancer_gene_disease": "Variant→enhancer→gene→disease was explicitly removed from v1.",
    "c4_tf_enhancer_gene": "TF→enhancer→gene is outside the approved v1 batch.",
    "h3_cell_line_response_disease": "Cell-line response cannot generate disease treatment candidates.",
    "h4_synthetic_rescue_interaction": "Synthetic-rescue/interaction chains are too tenuous for v1.",
    "reactome_pathway_closure": "Pathway closure awaits a source-predicate audit.",
    "prism_cell_line_molecule": "PRISM is an independent observed dataset, never an inference premise.",
    "d1_ontology_closure": "Ontology closure was explicitly removed from v1.",
    "d2_hpo_generalization": "HPO ancestor generalization was explicitly removed from v1.",
    "d3_gene_protein_product": "Gene→transcript→protein-product derivation was explicitly removed from v1.",
}


def _rule(
    rule_id: str,
    premises: tuple[tuple[str, str, str], ...],
    conclusion: tuple[str, str, str],
    epistemic_class: EpistemicClass,
    *,
    required: tuple[str, ...],
    forbidden: tuple[str, ...],
    context: tuple[str, ...],
    sign: str = "not_applicable",
    quantifier: str = "exists compatible support path",
    fail_closed: tuple[str, ...],
    version: str = "1.0.0",
) -> InferenceRule:
    return InferenceRule(
        rule_id=rule_id,
        version=version,
        premises=tuple(TypedRelation(*premise) for premise in premises),
        conclusion=TypedRelation(*conclusion),
        epistemic_class=epistemic_class,
        required_evidence=required,
        forbidden_evidence=forbidden,
        context_join_keys=context,
        sign_algebra=sign,
        quantifier=quantifier,
        fail_closed_conditions=fail_closed,
    )


_RULES = (
    _rule(
        "variant_protein_disease_v1",
        (
            ("mutation_causes_protein_change", "mutation", "protein"),
            ("mutation_associated_disease", "mutation", "disease"),
        ),
        ("disease_associated_protein", "protein", "disease"),
        EpistemicClass.CONDITIONAL,
        required=("exact_variant", "direct_protein_consequence", "disease_support"),
        forbidden=("gene_projection", "ld_only", "metadata_only"),
        context=("variant_id", "isoform_id", "tissue", "population"),
        fail_closed=("variant_mismatch", "isoform_mismatch", "context_mismatch"),
    ),
    _rule(
        "variant_gene_disease_v1",
        (
            ("mutation_in_gene", "mutation", "gene"),
            ("mutation_associated_disease", "mutation", "disease"),
        ),
        ("disease_associated_gene", "gene", "disease"),
        EpistemicClass.CONDITIONAL,
        required=("exact_variant", "functional_or_causal_support", "disease_support"),
        forbidden=(
            "intragenic_containment_only",
            "generic_transcript_consequence_containment",
            "ld_only",
            "nearest_gene",
            "ambiguous_gene_attribution",
            "missing_or_conflicting_attribution",
            "metadata_only",
        ),
        context=("variant_id", "tissue", "population"),
        fail_closed=("variant_mismatch", "context_mismatch", "attribution_conflict"),
        version="1.1.0",
    ),
    _rule(
        "pharmacogenomic_variant_drug_disease_v1",
        (
            ("mutation_associated_disease", "mutation", "disease"),
            ("mutation_affects_molecule_response", "mutation", "molecule"),
        ),
        ("molecule_treats_disease", "molecule", "disease"),
        EpistemicClass.CONDITIONAL,
        required=("exact_variant", "sensitivity_or_benefit_response", "compatible_population_context"),
        forbidden=("resistance", "toxicity", "unknown_direction", "metadata_only"),
        context=("variant_id", "disease", "population", "tissue", "treatment_context"),
        sign="response must be sensitivity/benefit-compatible; resistance/toxicity/unknown fail closed",
        fail_closed=("resistance", "toxicity", "unknown_direction", "population_mismatch", "context_mismatch"),
    ),
    _rule(
        "signed_target_mechanism_gene_drug_disease_v1",
        (
            ("molecule_targets_gene", "molecule", "gene"),
            ("disease_associated_gene", "gene", "disease"),
        ),
        ("molecule_treats_disease", "molecule", "disease"),
        EpistemicClass.ABDUCTIVE,
        required=("known_pharmacological_action_sign", "known_pathological_mechanism_sign", "causal_disease_support"),
        forbidden=("association_only", "expression_only", "metadata_only"),
        context=("target_id", "tissue", "biosample", "population"),
        sign="pharmacological action and pathological mechanism must be known and therapeutic-opposite",
        fail_closed=("unknown_sign", "conflicting_sign", "same_sign", "association_only", "context_mismatch"),
    ),
    _rule(
        "signed_target_mechanism_protein_drug_disease_v1",
        (
            ("molecule_targets_protein", "molecule", "protein"),
            ("disease_associated_protein", "protein", "disease"),
        ),
        ("molecule_treats_disease", "molecule", "disease"),
        EpistemicClass.ABDUCTIVE,
        required=("known_pharmacological_action_sign", "known_pathological_mechanism_sign", "causal_disease_support"),
        forbidden=("gene_to_protein_projection", "expression_only", "metadata_only"),
        context=("target_id", "isoform_id", "tissue", "biosample", "population"),
        sign="pharmacological action and pathological mechanism must be known and therapeutic-opposite",
        fail_closed=("unknown_sign", "conflicting_sign", "same_sign", "association_only", "isoform_mismatch", "context_mismatch"),
    ),
)

RULES_BY_ID: Mapping[str, InferenceRule] = {rule.rule_id: rule for rule in _RULES}
INFERRED_RELATION_BY_NAME: Mapping[str, TypedRelation] = {
    rule.conclusion.relation: rule.conclusion for rule in _RULES
}


@dataclass(frozen=True)
class BuildConfig:
    kg_root: Path
    output_root: Path
    kg_snapshot_id: str
    kg_generations: Mapping[str, str]
    producer_revision: str
    rule_ids: tuple[str, ...]
    max_anchors: int = 1000
    sample_limit: int = 10
    max_input_rows: int = 100_000


_CONTEXT_KEYS = ("isoform_id", "tissue", "biosample", "population", "organism", "treatment_context")
_FUNCTIONAL_SUPPORT = {"allele_specific", "colocalization", "crispr", "eqtl_colocalization", "mpra"}
_CAUSAL_DISEASE_SUPPORT = {"causal", "fine_mapped", "likely_pathogenic", "pathogenic"}
_PATHOGENIC_SUPPORT = {"likely_pathogenic", "pathogenic"}
_CODING_CONSEQUENCES = {
    "coding_sequence_variant",
    "frameshift_variant",
    "inframe_deletion",
    "inframe_insertion",
    "missense_variant",
    "protein_altering_variant",
    "start_lost",
    "stop_gained",
    "stop_lost",
    "synonymous_variant",
    "so_0001578",
    "so_0001580",
    "so_0001583",
    "so_0001587",
    "so_0001589",
    "so_0001818",
    "so_0001819",
    "so_0001821",
    "so_0001822",
    "so_0002012",
}
_SPLICE_CONSEQUENCES = {
    "splice_acceptor_variant",
    "splice_donor_variant",
    "splice_region_variant",
    "so_0001574",
    "so_0001575",
    "so_0001630",
}
_EQTL_SUPPORT = {"colocalized_eqtl", "eqtl_colocalization"}
_L2G_SUPPORT = {"l2g", "opentargets_l2g", "open_targets_l2g"}
_DEPRECATED_RULE_ARTIFACTS = {
    "variant_enhancer_gene_disease_v1": "disease_associated_gene",
}
_POSITIVE_RESPONSE = {"benefit", "increased_response", "sensitivity", "therapeutic_benefit"}
_FORBIDDEN_RESPONSE = {"adverse_effect", "decreased_response", "resistance", "toxicity", "unknown", "unknown_direction"}
_SIGN = {
    "activate": 1,
    "activation": 1,
    "agonist": 1,
    "gain_of_function": 1,
    "increase": 1,
    "up": 1,
    "inhibit": -1,
    "inhibition": -1,
    "antagonist": -1,
    "loss_of_function": -1,
    "decrease": -1,
    "down": -1,
}


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass
    to_list = getattr(value, "tolist", None)
    if callable(to_list):
        try:
            value = to_list()
        except (AttributeError, ValueError):
            pass
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    return value


def _json(value: Any) -> str:
    return json.dumps(_clean(value), sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _read_relation(
    root: Path,
    relation: str,
    *,
    required: bool = True,
    max_rows: int | None = None,
) -> list[dict[str, Any]]:
    path = root / "edges" / f"{relation}.parquet"
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required immutable-snapshot relation is missing: {path}")
        return []
    row_count = pq.ParquetFile(path).metadata.num_rows
    if max_rows is not None and row_count > max_rows:
        raise ValueError(f"{path} has {row_count} rows and exceeds bounded input limit {max_rows}")
    rows = [_clean(row) for row in pd.read_parquet(path).to_dict(orient="records")]
    for row in rows:
        if row.get("relation") != relation:
            raise ValueError(f"{path} contains a non-{relation} row")
        row.setdefault("edge_key", f"{relation}|{row.get('x_id')}|{row.get('y_id')}")
    return sorted(rows, key=lambda row: (str(row.get("x_id", "")), str(row.get("y_id", "")), str(row["edge_key"])))


def _evidence_index(root: Path, relation: str, *, max_rows: int | None = None) -> Mapping[str, dict[str, Any]]:
    path = root / "evidence" / f"{relation}.parquet"
    if not path.exists():
        return {}
    row_count = pq.ParquetFile(path).metadata.num_rows
    if max_rows is not None and row_count > max_rows:
        raise ValueError(f"{path} has {row_count} rows and exceeds bounded input limit {max_rows}")
    identifiers: dict[str, set[str]] = {}
    field_values: dict[str, dict[str, set[str]]] = {}
    records: dict[str, list[dict[str, Any]]] = {}
    for raw in pd.read_parquet(path).to_dict(orient="records"):
        row = _clean(raw)
        edge_key = str(row.get("edge_key") or f"{relation}|{row.get('x_id')}|{row.get('y_id')}")
        evidence_id = str(row.get("evidence_key") or row.get("source_record_id") or _sha(row))
        identifiers.setdefault(edge_key, set()).add(evidence_id)
        records.setdefault(edge_key, []).append(row)
        structured = row.get("text_span")
        if isinstance(structured, str) and structured.strip().startswith("{"):
            try:
                parsed = json.loads(structured)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, Mapping):
                for key in (
                    "clinical_significance",
                    "colocalization_method",
                    "consequence",
                    "consequence_ids",
                    "impact",
                    "l2g_model",
                    "l2g_score",
                    "study_id",
                    "tissue",
                    "transcript_id",
                    "transcript_ids",
                ):
                    if not _normalized_values(row.get(key)) and key in parsed:
                        row[key] = parsed[key]
        for field in (
            "action_sign",
            "action_type",
            "alternative_targets",
            "association_basis",
            "attribution_method",
            "biosample",
            "causal_support",
            "clinical_source",
            "clinical_significance",
            "colocalization_method",
            "consequence",
            "consequence_ids",
            "consequence_source",
            "direction",
            "directionality",
            "disease_support",
            "evidence_score",
            "functional_support",
            "impact",
            "isoform_id",
            "l2g_model",
            "l2g_score",
            "mechanism_sign",
            "pathological_mechanism_sign",
            "pgx_category",
            "population",
            "predicate",
            "protein_isoform",
            "regulatory_support",
            "response_category",
            "response_direction",
            "source",
            "source_dataset",
            "source_record_id",
            "study_id",
            "tissue",
            "treatment_context",
            "transcript_id",
            "transcript_ids",
        ):
            value = row.get(field)
            values = value if isinstance(value, (list, tuple, set)) else (value,)
            for item in values:
                if item is not None and str(item).strip():
                    field_values.setdefault(edge_key, {}).setdefault(field, set()).add(str(item))
    result: dict[str, dict[str, Any]] = {}
    for edge_key, ids in identifiers.items():
        fields = {
            field: next(iter(values))
            for field, values in field_values.get(edge_key, {}).items()
            if len(values) == 1
        }
        conflicts = {
            field: tuple(sorted(values))
            for field, values in field_values.get(edge_key, {}).items()
            if len(values) > 1
        }
        result[edge_key] = {
            "ids": tuple(sorted(ids)),
            "fields": fields,
            "conflicts": conflicts,
            "records": tuple(
                sorted(records.get(edge_key, ()), key=lambda row: _json(row))
            ),
        }
    return result


def _by(rows: Iterable[dict[str, Any]], key: str) -> Mapping[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(str(row.get(key)), []).append(row)
    return result


def _is_conflicting(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() == SignStatus.CONFLICTING.value
    if isinstance(value, Mapping):
        return str(value.get("status", "")).strip().lower() == SignStatus.CONFLICTING.value
    if isinstance(value, (list, tuple, set)):
        values = {
            str(item).strip().lower()
            for item in value
            if item is not None and str(item).strip()
        }
        return SignStatus.CONFLICTING.value in values or len(values) > 1
    return False


def _normalized_values(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, Mapping):
        value = value.get("values", ())
    values = value if isinstance(value, (list, tuple, set)) else (value,)
    return {
        str(item).strip().lower()
        for item in values
        if item is not None
        and str(item).strip()
        and str(item).strip().lower() != EvidenceValueStatus.CONFLICTING.value
    }


def _resolve_value(row: Mapping[str, Any], *names: str) -> EvidenceValue:
    evidence_fields = row.get("support_evidence_fields", {})
    if not isinstance(evidence_fields, Mapping):
        evidence_fields = {}
    evidence_conflicts = row.get("support_evidence_conflicts", {})
    if not isinstance(evidence_conflicts, Mapping):
        evidence_conflicts = {}
    values: set[str] = set()
    conflicting = False
    for name in names:
        value = row.get(name)
        direct_values = _normalized_values(value)
        if _is_conflicting(value) or len(direct_values) > 1:
            conflicting = True
        values.update(direct_values)
        evidence_value = evidence_fields.get(name)
        evidence_values = _normalized_values(evidence_value)
        if _is_conflicting(evidence_value) or len(evidence_values) > 1:
            conflicting = True
        values.update(evidence_values)
        if name in evidence_conflicts:
            conflicting = True
            values.update(_normalized_values(evidence_conflicts[name]))
    ordered = tuple(sorted(values))
    if conflicting or len(ordered) > 1:
        return EvidenceValue(EvidenceValueStatus.CONFLICTING, ordered)
    if ordered:
        return EvidenceValue(EvidenceValueStatus.SINGLE, ordered)
    return EvidenceValue(EvidenceValueStatus.MISSING)


def _value(row: Mapping[str, Any], *names: str) -> str:
    return _resolve_value(row, *names).value


def _is_true(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _compatible(rows: Iterable[Mapping[str, Any]], keys: Iterable[str] = _CONTEXT_KEYS) -> bool:
    rows = tuple(rows)
    for key in keys:
        resolved = tuple(_resolve_value(row, key) for row in rows)
        if any(value.status is EvidenceValueStatus.CONFLICTING for value in resolved):
            return False
        values = {value.value for value in resolved if value.status is EvidenceValueStatus.SINGLE}
        if len(values) > 1:
            return False
    return True


def _context(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    result: dict[str, Any] = {}
    conflicts: dict[str, set[str]] = {}
    for key in _CONTEXT_KEYS:
        values: set[str] = set()
        for row in rows:
            resolved = _resolve_value(row, key)
            if resolved.status is EvidenceValueStatus.CONFLICTING:
                conflicts.setdefault(key, set()).update(resolved.values)
            elif resolved.status is EvidenceValueStatus.SINGLE:
                values.add(resolved.value)
        sorted_values = sorted(values)
        if sorted_values:
            result[key] = sorted_values[0] if len(sorted_values) == 1 else sorted_values
    if conflicts:
        result["context_conflicts"] = {
            key: sorted(values)
            for key, values in sorted(conflicts.items())
        }
    return result


def _path(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{str(key): _clean(value) for key, value in row.items()} for row in rows]


def _candidate(
    rule: InferenceRule,
    x_id: str,
    y_id: str,
    supports: tuple[dict[str, Any], ...],
    strength: str,
    *,
    sign_status: SignStatus = SignStatus.UNKNOWN,
    context: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "x_id": str(x_id),
        "x_type": rule.conclusion.source_type,
        "y_id": str(y_id),
        "y_type": rule.conclusion.target_type,
        "relation": rule.conclusion.relation,
        "display_relation": f"inferred {rule.conclusion.relation}",
        "inference_rule_id": rule.rule_id,
        "inference_rule_version": rule.version,
        "epistemic_class": rule.epistemic_class.value,
        "inference_strength": strength,
        "sign_status": sign_status.value,
        "support_edge_ids": sorted({str(row["edge_key"]) for row in supports}),
        "support_rows": list(supports),
        "context": dict(context or _context(supports)),
        **dict(extra or {}),
    }


def _single_detail(row: Mapping[str, Any], *names: str) -> str:
    value = _resolve_value(row, *names)
    return value.value if value.status is EvidenceValueStatus.SINGLE else ""


def _joined_detail(row: Mapping[str, Any], *names: str) -> str:
    values: set[str] = set()
    evidence_fields = row.get("support_evidence_fields", {})
    evidence_conflicts = row.get("support_evidence_conflicts", {})
    for name in names:
        values.update(_normalized_values(row.get(name)))
        if isinstance(evidence_fields, Mapping):
            values.update(_normalized_values(evidence_fields.get(name)))
        if isinstance(evidence_conflicts, Mapping):
            values.update(_normalized_values(evidence_conflicts.get(name)))
    return "|".join(sorted(values))


def _c2_consequence_family(endpoint: Mapping[str, Any]) -> tuple[str, str] | None:
    evidence_fields = endpoint.get("support_evidence_fields", {})
    consequence_names = ("consequence", "consequence_id", "consequence_ids")
    if any(_is_conflicting(endpoint.get(name)) for name in consequence_names) or (
        isinstance(evidence_fields, Mapping)
        and any(_is_conflicting(evidence_fields.get(name)) for name in consequence_names)
    ):
        return None
    detail = _joined_detail(
        endpoint,
        *consequence_names,
    )
    values = {value for value in detail.split("|") if value}
    if not values:
        return "", ""
    if values & _SPLICE_CONSEQUENCES:
        return "splice", detail
    if values & _CODING_CONSEQUENCES:
        return "coding_pathogenic", detail
    return "", detail


def _classify_c2_support(endpoint: Mapping[str, Any]) -> tuple[str, dict[str, str]] | None:
    """Classify an exact variant→gene attribution into the approved C2 families."""
    consequence_support = _c2_consequence_family(endpoint)
    if consequence_support is None:
        return None
    consequence_family, consequence = consequence_support
    clinical_value = _resolve_value(endpoint, "clinical_significance")
    support_value = _resolve_value(
        endpoint,
        "functional_support",
        "regulatory_support",
        "attribution_method",
    )
    if support_value.status is EvidenceValueStatus.MISSING:
        support_value = _resolve_value(endpoint, "predicate")
    if any(
        value.status is EvidenceValueStatus.CONFLICTING
        for value in (clinical_value, support_value)
    ):
        return None
    support = support_value.value
    if support in {"nearest", "nearest_gene"}:
        return None
    alternative_targets = _joined_detail(endpoint, "alternative_targets")
    alternatives = {
        target.strip().lower()
        for value in alternative_targets.split("|")
        for target in value.replace(",", "|").split("|")
        if target.strip()
    }
    if len(alternatives) > 1 and support not in _EQTL_SUPPORT | _L2G_SUPPORT:
        return None

    clinical = clinical_value.value
    transcript_id = _single_detail(
        endpoint,
        "transcript_id",
        "transcript_ids",
        "transcript",
    )
    common = {
        "clinical_significance": clinical,
        "clinical_source": _single_detail(endpoint, "clinical_source"),
        "consequence": consequence,
        "consequence_source": _single_detail(endpoint, "consequence_source"),
        "impact": _single_detail(endpoint, "impact"),
        "source": _joined_detail(endpoint, "source", "source_dataset"),
        "source_record_id": _single_detail(endpoint, "source_record_id"),
        "transcript_id": transcript_id,
        "transcript_provenance": transcript_id
        or _single_detail(endpoint, "source_record_id"),
    }
    if consequence_family == "splice":
        return "splice", {key: value for key, value in common.items() if value}
    if consequence_family == "coding_pathogenic" or clinical in _PATHOGENIC_SUPPORT:
        return "coding_pathogenic", {
            key: value for key, value in common.items() if value
        }

    study_id = _single_detail(endpoint, "study_id")
    source = _joined_detail(endpoint, "source", "source_dataset")
    if support in _EQTL_SUPPORT:
        method = _single_detail(endpoint, "colocalization_method")
        tissue = _single_detail(endpoint, "tissue", "biosample")
        if not method or not study_id or not tissue:
            return None
        return "colocalized_eqtl", {
            "colocalization_method": method,
            "source": source,
            "study_id": study_id,
            "tissue": tissue,
        }
    if support in _L2G_SUPPORT:
        model = _single_detail(endpoint, "l2g_model")
        score = _single_detail(endpoint, "l2g_score", "evidence_score")
        if not model or not score or not source:
            return None
        return "l2g", {
            "l2g_model": model,
            "l2g_score": score,
            "source": source,
            "study_id": study_id,
        }
    return None


def _generate(rule: InferenceRule, relation_rows: Mapping[str, list[dict[str, Any]]], config: BuildConfig) -> tuple[list[dict[str, Any]], int]:
    rule_id = rule.rule_id
    premise = [relation_rows[item.relation] for item in rule.premises]
    candidates: list[dict[str, Any]] = []
    rejected = 0


    if rule_id == "variant_protein_disease_v1":
        disease_by_variant = _by(premise[1], "x_id")
        for endpoint in premise[0][: config.max_anchors]:
            for disease in disease_by_variant.get(str(endpoint["x_id"]), []):
                if not _compatible((endpoint, disease)):
                    rejected += 1
                    continue
                direct = _value(endpoint, "consequence", "predicate") in {"amino_acid_change", "direct_protein_consequence", "protein_change"}
                causal = _value(disease, "disease_support", "clinical_significance") in _CAUSAL_DISEASE_SUPPORT
                functional = _value(disease, "functional_support") not in {"", "none"}
                isoform = _value(endpoint, "isoform_id", "protein_isoform")
                compatible_isoform = bool(isoform) and isoform == _value(disease, "isoform_id", "protein_isoform")
                strength = "strong" if direct and causal and functional and compatible_isoform else "hypothesis"
                if not direct:
                    rejected += 1
                    continue
                candidates.append(_candidate(rule, endpoint["y_id"], disease["y_id"], (endpoint, disease), strength))
        return candidates, rejected

    if rule_id == "variant_gene_disease_v1":
        disease_by_variant = _by(premise[1], "x_id")
        for endpoint in premise[0][: config.max_anchors]:
            classified = _classify_c2_support(endpoint)
            matching_diseases = disease_by_variant.get(str(endpoint["x_id"]), [])
            if classified is None:
                rejected += len(matching_diseases)
                continue
            support_family, support_details = classified
            for disease in matching_diseases:
                if not _compatible((endpoint, disease)):
                    rejected += 1
                    continue
                causal = _value(
                    disease,
                    "disease_support",
                    "clinical_significance",
                ) in _CAUSAL_DISEASE_SUPPORT
                endpoint_pathogenic = _value(
                    endpoint,
                    "clinical_significance",
                ) in _PATHOGENIC_SUPPORT
                if support_family in {"colocalized_eqtl", "l2g"}:
                    strength = "strong" if causal else "statistical_conditional"
                else:
                    strength = "strong" if causal or endpoint_pathogenic else "conditional"
                candidates.append(
                    _candidate(
                        rule,
                        endpoint["y_id"],
                        disease["y_id"],
                        (endpoint, disease),
                        strength,
                        extra={
                            "c2_support_family": support_family,
                            "c2_support_details": _json(support_details),
                        },
                    )
                )
        return candidates, rejected

    if rule_id == "pharmacogenomic_variant_drug_disease_v1":
        responses_by_variant = _by(premise[1], "x_id")
        for disease in premise[0][: config.max_anchors]:
            for response in responses_by_variant.get(str(disease["x_id"]), []):
                direction = _value(response, "response_direction", "direction", "directionality")
                category = _value(response, "response_category", "pgx_category", "predicate")
                if direction in _FORBIDDEN_RESPONSE or category in {"adverse_effect", "toxicity"} or direction not in _POSITIVE_RESPONSE:
                    rejected += 1
                    continue
                if not _compatible((disease, response), ("population", "tissue", "biosample", "treatment_context")):
                    rejected += 1
                    continue
                candidates.append(_candidate(rule, response["y_id"], disease["y_id"], (disease, response), "strong", sign_status=SignStatus.KNOWN))
        return candidates, rejected

    if rule_id.startswith("signed_target_mechanism_"):
        mechanisms_by_target = _by(premise[1], "x_id")
        tissue_edges = relation_rows.get("disease_manifests_in_tissue", [])
        disease_tissues = _by(tissue_edges, "x_id")
        expression_relation = "tissue_expresses_gene" if rule.conclusion.source_type == "molecule" and rule.premises[0].target_type == "gene" else "tissue_expresses_protein"
        expression_pairs = {(str(row["x_id"]), str(row["y_id"])) for row in relation_rows.get(expression_relation, [])}
        for target in premise[0][: config.max_anchors]:
            for mechanism in mechanisms_by_target.get(str(target["y_id"]), []):
                action = _SIGN.get(_value(target, "action_sign", "action_type"))
                pathological = _SIGN.get(_value(mechanism, "mechanism_sign", "pathological_mechanism_sign"))
                causal_flag = _resolve_value(mechanism, "causal_support")
                disease_support = _resolve_value(mechanism, "disease_support")
                causal_conflict = (
                    causal_flag.status is EvidenceValueStatus.CONFLICTING
                    or disease_support.status is EvidenceValueStatus.CONFLICTING
                )
                causal = not causal_conflict and (
                    _is_true(causal_flag.value)
                    or disease_support.value in _CAUSAL_DISEASE_SUPPORT
                )
                if action is None or pathological is None or action == pathological or not causal or not _compatible((target, mechanism)):
                    rejected += 1
                    continue
                tissues = sorted(
                    str(edge["y_id"])
                    for edge in disease_tissues.get(str(mechanism["y_id"]), [])
                    if (str(edge["y_id"]), str(target["y_id"])) in expression_pairs
                )
                context = _context((target, mechanism))
                context["h2_tissues"] = tissues
                candidates.append(
                    _candidate(
                        rule,
                        target["x_id"],
                        mechanism["y_id"],
                        (target, mechanism),
                        "strong_reinforced" if tissues else "strong",
                        sign_status=SignStatus.KNOWN,
                        context=context,
                    )
                )
        return candidates, rejected

    raise NotImplementedError(rule_id)


def _finalize_candidates(
    candidates: list[dict[str, Any]],
    rule: InferenceRule,
    config: BuildConfig,
    evidence_by_relation: Mapping[str, Mapping[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    observed = _read_relation(
        config.kg_root,
        rule.conclusion.relation,
        required=False,
        max_rows=config.max_input_rows,
    )
    observed_pairs = {(str(row["x_id"]), str(row["y_id"])) for row in observed}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidates:
        grouped.setdefault((candidate["x_id"], candidate["y_id"]), []).append(candidate)
    strength_rank = {
        "derived": 1,
        "hypothesis": 1,
        "statistical_conditional": 2,
        "conditional": 2,
        "strong": 3,
        "strong_reinforced": 4,
    }
    result: list[dict[str, Any]] = []
    for pair, paths in sorted(grouped.items()):
        chosen = max(paths, key=lambda item: strength_rank[item["inference_strength"]])
        support_paths = [tuple(path["support_rows"]) for path in paths]
        support_rows = [row for support_path in support_paths for row in support_path]
        support_edge_ids = sorted({str(row["edge_key"]) for row in support_rows})
        support_evidence_ids = sorted(
            {
                evidence_id
                for row in support_rows
                for evidence_id in evidence_by_relation.get(str(row["relation"]), {}).get(str(row["edge_key"]), {}).get("ids", ())
            }
        )
        full_paths = [_path(support_path) for support_path in support_paths]
        overlap = pair in observed_pairs
        derivation_payload = {
            "rule_id": rule.rule_id,
            "rule_version": rule.version,
            "x_id": pair[0],
            "y_id": pair[1],
            "support_edge_ids": support_edge_ids,
            "support_evidence_ids": support_evidence_ids,
            "full_path": full_paths,
            "kg_snapshot_id": config.kg_snapshot_id,
            "kg_generations": config.kg_generations,
            "context": chosen["context"],
            "sign_status": chosen["sign_status"],
            "inference_strength": chosen["inference_strength"],
            "c2_support_family": chosen.get("c2_support_family"),
            "c2_support_details": chosen.get("c2_support_details"),
        }
        row = {key: value for key, value in chosen.items() if key not in {"support_edge_ids", "support_rows", "context"}}
        row.update(
            {
                "edge_key": f"{rule.conclusion.relation}|{pair[0]}|{pair[1]}|{rule.rule_id}",
                "support_edge_ids_or_hashes": _json(support_edge_ids),
                "support_evidence_ids_or_hashes": _json(support_evidence_ids),
                "full_path": _json(full_paths),
                "kg_snapshot_id": config.kg_snapshot_id,
                "kg_generations": _json(config.kg_generations),
                "context_intersection": _json(chosen["context"]),
                "canonical_observed_overlap": overlap,
                "observed_antijoin_status": "overlaps_observed_relation" if overlap else "missing_from_observed_relation",
                "absence_is_not_biological_negation": True,
                "derivation_hash": _sha(derivation_payload),
            }
        )
        result.append(row)
    return result


def _registry_json() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": rule.rule_id,
            "version": rule.version,
            "premises": [premise.__dict__ for premise in rule.premises],
            "conclusion": rule.conclusion.__dict__,
            "epistemic_class": rule.epistemic_class.value,
            "required_evidence": rule.required_evidence,
            "forbidden_evidence": rule.forbidden_evidence,
            "context_join_keys": rule.context_join_keys,
            "sign_algebra": rule.sign_algebra,
            "quantifier": rule.quantifier,
            "fail_closed_conditions": rule.fail_closed_conditions,
        }
        for rule in RULES_BY_ID.values()
    ]


def _replace_parquet_pair(
    edge_path: Path,
    edge_rows: list[dict[str, Any]],
    evidence_path: Path,
    evidence_rows: list[dict[str, Any]],
) -> None:
    """Replace or remove a rule-owned edge/evidence pair with rollback on failure."""
    paths_and_rows = ((edge_path, edge_rows), (evidence_path, evidence_rows))
    transaction_id = uuid.uuid4().hex
    temporary: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    installed: set[Path] = set()
    try:
        for path, rows in paths_and_rows:
            if not rows:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = path.with_name(f".{path.name}.{transaction_id}.tmp")
            pd.DataFrame(rows).to_parquet(temporary_path, index=False)
            temporary[path] = temporary_path
        for path, _rows in paths_and_rows:
            if path.exists():
                backup_path = path.with_name(f".{path.name}.{transaction_id}.bak")
                os.replace(path, backup_path)
                backups[path] = backup_path
        for path, _rows in paths_and_rows:
            if path in temporary:
                os.replace(temporary[path], path)
                installed.add(path)
    except Exception:
        for path in installed:
            path.unlink(missing_ok=True)
        for path, backup_path in backups.items():
            if backup_path.exists():
                os.replace(backup_path, path)
        raise
    else:
        for backup_path in backups.values():
            backup_path.unlink(missing_ok=True)
    finally:
        for temporary_path in temporary.values():
            temporary_path.unlink(missing_ok=True)


def build_inferred_edges(config: BuildConfig) -> dict[str, Any]:
    """Build a bounded, deterministic staged inferred layer from an immutable snapshot."""
    if not config.kg_snapshot_id or "immutable" not in config.kg_snapshot_id.lower() and not config.kg_generations:
        raise ValueError("An immutable kg_snapshot_id or object generations are required")
    unknown = set(config.rule_ids) - set(RULES_BY_ID)
    if unknown:
        raise ValueError(f"Unknown/unapproved rule IDs: {sorted(unknown)}")
    kg_root = config.kg_root.resolve()
    output_root = config.output_root.resolve()
    if output_root == kg_root or kg_root in output_root.parents:
        raise ValueError("Output must remain outside the read-only immutable snapshot")
    if any(part in {"edges", "evidence"} for part in config.output_root.parts):
        raise ValueError("Output root must not be canonical edges/ or evidence/")

    relation_names = {
        premise.relation
        for rule_id in config.rule_ids
        for premise in RULES_BY_ID[rule_id].premises
    }
    if any(rule_id.startswith("signed_target_mechanism_") for rule_id in config.rule_ids):
        relation_names.update({"disease_manifests_in_tissue", "tissue_expresses_gene", "tissue_expresses_protein"})
    relation_rows = {
        relation: _read_relation(
            config.kg_root,
            relation,
            required=relation in {premise.relation for rule_id in config.rule_ids for premise in RULES_BY_ID[rule_id].premises},
            max_rows=config.max_input_rows,
        )
        for relation in sorted(relation_names)
    }
    evidence_by_relation = {
        relation: _evidence_index(config.kg_root, relation, max_rows=config.max_input_rows)
        for relation in relation_rows
    }
    for relation, rows in relation_rows.items():
        for row in rows:
            evidence = evidence_by_relation[relation].get(str(row["edge_key"]), {})
            row["support_evidence_ids"] = list(evidence.get("ids", ()))
            row["support_evidence_fields"] = dict(evidence.get("fields", {}))
            row["support_evidence_conflicts"] = {
                field: list(values)
                for field, values in evidence.get("conflicts", {}).items()
            }
            row["support_evidence_records"] = list(evidence.get("records", ()))
    counts_by_rule: dict[str, dict[str, int]] = {}
    samples_by_rule: dict[str, list[dict[str, Any]]] = {}
    artifacts: dict[str, dict[str, str]] = {}

    for rule_id in config.rule_ids:
        rule = RULES_BY_ID[rule_id]
        generated, fail_closed = _generate(rule, relation_rows, config)
        finalized = _finalize_candidates(generated, rule, config, evidence_by_relation)
        overlap_count = sum(bool(row["canonical_observed_overlap"]) for row in finalized)
        counts_by_rule[rule_id] = {
            "candidate_rows": len(finalized),
            "strong_rows": sum(str(row["inference_strength"]).startswith("strong") for row in finalized),
            "hypothesis_rows": sum(row["inference_strength"] == "hypothesis" for row in finalized),
            "observed_overlap_rows": overlap_count,
            "missing_from_observed_rows": len(finalized) - overlap_count,
            "fail_closed_paths": fail_closed,
        }
        if rule_id == "variant_gene_disease_v1":
            counts_by_rule[rule_id]["support_family_rows"] = {
                family: sum(
                    row.get("c2_support_family") == family
                    for row in finalized
                )
                for family in sorted(
                    {
                        str(row["c2_support_family"])
                        for row in finalized
                        if row.get("c2_support_family")
                    }
                )
            }
        samples_by_rule[rule_id] = [
            {
                key: row[key]
                for key in (
                    "x_id",
                    "y_id",
                    "inference_strength",
                    "canonical_observed_overlap",
                    "derivation_hash",
                    "full_path",
                )
            }
            | {
                key: row[key]
                for key in ("c2_support_family", "c2_support_details")
                if key in row
            }
            for row in sorted(finalized, key=lambda item: (item["x_id"], item["y_id"], item["derivation_hash"]))[: config.sample_limit]
        ]
        edge_path = config.output_root / "edges_inferred" / rule.conclusion.relation / f"{rule_id}.parquet"
        evidence_path = config.output_root / "evidence_inferred" / rule.conclusion.relation / f"{rule_id}.parquet"
        evidence_rows = [
            {
                "inferred_edge_key": row["edge_key"],
                "derivation_hash": row["derivation_hash"],
                "relation": row["relation"],
                "x_id": row["x_id"],
                "y_id": row["y_id"],
                "inference_rule_id": row["inference_rule_id"],
                "support_edge_ids_or_hashes": row["support_edge_ids_or_hashes"],
                "support_evidence_ids_or_hashes": row["support_evidence_ids_or_hashes"],
                "full_path": row["full_path"],
                "kg_snapshot_id": row["kg_snapshot_id"],
                "kg_generations": row["kg_generations"],
                "context_intersection": row["context_intersection"],
                "sign_status": row["sign_status"],
                "inference_strength": row["inference_strength"],
            }
            for row in finalized
        ]
        _replace_parquet_pair(edge_path, finalized, evidence_path, evidence_rows)
        if finalized:
            artifacts[rule_id] = {"edges_inferred": str(edge_path), "evidence_inferred": str(evidence_path)}

    for deprecated_rule_id, relation in _DEPRECATED_RULE_ARTIFACTS.items():
        _replace_parquet_pair(
            config.output_root
            / "edges_inferred"
            / relation
            / f"{deprecated_rule_id}.parquet",
            [],
            config.output_root
            / "evidence_inferred"
            / relation
            / f"{deprecated_rule_id}.parquet",
            [],
        )

    manifest = {
        "status": "staged-only/review-required",
        "registry_version": "1.1.0",
        "kg_snapshot_id": config.kg_snapshot_id,
        "kg_generations": dict(config.kg_generations),
        "producer_revision": config.producer_revision,
        "bounds": {
            "max_anchors": config.max_anchors,
            "max_input_rows_per_file": config.max_input_rows,
        },
        "rules_requested": list(config.rule_ids),
        "excluded_motifs": dict(EXCLUDED_MOTIFS),
        "counts_by_rule": counts_by_rule,
        "top_candidate_samples": samples_by_rule,
        "artifacts": artifacts,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "claims": {"scientific_novelty": False, "literature_validated": False, "canonical_observed": False},
    }
    manifest_dir = config.output_root / "manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "rule_registry_v1.json").write_text(json.dumps(_registry_json(), indent=2, sort_keys=True) + "\n")
    (manifest_dir / "pilot_report.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
