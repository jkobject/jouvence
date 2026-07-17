# ReMap CRM TF-enhancer support feature promotion

Kanban task: `t_656a1102`  
Canonical target: `features/remap_crm_tf_enhancer_support.parquet`  
Status: promoted; tester/reviewer validation still required before counting terminal

## Approval gate

Reviewer-approved readiness decision: `docs/remap_crm_canonical_readiness.md` via parent `t_6d9f250d`.
Approved exact target: `features/remap_crm_tf_enhancer_support.parquet`.
Approved semantics: `crm_aggregated_support` support/evidence sidecar only.

## Schema contract

Granularity: one compact support summary row per support entity, preserving staged `summary_type` semantics (`tf` or `enhancer`). This is not a full TF×enhancer pair table and must not be consumed as graph edges.

Columns:

```text
feature_table: string
support_entity_type: string
tf_gene_id: string
tf_symbol_sample: string
enhancer_id: string
enhancer_chromosome: string
enhancer_start: int64
enhancer_end: int64
support_entity_id: string
support_entity_label: string
crm_support_rows: int64
crm_interval_count: int64
evidence_type: string
support_semantics: string
relation_under_review: string
support_scope: string
source: string
source_release: string
source_url: string
genome_build: string
liftover_performed: bool
aggregation_policy: string
provenance_caveat: string
source_task_id: string
promotion_task_id: string
source_report: string
readiness_decision_doc: string
```

Endpoint contract:
- `support_entity_type = 'tf'`: `tf_gene_id` is populated and must anti-join 0 against canonical `nodes/gene.parquet`; enhancer endpoint columns are null.
- `support_entity_type = 'enhancer'`: `enhancer_id`, `enhancer_chromosome`, `enhancer_start`, and `enhancer_end` are populated and must anti-join/mismatch 0 against canonical `nodes/enhancer.parquet`; TF endpoint columns are null.
- `evidence_type` is constant `crm_aggregated_support`.
- `support_scope` is constant `bounded_all_chromosomes_5k_crm_per_chromosome`.
- `liftover_performed` is false; declared genome build is `GRCh38/hg38`.

## Validation summary

- Output rows: 2,915,130
- Enhancer summary rows: 2,891,253
- TF summary rows: 23,877
- Distinct enhancer endpoints: 2,891,253
- Distinct TF gene endpoints: 1,169
- TF gene anti-join: 0
- Enhancer anti-join: 0
- Enhancer coordinate mismatches by ID: 0
- Invalid support chromosomes: 0
- CRM interval invalid chromosomes: 0
- CRM interval invalid intervals: 0
- Output SHA256: `5c7e72c8cbdfb2a15a80f39e56ee569d95e711b60c554f197865628e2aef8bfd`

Machine-readable validation: `artifacts/reports/t_656a1102_remap_crm_tf_enhancer_support_validation.json`.

## TF mapping QA

Mapping policy: prefer unique human ENSG for hg38 ReMap CRM; fallback unique NCBI/other; multi-ENSG remains ambiguous

Recomputed status counts:

```json
[
  {
    "tf_mapping_status": "accepted",
    "regulator_mentions": 3172778,
    "distinct_symbols": 1176,
    "distinct_gene_ids": 1176
  },
  {
    "tf_mapping_status": "ambiguous",
    "regulator_mentions": 1872,
    "distinct_symbols": 2,
    "distinct_gene_ids": 0
  },
  {
    "tf_mapping_status": "rejected",
    "regulator_mentions": 66455,
    "distinct_symbols": 29,
    "distinct_gene_ids": 0
  }
]
```

Ambiguous/rejected TF symbols remain excluded from canonical support rows and are preserved in staged QA files:
- `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom/parsed/crm_tf_symbols_ambiguous.parquet`
- `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom/parsed/crm_tf_symbols_rejected.parquet`

## Semantic and GNN leakage policy

This table is QA/triage/feature support only. It is not `observed_binding`, not canonical `tf_binds_enhancer` edge/evidence, not `tf_regulates_gene`, and not an `edges_inferred` table.

Default GNN use policy: exclude this feature table from training labels for `tf_binds_enhancer`, `enhancer_regulates_gene`, disease/drug prediction, or any target constructed from overlapping regulatory evidence unless an explicit split policy prevents leakage.

## Scope caveat

Scope is bounded all-chromosome 5k-per-chromosome CRM support from ReMap 2022 hg38 CRM source, not full/unbounded ReMap.
