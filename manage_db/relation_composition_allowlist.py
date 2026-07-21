"""Fail-closed staged executor for the approved Jouvence composition allowlist.

The executor never writes observed ``edges/`` or ``evidence/``. Biological
candidates are stored in ``edges_inferred``/``evidence_inferred``; existential
and coherence products are stored in ``derived_views``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
import pyarrow.parquet as pq

POLICY_REVISION = "5dc88d4b5372eb2cf99039d455c556314564450c"
REGISTRY_VERSION = "2.0.0"
CANONICAL_TARGET_INVENTORY_RECEIPT_VERSION = "canonical-target-inventory-v1"
CONTEXT_FIELDS = (
    "assembly",
    "organism",
    "tissue",
    "biosample",
    "cell_type",
    "cell_line",
    "disease_context",
    "phenotype_context",
    "population",
    "dose",
    "time",
    "readout",
)
EVIDENCE_ID_FIELDS = (
    "evidence_key",
    "source_record_id",
    "study_id",
    "dataset_id",
    "paper_id",
)
EVIDENCE_ONLY_FIELDS = {
    "typed_path",
    "support_edge_ids_or_hashes",
    "support_evidence_ids_or_hashes",
    "context_intersection",
    "input_snapshot_id",
    "input_snapshot_sha256",
    "source_releases",
    "context_compatibility",
    "sign_computation",
    "conflict_state",
    "canonical_observed_overlap",
    "staged_source_native_overlap",
    "canonical_target_inventory_available",
    "canonical_target_inventory_receipt_sha256",
}
INFERRED_EDGE_DERIVATION_FIELDS = {
    "supporting_protein_id",
    "supporting_cell_type_id",
    "supporting_mutation_id",
    "anchor_disease_id",
}
ALLOWLISTED_MUTATION_DISEASE_SUPPORT = {
    "pathogenic",
    "likely_pathogenic",
    "pathogenic_likely_pathogenic",
    "reviewed_causal",
    "causal_reviewed",
}
REJECTED_MUTATION_DISEASE_SUPPORT_REASONS = {
    "benign": "non_pathogenic_benign",
    "likely_benign": "non_pathogenic_likely_benign",
    "associative": "noncausal_associative_support",
    "association": "noncausal_generic_support",
    "generic": "noncausal_generic_support",
}
# Mapping versions are provenance and are expected to differ between premise
# producers. Compatibility is about biological identity/context, not identical
# software/release labels; all versions remain preserved in ``typed_path``.
MAPPING_FIELDS = (
    "assembly",
    "organism",
    "transcript_id",
    "isoform_id",
    "protein_isoform",
)


@dataclass(frozen=True)
class Template:
    template_id: str
    premises: tuple[str, ...]
    target: str
    output_class: str
    confidence: str
    required_fields: tuple[str, ...]
    expected_zero: tuple[str, ...]


TEMPLATES: tuple[Template, ...] = (
    Template(
        "mutation_transcript_gene_attribution_v2",
        ("mutation_affects_transcript", "gene_has_transcript"),
        "mutation_associated_gene",
        "inferred_edge",
        "inferred_obvious",
        ("exact_transcript_mapping", "assembly_compatible"),
        ("containment_only", "assembly_mismatch", "missing_mapping"),
    ),
    Template(
        "mutation_protein_gene_attribution_v2",
        (
            "mutation_causes_protein_change",
            "transcript_encodes_protein",
            "gene_has_transcript",
        ),
        "mutation_associated_gene",
        "inferred_edge",
        "inferred_obvious",
        ("exact_protein_transcript_gene_mapping", "assembly_compatible"),
        ("isoform_mismatch", "assembly_mismatch", "missing_mapping"),
    ),
    Template(
        "mutation_disease_phenotype_candidate_v2",
        ("mutation_associated_disease", "disease_has_phenotype"),
        "mutation_associated_phenotype",
        "inferred_edge",
        "inferred_weak",
        ("disease_context_compatible", "source_independent"),
        ("shared_phenotype_only", "source_circularity", "context_mismatch"),
    ),
    Template(
        "mutation_disease_phenotype_triangle_v2",
        (
            "mutation_associated_disease",
            "disease_has_phenotype",
            "mutation_associated_phenotype",
        ),
        "mutation_disease_phenotype_coherence",
        "derived_view",
        "coherence_only",
        ("complete_triangle",),
        ("incomplete_triangle",),
    ),
    Template(
        "cell_type_tissue_gene_existential_v2",
        ("cell_type_found_in_tissue", "cell_type_expresses_gene"),
        "tissue_expresses_gene",
        "inferred_edge",
        "inferred_obvious",
        ("compatible_cell_population_context",),
        ("context_mismatch", "missing_population"),
    ),
    Template(
        "mutation_protein_disease_candidate_v2",
        ("mutation_causes_protein_change", "mutation_associated_disease"),
        "disease_associated_protein",
        "inferred_edge",
        "inferred_weak",
        ("exact_protein_consequence", "pathogenicity_usable"),
        ("isoform_mismatch", "unknown_pathogenicity", "conflicting_pathogenicity"),
    ),
    Template(
        "mutation_protein_gene_disease_candidate_v2",
        (
            "mutation_causes_protein_change",
            "transcript_encodes_protein",
            "gene_has_transcript",
            "mutation_associated_disease",
        ),
        "disease_associated_gene",
        "inferred_edge",
        "inferred_weak",
        ("exact_protein_mapping", "pathogenicity_usable"),
        ("isoform_mismatch", "assembly_mismatch", "unknown_pathogenicity"),
    ),
    Template(
        "mutation_protein_gene_phenotype_candidate_v2",
        (
            "mutation_causes_protein_change",
            "transcript_encodes_protein",
            "gene_has_transcript",
            "mutation_associated_phenotype",
        ),
        "gene_associated_phenotype",
        "inferred_edge",
        "inferred_weak",
        ("exact_protein_mapping", "phenotype_context_compatible"),
        ("isoform_mismatch", "assembly_mismatch", "context_mismatch"),
    ),
    Template(
        "tissue_protein_to_gene_expression_v2",
        (
            "tissue_expresses_protein",
            "transcript_encodes_protein",
            "gene_has_transcript",
        ),
        "tissue_expresses_gene",
        "inferred_edge",
        "inferred_obvious",
        ("protein_product_observed", "exact_mapping"),
        ("rna_to_protein_reverse", "isoform_mismatch", "missing_mapping"),
    ),
    Template(
        "cell_type_protein_to_gene_expression_v2",
        (
            "cell_type_expresses_protein",
            "transcript_encodes_protein",
            "gene_has_transcript",
        ),
        "cell_type_expresses_gene",
        "inferred_edge",
        "inferred_obvious",
        ("protein_product_observed", "exact_mapping"),
        ("rna_to_protein_reverse", "isoform_mismatch", "missing_mapping"),
    ),
    Template(
        "cell_line_protein_to_gene_expression_v2",
        (
            "cell_line_expresses_protein",
            "transcript_encodes_protein",
            "gene_has_transcript",
        ),
        "cell_line_expresses_gene",
        "inferred_edge",
        "inferred_obvious",
        ("protein_product_observed", "exact_mapping"),
        ("rna_to_protein_reverse", "isoform_mismatch", "missing_mapping"),
    ),
    Template(
        "protein_disease_to_gene_disease_v2",
        (
            "disease_associated_protein",
            "transcript_encodes_protein",
            "gene_has_transcript",
        ),
        "disease_associated_gene",
        "inferred_edge",
        "inferred_obvious",
        ("protein_native_assertion", "exact_mapping"),
        ("gene_to_protein_reverse", "isoform_mismatch", "missing_mapping"),
    ),
    Template(
        "gene_disease_to_protein_disease_strict_v2",
        (
            "disease_associated_gene",
            "transcript_encodes_protein",
            "gene_has_transcript",
        ),
        "disease_associated_protein",
        "inferred_edge",
        "inferred_weak",
        ("explicit_protein_isoform_support",),
        ("missing_isoform_support", "gene_to_all_isoforms"),
    ),
    Template(
        "pathway_associated_member_feature_v2",
        ("pathway_contains_gene", "disease_associated_gene"),
        "pathway_associated_member",
        "derived_view",
        "coherence_only",
        ("associated_member",),
        ("every_member_projection",),
    ),
    Template(
        "pathway_associated_protein_member_feature_v2",
        ("pathway_contains_protein", "disease_associated_protein"),
        "pathway_associated_member",
        "derived_view",
        "coherence_only",
        ("associated_member",),
        ("every_member_projection",),
    ),
    Template(
        "pathway_disease_candidate_v2",
        ("pathway_contains_gene", "disease_associated_gene"),
        "disease_involves_pathway",
        "inferred_edge",
        "inferred_weak",
        ("specific_pathway", "independent_members_or_native_support", "noncircular"),
        ("single_nonspecific_member", "source_circularity", "pathway_fanout"),
    ),
    Template(
        "disease_phenotype_tissue_localization_v2",
        ("disease_has_phenotype", "disease_manifests_in_tissue"),
        "phenotype_observed_in_tissue",
        "inferred_edge",
        "inferred_weak",
        ("exact_disease_anchor", "source_independent", "context_compatible"),
        ("cartesian_without_disease_anchor", "source_circularity", "context_mismatch"),
    ),
    Template(
        "disease_phenotype_tissue_triangle_v2",
        (
            "disease_has_phenotype",
            "disease_manifests_in_tissue",
            "phenotype_observed_in_tissue",
        ),
        "disease_phenotype_tissue_coherence",
        "derived_view",
        "coherence_only",
        ("complete_triangle",),
        ("incomplete_triangle",),
    ),
    Template(
        "signed_gene_target_treatment_v2",
        ("molecule_targets_gene", "disease_associated_gene"),
        "molecule_treats_disease",
        "inferred_edge",
        "inferred_weak",
        ("known_action_mechanism_direction", "negative_sign_product", "causal_support", "context_compatible"),
        ("missing_sign", "conflicting_sign", "nontherapeutic_sign_product", "context_mismatch"),
    ),
    Template(
        "signed_protein_target_treatment_v2",
        ("molecule_targets_protein", "disease_associated_protein"),
        "molecule_treats_disease",
        "inferred_edge",
        "inferred_weak",
        ("known_action_mechanism_direction", "negative_sign_product", "causal_support", "context_compatible"),
        ("missing_sign", "conflicting_sign", "nontherapeutic_sign_product", "isoform_mismatch"),
    ),
    Template(
        "signed_gene_target_contraindication_v2",
        ("molecule_targets_gene", "disease_associated_gene"),
        "molecule_contraindicates_disease",
        "inferred_edge",
        "inferred_weak",
        ("known_action_mechanism_direction", "positive_sign_product", "causal_support", "context_compatible"),
        ("missing_sign", "conflicting_sign", "nonharmful_sign_product", "context_mismatch"),
    ),
    Template(
        "signed_protein_target_contraindication_v2",
        ("molecule_targets_protein", "disease_associated_protein"),
        "molecule_contraindicates_disease",
        "inferred_edge",
        "inferred_weak",
        ("known_action_mechanism_direction", "positive_sign_product", "causal_support", "context_compatible"),
        ("missing_sign", "conflicting_sign", "nonharmful_sign_product", "isoform_mismatch"),
    ),
    Template(
        "allelic_triangulation_treatment_v2",
        (
            "molecule_targets_gene",
            "mutation_associated_gene",
            "mutation_associated_disease",
        ),
        "molecule_treats_disease",
        "inferred_edge",
        "inferred_weak",
        ("explicit_variant_mechanism", "known_action_sign", "disease_effect_direction"),
        ("containment_only", "missing_sign", "conflicting_sign", "context_mismatch"),
    ),
    Template(
        "pharmacogenomic_efficacy_treatment_v2",
        ("mutation_associated_disease", "mutation_affects_molecule_response"),
        "molecule_treats_disease",
        "inferred_edge",
        "inferred_weak",
        ("efficacy_category", "benefit_direction", "exact_disease_context"),
        (
            "resistance",
            "toxicity",
            "dosage",
            "metabolism_pk",
            "missing_context",
            "conflicting_direction",
        ),
    ),
)
TEMPLATE_BY_ID = {t.template_id: t for t in TEMPLATES}
REJECTED_MOTIFS = {
    "c3_variant_enhancer_gene_disease": "removed from approved v2 allowlist",
    "shared_phenotype_disease_identity": "shared phenotype is retrieval context, not disease identity",
    "rna_gene_to_protein_expression": "RNA/gene expression does not entail protein or isoform production",
    "pathway_every_member_projection": "pathway involvement does not implicate every member",
    "generic_cell_response_phenotype": "requires exact readout, direction, dose, time, and context; no approved endpoint template",
}


@dataclass(frozen=True)
class BuildConfig:
    input_root: Path
    output_root: Path
    snapshot_id: str
    producer_revision: str
    staged_input_roots: tuple[Path, ...] = ()
    template_ids: tuple[str, ...] = tuple(t.template_id for t in TEMPLATES)
    max_rows_per_file: int = 100_000
    max_paths_per_template: int = 100_000
    sample_limit: int = 10
    require_canonical_target_inventory: bool = True
    canonical_target_inventory_source_identity: str | None = None
    canonical_target_inventory_receipt_sha256: str | None = None


def _clean(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes, dict)):
        try:
            value = value.tolist()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, (list, tuple, set)):
        return [_clean(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _clean(v) for k, v in value.items()}
    return value


def _json(value: Any) -> str:
    return json.dumps(_clean(value), sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _values(row: Mapping[str, Any], *fields: str) -> set[str]:
    found: set[str] = set()
    for field in fields:
        value = row.get(field)
        if isinstance(value, str) and value.strip().startswith("["):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        items = value if isinstance(value, (list, tuple, set)) else (value,)
        for item in items:
            if item is not None and str(item).strip():
                found.add(str(item).strip().lower())
    return found


def _literal_values(row: Mapping[str, Any], *fields: str) -> set[str]:
    """Return provenance values without semantic case normalization."""
    found: set[str] = set()
    for field in fields:
        value = row.get(field)
        if isinstance(value, str) and value.strip().startswith("["):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        items = value if isinstance(value, (list, tuple, set)) else (value,)
        for item in items:
            if item is not None and str(item).strip():
                found.add(str(item).strip())
    return found


def _resolved(row: Mapping[str, Any], *fields: str) -> tuple[str, str]:
    statuses = _values(row, *(f"{field}_status" for field in fields))
    values = _values(row, *fields)
    if "conflicting" in statuses or "conflicting" in values or len(values) > 1:
        return "conflicting", ""
    if not values or "unknown" in statuses:
        return "unknown", ""
    return "known", next(iter(values))


def _normalized_support_value(value: str) -> str:
    return "_".join(
        part
        for part in value.strip().lower().replace("/", " ").replace("-", " ").split()
        if part
    )


def _mutation_disease_support_gate(
    row: Mapping[str, Any],
) -> tuple[bool, str, str]:
    fields = ("pathogenicity", "clinical_significance", "disease_support")
    statuses = _values(row, *(f"{field}_status" for field in fields))
    values = {_normalized_support_value(value) for value in _values(row, *fields)}
    if "conflicting" in statuses or "conflicting" in values:
        return False, "", "conflicting_pathogenicity"
    if not values or "unknown" in statuses or "unknown" in values:
        return False, "", "unknown_pathogenicity"
    allowed = values & ALLOWLISTED_MUTATION_DISEASE_SUPPORT
    rejected = values - ALLOWLISTED_MUTATION_DISEASE_SUPPORT
    if allowed and not rejected:
        return True, sorted(allowed)[0], ""
    if allowed and rejected:
        return False, "", "conflicting_pathogenicity"
    rejected_value = sorted(rejected)[0]
    reason = REJECTED_MUTATION_DISEASE_SUPPORT_REASONS.get(
        rejected_value, f"nonallowlisted_disease_support_{rejected_value}"
    )
    return False, "", reason


def _compatible(
    rows: Sequence[Mapping[str, Any]], fields: Sequence[str] = CONTEXT_FIELDS
) -> bool:
    for field in fields:
        seen: set[str] = set()
        for row in rows:
            status, value = _resolved(row, field)
            if status == "conflicting":
                return False
            if status == "known":
                seen.add(value)
        if len(seen) > 1:
            return False
    return True


def _source_set(row: Mapping[str, Any]) -> set[str]:
    return _values(row, "source", "source_dataset", "study_id", "dataset_id")


def _independent(rows: Sequence[Mapping[str, Any]]) -> bool:
    source_sets = [_source_set(row) for row in rows]
    return bool(source_sets) and all(source_sets) and not set.intersection(*source_sets)


def _has_shared_context(rows: Sequence[Mapping[str, Any]]) -> bool:
    """Require at least one explicit, non-conflicting context shared by all rows."""
    for field in CONTEXT_FIELDS:
        values = [_values(row, field) for row in rows]
        if all(values) and len(set.union(*values)) == 1:
            return True
    return False


def _edge_key(row: Mapping[str, Any]) -> str:
    return str(
        row.get("edge_key")
        or f"{row.get('relation')}|{row.get('x_id')}|{row.get('y_id')}"
    )


def _with_evidence(
    edge: dict[str, Any], evidence: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    rows = [ev for ev in evidence if _edge_key(ev) == _edge_key(edge)]
    merged = dict(edge)
    merged["edge_key"] = _edge_key(edge)
    merged["evidence_rows"] = rows
    merged["evidence_ids"] = sorted(
        {
            str(ev.get(field))
            for ev in rows
            for field in EVIDENCE_ID_FIELDS
            if ev.get(field)
        }
    )
    for field in set().union(*(set(row) for row in rows)) if rows else ():
        evidence_values = {
            _json(row[field])
            for row in rows
            if row.get(field) is not None and str(row.get(field)).strip()
        }
        values = set(evidence_values)
        if merged.get(field) is not None and str(merged.get(field)).strip():
            values.add(_json(merged[field]))
        if len(values) == 1 and field not in merged:
            merged[field] = json.loads(next(iter(values)))
        elif len(values) > 1:
            merged[f"{field}_status"] = "conflicting"
            merged[f"{field}_values"] = sorted(json.loads(v) for v in values)
    return merged


def _discover_file(roots: Sequence[Path], layer: str, relation: str) -> list[Path]:
    files: set[Path] = set()
    for root in roots:
        root = root.resolve()
        candidates = (
            root / layer / f"{relation}.parquet",
            root / layer / relation / "source_native.parquet",
        )
        files.update(path for path in candidates if path.exists())
    return sorted(files)


def _read_files(
    paths: Sequence[Path], relation: str, limit: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        count = pq.ParquetFile(path).metadata.num_rows
        if count > limit:
            raise ValueError(
                f"{path} has {count} rows; exceeds max_rows_per_file={limit}"
            )
        frame = pd.read_parquet(path)
        for raw in frame.to_dict(orient="records"):
            row = {str(k): _clean(v) for k, v in raw.items()}
            if row.get("relation") not in (None, "", relation):
                raise ValueError(f"{path} contains non-{relation} row")
            row["relation"] = relation
            row["edge_key"] = _edge_key(row)
            row["input_path"] = str(path)
            rows.append(row)
    return sorted(rows, key=lambda row: (_edge_key(row), _json(row)))


def _load(
    config: BuildConfig, relations: Iterable[str]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    roots = (config.input_root, *config.staged_input_roots)
    loaded: dict[str, list[dict[str, Any]]] = {}
    manifest_files: dict[str, Any] = {}
    for relation in sorted(set(relations)):
        edge_paths = _discover_file(roots, "edges", relation)
        evidence_paths = _discover_file(roots, "evidence", relation)
        edge_rows = _read_files(edge_paths, relation, config.max_rows_per_file)
        evidence_rows = _read_files(evidence_paths, relation, config.max_rows_per_file)
        loaded[relation] = [_with_evidence(row, evidence_rows) for row in edge_rows]
        for layer, paths in (("edges", edge_paths), ("evidence", evidence_paths)):
            for path in paths:
                manifest_files[str(path)] = {
                    "layer": layer,
                    "relation": relation,
                    "rows": pq.ParquetFile(path).metadata.num_rows,
                    "columns": pq.ParquetFile(path).schema_arrow.names,
                    "sha256": _file_sha(path),
                }
    payload = {"snapshot_id": config.snapshot_id, "files": manifest_files}
    payload["manifest_sha256"] = _sha(payload)
    return loaded, payload


def _by(rows: Iterable[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[str(row.get(field))].append(row)
    return result


def _mapping_paths(
    relations: Mapping[str, list[dict[str, Any]]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    genes_by_transcript = _by(relations.get("gene_has_transcript", []), "y_id")
    result: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for encoding in relations.get("transcript_encodes_protein", []):
        for gene_tx in genes_by_transcript.get(str(encoding.get("x_id")), []):
            if _compatible((encoding, gene_tx), MAPPING_FIELDS):
                result.append((encoding, gene_tx))
    return result


def _candidate(
    template: Template,
    x_id: Any,
    x_type: str,
    y_id: Any,
    y_type: str,
    supports: Sequence[dict[str, Any]],
    *,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    support_ids = sorted({_edge_key(row) for row in supports})
    evidence_ids = sorted(
        {str(value) for row in supports for value in row.get("evidence_ids", [])}
    )
    context = {
        field: sorted({value for row in supports for value in _values(row, field)})
        for field in CONTEXT_FIELDS
    }
    context = {
        key: values[0] if len(values) == 1 else values
        for key, values in context.items()
        if values
    }
    path = [
        {key: value for key, value in row.items() if key not in {"evidence_rows"}}
        for row in supports
    ]
    payload = {
        "template": template.template_id,
        "x_id": str(x_id),
        "y_id": str(y_id),
        "support": support_ids,
        "evidence": evidence_ids,
        "context": context,
        "path": path,
    }
    return {
        "x_id": str(x_id),
        "x_type": x_type,
        "y_id": str(y_id),
        "y_type": y_type,
        "relation": template.target,
        "display_relation": f"inferred {template.target}",
        "inference_template_id": template.template_id,
        "inference_template_version": REGISTRY_VERSION,
        "epistemic_class": template.confidence,
        "support_count": len(support_ids),
        "support_edge_ids_or_hashes": _json(support_ids),
        "support_evidence_ids_or_hashes": _json(evidence_ids),
        "typed_path": _json(path),
        "context_intersection": _json(context),
        "derivation_hash": _sha(payload),
        **dict(extra or {}),
    }


def _sign(row: Mapping[str, Any], *fields: str) -> tuple[str, int | None]:
    signs = {
        "activate": 1,
        "activation": 1,
        "agonist": 1,
        "gain_of_function": 1,
        "increase": 1,
        "risk": 1,
        "positive": 1,
        "inhibit": -1,
        "inhibition": -1,
        "inhibitor": -1,
        "antagonist": -1,
        "loss_of_function": -1,
        "decrease": -1,
        "protective": -1,
        "negative": -1,
    }
    statuses = _values(row, *(f"{field}_status" for field in fields))
    if "conflicting" in statuses:
        return "conflicting", None
    values = _values(row, *fields)
    if "conflicting" in values:
        return "conflicting", None
    if (
        not values
        or "unknown" in statuses
        or "unknown" in values
        or any(value not in signs for value in values)
    ):
        return "unknown", None
    resolved = {signs[value] for value in values}
    if len(resolved) > 1:
        return "conflicting", None
    return "known", resolved.pop()


def _disease_sign(row: Mapping[str, Any]) -> tuple[str, int | None, dict[str, Any]]:
    """Compose distinct disease mechanism and outcome-direction operands."""
    mechanism_fields = (
        "causal_mechanisms",
        "causal_mechanism",
        "pathological_mechanism_sign",
    )
    effect_fields = ("effect_directions", "effect_direction")
    mechanism_status, mechanism = _sign(row, *mechanism_fields)
    effect_status, effect = _sign(row, *effect_fields)
    mechanism_aggregate_status = _values(row, "mechanism_status")
    effect_aggregate_status = _values(row, "effect_direction_status")
    if "conflicting" in mechanism_aggregate_status:
        mechanism_status, mechanism = "conflicting", None
    elif "unknown" in mechanism_aggregate_status:
        mechanism_status, mechanism = "unknown", None
    if "conflicting" in effect_aggregate_status:
        effect_status, effect = "conflicting", None
    elif "unknown" in effect_aggregate_status:
        effect_status, effect = "unknown", None
    detail = {
        "disease_mechanism_sign": mechanism,
        "effect_direction_sign": effect,
    }
    if "conflicting" in {mechanism_status, effect_status}:
        return "conflicting", None, detail
    if "unknown" in {mechanism_status, effect_status}:
        return "unknown", None, detail
    if mechanism is None or effect is None:
        return "unknown", None, detail
    disease_sign = mechanism * effect
    detail["net_disease_sign"] = disease_sign
    return "known", disease_sign, detail


def _action_sign(row: Mapping[str, Any]) -> tuple[str, int | None]:
    aggregate_status = _values(row, "action_status")
    if "conflicting" in aggregate_status:
        return "conflicting", None
    if "unknown" in aggregate_status:
        return "unknown", None
    fields = ("action_direction", "target_modulation", "action_types", "action_type")
    present_fields = [
        field
        for field in fields
        if _values(row, field) or _values(row, f"{field}_status")
    ]
    resolved = [_sign(row, field) for field in present_fields]
    if any(status == "conflicting" for status, _ in resolved):
        return "conflicting", None
    if any(status == "unknown" for status, _ in resolved):
        return "unknown", None
    signs = {sign for _, sign in resolved if sign is not None}
    if len(signs) > 1:
        return "conflicting", None
    if not signs:
        return "unknown", None
    return "known", signs.pop()


def _generate(
    template: Template,
    r: Mapping[str, list[dict[str, Any]]],
    rejected: Counter[str],
    max_paths: int,
    rejected_samples: list[dict[str, Any]],
    sample_limit: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tid = template.template_id

    def add(row: dict[str, Any]) -> None:
        if len(out) >= max_paths:
            rejected["max_paths_bound"] += 1
        else:
            out.append(row)

    genes_by_tx = _by(r.get("gene_has_transcript", []), "y_id")
    mappings = _mapping_paths(r)
    mappings_by_protein = defaultdict(list)
    for encoding, gene_tx in mappings:
        mappings_by_protein[str(encoding["y_id"])].append((encoding, gene_tx))

    if tid == "mutation_transcript_gene_attribution_v2":
        for mutation_tx in r.get("mutation_affects_transcript", []):
            matches = genes_by_tx.get(str(mutation_tx["y_id"]), [])
            if not matches:
                rejected["missing_mapping"] += 1
            for gene_tx in matches:
                if not _compatible((mutation_tx, gene_tx), MAPPING_FIELDS):
                    rejected["assembly_mismatch"] += 1
                    continue
                add(
                    _candidate(
                        template,
                        mutation_tx["x_id"],
                        "mutation",
                        gene_tx["x_id"],
                        "gene",
                        (mutation_tx, gene_tx),
                        extra={"attribution_mode": "exact_transcript_consequence"},
                    )
                )
    elif tid == "mutation_protein_gene_attribution_v2":
        for mutation_protein in r.get("mutation_causes_protein_change", []):
            matches = mappings_by_protein.get(str(mutation_protein["y_id"]), [])
            if not matches:
                rejected["missing_mapping"] += 1
            for encoding, gene_tx in matches:
                if not _compatible(
                    (mutation_protein, encoding, gene_tx), MAPPING_FIELDS
                ):
                    rejected["isoform_or_assembly_mismatch"] += 1
                    continue
                add(
                    _candidate(
                        template,
                        mutation_protein["x_id"],
                        "mutation",
                        gene_tx["x_id"],
                        "gene",
                        (mutation_protein, encoding, gene_tx),
                        extra={"attribution_mode": "exact_protein_consequence"},
                    )
                )
    elif tid in {
        "mutation_disease_phenotype_candidate_v2",
        "mutation_disease_phenotype_triangle_v2",
    }:
        phenotypes = _by(r.get("disease_has_phenotype", []), "x_id")
        observed = {
            (str(x["x_id"]), str(x["y_id"])): x
            for x in r.get("mutation_associated_phenotype", [])
        }
        for md in r.get("mutation_associated_disease", []):
            for dp in phenotypes.get(str(md["y_id"]), []):
                if not _compatible((md, dp)) or not _independent((md, dp)):
                    rejected["context_or_source_circularity"] += 1
                    continue
                direct = observed.get((str(md["x_id"]), str(dp["y_id"])))
                if tid.endswith("triangle_v2"):
                    if direct:
                        add(
                            _candidate(
                                template,
                                md["x_id"],
                                "mutation",
                                dp["y_id"],
                                "phenotype",
                                (md, dp, direct),
                                extra={
                                    "coherence_only": True,
                                    "anchor_disease_id": md["y_id"],
                                },
                            )
                        )
                    else:
                        rejected["incomplete_triangle"] += 1
                else:
                    add(
                        _candidate(
                            template,
                            md["x_id"],
                            "mutation",
                            dp["y_id"],
                            "phenotype",
                            (md, dp),
                            extra={"anchor_disease_id": md["y_id"]},
                        )
                    )
    elif tid == "cell_type_tissue_gene_existential_v2":
        expression = _by(r.get("cell_type_expresses_gene", []), "x_id")
        for ct in r.get("cell_type_found_in_tissue", []):
            for ex in expression.get(str(ct["x_id"]), []):
                if not _compatible((ct, ex)):
                    rejected["context_mismatch"] += 1
                    continue
                add(
                    _candidate(
                        template,
                        ct["y_id"],
                        "tissue",
                        ex["y_id"],
                        "gene",
                        (ct, ex),
                        extra={
                            "quantifier": "exists_supporting_cell_population",
                            "supporting_cell_type_id": ct["x_id"],
                        },
                    )
                )
    elif tid in {
        "mutation_protein_disease_candidate_v2",
        "mutation_protein_gene_disease_candidate_v2",
        "mutation_protein_gene_phenotype_candidate_v2",
    }:
        endpoint_relation = (
            "mutation_associated_phenotype"
            if tid.endswith("phenotype_candidate_v2")
            else "mutation_associated_disease"
        )
        endpoints = _by(r.get(endpoint_relation, []), "x_id")
        for mp in r.get("mutation_causes_protein_change", []):
            for endpoint in endpoints.get(str(mp["x_id"]), []):
                pathogenicity = ""
                if endpoint_relation.endswith("disease"):
                    allowed, pathogenicity, reason = _mutation_disease_support_gate(
                        endpoint
                    )
                    if not allowed:
                        rejected[reason] += 1
                        continue
                if not _compatible((mp, endpoint)):
                    rejected["context_mismatch"] += 1
                    continue
                if tid == "mutation_protein_disease_candidate_v2":
                    add(
                        _candidate(
                            template,
                            mp["y_id"],
                            "protein",
                            endpoint["y_id"],
                            "disease",
                            (mp, endpoint),
                            extra={"pathogenicity": pathogenicity},
                        )
                    )
                else:
                    maps = mappings_by_protein.get(str(mp["y_id"]), [])
                    if not maps:
                        rejected["missing_mapping"] += 1
                    for encoding, gene_tx in maps:
                        if not _compatible(
                            (mp, endpoint, encoding, gene_tx), MAPPING_FIELDS
                        ):
                            rejected["isoform_or_assembly_mismatch"] += 1
                            continue
                        y_type = (
                            "phenotype"
                            if endpoint_relation.endswith("phenotype")
                            else "disease"
                        )
                        add(
                            _candidate(
                                template,
                                gene_tx["x_id"],
                                "gene",
                                endpoint["y_id"],
                                y_type,
                                (mp, encoding, gene_tx, endpoint),
                                extra={"pathogenicity": pathogenicity},
                            )
                        )
    elif "protein_to_gene_expression" in tid:
        relation, x_type = {
            "tissue_protein_to_gene_expression_v2": (
                "tissue_expresses_protein",
                "tissue",
            ),
            "cell_type_protein_to_gene_expression_v2": (
                "cell_type_expresses_protein",
                "cell_type",
            ),
            "cell_line_protein_to_gene_expression_v2": (
                "cell_line_expresses_protein",
                "cell_line",
            ),
        }[tid]
        for expression in r.get(relation, []):
            maps = mappings_by_protein.get(str(expression["y_id"]), [])
            if not maps:
                rejected["missing_mapping"] += 1
            for encoding, gene_tx in maps:
                if not _compatible((expression, encoding, gene_tx), MAPPING_FIELDS):
                    rejected["isoform_or_assembly_mismatch"] += 1
                    continue
                add(
                    _candidate(
                        template,
                        expression["x_id"],
                        x_type,
                        gene_tx["x_id"],
                        "gene",
                        (expression, encoding, gene_tx),
                        extra={
                            "support_mode": "protein_product_observed",
                            "rna_measured": False,
                            "supporting_protein_id": expression["y_id"],
                        },
                    )
                )
    elif tid in {
        "protein_disease_to_gene_disease_v2",
        "gene_disease_to_protein_disease_strict_v2",
    }:
        if tid.startswith("protein"):
            for pdisease in r.get("disease_associated_protein", []):
                for encoding, gene_tx in mappings_by_protein.get(
                    str(pdisease["x_id"]), []
                ):
                    if _compatible((pdisease, encoding, gene_tx), MAPPING_FIELDS):
                        add(
                            _candidate(
                                template,
                                gene_tx["x_id"],
                                "gene",
                                pdisease["y_id"],
                                "disease",
                                (pdisease, encoding, gene_tx),
                                extra={
                                    "projection_mode": "protein_native_to_encoding_gene"
                                },
                            )
                        )
                    else:
                        rejected["isoform_or_assembly_mismatch"] += 1
        else:
            proteins_by_gene = defaultdict(list)
            for encoding, gene_tx in mappings:
                proteins_by_gene[str(gene_tx["x_id"])].append((encoding, gene_tx))
            for gd in r.get("disease_associated_gene", []):
                explicit = _values(gd, "protein_id", "protein_isoform", "isoform_id")
                if not explicit:
                    rejected["missing_isoform_support"] += 1
                    continue
                for encoding, gene_tx in proteins_by_gene.get(str(gd["x_id"]), []):
                    if str(encoding["y_id"]).lower() not in explicit:
                        continue
                    add(
                        _candidate(
                            template,
                            encoding["y_id"],
                            "protein",
                            gd["y_id"],
                            "disease",
                            (gd, encoding, gene_tx),
                            extra={"projection_mode": "explicit_supported_isoform"},
                        )
                    )
    elif tid.startswith("pathway_associated_"):
        protein = "protein" in tid
        membership = "pathway_contains_protein" if protein else "pathway_contains_gene"
        association = (
            "disease_associated_protein" if protein else "disease_associated_gene"
        )
        assoc = _by(r.get(association, []), "x_id")
        for member in r.get(membership, []):
            for disease in assoc.get(str(member["y_id"]), []):
                add(
                    _candidate(
                        template,
                        member["x_id"],
                        "pathway",
                        disease["y_id"],
                        "disease",
                        (member, disease),
                        extra={
                            "coherence_only": True,
                            "associated_member_id": member["y_id"],
                            "member_type": "protein" if protein else "gene",
                        },
                    )
                )
    elif tid == "pathway_disease_candidate_v2":
        assoc = _by(r.get("disease_associated_gene", []), "x_id")
        grouped: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = (
            defaultdict(list)
        )
        pathway_sizes = Counter(
            str(row["x_id"]) for row in r.get("pathway_contains_gene", [])
        )
        for member in r.get("pathway_contains_gene", []):
            for disease in assoc.get(str(member["y_id"]), []):
                grouped[(str(member["x_id"]), str(disease["y_id"]))].append(
                    (member, disease)
                )
        for (pathway, disease_id), paths in grouped.items():
            native = any(
                _values(disease, "pathway_native_support") & {"true", "1", "yes"}
                for _, disease in paths
            )
            if pathway_sizes[pathway] > 500:
                rejected["pathway_fanout"] += 1
                continue
            independent_paths = [
                (member, disease)
                for member, disease in paths
                if _independent((member, disease))
            ]
            member_sources: dict[str, set[str]] = defaultdict(set)
            for member, disease in independent_paths:
                member_sources[str(member["y_id"])].update(_source_set(disease))
            independent_member_pairs = any(
                left != right
                and member_sources[left]
                and member_sources[right]
                and member_sources[left].isdisjoint(member_sources[right])
                for left in member_sources
                for right in member_sources
            )
            if len(member_sources) < 2 and not native:
                rejected["insufficient_independent_members"] += 1
                continue
            if not independent_member_pairs and not native:
                rejected["source_commonality_or_circularity"] += 1
                continue
            accepted_paths = paths if native else independent_paths
            supports = tuple(row for pair in accepted_paths for row in pair)
            add(
                _candidate(
                    template,
                    pathway,
                    "pathway",
                    disease_id,
                    "disease",
                    supports,
                    extra={
                        "associated_member_count": len(
                            {m["y_id"] for m, _ in accepted_paths}
                        ),
                        "pathway_size": pathway_sizes[pathway],
                    },
                )
            )
    elif tid in {
        "disease_phenotype_tissue_localization_v2",
        "disease_phenotype_tissue_triangle_v2",
    }:
        tissues = _by(r.get("disease_manifests_in_tissue", []), "x_id")
        observed = {
            (str(row["x_id"]), str(row["y_id"])): row
            for row in r.get("phenotype_observed_in_tissue", [])
        }
        for dp in r.get("disease_has_phenotype", []):
            for dt in tissues.get(str(dp["x_id"]), []):
                if not _compatible((dp, dt)) or not _independent((dp, dt)):
                    rejected["context_or_source_circularity"] += 1
                    continue
                direct = observed.get((str(dt["y_id"]), str(dp["y_id"])))
                if tid.endswith("triangle_v2"):
                    if direct:
                        add(
                            _candidate(
                                template,
                                dt["y_id"],
                                "tissue",
                                dp["y_id"],
                                "phenotype",
                                (dp, dt, direct),
                                extra={
                                    "coherence_only": True,
                                    "anchor_disease_id": dp["x_id"],
                                },
                            )
                        )
                    else:
                        rejected["incomplete_triangle"] += 1
                else:
                    add(
                        _candidate(
                            template,
                            dt["y_id"],
                            "tissue",
                            dp["y_id"],
                            "phenotype",
                            (dp, dt),
                            extra={
                                "anchor_disease_id": dp["x_id"],
                                "quantifier": "same_disease_anchor_only",
                            },
                        )
                    )
    elif tid.startswith("signed_"):
        protein = "protein" in tid
        contraindication = "contraindication" in tid
        target_relation = (
            "molecule_targets_protein" if protein else "molecule_targets_gene"
        )
        disease_relation = (
            "disease_associated_protein" if protein else "disease_associated_gene"
        )
        mechanisms = _by(r.get(disease_relation, []), "x_id")
        for target in r.get(target_relation, []):
            for mechanism in mechanisms.get(str(target["y_id"]), []):
                action_status, action = _action_sign(target)
                mechanism_status, mechanism_sign, sign_detail = _disease_sign(mechanism)
                causal_status, causal = _resolved(
                    mechanism, "causal_support_level", "causal_support"
                )
                sign_computation = {
                    "action_sign": action,
                    **sign_detail,
                    "relation": template.target,
                }
                if action is not None and mechanism_sign is not None:
                    sign_computation["sign_product"] = action * mechanism_sign

                def reject_signed(reason: str) -> None:
                    rejected[reason] += 1
                    if len(rejected_samples) >= sample_limit:
                        return
                    supports = (target, mechanism)
                    typed_path = [
                        {
                            key: value
                            for key, value in row.items()
                            if key != "evidence_rows"
                        }
                        for row in supports
                    ]
                    releases = sorted(
                        {
                            value
                            for row in supports
                            for value in _literal_values(
                                row, "release", "release_values", "source_release"
                            )
                        }
                    )
                    rejected_samples.append(
                        {
                            "reason": reason,
                            "decision": "rejected",
                            "classification": "plausible hypothesis",
                            "human_readable_path": (
                                f"{target['x_id']} -[{target_relation}]-> {target['y_id']} "
                                f"-[{disease_relation}]-> {mechanism['y_id']}"
                            ),
                            "typed_path": _json(typed_path),
                            "source_releases": _json(releases),
                            "sign_computation": _json(sign_computation),
                        }
                    )

                if "conflicting" in {action_status, mechanism_status, causal_status}:
                    reject_signed("conflicting_sign")
                    continue
                accepted_causal_support = {
                    "causal",
                    "causal_mechanistic",
                    "genetic_causal",
                    "mechanistic",
                    "pathogenic_causal",
                    "validated_causal",
                }
                if action is None or mechanism_sign is None or causal_status != "known":
                    reject_signed("missing_sign_or_causal_support")
                    continue
                if causal not in accepted_causal_support:
                    reject_signed("noncausal_support")
                    continue
                sign_product = action * mechanism_sign
                if (sign_product > 0) != contraindication:
                    reject_signed(
                        "nonharmful_sign_product"
                        if contraindication
                        else "nontherapeutic_sign_product"
                    )
                    continue
                if not _compatible((target, mechanism)):
                    reject_signed("context_mismatch")
                    continue
                if not _has_shared_context((target, mechanism)):
                    reject_signed("missing_shared_context")
                    continue
                releases = sorted(
                    {
                        value
                        for row in (target, mechanism)
                        for value in _literal_values(
                            row, "release", "release_values", "source_release"
                        )
                    }
                )
                add(
                    _candidate(
                        template,
                        target["x_id"],
                        "molecule",
                        mechanism["y_id"],
                        "disease",
                        (target, mechanism),
                        extra={
                            "sign_status": "known",
                            "therapeutic_sign": (
                                "product_positive"
                                if contraindication
                                else "product_negative"
                            ),
                            "causal_support": causal,
                            "source_releases": _json(releases),
                            "context_compatibility": "compatible",
                            "sign_computation": _json(sign_computation),
                            "conflict_state": "none",
                        },
                    )
                )
    elif tid == "allelic_triangulation_treatment_v2":
        genes = _by(r.get("mutation_associated_gene", []), "y_id")
        diseases = _by(r.get("mutation_associated_disease", []), "x_id")
        for target in r.get("molecule_targets_gene", []):
            for mg in genes.get(str(target["y_id"]), []):
                for md in diseases.get(str(mg["x_id"]), []):
                    if _values(mg, "attribution_mode", "functional_support") & {
                        "containment",
                        "genomic_containment",
                        "nearest_gene",
                        "ld_only",
                    }:
                        rejected["containment_or_weak_attribution"] += 1
                        continue
                    action_status, action = _sign(
                        target, "action_direction", "target_modulation", "action_type"
                    )
                    variant_status, variant = _sign(
                        mg, "functional_mechanism", "effect_direction"
                    )
                    disease_status, disease_sign = _sign(
                        md, "effect_direction", "association_direction"
                    )
                    if any(
                        status != "known"
                        for status in (action_status, variant_status, disease_status)
                    ):
                        rejected["missing_or_conflicting_sign"] += 1
                        continue
                    if not _compatible((target, mg, md)):
                        rejected["context_mismatch"] += 1
                        continue
                    if action * variant * disease_sign >= 0:
                        rejected["nontherapeutic_sign_product"] += 1
                        continue
                    add(
                        _candidate(
                            template,
                            target["x_id"],
                            "molecule",
                            md["y_id"],
                            "disease",
                            (target, mg, md),
                            extra={
                                "sign_status": "known",
                                "supporting_mutation_id": mg["x_id"],
                            },
                        )
                    )
    elif tid == "pharmacogenomic_efficacy_treatment_v2":
        responses = _by(r.get("mutation_affects_molecule_response", []), "x_id")
        for md in r.get("mutation_associated_disease", []):
            for response in responses.get(str(md["x_id"]), []):
                category_status, category = _resolved(
                    response, "response_category", "pgx_category"
                )
                direction_status, direction = _resolved(
                    response, "response_direction", "direction"
                )
                disease_context_status, disease_context = _resolved(
                    response, "disease_context"
                )
                if "conflicting" in {
                    category_status,
                    direction_status,
                    disease_context_status,
                }:
                    rejected["conflicting_direction_or_context"] += 1
                    continue
                if category != "efficacy":
                    rejected[category or "missing_category"] += 1
                    continue
                if direction not in {
                    "sensitive",
                    "sensitivity",
                    "benefit",
                    "increased_efficacy",
                    "increased_response",
                    "therapeutic_benefit",
                }:
                    rejected[direction or "missing_direction"] += 1
                    continue
                if (
                    disease_context_status != "known"
                    or disease_context != str(md["y_id"]).lower()
                ):
                    rejected["missing_or_mismatched_disease_context"] += 1
                    continue
                if not _compatible((md, response)):
                    rejected["context_mismatch"] += 1
                    continue
                add(
                    _candidate(
                        template,
                        response["y_id"],
                        "molecule",
                        md["y_id"],
                        "disease",
                        (md, response),
                        extra={
                            "sign_status": "known",
                            "response_category": "efficacy",
                            "response_direction": direction,
                            "supporting_mutation_id": md["x_id"],
                        },
                    )
                )
    else:
        raise NotImplementedError(tid)
    return out


def _deduplicate(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        # Derived views can have several meaningful records for the same endpoint
        # pair (for example one row per associated pathway member or disease
        # anchor).  Preserve that identity instead of laundering it into support
        # multiplicity on one edge-like row.
        identity = (
            row["x_id"],
            row["y_id"],
            row["inference_template_id"],
            str(row.get("associated_member_id", "")),
            str(row.get("anchor_disease_id", "")),
        )
        grouped[identity].append(row)
    result: list[dict[str, Any]] = []
    for key, paths in sorted(grouped.items()):
        first = min(paths, key=lambda row: row["derivation_hash"])
        first = dict(first)
        first["support_multiplicity"] = len(paths)
        first["derivation_hashes"] = _json(
            sorted(row["derivation_hash"] for row in paths)
        )
        result.append(first)
    return result


def _inventory_key_sha256(keys: set[str]) -> str:
    return hashlib.sha256(_json(sorted(keys)).encode()).hexdigest()


def _validated_inventory_receipt(
    config: BuildConfig,
    relation: str,
    edge_paths: Sequence[Path],
    evidence_paths: Sequence[Path],
) -> str:
    """Return the accepted receipt hash only for an exact, complete inventory."""
    if len(edge_paths) != 1 or len(evidence_paths) != 1:
        return ""
    receipt_path = (
        config.input_root
        / "manifest"
        / "canonical_target_inventory"
        / f"{relation}.json"
    )
    if not receipt_path.is_file():
        return ""
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            return ""
        claimed_hash = receipt.get("receipt_sha256")
        unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if (
            not isinstance(claimed_hash, str)
            or claimed_hash != _sha(unsigned)
            or claimed_hash != config.canonical_target_inventory_receipt_sha256
        ):
            return ""
        if (
            receipt.get("receipt_version")
            != CANONICAL_TARGET_INVENTORY_RECEIPT_VERSION
            or receipt.get("accepted") is not True
            or receipt.get("relation") != relation
            or receipt.get("snapshot_id") != config.snapshot_id
            or not config.canonical_target_inventory_source_identity
            or receipt.get("source_identity")
            != config.canonical_target_inventory_source_identity
        ):
            return ""

        edge_path = edge_paths[0]
        evidence_path = evidence_paths[0]
        edge_frame = pd.read_parquet(edge_path)
        evidence_frame = pd.read_parquet(evidence_path)
        required_columns = {"edge_key", "relation"}
        if (
            edge_frame.empty
            or evidence_frame.empty
            or not required_columns.issubset(edge_frame.columns)
            or not required_columns.issubset(evidence_frame.columns)
            or set(edge_frame["relation"].astype(str)) != {relation}
            or set(evidence_frame["relation"].astype(str)) != {relation}
        ):
            return ""
        edge_keys = set(edge_frame["edge_key"].astype(str))
        evidence_keys = set(evidence_frame["edge_key"].astype(str))
        supported = edge_keys & evidence_keys
        orphans = evidence_keys - edge_keys
        gaps = edge_keys - evidence_keys
        expected = {
            "receipt_version": CANONICAL_TARGET_INVENTORY_RECEIPT_VERSION,
            "accepted": True,
            "relation": relation,
            "snapshot_id": config.snapshot_id,
            "source_identity": config.canonical_target_inventory_source_identity,
            "edges": {
                "path": str(edge_path.resolve().relative_to(config.input_root.resolve())),
                "file_sha256": _file_sha(edge_path),
                "edge_key_count": len(edge_keys),
                "edge_key_set_sha256": _inventory_key_sha256(edge_keys),
            },
            "evidence": {
                "path": str(
                    evidence_path.resolve().relative_to(config.input_root.resolve())
                ),
                "file_sha256": _file_sha(evidence_path),
                "edge_key_count": len(evidence_keys),
                "edge_key_set_sha256": _inventory_key_sha256(evidence_keys),
            },
            "coverage": {
                "supported_edge_key_count": len(supported),
                "orphan_evidence_edge_key_count": len(orphans),
                "gap_edge_key_count": len(gaps),
            },
        }
        if unsigned != expected or orphans or gaps or supported != edge_keys:
            return ""
        return claimed_hash
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return ""


def _target_pairs(
    config: BuildConfig, relation: str
) -> tuple[set[tuple[str, str]], set[tuple[str, str]], bool, str]:
    canonical_paths = _discover_file((config.input_root,), "edges", relation)
    canonical_evidence_paths = _discover_file(
        (config.input_root,), "evidence", relation
    )
    canonical = _read_files(canonical_paths, relation, config.max_rows_per_file)
    staged = _read_files(
        _discover_file(config.staged_input_roots, "edges", relation),
        relation,
        config.max_rows_per_file,
    )
    inventory_receipt_sha256 = ""
    inventory_complete = bool(canonical_paths)
    if relation == "molecule_contraindicates_disease":
        inventory_receipt_sha256 = _validated_inventory_receipt(
            config, relation, canonical_paths, canonical_evidence_paths
        )
        inventory_complete = bool(inventory_receipt_sha256)
    return (
        {(str(row["x_id"]), str(row["y_id"])) for row in canonical},
        {(str(row["x_id"]), str(row["y_id"])) for row in staged},
        inventory_complete,
        inventory_receipt_sha256,
    )


def _replace_pair(
    edge_path: Path, evidence_path: Path, rows: Sequence[dict[str, Any]]
) -> None:
    txid = uuid.uuid4().hex
    backups: dict[Path, Path] = {}
    temporary: dict[Path, Path] = {}
    evidence = [
        {
            "inferred_edge_key": f"{row['relation']}|{row['x_id']}|{row['y_id']}|{row['inference_template_id']}",
            "relation": row["relation"],
            "x_id": row["x_id"],
            "y_id": row["y_id"],
            "inference_template_id": row["inference_template_id"],
            "derivation_hash": row["derivation_hash"],
            "support_edge_ids_or_hashes": row["support_edge_ids_or_hashes"],
            "support_evidence_ids_or_hashes": row["support_evidence_ids_or_hashes"],
            "typed_path": row["typed_path"],
            "context_intersection": row["context_intersection"],
            "input_snapshot_id": row["input_snapshot_id"],
            "input_snapshot_sha256": row["input_snapshot_sha256"],
            "epistemic_class": row["epistemic_class"],
            "support_multiplicity": row["support_multiplicity"],
            **{
                key: row[key]
                for key in (
                    "support_mode",
                    "rna_measured",
                    "supporting_protein_id",
                    "supporting_cell_type_id",
                    "supporting_mutation_id",
                    "associated_member_id",
                    "anchor_disease_id",
                    "sign_status",
                    "canonical_observed_overlap",
                    "staged_source_native_overlap",
                    "canonical_target_inventory_available",
                    "canonical_target_inventory_receipt_sha256",
                    "source_releases",
                    "context_compatibility",
                    "sign_computation",
                    "conflict_state",
                )
                if key in row
            },
        }
        for row in rows
    ]
    edge_only_exclusions = set(EVIDENCE_ONLY_FIELDS)
    if "edges_inferred" in edge_path.parts:
        edge_only_exclusions.update(INFERRED_EDGE_DERIVATION_FIELDS)
    edge_rows = [
        {key: value for key, value in row.items() if key not in edge_only_exclusions}
        for row in rows
    ]
    try:
        for path, payload in ((edge_path, edge_rows), (evidence_path, evidence)):
            if payload:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(f".{path.name}.{txid}.tmp")
                pd.DataFrame(payload).to_parquet(tmp, index=False)
                temporary[path] = tmp
        for path in (edge_path, evidence_path):
            if path.exists():
                backup = path.with_name(f".{path.name}.{txid}.bak")
                os.replace(path, backup)
                backups[path] = backup
        for path, tmp in temporary.items():
            os.replace(tmp, path)
    except Exception:
        for path in temporary:
            path.unlink(missing_ok=True)
        for path, backup in backups.items():
            path.unlink(missing_ok=True)
            os.replace(backup, path)
        raise
    else:
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    finally:
        for tmp in temporary.values():
            tmp.unlink(missing_ok=True)


def _publish_output_tree(
    config: BuildConfig,
    pending_outputs: Sequence[tuple[Path, Path, list[dict[str, Any]]]],
    input_manifest: Mapping[str, Any],
    report: Mapping[str, Any],
) -> None:
    """Build a complete rule-owned tree and atomically swap it into place."""
    output_root = config.output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.tmp-", dir=output_root.parent)
    )
    backup_root = output_root.with_name(
        f".{output_root.name}.backup-{uuid.uuid4().hex}"
    )
    moved_existing = False
    try:
        for edge_path, evidence_path, generated in pending_outputs:
            _replace_pair(
                temporary_root / edge_path.relative_to(config.output_root),
                temporary_root / evidence_path.relative_to(config.output_root),
                generated,
            )
        manifest_dir = temporary_root / "manifest"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "input_manifest.json").write_text(
            json.dumps(input_manifest, indent=2, sort_keys=True) + "\n"
        )
        (manifest_dir / "template_registry_v2.json").write_text(
            json.dumps([asdict(t) for t in TEMPLATES], indent=2, sort_keys=True) + "\n"
        )
        (manifest_dir / "pilot_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        if output_root.exists():
            os.replace(output_root, backup_root)
            moved_existing = True
        try:
            os.replace(temporary_root, output_root)
        except Exception:
            if moved_existing and backup_root.exists():
                os.replace(backup_root, output_root)
                moved_existing = False
            raise
        if moved_existing:
            shutil.rmtree(backup_root)
            moved_existing = False
    finally:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)
        if moved_existing and backup_root.exists() and not output_root.exists():
            os.replace(backup_root, output_root)


def build_composition_allowlist(config: BuildConfig) -> dict[str, Any]:
    if config.producer_revision != POLICY_REVISION:
        raise ValueError(
            f"producer_revision must equal approved policy revision {POLICY_REVISION}"
        )
    unknown = set(config.template_ids) - set(TEMPLATE_BY_ID)
    if unknown:
        raise ValueError(f"unknown/unapproved template IDs: {sorted(unknown)}")
    output_root = config.output_root.resolve()
    immutable_roots = (
        config.input_root.resolve(),
        *(root.resolve() for root in config.staged_input_roots),
    )
    if any(
        output_root == root
        or output_root in root.parents
        or root in output_root.parents
        for root in immutable_roots
    ):
        raise ValueError("output root must be disjoint from immutable input roots")
    if any(part in {"edges", "evidence"} for part in config.output_root.parts):
        raise ValueError("refusing observed edges/evidence output root")
    requested = [TEMPLATE_BY_ID[tid] for tid in config.template_ids]
    relations = {
        relation for template in requested for relation in template.premises
    } | {
        template.target
        for template in requested
        if template.output_class == "inferred_edge"
    }
    loaded, input_manifest = _load(config, relations)
    counts: dict[str, Any] = {}
    samples: dict[str, Any] = {}
    generated_samples: dict[str, Any] = {}
    rejected_samples: dict[str, Any] = {}
    artifacts: dict[str, Any] = {}
    all_rejections: dict[str, Any] = {}
    pending_outputs: list[tuple[Path, Path, list[dict[str, Any]]]] = []
    for template in requested:
        rejected: Counter[str] = Counter()
        template_rejected_samples: list[dict[str, Any]] = []
        generated = _deduplicate(
            _generate(
                template,
                loaded,
                rejected,
                config.max_paths_per_template,
                template_rejected_samples,
                config.sample_limit,
            )
        )
        for row in generated:
            row["input_snapshot_id"] = config.snapshot_id
            row["input_snapshot_sha256"] = input_manifest["manifest_sha256"]
        generated_count = len(generated)
        generated_before_antijoin = generated
        if template.output_class == "inferred_edge":
            (
                observed,
                staged,
                canonical_inventory_available,
                canonical_inventory_receipt_sha256,
            ) = _target_pairs(config, template.target)
            retained = []
            for row in generated:
                pair = (row["x_id"], row["y_id"])
                row["canonical_observed_overlap"] = pair in observed
                row["staged_source_native_overlap"] = pair in staged
                row["canonical_target_inventory_available"] = (
                    canonical_inventory_available
                )
                row["canonical_target_inventory_receipt_sha256"] = (
                    canonical_inventory_receipt_sha256
                )
                if (
                    config.require_canonical_target_inventory
                    and not canonical_inventory_available
                ):
                    rejected["canonical_target_inventory_missing"] += 1
                    continue
                if pair in observed:
                    rejected["canonical_observed_overlap"] += 1
                    continue
                if pair in staged:
                    rejected["staged_source_native_overlap"] += 1
                    continue
                retained.append(row)
            generated = retained
            edge_path = (
                config.output_root
                / "edges_inferred"
                / template.target
                / f"{template.template_id}.parquet"
            )
            evidence_path = (
                config.output_root
                / "evidence_inferred"
                / template.target
                / f"{template.template_id}.parquet"
            )
        else:
            edge_path = (
                config.output_root
                / "derived_views"
                / template.target
                / f"{template.template_id}.parquet"
            )
            evidence_path = (
                config.output_root
                / "derived_views_evidence"
                / template.target
                / f"{template.template_id}.parquet"
            )
        generated_samples[template.template_id] = [
            {
                key: row[key]
                for key in (
                    "x_id",
                    "y_id",
                    "relation",
                    "derivation_hash",
                    "typed_path",
                    "input_snapshot_id",
                    "canonical_observed_overlap",
                    "staged_source_native_overlap",
                    "canonical_target_inventory_available",
                    "canonical_target_inventory_receipt_sha256",
                )
                if key in row
            }
            for row in generated_before_antijoin[: config.sample_limit]
        ]
        pending_outputs.append((edge_path, evidence_path, generated))
        if generated:
            artifacts[template.template_id] = {
                "rows": str(edge_path),
                "derivation": str(evidence_path),
            }
        counts[template.template_id] = {
            "generated_paths_before_antijoin": generated_count,
            "output_rows": len(generated),
            "epistemic_class": template.confidence,
            "output_class": template.output_class,
        }
        all_rejections[template.template_id] = dict(sorted(rejected.items()))
        rejected_samples[template.template_id] = template_rejected_samples
        samples[template.template_id] = [
            {
                key: row[key]
                for key in ("x_id", "y_id", "relation", "derivation_hash", "typed_path")
                if key in row
            }
            for row in generated[: config.sample_limit]
        ]
    # Prove the immutable source did not change after all computation and before
    # publishing any output. Generation reads only the in-memory snapshot after
    # this point, so an immutability failure cannot leave partial new artifacts.
    for path, metadata in input_manifest["files"].items():
        if _file_sha(Path(path)) != metadata["sha256"]:
            raise RuntimeError(f"input changed during build: {path}")

    report = {
        "status": "staged-only/review-required",
        "policy_revision": POLICY_REVISION,
        "registry_version": REGISTRY_VERSION,
        "snapshot_id": config.snapshot_id,
        "input_manifest_sha256": input_manifest["manifest_sha256"],
        "require_canonical_target_inventory": config.require_canonical_target_inventory,
        "counts_by_template": counts,
        "rejection_reason_counts": all_rejections,
        "generated_path_samples_before_antijoin": generated_samples,
        "rejected_path_samples": rejected_samples,
        "sampled_examples": samples,
        "artifacts": artifacts,
        "rejected_motifs": REJECTED_MOTIFS,
        "claims": {"scientific_novelty": False, "canonical_observed": False},
    }
    _publish_output_tree(config, pending_outputs, input_manifest, report)
    return report
