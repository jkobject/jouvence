# ReMap CRM full support sidecar canonical promotion

Task: `t_f2a2952e`  
Source staged candidate: `t_5968ce32`  
Promotion-readiness gate: `t_7e356c5c`  
Readiness reviewer: `t_0d77b4f0`  
Status: `canonical promoted full support sidecar` / `review-required`.

## Verdict

The reviewed full/unbounded ReMap CRM support-only feature sidecar was canonically promoted to a new sharded feature prefix:

- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr*.parquet`
- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/tf_global_summary.parquet`
- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/manifest.json`
- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/metadata.json`

This is support-only feature/QA material. It is not graph topology, not `edges/tf_binds_enhancer.parquet`, not `evidence/tf_binds_enhancer.parquet`, not inferred edges, and not observed binding.

The existing bounded sidecar was left untouched:

- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support.parquet`
- bounded generation before/after: `1782308308670478` / `1782308308670478`
- bounded bytes before/after: `175361142` / `175361142`

## Canonical objects and counts

- Chromosome summary Parquets: `24`
- Summary rows: `48,768,788`
- Enhancer summary rows: `48,741,900`
- Per-chromosome TF summary rows: `26,888`
- Global TF summary rows: `1,179`
- Data payload bytes: `5,144,121,535`
- Canonical object count under prefix after promotion: `27` (`25` data Parquets + `manifest.json` + `metadata.json`)

The full per-object path, row count, source SHA256, canonical readback SHA256, size, GCS generation, CRC32C, and MD5 are recorded in:

- local manifest: `artifacts/reports/t_f2a2952e_remap_crm_full_support_sidecar_canonical_manifest.json`
- local validation: `artifacts/reports/t_f2a2952e_remap_crm_full_support_sidecar_postwrite_validation.json`
- canonical manifest: `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/manifest.json` generation `1782327802646296` bytes `57066`
- canonical metadata: `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/metadata.json` generation `1782327803373250` bytes `1206`

Example object proofs:

| object | rows | bytes | generation | sha256 |
|---|---:|---:|---|---|
| `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr1.parquet` | 5,069,453 | 534,732,181 | `1782327502251035` | `bbbd395f1f83d95a3f0863141ce5d0ddc793db137edf0348451e830fa0aef9b9` |
| `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/tf_global_summary.parquet` | 1,179 | 48,858 | `1782327701359421` | `c00baa6839ef86f71b48eca73ef271944384d988efdf186e70a91c3d942170c4` |

## Schema / semantics contract

The promoted chromosome shards preserve the accepted compact feature schema from `t_7e356c5c`:

```text
feature_table, support_entity_type, tf_gene_id, tf_symbol_sample, enhancer_id, enhancer_chromosome, enhancer_start, enhancer_end, support_entity_id, support_entity_label, crm_support_rows, crm_interval_count, evidence_type, support_semantics, relation_under_review, support_scope, source, source_release, source_url, genome_build, liftover_performed, aggregation_policy, provenance_caveat, source_task_id, promotion_task_id, source_report, readiness_decision_doc
```

Validated constants inherited from the readiness gate:

- `feature_table = remap_crm_tf_enhancer_support`
- `evidence_type = crm_aggregated_support`
- `support_semantics = support_only_compact_crm_aggregate;not_observed_binding;not_graph_edge`
- `relation_under_review = tf_binds_enhancer`
- `support_scope = full_unbounded_all_chromosomes_crm`
- `source = ReMap`
- `source_release = 2022`
- `genome_build = GRCh38/hg38`
- `liftover_performed = false`
- `source_task_id = t_5968ce32`

Downstream reader caveat: readers must be shard-aware (`summary_chr1` ... `summary_chr22`, `summary_chrX`, `summary_chrY`, plus `tf_global_summary`). Do not assume a monolithic Parquet and do not silently replace the bounded single-file sidecar.

## Shard-aware reader helper

Task `t_6c07d9c8` added a read-only helper for the canonical full support sidecar:

```bash
uv run python -m manage_db.remap_crm_support_reader status
uv run python -m manage_db.remap_crm_support_reader list-chromosomes
uv run python -m manage_db.remap_crm_support_reader tf-global-summary \
  --columns tf_gene_id,tf_symbol_sample,crm_support_rows,crm_interval_count,support_semantics \
  --limit 5 --format json
uv run python -m manage_db.remap_crm_support_reader read-chromosome \
  --chromosome 1 \
  --tf-gene-id ENSG00000213999 \
  --support-entity-type tf \
  --columns tf_gene_id,tf_symbol_sample,support_entity_type,crm_support_rows,crm_interval_count,support_semantics \
  --limit 5 --format json
uv run python -m manage_db.remap_crm_support_reader read-chromosome \
  --chromosome 1 \
  --support-entity-type enhancer \
  --columns enhancer_id,enhancer_chromosome,enhancer_start,enhancer_end,support_semantics \
  --limit 3 --format json
uv run python -m manage_db.remap_crm_support_reader check-endpoints \
  --chromosome 1 --support-entity-type enhancer --limit 3
