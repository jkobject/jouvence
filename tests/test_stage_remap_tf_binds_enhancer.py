from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import gzip
import io
from types import SimpleNamespace

import duckdb
import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / ".omoc" / "scripts" / "stage_remap_tf_binds_enhancer.py"
spec = importlib.util.spec_from_file_location("stage_remap_tf_binds_enhancer", SCRIPT)
assert spec is not None and spec.loader is not None
stage_remap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_remap)

COMPACT_SCRIPT = Path(__file__).resolve().parents[1] / ".omoc" / "scripts" / "stage_remap_tf_binds_enhancer_compact.py"
compact_spec = importlib.util.spec_from_file_location("stage_remap_tf_binds_enhancer_compact", COMPACT_SCRIPT)
assert compact_spec is not None and compact_spec.loader is not None
stage_remap_compact = importlib.util.module_from_spec(compact_spec)
compact_spec.loader.exec_module(stage_remap_compact)

CRM_SCRIPT = Path(__file__).resolve().parents[1] / ".omoc" / "scripts" / "stage_remap_crm_tf_binds_enhancer_support.py"
crm_spec = importlib.util.spec_from_file_location("stage_remap_crm_tf_binds_enhancer_support", CRM_SCRIPT)
assert crm_spec is not None and crm_spec.loader is not None
stage_remap_crm = importlib.util.module_from_spec(crm_spec)
crm_spec.loader.exec_module(stage_remap_crm)


def _write_minimal_kg(root: Path) -> None:
    (root / "nodes").mkdir(parents=True)
    pd.DataFrame(
        [
            {"id": "ENSG000001", "gene_name": "CTCF"},
            {"id": "ENSG000002", "gene_name": "GATA1"},
        ]
    ).to_parquet(root / "nodes" / "gene.parquet", index=False)
    pd.DataFrame(
        [
            {"id": "enh1", "chromosome": "1", "start": 100, "end": 250, "name": "enh1", "source": "test/enhancer"},
            {"id": "enh2", "chromosome": "1", "start": 500, "end": 650, "name": "enh2", "source": "test/enhancer"},
        ]
    ).to_parquet(root / "nodes" / "enhancer.parquet", index=False)


def test_crm_support_pilot_keeps_support_only_semantics_and_exact_counts(tmp_path: Path, monkeypatch) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    crm_bed_fixture = tmp_path / "crm_fixture.bed"
    crm_bed_fixture.write_text(
        "chr1\t120\t220\tCTCF,GATA1\t5\t.\t150\t151\t0,0,0\n"
        "chr1\t520\t620\tCTCF,UNKNOWN\t3\t.\t540\t541\t0,0,0\n"
    )

    def fake_stream(dest: Path, url: str, chromosomes: set[str], max_source_rows, stop_after_selected_chromosomes=True):
        dest.write_bytes(crm_bed_fixture.read_bytes())
        return {
            "url": url,
            "cache_path": str(dest),
            "source_rows_seen": 2,
            "rows_written": 2,
            "sha256_uncompressed_written": "fixture",
            "sample_lines": crm_bed_fixture.read_text().splitlines(),
            "chromosome_filter": ["1"],
            "chromosome_counts_written": {"1": 2},
            "max_source_rows": max_source_rows,
            "stopped_after_selected_chromosomes": True,
        }

    monkeypatch.setattr(stage_remap_crm, "stream_crm_to_bed", fake_stream)
    report = stage_remap_crm.write_tables_and_report(
        SimpleNamespace(
            kg_root=str(kg),
            stage_root=str(tmp_path / "stage"),
            force=False,
            chromosomes="1",
            max_source_rows=0,
            crm_url="fixture://crm",
            min_overlap_bp=1,
            min_fraction_overlap=0.0,
            detailed_row_limit=1,
            top_n=10,
            all_peak_stage_root="",
            task_id="test_crm",
            no_sorted_chrom_stop=False,
        )
    )

    assert report["canonical_writes"] is False
    assert report["evidence_type"] == "crm_aggregated_support"
    assert report["counts"]["candidate_support_rows"] == 3
    assert report["counts"]["distinct_candidate_tfs"] == 2
    assert report["counts"]["distinct_candidate_enhancers"] == 2
    assert report["validations"]["tf_gene_endpoint_antijoin"] == 0
    assert report["validations"]["enhancer_endpoint_antijoin"] == 0
    assert report["validations"]["observed_binding_rows"] == 0
    assert report["validations"]["tf_regulates_gene_rows"] == 0
    assert report["validations"]["detailed_rows_materialized"] == 1
    assert report["counts"]["support_edge_summary_policy"].startswith("not_materialized")


