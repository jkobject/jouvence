"""Backfill TxGNN edge evidence records from existing canonical edge files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

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


def _pmid(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.upper().startswith("PMID:"):
        return "PMID:" + text.split(":", 1)[1].strip()
    if text.isdigit():
        return f"PMID:{text}"
    return text


def _evidence_from_edges(edges: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for _, row in edges.iterrows():
        relation = str(row["relation"])
        x_id = str(row["x_id"])
        y_id = str(row["y_id"])
        source_raw = str(row.get("source") or "")
        source, source_dataset = _split_source(source_raw)
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
                "source_record_id": f"{source_raw}:{relation}:{x_id}:{y_id}",
                "paper_id": "",
                "dataset_id": "",
                "study_id": "",
                "evidence_score": row.get("score"),
                "direction": str(row.get("direction") or ""),
                "predicate": relation,
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
            variant_id = str(row.get("variantId") or "").strip()
            if not variant_id:
                continue
            datasrc = str(row.get("datasourceId") or "clinpgx").strip() or "clinpgx"
            version = str(row.get("datasourceVersion") or "").strip()
            datatype = str(row.get("datatypeId") or "pharmacogenomics").strip()
            direction = str(row.get("directionality") or "").strip()
            evidence_level = str(row.get("evidenceLevel") or "").strip()
            pgx_category = str(row.get("pgxCategory") or datatype).strip() or datatype
            study_id = str(row.get("studyId") or "").strip()
            text_span = str(row.get("genotypeAnnotationText") or row.get("phenotypeText") or "").strip()
            literature = [_pmid(item) for item in _to_list(row.get("literature"))]
            literature = [item for item in literature if item]

            for drug in _to_list(row.get("drugs")):
                if not isinstance(drug, dict):
                    continue
                drug_id = str(drug.get("drugId") or "").strip()
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
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    counts: dict[str, int] = {}
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
