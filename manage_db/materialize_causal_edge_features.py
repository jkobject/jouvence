"""Materialize source-backed causal/action/response features on staged edges.

The input edge and evidence tables remain authoritative for relation identity and
source assertions.  This module only adds deterministic optional columns.  It
never derives a feature from a relation name, a direct edge shortcut, generic
variant consequence text, or a quantitative sign without explicit source
polarity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

CONTRACT_VERSION = "causal-edge-features-v1"
AGGREGATION_STATES = ("single", "consensus", "conflicting", "unknown")
STAGING_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "staged"

ACTION_NORMALIZATION: dict[str, tuple[str, str, str]] = {
    "INHIBITOR": ("inhibitor", "negative", "decrease"),
    "ANTISENSE INHIBITOR": ("inhibitor", "negative", "decrease"),
    "RNAI INHIBITOR": ("inhibitor", "negative", "decrease"),
    "ANTAGONIST": ("antagonist", "negative", "decrease"),
    "ALLOSTERIC ANTAGONIST": ("antagonist", "negative", "decrease"),
    "INVERSE AGONIST": ("antagonist", "negative", "decrease"),
    "BLOCKER": ("blocker", "negative", "decrease"),
    "DEGRADER": ("degrader", "negative", "decrease"),
    "NEGATIVE MODULATOR": ("inhibitor", "negative", "decrease"),
    "NEGATIVE ALLOSTERIC MODULATOR": ("inhibitor", "negative", "decrease"),
    "GENE EDITING NEGATIVE MODULATOR": ("inhibitor", "negative", "decrease"),
    "AGONIST": ("agonist", "positive", "increase"),
    "PARTIAL AGONIST": ("agonist", "positive", "increase"),
    "ACTIVATOR": ("activator", "positive", "increase"),
    "POSITIVE MODULATOR": ("activator", "positive", "increase"),
    "POSITIVE ALLOSTERIC MODULATOR": ("activator", "positive", "increase"),
    "OPENER": ("activator", "positive", "increase"),
    "BINDING AGENT": ("binder_unknown_effect", "unknown", "binding"),
}

CAUSAL_MECHANISMS = {
    "loss_of_function",
    "gain_of_function",
    "dominant_negative",
    "haploinsufficiency",
    "dosage_gain",
    "hypomorphic",
}
EFFECT_DIRECTIONS = {"risk", "protective", "protection"}
RESPONSE_DIRECTIONS = {
    "sensitive",
    "resistant",
    "increased_efficacy",
    "decreased_efficacy",
    "increased_toxicity",
    "decreased_toxicity",
    "increased_exposure",
    "decreased_exposure",
}
RESPONSE_CATEGORY_NORMALIZATION = {
    "efficacy": "efficacy",
    "toxicity": "toxicity",
    "dosage": "dosage",
    "dose": "dosage",
    "metabolism/pk": "metabolism_pk",
    "metabolism_pk": "metabolism_pk",
    "metabolism": "metabolism_pk",
    "pk": "metabolism_pk",
}
CLINICAL_SIGNIFICANCE_NORMALIZATION = {
    "LP/P": "likely_pathogenic_or_pathogenic",
    "P/LP": "likely_pathogenic_or_pathogenic",
    "LB/B": "likely_benign_or_benign",
    "B/LB": "likely_benign_or_benign",
    "US": "uncertain_significance",
    "VUS": "uncertain_significance",
    "PATHOGENIC": "pathogenic",
    "LIKELY PATHOGENIC": "likely_pathogenic",
    "BENIGN": "benign",
    "LIKELY BENIGN": "likely_benign",
    "UNCERTAIN SIGNIFICANCE": "uncertain_significance",
}

RELATION_FEATURE_COLUMNS: dict[str, list[str]] = {
    "molecule_targets_gene": [
        "action_types",
        "action_direction",
        "target_modulation",
        "action_status",
        "evidence_count",
        "causal_feature_contract_version",
    ],
    "molecule_targets_protein": [
        "action_types",
        "action_direction",
        "target_modulation",
        "action_status",
        "evidence_count",
        "causal_feature_contract_version",
    ],
    "disease_associated_gene": [
        "causal_mechanisms",
        "mechanism_status",
        "effect_directions",
        "effect_direction_status",
        "inheritance_modes",
        "causal_support_level",
        "evidence_count",
        "causal_feature_contract_version",
    ],
    "disease_associated_protein": [
        "causal_mechanisms",
        "mechanism_status",
        "effect_directions",
        "effect_direction_status",
        "inheritance_modes",
        "causal_support_level",
        "evidence_count",
        "causal_feature_contract_version",
    ],
    "mutation_associated_disease": [
        "effect_alleles",
        "beta",
        "odds_ratio",
        "effect_directions",
        "clinical_significance",
        "germline_somatic",
        "association_status",
        "evidence_count",
        "causal_feature_contract_version",
    ],
    "mutation_affects_molecule_response": [
        "response_categories",
        "response_directions",
        "response_status",
        "disease_context_status",
        "evidence_count",
        "causal_feature_contract_version",
    ],
}

RELATION_ENDPOINT_TYPES: dict[str, tuple[str, str]] = {
    "molecule_targets_gene": ("molecule", "gene"),
    "molecule_targets_protein": ("molecule", "protein"),
    "disease_associated_gene": ("gene", "disease"),
    "disease_associated_protein": ("protein", "disease"),
    "mutation_associated_disease": ("mutation", "disease"),
    "mutation_affects_molecule_response": ("mutation", "molecule"),
}

RELATION_NORMALIZED_COLUMNS: dict[str, list[str]] = {
    "molecule_targets_gene": [
        "normalized_action_type",
        "normalized_action_direction",
        "normalized_target_modulation",
    ],
    "molecule_targets_protein": [
        "normalized_action_type",
        "normalized_action_direction",
        "normalized_target_modulation",
    ],
    "disease_associated_gene": [
        "normalized_causal_mechanism",
        "normalized_effect_direction",
        "normalized_inheritance_mode",
        "normalized_clinical_significance",
        "normalized_causal_support_level",
    ],
    "disease_associated_protein": [
        "normalized_causal_mechanism",
        "normalized_effect_direction",
        "normalized_inheritance_mode",
        "normalized_clinical_significance",
        "normalized_causal_support_level",
    ],
    "mutation_associated_disease": [
        "normalized_effect_allele",
        "normalized_beta",
        "normalized_odds_ratio",
        "normalized_effect_direction",
        "normalized_clinical_significance",
        "normalized_germline_somatic",
    ],
    "mutation_affects_molecule_response": [
        "normalized_response_category",
        "normalized_response_direction",
        "normalized_disease_context",
    ],
}

RELATION_USABLE_ASSERTION_COLUMNS: dict[str, list[str]] = {
    "molecule_targets_gene": ["normalized_action_type"],
    "molecule_targets_protein": ["normalized_action_type"],
    "disease_associated_gene": [
        "normalized_causal_mechanism",
        "normalized_effect_direction",
        "normalized_inheritance_mode",
        "normalized_clinical_significance",
        "normalized_causal_support_level",
    ],
    "disease_associated_protein": [
        "normalized_causal_mechanism",
        "normalized_effect_direction",
        "normalized_inheritance_mode",
        "normalized_clinical_significance",
        "normalized_causal_support_level",
    ],
    "mutation_associated_disease": [
        "normalized_effect_allele",
        "normalized_beta",
        "normalized_odds_ratio",
        "normalized_effect_direction",
        "normalized_clinical_significance",
        "normalized_germline_somatic",
    ],
    "mutation_affects_molecule_response": [
        "normalized_response_category",
        "normalized_response_direction",
    ],
}


def _clean(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _snake(value: object) -> str:
    return "_".join(_clean(value).lower().replace("/", " ").replace("-", " ").split())


def _json_values(values: Iterable[object]) -> str:
    clean = sorted({_clean(value) for value in values if _clean(value)})
    return json.dumps(clean, separators=(",", ":"))


def _edge_key(relation: str, x_id: object, y_id: object) -> str:
    return f"{relation}|{_clean(x_id)}|{_clean(y_id)}"


def _coalesce_columns(frame: pd.DataFrame, columns: Iterable[str]) -> pd.Series:
    result = pd.Series("", index=frame.index, dtype="object")
    for column in columns:
        if column not in frame:
            continue
        candidate = frame[column]
        result = result.where(result.map(_clean).ne(""), candidate)
    return result


def _assertion_id(row: pd.Series) -> str:
    explicit = _clean(row.get("source_assertion_id"))
    record_id = _clean(row.get("source_record_id"))
    dataset = _clean(row.get("source_dataset"))
    if dataset == "reviewed_human_disease_comments" and ":PMID:" in record_id:
        record_id = record_id.split(":PMID:", 1)[0]
    assertion = explicit or record_id
    if assertion:
        return "|".join(
            (
                _clean(row.get("relation")),
                _clean(row.get("x_id")),
                _clean(row.get("y_id")),
                _clean(row.get("source")),
                dataset,
                assertion,
            )
        )
    payload = json.dumps(
        {str(column): _clean(value) for column, value in row.items()},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _normalise_evidence(evidence: pd.DataFrame, relation: str) -> pd.DataFrame:
    out = evidence.copy()
    canonical_edge_keys = pd.Series(
        [_edge_key(relation, x_id, y_id) for x_id, y_id in zip(out["x_id"], out["y_id"], strict=False)],
        index=out.index,
    )
    if "edge_key" in out:
        mismatch = out["edge_key"].map(_clean) != canonical_edge_keys
        if mismatch.any():
            raise ValueError(f"evidence/{relation} edge_key does not match relation/x_id/y_id")
    else:
        out["edge_key"] = canonical_edge_keys
    out["materialization_assertion_id"] = out.apply(_assertion_id, axis=1)
    if "source_assertion_id" not in out:
        out["source_assertion_id"] = out["materialization_assertion_id"]

    semantic_values = pd.DataFrame(index=out.index)
    if relation.startswith("molecule_targets_"):
        raw_actions = _coalesce_columns(out, ("action_type", "predicate"))
        semantic_values["raw_action"] = raw_actions.map(_clean)
        normalized = raw_actions.map(lambda value: ACTION_NORMALIZATION.get(_clean(value).upper(), ("", "", "")))
        out["normalized_action_type"] = normalized.map(lambda value: value[0])
        out["normalized_action_direction"] = normalized.map(lambda value: value[1])
        out["normalized_target_modulation"] = normalized.map(lambda value: value[2])

    elif relation.startswith("disease_associated_"):
        raw_mechanisms = _coalesce_columns(out, ("causal_mechanism", "mechanism"))
        raw_directions = _coalesce_columns(out, ("effect_direction", "direction"))
        raw_inheritance = _coalesce_columns(out, ("inheritance_mode", "inheritance"))
        raw_significance = _coalesce_columns(out, ("clinical_significance", "variant_category"))
        semantic_values = pd.DataFrame(
            {
                "raw_mechanism": raw_mechanisms.map(_clean),
                "raw_direction": raw_directions.map(_clean),
                "raw_inheritance": raw_inheritance.map(_clean),
                "raw_significance": raw_significance.map(_clean),
            },
            index=out.index,
        )
        mechanisms = raw_mechanisms.map(_snake)
        out["normalized_causal_mechanism"] = mechanisms.where(mechanisms.isin(CAUSAL_MECHANISMS), "")
        directions = raw_directions.map(_snake)
        out["normalized_effect_direction"] = directions.where(directions.isin(EFFECT_DIRECTIONS), "").replace(
            "protection", "protective"
        )
        out["normalized_inheritance_mode"] = raw_inheritance.map(_snake)
        category = out.get("variant_category", pd.Series("", index=out.index)).map(
            lambda value: CLINICAL_SIGNIFICANCE_NORMALIZATION.get(_clean(value).upper(), "")
        )
        explicit = _coalesce_columns(out, ("clinical_significance",)).map(
            lambda value: CLINICAL_SIGNIFICANCE_NORMALIZATION.get(_clean(value).upper(), _snake(value))
        )
        out["normalized_clinical_significance"] = explicit.where(explicit != "", category)
        datasets = out.get("source_dataset", pd.Series("", index=out.index)).map(_clean)
        out["normalized_causal_support_level"] = datasets.map(
            {
                "reviewed_human_disease_comments": "source_backed_disease_assertion",
                "humsavar_missense_variants": "source_backed_variant_disease_assertion",
            }
        ).fillna("source_backed_association")

    elif relation == "mutation_associated_disease":
        raw_allele = _coalesce_columns(out, ("effect_allele",))
        raw_beta = _coalesce_columns(out, ("beta",))
        raw_odds_ratio = _coalesce_columns(out, ("odds_ratio", "oddsRatio"))
        raw_direction = _coalesce_columns(out, ("effect_direction", "direction"))
        raw_significance = _coalesce_columns(out, ("clinical_significance",))
        raw_origin = _coalesce_columns(out, ("germline_somatic", "genetic_origin"))
        semantic_values = pd.DataFrame(
            {
                "raw_allele": raw_allele.map(_clean),
                "raw_beta": raw_beta.map(_clean),
                "raw_odds_ratio": raw_odds_ratio.map(_clean),
                "raw_direction": raw_direction.map(_clean),
                "raw_significance": raw_significance.map(_clean),
                "raw_origin": raw_origin.map(_clean),
            },
            index=out.index,
        )
        out["normalized_effect_allele"] = raw_allele.map(_clean)
        out["normalized_beta"] = pd.to_numeric(raw_beta, errors="coerce")
        out["normalized_odds_ratio"] = pd.to_numeric(raw_odds_ratio, errors="coerce")
        explicit_direction = raw_direction.map(_snake)
        out["normalized_effect_direction"] = explicit_direction.where(
            explicit_direction.isin(EFFECT_DIRECTIONS), ""
        ).replace("protection", "protective")
        out["normalized_clinical_significance"] = raw_significance.map(
            lambda value: CLINICAL_SIGNIFICANCE_NORMALIZATION.get(_clean(value).upper(), _snake(value))
        )
        out["normalized_germline_somatic"] = raw_origin.map(_snake)

    elif relation == "mutation_affects_molecule_response":
        raw_categories = _coalesce_columns(out, ("response_category", "pgx_category", "predicate"))
        raw_directions = _coalesce_columns(out, ("response_direction", "direction"))
        raw_contexts = _coalesce_columns(out, ("disease_id", "disease_context"))
        semantic_values = pd.DataFrame(
            {
                "raw_category": raw_categories.map(_clean),
                "raw_direction": raw_directions.map(_clean),
                "raw_context": raw_contexts.map(_clean),
            },
            index=out.index,
        )
        out["normalized_response_category"] = raw_categories.map(
            lambda value: RESPONSE_CATEGORY_NORMALIZATION.get(_clean(value).lower(), "")
        )
        normalized_directions = raw_directions.map(_snake)
        out["normalized_response_direction"] = normalized_directions.where(
            normalized_directions.isin(RESPONSE_DIRECTIONS), ""
        )
        out["normalized_disease_context"] = raw_contexts.map(_clean)

    semantic_payload = semantic_values.apply(
        lambda row: json.dumps(row.map(_clean).to_dict(), sort_keys=True, separators=(",", ":")),
        axis=1,
    )
    semantic_variants = semantic_payload.groupby(out["materialization_assertion_id"]).transform("nunique")
    out["materialization_assertion_conflict"] = semantic_variants.gt(1)
    return out


def _assertion_count(group: pd.DataFrame, relation: str) -> int:
    usable = pd.Series(False, index=group.index)
    for column in RELATION_USABLE_ASSERTION_COLUMNS[relation]:
        usable |= group[column].map(_clean).map(lambda value: value not in {"", "unknown"})
    return int(
        group.loc[usable, "materialization_assertion_id"].map(_clean).replace("", pd.NA).nunique()
    )


def _feature_status(group: pd.DataFrame, column: str, *, conflicts: bool | None = None) -> str:
    if group.get("materialization_assertion_conflict", pd.Series(False, index=group.index)).any():
        return "conflicting"
    usable = group[group[column].map(_clean).map(lambda value: value not in {"", "unknown"})]
    if usable.empty:
        return "unknown"
    values = set(usable[column].map(_clean))
    if conflicts is True or (conflicts is None and len(values) > 1):
        return "conflicting"
    supporting_assertions = usable["materialization_assertion_id"].map(_clean).replace("", pd.NA).nunique()
    return "single" if supporting_assertions == 1 else "consensus"


def _aggregate_action(group: pd.DataFrame) -> dict[str, object]:
    action_types = group["normalized_action_type"].tolist()
    directions = group["normalized_action_direction"].tolist()
    modulations = group["normalized_target_modulation"].tolist()
    direction_set = {_clean(value) for value in directions if _clean(value) not in {"", "unknown"}}
    conflicting = "positive" in direction_set and "negative" in direction_set
    return {
        "action_types": _json_values(action_types),
        "action_direction": _json_values(directions),
        "target_modulation": _json_values(modulations),
        "action_status": _feature_status(group, "normalized_action_type", conflicts=conflicting),
        "evidence_count": _assertion_count(group, "molecule_targets_protein"),
    }


def _aggregate_disease(group: pd.DataFrame) -> dict[str, object]:
    mechanisms = group["normalized_causal_mechanism"].tolist()
    directions = group["normalized_effect_direction"].tolist()
    inheritance = group["normalized_inheritance_mode"].tolist()
    support = sorted(set(group["normalized_causal_support_level"].map(_clean)) - {""})
    if not support:
        support_level = "unknown"
    elif len(support) == 1:
        support_level = support[0]
    else:
        support_level = "mixed_source_backed_assertions"
    return {
        "causal_mechanisms": _json_values(mechanisms),
        "mechanism_status": _feature_status(group, "normalized_causal_mechanism"),
        "effect_directions": _json_values(directions),
        "effect_direction_status": _feature_status(group, "normalized_effect_direction"),
        "inheritance_modes": _json_values(inheritance),
        "causal_support_level": support_level,
        "evidence_count": _assertion_count(group, "disease_associated_protein"),
    }


def _numeric_json(values: pd.Series) -> str:
    return json.dumps(sorted({float(value) for value in values.dropna()}), separators=(",", ":"))


def _aggregate_mutation_disease(group: pd.DataFrame) -> dict[str, object]:
    directions = group["normalized_effect_direction"].tolist()
    return {
        "effect_alleles": _json_values(group["normalized_effect_allele"]),
        "beta": _numeric_json(group["normalized_beta"]),
        "odds_ratio": _numeric_json(group["normalized_odds_ratio"]),
        "effect_directions": _json_values(directions),
        "clinical_significance": _json_values(group["normalized_clinical_significance"]),
        "germline_somatic": _json_values(group["normalized_germline_somatic"]),
        "association_status": _feature_status(group, "normalized_effect_direction"),
        "evidence_count": _assertion_count(group, "mutation_associated_disease"),
    }


def _aggregate_response(group: pd.DataFrame) -> dict[str, object]:
    categories = group["normalized_response_category"].tolist()
    directions = group["normalized_response_direction"].tolist()
    direction_set = {_clean(value) for value in directions if _clean(value)}
    conflict_pairs = [
        {"sensitive", "resistant"},
        {"increased_efficacy", "decreased_efficacy"},
        {"increased_toxicity", "decreased_toxicity"},
        {"increased_exposure", "decreased_exposure"},
    ]
    conflicting = any(pair <= direction_set for pair in conflict_pairs)
    status_group = group.copy()
    status_group["normalized_response_assertion"] = [
        category or direction for category, direction in zip(categories, directions, strict=False)
    ]
    return {
        "response_categories": _json_values(categories),
        "response_directions": _json_values(directions),
        "response_status": _feature_status(
            status_group, "normalized_response_assertion", conflicts=conflicting
        ),
        "disease_context_status": _feature_status(group, "normalized_disease_context"),
        "evidence_count": _assertion_count(group, "mutation_affects_molecule_response"),
    }


def materialize_relation(
    edges: pd.DataFrame,
    evidence: pd.DataFrame,
    relation: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Return edge/evidence copies enriched solely from row-level evidence."""

    if relation not in RELATION_FEATURE_COLUMNS:
        raise ValueError(f"unsupported causal-feature relation: {relation}")
    for frame_name, frame in (("edges", edges), ("evidence", evidence)):
        required = {"relation", "x_id", "x_type", "y_id", "y_type"}
        if frame_name == "evidence":
            required.update({"source", "source_dataset", "source_record_id"})
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{frame_name}/{relation} missing columns: {missing}")
        blank = sorted(column for column in required if frame[column].map(_clean).eq("").any())
        if blank:
            raise ValueError(f"{frame_name}/{relation} has blank required values: {blank}")
        if not frame.empty and set(frame["relation"].map(_clean)) != {relation}:
            raise ValueError(f"{frame_name}/{relation} contains another relation")
        expected_x_type, expected_y_type = RELATION_ENDPOINT_TYPES[relation]
        endpoint_types = set(
            zip(frame["x_type"].map(_clean), frame["y_type"].map(_clean), strict=False)
        )
        if endpoint_types - {(expected_x_type, expected_y_type)}:
            raise ValueError(
                f"{frame_name}/{relation} has invalid endpoint types: {sorted(endpoint_types)}"
            )

    edge_collisions = sorted(set(edges.columns) & set(RELATION_FEATURE_COLUMNS[relation]))
    evidence_collisions = sorted(
        column
        for column in evidence.columns
        if column == "causal_feature_contract_version"
        or column.startswith("materialization_")
        or column.startswith("normalized_")
    )
    if edge_collisions or evidence_collisions:
        raise ValueError(
            f"{relation} already contains materialized columns: "
            f"edges={edge_collisions}, evidence={evidence_collisions}"
        )

    enriched_evidence = _normalise_evidence(evidence, relation)
    enriched_edges = edges.copy().reset_index(drop=True)
    edge_keys = [
        _edge_key(relation, x_id, y_id)
        for x_id, y_id in zip(enriched_edges["x_id"], enriched_edges["y_id"], strict=False)
    ]
    groups = {key: group for key, group in enriched_evidence.groupby("edge_key", sort=False)}

    if relation.startswith("molecule_targets_"):
        aggregator = _aggregate_action
    elif relation.startswith("disease_associated_"):
        aggregator = _aggregate_disease
    elif relation == "mutation_associated_disease":
        aggregator = _aggregate_mutation_disease
    else:
        aggregator = _aggregate_response

    aggregates: list[dict[str, object]] = []
    for key in edge_keys:
        group = groups.get(key)
        if group is None:
            group = enriched_evidence.iloc[0:0].copy()
        aggregates.append(aggregator(group))
    aggregate_frame = pd.DataFrame(aggregates, index=enriched_edges.index)
    for column in aggregate_frame.columns:
        enriched_edges[column] = aggregate_frame[column]
    enriched_edges["causal_feature_contract_version"] = CONTRACT_VERSION
    enriched_evidence["causal_feature_contract_version"] = CONTRACT_VERSION

    validation_errors = validate_staged_relation(enriched_edges, enriched_evidence, relation)
    status_columns = [column for column in enriched_edges.columns if column.endswith("_status")]
    status_counts = {
        column: {str(key): int(value) for key, value in enriched_edges[column].value_counts(dropna=False).items()}
        for column in status_columns
    }
    edge_source_counts = enriched_edges.get("source", pd.Series(dtype=str)).map(_clean).value_counts()
    evidence_source_counts = enriched_evidence.get("source", pd.Series(dtype=str)).map(_clean).value_counts()
    source_summary = {
        source: {
            "edge_rows": int(edge_source_counts.get(source, 0)),
            "evidence_rows": int(evidence_source_counts.get(source, 0)),
        }
        for source in sorted((set(edge_source_counts.index) | set(evidence_source_counts.index)) - {""})
    }
    availability_fields = {
        "molecule_targets_gene": [
            "normalized_action_type",
            "normalized_action_direction",
            "normalized_target_modulation",
        ],
        "molecule_targets_protein": [
            "normalized_action_type",
            "normalized_action_direction",
            "normalized_target_modulation",
        ],
        "disease_associated_gene": [
            "normalized_causal_mechanism",
            "normalized_effect_direction",
            "normalized_inheritance_mode",
        ],
        "disease_associated_protein": [
            "normalized_causal_mechanism",
            "normalized_effect_direction",
            "normalized_inheritance_mode",
        ],
        "mutation_associated_disease": [
            "normalized_effect_allele",
            "normalized_beta",
            "normalized_odds_ratio",
            "normalized_effect_direction",
            "normalized_clinical_significance",
            "normalized_germline_somatic",
        ],
        "mutation_affects_molecule_response": [
            "normalized_response_category",
            "normalized_response_direction",
            "normalized_disease_context",
        ],
    }[relation]
    fields_still_unavailable = [
        field
        for field in availability_fields
        if field not in enriched_evidence
        or not enriched_evidence[field].map(_clean).ne("").any()
    ]
    report = {
        "relation": relation,
        "edge_rows": int(len(enriched_edges)),
        "evidence_rows": int(len(enriched_evidence)),
        "status_counts": status_counts,
        "source_counts": {
            str(key): int(value)
            for key, value in enriched_evidence.get("source", pd.Series(dtype=str)).value_counts().items()
        },
        "source_summary": source_summary,
        "source_fields_preserved": sorted(evidence.columns.astype(str).tolist()),
        "fields_still_unavailable": fields_still_unavailable,
        "feature_columns_added_to_edges": [
            column for column in RELATION_FEATURE_COLUMNS[relation] if column not in edges.columns
        ],
        "feature_columns_added_to_evidence": sorted(set(enriched_evidence.columns) - set(evidence.columns)),
        "validation_errors": validation_errors,
    }
    return enriched_edges, enriched_evidence, report