def test_remap_observed_binding_creates_staged_edge_with_evidence(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    remap = pd.DataFrame(
        [
            {
                "remap_row_number": 1,
                "chromosome": "1",
                "start": 120,
                "end": 220,
                "remap_peak_name": "ENCSR000AAA.CTCF.K562",
                "peak_score": 42.0,
                "strand": ".",
                "summit_start": 150,
                "summit_end": 151,
                "item_rgb": "0,0,0",
                "remap_source_accession": "ENCSR000AAA",
                "remap_tf_symbol": "CTCF",
                "remap_biotype": "K562",
            }
        ]
    )

    overlaps, stats = stage_remap.intersect_remap_with_enhancers(remap, kg)
    observed = stage_remap.observed_evidence_from_overlaps(overlaps, "fixture.bed")
    edges = stage_remap.edge_rows_from_evidence(observed)

    assert stats["active_overlap_rows"] == 1
    assert len(edges) == 1
    assert edges.loc[0, "relation"] == "tf_binds_enhancer"
    assert edges.loc[0, "x_id"] == "ENSG000001"
    assert edges.loc[0, "y_id"] == "enh1"
    assert set(observed["evidence_type"]) == {"observed_binding"}
    assert observed.loc[0, "predicate"] == "binds_enhancer"


def test_motif_only_is_predicted_support_and_does_not_create_active_edge(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    motifs = pd.DataFrame(
        [
            {
                "chromosome": "1",
                "start": 130,
                "end": 140,
                "motif_tf_symbol": "CTCF",
                "motif_id": "MA0139.1",
                "motif_source": "JASPAR",
                "motif_score": 12.3,
            }
        ]
    )

    motif_ev, stats = stage_remap.motif_evidence(motifs, pd.DataFrame(columns=stage_remap.EVIDENCE_COLUMNS), kg)
    edges = stage_remap.edge_rows_from_evidence(motif_ev)

    assert stats["motif_only_candidate_rows"] == 1
    assert set(motif_ev["evidence_type"]) == {"motif_predicted"}
    assert set(motif_ev["predicate"]) == {"motif_matches_enhancer"}
    assert bool(motif_ev.loc[0, "motif_only_candidate"]) is True
    assert edges.empty


def test_motif_support_is_not_observed_and_no_tf_regulates_gene_outputs(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    observed = pd.DataFrame(
        [
            {
                "edge_key": "tf_binds_enhancer|ENSG000001|enh1",
                "x_id": "ENSG000001",
                "x_type": "gene",
                "y_id": "enh1",
                "y_type": "enhancer",
                "relation": "tf_binds_enhancer",
                "source_record_id": "ReMap2022:1:ENCSR000AAA.CTCF.K562:enh1",
                "chromosome": "1",
                "start": 120,
                "end": 220,
                "evidence_type": "observed_binding",
            }
        ]
    )
    motifs = pd.DataFrame(
        [
            {
                "chromosome": "1",
                "start": 150,
                "end": 160,
                "motif_tf_symbol": "CTCF",
                "motif_id": "MA0139.1",
                "motif_source": "JASPAR",
                "motif_score": 12.3,
            }
        ]
    )

    motif_ev, stats = stage_remap.motif_evidence(motifs, observed, kg)
    evidence = pd.concat([observed.reindex(columns=stage_remap.EVIDENCE_COLUMNS), motif_ev], ignore_index=True)
    edges = stage_remap.edge_rows_from_evidence(evidence)
    stage_root = tmp_path / "stage"
    (stage_root / "edges").mkdir(parents=True)
    (stage_root / "evidence").mkdir(parents=True)
    edges.to_parquet(stage_root / "edges" / "tf_binds_enhancer.parquet", index=False)
    evidence.to_parquet(stage_root / "evidence" / "tf_binds_enhancer.parquet", index=False)
    validations = stage_remap.validate_outputs(stage_root, edges, evidence, kg)

    assert stats["motif_support_rows"] == 1
    assert set(motif_ev["evidence_type"]) == {"motif_support"}
    assert set(motif_ev["predicate"]) == {"motif_supports_observed_binding"}
    assert len(edges) == 1
    assert validations["no_tf_regulates_gene_files"] is True
    assert validations["active_edges_without_observed_binding"] == 0
    assert validations["ok"] is True


def test_streaming_remap_reader_batches_and_filters_before_materializing(tmp_path: Path) -> None:
    bed = tmp_path / "remap.bed"
    bed.write_text(
        "chr1\t10\t20\tSRC1.CTCF.K562\t1\t.\t15\t16\t0,0,0\n"
        "chr2\t20\t30\tSRC2.GATA1.K562\t2\t.\t25\t26\t0,0,0\n"
        "chr2\t30\t40\tSRC3.CTCF.K562\t3\t.\t35\t36\t0,0,0\n"
        "chr3\t40\t50\tSRC4.CTCF.K562\t4\t.\t45\t46\t0,0,0\n"
    )

    batches = list(stage_remap.read_remap_bed_batches(bed, max_rows=3, batch_size=1, chromosomes={"2"}))

    assert len(batches) == 2
    assert [int(batch.iloc[0]["remap_row_number"]) for batch in batches] == [2, 3]
    assert [batch.iloc[0]["chromosome"] for batch in batches] == ["2", "2"]
    assert [batch.iloc[0]["remap_tf_symbol"] for batch in batches] == ["GATA1", "CTCF"]


def test_windowed_intersection_keeps_boundary_spanning_peak_and_reports_bounded_scans(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    (kg / "nodes").mkdir(parents=True)
    pd.DataFrame([{"id": "ENSG000001", "gene_name": "CTCF"}]).to_parquet(kg / "nodes" / "gene.parquet", index=False)
    pd.DataFrame(
        [
            {"id": "enh_boundary", "chromosome": "1", "start": 95, "end": 110, "name": "enh_boundary", "source": "test/enhancer"},
            {"id": "enh_far", "chromosome": "1", "start": 10_005, "end": 10_030, "name": "enh_far", "source": "test/enhancer"},
            {"id": "enh_between", "chromosome": "1", "start": 5_000, "end": 5_100, "name": "enh_between", "source": "test/enhancer"},
        ]
    ).to_parquet(kg / "nodes" / "enhancer.parquet", index=False)
    remap = pd.DataFrame(
        [
            {
                "remap_row_number": 1,
                "chromosome": "1",
                "start": 98,
                "end": 104,
                "remap_peak_name": "ENCSR000AAA.CTCF.K562",
                "peak_score": 42.0,
                "strand": ".",
                "summit_start": 100,
                "summit_end": 101,
                "item_rgb": "0,0,0",
                "remap_source_accession": "ENCSR000AAA",
                "remap_tf_symbol": "CTCF",
                "remap_biotype": "K562",
            },
            {
                "remap_row_number": 2,
                "chromosome": "1",
                "start": 10_000,
                "end": 10_020,
                "remap_peak_name": "ENCSR000AAB.CTCF.K562",
                "peak_score": 43.0,
                "strand": ".",
                "summit_start": 10_010,
                "summit_end": 10_011,
                "item_rgb": "0,0,0",
                "remap_source_accession": "ENCSR000AAB",
                "remap_tf_symbol": "CTCF",
                "remap_biotype": "K562",
            },
        ]
    )

    overlaps, stats = stage_remap.intersect_remap_with_enhancers(remap, kg, window_bp=100)

    assert set(overlaps["enhancer_id"]) == {"enh_boundary", "enh_far"}
    assert stats["window_count"] == 2
    assert stats["max_enhancer_rows_per_window"] == 1
    assert stats["active_overlap_rows"] == 2


def test_duplicate_remap_rows_do_not_duplicate_edges_or_observed_evidence(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    row = {
        "remap_row_number": 1,
        "chromosome": "1",
        "start": 120,
        "end": 220,
        "remap_peak_name": "ENCSR000AAA.CTCF.K562",
        "peak_score": 42.0,
        "strand": ".",
        "summit_start": 150,
        "summit_end": 151,
        "item_rgb": "0,0,0",
        "remap_source_accession": "ENCSR000AAA",
        "remap_tf_symbol": "CTCF",
        "remap_biotype": "K562",
    }
    remap = pd.DataFrame([row, row.copy()])

    overlaps, _ = stage_remap.intersect_remap_with_enhancers(remap, kg, window_bp=100)
    observed = stage_remap.observed_evidence_from_overlaps(overlaps, "fixture.bed")
    edges = stage_remap.edge_rows_from_evidence(observed)

    assert len(observed) == 1
    assert observed["source_record_id"].is_unique
    assert len(edges) == 1
    assert edges.loc[0, "supporting_observed_evidence_count"] == 1


def test_compact_remap_stream_cache_is_gzip_and_readable(tmp_path: Path, monkeypatch) -> None:
    raw = (
        b"chr1\t10\t20\tSRC1.CTCF.K562\t1\t.\t15\t16\t0,0,0\n"
        b"chr2\t20\t30\tSRC2.GATA1.K562\t2\t.\t25\t26\t0,0,0\n"
    )
    compressed = gzip.compress(raw)

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()

    monkeypatch.setattr(stage_remap_compact.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse(compressed))
    dest = tmp_path / "remap_chr1.bed.gz"

    manifest = stage_remap_compact._stream_remap_to_gzip(dest, "https://example.invalid/remap.bed.gz", chromosomes={"1"})
    batches = list(stage_remap.read_remap_bed_batches(dest, batch_size=10, chromosomes={"1"}))

    assert manifest["rows_written"] == 1
    assert manifest["source_rows_seen"] == 2
    assert manifest["gzip_cache_path"] == str(dest)
    assert gzip.open(dest, "rt").read().startswith("chr1\t10\t20")
    assert len(batches) == 1
    assert batches[0].loc[0, "chromosome"] == "1"
    assert batches[0].loc[0, "remap_tf_symbol"] == "CTCF"


def test_compact_feature_first_prototype_aggregates_without_raw_evidence_chunks(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    bed = tmp_path / "remap.bed"
    bed.write_text(
        "chr1\t120\t220\tENCSR000AAA.CTCF.K562\t42\t.\t150\t151\t0,0,0\n"
        "chr1\t125\t225\tENCSR000AAB.CTCF.K562\t43\t.\t155\t156\t0,0,0\n"
    )
    stage_root = tmp_path / "compact-stage"

    report = stage_remap_compact.run(
        stage_remap_compact.parse_args(
            [
                "--kg-root",
                str(kg),
                "--stage-root",
                str(stage_root),
                "--remap-bed",
                str(bed),
                "--max-remap-rows",
                "0",
                "--remap-batch-size",
                "10",
                "--window-bp",
                "100",
                "--chromosomes",
                "1",
                "--max-stage-gib",
                "1",
                "--force",
            ]
        )
    )

    edges = pd.read_parquet(stage_root / "edges" / "tf_binds_enhancer.parquet")
    evidence = pd.read_parquet(stage_root / "evidence" / "tf_binds_enhancer.parquet")

    assert report["prototype_mode"] == "compact_feature_first"
    assert report["counts"]["raw_observed_evidence_rows_materialized"] == 0
    assert report["counts"]["observed_binding_count_sum"] == 2
    assert report["counts"]["edge_rows"] == 1
    assert report["counts"]["evidence_rows"] == 1
    assert not (stage_root / "_chunks" / "evidence").exists()
    assert not (stage_root / "_compact_chunks" / "support").exists()
    assert (stage_root / "_compact_chunks" / "support.duckdb").exists()
    assert report["counts"]["support_accumulation_backend"] == "duckdb_aggregate_table"
    assert report["counts"]["compact_support_chunk_files"] == 0
    assert len(edges) == 1
    assert int(edges.loc[0, "supporting_observed_evidence_count"]) == 2
    assert len(evidence) == 1
    assert evidence.loc[0, "source_record_id"].startswith("ReMap2022:compact:")
    assert report["validations"]["duplicate_active_edges"] == 0
    assert report["validations"]["duplicate_source_record_edge_keys"] == 0
    assert report["validations"]["tf_regulates_gene_edges"] == 0


def test_compact_support_streams_into_duckdb_aggregate_without_window_shards(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    (kg / "nodes").mkdir(parents=True)
    pd.DataFrame([{"id": "ENSG000001", "gene_name": "CTCF"}]).to_parquet(kg / "nodes" / "gene.parquet", index=False)
    pd.DataFrame(
        [
            {"id": "enh1", "chromosome": "1", "start": 100, "end": 250, "name": "enh1", "source": "test/enhancer"},
            {"id": "enh2", "chromosome": "1", "start": 10_100, "end": 10_250, "name": "enh2", "source": "test/enhancer"},
        ]
    ).to_parquet(kg / "nodes" / "enhancer.parquet", index=False)
    bed = tmp_path / "remap.bed"
    bed.write_text(
        "chr1\t120\t220\tENCSR000AAA.CTCF.K562\t42\t.\t150\t151\t0,0,0\n"
        "chr1\t10120\t10220\tENCSR000AAB.CTCF.K562\t43\t.\t10150\t10151\t0,0,0\n"
    )
    stage_root = tmp_path / "compact-stage"

    report = stage_remap_compact.run(
        stage_remap_compact.parse_args(
            [
                "--kg-root",
                str(kg),
                "--stage-root",
                str(stage_root),
                "--remap-bed",
                str(bed),
                "--max-remap-rows",
                "0",
                "--remap-batch-size",
                "1",
                "--window-bp",
                "10000",
                "--chromosomes",
                "1",
                "--max-stage-gib",
                "1",
                "--force",
            ]
        )
    )

    support_dir = stage_root / "_compact_chunks" / "support"
    support_files = list(support_dir.glob("*.parquet")) if support_dir.exists() else []
    edges = pd.read_parquet(stage_root / "edges" / "tf_binds_enhancer.parquet")
    evidence = pd.read_parquet(stage_root / "evidence" / "tf_binds_enhancer.parquet")

    assert support_files == []
    assert (stage_root / "_compact_chunks" / "support.duckdb").exists()
    assert report["counts"]["support_accumulation_backend"] == "duckdb_aggregate_table"
    assert report["counts"]["compact_support_chunk_files"] == 0
    assert report["counts"]["support_merge_batches"] == 2
    assert report["counts"]["support_rows"] == 2
    assert report["counts"]["edge_rows"] == 2
    assert report["counts"]["evidence_rows"] == 2
    assert set(edges["y_id"]) == {"enh1", "enh2"}
    assert set(evidence["source_record_id"].str.startswith("ReMap2022:compact:")) == {True}


def test_compact_support_aggregate_schema_avoids_primary_key_index(tmp_path: Path) -> None:
    db_path = tmp_path / "support.duckdb"
    con = duckdb.connect(db_path.as_posix())
    try:
        stage_remap_compact._write_empty_support_agg(con)
        columns = con.execute("pragma table_info('support_agg')").fetchall()
    finally:
        con.close()

    edge_key_rows = [row for row in columns if row[1] == "edge_key"]
    assert len(edge_key_rows) == 1
    # DuckDB stores the PRIMARY KEY flag in the last pragma table_info column.
    # Full chr1 showed the ART index for a long string primary key can exceed
    # the bounded stage guard before finalization; MERGE does not need it.
    assert edge_key_rows[0][-1] is False


def test_compact_edge_hash_bucket_is_stable_and_colocates_same_edge() -> None:
    edge_key = "tf_binds_enhancer|ENSG000001|enh1"

    bucket_a = stage_remap_compact._edge_hash_bucket(edge_key, 17)
    bucket_b = stage_remap_compact._edge_hash_bucket(str(edge_key), 17)

    assert bucket_a == bucket_b
    assert 0 <= bucket_a < 17
    assert stage_remap_compact._edge_hash_bucket(edge_key, 1) == 0


def test_compact_bucketed_runs_colocate_support_and_do_not_duplicate_edges_across_buckets(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    bed = tmp_path / "remap.bed"
    # Two rows for the same TF/enhancer edge land in different input batches but
    # must co-locate in exactly one deterministic edge-hash bucket.
    bed.write_text(
        "chr1\t120\t220\tENCSR000AAA.CTCF.K562\t42\t.\t150\t151\t0,0,0\n"
        "chr1\t125\t225\tENCSR000AAB.CTCF.K562\t43\t.\t155\t156\t0,0,0\n"
    )
    bucket_count = 5
    edge_key = "tf_binds_enhancer|ENSG000001|enh1"
    owner_bucket = stage_remap_compact._edge_hash_bucket(edge_key, bucket_count)
    edge_parts = []
    reports = []

    for bucket_index in range(bucket_count):
        stage_root = tmp_path / f"bucket-{bucket_index}"
        report = stage_remap_compact.run(
            stage_remap_compact.parse_args(
                [
                    "--kg-root",
                    str(kg),
                    "--stage-root",
                    str(stage_root),
                    "--remap-bed",
                    str(bed),
                    "--max-remap-rows",
                    "0",
                    "--remap-batch-size",
                    "1",
                    "--window-bp",
                    "100",
                    "--chromosomes",
                    "1",
                    "--support-bucket-count",
                    str(bucket_count),
                    "--support-bucket-index",
                    str(bucket_index),
                    "--max-stage-gib",
                    "1",
                    "--force",
                ]
            )
        )
        reports.append(report)
        edge_parts.append(pd.read_parquet(stage_root / "edges" / "tf_binds_enhancer.parquet"))

    combined = pd.concat(edge_parts, ignore_index=True)

    assert len(combined) == 1
    assert combined.loc[0, "x_id"] == "ENSG000001"
    assert combined.loc[0, "y_id"] == "enh1"
    assert int(combined.loc[0, "supporting_observed_evidence_count"]) == 2
    assert [r["counts"]["edge_rows"] for r in reports].count(1) == 1
    assert reports[owner_bucket]["counts"]["edge_rows"] == 1
    assert reports[owner_bucket]["counts"]["observed_binding_count_sum"] == 2
    assert sum(r["counts"]["observed_binding_count_sum"] for r in reports) == 2


def test_compact_one_pass_partitions_all_buckets_without_rescanning_source(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    bed = tmp_path / "remap.bed"
    bed.write_text(
        "chr1\t120\t220\tENCSR000AAA.CTCF.K562\t42\t.\t150\t151\t0,0,0\n"
        "chr1\t125\t225\tENCSR000AAB.CTCF.K562\t43\t.\t155\t156\t0,0,0\n"
        "chr1\t520\t620\tENCSR000BBB.GATA1.K562\t41\t.\t550\t551\t0,0,0\n"
    )
    stage_root = tmp_path / "one-pass"
    bucket_count = 7

    report = stage_remap_compact.run(
        stage_remap_compact.parse_args(
            [
                "--kg-root",
                str(kg),
                "--stage-root",
                str(stage_root),
                "--remap-bed",
                str(bed),
                "--max-remap-rows",
                "0",
                "--remap-batch-size",
                "1",
                "--window-bp",
                "1000",
                "--chromosomes",
                "1",
                "--support-bucket-count",
                str(bucket_count),
                "--one-pass-bucket-partitions",
                "--max-stage-gib",
                "1",
                "--force",
            ]
        )
    )

    bucket_edge_paths = sorted((stage_root / "buckets").glob("bucket=*/edges/tf_binds_enhancer.parquet"))
    edge_parts = [pd.read_parquet(path) for path in bucket_edge_paths]
    combined = pd.concat(edge_parts, ignore_index=True)
    delta_files = sorted((stage_root / "_compact_chunks" / "support_delta_partitions").glob("bucket=*/*.parquet"))
    partition_manifest = json.loads((stage_root / "support_delta_partition_manifest.json").read_text())
    delta_rows = pd.concat([pd.read_parquet(path) for path in delta_files], ignore_index=True)
    completed_buckets = [b for b in report["bucket_finalizations"] if b["status"] == "finalized"]

    assert report["counts"]["support_accumulation_backend"] == "one_pass_partitioned_support_deltas"
    assert report["counts"]["remap_rows"] == 3
    assert report["counts"]["source_scan_passes"] == 1
    assert report["counts"]["support_delta_partition_files"] == len(delta_files)
    assert report["counts"]["support_rows"] == 2
    assert report["counts"]["edge_rows"] == 2
    assert len(combined) == 2
    assert combined[["x_id", "y_id", "relation"]].duplicated().sum() == 0
    assert set(combined["supporting_observed_evidence_count"]) == {1, 2}
    assert all(row["support_bucket_count"] == bucket_count for row in partition_manifest)
    assert all(row["support_bucket_index"] == stage_remap_compact._edge_hash_bucket(row["edge_key"], bucket_count) for _, row in delta_rows.iterrows())
    assert len(completed_buckets) == bucket_count
    assert all(b["validations"]["tf_regulates_gene_edges"] == 0 for b in completed_buckets)


def test_compact_bucket_manifest_counts_are_scoped_to_uploaded_bucket(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    bed = tmp_path / "remap.bed"
    bed.write_text(
        "chr1\t120\t220\tENCSR000AAA.CTCF.K562\t42\t.\t150\t151\t0,0,0\n"
        "chr1\t520\t620\tENCSR000BBB.GATA1.K562\t41\t.\t550\t551\t0,0,0\n"
    )
    bucket_count = 7
    owner_bucket = stage_remap_compact._edge_hash_bucket("tf_binds_enhancer|ENSG000001|enh1", bucket_count)
    stage_root = tmp_path / "owner-bucket"

    report = stage_remap_compact.run(
        stage_remap_compact.parse_args(
            [
                "--kg-root",
                str(kg),
                "--stage-root",
                str(stage_root),
                "--remap-bed",
                str(bed),
                "--max-remap-rows",
                "0",
                "--remap-batch-size",
                "10",
                "--window-bp",
                "1000",
                "--chromosomes",
                "1",
                "--support-bucket-count",
                str(bucket_count),
                "--support-bucket-index",
                str(owner_bucket),
                "--max-stage-gib",
                "1",
                "--force",
            ]
        )
    )
    manifest = json.loads((stage_root / "chunk_manifest.json").read_text())

    assert report["counts"]["support_bucket_count"] == bucket_count
    assert report["counts"]["support_bucket_index"] == owner_bucket
    assert report["counts"]["support_rows"] == 1
    assert report["counts"]["observed_binding_count_sum"] == 1
    assert sum(row["observed_binding_count_sum"] for row in manifest) == 1
    assert all(row["support_bucket_index"] == owner_bucket for row in manifest)


def test_compact_one_pass_remote_first_uploads_verifies_prunes_and_finalizes_from_remote(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    bed = tmp_path / "remap.bed"
    bed.write_text(
        "chr1\t120\t220\tENCSR000AAA.CTCF.K562\t42\t.\t150\t151\t0,0,0\n"
        "chr1\t125\t225\tENCSR000AAB.CTCF.K562\t43\t.\t155\t156\t0,0,0\n"
        "chr1\t520\t620\tENCSR000BBB.GATA1.K562\t41\t.\t550\t551\t0,0,0\n"
    )
    stage_root = tmp_path / "remote-first-stage"
    remote_prefix = tmp_path / "remote-prefix"
    bucket_count = 7

    report = stage_remap_compact.run(
        stage_remap_compact.parse_args(
            [
                "--kg-root",
                str(kg),
                "--stage-root",
                str(stage_root),
                "--remap-bed",
                str(bed),
                "--max-remap-rows",
                "0",
                "--remap-batch-size",
                "1",
                "--window-bp",
                "1000",
                "--chromosomes",
                "1",
                "--support-bucket-count",
                str(bucket_count),
                "--one-pass-bucket-partitions",
                "--remote-stage-prefix",
                str(remote_prefix),
                "--max-stage-gib",
                "1",
                "--force",
            ]
        )
    )

    manifest = json.loads((stage_root / "support_delta_partition_manifest.json").read_text())
    local_delta_files = sorted((stage_root / "_compact_chunks" / "support_delta_partitions").glob("bucket=*/*.parquet"))
    remote_delta_files = sorted((remote_prefix / "support_delta_partitions").glob("bucket=*/*.parquet"))
    remote_sha_files = sorted((remote_prefix / "support_delta_partitions").glob("bucket=*/*.parquet.sha256"))
    bucket_edge_paths = sorted((remote_prefix / "buckets").glob("bucket=*/edges/tf_binds_enhancer.parquet"))
    combined = pd.concat([pd.read_parquet(path) for path in bucket_edge_paths], ignore_index=True)
    local_bucket_edge_paths = sorted((stage_root / "buckets").glob("bucket=*/edges/tf_binds_enhancer.parquet"))
    completed_buckets = [b for b in report["bucket_finalizations"] if b["status"] == "finalized"]

    assert report["counts"]["remote_first_partitions"] is True
    assert report["inputs"]["duckdb_temp_dir"] == str(stage_root / "_compact_chunks" / "duckdb_temp")
    assert report["counts"]["remote_verified_partition_files"] == len(manifest)
    assert report["counts"]["local_pruned_partition_files"] == len(manifest)
    assert local_delta_files == []
    assert len(remote_delta_files) == len(manifest)
    assert len(remote_sha_files) == len(manifest)
    assert local_bucket_edge_paths == []
    assert report["counts"]["local_pruned_final_output_files"] == bucket_count * 2
    assert all(row["partition_status"] == "uploaded_verified_pruned" for row in manifest)
    assert all(row["local_pruned"] is True for row in manifest)
    assert report["counts"]["source_scan_passes"] == 1
    assert report["counts"]["edge_rows"] == 2
    assert report["counts"]["evidence_rows"] == 2
    assert len(combined) == 2
    assert combined[["x_id", "y_id", "relation"]].duplicated().sum() == 0
    assert len(completed_buckets) == bucket_count
    assert (remote_prefix / "validation_report.json").exists()
    assert any((remote_prefix / "buckets").glob("bucket=*/edges/tf_binds_enhancer.parquet"))


def test_compact_one_pass_resume_verified_remote_partitions_skips_source_scan(tmp_path: Path) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    bed = tmp_path / "remap.bed"
    bed.write_text(
        "chr1\t120\t220\tENCSR000AAA.CTCF.K562\t42\t.\t150\t151\t0,0,0\n"
        "chr1\t125\t225\tENCSR000AAB.CTCF.K562\t43\t.\t155\t156\t0,0,0\n"
        "chr1\t520\t620\tENCSR000BBB.GATA1.K562\t41\t.\t550\t551\t0,0,0\n"
    )
    initial_stage = tmp_path / "initial-stage"
    resume_stage = tmp_path / "resume-stage"
    remote_prefix = tmp_path / "remote-prefix"
    bucket_count = 7

    initial_report = stage_remap_compact.run(
        stage_remap_compact.parse_args(
            [
                "--kg-root",
                str(kg),
                "--stage-root",
                str(initial_stage),
                "--remap-bed",
                str(bed),
                "--max-remap-rows",
                "0",
                "--remap-batch-size",
                "1",
                "--window-bp",
                "1000",
                "--chromosomes",
                "1",
                "--support-bucket-count",
                str(bucket_count),
                "--one-pass-bucket-partitions",
                "--remote-stage-prefix",
                str(remote_prefix),
                "--max-stage-gib",
                "1",
                "--force",
            ]
        )
    )

    bed.unlink()
    report = stage_remap_compact.run(
        stage_remap_compact.parse_args(
            [
                "--kg-root",
                str(kg),
                "--stage-root",
                str(resume_stage),
                "--support-bucket-count",
                str(bucket_count),
                "--one-pass-bucket-partitions",
                "--remote-stage-prefix",
                str(remote_prefix),
                "--resume-verified-remote-partitions",
                "--max-stage-gib",
                "1",
                "--force",
            ]
        )
    )

    manifest = json.loads((resume_stage / "support_delta_partition_manifest.json").read_text())
    combined = pd.concat(
        [pd.read_parquet(path) for path in sorted((remote_prefix / "buckets").glob("bucket=*/edges/tf_binds_enhancer.parquet"))],
        ignore_index=True,
    )

    assert report["counts"]["remote_resume_partitions"] is True
    assert report["counts"]["source_scan_passes"] == 0
    assert report["counts"]["remap_rows"] == 0
    assert report["counts"]["remote_verified_partition_files"] == initial_report["counts"]["remote_verified_partition_files"]
    assert len(manifest) == initial_report["counts"]["remote_verified_partition_files"]
    assert all(row["remote_resume_discovered"] is True for row in manifest)
    assert report["counts"]["edge_rows"] == initial_report["counts"]["edge_rows"] == 2
    assert report["counts"]["evidence_rows"] == initial_report["counts"]["evidence_rows"] == 2
    assert len(combined) == 2
    assert combined[["x_id", "y_id", "relation"]].duplicated().sum() == 0


def test_compact_one_pass_remote_first_excludes_unverified_interrupted_partitions(tmp_path: Path, monkeypatch) -> None:
    kg = tmp_path / "kg"
    _write_minimal_kg(kg)
    bed = tmp_path / "remap.bed"
    bed.write_text("chr1\t120\t220\tENCSR000AAA.CTCF.K562\t42\t.\t150\t151\t0,0,0\n")
    stage_root = tmp_path / "interrupted-stage"
    remote_prefix = tmp_path / "remote-prefix"

    def fake_upload(local_path: Path, remote_uri: str, *, prune_local: bool) -> dict[str, object]:
        # Simulate an interrupted upload that never reached the required
        # uploaded_verified_pruned manifest state. Finalization must not consume
        # the local leftover, because a retry/resume could otherwise double-count
        # or finalize data whose remote parity was never proven.
        return {
            "remote_uri": remote_uri,
            "bytes": int(Path(local_path).stat().st_size),
            "sha256": stage_remap_compact._sha256_file(Path(local_path)),
            "upload_status": "upload_interrupted",
            "local_pruned": False,
        }

    monkeypatch.setattr(stage_remap_compact, "_upload_verified_pruned", fake_upload)

    report = stage_remap_compact.run(
        stage_remap_compact.parse_args(
            [
                "--kg-root",
                str(kg),
                "--stage-root",
                str(stage_root),
                "--remap-bed",
                str(bed),
                "--max-remap-rows",
                "0",
                "--remap-batch-size",
                "1",
                "--window-bp",
                "1000",
                "--chromosomes",
                "1",
                "--support-bucket-count",
                "3",
                "--one-pass-bucket-partitions",
                "--remote-stage-prefix",
                str(remote_prefix),
                "--max-stage-gib",
                "1",
                "--force",
            ]
        )
    )

    manifest = json.loads((stage_root / "support_delta_partition_manifest.json").read_text())
    owner_bucket = stage_remap_compact._edge_hash_bucket("tf_binds_enhancer|ENSG000001|enh1", 3)
    owner_report = report["bucket_finalizations"][owner_bucket]
    owner_edges = pd.read_parquet(stage_root / "buckets" / f"bucket={owner_bucket:04d}" / "edges" / "tf_binds_enhancer.parquet")

    assert len(manifest) == 1
    assert manifest[0]["partition_status"] == "upload_interrupted"
    assert owner_report["excluded_partition_files"] == 1
    assert owner_report["validations"]["empty_bucket"] is True
    assert owner_edges.empty
    assert report["counts"]["edge_rows"] == 0
