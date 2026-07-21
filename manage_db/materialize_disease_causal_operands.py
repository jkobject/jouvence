"""Materialize fail-closed disease causal operands on accepted staged evidence."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd


_UNIPROT_GOF_CAUSAL_PHRASE = re.compile(
    r"\b(?:disorder|disease)\s+due\s+to\s+(?:an?\s+)?gain[ -]of[ -]function\s+defect\b",
    re.IGNORECASE,
)
_EXACT_MAPPING = {
    "exact_uniprot_accession_to_existing_protein_node",
    "exact_disease_xref_to_existing_disease_node",
}
_EXPECTED_SOURCES = {
    "reviewed_human_disease_comments": "UniProtKB",
    "humsavar_missense_variants": "UniProtKB/humsavar",
}
CONTRACT_VERSION = "disease-causal-operands-v1"
AGGREGATION_STATES = {"single", "consensus", "conflicting", "unknown"}
STAGING_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "staged"
REQUIRED_ASSERTION_COLUMNS = (
    "operand_source_family",
    "operand_source_record_id",
    "operand_source_release",
    "operand_mapping_path",
    "mechanism_operand",
    "disease_direction_operand",
    "operand_confidence",
    "operand_support_class",
    "mechanism_operand_conflict",
    "disease_direction_operand_conflict",
    "operand_reject_reason",
    "disease_operand_contract_version",
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


def _empty(*, reject_reason: str = "no_eligible_explicit_operand") -> dict[str, str]:
    return {
        "mechanism_operand": "",
        "disease_direction_operand": "",
        "operand_support_class": "unusable",
        "operand_confidence": "unknown",
        "reject_reason": reject_reason,
    }


def _truthy(value: Any) -> bool:
    return _clean(value).lower() in {"1", "true", "yes"}


def _mapping_reject_reason(row: Mapping[str, Any], *, require_variant: bool) -> str:
    if not _clean(row.get("disease_source_id")) or not _clean(row.get("y_id")):
        return "missing_disease_context"
    if require_variant and (
        not _clean(row.get("variant_ft_id")) or not _clean(row.get("source_record_id"))
    ):
        return "missing_exact_variant_identity"
    if _clean(row.get("isoform")) != "canonical":
        return "mixed_or_noncanonical_isoform"
    mapping = set(_clean(row.get("mapping_confidence")).split(";"))
    if not _EXACT_MAPPING.issubset(mapping):
        return "ambiguous_or_inexact_mapping"
    if not _clean(row.get("x_id")) or not _clean(row.get("uniprot_accession")):
        return "ambiguous_or_inexact_mapping"
    return ""


def normalize_disease_operand_assertion(row: Mapping[str, Any]) -> dict[str, str]:
    """Normalize only explicit, disease-specific source assertions."""

    dataset = _clean(row.get("source_dataset"))
    if dataset not in _EXPECTED_SOURCES:
        return _empty(reject_reason="unsupported_source_family_or_mapping")
    if not all(_clean(row.get(column)) for column in ("source", "source_record_id", "release")):
        return _empty(reject_reason="missing_source_provenance")
    if _clean(row.get("source")) != _EXPECTED_SOURCES[dataset]:
        return _empty(reject_reason="source_family_mismatch")
    mapping_reject = _mapping_reject_reason(
        row,
        require_variant=dataset == "humsavar_missense_variants",
    )
    if mapping_reject:
        return _empty(reject_reason=mapping_reject)
    if (
        dataset == "humsavar_missense_variants"
        and _clean(row.get("source_record_id")) != _clean(row.get("variant_ft_id"))
    ):
        return _empty(reject_reason="variant_source_record_mismatch")

    text = _clean(row.get("disease_description"))
    if dataset == "reviewed_human_disease_comments" and _UNIPROT_GOF_CAUSAL_PHRASE.search(text):
        return {
            "mechanism_operand": "gain_of_function",
            "disease_direction_operand": "risk",
            "operand_support_class": "explicit_uniprot_disease_causal_phrase",
            "operand_confidence": "direct_explicit",
            "reject_reason": "",
        }
    if dataset == "humsavar_missense_variants" and _clean(row.get("variant_category")).upper() == "LP/P":
        return {
            "mechanism_operand": "",
            "disease_direction_operand": "risk",
            "operand_support_class": "explicit_humsavar_pathogenic_variant_disease",
            "operand_confidence": "direct_explicit",
            "reject_reason": "",
        }
    return _empty()


def _aggregate(
    values: pd.Series,
    assertion_ids: pd.Series,
    conflicts: pd.Series | None = None,
) -> tuple[list[str], str]:
    if conflicts is not None and conflicts.fillna(False).astype(bool).any():
        unique_values = sorted({_clean(value) for value in values if _clean(value)})
        return unique_values, "conflicting"
    usable = pd.DataFrame({"value": values.map(_clean), "assertion_id": assertion_ids.map(_clean)})
    usable = usable[(usable["value"] != "") & (usable["assertion_id"] != "")].drop_duplicates()
    unique_values = sorted(set(usable["value"]))
    if not unique_values:
        return [], "unknown"
    if len(unique_values) > 1:
        return unique_values, "conflicting"
    assertion_count = usable["assertion_id"].nunique()
    return unique_values, "single" if assertion_count == 1 else "consensus"


def aggregate_edge_operands(group: pd.DataFrame) -> dict[str, Any]:
    """Aggregate assertion operands without selecting through conflicts."""

    mechanisms, mechanism_status = _aggregate(
        group["mechanism_operand"],
        group["materialization_assertion_id"],
        group.get("mechanism_operand_conflict"),
    )
    directions, direction_status = _aggregate(
        group["disease_direction_operand"],
        group["materialization_assertion_id"],
        group.get("disease_direction_operand_conflict"),
    )
    return {
        "causal_mechanisms": mechanisms,
        "mechanism_status": mechanism_status,
        "effect_directions": directions,
        "effect_direction_status": direction_status,
    }


def _mapping_path(row: pd.Series) -> str:
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


def _mark_assertion_conflicts(evidence: pd.DataFrame, operand: str) -> pd.Series:
    semantic_variants = evidence.groupby(
        ["edge_key", "materialization_assertion_id"], sort=False
    )[operand].transform(lambda values: values.map(_clean).nunique(dropna=False))
    return semantic_variants.gt(1)


def materialize_disease_operands(
    edges: pd.DataFrame,
    evidence: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Enrich accepted protein-disease rows while conserving source rows."""

    required_edges = {"x_id", "x_type", "y_id", "y_type", "relation"}
    required_evidence = {
        *required_edges,
        "edge_key",
        "source",
        "source_dataset",
        "source_record_id",
        "release",
        "materialization_assertion_id",
    }
    for label, frame, required in (
        ("edges", edges, required_edges),
        ("evidence", evidence, required_evidence),
    ):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{label} missing required columns: {missing}")
        if set(frame["relation"].map(_clean)) != {"disease_associated_protein"}:
            raise ValueError(f"{label} relation must be disease_associated_protein")
        if set(frame["x_type"].map(_clean)) != {"protein"} or set(
            frame["y_type"].map(_clean)
        ) != {"disease"}:
            raise ValueError(f"{label} endpoint types must be protein to disease")
    edge_keys = (
        edges["relation"].map(_clean)
        + "|"
        + edges["x_id"].map(_clean)
        + "|"
        + edges["y_id"].map(_clean)
    )
    if edge_keys.duplicated().any():
        raise ValueError("edges contain duplicate edge identities")
    reconstructed_evidence_keys = (
        evidence["relation"].map(_clean)
        + "|"
        + evidence["x_id"].map(_clean)
        + "|"
        + evidence["y_id"].map(_clean)
    )
    if not reconstructed_evidence_keys.equals(evidence["edge_key"].map(_clean)):
        raise ValueError("evidence edge_key differs from reconstructed edge key")
    if set(reconstructed_evidence_keys) - set(edge_keys):
        raise ValueError("evidence contains keys without a disease_associated_protein edge")

    enriched_evidence = evidence.copy().reset_index(drop=True)
    normalized = pd.DataFrame(
        [normalize_disease_operand_assertion(row) for row in enriched_evidence.to_dict("records")],
        index=enriched_evidence.index,
    )
    enriched_evidence["operand_source_family"] = enriched_evidence["source_dataset"].map(
        {
            "reviewed_human_disease_comments": "UniProtKB_reviewed_disease_comment",
            "humsavar_missense_variants": "UniProtKB_humsavar",
        }
    ).fillna("unsupported")
    enriched_evidence["operand_source_record_id"] = enriched_evidence["source_record_id"].map(_clean)
    enriched_evidence["operand_source_release"] = enriched_evidence["release"].map(_clean)
    enriched_evidence["operand_mapping_path"] = enriched_evidence.apply(_mapping_path, axis=1)
    enriched_evidence["mechanism_operand"] = normalized["mechanism_operand"]
    enriched_evidence["disease_direction_operand"] = normalized["disease_direction_operand"]
    enriched_evidence["operand_confidence"] = normalized["operand_confidence"]
    enriched_evidence["operand_support_class"] = normalized["operand_support_class"]
    enriched_evidence["operand_reject_reason"] = normalized["reject_reason"]
    inherited_conflict = enriched_evidence.get(
        "materialization_assertion_conflict", pd.Series(False, index=enriched_evidence.index)
    ).map(_truthy)
    enriched_evidence["mechanism_operand_conflict"] = inherited_conflict | _mark_assertion_conflicts(
        enriched_evidence, "mechanism_operand"
    )
    enriched_evidence["disease_direction_operand_conflict"] = (
        inherited_conflict
        | _mark_assertion_conflicts(enriched_evidence, "disease_direction_operand")
    )
    enriched_evidence["disease_operand_contract_version"] = CONTRACT_VERSION
    enriched_evidence["normalized_causal_mechanism"] = enriched_evidence["mechanism_operand"]
    enriched_evidence["normalized_effect_direction"] = enriched_evidence["disease_direction_operand"]

    enriched_edges = edges.copy().reset_index(drop=True)
    groups = {key: group for key, group in enriched_evidence.groupby("edge_key", sort=False)}
    aggregates: list[dict[str, Any]] = []
    empty = enriched_evidence.iloc[0:0]
    for edge_key in edge_keys:
        aggregate = aggregate_edge_operands(groups.get(edge_key, empty))
        aggregate["causal_mechanisms"] = json.dumps(
            aggregate["causal_mechanisms"], separators=(",", ":")
        )
        aggregate["effect_directions"] = json.dumps(
            aggregate["effect_directions"], separators=(",", ":")
        )
        aggregates.append(aggregate)
    aggregate_frame = pd.DataFrame(aggregates, index=enriched_edges.index)
    for column in aggregate_frame:
        enriched_edges[column] = aggregate_frame[column]
    enriched_edges["both_operands_known"] = (
        enriched_edges["mechanism_status"].isin({"single", "consensus"})
        & enriched_edges["effect_direction_status"].isin({"single", "consensus"})
    )
    enriched_edges["disease_operand_contract_version"] = CONTRACT_VERSION
    return enriched_edges, enriched_evidence


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _semantic_hash(frame: pd.DataFrame) -> str:
    payload = frame.to_json(orient="records", date_format="iso", double_precision=15)
    return hashlib.sha256(payload.encode()).hexdigest()


