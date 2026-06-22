"""Backfill protein-expression edges by projecting gene expression through proteins.

This module is intentionally local-root oriented: it reads from a source KG root
and writes the derived relation to a caller-supplied destination KG root.  It
never writes to the source root unless the caller explicitly passes the same
path.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from . import kg_evidence, kg_storage
from .kg_schema import Credibility, NodeType


@dataclass(frozen=True)
class ProjectionResult:
    source_relation: str
    dest_relation: str
    input_rows: int
    mapped_gene_rows: int
    unmapped_gene_rows: int
    estimated_output_rows: int
    output_rows: int
    distinct_pairs: int


class ProjectionTooLargeError(RuntimeError):
    """Raised when the projected relation exceeds the caller's row cap."""

    def __init__(self, estimated_output_rows: int, max_output_rows: int) -> None:
        super().__init__(
            f"projected output has {estimated_output_rows:,} rows, above cap {max_output_rows:,}"
        )
        self.estimated_output_rows = estimated_output_rows
        self.max_output_rows = max_output_rows


def _read_gene_protein_edges(root: kg_storage.KGRoot) -> pd.DataFrame:
    """Return distinct ENSG→ENSP rows from ``nodes/protein.ensembl_gene_id``.

    The historical ``gene_encodes_protein`` shortcut edge has been removed from
    the active KG; this helper intentionally does not read or recreate it.
    """

    proteins = kg_storage.read_nodes(
        root,
        NodeType.PROTEIN.value,
        columns=["id", "ensembl_gene_id"],
    )
    if proteins.empty or not {"id", "ensembl_gene_id"} <= set(proteins.columns):
        return pd.DataFrame(columns=["gene_id", "protein_id"])
    mapping = proteins[["ensembl_gene_id", "id"]].dropna()
    mapping = mapping[
        mapping["ensembl_gene_id"].astype(str).str.startswith("ENSG")
        & mapping["id"].astype(str).str.startswith("ENSP")
    ].rename(columns={"ensembl_gene_id": "gene_id", "id": "protein_id"})
    return mapping.drop_duplicates().reset_index(drop=True)


def estimate_expression_to_protein_rows(
    *,
    source_root: kg_storage.KGRoot,
    source_relation: str,
    source_x_type: str,
) -> tuple[int, int, int, int]:
    """Estimate projection size without materializing protein-expression rows.

    Returns ``(input_rows, mapped_gene_rows, unmapped_gene_rows,
    estimated_output_rows)``. Duplicate source edge rows are counted in
    ``input_rows`` but deduplicated before estimating the final edge count.
    """

    expr = kg_storage.read_edges(source_root, source_relation, columns=["x_id", "x_type", "y_id", "y_type"])
    input_rows = len(expr)
    expr = expr[
        (expr["x_type"].astype(str) == source_x_type)
        & (expr["y_type"].astype(str) == NodeType.GENE.value)
        & expr["y_id"].astype(str).str.startswith("ENSG")
    ][["x_id", "y_id"]].drop_duplicates()

    mapping = _read_gene_protein_edges(source_root)
    if mapping.empty or expr.empty:
        return input_rows, 0, len(expr), 0

    per_gene = mapping.groupby("gene_id", dropna=False).size().rename("protein_count").reset_index()
    joined = expr.rename(columns={"y_id": "gene_id"}).merge(per_gene, on="gene_id", how="left")
    mapped = joined["protein_count"].notna()
    mapped_gene_rows = int(mapped.sum())
    unmapped_gene_rows = int((~mapped).sum())
    estimated_output_rows = int(joined.loc[mapped, "protein_count"].sum())
    return input_rows, mapped_gene_rows, unmapped_gene_rows, estimated_output_rows