def validate_staged_relation(edges: pd.DataFrame, evidence: pd.DataFrame, relation: str) -> list[str]:
    errors: list[str] = []
    if relation not in RELATION_FEATURE_COLUMNS:
        return [f"unsupported relation: {relation}"]
    missing_edge_features = sorted(set(RELATION_FEATURE_COLUMNS[relation]) - set(edges.columns))
    if missing_edge_features:
        errors.append(f"missing feature columns: {missing_edge_features}")
    required_evidence_features = {
        "edge_key",
        "materialization_assertion_id",
        "materialization_assertion_conflict",
        "causal_feature_contract_version",
        *RELATION_NORMALIZED_COLUMNS[relation],
    }
    missing_evidence_features = sorted(required_evidence_features - set(evidence.columns))
    if missing_evidence_features:
        errors.append(f"missing normalized evidence columns: {missing_evidence_features}")
    if set(edges.get("relation", pd.Series(dtype=str)).map(_clean)) not in ({relation}, set()):
        errors.append("edge relation drift")
    if set(evidence.get("relation", pd.Series(dtype=str)).map(_clean)) not in ({relation}, set()):
        errors.append("evidence relation drift")
    expected_types = RELATION_ENDPOINT_TYPES[relation]
    for frame_name, frame in (("edges", edges), ("evidence", evidence)):
        identity_columns = {"relation", "x_id", "x_type", "y_id", "y_type"}
        if frame_name == "evidence":
            identity_columns.update({"source", "source_dataset", "source_record_id"})
        missing_identity = sorted(identity_columns - set(frame.columns))
        if missing_identity:
            errors.append(f"{frame_name} missing identity columns: {missing_identity}")
            continue
        blank_identity = sorted(
            column for column in identity_columns if frame[column].map(_clean).eq("").any()
        )
        if blank_identity:
            errors.append(f"{frame_name} blank identity values: {blank_identity}")
        endpoint_types = set(
            zip(frame["x_type"].map(_clean), frame["y_type"].map(_clean), strict=False)
        )
        if endpoint_types - {expected_types}:
            errors.append(f"{frame_name} endpoint types mismatch: {sorted(endpoint_types)}")
    for column in [name for name in edges.columns if name.endswith("_status")]:
        invalid = sorted(set(edges[column].map(_clean)) - set(AGGREGATION_STATES))
        if invalid:
            errors.append(f"{column} has invalid states: {invalid}")
    edge_keys = {
        _edge_key(relation, x_id, y_id) for x_id, y_id in zip(edges.get("x_id", []), edges.get("y_id", []), strict=False)
    }
    evidence_keys = set(evidence.get("edge_key", pd.Series(dtype=str)).map(_clean))
    if {"x_id", "y_id", "edge_key"}.issubset(evidence.columns):
        canonical_evidence_keys = pd.Series(
            [
                _edge_key(relation, x_id, y_id)
                for x_id, y_id in zip(evidence["x_id"], evidence["y_id"], strict=False)
            ],
            index=evidence.index,
        )
        if (evidence["edge_key"].map(_clean) != canonical_evidence_keys).any():
            errors.append("evidence edge_key does not match relation/x_id/y_id")
    if evidence_keys - edge_keys:
        errors.append(f"evidence without edge: {len(evidence_keys - edge_keys)}")
    if edge_keys - evidence_keys:
        errors.append(f"edges without evidence: {len(edge_keys - evidence_keys)}")
    for frame_name, frame in (("edge", edges), ("evidence", evidence)):
        if "causal_feature_contract_version" not in frame:
            errors.append(f"{frame_name} contract version missing")
        elif set(frame["causal_feature_contract_version"].map(_clean)) != {CONTRACT_VERSION}:
            errors.append(f"{frame_name} contract version mismatch")
    return errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _refuse_unsafe_path(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved.startswith("/Users/jkobject/mnt/gcs") or resolved.startswith("/mnt/gcs"):
        raise ValueError(f"FUSE/canonical paths are forbidden for this local staged build: {resolved}")


def _validate_output_path(path: Path, task_id: str) -> None:
    if re.fullmatch(r"t_[0-9A-Za-z]+", task_id) is None:
        raise ValueError(f"invalid task id for staged output: {task_id!r}")
    resolved = path.resolve()
    task_root = (STAGING_ROOT / task_id).resolve()
    try:
        resolved.relative_to(task_root)
    except ValueError as exc:
        raise ValueError(f"output must be under artifacts/staged/{task_id}: {resolved}") from exc


def stage_relations(
    *,
    inputs: Mapping[str, Mapping[str, Path]],
    output_root: Path,
    source_revision: str,
    task_id: str,
) -> dict[str, Any]:
    """Write immutable staged outputs and a machine-readable validation receipt."""

    _refuse_unsafe_path(output_root)
    _validate_output_path(output_root, task_id)
    if output_root.resolve() != (STAGING_ROOT / task_id).resolve():
        raise ValueError(f"output root must equal artifacts/staged/{task_id}: {output_root.resolve()}")
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"immutable staging root already contains files: {output_root}")
    (output_root / "edges").mkdir(parents=True, exist_ok=True)
    (output_root / "evidence").mkdir(parents=True, exist_ok=True)
    (output_root / "reports").mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "task_id": task_id,
        "contract_version": CONTRACT_VERSION,
        "source_revision": source_revision,
        "staging_only": True,
        "canonical_write": False,
        "relations": {},
        "legacy_contraindication_pairs": {
            "relation": "molecule_contraindicates_disease",
            "distinct_pairs": 30675,
            "evidence_assertions": 0,
            "usable_for_sign": False,
            "usable_for_anti_join_completeness": False,
        },
    }
    for relation, paths in inputs.items():
        edge_input = Path(paths["edges"])
        evidence_input = Path(paths["evidence"])
        _refuse_unsafe_path(edge_input)
        _refuse_unsafe_path(evidence_input)
        edges = pd.read_parquet(edge_input)
        evidence = pd.read_parquet(evidence_input)
        identity_before = edges[["x_id", "y_id", "relation"]].astype(str).reset_index(drop=True)
        edge_schema_before = {column: str(dtype) for column, dtype in edges.dtypes.items()}
        evidence_schema_before = {column: str(dtype) for column, dtype in evidence.dtypes.items()}

        staged_edges, staged_evidence, report = materialize_relation(edges, evidence, relation)
        edge_output = output_root / "edges" / f"{relation}.parquet"
        evidence_output = output_root / "evidence" / f"{relation}.parquet"
        staged_edges.to_parquet(edge_output, index=False)
        staged_evidence.to_parquet(evidence_output, index=False)
        identity_after = staged_edges[["x_id", "y_id", "relation"]].astype(str).reset_index(drop=True)
        validation = {
            "edge_identity_unchanged": bool(identity_before.equals(identity_after)),
            "edge_row_conservation": int(len(edges)) == int(len(staged_edges)),
            "source_edge_values_unchanged": edges.reset_index(drop=True).equals(
                staged_edges[edges.columns].reset_index(drop=True)
            ),
            "evidence_row_conservation": int(len(evidence)) == int(len(staged_evidence)),
            "source_evidence_unchanged": evidence.reset_index(drop=True).equals(
                staged_evidence[evidence.columns].reset_index(drop=True)
            ),
            "errors": validate_staged_relation(staged_edges, staged_evidence, relation),
        }
        if not all(
            [
                validation["edge_identity_unchanged"],
                validation["edge_row_conservation"],
                validation["source_edge_values_unchanged"],
                validation["evidence_row_conservation"],
                validation["source_evidence_unchanged"],
                not validation["errors"],
            ]
        ):
            raise ValueError(f"staged validation failed for {relation}: {validation}")
        manifest["relations"][relation] = {
            **report,
            "inputs": {
                "edges": str(edge_input),
                "evidence": str(evidence_input),
                "edge_sha256": _sha256(edge_input),
                "evidence_sha256": _sha256(evidence_input),
            },
            "outputs": {
                "edges": str(edge_output.resolve()),
                "evidence": str(evidence_output.resolve()),
                "edge_sha256": _sha256(edge_output),
                "evidence_sha256": _sha256(evidence_output),
            },
            "schema_before": {"edges": edge_schema_before, "evidence": evidence_schema_before},
            "schema_after": {
                "edges": {column: str(dtype) for column, dtype in staged_edges.dtypes.items()},
                "evidence": {column: str(dtype) for column, dtype in staged_evidence.dtypes.items()},
            },
            "validation": validation,
        }

    manifest_path = output_root / "reports" / "materialization_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    manifest["manifest_sha256"] = _sha256(manifest_path)
    return manifest