def _status_counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    counts = frame[column].value_counts().to_dict()
    return {state: int(counts.get(state, 0)) for state in sorted(AGGREGATION_STATES)}


def _collapsed_coverage(frame: pd.DataFrame, column: str) -> dict[str, int]:
    counts = _status_counts(frame, column)
    return {
        "known": counts["single"] + counts["consensus"],
        "unknown": counts["unknown"],
        "conflicting": counts["conflicting"],
    }


def _known_status(values: pd.Series) -> pd.Series:
    return values.isin({"single", "consensus"})


def _has_signed_action(value: Any) -> bool:
    try:
        parsed = json.loads(_clean(value))
    except (json.JSONDecodeError, TypeError):
        parsed = [_clean(value)]
    values = parsed if isinstance(parsed, list) else [parsed]
    return bool({_clean(item) for item in values} & {"negative", "positive"})


def _source_inventory(evidence: pd.DataFrame, source_revision: str) -> dict[str, Any]:
    assertions = evidence.drop_duplicates(
        subset=["operand_source_family", "materialization_assertion_id"], keep="first"
    )
    families: dict[str, Any] = {}
    raw_semantics = {
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
            "disease_direction_semantics": "risk from the same explicit causal disease phrase",
        },
        "UniProtKB_humsavar": {
            "raw_fields": [
                "variant_category",
                "variant_ft_id",
                "disease_source_id",
                "mapping_confidence",
            ],
            "accepted_values": {"variant_category": ["LP/P"]},
            "mechanism_semantics": "none; missense/consequence/pathogenicity never implies GoF/LoF",
            "disease_direction_semantics": "risk/pathogenic",
        },
    }
    for family in sorted(raw_semantics):
        rows = assertions[assertions["operand_source_family"] == family]
        usable = (rows["mechanism_operand"] != "") | (rows["disease_direction_operand"] != "")
        rejects = Counter(rows.loc[~usable, "operand_reject_reason"].map(_clean))
        families[family] = {
            **raw_semantics[family],
            "denominator": int(len(rows)),
            "evidence_rows": int((evidence["operand_source_family"] == family).sum()),
            "eligible_assertions": int(usable.sum()),
            "mapped_assertions": int(usable.sum()),
            "rejects_by_reason": {
                reason: int(count) for reason, count in sorted(rejects.items()) if reason
            },
            "license": sorted(set(rows.get("license", pd.Series(dtype=str)).map(_clean)) - {""}),
            "release": sorted(set(rows["operand_source_release"].map(_clean)) - {""}),
            "snapshot": source_revision,
        }
    families["ClinVar_OpenTargets_local"] = {
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
        "mechanism_semantics": "not materialized; consequence, L2G, LD, and proximity are not mechanism",
        "disease_direction_semantics": "not materialized without a local exact protein/variant/disease snapshot",
        "denominator": 0,
        "evidence_rows": 0,
        "eligible_assertions": 0,
        "mapped_assertions": 0,
        "rejects_by_reason": {"missing_local_source_snapshot": 1},
        "license": [],
        "release": [],
        "snapshot": source_revision,
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "source_revision": source_revision,
        "source_families": families,
    }