def project_expression_to_protein(
    *,
    source_root: kg_storage.KGRoot,
    dest_root: kg_storage.KGRoot,
    source_relation: str,
    dest_relation: str,
    source_x_type: str,
    max_output_rows: int = 10_000_000,
) -> ProjectionResult:
    """Build a bounded local protein-expression relation in ``dest_root``."""

    input_rows, mapped_gene_rows, unmapped_gene_rows, estimated_output_rows = estimate_expression_to_protein_rows(
        source_root=source_root,
        source_relation=source_relation,
        source_x_type=source_x_type,
    )
    if estimated_output_rows > max_output_rows:
        raise ProjectionTooLargeError(estimated_output_rows, max_output_rows)

    expr = kg_storage.read_edges(source_root, source_relation)
    expr = expr[
        (expr["x_type"].astype(str) == source_x_type)
        & (expr["y_type"].astype(str) == NodeType.GENE.value)
        & expr["y_id"].astype(str).str.startswith("ENSG")
    ].drop_duplicates(subset=["x_id", "y_id", "relation"])

    mapping = _read_gene_protein_edges(source_root)
    if expr.empty or mapping.empty:
        out = pd.DataFrame(columns=list(expr.columns) + ["gene_id"])
    else:
        out = expr.rename(columns={"y_id": "gene_id"}).merge(mapping, on="gene_id", how="inner")
        out = out.drop(columns=["y_type", "relation", "display_relation"], errors="ignore")
        out = out.rename(columns={"protein_id": "y_id"})
        out["y_type"] = NodeType.PROTEIN.value
        out["relation"] = dest_relation
        out["display_relation"] = "expresses protein"
        out["source"] = out["source"].astype(str).str.replace(
            ";projected_via_protein_node_xref", "", regex=False
        ) + ";projected_via_protein_node_xref"
        out["credibility"] = int(Credibility.ESTABLISHED_FACT)
        preferred = [
            "x_id",
            "x_type",
            "y_id",
            "y_type",
            "relation",
            "display_relation",
            "source",
            "credibility",
            "gene_id",
        ]
        out = out[[*preferred, *[c for c in out.columns if c not in preferred]]]
        out = out.drop_duplicates(subset=["x_id", "y_id", "relation", "source"]).reset_index(drop=True)

    output_rows = kg_storage.write_edges(dest_root, dest_relation, out, mode="overwrite")
    return ProjectionResult(
        source_relation=source_relation,
        dest_relation=dest_relation,
        input_rows=input_rows,
        mapped_gene_rows=mapped_gene_rows,
        unmapped_gene_rows=unmapped_gene_rows,
        estimated_output_rows=estimated_output_rows,
        output_rows=output_rows,
        distinct_pairs=output_rows,
    )


def build_cell_line_protein_expression_duckdb(
    *,
    source_kg_root: str | Path,
    dest_kg_root: str | Path,
    min_expression: float,
    duckdb_memory_limit: str = "4GB",
    threads: int = 2,
) -> ProjectionResult:
    """Build bounded cell-line→protein expression edges and evidence with DuckDB.

    This intentionally treats the protein edge as an mRNA-derived proxy, not
    direct proteomics. The source gene-expression relation is filtered by
    ``expression >= min_expression`` before projecting ENSG genes to ENSP
    proteins through ``nodes/protein.ensembl_gene_id``.
    """

    source_root = Path(source_kg_root)
    dest_root = Path(dest_kg_root)
    dest_edges = dest_root / "edges"
    dest_evidence = dest_root / "evidence"
    dest_edges.mkdir(parents=True, exist_ok=True)
    dest_evidence.mkdir(parents=True, exist_ok=True)

    source_edge = source_root / "edges" / "cell_line_expresses_gene.parquet"
    proteins = source_root / "nodes" / "protein.parquet"
    edge_out = dest_edges / "cell_line_expresses_protein.parquet"
    evidence_out = dest_evidence / "cell_line_expresses_protein.parquet"
    credibility = int(Credibility.ESTABLISHED_FACT)

    con = duckdb.connect()
    con.execute(f"PRAGMA memory_limit='{duckdb_memory_limit}'")
    con.execute(f"PRAGMA threads={threads}")
    con.execute(
        f"""
        CREATE TEMP TABLE expr AS
        SELECT DISTINCT
            x_id,
            x_type,
            y_id AS gene_id,
            TRY_CAST(expression AS DOUBLE) AS expression,
            TRY_CAST(gene_effect AS DOUBLE) AS gene_effect,
            TRY_CAST(is_essential AS BOOLEAN) AS is_essential,
            source
        FROM read_parquet('{source_edge}')
        WHERE x_type = 'cell_line'
          AND y_type = 'gene'
          AND starts_with(y_id, 'ENSG')
          AND TRY_CAST(expression AS DOUBLE) >= {float(min_expression)}
        """
    )
    input_rows = int(con.execute("SELECT count(*) FROM read_parquet(?)", [str(source_edge)]).fetchone()[0])
    con.execute(
        f"""
        CREATE TEMP TABLE protein_map AS
        SELECT DISTINCT
            ensembl_gene_id AS gene_id,
            id AS protein_id
        FROM read_parquet('{proteins}')
        WHERE starts_with(ensembl_gene_id, 'ENSG')
          AND starts_with(id, 'ENSP')
        """
    )
    mapped_gene_rows = int(
        con.execute("SELECT count(*) FROM expr SEMI JOIN protein_map USING (gene_id)").fetchone()[0]
    )
    unmapped_gene_rows = int(
        con.execute("SELECT count(*) FROM expr ANTI JOIN protein_map USING (gene_id)").fetchone()[0]
    )
    estimated_output_rows = int(
        con.execute("SELECT count(*) FROM expr JOIN protein_map USING (gene_id)").fetchone()[0]
    )
    con.execute(
        f"""
        CREATE TEMP TABLE out_edges AS
        SELECT DISTINCT
            expr.x_id,
            expr.x_type,
            protein_map.protein_id AS y_id,
            'protein' AS y_type,
            'cell_line_expresses_protein' AS relation,
            'expresses protein' AS display_relation,
            expr.source || ';projected_via_protein.ensembl_gene_id;min_expression>={float(min_expression)}' AS source,
            {credibility} AS credibility,
            expr.gene_id,
            expr.expression,
            expr.gene_effect,
            expr.is_essential,
            {float(min_expression)} AS min_expression,
            'high_mrna_expression_projected_to_protein' AS projection_method
        FROM expr
        JOIN protein_map USING (gene_id)
        """
    )
    con.execute(f"COPY out_edges TO '{edge_out}' (FORMAT PARQUET)")
    con.execute(
        f"""
        CREATE TEMP TABLE out_evidence AS
        SELECT
            'cell_line_expresses_protein|' || x_id || '|' || y_id AS edge_key,
            relation,
            x_id,
            x_type,
            y_id,
            y_type,
            'database_record' AS evidence_type,
            'OpenTargets' AS source,
            'DepMap' AS source_dataset,
            'OpenTargets/DepMap:cell_line_expresses_protein:' || x_id || ':' || gene_id || ':' || y_id || ':expression=' || CAST(expression AS VARCHAR) || ':min_expression={float(min_expression)}' AS source_record_id,
            '' AS paper_id,
            '' AS dataset_id,
            '' AS study_id,
            expression AS evidence_score,
            gene_effect AS effect_size,
            NULL::DOUBLE AS p_value,
            CASE WHEN is_essential THEN 'essential' ELSE '' END AS direction,
            '' AS confidence_interval,
            'high_mrna_expression_projected_to_protein' AS predicate,
            '' AS text_span,
            '' AS section,
            'DepMap expression threshold projected through protein.ensembl_gene_id' AS extraction_method,
            '' AS license,
            '' AS release,
            '' AS created_at
        FROM out_edges
        """
    )
    # Preserve kg_evidence schema column order/types.
    cols = ", ".join(name for name, _ in kg_evidence.EVIDENCE_PARQUET_COLUMNS)
    con.execute(f"COPY (SELECT {cols} FROM out_evidence) TO '{evidence_out}' (FORMAT PARQUET)")
    output_rows = int(con.execute("SELECT count(*) FROM out_edges").fetchone()[0])
    con.close()
    return ProjectionResult(
        source_relation="cell_line_expresses_gene",
        dest_relation="cell_line_expresses_protein",
        input_rows=input_rows,
        mapped_gene_rows=mapped_gene_rows,
        unmapped_gene_rows=unmapped_gene_rows,
        estimated_output_rows=estimated_output_rows,
        output_rows=output_rows,
        distinct_pairs=output_rows,
    )


