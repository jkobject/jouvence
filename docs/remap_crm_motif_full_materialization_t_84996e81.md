# ReMap CRM motif full-materialization attempt

Task: `t_84996e81`  
Status: `blocked-with-artifacts`; staged-only; support-only; no canonical writes.

## What this task resolved

This task located and pinned a reviewed genome-wide hg38 motif-hit input that can replace per-interval UCSC sequence API scanning for full-scale work:

- UCSC hg38 JASPAR2026 genome-wide motif-hit bigBed: `https://hgdownload.soe.ucsc.edu/gbdb/hg38/jaspar/JASPAR2026.bb`
  - HEAD status: 200
  - content length: `196,186,295,304` bytes
  - last modified: `Sun, 18 Jan 2026 18:21:24 GMT`
  - ETag: `"2dad9d4c08-648ada4577100"`
- UCSC hg38 twoBit reference registered for provenance/fallback sequence work: `https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.2bit`
  - HEAD status: 200
  - content length: `835,393,456` bytes
  - last modified: `Thu, 30 Apr 2015 23:16:38 GMT`
  - ETag: `"31cb17b0-514f9499d2180"`
- JASPAR mapping remains pinned to `JASPAR2026_CORE_vertebrates_non-redundant`, mapping parquet SHA256 `7c62396a25142745b40e7a8b6efe034cd6d54f07ad74d0f7f82066b9209cc257`.
- Full ReMap CRM BED remains pinned at `artifacts/staged/t_b599d3bb/full_local/source_cache/remap2022_crm_selected.bed`, 3,327,980 rows, SHA256 `22f6fac5c1be237a3f46f720d348734b3ee261e8b1c8856b2d262957cfc60619`.

## Materializer added

Script:

- `artifacts/staged/t_84996e81/build_remap_crm_motif_full_materialization.py`
- Script SHA256 after validation: `0038c36667e916351d8de355211d0427412895fbb12522d19f6cfe14657e091d`

The script streams UCSC `bigBedToBed -bed=<CRM shard>` output, filters motif hits to rows where the motif TF symbol is among the CRM interval's declared regulators, and writes support-only CRM/motif co-location shards:

- output pattern: `artifacts/staged/t_84996e81/features/remap_crm_motif_colocation_full/motif_crm_colocation_chr*.parquet`
- manifest: `artifacts/staged/t_84996e81/manifests/remap_crm_motif_full_materialization_manifest.json`
- report: `artifacts/staged/t_84996e81/reports/remap_crm_motif_full_materialization_report.json`
- query examples: `artifacts/staged/t_84996e81/reports/query_examples.sql`

## TF×CRM×enhancer link policy

Policy used by the script:

`crm_interval_motif_support_only`: motif hits are linked to ReMap CRM intervals when the JASPAR motif TF symbol is one of the CRM regulator symbols and coordinates overlap by >=1 bp. This task does not expand the known 24.45B TF × CRM × enhancer product and does not assert active TF-enhancer graph edges; enhancer linkage remains via the reviewed compact/support sidecar/reducer policy, not row-wise canonical edges.

This preserves the existing ReMap posture:

- relation under review: `tf_binds_enhancer`
- semantics: `support_only_motif_colocation;not_observed_binding;not_graph_edge`
- canonical writes: false
- no `edges/tf_binds_enhancer.parquet` write
- no `evidence/tf_binds_enhancer.parquet` write

## Actual run results

A truncated chrY materialization smoke was run to validate the input, parser, join, schema, and query path:

```bash
uv run python -m py_compile artifacts/staged/t_84996e81/build_remap_crm_motif_full_materialization.py
uv run python artifacts/staged/t_84996e81/build_remap_crm_motif_full_materialization.py --chroms Y --max-raw-hits-per-chrom 100000
```

Observed output:

- selected chrY CRM intervals: 2,571
- raw UCSC/JASPAR motif hits consumed before truncation: 100,001
- materialized support rows after CRM-regulator filtering: 2,015
- CRM intervals with motif support in truncated run: 33
- distinct motif IDs: 152
- distinct TF symbols: 143
- output shard: `artifacts/staged/t_84996e81/features/remap_crm_motif_colocation_full/motif_crm_colocation_chrY.parquet`
- output shard SHA256: `a647ce5b2f474357a964616bbf91d8bbbf8789057e99069580e89e73bdd6379a`

Independent DuckDB readback over the staged shard returned:

```text
n_rows=2015
crms=33
tfs=143
motifs=152
min_start=2781711
max_end=2850562
```

Top TF symbols by support rows in the truncated shard included `ZNF384`, `NR2C2`, `TBP`, `HOXA3`, `ARID3A`, `ISL2`, `LIN54`, `FOXA1`, `JUN`, and `GATA6`.

## Blocker to full acceptance

The full 3,327,980-CRM materialization was not completed in this worker run. A non-truncated chrY run exceeded the 600-second command cap before completion, and the reviewed UCSC JASPAR2026 bigBed is 196 GB with very dense motif calls. Even the first 100 chrY CRM intervals produced 290,815 raw motif-hit rows before filtering; 100 mid-chr1 CRM intervals produced 316,322 raw rows before filtering.

Therefore, the full all-chromosome run needs either:

1. external/long-running compute with checkpointed per-chromosome jobs and no 600-second tool cap;
2. a reviewed score/threshold reduction over the UCSC JASPAR track before overlap; or
3. a local optimized motif-scanning implementation over hg38.2bit with explicit threshold semantics and resource budget.

Until one of those is approved/run, this task remains `blocked-with-artifacts`, not production/full done.

## Validation flags from the generated report

```json
{
  "all_24_chromosomes_selected": false,
  "all_selected_chromosomes_have_output": true,
  "full_3327980_crm_intervals_selected": false,
  "materialized_rows_gt_zero": true,
  "no_canonical_writes": true,
  "not_truncated": false,
  "uses_reviewed_genomewide_motif_track": true
}
```
