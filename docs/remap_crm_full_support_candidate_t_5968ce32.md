# ReMap CRM full/unbounded support sidecar candidate

Kanban task: `t_5968ce32`
Status: staged-only review-required; no canonical writes.
Recommendation: `staged full candidate`.

## Decision
A full/unbounded CRM support sidecar is scientifically useful under the already accepted support-only semantics because it adds the 96.5% of CRM intervals omitted by the bounded 5k-per-chromosome canonical sidecar while preserving the non-edge/non-observed-binding contract. Operationally, a monolithic parquet was avoided; the candidate is staged as 24 chromosome shards plus a compact global TF summary.

## Outputs
- stage_root: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32`
- source_inventory: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/full_source_inventory.json`
- support_summary_glob: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/support_candidates/remap_crm_tf_enhancer_support_summary_chr*.parquet`
- tf_global_summary: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/support_candidates/remap_crm_tf_enhancer_support_tf_global_summary.parquet`
- detailed_sample: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/support_candidates/remap_crm_tf_enhancer_support_detailed_sample.parquet`
- sharded_validation_details: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/reports/sharded_validation_details.json`
- json_report: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/reports/validation_report.json`
- markdown_report: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/reports/remap_crm_full_support_candidate_report.md`
- builder_script: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/build_full_crm_support_candidate.py`

## Inventory and bounded omission
- full_crm_intervals: 3327980
- full_regulator_mentions: 67317307
- distinct_symbols_total: 1210
- accepted_mentions: 65945977
- accepted_distinct_symbols: 1179
- ambiguous_mentions: 35882
- ambiguous_distinct_symbols: 2
- rejected_mentions: 1335448
- rejected_distinct_symbols: 29
- bounded_crm_intervals: 117571
- full_crm_intervals: 3327980
- bounded_omitted_crm_intervals: 3210409
- bounded_fraction_of_full: 0.035328036827144395
- bounded_omitted_fraction_of_full: 0.9646719631728556
- full_vs_bounded_multiplier: 28.306129912988748

## Candidate counts
- summary_files: 24
- summary_rows: 48768788
- enhancer_summary_rows: 48741900
- per_chrom_tf_rows_before_global_aggregation: 26888
- tf_global_rows: 1179
- distinct_support_tfs: 1179
- candidate_support_rows_not_materialized: 24453482386

## Validation gates
- ok: True
- all_shards_ok: True
- tf_global_endpoint_antijoin: 0
- no_edges_directory: True
- no_evidence_directory: True
- per_chromosome_details_path: /Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_5968ce32/reports/sharded_validation_details.json

Full per-chromosome validation details are in `artifacts/staged/t_5968ce32/reports/sharded_validation_details.json`; each shard passed endpoint anti-joins, coordinate consistency, semantic checks, and within-shard duplicate-key checks.

## Policies / non-goals
- semantics: support-only crm_aggregated_support feature/QA sidecar; not observed TF-enhancer binding; not tf_regulates_gene; not graph edge
- tf_mapping: only accepted unique HGNC-symbol-to-gene mappings enter support rows; ambiguous/rejected symbols are excluded and quantified
- full_product: full TF x CRM x enhancer support product is not materialized; summary stores compact per-enhancer/per-TF support counts plus bounded detailed sample
- gnn_leakage: exclude from supervised labels/default graph topology for tf_binds_enhancer, enhancer_regulates_gene, disease/drug prediction unless a future split policy explicitly prevents leakage
- promotion: do not write canonical features/ from this task; create a later promotion/review card if this candidate is accepted

## No canonical promotion in this task
- Did not write canonical `gs://jouvencekb/kg/v2/features/`.
- Did not create staged or canonical `edges/` or `evidence/` outputs.
- All-peak observed-binding ingestion remains stopped/deferred.