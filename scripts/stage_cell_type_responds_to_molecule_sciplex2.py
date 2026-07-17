#!/usr/bin/env python3
"""Stage a conservative Sci-Plex2 candidate/context table.

This is intentionally staged-only. It accepts only source rows that carry:
- a direct cell_type label from the obs metadata;
- a compound perturbation;
- at least one ChEMBL identifier in the source obs row;
- dose/time context.

It does not synthesize from cell-line response screens and does not promote to
canonical KG. The current pert-gym Sci-Plex2 obs artifact exposes condition
metadata and per-cell QC fields but no source-native response/effect metric
relative to controls. Because observation counts are exposure support rather
than response evidence, this script intentionally writes candidate/rejected
context tables and empty edge/evidence Parquets for the responds_to relation.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from manage_db.kg_evidence import EVIDENCE_PARQUET_COLUMNS
from manage_db.kg_schema import EDGE_PARQUET_COLUMNS

RELATION = "cell_type_responds_to_molecule"
DISPLAY_RELATION = "responds to"
SOURCE = "scPerturb/Sci-Plex"
SOURCE_DATASET = "scperturb/srivatsan20_sciplex2"
SOURCE_RELEASE = "pert-gym canonical 20260621; obs artifact scperturb/srivatsan20_sciplex2/obs.parquet"
PAPER_ID = "PMID:31978363"

# Source obs cell_type labels are not CL IDs. Keep the pilot bounded to labels
# that can be mapped directly by exact CL name or exact synonym in Cell Ontology.
CELL_TYPE_MAP = {
    "pneumocyte": {
        "cl_id": "CL:0000322",
        "cl_name": "pulmonary alveolar epithelial cell",
        "mapping_basis": "Cell Ontology exact synonym: pneumocyte",
    },
    "mammary gland epithelial cell": {
        "cl_id": "CL:0002327",
        "cl_name": "mammary gland epithelial cell",
        "mapping_basis": "Cell Ontology exact label",
    },
    "lymphoblast": {
        "cl_id": "CL:0017005",
        "cl_name": "lymphoblast",
        "mapping_basis": "Cell Ontology exact label",
    },
}

EDGE_COLUMNS = [name for name, _ in EDGE_PARQUET_COLUMNS]
EVIDENCE_COLUMNS = [name for name, _ in EVIDENCE_PARQUET_COLUMNS]

CANDIDATE_COLUMNS = [
    "source",
    "source_dataset",
    "source_record_id",
    "source_cell_type_label",
    "cell_type_id",
    "cell_type_name",
    "cell_type_mapping_basis",
    "cell_line",
    "tissue",
    "assay",
    "suspension_type",
    "pert_name",
    "pert_compound",
    "pert_target",
    "molecule_id",
    "molecule_id_namespace",
    "pert_dose",
    "dose_value",
    "dose_unit",
    "pert_time",
    "response_metric_name",
    "response_metric_value",
    "n_source_obs",
    "source_release",
    "paper_id",
    "raw_context_json",
]
REJECTED_COLUMNS = CANDIDATE_COLUMNS + ["reject_reason"]


def _clean(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "na"} else text


def _split_chembl(value: Any) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    ids = []
    for part in re.split(r"[;,|]\s*", text):
        part = part.strip()
        if re.fullmatch(r"CHEMBL\d+", part):
            ids.append(part)
    return sorted(set(ids))


def _dose_unit(row: pd.Series) -> str:
    dose = _clean(row.get("pert_dose"))
    match = re.search(r"[0-9.]+\s*([^0-9.\s]+)$", dose)
    return match.group(1) if match else ""


def _source_record_id(row: pd.Series, chembl_id: str) -> str:
    parts = [
        SOURCE_DATASET,
        _clean(row.get("cell_type")),
        _clean(row.get("cell_line")),
        _clean(row.get("pert_name")) or _clean(row.get("pert_compound")),
        chembl_id,
        _clean(row.get("pert_dose")),
        _clean(row.get("pert_time")),
    ]
    return ":".join(p.replace(":", "_") for p in parts if p)


def build(obs_path: Path, out_dir: Path, *, min_cells: int) -> dict[str, Any]:
    obs = pd.read_parquet(obs_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()

    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    considered = obs.loc[obs.get("pert_type", "").astype(str).str.lower().eq("compound")].copy()
    considered = considered.loc[~considered.get("pert_name", "").astype(str).str.lower().isin(["vehicle", "control", "nan", "none", ""])]

    group_cols = [
        "cell_type",
        "cell_line",
        "tissue",
        "assay",
        "suspension_type",
        "pert_name",
        "pert_compound",
        "pert_target",
        "pert_dose",
        "dose_value",
        "pert_time",
        "chembl-ID",
    ]
    for col in group_cols:
        if col not in considered.columns:
            considered[col] = ""
    grouped = considered.groupby(group_cols, dropna=False).size().reset_index(name="n_source_obs")

    for _, row in grouped.iterrows():
        cell_label = _clean(row.get("cell_type"))
        mapping = CELL_TYPE_MAP.get(cell_label)
        chembl_ids = _split_chembl(row.get("chembl-ID"))
        base = {
            "source": SOURCE,
            "source_dataset": SOURCE_DATASET,
            "source_record_id": "",
            "source_cell_type_label": cell_label,
            "cell_type_id": mapping["cl_id"] if mapping else "",
            "cell_type_name": mapping["cl_name"] if mapping else "",
            "cell_type_mapping_basis": mapping["mapping_basis"] if mapping else "",
            "cell_line": _clean(row.get("cell_line")),
            "tissue": _clean(row.get("tissue")),
            "assay": _clean(row.get("assay")),
            "suspension_type": _clean(row.get("suspension_type")),
            "pert_name": _clean(row.get("pert_name")),
            "pert_compound": _clean(row.get("pert_compound")),
            "pert_target": _clean(row.get("pert_target")),
            "molecule_id": "",
            "molecule_id_namespace": "ChEMBL",
            "pert_dose": _clean(row.get("pert_dose")),
            "dose_value": _clean(row.get("dose_value")),
            "dose_unit": _dose_unit(row),
            "pert_time": _clean(row.get("pert_time")),
            "response_metric_name": "not_available_in_obs_metadata",
            "response_metric_value": pd.NA,
            "n_source_obs": int(row.get("n_source_obs") or 0),
            "source_release": SOURCE_RELEASE,
            "paper_id": PAPER_ID,
            "raw_context_json": json.dumps({k: _clean(row.get(k)) for k in group_cols}, sort_keys=True),
        }
        reasons = []
        if not mapping:
            reasons.append("cell_type_label_not_mapped_to_CL_by_exact_label_or_synonym")
        if not chembl_ids:
            reasons.append("missing_source_chembl_id")
        dose_numeric = pd.to_numeric(row.get("dose_value"), errors="coerce")
        if pd.isna(dose_numeric) or float(dose_numeric) <= 0:
            reasons.append("zero_or_missing_dose_value")
        if int(row.get("n_source_obs") or 0) < min_cells:
            reasons.append(f"n_source_obs_below_min_cells_{min_cells}")
        if reasons:
            rec = dict(base)
            rec["reject_reason"] = ";".join(reasons)
            rejected.append(rec)
            continue
        for chembl_id in chembl_ids:
            rec = dict(base)
            rec["molecule_id"] = chembl_id
            rec["source_record_id"] = _source_record_id(row, chembl_id)
            rows.append(rec)

    candidates = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    rejected_df = pd.DataFrame(rejected, columns=REJECTED_COLUMNS)

    # Downgrade: accepted rows are condition candidates only. A responds_to edge
    # needs source-native response/effect evidence versus controls; n_source_obs
    # is only support for exposure/condition presence and must not be emitted as
    # evidence_score/effect_size for cell_type_responds_to_molecule.
    edges = pd.DataFrame(columns=EDGE_COLUMNS)
    evidence = pd.DataFrame(columns=EVIDENCE_COLUMNS)

    cell_nodes = (
        candidates[["cell_type_id", "cell_type_name"]]
        .drop_duplicates()
        .rename(columns={"cell_type_id": "id", "cell_type_name": "name"})
    ) if not candidates.empty else pd.DataFrame(columns=["id", "name"])
    mol_nodes = (
        candidates[["molecule_id", "pert_name"]]
        .drop_duplicates()
        .rename(columns={"molecule_id": "id", "pert_name": "name"})
    ) if not candidates.empty else pd.DataFrame(columns=["id", "name"])

    paths = {
        "edges": out_dir / "edges" / f"{RELATION}.parquet",
        "evidence": out_dir / "evidence" / f"{RELATION}.parquet",
        "candidates": out_dir / "candidates" / f"{RELATION}_sciplex2_candidates.parquet",
        "rejected": out_dir / "candidates" / f"{RELATION}_sciplex2_rejected.parquet",
        "cell_type_nodes": out_dir / "nodes" / "cell_type.parquet",
        "molecule_nodes": out_dir / "nodes" / "molecule.parquet",
    }
    for p in paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)

    pq.write_table(pa.Table.from_pandas(edges, preserve_index=False), paths["edges"])
    pq.write_table(pa.Table.from_pandas(evidence, preserve_index=False), paths["evidence"])
    pq.write_table(pa.Table.from_pandas(candidates, preserve_index=False), paths["candidates"])
    pq.write_table(pa.Table.from_pandas(rejected_df, preserve_index=False), paths["rejected"])
    pq.write_table(pa.Table.from_pandas(cell_nodes, preserve_index=False), paths["cell_type_nodes"])
    pq.write_table(pa.Table.from_pandas(mol_nodes, preserve_index=False), paths["molecule_nodes"])

    edge_pairs = set(map(tuple, edges[["x_id", "y_id"]].astype(str).to_numpy())) if not edges.empty else set()
    ev_pairs = set(map(tuple, evidence[["x_id", "y_id"]].astype(str).to_numpy())) if not evidence.empty else set()
    cell_ids = set(cell_nodes["id"].astype(str)) if not cell_nodes.empty else set()
    mol_ids = set(mol_nodes["id"].astype(str)) if not mol_nodes.empty else set()
    validation = {
        "edge_rows": int(len(edges)),
        "evidence_rows": int(len(evidence)),
        "candidate_context_rows": int(len(candidates)),
        "rejected_context_rows": int(len(rejected_df)),
        "distinct_cell_types": int(len(cell_ids)),
        "distinct_molecules": int(len(mol_ids)),
        "edge_without_evidence": int(len(edge_pairs - ev_pairs)),
        "evidence_without_edge": int(len(ev_pairs - edge_pairs)),
        "edge_x_cell_type_antijoin": int((~edges["x_id"].astype(str).isin(cell_ids)).sum()) if not edges.empty else 0,
        "edge_y_molecule_antijoin": int((~edges["y_id"].astype(str).isin(mol_ids)).sum()) if not edges.empty else 0,
        "evidence_x_cell_type_antijoin": int((~evidence["x_id"].astype(str).isin(cell_ids)).sum()) if not evidence.empty else 0,
        "evidence_y_molecule_antijoin": int((~evidence["y_id"].astype(str).isin(mol_ids)).sum()) if not evidence.empty else 0,
    }
    rejection_reason_counts: dict[str, int] = {}
    if not rejected_df.empty:
        for reasons in rejected_df["reject_reason"].fillna(""):
            for reason in str(reasons).split(";"):
                if reason:
                    rejection_reason_counts[reason] = rejection_reason_counts.get(reason, 0) + 1
    candidate_example_columns = [
        "source_cell_type_label",
        "cell_type_id",
        "pert_name",
        "molecule_id",
        "pert_dose",
        "pert_time",
        "n_source_obs",
        "response_metric_name",
    ]
    rejected_example_columns = candidate_example_columns + ["reject_reason"]
    summary = {
        "relation": RELATION,
        "source": SOURCE,
        "source_dataset": SOURCE_DATASET,
        "source_obs_path": str(obs_path),
        "output_dir": str(out_dir),
        "created_at": created_at,
        "min_cells": min_cells,
        "validation": validation,
        "paths": {k: str(v) for k, v in paths.items()},
        "artifact_status": "candidate_context_only_no_edges_emitted",
        "promotion_recommendation": "do_not_promote_to_cell_type_responds_to_molecule_without_source_native_response_effect_metric_vs_control",
        "downgrade_reason": "Sci-Plex2 obs metadata supports direct cell_type/molecule/dose/time candidate contexts, but exposes no DE, viability, perturbation-response score, dose effect, or other response/effect metric relative to controls. n_source_obs is condition support only.",
        "response_metric": {
            "available": False,
            "name": "not_available_in_obs_metadata",
            "effect_size_column": None,
            "evidence_score_column": None,
        },
        "examples": {
            "candidate_context_rows": candidates[candidate_example_columns].head(5).to_dict("records"),
            "rejected_rows": rejected_df[rejected_example_columns].head(5).to_dict("records"),
        },
        "rejection_reason_counts": rejection_reason_counts,
        "source_audit": {
            "accepted": "Sci-Plex2 obs rows have direct source cell_type labels, compound perturbations, dose/time, and ChEMBL IDs for a bounded candidate-context subset only.",
            "rejected_sources": [
                "LINCS L1000/GDSC/PRISM/Broad PRISM are cell-line/sample response screens, not direct cell_type endpoints.",
                "Sci-Plex3 has direct cell_type + compound dose/time but lacks source ChEMBL IDs in the current pert-gym obs artifact, so it is not staged here.",
                "scPerturb CRISPR datasets are gene perturbations, not molecule response sources for this relation.",
                "Tahoe-100M was not staged in this bounded pilot because current manifest metadata does not expose reviewed molecule IDs or response metrics for KG endpoint validation.",
            ],
            "limitation": "No responds_to edges/evidence emitted: n_source_obs is source condition support, not a response/effect metric.",
        },
    }
    report_path = out_dir / "reports" / f"{RELATION}_sciplex2_pilot_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    md_path = out_dir / "reports" / f"{RELATION}_sciplex2_pilot_report.md"
    md_path.write_text(
        "# Sci-Plex2 cell_type x molecule candidate-context table\n\n"
        f"Source: `{SOURCE_DATASET}` ({SOURCE_RELEASE})\n\n"
        "## Verdict\n\n"
        "Downgraded to candidate/context only: Sci-Plex2 obs metadata carries source-native `cell_type`, compound perturbation, ChEMBL IDs for some rows, dose, and time, "
        "but no response/effect metric versus controls. No `cell_type_responds_to_molecule` edges/evidence are emitted.\n\n"
        "## Validation\n\n"
        + "\n".join(f"- `{k}`: {v}" for k, v in validation.items())
        + "\n\n## Outputs\n\n"
        + "\n".join(f"- `{k}`: `{v}`" for k, v in paths.items())
        + "\n\n## Residual risk\n\n"
        "Candidate rows are endpoint/context support only. Canonical promotion requires a reviewed source-native response/effect computation (for example DE signature magnitude/significance versus controls) before any responds_to edge emission.\n",
        encoding="utf-8",
    )
    summary["paths"]["report_json"] = str(report_path)
    summary["paths"]["report_md"] = str(md_path)
    report_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--obs-parquet", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--min-cells", type=int, default=3)
    args = parser.parse_args()
    summary = build(args.obs_parquet, args.out_dir, min_cells=args.min_cells)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