def _coverage_report(
    before_edges: pd.DataFrame,
    before_evidence: pd.DataFrame,
    after_edges: pd.DataFrame,
    after_evidence: pd.DataFrame,
    molecule_edges: pd.DataFrame,
) -> dict[str, Any]:
    required_molecule_columns = {
        "x_id",
        "x_type",
        "y_id",
        "y_type",
        "relation",
        "action_direction",
        "action_status",
    }
    missing = sorted(required_molecule_columns - set(molecule_edges))
    if missing:
        raise ValueError(f"molecule edges missing required columns: {missing}")
    if set(molecule_edges["relation"].map(_clean)) != {"molecule_targets_protein"}:
        raise ValueError("molecule edge relation must be molecule_targets_protein")
    if set(molecule_edges["x_type"].map(_clean)) != {"molecule"} or set(
        molecule_edges["y_type"].map(_clean)
    ) != {"protein"}:
        raise ValueError("molecule edge endpoint types must be molecule to protein")
    identities = molecule_edges[["relation", "x_id", "y_id"]].astype(str)
    if identities.duplicated().any():
        raise ValueError("molecule edges contain duplicate edge identities")
    joined_before = molecule_edges.merge(
        before_edges,
        left_on="y_id",
        right_on="x_id",
        suffixes=("_drug", "_disease"),
    )
    joined_after = molecule_edges.merge(
        after_edges,
        left_on="y_id",
        right_on="x_id",
        suffixes=("_drug", "_disease"),
    )
    drug_known_before = _known_status(joined_before["action_status"]) & joined_before[
        "action_direction"
    ].map(_has_signed_action)
    drug_known_after = _known_status(joined_after["action_status"]) & joined_after[
        "action_direction"
    ].map(_has_signed_action)
    disease_known_before = _known_status(joined_before["mechanism_status"]) & _known_status(
        joined_before["effect_direction_status"]
    )
    disease_known_after = _known_status(joined_after["mechanism_status"]) & _known_status(
        joined_after["effect_direction_status"]
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "conservation": {
            "edge_rows": {"before": int(len(before_edges)), "after": int(len(after_edges))},
            "evidence_rows": {
                "before": int(len(before_evidence)),
                "after": int(len(after_evidence)),
            },
        },
        "mechanism_status": {
            "before": _status_counts(before_edges, "mechanism_status"),
            "after": _status_counts(after_edges, "mechanism_status"),
        },
        "effect_direction_status": {
            "before": _status_counts(before_edges, "effect_direction_status"),
            "after": _status_counts(after_edges, "effect_direction_status"),
        },
        "mechanism_coverage": {
            "before": _collapsed_coverage(before_edges, "mechanism_status"),
            "after": _collapsed_coverage(after_edges, "mechanism_status"),
        },
        "effect_direction_coverage": {
            "before": _collapsed_coverage(before_edges, "effect_direction_status"),
            "after": _collapsed_coverage(after_edges, "effect_direction_status"),
        },
        "both_operands_known": {
            "before": int(
                (
                    _known_status(before_edges["mechanism_status"])
                    & _known_status(before_edges["effect_direction_status"])
                ).sum()
            ),
            "after": int(after_edges["both_operands_known"].sum()),
        },
        "joined_paths": {
            "total": int(len(joined_after)),
            "drug_action_known": int(drug_known_after.sum()),
            "fully_signed_before": int((drug_known_before & disease_known_before).sum()),
            "fully_signed_after": int((drug_known_after & disease_known_after).sum()),
        },
    }