def backfill_protein_expression_evidence_duckdb(
    *,
    kg_root: str | Path,
    relation: str,
    source_dataset: str,
    predicate: str,
    extraction_method: str,
    duckdb_memory_limit: str = "4GB",
    threads: int = 2,
) -> int:
    """Write evidence for an existing protein-expression edge file with DuckDB.

    This is evidence-only: it does not modify edge files. It is intended for
    already-promoted RNA→protein proxy relations where edge rows carry the
    original gene and expression columns.
    """

    root = Path(kg_root)
    edge_file = root / "edges" / f"{relation}.parquet"
    evidence_dir = root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / f"{relation}.parquet"
    if not edge_file.exists():
        raise FileNotFoundError(edge_file)

    con = duckdb.connect()
    con.execute(f"PRAGMA memory_limit='{duckdb_memory_limit}'")
    con.execute(f"PRAGMA threads={threads}")
    columns = {row[0] for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(edge_file)]).fetchall()}
    if "tpm" in columns and "expression" in columns:
        score_expr = "COALESCE(TRY_CAST(tpm AS DOUBLE), TRY_CAST(expression AS DOUBLE))"
    elif "tpm" in columns:
        score_expr = "TRY_CAST(tpm AS DOUBLE)"
    elif "expression" in columns:
        score_expr = "TRY_CAST(expression AS DOUBLE)"
    else:
        score_expr = "NULL::DOUBLE"
    effect_expr = "TRY_CAST(gene_effect AS DOUBLE)" if "gene_effect" in columns else "NULL::DOUBLE"
    gene_expr = "COALESCE(gene_id, '')" if "gene_id" in columns else "''"
    con.execute(
        f"""
        COPY (
            SELECT
                relation || '|' || x_id || '|' || y_id AS edge_key,
                relation,
                x_id,
                x_type,
                y_id,
                y_type,
                'database_record' AS evidence_type,
                'OpenTargets' AS source,
                '{source_dataset}' AS source_dataset,
                source || ':' || relation || ':' || x_id || ':' || {gene_expr} || ':' || y_id AS source_record_id,
                '' AS paper_id,
                '' AS dataset_id,
                '' AS study_id,
                {score_expr} AS evidence_score,
                {effect_expr} AS effect_size,
                NULL::DOUBLE AS p_value,
                '' AS direction,
                '' AS confidence_interval,
                '{predicate}' AS predicate,
                '' AS text_span,
                '' AS section,
                '{extraction_method}' AS extraction_method,
                '' AS license,
                '' AS release,
                '' AS created_at
            FROM read_parquet('{edge_file}')
        ) TO '{evidence_file}' (FORMAT PARQUET)
        """
    )
    count = int(con.execute("SELECT count(*) FROM read_parquet(?)", [str(evidence_file)]).fetchone()[0])
    con.close()
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-kg-root", required=True, help="Read-only KG root to project from")
    parser.add_argument("--dest-kg-root", required=True, help="Local/temp KG root to write derived edge into")
    parser.add_argument("--max-output-rows", type=int, default=10_000_000)
    parser.add_argument("--estimate-only", action="store_true")
    parser.add_argument(
        "--min-expression",
        type=float,
        default=None,
        help="For cell_line_expresses_protein, build a bounded DuckDB projection with expression >= threshold.",
    )
    parser.add_argument("--duckdb-memory-limit", default="4GB")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument(
        "--allow-cell-line-build",
        action="store_true",
        help="Opt-in escape hatch; by default cell_line_expresses_protein is estimate-only.",
    )
    parser.add_argument(
        "--evidence-only",
        action="store_true",
        help="Backfill evidence for an already-existing protein-expression edge file without rewriting edges.",
    )
    parser.add_argument(
        "--relation",
        choices=["cell_type_expresses_protein", "cell_line_expresses_protein"],
        default="cell_type_expresses_protein",
    )
    args = parser.parse_args(argv)

    if args.evidence_only:
        if args.relation == "cell_type_expresses_protein":
            count = backfill_protein_expression_evidence_duckdb(
                kg_root=args.source_kg_root,
                relation=args.relation,
                source_dataset="HPA/OpenTargets expression",
                predicate="rna_expression_projected_to_protein",
                extraction_method="HPA/OpenTargets RNA expression projected through protein node xref",
                duckdb_memory_limit=args.duckdb_memory_limit,
                threads=args.threads,
            )
        else:
            count = backfill_protein_expression_evidence_duckdb(
                kg_root=args.source_kg_root,
                relation=args.relation,
                source_dataset="DepMap",
                predicate="high_mrna_expression_projected_to_protein",
                extraction_method="DepMap expression threshold projected through protein.ensembl_gene_id",
                duckdb_memory_limit=args.duckdb_memory_limit,
                threads=args.threads,
            )
        print(f"{args.relation}	{count}")
        return 0

    if args.relation == "cell_type_expresses_protein":
        source_relation = "cell_type_expresses_gene"
        source_x_type = NodeType.CELL_TYPE.value
    else:
        source_relation = "cell_line_expresses_gene"
        source_x_type = NodeType.CELL_LINE.value

    if args.relation == "cell_line_expresses_protein" and not args.estimate_only and not args.allow_cell_line_build:
        parser.error(
            "cell_line_expresses_protein is potentially very large; run --estimate-only first "
            "or pass --allow-cell-line-build explicitly for a bounded local build"
        )
    if args.min_expression is not None:
        if args.relation != "cell_line_expresses_protein":
            parser.error("--min-expression is currently only supported for cell_line_expresses_protein")
        if args.estimate_only:
            parser.error("--min-expression build mode cannot be combined with --estimate-only")
        result = build_cell_line_protein_expression_duckdb(
            source_kg_root=args.source_kg_root,
            dest_kg_root=args.dest_kg_root,
            min_expression=args.min_expression,
            duckdb_memory_limit=args.duckdb_memory_limit,
            threads=args.threads,
        )
        print(result)
        return 0

    source_root = kg_storage.open_kg_root(args.source_kg_root)
    dest_root = kg_storage.open_kg_root(args.dest_kg_root)

    if args.estimate_only:
        counts = estimate_expression_to_protein_rows(
            source_root=source_root,
            source_relation=source_relation,
            source_x_type=source_x_type,
        )
        print(
            "\t".join(
                [
                    "source_relation",
                    "dest_relation",
                    "input_rows",
                    "mapped_gene_rows",
                    "unmapped_gene_rows",
                    "estimated_output_rows",
                ]
            )
        )
        print("\t".join(map(str, [source_relation, args.relation, *counts])))
        return 0

    result = project_expression_to_protein(
        source_root=source_root,
        dest_root=dest_root,
        source_relation=source_relation,
        dest_relation=args.relation,
        source_x_type=source_x_type,
        max_output_rows=args.max_output_rows,
    )
    print(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
