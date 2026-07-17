# ReMap motif threshold compact full-scope rescue

Task: `t_83e0ceef`  
Status: `review-required`; staged-only; no canonical writes.

## Verdict

Implemented the next feasible full-scope motif materialization path as a checkpointed tile/chromosome reducer plus compact support-code representation. It does not repeat the unbounded row-wise all-hit materialization from `t_84996e81` and does not write canonical `edges/tf_binds_enhancer.parquet` or `evidence/tf_binds_enhancer.parquet`.

The selected rescue representation is:

- per-CRM compact rows with `support_codes: list<int64>`, TF/motif summaries, score threshold metadata, leakage policy, and `canonical_write=false`;
- per-tile support-code dictionary rows preserving each retained motif-hit atom: motif ID, TF symbol/gene mapping, motif coordinates, UCSC/JASPAR score, source URLs, threshold semantics, and support-only policy;
- per-tile completion checkpoint JSON under `artifacts/staged/t_83e0ceef/checkpoints/` for audit/progress records. Durable skip/reuse resume is not claimed; repeated commands reprocess requested tiles and overwrite checkpoint/output shards.

## Threshold semantics

Chosen reducer threshold: `UCSC/JASPAR hg38 bigBed score >= 500`.

This score is the UCSC BED score field from the pinned JASPAR2026 hg38 motif-hit bigBed (`0..1000` scale). It is a computational reduction and prioritization threshold, not a calibrated binding probability. Rows are support atoms for review, not active graph topology.

Calibration from the same non-truncated representative tiles:

| threshold | raw hits above threshold | retained CRM-regulator-matched support |
| --- | ---: | ---: |
| `>=900` | 3 | 0 |
| `>=800` | 6 | 0 |
| `>=500` | 2,368 | 95 |

`>=500` is therefore the highest tested threshold that still produced real retained CRM-regulator-matched support on the representative Y tiles. It remains `review-required` before any full-scale/canonical use.

## Non-truncated representative run

Command:

```bash
uv run python -m py_compile artifacts/staged/t_83e0ceef/build_remap_motif_threshold_compact_rescue.py
uv run python artifacts/staged/t_83e0ceef/build_remap_motif_threshold_compact_rescue.py \
  --chroms Y \
  --tile-size 100 \
  --tile-start-row 1 \
  --extra-tile Y:1201:100 \
  --min-ucsc-score 500
```

Final validated output:

```text
crm_intervals=200
raw_ucsc_jaspar_hits_overlapping_crms=561,989
raw_hits_above_threshold=2,368
retained_support_code_assignments=95
support_code_dictionary_rows=95
crm_intervals_with_thresholded_motif_support=54
elapsed_seconds=2.0838589159830008
```

Tile details:

| tile | CRM intervals | raw motif hits | score>=500 raw hits | retained support | CRM rows with support |
| --- | ---: | ---: | ---: | ---: | ---: |
| `chrY_rows1_100` | 100 | 290,815 | 1,348 | 66 | 35 |
| `chrY_rows1201_1300` | 100 | 271,174 | 1,020 | 29 | 19 |

Top retained TFs in the validated query were `CTCF`, `HNF1A`, `CEBPA`, `FOSL2`, and `NR3C1`.

## Full 3,327,980-CRM estimate

Linear extrapolation from the two non-truncated representative tiles:

```text
estimated_raw_motif_hits=9,351,440,761
estimated_retained_support_assignments=1,580,790
estimated_support_code_dictionary_rows=1,580,790
estimated_crm_intervals_with_support=898,554
estimated_runtime_hours_at_observed_tile_rate=9.63
estimated_total_storage_bytes=1,552,119,952 (~1.45 GiB)
```

Caveat: this is a tile-density estimate. Chromosome-specific motif density and UCSC remote-cache behavior may vary; a production run should use row-window tiles with per-tile completion checkpoints and validate chromosome-wise throughput/storage before declaring full production materialization.

## Outputs

- Builder: `artifacts/staged/t_83e0ceef/build_remap_motif_threshold_compact_rescue.py`
- Feature dir: `artifacts/staged/t_83e0ceef/features/remap_crm_motif_threshold_compact/`
- Checkpoints: `artifacts/staged/t_83e0ceef/checkpoints/`
- Report JSON: `artifacts/staged/t_83e0ceef/reports/remap_motif_threshold_compact_rescue_report.json`
- Human report: `artifacts/staged/t_83e0ceef/reports/remap_motif_threshold_compact_rescue_report.md`
- Manifest: `artifacts/staged/t_83e0ceef/manifests/remap_motif_threshold_compact_rescue_manifest.json`
- Authoritative hash sidecar: `artifacts/staged/t_83e0ceef/manifests/remap_motif_threshold_compact_rescue_hash_manifest.json`
- Query examples: `artifacts/staged/t_83e0ceef/reports/query_examples.sql`

Hash integrity policy: `report_json`, `manifest_json`, and the hash sidecar are intentionally excluded from the embedded `output_hashes` object to avoid impossible self-referential hashes. The authoritative final SHA256 values for report/manifest/query/human-report files are in the sidecar written after report/manifest finalization.

Final actual hashes validated after rerun:

```text
report_json=0febcc37172509112a2f59b79326ff69904a813741e159d6300640f16c00b42b
manifest_json=0febcc37172509112a2f59b79326ff69904a813741e159d6300640f16c00b42b
hash_manifest_json=b718614430b48ecd58ec5c5787216f288c8511060eaf7f5b1fe47f404359cb0e
report_md=777875da2b51bc721e34f123bc24b9f6e582cb193dd10311600d4d6f31118cda
query_examples_sql=d11bd9cc0ba0934f0a4129f8b108dee30494327287c691a4472c4255b84e67c8
```

Validated parquet counts:

```text
compact CRM rows=200
support-code dictionary rows=95
nonzero compact CRM rows=54
```

## Validation

Validation command used DuckDB/PyArrow to check:

- report has `canonical_writes=false`;
- `no_canonical_writes=true`;
- `materialized_rows_gt_zero=true`;
- `all_tiles_non_truncated=true`;
- threshold policy is `min_ucsc_score=500`;
- compact all-CRM tile shards have 200 rows;
- support-code dictionaries have 95 rows;
- nonzero compact shards have 54 rows;
- query examples return the expected tile, TF, and compact-summary counts.
- report/manifest JSON do not embed self-hashes;
- authoritative sidecar hashes for report JSON, manifest JSON, report MD, and query examples match actual final files;
- checkpoint JSON self-hashes are not embedded in tile metadata.

Observed validation summary:

```text
checkpoint_query:
chrY_rows1201_1300  crm=100  raw=271174  above_threshold=1020  retained=29  supported_crm=19
chrY_rows1_100      crm=100  raw=290815  above_threshold=1348  retained=66  supported_crm=35

compact_summary_query:
chromosome=Y  crm_rows=200  support_code_assignments=95  crm_rows_with_support=54
```

## Semantics / leakage policy

Relation under review remains `tf_binds_enhancer`, but this artifact is `support_only_thresholded_motif_colocation;not_observed_binding;not_graph_edge`.

Do not use these support codes as supervised labels or default graph topology for `tf_binds_enhancer`, `enhancer_regulates_gene`, disease/drug prediction, or overlapping regulatory targets unless a later reviewed reducer explicitly proves split-safe leakage handling.

No canonical writes were performed.
