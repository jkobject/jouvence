"""Build staged miRNA aliases, miRNA nodes, and miRNA target edges.

This module deliberately writes under a staging directory, not the canonical KG
root.  It implements the S1/A4 miRNA policy:

- existing ENST transcript nodes are reused when a release-pinned source gives a
  true 1:1 transcript <-> miRBase/RNAcentral identity mapping;
- mature/precursor miRNA products are emitted as staged miRNA nodes only when
  they are distinct from the existing ENST transcript entity;
- gene-level target assertions stay gene-level;
- transcript/UTR/site-level target assertions become transcript-level only when
  the target transcript endpoint is source-native or explicitly mapped.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

EDGE_COLUMNS = [
    "x_id",
    "x_type",
    "y_id",
    "y_type",
    "relation",
    "display_relation",
    "source",
    "credibility",
]

TARGET_EVIDENCE_COLUMNS = [
    "edge_key",
    "relation",
    "x_id",
    "x_type",
    "y_id",
    "y_type",
    "evidence_type",
    "source",
    "source_dataset",
    "source_release",
    "source_record_id",
    "original_mirna_id",
    "original_mirna_name",
    "original_mirna_id_namespace",
    "mirna_mapping_method",
    "mirna_mapping_confidence",
    "original_target_id",
    "original_target_name",
    "target_id_namespace",
    "target_mapping_method",
    "target_mapping_confidence",
    "species_id",
    "species_name",
    "assay",
    "support_type",
    "predicate",
    "regulation_direction",
    "sign_or_effect",
    "target_region",
    "target_site_id",
    "chromosome",
    "start",
    "end",
    "strand",
    "genome_assembly",
    "seed_match",
    "site_type",
    "binding_site_sequence",
    "pmid",
    "cell_line",
    "cell_type",
    "tissue",
    "disease_context",
    "treatment",
    "condition",
    "confidence",
    "score",
    "p_value",
    "effect_size",
    "source_url",
    "license_checked",
    "raw_metadata_json",
]

MIRNA_NODE_COLUMNS = [
    "id",
    "name",
    "mirna_product_type",
    "species_id",
    "mirbase_mature_accession",
    "mirbase_mature_name",
    "mirbase_precursor_accession",
    "mirbase_precursor_name",
    "arm",
    "ensembl_gene_id",
    "ensembl_transcript_id",
    "rnacentral_id",
    "sequence",
    "source",
    "source_release",
    "mapping_confidence",
    "mapping_method",
]

ALIAS_COLUMNS = [
    "ensembl_transcript_id",
    "ensembl_gene_id",
    "mirbase_accession",
    "mirbase_name",
    "mirbase_entity_type",
    "rnacentral_id",
    "mapping_method",
    "mapping_confidence",
    "source_dataset",
    "source_release",
    "source_record_id",
    "species_id",
    "notes_json",
]

PROCESSING_RELATION = "mirna_precursor_produces_mature_mirna"


@dataclass(frozen=True)
class BuildCounts:
    transcript_rows: int
    source_mapping_rows: int
    alias_rows: int
    rejected_alias_rows: int
    mirna_node_rows: int
    processing_edge_rows: int
    target_source_rows: int
    mirna_targets_gene_edges: int
    mirna_targets_gene_evidence: int
    mirna_targets_transcript_edges: int
    mirna_targets_transcript_evidence: int
    skipped_target_rows: int
    missing_gene_targets: int
    missing_transcript_targets: int

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def _read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.is_dir():
        frames = [_read_table(child) for child in sorted(path.iterdir()) if child.suffix in {".parquet", ".csv", ".tsv", ".json", ".jsonl"}]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix == ".tsv":
        return pd.read_csv(path, sep="\t")
    if path.suffix == ".jsonl":
        return pd.read_json(path, lines=True)
    if path.suffix == ".json":
        return pd.read_json(path)
    raise ValueError(f"unsupported table format: {path}")


def _ensure_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = pd.NA
    return out


def _nonnull_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _first_nonnull(*values: Any) -> Any:
    for value in values:
        if value is not None and not pd.isna(value):
            return value
    return ""


def _bool_value(value: Any, default: bool = False) -> bool:
    if value is None or pd.isna(value):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "same", "same_entity"}


def _raw_metadata(row: pd.Series) -> str:
    payload = {str(k): (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def _write_parquet(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.reset_index(drop=True).to_parquet(path, index=False)


def _default_output_dir(base: Path | str = ".omoc/staging") -> Path:
    return Path(base) / f"mirna-targets-{date.today().isoformat()}"


def _filter_true_one_to_one_aliases(mapping_df: pd.DataFrame, transcript_ids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = _ensure_columns(mapping_df, ALIAS_COLUMNS + ["is_same_entity_as_transcript"])
    df["ensembl_transcript_id"] = df["ensembl_transcript_id"].map(_nonnull_str)
    df["mirbase_accession"] = df["mirbase_accession"].map(_nonnull_str)
    df["mapping_confidence"] = df["mapping_confidence"].map(lambda v: _nonnull_str(v).lower())
    df["mirbase_entity_type"] = df["mirbase_entity_type"].map(lambda v: _nonnull_str(v).lower())
    df["same_entity"] = df["is_same_entity_as_transcript"].map(lambda v: _bool_value(v, default=True))

    candidates = df[
        df["ensembl_transcript_id"].isin(transcript_ids)
        & df["mirbase_accession"].ne("")
        & df["same_entity"]
        & df["mapping_confidence"].isin({"exact", "high", "1:1", "one_to_one"})
        & ~df["mirbase_entity_type"].isin({"mature", "mature_mirna"})
    ].copy()
    if candidates.empty:
        rejected = df[df["mirbase_accession"].ne("")].copy()
        return candidates[ALIAS_COLUMNS], rejected.drop(columns=["same_entity"], errors="ignore")

    transcript_counts = candidates.groupby("ensembl_transcript_id")["mirbase_accession"].nunique()
    accession_counts = candidates.groupby("mirbase_accession")["ensembl_transcript_id"].nunique()
    one_to_one = candidates[
        candidates["ensembl_transcript_id"].map(transcript_counts).eq(1)
        & candidates["mirbase_accession"].map(accession_counts).eq(1)
    ].copy()
    rejected = df.drop(index=one_to_one.index, errors="ignore").copy()
    return one_to_one[ALIAS_COLUMNS].drop_duplicates(), rejected.drop(columns=["same_entity"], errors="ignore")


def _node_from_row(row: pd.Series, fallback_source: str = "staged") -> dict[str, Any] | None:
    product_type = _nonnull_str(_first_nonnull(row.get("mirna_product_type"), row.get("mirbase_entity_type"))).lower()
    mature_acc = _nonnull_str(
        _first_nonnull(
            row.get("mirbase_mature_accession"),
            row.get("mirbase_accession") if product_type in {"mature", "mature_mirna"} else "",
        )
    )
    precursor_acc = _nonnull_str(
        _first_nonnull(
            row.get("mirbase_precursor_accession"),
            row.get("mirbase_accession") if product_type in {"precursor", "precursor_hairpin", "hairpin"} else "",
        )
    )
    mirna_id = _nonnull_str(_first_nonnull(row.get("id"), mature_acc, precursor_acc, row.get("mirna_id"), row.get("mirbase_accession")))
    if not mirna_id:
        return None
    if not product_type:
        product_type = "mature" if mirna_id.startswith("MIMAT") else "precursor_hairpin" if mirna_id.startswith("MI") else "unknown"
    return {
        "id": mirna_id,
        "name": _nonnull_str(_first_nonnull(row.get("name"), row.get("mirna_name"), row.get("mirbase_name"), row.get("original_mirna_name"))),
        "mirna_product_type": product_type,
        "species_id": _nonnull_str(_first_nonnull(row.get("species_id"), "NCBITaxon:9606")),
        "mirbase_mature_accession": mature_acc,
        "mirbase_mature_name": _nonnull_str(_first_nonnull(row.get("mirbase_mature_name"), row.get("mirbase_name") if product_type in {"mature", "mature_mirna"} else "")),
        "mirbase_precursor_accession": precursor_acc,
        "mirbase_precursor_name": _nonnull_str(_first_nonnull(row.get("mirbase_precursor_name"), row.get("mirbase_name") if product_type in {"precursor", "precursor_hairpin", "hairpin"} else "")),
        "arm": _nonnull_str(row.get("arm")),
        "ensembl_gene_id": _nonnull_str(row.get("ensembl_gene_id")),
        "ensembl_transcript_id": _nonnull_str(row.get("ensembl_transcript_id")),
        "rnacentral_id": _nonnull_str(row.get("rnacentral_id")),
        "sequence": _nonnull_str(row.get("sequence")),
        "source": _nonnull_str(_first_nonnull(row.get("source"), row.get("source_dataset"), fallback_source)),
        "source_release": _nonnull_str(_first_nonnull(row.get("source_release"), row.get("release"))),
        "mapping_confidence": _nonnull_str(_first_nonnull(row.get("mapping_confidence"), "source_native")),
        "mapping_method": _nonnull_str(_first_nonnull(row.get("mapping_method"), "source_record")),
    }


def _build_mirna_nodes(mapping_df: pd.DataFrame, catalog_df: pd.DataFrame | None, alias_df: pd.DataFrame) -> pd.DataFrame:
    alias_accessions = set(alias_df["mirbase_accession"].map(_nonnull_str)) if not alias_df.empty else set()
    rows: list[dict[str, Any]] = []
    if catalog_df is not None and not catalog_df.empty:
        for _, row in catalog_df.iterrows():
            node = _node_from_row(row, fallback_source="miRNA catalog")
            if node and node["id"] not in alias_accessions:
                rows.append(node)
    df = _ensure_columns(mapping_df, ["is_same_entity_as_transcript", *MIRNA_NODE_COLUMNS, *ALIAS_COLUMNS])
    for _, row in df.iterrows():
        same_entity = _bool_value(row.get("is_same_entity_as_transcript"), default=False)
        if same_entity and _nonnull_str(row.get("mirbase_accession")) in alias_accessions:
            continue
        node = _node_from_row(row, fallback_source="miRNA mapping")
        if node and node["id"] not in alias_accessions:
            rows.append(node)
    if not rows:
        return pd.DataFrame(columns=MIRNA_NODE_COLUMNS)
    return pd.DataFrame(rows).drop_duplicates(subset=["id"], keep="last")[MIRNA_NODE_COLUMNS]


def _build_processing_edges(nodes: pd.DataFrame) -> pd.DataFrame:
    if nodes.empty:
        return pd.DataFrame(columns=EDGE_COLUMNS)
    rows = []
    staged_mirna_ids = set(nodes["id"].map(_nonnull_str))
    mature = nodes[nodes["mirbase_mature_accession"].map(_nonnull_str).ne("")]
    for _, row in mature.iterrows():
        precursor = _nonnull_str(row.get("mirbase_precursor_accession"))
        mature_id = _nonnull_str(row.get("id"))
        # Policy: graph edges may only point at staged/canonical endpoints.  Some
        # miRBase precursor accessions are true aliases of existing ENST
        # transcript entities, not separate miRNA nodes.  Until a cross-layer
        # transcript->mature relation is approved, omit those processing edges
        # instead of emitting x_type=mirna rows with absent MI endpoints.
        if precursor and precursor not in staged_mirna_ids:
            continue
        if precursor and mature_id and precursor != mature_id:
            rows.append(
                {
                    "x_id": precursor,
                    "x_type": "mirna",
                    "y_id": mature_id,
                    "y_type": "mirna",
                    "relation": PROCESSING_RELATION,
                    "display_relation": "produces mature miRNA",
                    "source": _nonnull_str(_first_nonnull(row.get("source"), "miRBase")),
                    "credibility": 3,
                }
            )
    return pd.DataFrame(rows).drop_duplicates(subset=["x_id", "y_id", "relation"]) if rows else pd.DataFrame(columns=EDGE_COLUMNS)


def _processing_endpoint_anti_joins(processing_edges: pd.DataFrame, mirna_nodes: pd.DataFrame) -> dict[str, int]:
    mirna_ids = set(mirna_nodes["id"].map(_nonnull_str)) if not mirna_nodes.empty else set()
    if processing_edges.empty:
        return {
            "processing_edges_missing_x_mirna_nodes": 0,
            "processing_edges_missing_y_mirna_nodes": 0,
        }
    return {
        "processing_edges_missing_x_mirna_nodes": int((~processing_edges["x_id"].map(_nonnull_str).isin(mirna_ids)).sum()),
        "processing_edges_missing_y_mirna_nodes": int((~processing_edges["y_id"].map(_nonnull_str).isin(mirna_ids)).sum()),
    }


def _resolve_mirna_id(row: pd.Series, known_mirnas: set[str], alias_df: pd.DataFrame) -> tuple[str, str, str]:
    raw = _nonnull_str(_first_nonnull(row.get("mirna_id"), row.get("mirbase_accession"), row.get("original_mirna_id")))
    if raw in known_mirnas:
        return raw, _nonnull_str(_first_nonnull(row.get("mirna_mapping_method"), "source_primary_id")), _nonnull_str(_first_nonnull(row.get("mirna_mapping_confidence"), "exact"))
    # Do not use transcript aliases as regulator nodes for mature target rows; this
    # fallback is only for source rows that explicitly point to a precursor alias.
    if not alias_df.empty and raw:
        hits = alias_df[alias_df["mirbase_accession"].astype(str).eq(raw)]
        if len(hits) == 1:
            return raw, "transcript_alias_lookup", "exact_alias_not_regulator_node"
    return raw, _nonnull_str(_first_nonnull(row.get("mirna_mapping_method"), "unresolved")), _nonnull_str(_first_nonnull(row.get("mirna_mapping_confidence"), "unresolved"))


def _evidence_row(row: pd.Series, relation: str, x_id: str, y_id: str, y_type: str, mapping_method: str, mapping_confidence: str) -> dict[str, Any]:
    source = _nonnull_str(_first_nonnull(row.get("source"), row.get("source_dataset"), "unknown"))
    source_dataset = _nonnull_str(_first_nonnull(row.get("source_dataset"), source))
    record_id = _nonnull_str(_first_nonnull(row.get("source_record_id"), row.get("id"), f"{source_dataset}:{x_id}:{y_id}"))
    out = {
        "edge_key": f"{relation}|{x_id}|{y_id}",
        "relation": relation,
        "x_id": x_id,
        "x_type": "mirna",
        "y_id": y_id,
        "y_type": y_type,
        "evidence_type": _nonnull_str(_first_nonnull(row.get("evidence_type"), "experimental_validated")),
        "source": source,
        "source_dataset": source_dataset,
        "source_release": _nonnull_str(_first_nonnull(row.get("source_release"), row.get("release"))),
        "source_record_id": record_id,
        "original_mirna_id": _nonnull_str(_first_nonnull(row.get("original_mirna_id"), row.get("mirna_id"), row.get("mirbase_accession"))),
        "original_mirna_name": _nonnull_str(_first_nonnull(row.get("original_mirna_name"), row.get("mirna_name"))),
        "original_mirna_id_namespace": _nonnull_str(_first_nonnull(row.get("original_mirna_id_namespace"), row.get("mirna_id_namespace"), "miRBase")),
        "mirna_mapping_method": mapping_method,
        "mirna_mapping_confidence": mapping_confidence,
        "original_target_id": _nonnull_str(_first_nonnull(row.get("original_target_id"), row.get("target_id"), y_id)),
        "original_target_name": _nonnull_str(_first_nonnull(row.get("original_target_name"), row.get("target_name"))),
        "target_id_namespace": _nonnull_str(_first_nonnull(row.get("target_id_namespace"), "Ensembl transcript" if y_type == "transcript" else "Ensembl gene")),
        "target_mapping_method": _nonnull_str(_first_nonnull(row.get("target_mapping_method"), "source_native_endpoint")),
        "target_mapping_confidence": _nonnull_str(_first_nonnull(row.get("target_mapping_confidence"), "exact")),
        "species_id": _nonnull_str(_first_nonnull(row.get("species_id"), "NCBITaxon:9606")),
        "species_name": _nonnull_str(_first_nonnull(row.get("species_name"), "Homo sapiens")),
        "raw_metadata_json": _raw_metadata(row),
    }
    for col in TARGET_EVIDENCE_COLUMNS:
        out.setdefault(col, _nonnull_str(row.get(col)))
    return out


def _build_target_relation(
    targets: pd.DataFrame,
    *,
    relation: str,
    y_type: str,
    transcript_ids: set[str],
    known_mirnas: set[str],
    alias_df: pd.DataFrame,
    gene_ids: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, int, int]:
    target_level = "transcript" if y_type == "transcript" else "gene"
    source_level = targets.get("target_endpoint_level", pd.Series([pd.NA] * len(targets))).map(lambda v: _nonnull_str(v).lower())
    df = targets[source_level.eq(target_level)].copy()
    edge_rows: list[dict[str, Any]] = []
    ev_rows: list[dict[str, Any]] = []
    skipped = 0
    missing_endpoints = 0
    for _, row in df.iterrows():
        x_id, mapping_method, mapping_confidence = _resolve_mirna_id(row, known_mirnas, alias_df)
        if not x_id:
            skipped += 1
            continue
        y_id = _nonnull_str(row.get("target_transcript_id") if y_type == "transcript" else row.get("target_gene_id"))
        if y_type == "gene":
            if not y_id.startswith("ENSG"):
                skipped += 1
                continue
            if gene_ids is not None and y_id not in gene_ids:
                missing_endpoints += 1
                skipped += 1
                continue
        if y_type == "transcript":
            if not y_id.startswith("ENST"):
                skipped += 1
                continue
            if y_id not in transcript_ids:
                missing_endpoints += 1
                skipped += 1
                continue
        edge_rows.append(
            {
                "x_id": x_id,
                "x_type": "mirna",
                "y_id": y_id,
                "y_type": y_type,
                "relation": relation,
                "display_relation": "targets transcript" if y_type == "transcript" else "targets gene",
                "source": _nonnull_str(_first_nonnull(row.get("source"), row.get("source_dataset"), "unknown")),
                "credibility": int(float(row.get("credibility", 2) if not pd.isna(row.get("credibility", 2)) else 2)),
            }
        )
        ev_rows.append(_evidence_row(row, relation, x_id, y_id, y_type, mapping_method, mapping_confidence))
    edges = pd.DataFrame(edge_rows, columns=EDGE_COLUMNS).drop_duplicates(subset=["x_id", "y_id", "relation"]) if edge_rows else pd.DataFrame(columns=EDGE_COLUMNS)
    evidence = pd.DataFrame(ev_rows, columns=TARGET_EVIDENCE_COLUMNS).drop_duplicates(subset=["relation", "x_id", "y_id", "source", "source_dataset", "source_record_id"]) if ev_rows else pd.DataFrame(columns=TARGET_EVIDENCE_COLUMNS)
    return edges, evidence, skipped, missing_endpoints



def _load_source_gate(source_audit_path: str | Path | None) -> dict[str, Any]:
    if not source_audit_path:
        return {
            "status": "not_provided",
            "approved_for_staged_source_backed_sample": False,
            "note": "No source audit metadata was provided; outputs must not be treated as source-backed.",
        }
    path = Path(source_audit_path)
    payload = json.loads(path.read_text())
    sources = payload.get("sources", [])
    deferred_sources = [
        src for src in sources
        if str(src.get("approval_status", "")).strip().lower() in {"defer", "deferred"}
    ]
    ingested_sources = [src for src in sources if src not in deferred_sources]
    approved = bool(ingested_sources) and all(
        bool(src.get("license_checked"))
        and bool(src.get("schema_checked"))
        and str(src.get("approval_status", "")).lower() in {"approved", "recommended"}
        for src in ingested_sources
    )
    return {
        "status": "approved" if approved else "incomplete",
        "approved_for_staged_source_backed_sample": approved,
        "audit_path": str(path),
        "sources": ingested_sources,
        "deferred_sources": deferred_sources,
    }

def build_staged_mirna_targets(
    *,
    transcript_nodes_path: str | Path,
    transcript_mirbase_mapping_path: str | Path,
    output_dir: str | Path | None = None,
    mirna_catalog_path: str | Path | None = None,
    target_source_paths: Iterable[str | Path] = (),
    gene_nodes_path: str | Path | None = None,
    source_audit_path: str | Path | None = None,
) -> dict[str, int]:
    out_dir = Path(output_dir) if output_dir is not None else _default_output_dir()
    transcript_nodes = _read_table(transcript_nodes_path)
    if "id" not in transcript_nodes.columns:
        raise ValueError("transcript nodes table must contain id")
    transcript_ids = set(transcript_nodes["id"].map(_nonnull_str))
    gene_ids: set[str] | None = None
    if gene_nodes_path:
        gene_nodes = _read_table(gene_nodes_path)
        if "id" not in gene_nodes.columns:
            raise ValueError("gene nodes table must contain id")
        gene_ids = set(gene_nodes["id"].map(_nonnull_str))

    mapping_df = _read_table(transcript_mirbase_mapping_path)
    alias_df, rejected_alias_df = _filter_true_one_to_one_aliases(mapping_df, transcript_ids)
    catalog_df = _read_table(mirna_catalog_path) if mirna_catalog_path else None
    nodes = _build_mirna_nodes(mapping_df, catalog_df, alias_df)

    target_frames = [_read_table(path) for path in target_source_paths]
    targets = pd.concat(target_frames, ignore_index=True) if target_frames else pd.DataFrame()
    # Ensure target-reported mature IDs become staged nodes even if the catalog was partial.
    if not targets.empty:
        target_node_rows = []
        for _, row in targets.iterrows():
            node = _node_from_row(row, fallback_source=_nonnull_str(_first_nonnull(row.get("source_dataset"), "miRNA target source")))
            if node:
                target_node_rows.append(node)
        if target_node_rows:
            nodes = pd.concat([nodes, pd.DataFrame(target_node_rows)[MIRNA_NODE_COLUMNS]], ignore_index=True).drop_duplicates(subset=["id"], keep="last")

    processing_edges = _build_processing_edges(nodes)

    known_mirnas = set(nodes["id"].map(_nonnull_str)) if not nodes.empty else set()
    gene_edges, gene_evidence, skipped_gene, missing_gene = _build_target_relation(
        targets,
        relation="mirna_targets_gene",
        y_type="gene",
        transcript_ids=transcript_ids,
        known_mirnas=known_mirnas,
        alias_df=alias_df,
        gene_ids=gene_ids,
    )
    tx_edges, tx_evidence, skipped_tx, missing_tx = _build_target_relation(
        targets,
        relation="mirna_targets_transcript",
        y_type="transcript",
        transcript_ids=transcript_ids,
        known_mirnas=known_mirnas,
        alias_df=alias_df,
    )

    _write_parquet(out_dir / "mappings" / "transcript_mirbase_aliases.parquet", alias_df[ALIAS_COLUMNS])
    _write_parquet(out_dir / "mappings" / "transcript_mirbase_aliases_rejected.parquet", rejected_alias_df)
    _write_parquet(out_dir / "nodes" / "mirna.parquet", nodes[MIRNA_NODE_COLUMNS])
    _write_parquet(out_dir / "edges" / f"{PROCESSING_RELATION}.parquet", processing_edges[EDGE_COLUMNS])
    _write_parquet(out_dir / "edges" / "mirna_targets_gene.parquet", gene_edges[EDGE_COLUMNS])
    _write_parquet(out_dir / "edges" / "mirna_targets_transcript.parquet", tx_edges[EDGE_COLUMNS])
    _write_parquet(out_dir / "evidence" / "mirna_targets_gene.parquet", gene_evidence[TARGET_EVIDENCE_COLUMNS])
    _write_parquet(out_dir / "evidence" / "mirna_targets_transcript.parquet", tx_evidence[TARGET_EVIDENCE_COLUMNS])

    counts = BuildCounts(
        transcript_rows=len(transcript_nodes),
        source_mapping_rows=len(mapping_df),
        alias_rows=len(alias_df),
        rejected_alias_rows=len(rejected_alias_df),
        mirna_node_rows=len(nodes),
        processing_edge_rows=len(processing_edges),
        target_source_rows=len(targets),
        mirna_targets_gene_edges=len(gene_edges),
        mirna_targets_gene_evidence=len(gene_evidence),
        mirna_targets_transcript_edges=len(tx_edges),
        mirna_targets_transcript_evidence=len(tx_evidence),
        skipped_target_rows=skipped_gene + skipped_tx,
        missing_gene_targets=missing_gene,
        missing_transcript_targets=missing_tx,
    ).as_dict()
    processing_endpoint_anti_joins = _processing_endpoint_anti_joins(processing_edges, nodes)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out_dir),
        "policy": {
            "canonical_writes": False,
            "no_gene_to_transcript_forcing": True,
            "transcript_targets_require_existing_enst": True,
            "aliases_require_true_one_to_one": True,
        },
        "counts": counts,
        "inputs": {
            "transcript_nodes_path": str(transcript_nodes_path),
            "gene_nodes_path": str(gene_nodes_path) if gene_nodes_path else "",
            "transcript_mirbase_mapping_path": str(transcript_mirbase_mapping_path),
            "mirna_catalog_path": str(mirna_catalog_path) if mirna_catalog_path else "",
            "target_source_paths": [str(p) for p in target_source_paths],
            "source_audit_path": str(source_audit_path) if source_audit_path else "",
        },
        "endpoint_anti_joins": {
            "gene_targets_missing_from_gene_nodes": missing_gene,
            "transcript_targets_missing_from_transcript_nodes": missing_tx,
            **processing_endpoint_anti_joins,
            "gene_nodes_checked": gene_ids is not None,
            "transcript_nodes_checked": True,
            "mirna_nodes_checked": True,
        },
        "source_gate": _load_source_gate(source_audit_path),
    }
    (out_dir / "reports").mkdir(parents=True, exist_ok=True)
    (out_dir / "reports" / "build_summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript-nodes", required=True, help="Existing canonical/staged nodes/transcript.parquet")
    parser.add_argument("--transcript-mirbase-mapping", required=True, help="Release-pinned ENST<->miRBase mapping table")
    parser.add_argument("--mirna-catalog", default=None, help="Optional mature/precursor miRNA catalog table")
    parser.add_argument("--target-source", action="append", default=[], help="Approved source-native target table; repeatable")
    parser.add_argument("--gene-nodes", default=None, help="Optional nodes/gene.parquet for gene endpoint anti-join validation")
    parser.add_argument("--source-audit", default=None, help="Optional JSON document describing source license/schema approvals for this staged sample")
    parser.add_argument("--output-dir", default=None, help="Defaults to .omoc/staging/mirna-targets-YYYY-MM-DD")
    args = parser.parse_args(argv)
    counts = build_staged_mirna_targets(
        transcript_nodes_path=args.transcript_nodes,
        transcript_mirbase_mapping_path=args.transcript_mirbase_mapping,
        mirna_catalog_path=args.mirna_catalog,
        target_source_paths=args.target_source,
        output_dir=args.output_dir,
        gene_nodes_path=args.gene_nodes,
        source_audit_path=args.source_audit,
    )
    print(json.dumps(counts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
