# ReMap CRM full support sidecar promotion-readiness decision

Kanban task: `t_7e356c5c`  
Source staged candidate: `t_5968ce32`  
Status: `review-required`; no canonical write performed.  
Recommendation: `promote canonical full support sidecar` after independent review, as a sharded feature/QA sidecar, not as graph edges/evidence/inferred output.

## Decision

Promote the full/unbounded ReMap CRM support candidate only after review, and keep the 24 chromosome-sharded summary Parquets plus one global TF summary Parquet. Do not build a monolithic Parquet for canonical promotion.

Proposed canonical layout, if reviewer accepts this readiness artifact:

- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/summary_chr1.parquet` ... `summary_chr22.parquet`, `summary_chrX.parquet`, `summary_chrY.parquet`
- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/tf_global_summary.parquet`
- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/manifest.json`

The existing bounded sidecar should remain untouched unless a reviewer explicitly approves replacing it:

- existing bounded artifact: `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support.parquet`

## Why sharded layout wins

The accepted staged full candidate has 48,768,788 compact summary rows and is about 4.8 GiB locally. A monolithic Parquet would be operationally worse for promotion and readers because every checksum, retry, copy, validation, or partial downstream read would operate on one large object.

The 24-shard layout is better because:

- Promotion retries are bounded to the failed chromosome shard.
- Endpoint and coordinate validation can be chunked by chromosome.
- Downstream readers that operate by genome window/chromosome can avoid scanning all 48.8M rows.
- The compact global TF summary stays tiny and separate from enhancer-heavy chromosome shards.
- It preserves the current staged producer layout and avoids a lossy/opaque rewrite step.

GCS staging recommendation:

- Full candidate data should be copied only to an explicit staging prefix first, e.g. `gs://jouvencekb/kg/staging/remap-crm-full-support-sidecar-readiness-t_7e356c5c/support_candidates/`, if the reviewer wants GCS durability before canonical promotion.
- This task uploaded only the readiness report/manifest to staging for durability; it did not copy the 4.8 GiB data payload and did not canonical-write.

Uploaded readiness objects:

- `gs://jouvencekb/kg/staging/remap-crm-full-support-sidecar-readiness-t_7e356c5c/reports/t_7e356c5c_remap_crm_full_sidecar_promotion_readiness_validation.json`
- `gs://jouvencekb/kg/staging/remap-crm-full-support-sidecar-readiness-t_7e356c5c/reports/remap_crm_full_sidecar_promotion_readiness_manifest.json`

## Inputs used

Accepted source candidate under local staged artifacts only:

- `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/support_candidates/remap_crm_tf_enhancer_support_summary_chr*.parquet`
- `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/support_candidates/remap_crm_tf_enhancer_support_tf_global_summary.parquet`
- `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/support_candidates/remap_crm_tf_enhancer_support_detailed_sample.parquet`
- `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/parsed/tf_symbol_map.parquet`
- `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/reports/validation_report.json`
- `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/reports/sharded_validation_details.json`

Canonical endpoint references checked through the verified FUSE root:

- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/nodes/gene.parquet`
- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/nodes/enhancer.parquet`

## Promotion-grade validation rerun

Machine-readable validation:

- `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/reports/t_7e356c5c_remap_crm_full_sidecar_promotion_readiness_validation.json`
- `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_7e356c5c/remap_crm_full_sidecar_promotion_readiness_manifest.json`

Validation method:

- Streamed all 48,741,900 staged support enhancer rows to TSV.
- Streamed all 48,808,144 canonical enhancer node rows to TSV.
- External-sorted both by enhancer ID.
- Used `join` to compute all-shard enhancer endpoint anti-join and coordinate mismatch counts.
- Used DuckDB for schema constants, TF endpoint anti-joins, entity-shape checks, semantic guard checks, and forbidden path checks.

Rerun result: `ok: true`.

Key counts:

- summary files: 24
- summary rows: 48,768,788
- enhancer summary rows: 48,741,900
- per-chromosome TF summary rows: 26,888
- global TF summary rows: 1,179
- canonical enhancer node rows streamed for validation: 48,808,144

Gate results:

- all-shard enhancer endpoint anti-join: 0
- all-shard enhancer coordinate mismatches by ID: 0
- all-shard duplicate enhancer IDs: 0
- per-chromosome TF gene endpoint anti-join: 0
- global TF endpoint anti-join: 0
- invalid entity-shape rows: 0
- invalid coordinate rows: 0
- semantic forbidden rows: 0
- schema columns match expected contract across all 24 shards: true
- constant guard violations for feature table/evidence type/support semantics/relation/scope/source/release/build/liftover/source task: all 0
- forbidden local staged `edges/`, `evidence/`, `edges_inferred/`, and full-candidate feature file under `t_5968ce32`: absent
- forbidden canonical GCS paths checked by `gsutil -q stat`: absent

Forbidden canonical paths checked absent:

- `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full_candidate.parquet`
- `gs://jouvencekb/kg/v2/edges/tf_binds_enhancer.parquet`
- `gs://jouvencekb/kg/v2/evidence/tf_binds_enhancer.parquet`
- `gs://jouvencekb/kg/v2/edges_inferred/remap_crm_supports_tf_enhancer.parquet`

## Schema / semantics contract

The full support candidate remains a feature/QA sidecar with the same compact per-entity schema family as the bounded support sidecar. It is not a graph edge, not evidence, not an inferred edge, and not observed binding.

Required constants validated:

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

## Non-goals preserved

This readiness task did not:

- write canonical `gs://jouvencekb/kg/v2/features/` data,
- write canonical or staged graph `edges/`,
- write canonical or staged `evidence/`,
- write `edges_inferred/`,
- reinterpret CRM support rows as `observed_binding`,
- materialize a full TF × CRM × enhancer product.

## Residual risks / reviewer notes

- The object should be promoted as a new full sidecar prefix, not silently overwrite the existing bounded single-file sidecar.
- The full sidecar is a large feature/QA artifact. Downstream loaders must be shard-aware and should not assume one Parquet file.
- It remains support-only and high leakage-risk for supervised regulatory/disease/drug tasks. Exclude from labels/default graph topology unless a future split policy explicitly prevents leakage.
- If GCS durability of the data payload is desired before canonical review, copy the 24 shards plus TF global summary to the proposed `kg/staging` prefix first and re-run manifest checks there.

## Commands run

```bash
uv run python artifacts/staged/t_7e356c5c/validate_remap_crm_full_sidecar_external.py
python - <<'PY'
# generated SHA256 manifest for the 24 shard parquets, TF global summary,
# detailed sample, source reports, builder script, mapping table, and validation JSON
PY
gsutil -m cp artifacts/reports/t_7e356c5c_remap_crm_full_sidecar_promotion_readiness_validation.json \
  artifacts/staged/t_7e356c5c/remap_crm_full_sidecar_promotion_readiness_manifest.json \
  gs://jouvencekb/kg/staging/remap-crm-full-support-sidecar-readiness-t_7e356c5c/reports/
```

## Final recommendation

`promote canonical full support sidecar` after independent review, using the sharded full-support layout above. Keep the current bounded sidecar until the reviewer explicitly approves either an additive full sidecar prefix or a controlled replacement/migration. Do not canonical-write from this task.
