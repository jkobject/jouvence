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


def _edge_source_metadata(row: pd.Series, relation: str, source_raw: str) -> tuple[str, str, str, str]:
    """Return source, source_dataset, source-record suffix, and predicate for an edge row."""

    source, source_dataset = _split_source(source_raw)
    predicate = relation
    suffix_parts: list[str] = []

    if relation == "molecule_targets_protein" and source == "OpenTargets":
        # Historical canonical exports use this relation name for OpenTargets
        # mechanism-of-action rows whose target endpoint is still an ENSG gene.
        # Preserve the canonical endpoint and action metadata; do not remap to ENSP.
        source_dataset = source_dataset or "drug_mechanism_of_action"
        action_type = _clean_str(row.get("action_type"))
        if action_type:
            predicate = action_type
            suffix_parts.append(action_type)

    return source, source_dataset, ":".join(suffix_parts), predicate


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


def _evidence_from_edges(edges: pd.DataFrame) -> pd.DataFrame:
    if not edges.empty and set(edges["relation"].astype(str)) == {"mutation_associated_gene"}:
        return _mutation_associated_gene_l2g_evidence_from_edges(edges)

    rows: list[dict] = []
    for _, row in edges.iterrows():
        relation = str(row["relation"])
        x_id = str(row["x_id"])
        y_id = str(row["y_id"])
        if relation == "mutation_causes_protein_change":
            rows.append(_protein_change_evidence_row(row, relation, x_id, y_id))
            continue

        source_raw = _clean_str(row.get("source"))
        source, source_dataset, source_record_suffix, predicate = _edge_source_metadata(
            row, relation, source_raw
        )
        source_record_id = f"{source_raw}:{relation}:{x_id}:{y_id}"
        if source_dataset and source_raw == source:
            source_record_id = f"{source}:{source_dataset}:{relation}:{x_id}:{y_id}"
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
                "direction": predicate if relation == "molecule_targets_protein" else str(row.get("direction") or ""),
                "predicate": predicate,
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