def validate_manifest(
    manifest_path: Path,
    *,
    expected_task_id: str,
    expected_relations: set[str],
) -> list[str]:
    """Validate staged files, receipts, conservation, and relation identity."""

    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    expected_root = (STAGING_ROOT / expected_task_id).resolve()
    expected_manifest_path = expected_root / "reports" / "materialization_manifest.json"
    if manifest_path.resolve() != expected_manifest_path:
        errors.append(f"manifest is outside expected task root: {expected_manifest_path}")
    if manifest.get("task_id") != expected_task_id:
        errors.append(
            f"manifest task {manifest.get('task_id')!r} does not match expected task {expected_task_id!r}"
        )
    if manifest.get("contract_version") != CONTRACT_VERSION:
        errors.append("contract version mismatch")
    if manifest.get("staging_only") is not True or manifest.get("canonical_write") is not False:
        errors.append("manifest is not staged-only")
    contraindication = manifest.get("legacy_contraindication_pairs", {})
    if contraindication != {
        "relation": "molecule_contraindicates_disease",
        "distinct_pairs": 30675,
        "evidence_assertions": 0,
        "usable_for_sign": False,
        "usable_for_anti_join_completeness": False,
    }:
        errors.append("legacy contraindication fail-closed receipt mismatch")

    manifest_relations = set(manifest.get("relations", {}))
    missing_relations = sorted(expected_relations - manifest_relations)
    unexpected_relations = sorted(manifest_relations - expected_relations)
    if missing_relations:
        errors.append(f"missing expected relations: {missing_relations}")
    if unexpected_relations:
        errors.append(f"unexpected relations: {unexpected_relations}")

    for relation, receipt in manifest.get("relations", {}).items():
        if relation not in RELATION_FEATURE_COLUMNS:
            errors.append(f"forbidden relation-name alias: {relation}")
            continue
        input_edges = Path(receipt["inputs"]["edges"])
        input_evidence = Path(receipt["inputs"]["evidence"])
        output_edges = Path(receipt["outputs"]["edges"])
        output_evidence = Path(receipt["outputs"]["evidence"])
        for output_path in (output_edges, output_evidence):
            try:
                _validate_output_path(output_path, expected_task_id)
            except ValueError as exc:
                errors.append(f"{relation} {exc}")
        expected_edge_output = expected_root / "edges" / f"{relation}.parquet"
        expected_evidence_output = expected_root / "evidence" / f"{relation}.parquet"
        if output_edges.resolve() != expected_edge_output:
            errors.append(f"{relation} edge output path mismatch")
        if output_evidence.resolve() != expected_evidence_output:
            errors.append(f"{relation} evidence output path mismatch")
        for label, path, expected_sha in (
            ("input edges", input_edges, receipt["inputs"]["edge_sha256"]),
            ("input evidence", input_evidence, receipt["inputs"]["evidence_sha256"]),
            ("output edges", output_edges, receipt["outputs"]["edge_sha256"]),
            ("output evidence", output_evidence, receipt["outputs"]["evidence_sha256"]),
        ):
            if not path.exists():
                errors.append(f"{relation} {label} missing: {path}")
            elif _sha256(path) != expected_sha:
                errors.append(f"{relation} {label} sha256 mismatch")
        if not all(path.exists() for path in (input_edges, input_evidence, output_edges, output_evidence)):
            continue

        before_edges = pd.read_parquet(input_edges)
        before_evidence = pd.read_parquet(input_evidence)
        after_edges = pd.read_parquet(output_edges)
        after_evidence = pd.read_parquet(output_evidence)
        before_identity = before_edges[["x_id", "y_id", "relation"]].astype(str).reset_index(drop=True)
        after_identity = after_edges[["x_id", "y_id", "relation"]].astype(str).reset_index(drop=True)
        if not before_identity.equals(after_identity):
            errors.append(f"{relation} edge identity changed")
        if not set(before_edges.columns).issubset(after_edges.columns):
            errors.append(f"{relation} source edge columns were dropped")
        elif not before_edges.reset_index(drop=True).equals(
            after_edges[before_edges.columns].reset_index(drop=True)
        ):
            errors.append(f"{relation} source edge values changed")
        if len(before_evidence) != len(after_evidence):
            errors.append(f"{relation} evidence row conservation failed")
        if not set(before_evidence.columns).issubset(after_evidence.columns):
            errors.append(f"{relation} source evidence columns were dropped")
        elif not before_evidence.reset_index(drop=True).equals(
            after_evidence[before_evidence.columns].reset_index(drop=True)
        ):
            errors.append(f"{relation} source evidence values changed")
        try:
            expected_edges, expected_evidence, expected_report = materialize_relation(
                before_edges,
                before_evidence,
                relation,
            )
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{relation} source rematerialization failed: {exc}")
        else:
            try:
                pd.testing.assert_frame_equal(
                    expected_edges.reset_index(drop=True),
                    after_edges.reset_index(drop=True),
                    check_dtype=False,
                )
            except AssertionError:
                errors.append(f"{relation} materialized edge values changed")
            try:
                pd.testing.assert_frame_equal(
                    expected_evidence.reset_index(drop=True),
                    after_evidence.reset_index(drop=True),
                    check_dtype=False,
                )
            except AssertionError:
                errors.append(f"{relation} normalized evidence values changed")
            for key, expected_value in expected_report.items():
                if receipt.get(key) != expected_value:
                    errors.append(f"{relation} receipt field mismatch: {key}")
        errors.extend(
            f"{relation} {error}" for error in validate_staged_relation(after_edges, after_evidence, relation)
        )
    return errors


def _parse_input(specification: str) -> tuple[str, dict[str, Path]]:
    parts = specification.split("=", 1)
    if len(parts) != 2 or "," not in parts[1]:
        raise argparse.ArgumentTypeError("input must be RELATION=EDGE_PARQUET,EVIDENCE_PARQUET")
    relation, paths = parts
    edge_path, evidence_path = paths.split(",", 1)
    return relation, {"edges": Path(edge_path), "evidence": Path(evidence_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, help="RELATION=EDGE_PARQUET,EVIDENCE_PARQUET")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args(argv)
    inputs = dict(_parse_input(value) for value in args.input)
    manifest = stage_relations(
        inputs=inputs,
        output_root=args.output_root,
        source_revision=args.source_revision,
        task_id=args.task_id,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
