"""Build an immutable staged DepMap repair candidate from the legacy mixed edge file.

This module is intentionally staging-only. It splits the legacy
``cell_line_expresses_gene`` topology into source-native gene-essentiality and
gene-expression edge/evidence pairs without creating protein projections.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from .kg_evidence import EVIDENCE_PARQUET_COLUMNS
from .kg_schema import EDGE_PARQUET_COLUMNS

ESSENTIALITY = "cell_line_gene_essentiality"
EXPRESSION = "cell_line_expresses_gene"
EDGE_COLUMNS = [name for name, _ in EDGE_PARQUET_COLUMNS]
EVIDENCE_COLUMNS = [name for name, _ in EVIDENCE_PARQUET_COLUMNS]
_REQUIRED_SOURCE_COLUMNS = {
    "x_id",
    "x_type",
    "y_id",
    "y_type",
    "source",
    "credibility",
    "gene_effect",
    "expression",
    "is_essential",
}
_EXPLICIT_EXPRESSION_SQL = (
    "TRY_CAST(expression AS DOUBLE) IS NOT NULL "
    "AND NOT isnan(TRY_CAST(expression AS DOUBLE))"
)


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_query(connection: duckdb.DuckDBPyConnection, query: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection.execute(
        f"COPY ({query}) TO {_sql_string(path)} "
        "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )


def _validate_relation_artifacts(
    edge_path: Path,
    evidence_path: Path,
    *,
    cell_line_nodes: Path | None,
    gene_nodes: Path | None,
) -> dict[str, int]:
    connection = duckdb.connect()
    try:
        edge_sql = _sql_string(edge_path)
        evidence_sql = _sql_string(evidence_path)
        endpoint_selects = "0, 0"
        if cell_line_nodes is not None and gene_nodes is not None:
            endpoint_selects = f"""
                (SELECT count(*) FROM read_parquet({edge_sql}) AS edges
                 LEFT JOIN read_parquet({_sql_string(cell_line_nodes)}) AS nodes
                   ON CAST(edges.x_id AS VARCHAR) = CAST(nodes.id AS VARCHAR)
                 WHERE nodes.id IS NULL),
                (SELECT count(*) FROM read_parquet({edge_sql}) AS edges
                 LEFT JOIN read_parquet({_sql_string(gene_nodes)}) AS nodes
                   ON CAST(edges.y_id AS VARCHAR) = CAST(nodes.id AS VARCHAR)
                 WHERE nodes.id IS NULL)
            """
        values = connection.execute(
            f"""
            SELECT
                (SELECT count(*) - count(DISTINCT (relation, x_id, y_id)) FROM read_parquet({edge_sql})),
                (SELECT count(*) - count(DISTINCT (edge_key, source_record_id)) FROM read_parquet({evidence_sql})),
                (SELECT count(*) FROM (
                    SELECT relation, x_id, y_id FROM read_parquet({edge_sql})
                    EXCEPT
                    SELECT relation, x_id, y_id FROM read_parquet({evidence_sql})
                )),
                (SELECT count(*) FROM (
                    SELECT relation, x_id, y_id FROM read_parquet({evidence_sql})
                    EXCEPT
                    SELECT relation, x_id, y_id FROM read_parquet({edge_sql})
                )),
                (SELECT count(*) FROM read_parquet({edge_sql})
                 WHERE x_id IS NULL OR x_type IS NULL OR y_id IS NULL OR y_type IS NULL
                    OR relation IS NULL OR source IS NULL OR credibility IS NULL),
                (SELECT count(*) FROM read_parquet({evidence_sql})
                 WHERE edge_key IS NULL OR relation IS NULL OR x_id IS NULL OR x_type IS NULL
                    OR y_id IS NULL OR y_type IS NULL OR source IS NULL OR source_record_id IS NULL),
                {endpoint_selects}
            """
        ).fetchone()
        assert values is not None
    finally:
        connection.close()
    names = (
        "duplicate_edge_identities",
        "duplicate_evidence_identities",
        "edges_without_evidence",
        "evidence_without_edge",
        "null_edge_identity_rows",
        "null_evidence_identity_rows",
        "missing_cell_line_endpoints",
        "missing_gene_endpoints",
    )
    return {name: int(value) for name, value in zip(names, values, strict=True)}


def _edge_query(source: str, relation: str, *, explicit_expression: bool) -> str:
    where = f"WHERE {_EXPLICIT_EXPRESSION_SQL}" if explicit_expression else ""
    display = "expresses gene" if relation == EXPRESSION else "gene essentiality"
    return f"""
        SELECT
            CAST(x_id AS VARCHAR) AS x_id,
            'cell_line'::VARCHAR AS x_type,
            CAST(y_id AS VARCHAR) AS y_id,
            'gene'::VARCHAR AS y_type,
            {_sql_string(relation)}::VARCHAR AS relation,
            {_sql_string(display)}::VARCHAR AS display_relation,
            CAST(source AS VARCHAR) AS source,
            CAST(credibility AS BIGINT) AS credibility
        FROM read_parquet({_sql_string(source)})
        {where}
        ORDER BY x_id, y_id
    """


def _evidence_query(
    source: str,
    relation: str,
    source_generation: str,
    created_at: str,
    *,
    explicit_expression: bool,
) -> str:
    where = f"WHERE {_EXPLICIT_EXPRESSION_SQL}" if explicit_expression else ""
    score = "CAST(expression AS DOUBLE)" if explicit_expression else "NULL::DOUBLE"
    effect = "NULL::DOUBLE" if explicit_expression else "CAST(gene_effect AS DOUBLE)"
    direction = (
        "''::VARCHAR"
        if explicit_expression
        else "CASE WHEN CAST(is_essential AS BOOLEAN) THEN 'essential' ELSE 'not_essential' END"
    )
    predicate = "depmap_gene_expression_measurement" if explicit_expression else "depmap_gene_essentiality_measurement"
    source_dataset = "OpenTargets targetEssentiality/DepMap"
    record_payload = (
        "concat_ws('|', "
        f"{_sql_string(source_generation)}, {_sql_string(relation)}, "
        "CAST(x_id AS VARCHAR), CAST(y_id AS VARCHAR))"
    )
    return f"""
        SELECT
            concat({_sql_string(relation + '|')}, CAST(x_id AS VARCHAR), '|', CAST(y_id AS VARCHAR))::VARCHAR AS edge_key,
            {_sql_string(relation)}::VARCHAR AS relation,
            CAST(x_id AS VARCHAR) AS x_id,
            'cell_line'::VARCHAR AS x_type,
            CAST(y_id AS VARCHAR) AS y_id,
            'gene'::VARCHAR AS y_type,
            'database_record'::VARCHAR AS evidence_type,
            CAST(source AS VARCHAR) AS source,
            {_sql_string(source_dataset)}::VARCHAR AS source_dataset,
            sha256({record_payload})::VARCHAR AS source_record_id,
            ''::VARCHAR AS paper_id,
            ''::VARCHAR AS dataset_id,
            'DepMap'::VARCHAR AS study_id,
            {score} AS evidence_score,
            {effect} AS effect_size,
            NULL::DOUBLE AS p_value,
            {direction} AS direction,
            ''::VARCHAR AS confidence_interval,
            {_sql_string(predicate)}::VARCHAR AS predicate,
            ''::VARCHAR AS text_span,
            ''::VARCHAR AS section,
            'source_native_split_from_pinned_canonical_object'::VARCHAR AS extraction_method,
            ''::VARCHAR AS license,
            {_sql_string(source_generation)}::VARCHAR AS release,
            {_sql_string(created_at)}::VARCHAR AS created_at
        FROM read_parquet({_sql_string(source)})
        {where}
        ORDER BY x_id, y_id
    """


def build_depmap_repair_candidate(
    source_path: str | Path,
    output_dir: str | Path,
    *,
    source_generation: str,
    created_at: str,
    source_uri: str | None = None,
    source_metageneration: str | None = None,
    expected_source_rows: int | None = None,
    expected_expression_rows: int | None = None,
    cell_line_nodes_path: str | Path | None = None,
    gene_nodes_path: str | Path | None = None,
) -> dict[str, Any]:
    """Split one pinned legacy DepMap object into deterministic staged artifacts."""
    source = Path(source_path)
    output = Path(output_dir)
    cell_line_nodes = None if cell_line_nodes_path is None else Path(cell_line_nodes_path)
    gene_nodes = None if gene_nodes_path is None else Path(gene_nodes_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if (cell_line_nodes is None) != (gene_nodes is None):
        raise ValueError("cell-line and gene node paths must be provided together")
    for node_path in (cell_line_nodes, gene_nodes):
        if node_path is not None and not node_path.is_file():
            raise FileNotFoundError(node_path)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")

    source_columns = set(pq.read_schema(source).names)
    missing = sorted(_REQUIRED_SOURCE_COLUMNS - source_columns)
    if missing:
        raise ValueError(f"source is missing required columns: {missing}")

    connection = duckdb.connect()
    connection.execute("SET threads = 1")
    connection.execute("SET preserve_insertion_order = true")
    source_sql = str(source)
    try:
        source_stats = connection.execute(
            f"""
            SELECT
                count(*) AS source_rows,
                count(*) FILTER (WHERE {_EXPLICIT_EXPRESSION_SQL}) AS explicit_expression_rows,
                count(*) FILTER (
                    WHERE TRY_CAST(gene_effect AS DOUBLE) IS NULL
                       OR isnan(TRY_CAST(gene_effect AS DOUBLE))
                ) AS null_gene_effect_rows,
                count(*) FILTER (WHERE is_essential IS NULL) AS null_is_essential_rows,
                count(*) - count(DISTINCT (CAST(x_id AS VARCHAR), CAST(y_id AS VARCHAR))) AS duplicate_edge_identities,
                count(*) FILTER (
                    WHERE x_id IS NULL OR CAST(x_id AS VARCHAR) = ''
                       OR CAST(x_type AS VARCHAR) IS DISTINCT FROM 'cell_line'
                ) AS invalid_x_types,
                count(*) FILTER (
                    WHERE y_id IS NULL OR CAST(y_id AS VARCHAR) = ''
                       OR CAST(y_type AS VARCHAR) IS DISTINCT FROM 'gene'
                ) AS invalid_y_types,
                count(*) FILTER (WHERE source IS NULL OR CAST(source AS VARCHAR) = '') AS null_source_rows,
                count(*) FILTER (WHERE credibility IS NULL) AS null_credibility_rows
            FROM read_parquet({_sql_string(source_sql)})
            """
        ).fetchone()
        assert source_stats is not None
        stats_names = [description[0] for description in connection.description]
        stats = dict(zip(stats_names, source_stats, strict=True))
        failing = {
            name: int(stats[name])
            for name in (
                "null_gene_effect_rows",
                "null_is_essential_rows",
                "duplicate_edge_identities",
                "invalid_x_types",
                "invalid_y_types",
                "null_source_rows",
                "null_credibility_rows",
            )
            if int(stats[name]) != 0
        }
        if failing:
            raise ValueError(f"source validation failed: {failing}")

        observed_counts = {
            "source_rows": int(stats["source_rows"]),
            "explicit_expression_rows": int(stats["explicit_expression_rows"]),
        }
        expected_counts = {
            "source_rows": expected_source_rows,
            "explicit_expression_rows": expected_expression_rows,
        }
        changed_counts = {
            name: {"expected": expected, "observed": observed_counts[name]}
            for name, expected in expected_counts.items()
            if expected is not None and observed_counts[name] != expected
        }
        if changed_counts:
            raise ValueError(f"pinned count contract changed: {changed_counts}")

        if cell_line_nodes is not None and gene_nodes is not None:
            endpoint_stats = connection.execute(
                f"""
                SELECT
                    count(*) FILTER (WHERE cells.id IS NULL) AS missing_cell_line_endpoints,
                    count(*) FILTER (WHERE genes.id IS NULL) AS missing_gene_endpoints
                FROM read_parquet({_sql_string(source_sql)}) AS source
                LEFT JOIN read_parquet({_sql_string(cell_line_nodes)}) AS cells
                    ON CAST(source.x_id AS VARCHAR) = CAST(cells.id AS VARCHAR)
                LEFT JOIN read_parquet({_sql_string(gene_nodes)}) AS genes
                    ON CAST(source.y_id AS VARCHAR) = CAST(genes.id AS VARCHAR)
                """
            ).fetchone()
            assert endpoint_stats is not None
            missing_endpoints = {
                "missing_cell_line_endpoints": int(endpoint_stats[0]),
                "missing_gene_endpoints": int(endpoint_stats[1]),
            }
            if any(missing_endpoints.values()):
                raise ValueError(f"source endpoint validation failed: {missing_endpoints}")

        for relation, explicit_expression in ((ESSENTIALITY, False), (EXPRESSION, True)):
            _copy_query(
                connection,
                _edge_query(source_sql, relation, explicit_expression=explicit_expression),
                output / "edges" / f"{relation}.parquet",
            )
            _copy_query(
                connection,
                _evidence_query(
                    source_sql,
                    relation,
                    source_generation,
                    created_at,
                    explicit_expression=explicit_expression,
                ),
                output / "evidence" / f"{relation}.parquet",
            )
    finally:
        connection.close()

    expected_rows = {
        ESSENTIALITY: int(stats["source_rows"]),
        EXPRESSION: int(stats["explicit_expression_rows"]),
    }
    relations: dict[str, dict[str, Any]] = {}
    content_hashes: dict[str, str] = {}
    objects: dict[str, dict[str, Any]] = {}
    for relation, expected in expected_rows.items():
        edge_path = output / "edges" / f"{relation}.parquet"
        evidence_path = output / "evidence" / f"{relation}.parquet"
        edge_rows = pq.ParquetFile(edge_path).metadata.num_rows
        evidence_rows = pq.ParquetFile(evidence_path).metadata.num_rows
        if edge_rows != expected or evidence_rows != expected:
            raise RuntimeError(
                f"{relation} parity failed: expected={expected} edges={edge_rows} evidence={evidence_rows}"
            )
        edge_schema = pq.read_schema(edge_path).names
        evidence_schema = pq.read_schema(evidence_path).names
        if edge_schema != EDGE_COLUMNS:
            raise RuntimeError(f"{relation} edge schema mismatch: {edge_schema}")
        if evidence_schema != EVIDENCE_COLUMNS:
            raise RuntimeError(f"{relation} evidence schema mismatch: {evidence_schema}")
        validation = _validate_relation_artifacts(
            edge_path,
            evidence_path,
            cell_line_nodes=cell_line_nodes,
            gene_nodes=gene_nodes,
        )
        if any(validation.values()):
            raise RuntimeError(f"{relation} validation failed: {validation}")
        relations[relation] = {
            "edge_rows": edge_rows,
            "evidence_rows": evidence_rows,
            **validation,
        }
        for path in (edge_path, evidence_path):
            relative = path.relative_to(output).as_posix()
            sha256 = _sha256(path)
            content_hashes[relative] = sha256
            schema = pq.read_schema(path)
            objects[relative] = {
                "rows": pq.ParquetFile(path).metadata.num_rows,
                "size_bytes": path.stat().st_size,
                "sha256": sha256,
                "schema": [
                    {"name": field.name, "type": str(field.type), "nullable": field.nullable}
                    for field in schema
                ],
            }

    report: dict[str, Any] = {
        "status": "staged-only",
        "source": {
            "uri": source_uri or source.name,
            "generation": str(source_generation),
            "metageneration": None if source_metageneration is None else str(source_metageneration),
            "sha256": _sha256(source),
            "rows": int(stats["source_rows"]),
            "explicit_expression_rows": int(stats["explicit_expression_rows"]),
        },
        "transformation_policy": {
            "essentiality": "all pinned source rows; gene_effect -> evidence.effect_size; is_essential -> evidence.direction",
            "expression": "expression IS NOT NULL; explicit numeric zero retained; expression -> evidence.evidence_score",
            "topology": "standard eight edge columns only; measurements excluded",
            "protein_projection": "forbidden; no cell_line_expresses_protein output",
        },
        "relations": relations,
        "content_hashes": dict(sorted(content_hashes.items())),
        "objects": dict(sorted(objects.items())),
        "created_at": created_at,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "promotion_candidate_manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_path")
    parser.add_argument("output_dir")
    parser.add_argument("--source-generation", required=True)
    parser.add_argument("--source-metageneration")
    parser.add_argument("--source-uri")
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--expected-source-rows", type=int, required=True)
    parser.add_argument("--expected-expression-rows", type=int, required=True)
    parser.add_argument("--cell-line-nodes-path", required=True)
    parser.add_argument("--gene-nodes-path", required=True)
    args = parser.parse_args(argv)
    report = build_depmap_repair_candidate(
        args.source_path,
        args.output_dir,
        source_generation=args.source_generation,
        source_metageneration=args.source_metageneration,
        source_uri=args.source_uri,
        created_at=args.created_at,
        expected_source_rows=args.expected_source_rows,
        expected_expression_rows=args.expected_expression_rows,
        cell_line_nodes_path=args.cell_line_nodes_path,
        gene_nodes_path=args.gene_nodes_path,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