def _write_exclusive(directory_fd: int, name: str, payload: bytes) -> None:
    """Write beneath an already-open directory without following path replacements."""

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    file_fd = os.open(name, flags, 0o644, dir_fd=directory_fd)
    try:
        view = memoryview(payload)
        while view:
            view = view[os.write(file_fd, view) :]
        os.fsync(file_fd)
    finally:
        os.close(file_fd)


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


def _bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stage_disease_operands(
    *,
    disease_edges_path: Path,
    disease_evidence_path: Path,
    molecule_edges_path: Path,
    output_root: Path,
    source_revision: str,
    task_id: str,
) -> dict[str, Any]:
    """Write one immutable task-scoped staged disease operand candidate."""

    output_root = Path(output_root)
    if re.fullmatch(r"t_[a-z0-9_]+", task_id) is None:
        raise ValueError("task id must match t_[a-z0-9_]+")
    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    if STAGING_ROOT.is_symlink():
        raise ValueError(f"staging root must not be a symlink: {STAGING_ROOT}")
    staging_root = STAGING_ROOT.resolve()
    expected_root = staging_root / task_id
    if output_root.is_symlink():
        raise ValueError(f"output root must not be a symlink: {output_root}")
    if output_root.absolute() != expected_root or output_root.parent.resolve() != staging_root:
        raise ValueError(f"output root must equal {expected_root}")
    if output_root.exists():
        raise FileExistsError(f"immutable output root already exists: {output_root}")
    for path in (disease_edges_path, disease_evidence_path, molecule_edges_path, output_root):
        resolved = str(Path(path).resolve())
        if resolved.startswith(("/Users/jkobject/mnt/gcs", "/mnt/gcs")):
            raise ValueError(f"GCS-FUSE path forbidden for local staged build: {resolved}")
    before_edges = pd.read_parquet(disease_edges_path)
    before_evidence = pd.read_parquet(disease_evidence_path)
    molecule_edges = pd.read_parquet(molecule_edges_path)
    after_edges, after_evidence = materialize_disease_operands(before_edges, before_evidence)
    source_inventory = _source_inventory(after_evidence, source_revision)
    coverage = _coverage_report(
        before_edges,
        before_evidence,
        after_edges,
        after_evidence,
        molecule_edges,
    )

    raw_evidence_columns = [
        column
        for column in before_evidence.columns
        if not column.startswith("normalized_")
    ]
    edge_identity = ["x_id", "x_type", "y_id", "y_type", "relation"]
    validation = {
        "edge_row_conservation": len(before_edges) == len(after_edges),
        "evidence_row_conservation": len(before_evidence) == len(after_evidence),
        "edge_identity_conservation": before_edges[edge_identity].equals(after_edges[edge_identity]),
        "raw_evidence_conservation": before_evidence[raw_evidence_columns].equals(
            after_evidence[raw_evidence_columns]
        ),
        "valid_aggregation_states": all(
            set(after_edges[column]) <= AGGREGATION_STATES
            for column in ("mechanism_status", "effect_direction_status")
        ),
    }
    if not all(validation.values()):
        raise ValueError(f"staged disease operand validation failed: {validation}")
    edge_payload = _parquet_bytes(after_edges)
    evidence_payload = _parquet_bytes(after_evidence)
    inventory_payload = _json_bytes(source_inventory)
    coverage_payload = _json_bytes(coverage)
    edge_output = expected_root / "edges" / "disease_associated_protein.parquet"
    evidence_output = expected_root / "evidence" / "disease_associated_protein.parquet"
    inventory_path = expected_root / "reports" / "source_operand_inventory.json"
    coverage_path = expected_root / "reports" / "coverage_before_after.json"
    receipt = {
        "task_id": task_id,
        "source_revision": source_revision,
        "contract_version": CONTRACT_VERSION,
        "staging_only": True,
        "canonical_write": False,
        "inputs": {
            "disease_edges": {"path": str(disease_edges_path), "sha256": _sha256(disease_edges_path)},
            "disease_evidence": {
                "path": str(disease_evidence_path),
                "sha256": _sha256(disease_evidence_path),
            },
            "molecule_edges": {"path": str(molecule_edges_path), "sha256": _sha256(molecule_edges_path)},
        },
        "outputs": {
            "disease_edges": {
                "path": str(edge_output),
                "sha256": _bytes_sha256(edge_payload),
                "semantic_sha256": _semantic_hash(after_edges),
            },
            "disease_evidence": {
                "path": str(evidence_output),
                "sha256": _bytes_sha256(evidence_payload),
                "semantic_sha256": _semantic_hash(after_evidence),
            },
            "source_operand_inventory": {
                "path": str(inventory_path),
                "sha256": _bytes_sha256(inventory_payload),
            },
            "coverage_before_after": {
                "path": str(coverage_path),
                "sha256": _bytes_sha256(coverage_payload),
            },
        },
        "coverage": coverage,
        "validation": validation,
    }
    staging_fd = os.open(staging_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    opened_fds: list[int] = []
    try:
        try:
            os.mkdir(task_id, 0o755, dir_fd=staging_fd)
        except FileExistsError as exc:
            raise FileExistsError(f"immutable output root already exists: {expected_root}") from exc
        output_fd = os.open(
            task_id,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=staging_fd,
        )
        opened_fds.append(output_fd)
        directory_fds: dict[str, int] = {}
        for name in ("edges", "evidence", "reports"):
            os.mkdir(name, 0o755, dir_fd=output_fd)
            directory_fd = os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=output_fd,
            )
            opened_fds.append(directory_fd)
            directory_fds[name] = directory_fd
        _write_exclusive(
            directory_fds["edges"], "disease_associated_protein.parquet", edge_payload
        )
        _write_exclusive(
            directory_fds["evidence"],
            "disease_associated_protein.parquet",
            evidence_payload,
        )
        _write_exclusive(
            directory_fds["reports"], "source_operand_inventory.json", inventory_payload
        )
        _write_exclusive(
            directory_fds["reports"], "coverage_before_after.json", coverage_payload
        )
        _write_exclusive(
            directory_fds["reports"], "materialization_manifest.json", _json_bytes(receipt)
        )
        opened = os.fstat(output_fd)
        linked = os.stat(task_id, dir_fd=staging_fd, follow_symlinks=False)
        if (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino):
            raise RuntimeError("output root changed during descriptor-relative write")
    finally:
        for file_descriptor in reversed(opened_fds):
            os.close(file_descriptor)
        os.close(staging_fd)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disease-edges", type=Path, required=True)
    parser.add_argument("--disease-evidence", type=Path, required=True)
    parser.add_argument("--molecule-edges", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args(argv)
    receipt = stage_disease_operands(
        disease_edges_path=args.disease_edges,
        disease_evidence_path=args.disease_evidence,
        molecule_edges_path=args.molecule_edges,
        output_root=args.output_root,
        source_revision=args.source_revision,
        task_id=args.task_id,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())