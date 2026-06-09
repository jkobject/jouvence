"""Credibility scoring utilities for TxGNN edges.

This module centralises logic for deduplicating evidence, computing
credibility scores, and composing multi-hop paths into aggregated edges.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Iterable, Optional, TypedDict

import pandas as pd

from .kg_schema import Credibility as SchemaCredibility


class Credibility(IntEnum):
    """IntEnum re-export mirroring :class:`kg_schema.Credibility`."""

    SINGLE_EVIDENCE = int(SchemaCredibility.SINGLE_EVIDENCE)
    MULTI_EVIDENCE = int(SchemaCredibility.MULTI_EVIDENCE)
    ESTABLISHED_FACT = int(SchemaCredibility.ESTABLISHED_FACT)


@dataclass(slots=True)
class EdgeEvidence:
    """Representation of a single piece of edge evidence."""

    source: str
    paper_id: Optional[str]
    author_group_key: Optional[str]
    raw_score: Optional[float]
    datatype: Optional[str]


class Edge(TypedDict, total=False):
    """Minimal dictionary schema for an edge entry used during merges."""

    x_id: str
    x_type: str
    y_id: str
    y_type: str
    relation: str
    display_relation: str
    source: str
    credibility: int


CURATED_DB_SOURCES: set[str] = {
    "drugbank",
    "chembl_indication",
    "chembl_moa",
    "reactome",
    "go",
    "mondo",
    "hpo",
}

DATATYPE_BUMP_ELIGIBLE: set[str] = {
    "genetic_association",
    "animal_model",
    "known_drug",
    "clinical_trial",
}


def _is_duplicate(a: EdgeEvidence, b: EdgeEvidence) -> bool:
    if a.paper_id and b.paper_id and a.paper_id == b.paper_id:
        return True
    if (
        a.paper_id
        and b.paper_id
        and a.paper_id == b.paper_id
        and (a.source.startswith(b.source) or b.source.startswith(a.source))
    ):
        return True
    return False


def _prefer_evidence(new: EdgeEvidence, current: EdgeEvidence) -> EdgeEvidence:
    new_score = new.raw_score if new.raw_score is not None else float("-inf")
    cur_score = current.raw_score if current.raw_score is not None else float("-inf")
    if new_score > cur_score:
        return new
    return current


def score_credibility(evidences: Iterable[EdgeEvidence]) -> int:
    """Compute a credibility level from a collection of evidence records."""

    evidence_list = list(evidences)
    if not evidence_list:
        return Credibility.SINGLE_EVIDENCE

    for evidence in evidence_list:
        if evidence.source in CURATED_DB_SOURCES:
            return Credibility.ESTABLISHED_FACT

    deduped: list[EdgeEvidence] = []
    for evidence in evidence_list:
        duplicate_index: Optional[int] = None
        for idx, existing in enumerate(deduped):
            if _is_duplicate(evidence, existing):
                duplicate_index = idx
                break
        if duplicate_index is None:
            deduped.append(evidence)
        else:
            deduped[duplicate_index] = _prefer_evidence(evidence, deduped[duplicate_index])

    author_groups = {ev.author_group_key for ev in deduped if ev.author_group_key}
    if author_groups:
        distinct_count = len(author_groups)
    else:
        paper_ids = {ev.paper_id for ev in deduped if ev.paper_id}
        if paper_ids:
            distinct_count = len(paper_ids)
        else:
            distinct_count = len({ev.source for ev in deduped})

    if distinct_count >= 2:
        return Credibility.MULTI_EVIDENCE

    for ev in deduped:
        if (
            ev.raw_score is not None
            and ev.raw_score >= 0.75
            and ev.datatype in DATATYPE_BUMP_ELIGIBLE
        ):
            return Credibility.MULTI_EVIDENCE

    return Credibility.SINGLE_EVIDENCE


def merge_composed_path(edges_a_c: list[Edge], edges_c_b: list[Edge]) -> list[Edge]:
    """Compose two-hop paths (A→C and C→B) into A→B edges.

    The returned edges combine relations from both hops using the pattern
    ``"composed:{relation_ac}+{relation_cb}"`, and each edge is marked with a
    ``display_relation`` of ``"via:{C_type}:{C_id}"`` to highlight the
    intermediary node. Callers should store composed edges with a dedicated
    ``relation`` distinct from any direct edge relation to avoid mixing direct
    and inferred evidence unintentionally.
    """

    composed: list[Edge] = []
    for edge_ac in edges_a_c:
        for edge_cb in edges_c_b:
            c_id = edge_ac.get("y_id")
            c_type = edge_ac.get("y_type")
            new_edge: Edge = {
                "x_id": edge_ac.get("x_id"),
                "x_type": edge_ac.get("x_type"),
                "y_id": edge_cb.get("y_id"),
                "y_type": edge_cb.get("y_type"),
                "relation": f"composed:{edge_ac.get('relation')}+{edge_cb.get('relation')}",
                "display_relation": f"via:{c_type}:{c_id}",
                "source": f"composed:{edge_ac.get('source')}+{edge_cb.get('source')}",
                "credibility": min(
                    int(edge_ac.get("credibility", Credibility.SINGLE_EVIDENCE)),
                    int(edge_cb.get("credibility", Credibility.SINGLE_EVIDENCE)),
                ),
            }

            for k, v in edge_ac.items():
                if k not in new_edge:
                    new_edge[k] = v
            for k, v in edge_cb.items():
                if k not in new_edge:
                    new_edge[k] = v

            composed.append(new_edge)

    return composed


def dedup_edges(
    edges_df: pd.DataFrame,
    key_cols: tuple[str, ...] = ("x_id", "y_id", "relation"),
) -> pd.DataFrame:
    """Deduplicate edge rows and recompute credibility based on merged evidence."""

    if edges_df.empty:
        return edges_df.copy()

    evidence_cols = {"paper_id", "author_group_key", "raw_score", "datatype"}
    has_evidence_columns = any(col in edges_df.columns for col in evidence_cols)
    if not has_evidence_columns and edges_df["source"].nunique(dropna=False) == 1:
        return (
            edges_df.drop_duplicates(subset=list(key_cols), keep="first")
            .sort_values(list(key_cols))
            .reset_index(drop=True)
        )
    if not has_evidence_columns:
        key_cols_list = list(key_cols)
        duplicate_mask = edges_df.duplicated(subset=key_cols_list, keep=False)
        if not duplicate_mask.any():
            return edges_df.sort_values(key_cols_list).reset_index(drop=True)

        unique_rows = edges_df.loc[~duplicate_mask]
        duplicate_rows = edges_df.loc[duplicate_mask]
        representatives = duplicate_rows.drop_duplicates(
            subset=key_cols_list,
            keep="first",
        ).copy()
        merged = duplicate_rows.groupby(key_cols_list, sort=False).agg({
            "source": lambda values: ",".join(dict.fromkeys(str(v) for v in values)),
            "credibility": "max",
        }).reset_index()
        representatives = representatives.drop(columns=["source", "credibility"]).merge(
            merged,
            on=key_cols_list,
            how="left",
        )
        return (
            pd.concat([unique_rows, representatives], ignore_index=True)
            .sort_values(key_cols_list)
            .reset_index(drop=True)
        )

    columns = list(edges_df.columns)
    grouped_rows: list[pd.Series] = []

    for _, group in edges_df.groupby(list(key_cols), sort=False):
        representative = group.iloc[0].copy()
        sources: list[str] = []
        evidences: list[EdgeEvidence] = []

        for _, row in group.iterrows():
            source_val = str(row.get("source", ""))
            if source_val not in sources:
                sources.append(source_val)

            evidences.append(
                EdgeEvidence(
                    source=source_val,
                    paper_id=_coerce_optional_str(row.get("paper_id")),
                    author_group_key=_coerce_optional_str(row.get("author_group_key")),
                    raw_score=_coerce_optional_float(row.get("raw_score")),
                    datatype=_coerce_optional_str(row.get("datatype")),
                )
            )

        representative["source"] = ",".join(sources)
        representative["credibility"] = score_credibility(evidences)
        grouped_rows.append(representative)

    result = pd.DataFrame(grouped_rows, columns=columns)
    result = result.sort_values(list(key_cols)).reset_index(drop=True)
    return result


def _coerce_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value)


def _coerce_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
