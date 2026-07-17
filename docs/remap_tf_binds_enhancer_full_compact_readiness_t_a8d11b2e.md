# ReMap `tf_binds_enhancer` full compact-coded canonical-readiness build

Task: `t_a8d11b2e`  
Status: `review-required`; staged support/feature build; no canonical KG writes.

## Verdict

Built full chromosome-sharded compact support-code arrays over the available full ReMap CRM aggregate sidecar and range dictionaries that resolve support codes back to the validated source sidecar. No `edges/tf_binds_enhancer.parquet` or `evidence/tf_binds_enhancer.parquet` was written or authorized.

Per-relation decision: keep the full artifact as a feature/support sidecar now. `tf_binds_enhancer` remains the right relation label for reviewed TF-enhancer binding evidence, but the current full CRM aggregate object is not itself canonical graph topology.

## Outputs

- Feature prefix: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_a8d11b2e/features/tf_binds_enhancer_compact_support_codes_full`
- Enhancer array shards: `enhancer_support_codes_chr1.parquet` ... `enhancer_support_codes_chrY.parquet`
- Range dictionary: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_a8d11b2e/features/tf_binds_enhancer_compact_support_codes_full/support_code_dictionary_ranges.parquet`
- TF global dictionary: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_a8d11b2e/features/tf_binds_enhancer_compact_support_codes_full/tf_global_support_code_dictionary.parquet`
- Evidence inventory: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_a8d11b2e/features/tf_binds_enhancer_compact_support_codes_full/available_evidence_inventory.parquet`
- Query examples: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_a8d11b2e/reports/query_examples.sql`
- JSON report: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_a8d11b2e/reports/remap_tf_binds_enhancer_full_compact_readiness_report.json`
- Manifest: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_a8d11b2e/manifests/remap_tf_binds_enhancer_full_compact_readiness_manifest.json`

## Counts

- chromosome array shards: 24
- enhancer array rows: 48,741,900
- support-code assignments in arrays: 48,741,900
- range dictionary rows: 24
- range-resolvable support codes: 48,741,900
- TF global dictionary rows: 1,179
- full sidecar summary rows inherited from source: 48,768,788

## Range dictionary

| chromosome | support_code_start | support_code_end | support_code_count | source_enhancer_rows |
| --- | --- | --- | --- | --- |
| 1 | 1 | 5068275 | 5068275 | 5068275 |
| 2 | 5068276 | 8432416 | 3364141 | 3364141 |
| 3 | 8432417 | 11085322 | 2652906 | 2652906 |
| 4 | 11085323 | 12802909 | 1717587 | 1717587 |
| 5 | 12802910 | 15020962 | 2218053 | 2218053 |
| 6 | 15020963 | 17518297 | 2497335 | 2497335 |
| 7 | 17518298 | 19712604 | 2194307 | 2194307 |
| 8 | 19712605 | 21482849 | 1770245 | 1770245 |
| 9 | 21482850 | 23411488 | 1928639 | 1928639 |
| 10 | 23411489 | 25435995 | 2024507 | 2024507 |
| 11 | 25435996 | 28222164 | 2786169 | 2786169 |
| 12 | 28222165 | 30639259 | 2417095 | 2417095 |
| 13 | 30639260 | 31575802 | 936543 | 936543 |
| 14 | 31575803 | 33115475 | 1539673 | 1539673 |
| 15 | 33115476 | 34725882 | 1610407 | 1610407 |
| 16 | 34725883 | 36816240 | 2090358 | 2090358 |
| 17 | 36816241 | 39861459 | 3045219 | 3045219 |
| 18 | 39861460 | 40542051 | 680592 | 680592 |
| 19 | 40542052 | 43593852 | 3051801 | 3051801 |
| 20 | 43593853 | 45061681 | 1467829 | 1467829 |
| 21 | 45061682 | 45549663 | 487982 | 487982 |
| 22 | 45549664 | 46857780 | 1308117 | 1308117 |
| X | 46857781 | 48741900 | 1884120 | 1884120 |
| Y | 48741901 | 48741900 | 0 | 0 |

## Available evidence inventory

| input_family | scope | rows_available | used_in_this_build | canonical_edge_ready |
| --- | --- | --- | --- | --- |
| full_crm_aggregate_sidecar | full_unbounded_all_chromosomes | 48768788 | True | False |
| bounded_observed_peak_and_reconstructed_crm_pilot | bounded first80 chr1 pilot | 6356561 | False | False |
| bounded_motif_colocation | bounded accepted motif evidence | 549 | False | False |
| full_motif_scan_manifest | full scan/resume manifest only | 549 | True | False |

## Validation

```json
{
  "ok": true,
  "canonical_writes": false,
  "array_shards": 24,
  "array_total_rows": 48741900,
  "support_code_assignments_in_arrays": 48741900,
  "range_dictionary_rows": 24,
  "tf_global_dictionary_rows": 1179,
  "array_row_count_matches_range_dictionary": true,
  "support_code_ranges_contiguous_allowing_zero_row_chrY": true,
  "inherited_endpoint_antijoins": {
    "source": "artifacts/reports/t_7e356c5c_remap_crm_full_sidecar_promotion_readiness_validation.json",
    "all_shard_enhancer_endpoint_antijoin": 0,
    "all_shard_enhancer_coordinate_mismatches": 0,
    "per_chromosome_tf_gene_endpoint_antijoin": 0,
    "tf_global_endpoint_antijoin": 0,
    "note": "Endpoint membership was promotion-grade validated on the source sidecar; this build preserves the exact enhancer IDs from that source and adds deterministic support-code arrays."
  }
}
```

Endpoint anti-joins are inherited from the promotion-grade full sidecar readiness validation (`t_7e356c5c`): all-shard enhancer endpoint anti-join 0, enhancer coordinate mismatches 0, per-chromosome TF gene endpoint anti-join 0, and TF global endpoint anti-join 0. This build preserves the exact enhancer IDs from that source and adds deterministic support-code arrays only.

## Leakage / training policy

exclude ReMap CRM/peak/motif support codes from supervised labels and default training graph topology for tf_binds_enhancer, enhancer_regulates_gene, disease/drug prediction, or overlapping regulatory targets unless a future split policy explicitly prevents source/interval/context leakage

Default supervised graph topology must use empty allowed support-code arrays from this sidecar unless a later review explicitly approves a split-safe reducer.

## Canonical namespace proposal

`features/tf_binds_enhancer_compact_support_codes_full/` as chromosome shards plus range dictionaries after review; do not write `edges/tf_binds_enhancer.parquet` or `evidence/tf_binds_enhancer.parquet` from this aggregate support build.

## Why and when `tf_binds_enhancer` becomes canonical

`tf_binds_enhancer` is canonical when rows assert source-backed TF binding at enhancer intervals and evidence rows preserve observed/reconstructed support classes, provenance, scores, context, and leakage controls. The bounded pilot shows that semantics are possible at limited scope. The full CRM aggregate support sidecar is not enough on its own because it lacks per-observed-peak and per-TF-enhancer evidence semantics and would silently change the accepted evidence model.

A future canonical edge/evidence promotion is appropriate only after a reviewed reducer or full materialization policy defines thresholds/support classes, passes endpoint/evidence audits, proves leakage-safe train/test treatment, and receives independent acceptance. Until then, this artifact is canonical-readiness/support material only.