```

Default reads use the healthy canonical FUSE prefix when mounted:

```text
/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/remap_crm_tf_enhancer_support_full
```

If FUSE is unavailable, the helper falls back to the canonical GCS URI:

```text
gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full
```

The helper accepts `--prefix` for explicit GCS/FUSE/local fixture reads. It lists shards without reading their contents, reads only one chromosome shard per `read-chromosome` call, and pushes `--limit` into a streaming Parquet scan so examples do not require a full shard or all 24 shards. `check-endpoints` is intentionally bounded: it checks only distinct TF/enhancer IDs present in the loaded sample against canonical `nodes/gene.parquet` and/or `nodes/enhancer.parquet`.

Observed live bounded readback for `t_6c07d9c8` used the healthy FUSE prefix and is recorded at:

- `artifacts/reports/t_6c07d9c8_remap_crm_support_reader_live_readback.json`

Observed readback facts from that report:

- `list-chromosomes` returned all 24 shards (`1`-`22`, `X`, `Y`).
- `tf-global-summary --limit 3` returned support-only TF rows, including `ENSG00000213999` / `MEF2B`, with `support_semantics = support_only_compact_crm_aggregate;not_observed_binding;not_graph_edge`.
- `read-chromosome --chromosome 1 --tf-gene-id ENSG00000213999 --support-entity-type tf --limit 5` returned one chr1 TF support row for `MEF2B`.
- `read-chromosome --chromosome 1 --support-entity-type enhancer --limit 3` returned three chr1 enhancer support rows.
- `check-endpoints --chromosome 1 --support-entity-type enhancer --limit 3` checked three loaded enhancer IDs with enhancer endpoint anti-join `0`.

Semantics remain unchanged: this reader exposes the `canonical promoted full support sidecar` as support-only feature/QA material. It must not be interpreted as `edges/tf_binds_enhancer.parquet`, `evidence/tf_binds_enhancer.parquet`, observed binding, inferred edges, or graph topology.

## Validation performed

Preflight and post-write validation were run with:

```bash
uv run python -m py_compile artifacts/staged/t_f2a2952e/promote_remap_crm_full_support_sidecar.py
uv run python artifacts/staged/t_f2a2952e/promote_remap_crm_full_support_sidecar.py preflight
uv run python artifacts/staged/t_f2a2952e/promote_remap_crm_full_support_sidecar.py copy
uv run python artifacts/staged/t_f2a2952e/promote_remap_crm_full_support_sidecar.py validate
```

Observed PASS outputs:

```text
PRECHECK PASS: artifacts/reports/t_f2a2952e_remap_crm_full_support_sidecar_preflight.json
summary_files=24 summary_rows=48,768,788 tf_global_rows=1,179 all_data_size_bytes=5,144,121,535
POSTWRITE VALIDATION PASS: artifacts/reports/t_f2a2952e_remap_crm_full_support_sidecar_postwrite_validation.json
summary_files=24 summary_rows=48,768,788 enhancer_summary_rows=48,741,900 tf_rows_per_chromosome_sum=26,888 tf_global_rows=1,179 all_data_size_bytes=5,144,121,535
```

Post-write validation read canonical objects back through the verified FUSE root and checked:

- all 25 expected data Parquets exist under the new canonical prefix;
- row counts match the source/readiness manifest (`48,768,788` summary rows, `1,179` global TF rows);
- source SHA256 equals canonical FUSE readback SHA256 for every data object;
- source size equals canonical GCS size for every data object;
- chromosome shard columns match the accepted 27-column schema contract;
- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support.parquet` generation and size stayed unchanged;
- forbidden graph/topology paths remain absent.

Readiness validation reused as immutable evidence from `t_7e356c5c`:

- all-shard enhancer endpoint anti-join: `0`
- all-shard enhancer coordinate mismatches by ID: `0`
- all-shard duplicate enhancer IDs: `0`
- per-chromosome TF gene endpoint anti-join: `0`
- TF global endpoint anti-join: `0`
- schema ok all shards: `True`

Forbidden canonical paths checked absent after promotion:

- `gs://jouvencekb/kg/v2/edges/tf_binds_enhancer.parquet`: `False`
- `gs://jouvencekb/kg/v2/edges_inferred/remap_crm_supports_tf_enhancer.parquet`: `False`
- `gs://jouvencekb/kg/v2/evidence/tf_binds_enhancer.parquet`: `False`
- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full_candidate.parquet`: `False`

## Rollback handle

If reviewer rejects the canonical sidecar, remove exactly the objects written by this card using the generation-checked manifest. The full object/generation list is in `artifacts/reports/t_f2a2952e_remap_crm_full_support_sidecar_canonical_manifest.json`. Generation-checked rollback commands:

```bash
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr1.parquet#1782327502251035'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr2.parquet#1782327507603172'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr3.parquet#1782327511398126'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr4.parquet#1782327514671807'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr5.parquet#1782327518834391'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr6.parquet#1782327522857829'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr7.parquet#1782327526525564'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr8.parquet#1782327529924810'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr9.parquet#1782327533046055'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr10.parquet#1782327536400823'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr11.parquet#1782327540655392'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr12.parquet#1782327544759887'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr13.parquet#1782327546677557'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr14.parquet#1782327549638358'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr15.parquet#1782327676025115'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr16.parquet#1782327679532440'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr17.parquet#1782327684365701'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr18.parquet#1782327686016960'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr19.parquet#1782327690466921'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr20.parquet#1782327692921971'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr21.parquet#1782327694291676'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr22.parquet#1782327696603664'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chrX.parquet#1782327699912116'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chrY.parquet#1782327700649150'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/tf_global_summary.parquet#1782327701359421'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/manifest.json#1782327802646296'
gsutil rm 'gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/metadata.json#1782327803373250'
```

## Residual risks

- This sidecar is large support/QA material with leakage risk for supervised regulatory/disease/drug tasks. Exclude it from labels/default graph topology unless a future split policy explicitly permits it.
- It is not sufficient evidence for canonical `tf_binds_enhancer` edge/evidence promotion; the full CRM/peak edge feasibility gate remains separate.
- Downstream code that expects a single feature Parquet must be updated before consuming the full sidecar.
