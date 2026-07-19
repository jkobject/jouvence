"""Build a fail-closed, human-ENSG-only staged KG candidate.

This command never writes to the canonical KG.  It consumes a local, immutable
snapshot of ``nodes/``, ``edges/`` and ``evidence/`` plus pinned NCBI mapping
files, and creates a complete candidate root and audit manifests.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pyarrow.parquet as pq

TASK_ID = "t_8b9cdabc"
NCBI_GENE2ENSEMBL_URL = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2ensembl.gz"
NCBI_GENE_HISTORY_URL = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/gene_history.gz"
HUMAN_TAXON_ID = "9606"
ENSG_RE = re.compile(r"^ENSG\d+$")
NONHUMAN_ENSEMBL_GENE_RE = re.compile(r"^ENS[A-Z]+G\d+$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def clean(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def load_authoritative_mapping(
    ncbi_ids: set[str], gene2ensembl: Path, gene_history: Path
) -> pd.DataFrame:
    active: dict[str, set[str]] = defaultdict(set)
    with gzip.open(gene2ensembl, "rt", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) < 3 or row[0] != HUMAN_TAXON_ID or row[2] in {"", "-"}:
                continue
            ensembl_id = row[2].split(".", 1)[0]
            if ENSG_RE.fullmatch(ensembl_id):
                active[row[1]].add(ensembl_id)

    history: dict[str, str | None] = {}
    with gzip.open(gene_history, "rt", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) >= 3 and row[0] == HUMAN_TAXON_ID:
                history[row[2]] = None if row[1] == "-" else row[1]

    rows: list[dict[str, Any]] = []
    for ncbi_id in sorted(ncbi_ids, key=lambda value: int(value)):
        direct = sorted(active.get(ncbi_id, set()))
        replacement = history.get(ncbi_id)
        replacement_targets = sorted(active.get(replacement or "", set()))
        targets = direct or replacement_targets
        if len(targets) == 1:
            status = "accepted_1to1" if direct else "retired_replaced_1to1"
        elif len(targets) > 1:
            status = (
                "ambiguous_one_to_many"
                if direct
                else "retired_replaced_ambiguous"
            )
        elif ncbi_id in history:
            status = (
                "retired_unmapped"
                if replacement is None
                else "retired_replacement_unmapped"
            )
        else:
            status = "unmapped"
        rows.append(
            {
                "ncbi_gene_id": ncbi_id,
                "ncbi_node_id": f"NCBI:{ncbi_id}",
                "mapping_status": status,
                "canonical_ensembl_gene_id": targets[0] if len(targets) == 1 else None,
                "candidate_ensembl_gene_ids": "|".join(targets) or None,
                "replacement_ncbi_gene_id": replacement,
                "mapping_authority": "NCBI gene2ensembl + gene_history",
            }
        )
    return pd.DataFrame(rows)


def merge_gene_nodes(gene_path: Path, mapping: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    genes = pd.read_parquet(gene_path)
    ids = genes["id"].astype(str)
    classes = {
        "human_ensg": ids.str.fullmatch(r"ENSG\d+"),
        "human_ncbi": ids.str.fullmatch(r"NCBI:\d+"),
        "nonhuman_ensembl": ids.str.fullmatch(r"ENS[A-Z]+G\d+"),
    }
    if int(sum(mask.sum() for mask in classes.values())) != len(genes):
        unknown = sorted(ids[~pd.concat(classes, axis=1).any(axis=1)].unique())[:20]
        raise RuntimeError(f"unclassified canonical gene IDs: {unknown}")

    human = genes.loc[classes["human_ensg"]].copy()
    accepted = mapping[mapping["canonical_ensembl_gene_id"].notna()].copy()
    missing_targets = sorted(set(accepted["canonical_ensembl_gene_id"]) - set(human["id"]))
    if missing_targets:
        raise RuntimeError(f"authoritative mappings target absent human genes: {missing_targets[:20]}")

    aliases = (
        accepted.groupby("canonical_ensembl_gene_id")["ncbi_gene_id"]
        .agg(lambda values: "|".join(sorted(set(map(str, values)), key=int)))
        .to_dict()
    )
    existing = human.get("ncbi_gene_id", pd.Series(pd.NA, index=human.index))
    human["ncbi_gene_id"] = [
        "|".join(
            sorted(
                {
                    token
                    for value in (clean(old), aliases.get(str(gene_id)))
                    if value
                    for token in value.split("|")
                },
                key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value),
            )
        )
        or None
        for gene_id, old in zip(human["id"], existing, strict=True)
    ]
    human = human.sort_values("id", kind="stable").reset_index(drop=True)
    return human, {
        "before_rows": len(genes),
        "before_human_ensg": int(classes["human_ensg"].sum()),
        "removed_ncbi_nodes": int(classes["human_ncbi"].sum()),
        "removed_nonhuman_ensembl_nodes": int(classes["nonhuman_ensembl"].sum()),
        "after_rows": len(human),
        "after_non_ensg_ids": int((~human["id"].astype(str).str.fullmatch(r"ENSG\d+")).sum()),
        "human_ensg_rows_with_ncbi_alias": int(human["ncbi_gene_id"].notna().sum()),
    }


def parquet_columns(path: Path) -> list[str]:
    return pq.read_schema(path).names


def quote(path: Path) -> str:
    return str(path).replace("'", "''")


def endpoint_expressions(columns: list[str]) -> tuple[str, str, str, str]:
    if not {"x_id", "x_type", "y_id", "y_type"} <= set(columns):
        raise RuntimeError(f"missing endpoint columns: {columns}")
    x_map = "mx.canonical_ensembl_gene_id"
    y_map = "my.canonical_ensembl_gene_id"
    x_join = "LEFT JOIN mapping mx ON i.x_type='gene' AND i.x_id=mx.ncbi_node_id"
    y_join = "LEFT JOIN mapping my ON i.y_type='gene' AND i.y_id=my.ncbi_node_id"
    return x_map, y_map, x_join, y_join


def relation_stats(con: duckdb.DuckDBPyConnection, path: Path) -> dict[str, int]:
    source = quote(path)
    row = con.execute(
        f"""
        SELECT count(*) AS row_count,
          count(*) FILTER (WHERE x_type='gene' AND x_id LIKE 'NCBI:%') ncbi_x_rows,
          count(*) FILTER (WHERE y_type='gene' AND y_id LIKE 'NCBI:%') ncbi_y_rows,
          count(*) FILTER (WHERE x_type='gene' AND regexp_matches(x_id, '^ENS[A-Z]+G[0-9]+$')) nonhuman_x_rows,
          count(*) FILTER (WHERE y_type='gene' AND regexp_matches(y_id, '^ENS[A-Z]+G[0-9]+$')) nonhuman_y_rows
        FROM read_parquet('{source}')
        """
    ).fetchone()
    assert row is not None
    keys = ["rows", "ncbi_x_rows", "ncbi_y_rows", "nonhuman_x_rows", "nonhuman_y_rows"]
    return dict(zip(keys, map(int, row), strict=True))


def transform_relation(
    con: duckdb.DuckDBPyConnection,
    source: Path,
    target: Path,
    quarantine: Path,
    *,
    evidence: bool,
) -> dict[str, Any]:
    columns = parquet_columns(source)
    stats = relation_stats(con, source)
    if stats["nonhuman_x_rows"] or stats["nonhuman_y_rows"]:
        raise RuntimeError(f"non-human gene endpoint outside orthology lane: {source}: {stats}")
    affected = stats["ncbi_x_rows"] + stats["ncbi_y_rows"]
    target.parent.mkdir(parents=True, exist_ok=True)
    quarantine.parent.mkdir(parents=True, exist_ok=True)
    src = quote(source)
    source_preexisting_duplicate_rows = 0
    if not evidence:
        source_preexisting_duplicate_rows = int(
            con.execute(
                f"""
                SELECT coalesce(sum(n - 1), 0) FROM (
                  SELECT count(*) AS n FROM read_parquet('{src}')
                  GROUP BY relation, x_id, y_id HAVING n > 1
                )
                """
            ).fetchone()[0]
        )
    if not affected:
        shutil.copy2(source, target)
        copied_byte_for_byte = sha256(source) == sha256(target)
        return {
            **stats,
            "affected_rows": 0,
            "after_rows": stats["rows"],
            "quarantine_rows": 0,
            "source_preexisting_duplicate_rows": source_preexisting_duplicate_rows,
            "remap_collision_rows": 0,
            "deduplicated_rows": 0,
            "copied_byte_for_byte": copied_byte_for_byte,
            "source_sha256": sha256(source),
            "candidate_sha256": sha256(target),
            "lineage_conservation_ok": copied_byte_for_byte,
        }

    if source_preexisting_duplicate_rows:
        raise RuntimeError(
            f"pre-existing duplicate edge identities in affected relation {source}: "
            f"{source_preexisting_duplicate_rows} excess rows"
        )

    dst = quote(target)
    qpath = quote(quarantine)
    x_map, y_map, x_join, y_join = endpoint_expressions(columns)
    unresolved = """
      (i.x_type='gene' AND i.x_id LIKE 'NCBI:%' AND mx.canonical_ensembl_gene_id IS NULL)
      OR (i.y_type='gene' AND i.y_id LIKE 'NCBI:%' AND my.canonical_ensembl_gene_id IS NULL)
    """
    con.execute(
        f"""
        COPY (
          SELECT i.*,
            CASE
              WHEN i.x_type='gene' AND i.x_id LIKE 'NCBI:%' AND mx.mapping_status LIKE 'ambiguous%' THEN 'ambiguous_x'
              WHEN i.y_type='gene' AND i.y_id LIKE 'NCBI:%' AND my.mapping_status LIKE 'ambiguous%' THEN 'ambiguous_y'
              WHEN i.x_type='gene' AND i.x_id LIKE 'NCBI:%' THEN coalesce(mx.mapping_status, 'unmapped_x')
              ELSE coalesce(my.mapping_status, 'unmapped_y')
            END AS quarantine_reason
          FROM read_parquet('{src}') i {x_join} {y_join}
          WHERE {unresolved}
        ) TO '{qpath}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    original_cols = ", ".join(f'i."{name}"' for name in columns if name not in {"x_id", "y_id", "edge_key"})
    source_endpoint_cols = (
        ", i.x_id AS canonicalization_source_x_id, i.y_id AS canonicalization_source_y_id"
        if evidence
        else ", i.x_id AS _canonicalization_source_x_id, i.y_id AS _canonicalization_source_y_id"
    )
    edge_key_expression = ""
    if "edge_key" in columns:
        edge_key_expression = (
            "i.relation || '|' || coalesce("
            + x_map
            + ", i.x_id) || '|' || coalesce("
            + y_map
            + ", i.y_id) AS edge_key,"
        )
    transformed = f"""
      SELECT
        {edge_key_expression}
        coalesce({x_map}, i.x_id) AS x_id,
        coalesce({y_map}, i.y_id) AS y_id,
        {original_cols}
        {source_endpoint_cols}
      FROM read_parquet('{src}') i {x_join} {y_join}
      WHERE NOT ({unresolved})
    """
    if evidence:
        # Evidence rows are source assertions, not graph identities. Preserve
        # every resolved row and retain its exact pre-remap endpoint lineage.
        con.execute(f"COPY ({transformed}) TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    else:
        order_cols = [name for name in ["credibility", "source", "display_relation"] if name in columns]
        order = ", ".join(
            [
                *(f'"{name}" DESC NULLS LAST' for name in order_cols),
                '"_canonicalization_source_x_id" ASC',
                '"_canonicalization_source_y_id" ASC',
            ]
        )
        con.execute(
            f"""
            COPY (
              SELECT * EXCLUDE (
                _dedup_rank,
                _canonicalization_source_x_id,
                _canonicalization_source_y_id
              ) FROM (
                SELECT *, row_number() OVER (
                  PARTITION BY relation, x_id, y_id ORDER BY {order}
                ) AS _dedup_rank
                FROM ({transformed})
              ) WHERE _dedup_rank=1
            ) TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )
    after = int(con.execute(f"SELECT count(*) FROM read_parquet('{dst}')").fetchone()[0])
    quarantined = int(con.execute(f"SELECT count(*) FROM read_parquet('{qpath}')").fetchone()[0])
    remap_collision_rows = stats["rows"] - quarantined - after
    lineage_conservation_ok = (
        stats["rows"] == after + quarantined + remap_collision_rows
        and remap_collision_rows >= 0
    )
    return {
        **stats,
        "affected_rows": affected,
        "after_rows": after,
        "quarantine_rows": quarantined,
        "source_preexisting_duplicate_rows": source_preexisting_duplicate_rows,
        "remap_collision_rows": remap_collision_rows,
        "deduplicated_rows": remap_collision_rows,
        "copied_byte_for_byte": False,
        "lineage_conservation_ok": lineage_conservation_ok,
    }


def validate_candidate(
    con: duckdb.DuckDBPyConnection, output: Path, relation_reports: dict[str, Any]
) -> dict[str, Any]:
    gene_path = output / "nodes" / "gene.parquet"
    gene_noncanonical = int(
        con.execute(
            f"SELECT count(*) FROM read_parquet('{quote(gene_path)}') WHERE NOT regexp_matches(id, '^ENSG[0-9]+$')"
        ).fetchone()[0]
    )
    failures: list[str] = []
    if gene_noncanonical:
        failures.append(f"gene_noncanonical={gene_noncanonical}")
    if (output / "edges" / "gene_ortholog_gene.parquet").exists():
        failures.append("orthology edge exists")
    if (output / "evidence" / "gene_ortholog_gene.parquet").exists():
        failures.append("orthology evidence exists")

    for surface in ("edges", "evidence"):
        for path in sorted((output / surface).glob("*.parquet")):
            stats = relation_stats(con, path)
            report = relation_reports[surface][path.stem]
            row_conservation_ok = report.get("rows") == (
                report.get("after_rows", -1)
                + report.get("quarantine_rows", -1)
                + report.get("remap_collision_rows", -1)
            )
            if not row_conservation_ok:
                failures.append(f"{surface}/{path.name}: row_conservation_failed")
            if stats["rows"] != report.get("after_rows"):
                failures.append(f"{surface}/{path.name}: reported_after_rows_mismatch")
            if report.get("deduplicated_rows") != report.get("remap_collision_rows"):
                failures.append(f"{surface}/{path.name}: collision_count_mismatch")
            if not report.get("lineage_conservation_ok", False):
                failures.append(f"{surface}/{path.name}: lineage_conservation_failed")
            if report.get("affected_rows") == 0:
                byte_preserved = (
                    report.get("copied_byte_for_byte", False)
                    and report.get("source_sha256") == report.get("candidate_sha256")
                    and report.get("after_rows") == report.get("rows")
                    and report.get("quarantine_rows") == 0
                    and report.get("remap_collision_rows") == 0
                )
                if not byte_preserved:
                    failures.append(f"{surface}/{path.name}: unaffected_relation_not_byte_preserved")
            elif report.get("source_preexisting_duplicate_rows", 0):
                failures.append(f"{surface}/{path.name}: preexisting_duplicates_in_affected_relation")
            if surface == "evidence" and report.get("remap_collision_rows"):
                failures.append(f"{surface}/{path.name}: evidence_rows_not_preserved")
            bad = sum(stats[key] for key in ("ncbi_x_rows", "ncbi_y_rows", "nonhuman_x_rows", "nonhuman_y_rows"))
            if bad:
                failures.append(f"{surface}/{path.name}: noncanonical_gene_endpoints={bad}")
            if surface == "edges":
                duplicate_edges = int(
                    con.execute(
                        f"""
                        SELECT count(*) FROM (
                          SELECT relation, x_id, y_id, count(*) AS n
                          FROM read_parquet('{quote(path)}')
                          GROUP BY ALL HAVING n > 1
                        )
                        """
                    ).fetchone()[0]
                )
                endpoint_antijoins: dict[str, int] = {}
                for side in ("x", "y"):
                    node_types = [
                        str(row[0])
                        for row in con.execute(
                            f"SELECT DISTINCT {side}_type FROM read_parquet('{quote(path)}')"
                        ).fetchall()
                    ]
                    for node_type in node_types:
                        node_path = output / "nodes" / f"{node_type}.parquet"
                        key = f"{side}:{node_type}"
                        if not node_path.exists():
                            endpoint_antijoins[key] = -1
                            failures.append(f"edges/{path.name}: missing nodes/{node_type}.parquet")
                            continue
                        missing = int(
                            con.execute(
                                f"""
                                SELECT count(*) FROM (
                                  SELECT DISTINCT {side}_id AS id
                                  FROM read_parquet('{quote(path)}')
                                  WHERE {side}_type = ?
                                  EXCEPT
                                  SELECT id FROM read_parquet('{quote(node_path)}')
                                )
                                """,
                                [node_type],
                            ).fetchone()[0]
                        )
                        endpoint_antijoins[key] = missing
                        if missing:
                            failures.append(
                                f"edges/{path.name}: endpoint_antijoin[{key}]={missing}"
                            )
                relation_reports["edges"][path.stem]["duplicate_edge_identities"] = duplicate_edges
                relation_reports["edges"][path.stem]["endpoint_antijoins"] = endpoint_antijoins
                if duplicate_edges and report.get("affected_rows", 0):
                    failures.append(f"edges/{path.name}: duplicate_identities={duplicate_edges}")
    for relation in sorted(set(p.stem for p in (output / "evidence").glob("*.parquet"))):
        edge = output / "edges" / f"{relation}.parquet"
        evidence = output / "evidence" / f"{relation}.parquet"
        if not edge.exists():
            failures.append(f"evidence without edge file: {relation}")
            continue
        missing = int(
            con.execute(
                f"""
                SELECT count(*) FROM (
                  SELECT DISTINCT edge_key FROM read_parquet('{quote(evidence)}')
                  EXCEPT
                  SELECT relation || '|' || x_id || '|' || y_id FROM read_parquet('{quote(edge)}')
                )
                """
            ).fetchone()[0]
        )
        relation_reports["evidence"][relation]["evidence_keys_without_edge"] = missing
        if missing:
            failures.append(f"evidence/{relation}: keys_without_edge={missing}")
    return {"ok": not failures, "failures": failures, "gene_noncanonical_ids": gene_noncanonical}


def inventory(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(root.rglob("*.parquet")):
        rows.append(
            {
                "path": str(path.relative_to(root)),
                "size_bytes": path.stat().st_size,
                "rows": pq.ParquetFile(path).metadata.num_rows,
                "sha256": sha256(path),
            }
        )
    return rows


def build(args: argparse.Namespace) -> dict[str, Any]:
    source = args.source_root.resolve()
    output = args.output_root.resolve()
    forbidden = Path("/Users/jkobject/mnt/gcs")
    if str(source).startswith(str(forbidden)) or str(output).startswith(str(forbidden)):
        raise RuntimeError("heavy migration through macOS GCS-FUSE is forbidden")
    if str(output).startswith("gs://") or output == source:
        raise RuntimeError("output must be a distinct local staged root")
    if output.exists():
        raise RuntimeError(f"immutable output already exists: {output}")
    if not (source / "nodes" / "gene.parquet").exists():
        raise RuntimeError("source root lacks nodes/gene.parquet")
    output.mkdir(parents=True)
    (output / "metadata").mkdir()
    (output / "quarantine" / "edges").mkdir(parents=True)
    (output / "quarantine" / "evidence").mkdir(parents=True)

    genes = pd.read_parquet(source / "nodes" / "gene.parquet", columns=["id"])
    ncbi_ids = {
        value[5:]
        for value in genes["id"].astype(str)
        if value.startswith("NCBI:") and value[5:].isdigit()
    }
    mapping = load_authoritative_mapping(ncbi_ids, args.gene2ensembl, args.gene_history)
    if len(mapping) != len(ncbi_ids):
        raise RuntimeError("crosswalk does not account for every canonical NCBI node")
    mapping_path = output / "metadata" / "ncbi_gene_to_human_ensg.parquet"
    mapping.to_parquet(mapping_path, index=False)

    human_genes, gene_report = merge_gene_nodes(source / "nodes" / "gene.parquet", mapping)
    (output / "nodes").mkdir()
    human_genes.to_parquet(output / "nodes" / "gene.parquet", index=False)
    for path in sorted((source / "nodes").glob("*.parquet")):
        if path.name != "gene.parquet":
            shutil.copy2(path, output / "nodes" / path.name)

    con = duckdb.connect(str(output / "metadata" / "migration.duckdb"))
    con.execute("CREATE TABLE mapping AS SELECT * FROM read_parquet(?)", [str(mapping_path)])
    reports: dict[str, dict[str, Any]] = {"edges": {}, "evidence": {}}
    for surface in ("edges", "evidence"):
        (output / surface).mkdir()
        for path in sorted((source / surface).glob("*.parquet")):
            relation = path.stem
            if relation == "gene_ortholog_gene":
                reports[surface][relation] = {
                    **relation_stats(con, path),
                    "after_rows": 0,
                    "removed_by_policy": True,
                }
                continue
            reports[surface][relation] = transform_relation(
                con,
                path,
                output / surface / path.name,
                output / "quarantine" / surface / path.name,
                evidence=surface == "evidence",
            )
    validation = validate_candidate(con, output, reports)
    con.close()

    mapping_counts = dict(Counter(mapping["mapping_status"]))
    source_inventory = inventory(source)
    candidate_inventory = inventory(output)
    manifest = {
        "task_id": TASK_ID,
        "status": "staged-only",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source),
        "candidate_root": str(output),
        "canonical_write_performed": False,
        "lamindb_write_performed": False,
        "policy": {
            "canonical_gene_identity": "human Ensembl ENSG only",
            "ncbi_ids": "aliases/xrefs only",
            "cross_species_orthology": "excluded from human KG candidate",
            "unresolved_rows": "excluded from candidate and preserved under quarantine/",
        },
        "authoritative_sources": {
            "gene2ensembl": {
                "url": NCBI_GENE2ENSEMBL_URL,
                "path": str(args.gene2ensembl),
                "sha256": sha256(args.gene2ensembl),
                "size_bytes": args.gene2ensembl.stat().st_size,
            },
            "gene_history": {
                "url": NCBI_GENE_HISTORY_URL,
                "path": str(args.gene_history),
                "sha256": sha256(args.gene_history),
                "size_bytes": args.gene_history.stat().st_size,
            },
        },
        "mapping": {"rows": len(mapping), "status_counts": mapping_counts},
        "gene_nodes": gene_report,
        "relations": reports,
        "validation": validation,
        "source_inventory": source_inventory,
        "candidate_inventory": candidate_inventory,
        "rollback": {
            "method": "discard staged candidate; canonical source objects were read-only",
            "canonical_source_unchanged": True,
        },
        "promotion": {
            "authorized": False,
            "requires_independent_review": True,
            "remove_relations": ["gene_ortholog_gene"],
            "replace_surfaces": ["nodes/gene.parquet", "edges/", "evidence/"],
        },
    }
    atomic_json(output / "metadata" / "promotion_rollback_manifest.json", manifest)
    if not validation["ok"]:
        raise RuntimeError(f"candidate validation failed: {validation['failures']}")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--gene2ensembl", type=Path, required=True)
    parser.add_argument("--gene-history", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    print(json.dumps(build(args)["validation"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
