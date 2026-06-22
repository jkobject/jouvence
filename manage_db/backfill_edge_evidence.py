"""Backfill TxGNN edge evidence records from existing canonical edge files."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from manage_db import kg_evidence, kg_storage
from manage_db.kg_schema import Credibility, NodeType


def _split_source(source: str) -> tuple[str, str]:
    if "/" in source:
        head, tail = source.split("/", 1)
        return head or source, tail or ""
    return source, ""


def _to_list(value: object) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if hasattr(value, "tolist"):
        converted = value.tolist()
        return converted if isinstance(converted, list) else [converted]
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    return [value]


def _clean_str(value: object) -> str:
    """Return a stripped string, treating pandas/null sentinels as empty."""

    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _score_token(value: object) -> str:
    """Stable source-record token for score-like values."""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    try:
        return f"{float(str(value)):.12g}"
    except (TypeError, ValueError):
        return _clean_str(value)


def _pmid(value: object) -> str:
    text = _clean_str(value)
    if not text:
        return ""
    if text.upper().startswith("PMID:"):
        return "PMID:" + text.split(":", 1)[1].strip()
    if text.isdigit():
        return f"PMID:{text}"
    return text


def _protein_change_evidence_row(row: pd.Series, relation: str, x_id: str, y_id: str) -> dict:
    """Build conservative OpenTargets variant evidence for mutation→protein changes."""

    source_raw = _clean_str(row.get("source")) or "OpenTargets"
    source, _ = _split_source(source_raw)
    amino_acid_change = _clean_str(row.get("amino_acid_change"))
    uniprot_id = _clean_str(row.get("uniprot_id"))
    source_record_prefix = source_raw if "/" in source_raw else f"{source_raw}/variant"
    return {
        "relation": relation,
        "x_id": x_id,
        "x_type": _clean_str(row.get("x_type")) or "mutation",
        "y_id": y_id,
        "y_type": _clean_str(row.get("y_type")) or "protein",
        "evidence_type": "database_record",
        "source": source,
        "source_dataset": "variant",
        "source_record_id": (
            f"{source_record_prefix}:{relation}:{x_id}:{y_id}:{uniprot_id}:{amino_acid_change}"
        ),
        "paper_id": "",
        "dataset_id": "",
        "study_id": "",
        "evidence_score": None,
        "direction": "",
        "predicate": "amino_acid_change",
    }


def _edge_source_metadata(
    row: pd.Series, relation: str, source_raw: str
) -> tuple[str, str, str, str, str, str, str]:
    """Return source metadata for an edge row.

    The tuple is ``(source, source_dataset, source_record_prefix,
    source_record_suffix, predicate, direction, text_span)``.  Keep broad
    normalized relation names in ``relation`` and preserve source-native detail
    in evidence metadata.
    """

    source, source_dataset = _split_source(source_raw)
    predicate = relation
    direction = _clean_str(row.get("direction"))
    suffix_parts: list[str] = []
    source_record_prefix = source_raw or source
    text_span = ""

    if relation == "molecule_targets_gene" and source == "OpenTargets":
        # Historical canonical exports use this relation name for OpenTargets
        # mechanism-of-action rows whose target endpoint is still an ENSG gene.
        # Preserve the canonical endpoint and action metadata; do not remap to ENSP.
        source_dataset = source_dataset or "drug_mechanism_of_action"
        source_record_prefix = f"{source}:{source_dataset}"
        action_type = _clean_str(row.get("action_type"))
        if action_type:
            predicate = action_type
            direction = action_type
            suffix_parts.append(action_type)
        mechanism = _clean_str(row.get("display_relation"))
        target_class = _clean_str(row.get("target_class") or row.get("targetClass"))
        release = _clean_str(row.get("release") or row.get("source_release") or row.get("datasourceVersion"))
        text_span = json.dumps(
            {
                "mechanism_of_action": mechanism or None,
                "action_type": action_type or None,
                "target_class": target_class or None,
                "target_id_namespace": "ENSG" if _clean_str(row.get("y_id")).startswith("ENSG") else None,
                "endpoint_policy": "OpenTargets MoA row retained as molecule->gene; no gene-to-protein projection",
                "release": release or None,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    elif relation == "molecule_targets_gene" and source == "TxGNN":
        # TxGNN/TxData legacy relation labels used protein wording even when
        # endpoint IDs are NCBI genes.  Do not propagate the stale protein token
        # into evidence predicate/direction/source_record_id.
        x_id = _clean_str(row.get("x_id"))
        y_type = _clean_str(row.get("y_type"))
        stale_dataset = source_dataset in {"", "molecule_targets_protein"}
        if x_id.startswith("DB"):
            source_dataset = "drug_protein" if stale_dataset else source_dataset
            predicate = "drug_protein"
        elif x_id.startswith("CTD:"):
            source_dataset = "ctd_chemical_gene" if stale_dataset else source_dataset
            predicate = "chemical_gene_target"
        else:
            source_dataset = "txdata_molecule_gene_target" if stale_dataset else source_dataset
            predicate = "targets_gene"
        direction = ""
        source_record_prefix = f"{source}:{source_dataset}"
        text_span = json.dumps(
            {
                "legacy_relation": "molecule_targets_protein",
                "legacy_source_dataset": _split_source(source_raw)[1] or None,
                "endpoint_policy": f"TxGNN molecule target row retained as molecule->{y_type or 'gene'}; no gene-to-protein projection",
                "source_detail_recovery": "x_id namespace heuristic: DrugBank DB* vs CTD:*",
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    return source, source_dataset, source_record_prefix, ":".join(suffix_parts), predicate, direction, text_span


def _release_from_edge(row: pd.Series, source: str, source_dataset: str) -> str:
    release = _clean_str(row.get("release") or row.get("source_release") or row.get("datasourceVersion"))
    if release:
        return release
    if source == "OpenTargets" and source_dataset == "drug_mechanism_of_action":
        return "26.03"
    return ""


def _mutation_associated_gene_l2g_evidence_from_edges(edges: pd.DataFrame) -> pd.DataFrame:
    """Build conservative OpenTargets L2G support rows for mutation→gene edges.

    The canonical ``mutation_associated_gene`` edge file can contain multiple
    distinct ``studyLocusId`` rows for the same mutation/gene edge. Evidence
    backfill keeps one support row per L2G source row and includes study locus,
    datatype, and score in ``source_record_id`` so those supports do not collapse.
    """

    rows: list[dict] = []
    relation = "mutation_associated_gene"
    for _, row in edges.iterrows():
        if _clean_str(row.get("relation")) != relation:
            continue
        source_raw = _clean_str(row.get("source"))
        source, source_dataset = _split_source(source_raw)
        if source != "OpenTargets" or source_dataset != "l2g":
            continue

        study_locus_id = _clean_str(row.get("studyLocusId"))
        if not study_locus_id:
            continue
        x_id = _clean_str(row.get("x_id"))
        y_id = _clean_str(row.get("y_id"))
        if not x_id or not y_id:
            continue

        datatype = _clean_str(row.get("datatype")) or "l2g"
        score = row.get("score")
        score_token = _score_token(score)
        evidence_type = "genetic_association" if datatype == "genetic_association" else "model_prediction"
        rows.append(
            {
                "relation": relation,
                "x_id": x_id,
                "x_type": _clean_str(row.get("x_type")) or "mutation",
                "y_id": y_id,
                "y_type": _clean_str(row.get("y_type")) or "gene",
                "evidence_type": evidence_type,
                "source": "OpenTargets",
                "source_dataset": "l2g",
                "source_record_id": ":".join(
                    [source_raw, relation, x_id, y_id, datatype, study_locus_id, score_token]
                ),
                "paper_id": "",
                "dataset_id": "",
                "study_id": study_locus_id,
                "evidence_score": score,
                "direction": _clean_str(row.get("direction")),
                "predicate": datatype,
                "extraction_method": "OpenTargets L2G",
            }
        )
    return pd.DataFrame(rows)


def _pathway_source_dataset(x_id: str, go_aspect: str) -> str:
    if x_id.startswith("R-HSA-"):
        return "txgnn_legacy_reactome"
    if go_aspect in {"P", "F", "C"}:
        return {"P": "go_biological_process", "F": "go_molecular_function", "C": "go_cellular_component"}[go_aspect]
    if x_id.startswith("GO:"):
        return "txgnn_legacy_go"
    return "pathway_membership"


def _pathway_contains_gene_evidence_from_edges(edges: pd.DataFrame) -> pd.DataFrame:
    """Build pathway→gene evidence while keeping current endpoints gene-level.

    OpenTargets GO annotations already carry source-native evidence/aspect on
    canonical edge rows. TxGNN/PrimeKG inherited rows do not preserve the raw
    legacy source row, PMID, or protein/participant endpoint; those rows are
    therefore marked as edge-derived legacy fallbacks instead of being projected
    to ``pathway_contains_protein``.
    """

    rows: list[dict] = []
    relation = "pathway_contains_gene"
    for _, row in edges.iterrows():
        if _clean_str(row.get("relation")) != relation:
            continue
        x_id = _clean_str(row.get("x_id"))
        y_id = _clean_str(row.get("y_id"))
        if not x_id or not y_id:
            continue
        x_type = _clean_str(row.get("x_type")) or "pathway"
        y_type = _clean_str(row.get("y_type")) or "gene"
        if y_type != "gene":
            raise ValueError(
                "pathway_contains_gene backfill refuses non-gene endpoints; "
                "use a protein-native pathway builder for protein endpoints"
            )

        source_raw = _clean_str(row.get("source"))
        source, source_dataset = _split_source(source_raw)
        go_evidence = _clean_str(row.get("go_evidence") or row.get("predicate"))
        go_aspect = _clean_str(row.get("go_aspect") or row.get("aspect"))
        release = _clean_str(row.get("release") or row.get("source_release"))
        paper_id = _pmid(row.get("pmid") or row.get("paper_id"))

        if source == "OpenTargets":
            source_dataset = "go"
            predicate = go_evidence or "go_annotation"
            direction = "gene_product_annotation"
            extraction_method = "OpenTargets target.go pathway membership"
            source_record_id = ":".join(
                part
                for part in [
                    "OpenTargets/go",
                    release,
                    y_id,
                    x_id,
                    go_evidence,
                    go_aspect,
                ]
                if part
            )
            fallback = False
        else:
            source = source or "TxGNN"
            source_dataset = source_dataset or _pathway_source_dataset(x_id, go_aspect)
            predicate = go_evidence or "pathway_membership"
            direction = relation
            extraction_method = "TxGNN legacy edge-derived pathway membership fallback"
            source_record_id = ":".join(
                part
                for part in [
                    source_raw or source,
                    source_dataset,
                    relation,
                    x_id,
                    y_id,
                    go_evidence,
                    go_aspect,
                ]
                if part
            )
            fallback = True

        text_span = json.dumps(
            {
                "original_source": source_raw,
                "source_pathway_id": x_id,
                "source_gene_id": y_id,
                "go_evidence": go_evidence or None,
                "go_aspect": go_aspect or None,
                "endpoint_policy": "gene-level pathway membership; no gene-to-protein projection",
                "edge_derived_legacy_fallback": fallback,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        rows.append(
            {
                "relation": relation,
                "x_id": x_id,
                "x_type": x_type,
                "y_id": y_id,
                "y_type": y_type,
                "evidence_type": "database_record",
                "source": source,
                "source_dataset": source_dataset,
                "source_record_id": source_record_id,
                "paper_id": paper_id,
                "dataset_id": "",
                "study_id": "",
                "evidence_score": row.get("score"),
                "direction": direction,
                "predicate": predicate,
                "text_span": text_span,
                "extraction_method": extraction_method,
                "release": release,
            }
        )
    return pd.DataFrame(rows)


def _evidence_from_edges(edges: pd.DataFrame) -> pd.DataFrame:
    if not edges.empty and set(edges["relation"].astype(str)) == {"mutation_associated_gene"}:
        return _mutation_associated_gene_l2g_evidence_from_edges(edges)
    if not edges.empty and set(edges["relation"].astype(str)) == {"pathway_contains_gene"}:
        return _pathway_contains_gene_evidence_from_edges(edges)

    rows: list[dict] = []
    for _, row in edges.iterrows():
        relation = str(row["relation"])
        x_id = str(row["x_id"])
        y_id = str(row["y_id"])
        if relation == "mutation_causes_protein_change":
            rows.append(_protein_change_evidence_row(row, relation, x_id, y_id))
            continue

        source_raw = _clean_str(row.get("source"))
        (
            source,
            source_dataset,
            source_record_prefix,
            source_record_suffix,
            predicate,
            direction,
            text_span,
        ) = _edge_source_metadata(row, relation, source_raw)
        source_record_id = f"{source_record_prefix}:{relation}:{x_id}:{y_id}"
        if source_record_suffix:
            source_record_id = f"{source_record_id}:{source_record_suffix}"
        rows.append(
            {
                "relation": relation,
                "x_id": x_id,
                "x_type": str(row["x_type"]),
                "y_id": y_id,
                "y_type": str(row["y_type"]),
                "evidence_type": "database_record",
                "source": source,
                "source_dataset": source_dataset,
                "source_record_id": source_record_id,
                "paper_id": "",
                "dataset_id": "",
                "study_id": "",
                "evidence_score": row.get("score"),
                "direction": direction,
                "predicate": predicate,
                "text_span": text_span,
                "release": _release_from_edge(row, source, source_dataset),
            }
        )
    return pd.DataFrame(rows)


def backfill_edge_evidence(kg_path: str | Path, relations: list[str]) -> dict[str, int]:
    """Create evidence Parquets from existing edge rows for selected relations."""

    root = kg_storage.open_kg_root(str(kg_path))
    counts: dict[str, int] = {}
    for relation in relations:
        if relation not in root.list_edges():
            counts[relation] = 0
            continue
        edges = kg_storage.read_edges(root, relation)
        evidence = _evidence_from_edges(edges)
        counts[relation] = kg_evidence.write_evidence(root, relation, evidence, mode="overwrite")
    return counts


def _is_protein_native_id(value: str) -> bool:
    return value.startswith(("ENSP", "UniProt:", "UNIPROT:", "RefSeqProtein:", "NP_", "XP_"))


def _frame_column(df: pd.DataFrame, name: str, default: object) -> pd.Series:
    if name in df.columns:
        return df[name]
    return pd.Series([default] * len(df), index=df.index)


def build_molecule_targets_protein_staged(
    kg_path: str | Path,
    source_rows: pd.DataFrame | str | Path,
    *,
    mode: str = "overwrite",
) -> dict[str, int]:
    """Stage source-native molecule→protein target edges and evidence.

    This is intentionally not a gene→protein projection helper. Every input row
    must already carry a protein endpoint (``y_type='protein'`` plus a protein
    or isoform-looking ID such as ENSP/UniProt/RefSeq protein). Gene endpoint
    rows belong in ``molecule_targets_gene`` and are rejected here.
    """

    if mode not in {"overwrite", "append"}:
        raise ValueError("mode must be 'overwrite' or 'append'")
    if isinstance(source_rows, (str, Path)):
        df = pd.read_parquet(source_rows)
    else:
        df = source_rows.copy()
    if df.empty:
        return {"molecule_targets_protein": 0}

    required = {"x_id", "y_id", "y_type", "source", "source_dataset"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"molecule_targets_protein source rows missing required columns: {missing}")

    df["x_id"] = df["x_id"].map(_clean_str)
    df["y_id"] = df["y_id"].map(_clean_str)
    df["y_type"] = df["y_type"].map(_clean_str)
    bad = df[(df["y_type"] != NodeType.PROTEIN.value) | ~df["y_id"].map(_is_protein_native_id)]
    if not bad.empty:
        examples = bad[["x_id", "y_id", "y_type"]].head(5).to_dict("records")
        raise ValueError(
            "molecule_targets_protein requires source-native protein endpoints; "
            f"refusing gene/projected rows: {examples}"
        )

    relation = "molecule_targets_protein"
    root = kg_storage.open_kg_root(str(kg_path))
    x_type = _frame_column(df, "x_type", NodeType.MOLECULE.value).map(_clean_str).replace("", NodeType.MOLECULE.value)
    display_relation = _frame_column(
        df,
        "mechanism",
        pd.NA,
    ).combine_first(_frame_column(df, "display_relation", pd.NA)).combine_first(
        _frame_column(df, "action_type", "targets protein")
    ).map(_clean_str).replace("", "targets protein")
    source = df["source"].map(_clean_str)
    source_dataset = df["source_dataset"].map(_clean_str)
    edges = pd.DataFrame(
        {
            "x_id": df["x_id"],
            "x_type": x_type,
            "y_id": df["y_id"],
            "y_type": NodeType.PROTEIN.value,
            "relation": relation,
            "display_relation": display_relation,
            "source": source,
            "credibility": pd.to_numeric(
                _frame_column(df, "credibility", int(Credibility.ESTABLISHED_FACT)),
                errors="coerce",
            ).fillna(int(Credibility.ESTABLISHED_FACT)).astype("int64"),
        }
    )
    edge_count = kg_storage.write_edges(root, relation, edges, mode=mode)  # type: ignore[arg-type]

    text_span = []
    for _, row in df.iterrows():
        y_id = _clean_str(row.get("y_id"))
        payload = {
            "mechanism_of_action": _clean_str(row.get("mechanism") or row.get("display_relation")) or None,
            "action_type": _clean_str(row.get("action_type")) or None,
            "target_class": _clean_str(row.get("target_class") or row.get("targetClass")) or None,
            "source_database": _clean_str(row.get("source")) or None,
            "source_dataset": _clean_str(row.get("source_dataset")) or None,
            "target_id_namespace": "ENSP" if y_id.startswith("ENSP") else "protein",
            "endpoint_policy": "source-native molecule->protein row; not projected from gene endpoint",
        }
        for source_col, payload_key in {
            "target_chembl_id": "target_chembl_id",
            "target_uniprot_id": "target_uniprot_id",
            "target_component_id": "target_component_id",
            "target_component_relationship": "target_component_relationship",
            "target_component_description": "target_component_description",
            "target_confidence": "target_confidence",
            "mechanism_comment": "mechanism_comment",
            "binding_site_comment": "binding_site_comment",
            "selectivity_comment": "selectivity_comment",
        }.items():
            value = _clean_str(row.get(source_col))
            if value:
                payload[payload_key] = value
        text_span.append(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            )
        )

    source_record = _frame_column(df, "source_record_id", "").map(_clean_str)
    fallback_record = source + ":" + source_dataset + ":" + relation + ":" + df["x_id"] + ":" + df["y_id"]
    evidence = pd.DataFrame(
        {
            "relation": relation,
            "x_id": df["x_id"],
            "x_type": x_type,
            "y_id": df["y_id"],
            "y_type": NodeType.PROTEIN.value,
            "evidence_type": "database_record",
            "source": source,
            "source_dataset": source_dataset,
            "source_record_id": source_record.where(source_record != "", fallback_record),
            "paper_id": _frame_column(df, "paper_id", "").map(_clean_str),
            "dataset_id": "",
            "study_id": _frame_column(df, "study_id", "").map(_clean_str),
            "evidence_score": pd.to_numeric(
                _frame_column(df, "score", pd.NA).combine_first(_frame_column(df, "evidence_score", pd.NA)),
                errors="coerce",
            ),
            "direction": _frame_column(df, "direction", "").map(_clean_str),
            "predicate": _frame_column(df, "predicate", pd.NA).combine_first(
                _frame_column(df, "action_type", "protein_target")
            ).map(_clean_str).replace("", "protein_target"),
            "text_span": text_span,
            "release": _frame_column(df, "release", pd.NA).combine_first(
                _frame_column(df, "source_release", "")
            ).map(_clean_str),
        }
    )
    evidence_count = kg_evidence.write_evidence(root, relation, evidence, mode=mode)  # type: ignore[arg-type]
    return {relation: min(edge_count, evidence_count)}


def _mutation_disease_batch_to_evidence(batch: pa.RecordBatch, row_offset: int) -> pa.Table:
    relation = "mutation_associated_disease"
    df = batch.to_pandas()
    n = len(df)
    source_raw = df["source"].fillna("").astype(str)
    source_parts = source_raw.str.split("/", n=1, expand=True)
    source = source_parts[0].where(source_parts[0] != "", "OpenTargets")
    if source_parts.shape[1] > 1:
        source_dataset = source_parts[1].fillna("")
    else:
        source_dataset = pd.Series([""] * n, index=df.index)
    datatype = df.get("datatype", pd.Series([""] * n, index=df.index)).fillna("").astype(str)
    study_locus = df.get("studyLocusId", pd.Series([""] * n, index=df.index)).fillna("").astype(str)
    score = pd.to_numeric(df.get("score", pd.Series([pd.NA] * n, index=df.index)), errors="coerce")
    score_token = score.map(_score_token).fillna("").astype(str)
    row_ids = pd.Series(range(row_offset, row_offset + n), index=df.index).astype(str)
    x_id = df["x_id"].fillna("").astype(str)
    y_id = df["y_id"].fillna("").astype(str)
    source_record_id = (
        source_raw + ":" + relation
        + ":" + x_id
        + ":" + y_id
        + ":datatype=" + datatype
        + ":studyLocusId=" + study_locus
        + ":score=" + score_token
        + ":row=" + row_ids
    )
    evidence_type = source_dataset.where(
        source_dataset != "gwas_credible_sets", "genetic_association"
    )
    evidence_type = evidence_type.where(evidence_type == "genetic_association", "database_record")

    out = pd.DataFrame(
        {
            "edge_key": relation + "|" + x_id + "|" + y_id,
            "relation": relation,
            "x_id": x_id,
            "x_type": df.get("x_type", pd.Series(["mutation"] * n, index=df.index)).fillna("mutation").astype(str),
            "y_id": y_id,
            "y_type": df.get("y_type", pd.Series(["disease"] * n, index=df.index)).fillna("disease").astype(str),
            "evidence_type": evidence_type,
            "source": source,
            "source_dataset": source_dataset,
            "source_record_id": source_record_id,
            "paper_id": "",
            "dataset_id": "",
            "study_id": study_locus,
            "evidence_score": score.astype("float64"),
            "effect_size": pd.Series([math.nan] * n, index=df.index, dtype="float64"),
            "p_value": pd.Series([math.nan] * n, index=df.index, dtype="float64"),
            "direction": "",
            "confidence_interval": "",
            "predicate": datatype,
            "text_span": "",
            "section": "",
            "extraction_method": "OpenTargets mutation associated disease edge backfill",
            "license": "",
            "release": "26.03",
            "created_at": "",
        }
    )
    return pa.Table.from_pandas(out, schema=kg_evidence.evidence_schema(), preserve_index=False)


def build_mutation_associated_disease_evidence(
    edge_parquet: str | Path,
    output_parquet: str | Path,
    *,
    batch_size: int = 100_000,
) -> dict[str, int]:
    """Stream-build source-aware evidence for canonical mutation→disease edges."""

    relation = "mutation_associated_disease"
    edge_parquet = Path(edge_parquet)
    output_parquet = Path(output_parquet)
    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "relation",
        "x_id",
        "x_type",
        "y_id",
        "y_type",
        "source",
        "score",
        "datatype",
        "studyLocusId",
    ]
    pf = pq.ParquetFile(edge_parquet)
    writer: pq.ParquetWriter | None = None
    rows_written = 0
    try:
        for batch in pf.iter_batches(batch_size=batch_size, columns=columns):
            table = _mutation_disease_batch_to_evidence(batch, rows_written)
            if writer is None:
                writer = pq.ParquetWriter(output_parquet, kg_evidence.evidence_schema())
            writer.write_table(table)
            rows_written += table.num_rows
    finally:
        if writer is not None:
            writer.close()
    return {relation: rows_written}


def _drugbank_mappings_from_drug_molecule_dir(drug_molecule_dir: str | Path) -> pd.DataFrame:
    """Return OpenTargets ChEMBL → DrugBank mappings from drug_molecule parquet files."""

    rows: list[tuple[str, str]] = []
    for parquet_file in sorted(Path(drug_molecule_dir).glob("*.parquet")):
        df = pd.read_parquet(parquet_file, columns=["id", "crossReferences"])
        for _, row in df.iterrows():
            chembl_id = _clean_str(row.get("id"))
            if not chembl_id:
                continue
            for ref in _to_list(row.get("crossReferences")):
                if not isinstance(ref, dict):
                    continue
                if _clean_str(ref.get("source")).lower() != "drugbank":
                    continue
                for drugbank_id in _to_list(ref.get("ids")):
                    drugbank_id = _clean_str(drugbank_id)
                    if drugbank_id.startswith("DB"):
                        rows.append((chembl_id, drugbank_id))
    if not rows:
        return pd.DataFrame(columns=["drugId", "x_id"])
    return pd.DataFrame(rows, columns=["drugId", "x_id"]).drop_duplicates()


def build_molecule_treats_disease_clinical_evidence(
    edge_parquet: str | Path,
    clinical_indication_parquet: str | Path,
    drug_molecule_dir: str | Path,
    output_parquet: str | Path,
) -> dict[str, int]:
    """Build partial OpenTargets clinical-indication support for treatment edges.

    This intentionally supports only positive indication/treatment semantics.
    It must not be used for ``molecule_contraindicates_disease`` because the
    OpenTargets clinical indication table records clinical-stage indications,
    not contraindications.
    """

    relation = "molecule_treats_disease"
    edges = pd.read_parquet(edge_parquet, columns=["x_id", "x_type", "y_id", "y_type", "relation"])
    edges = edges[edges["relation"].astype(str) == relation].copy()
    edges["x_id"] = edges["x_id"].astype(str)
    edges["y_id"] = edges["y_id"].astype(str)
    canonical = edges[["x_id", "x_type", "y_id", "y_type"]].drop_duplicates()

    mappings = _drugbank_mappings_from_drug_molecule_dir(drug_molecule_dir)
    if mappings.empty or canonical.empty:
        empty = pd.DataFrame(columns=kg_evidence.evidence_schema().names)
        output_parquet = Path(output_parquet)
        output_parquet.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(empty, schema=kg_evidence.evidence_schema(), preserve_index=False), output_parquet)
        return {relation: 0}

    clinical = pd.read_parquet(
        clinical_indication_parquet,
        columns=["id", "maxClinicalStage", "clinicalReportIds", "diseaseId", "drugId"],
    )
    clinical["drugId"] = clinical["drugId"].astype(str)
    clinical["y_id"] = clinical["diseaseId"].astype(str).str.replace("_", ":", regex=False)
    clinical = clinical.merge(mappings, on="drugId", how="inner")
    matched = clinical.merge(canonical, on=["x_id", "y_id"], how="inner")
    if matched.empty:
        output_parquet = Path(output_parquet)
        output_parquet.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(
            pa.Table.from_pandas(pd.DataFrame(columns=kg_evidence.evidence_schema().names), schema=kg_evidence.evidence_schema(), preserve_index=False),
            output_parquet,
        )
        return {relation: 0}

    matched = matched.drop_duplicates(subset=["id", "x_id", "y_id"])
    n = len(matched)
    study_id = matched["clinicalReportIds"].map(lambda value: ";".join(_clean_str(v) for v in _to_list(value) if _clean_str(v)))
    stage = matched["maxClinicalStage"].fillna("").astype(str)
    x_id = matched["x_id"].astype(str)
    y_id = matched["y_id"].astype(str)
    out = pd.DataFrame(
        {
            "edge_key": relation + "|" + x_id + "|" + y_id,
            "relation": relation,
            "x_id": x_id,
            "x_type": matched["x_type"].fillna("molecule").astype(str),
            "y_id": y_id,
            "y_type": matched["y_type"].fillna("disease").astype(str),
            "evidence_type": "clinical_trial",
            "source": "OpenTargets",
            "source_dataset": "clinical_indication",
            "source_record_id": matched["id"].astype(str),
            "paper_id": "",
            "dataset_id": "",
            "study_id": study_id,
            "evidence_score": pd.Series([math.nan] * n, index=matched.index, dtype="float64"),
            "effect_size": pd.Series([math.nan] * n, index=matched.index, dtype="float64"),
            "p_value": pd.Series([math.nan] * n, index=matched.index, dtype="float64"),
            "direction": "indication",
            "confidence_interval": "",
            "predicate": stage,
            "text_span": "",
            "section": "",
            "extraction_method": "OpenTargets clinical_indication + drug_molecule DrugBank xref",
            "license": "",
            "release": "26.03",
            "created_at": "",
        }
    )
    output_parquet = Path(output_parquet)
    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(out, schema=kg_evidence.evidence_schema(), preserve_index=False)
    pq.write_table(table, output_parquet)
    return {relation: table.num_rows}


def backfill_pharmacogenomics_evidence(
    kg_path: str | Path,
    pharmacogenomics_dir: str | Path,
) -> dict[str, int]:
    """Backfill source-aware PGx evidence for mutation-drug response edges.

    Only source rows whose ``variantId``/ChEMBL pair already exists in the
    canonical ``mutation_affects_molecule_response`` edge file are emitted.
    One ``database_record`` support row is written per matching source/drug pair,
    plus one ``paper`` support row per PMID-like literature reference.
    """

    relation = "mutation_affects_molecule_response"
    root = kg_storage.open_kg_root(str(kg_path))
    edges = kg_storage.read_edges(
        root,
        relation,
        columns=["relation", "x_id", "x_type", "y_id", "y_type"],
    )
    canonical = set(zip(edges["x_id"].astype(str), edges["y_id"].astype(str), strict=False))
    if not canonical:
        return {relation: 0}

    pgx_dir = Path(pharmacogenomics_dir)
    files = sorted(pgx_dir.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(pgx_dir)

    rows: list[dict] = []
    for parquet_file in files:
        df = pd.read_parquet(parquet_file)
        for _, row in df.iterrows():
            variant_id = _clean_str(row.get("variantId"))
            if not variant_id:
                continue
            datasrc = _clean_str(row.get("datasourceId")) or "clinpgx"
            version = _clean_str(row.get("datasourceVersion"))
            datatype = _clean_str(row.get("datatypeId")) or "pharmacogenomics"
            direction = _clean_str(row.get("directionality"))
            evidence_level = _clean_str(row.get("evidenceLevel"))
            pgx_category = _clean_str(row.get("pgxCategory")) or datatype
            study_id = _clean_str(row.get("studyId"))
            text_span = _clean_str(row.get("genotypeAnnotationText")) or _clean_str(row.get("phenotypeText"))
            literature = [_pmid(item) for item in _to_list(row.get("literature"))]
            literature = [item for item in literature if item]

            for drug in _to_list(row.get("drugs")):
                if not isinstance(drug, dict):
                    continue
                drug_id = _clean_str(drug.get("drugId"))
                if (variant_id, drug_id) not in canonical:
                    continue
                base_record = f"{datasrc}:{study_id}:{variant_id}:{drug_id}:{evidence_level}:{pgx_category}"
                common = {
                    "relation": relation,
                    "x_id": variant_id,
                    "x_type": "mutation",
                    "y_id": drug_id,
                    "y_type": "molecule",
                    "source": "OpenTargets",
                    "source_dataset": "pharmacogenomics",
                    "dataset_id": "",
                    "study_id": study_id,
                    "evidence_score": None,
                    "direction": direction,
                    "predicate": pgx_category,
                    "text_span": text_span,
                    "extraction_method": "OpenTargets pharmacogenomics",
                    "release": version,
                }
                rows.append(
                    {
                        **common,
                        "evidence_type": "database_record",
                        "source_record_id": base_record,
                        "paper_id": "",
                    }
                )
                for paper_id in literature:
                    rows.append(
                        {
                            **common,
                            "evidence_type": "paper",
                            "source_record_id": f"{base_record}:{paper_id}",
                            "paper_id": paper_id,
                        }
                    )

    if not rows:
        return {relation: 0}
    count = kg_evidence.write_evidence(root, relation, pd.DataFrame(rows), mode="overwrite")
    return {relation: count}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill TxGNN edge evidence from existing edge Parquets.")
    parser.add_argument("kg_path", help="Path or gs:// URI to a KG root.")
    parser.add_argument("relations", nargs="*", help="Relation names to backfill evidence for.")
    parser.add_argument(
        "--pharmacogenomics-dir",
        default=None,
        help="Optional OpenTargets pharmacogenomics parquet directory for source-aware PGx evidence.",
    )
    parser.add_argument(
        "--mutation-associated-disease-edge-parquet",
        default=None,
        help="Canonical mutation_associated_disease edge parquet to stream into evidence.",
    )
    parser.add_argument(
        "--output-parquet",
        default=None,
        help="Output parquet for streaming builders such as mutation_associated_disease.",
    )
    parser.add_argument(
        "--clinical-indication-parquet",
        default=None,
        help="OpenTargets clinical_indication parquet for partial molecule_treats_disease evidence staging.",
    )
    parser.add_argument(
        "--drug-molecule-dir",
        default=None,
        help="OpenTargets drug_molecule parquet directory for ChEMBL to DrugBank xrefs.",
    )
    parser.add_argument("--batch-size", type=int, default=100_000, help="Streaming batch size.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    counts: dict[str, int] = {}
    if args.mutation_associated_disease_edge_parquet:
        if not args.output_parquet:
            parser.error("--output-parquet is required with --mutation-associated-disease-edge-parquet")
        counts.update(
            build_mutation_associated_disease_evidence(
                args.mutation_associated_disease_edge_parquet,
                args.output_parquet,
                batch_size=args.batch_size,
            )
        )
    if args.clinical_indication_parquet or args.drug_molecule_dir:
        if not (args.clinical_indication_parquet and args.drug_molecule_dir and args.output_parquet):
            parser.error(
                "--clinical-indication-parquet, --drug-molecule-dir, and --output-parquet are required together"
            )
        edge_parquet = Path(args.kg_path) / "edges" / "molecule_treats_disease.parquet"
        counts.update(
            build_molecule_treats_disease_clinical_evidence(
                edge_parquet,
                args.clinical_indication_parquet,
                args.drug_molecule_dir,
                args.output_parquet,
            )
        )
    if args.pharmacogenomics_dir:
        counts.update(backfill_pharmacogenomics_evidence(args.kg_path, args.pharmacogenomics_dir))
    if args.relations:
        counts.update(backfill_edge_evidence(args.kg_path, args.relations))
    if args.json:
        print(json.dumps(counts, indent=2, sort_keys=True))
    else:
        for relation, count in counts.items():
            print(f"{relation}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
