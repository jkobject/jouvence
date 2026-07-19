from __future__ import annotations

import argparse
import gzip
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from manage_db.stage_human_ensg_gene_migration import (
    build,
    transform_relation,
    validate_candidate,
)


def _write_gzip(path: Path, text: str) -> None:
    with gzip.open(path, "wt") as handle:
        handle.write(text)


def _mapping_connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE mapping (
          ncbi_node_id VARCHAR,
          canonical_ensembl_gene_id VARCHAR,
          mapping_status VARCHAR
        )
        """
    )
    con.execute(
        "INSERT INTO mapping VALUES ('NCBI:7157', 'ENSG00000141510', 'accepted_1to1')"
    )
    return con


def _edge(x_id: str, *, source: str = "legacy", credibility: int = 1) -> dict[str, object]:
    return {
        "x_id": x_id,
        "x_type": "gene" if x_id.startswith(("NCBI:", "ENSG")) else "disease",
        "y_id": "MONDO:1",
        "y_type": "disease",
        "relation": "disease_associated_gene",
        "source": source,
        "credibility": credibility,
    }


def test_unaffected_duplicate_edge_relation_is_copied_byte_for_byte(tmp_path: Path) -> None:
    source = tmp_path / "unaffected.parquet"
    target = tmp_path / "candidate" / "unaffected.parquet"
    quarantine = tmp_path / "quarantine" / "unaffected.parquet"
    duplicate = _edge("MONDO:2")
    duplicate["x_type"] = "disease"
    pd.DataFrame([duplicate, duplicate]).to_parquet(source, index=False)
    con = _mapping_connection()

    report = transform_relation(con, source, target, quarantine, evidence=False)

    assert target.read_bytes() == source.read_bytes()
    assert len(pd.read_parquet(target)) == 2
    assert report["affected_rows"] == 0
    assert report["source_preexisting_duplicate_rows"] == 1
    assert report["remap_collision_rows"] == 0
    assert report["lineage_conservation_ok"] is True


def test_affected_edge_relation_rejects_preexisting_duplicate_identity(tmp_path: Path) -> None:
    source = tmp_path / "affected.parquet"
    duplicate = _edge("NCBI:7157")
    pd.DataFrame([duplicate, duplicate]).to_parquet(source, index=False)
    con = _mapping_connection()

    with pytest.raises(RuntimeError, match="pre-existing duplicate edge identities"):
        transform_relation(
            con,
            source,
            tmp_path / "candidate.parquet",
            tmp_path / "quarantine.parquet",
            evidence=False,
        )


def test_genuine_remap_collision_is_deduplicated_deterministically(tmp_path: Path) -> None:
    source = tmp_path / "affected.parquet"
    target = tmp_path / "candidate.parquet"
    pd.DataFrame(
        [
            _edge("NCBI:7157", source="legacy", credibility=1),
            _edge("ENSG00000141510", source="modern", credibility=2),
        ]
    ).to_parquet(source, index=False)
    con = _mapping_connection()

    report = transform_relation(
        con,
        source,
        target,
        tmp_path / "quarantine.parquet",
        evidence=False,
    )

    result = pd.read_parquet(target)
    assert len(result) == 1
    assert result.loc[0, "source"] == "modern"
    assert report["source_preexisting_duplicate_rows"] == 0
    assert report["remap_collision_rows"] == 1
    assert report["lineage_conservation_ok"] is True


def test_remap_collision_uses_source_endpoint_as_final_tiebreaker(tmp_path: Path) -> None:
    source = tmp_path / "affected.parquet"
    target = tmp_path / "candidate.parquet"
    ncbi = _edge("NCBI:7157", source="same", credibility=1)
    ncbi["marker"] = "ncbi"
    ensg = _edge("ENSG00000141510", source="same", credibility=1)
    ensg["marker"] = "ensg"
    pd.DataFrame([ncbi, ensg]).to_parquet(source, index=False)

    transform_relation(
        _mapping_connection(),
        source,
        target,
        tmp_path / "quarantine.parquet",
        evidence=False,
    )

    assert pd.read_parquet(target).loc[0, "marker"] == "ensg"


def test_affected_evidence_preserves_source_row_multiplicity(tmp_path: Path) -> None:
    source = tmp_path / "evidence.parquet"
    target = tmp_path / "candidate.parquet"
    base = {
        "y_id": "MONDO:1",
        "y_type": "disease",
        "relation": "disease_associated_gene",
        "source": "same-source",
        "source_record_id": "same-record",
    }
    pd.DataFrame(
        [
            {
                **base,
                "edge_key": "disease_associated_gene|NCBI:7157|MONDO:1",
                "x_id": "NCBI:7157",
                "x_type": "gene",
            },
            {
                **base,
                "edge_key": "disease_associated_gene|ENSG00000141510|MONDO:1",
                "x_id": "ENSG00000141510",
                "x_type": "gene",
            },
        ]
    ).to_parquet(source, index=False)
    con = _mapping_connection()

    report = transform_relation(
        con,
        source,
        target,
        tmp_path / "quarantine.parquet",
        evidence=True,
    )

    result = pd.read_parquet(target)
    assert len(result) == 2
    assert set(result["canonicalization_source_x_id"]) == {
        "NCBI:7157",
        "ENSG00000141510",
    }
    assert report["remap_collision_rows"] == 0
    assert report["lineage_conservation_ok"] is True


def test_builds_human_only_candidate_and_quarantines_unmapped_rows(tmp_path: Path) -> None:
    source = tmp_path / "source"
    for directory in ("nodes", "edges", "evidence"):
        (source / directory).mkdir(parents=True)
    pd.DataFrame(
        [
            {"id": "ENSG00000141510", "ncbi_gene_id": None, "gene_name": "TP53", "source": "OpenTargets"},
            {"id": "NCBI:7157", "ncbi_gene_id": "7157", "gene_name": "TP53", "source": "NCBI"},
            {"id": "NCBI:999", "ncbi_gene_id": "999", "gene_name": "OLD", "source": "NCBI"},
            {"id": "ENSMUSG00000059552", "ncbi_gene_id": None, "gene_name": "Trp53", "source": "OpenTargets/target.homologues"},
        ]
    ).to_parquet(source / "nodes" / "gene.parquet", index=False)
    pd.DataFrame([{"id": "MONDO:1"}]).to_parquet(source / "nodes" / "disease.parquet", index=False)
    pd.DataFrame(
        [
            {"x_id": "NCBI:7157", "x_type": "gene", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_gene", "source": "legacy", "credibility": 1},
            {"x_id": "ENSG00000141510", "x_type": "gene", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_gene", "source": "modern", "credibility": 2},
            {"x_id": "NCBI:999", "x_type": "gene", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_gene", "source": "legacy", "credibility": 1},
        ]
    ).to_parquet(source / "edges" / "disease_associated_gene.parquet", index=False)
    pd.DataFrame(
        [
            {"edge_key": "gene_ortholog_gene|ENSG00000141510|ENSMUSG00000059552", "x_id": "ENSG00000141510", "x_type": "gene", "y_id": "ENSMUSG00000059552", "y_type": "gene", "relation": "gene_ortholog_gene"}
        ]
    ).to_parquet(source / "edges" / "gene_ortholog_gene.parquet", index=False)
    pd.DataFrame(
        [
            {"edge_key": "disease_associated_gene|NCBI:7157|MONDO:1", "x_id": "NCBI:7157", "x_type": "gene", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_gene", "source": "NCBI", "source_dataset": "legacy", "source_record_id": "1"},
            {"edge_key": "disease_associated_gene|NCBI:999|MONDO:1", "x_id": "NCBI:999", "x_type": "gene", "y_id": "MONDO:1", "y_type": "disease", "relation": "disease_associated_gene", "source": "NCBI", "source_dataset": "legacy", "source_record_id": "2"},
        ]
    ).to_parquet(source / "evidence" / "disease_associated_gene.parquet", index=False)

    gene2ensembl = tmp_path / "gene2ensembl.gz"
    history = tmp_path / "gene_history.gz"
    _write_gzip(gene2ensembl, "9606\t7157\tENSG00000141510\t-\t-\t-\t-\n")
    _write_gzip(history, "9606\t-\t999\tOLD\t20200101\n")
    output = tmp_path / "candidate"
    manifest = build(
        argparse.Namespace(
            source_root=source,
            output_root=output,
            gene2ensembl=gene2ensembl,
            gene_history=history,
        )
    )

    genes = pd.read_parquet(output / "nodes" / "gene.parquet")
    edges = pd.read_parquet(output / "edges" / "disease_associated_gene.parquet")
    evidence = pd.read_parquet(output / "evidence" / "disease_associated_gene.parquet")
    quarantined = pd.read_parquet(output / "quarantine" / "edges" / "disease_associated_gene.parquet")

    assert genes["id"].tolist() == ["ENSG00000141510"]
    assert genes.loc[0, "ncbi_gene_id"] == "7157"
    assert len(edges) == 1
    assert edges.loc[0, "x_id"] == "ENSG00000141510"
    assert edges.loc[0, "source"] == "modern"
    assert evidence.loc[0, "edge_key"] == "disease_associated_gene|ENSG00000141510|MONDO:1"
    assert evidence.loc[0, "canonicalization_source_x_id"] == "NCBI:7157"
    assert quarantined.loc[0, "x_id"] == "NCBI:999"
    assert not (output / "edges" / "gene_ortholog_gene.parquet").exists()
    assert manifest["validation"]["ok"] is True
    assert manifest["mapping"]["status_counts"] == {"accepted_1to1": 1, "retired_unmapped": 1}

    manifest["relations"]["edges"]["disease_associated_gene"]["remap_collision_rows"] += 1
    revalidation = validate_candidate(duckdb.connect(), output, manifest["relations"])
    assert "edges/disease_associated_gene.parquet: row_conservation_failed" in revalidation[
        "failures"
    ]
