#!/usr/bin/env python3
"""Prepare a bounded real-data input snapshot for composition-allowlist pilots.

This helper reads only explicitly supplied local staged Parquets. It never reads or
writes canonical GCS/LaminDB. The mutation transcript→gene bridge is retained only
when OpenTargets transcript and contained-gene evidence share the exact mutation,
approved symbol, release, and consequence payload.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import duckdb
import pandas as pd
import pyarrow.parquet as pq


def _metadata(path: Path) -> dict[str, object]:
    parquet = pq.ParquetFile(path)
    return {
        "path": str(path),
        "rows": parquet.metadata.num_rows,
        "columns": parquet.schema_arrow.names,
    }


def _write(root: Path, layer: str, relation: str, frame: pd.DataFrame) -> None:
    path = root / layer / f"{relation}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def prepare(
    *,
    output_root: Path,
    mutation_transcript_edges: Path,
    mutation_transcript_evidence: Path,
    mutation_gene_evidence: Path,
    cell_tissue_edges: Path,
    cell_tissue_evidence: Path,
    disease_tissue_edges: Path,
    disease_tissue_evidence: Path,
    limit: int,
) -> dict[str, object]:
    output_root.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(database=":memory:")
    connection.execute("SET threads=2")
    connection.execute("SET memory_limit='2GB'")
    # Evidence rows are paired by exact source mutation plus release, approved
    # symbol and consequence payload. This prevents plain genomic containment
    # from becoming an attribution premise.
    query = """
        WITH tx AS (
          SELECT e.*, ev.source_record_id, ev.edge_key AS evidence_edge_key,
                 ev.source AS evidence_source, ev.source_dataset, ev.release,
                 ev.predicate, ev.text_span,
                 json_extract_string(ev.text_span, '$.approved_symbol') AS symbol,
                 CAST(json_extract(ev.text_span, '$.consequence_ids') AS VARCHAR) AS consequences
          FROM read_parquet(?) e
          JOIN read_parquet(?) ev USING (relation, x_id, y_id)
          WHERE json_extract_string(ev.text_span, '$.approved_symbol') IS NOT NULL
        ), gene AS (
          SELECT x_id, y_id AS gene_id, source_record_id, release, text_span,
                 json_extract_string(text_span, '$.approved_symbol') AS symbol,
                 CAST(json_extract(text_span, '$.consequence_ids') AS VARCHAR) AS consequences
          FROM read_parquet(?)
          WHERE json_extract_string(text_span, '$.approved_symbol') IS NOT NULL
        )
        SELECT tx.*, gene.gene_id, gene.source_record_id AS gene_source_record_id,
               gene.text_span AS gene_text_span
        FROM tx JOIN gene
          ON tx.x_id = gene.x_id
         AND tx.release = gene.release
         AND tx.symbol = gene.symbol
         AND tx.consequences = gene.consequences
        QUALIFY row_number() OVER (
          PARTITION BY tx.x_id, tx.y_id, gene.gene_id
          ORDER BY tx.source_record_id, gene.source_record_id
        ) = 1
        ORDER BY tx.x_id, tx.y_id, gene.gene_id
        LIMIT ?
    """
    joined = connection.execute(
        query,
        [
            str(mutation_transcript_edges),
            str(mutation_transcript_evidence),
            str(mutation_gene_evidence),
            limit,
        ],
    ).df()
    tx_columns = [
        "x_id",
        "x_type",
        "y_id",
        "y_type",
        "relation",
        "display_relation",
        "source",
        "credibility",
    ]
    transcript_edges = joined[tx_columns].drop_duplicates().reset_index(drop=True)
    transcript_evidence = (
        pd.DataFrame(
            {
                "edge_key": joined["evidence_edge_key"],
                "relation": joined["relation"],
                "x_id": joined["x_id"],
                "x_type": joined["x_type"],
                "y_id": joined["y_id"],
                "y_type": joined["y_type"],
                "source": joined["evidence_source"],
                "source_dataset": joined["source_dataset"],
                "source_record_id": joined["source_record_id"],
                "release": joined["release"],
                "predicate": joined["predicate"],
                "text_span": joined["text_span"],
                "assembly": "GRCh38",
                "mapping_version": "OpenTargets-26.03-VEP-canonical-transcript",
            }
        )
        .drop_duplicates()
        .reset_index(drop=True)
    )
    gene_transcript = (
        pd.DataFrame(
            {
                "x_id": joined["gene_id"],
                "x_type": "gene",
                "y_id": joined["y_id"],
                "y_type": "transcript",
                "relation": "gene_has_transcript",
                "display_relation": "has transcript",
                "source": "OpenTargets/variant+target exact matched consequence",
                "credibility": 3,
                "assembly": "GRCh38",
                "mapping_version": "OpenTargets-26.03-exact-mutation-symbol-consequence",
                "source_record_id": joined["gene_source_record_id"],
            }
        )
        .drop_duplicates(subset=["x_id", "y_id"])
        .reset_index(drop=True)
    )
    gene_transcript_evidence = gene_transcript.assign(
        edge_key=lambda f: (
            "gene_has_transcript|" + f.x_id.astype(str) + "|" + f.y_id.astype(str)
        ),
        source_dataset="OpenTargets variant+target",
        release="26.03",
        predicate="exact_transcript_gene_mapping_from_same_mutation_symbol_consequence",
        text_span=joined.drop_duplicates(subset=["gene_id", "y_id"])[
            "gene_text_span"
        ].reset_index(drop=True),
    )

    _write(output_root, "edges", "mutation_affects_transcript", transcript_edges)
    _write(output_root, "evidence", "mutation_affects_transcript", transcript_evidence)
    _write(output_root, "edges", "gene_has_transcript", gene_transcript)
    _write(output_root, "evidence", "gene_has_transcript", gene_transcript_evidence)

    for relation, edge_path, evidence_path in (
        ("cell_type_found_in_tissue", cell_tissue_edges, cell_tissue_evidence),
        ("disease_manifests_in_tissue", disease_tissue_edges, disease_tissue_evidence),
    ):
        edges = pd.read_parquet(edge_path).sort_values(["x_id", "y_id"]).head(limit)
        keys = set(
            edges["relation"].astype(str)
            + "|"
            + edges["x_id"].astype(str)
            + "|"
            + edges["y_id"].astype(str)
        )
        evidence = pd.read_parquet(evidence_path)
        if "edge_key" in evidence.columns:
            evidence = evidence[evidence["edge_key"].astype(str).isin(keys)]
        _write(output_root, "edges", relation, edges.reset_index(drop=True))
        _write(output_root, "evidence", relation, evidence.reset_index(drop=True))

    sources = [
        mutation_transcript_edges,
        mutation_transcript_evidence,
        mutation_gene_evidence,
        cell_tissue_edges,
        cell_tissue_evidence,
        disease_tissue_edges,
        disease_tissue_evidence,
    ]
    report = {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "staging_only": True,
        "source_files": [_metadata(path) for path in sources],
        "bounds": {
            "limit_per_real_source_family": limit,
            "duckdb_memory_limit": "2GB",
            "threads": 2,
        },
        "extracted_rows": {
            "mutation_affects_transcript": len(transcript_edges),
            "gene_has_transcript": len(gene_transcript),
            "cell_type_found_in_tissue": min(
                limit, pq.ParquetFile(cell_tissue_edges).metadata.num_rows
            ),
            "disease_manifests_in_tissue": min(
                limit, pq.ParquetFile(disease_tissue_edges).metadata.num_rows
            ),
        },
        "mapping_gate": "same OpenTargets mutation + approved symbol + release + consequence payload; containment alone is not consumed",
    }
    (output_root / "SOURCE_INVENTORY.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--mutation-transcript-edges", type=Path, required=True)
    parser.add_argument("--mutation-transcript-evidence", type=Path, required=True)
    parser.add_argument("--mutation-gene-evidence", type=Path, required=True)
    parser.add_argument("--cell-tissue-edges", type=Path, required=True)
    parser.add_argument("--cell-tissue-evidence", type=Path, required=True)
    parser.add_argument("--disease-tissue-edges", type=Path, required=True)
    parser.add_argument("--disease-tissue-evidence", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    print(json.dumps(prepare(**vars(args)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
