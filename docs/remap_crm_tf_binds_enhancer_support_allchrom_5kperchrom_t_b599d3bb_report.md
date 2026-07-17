# ReMap CRM tf_binds_enhancer support/QA artifact

Status: staged-only review-required (2026-06-23T18:20:34).
Evidence semantics: `crm_aggregated_support` support/QA only, not primary `observed_binding`.
Canonical writes: `False`.

## Scope
- Requested scope: all feasible CRM chromosomes: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, X, Y.
- Actual scope: bounded up to 5000 CRM intervals per selected chromosome.
- Source rows selected: 117571 CRM intervals from https://remap.univ-amu.fr/storage/remap2022/hg38/MACS2/remap2022_crm_macs2_hg38_v1_0.bed.gz.
- Genome build: ReMap CRM hg38/GRCh38; enhancer nodes assumed hg38/GRCh38; no liftover performed.

## Outputs
- gcs_stage_root: `gs://jouvencekb/kg/staging/source-native-expansion/remap-crm-tf-binds-enhancer-support-allchrom-5kperchrom-20260623-t_b599d3bb/all_chrom_5k_per_chrom/`
- stage_root: `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom`
- crm_intervals: `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom/parsed/crm_intervals_all.parquet`
- tf_symbol_candidates: `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom/parsed/crm_tf_symbol_candidates_all.parquet`
- support_summary_glob: `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom/support_candidates/tf_binds_enhancer_crm_support_summary_chr*.parquet`
- detailed_sample: `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom/support_candidates/tf_binds_enhancer_crm_support_detailed_sample.parquet`
- top_tfs: `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom/support_candidates/top_tfs_all.parquet`
- top_enhancers: `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom/support_candidates/top_enhancers_all.parquet`
- json_report: `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom/reports/validation_report.json`
- markdown_report: `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom/reports/remap_crm_tf_binds_enhancer_support_full_report.md`

## Counts
- crm_intervals: 117571
- crm_regulator_mentions: 3241105
- distinct_crm_symbols: 1207
- interval_enhancer_overlap_rows: 6232552
- accepted_interval_enhancer_overlap_rows: 6232552
- candidate_support_rows: 1442646529
- support_summary_rows: 2915130
- distinct_accepted_tfs: 1176 (accepted unique TF gene IDs in `parsed/crm_tf_symbol_candidates_all.parquet` before enhancer-support materialization; legacy JSON field `distinct_candidate_tfs` has this definition)
- distinct_supported_tfs: 1169 (unique TF entity IDs materialized in support summary/top TF rows after enhancer-overlap filtering)
- distinct_candidate_enhancers: 2891253
- support_summary_type_counts: enhancer=2891253, tf=23877 (`summary_type` is entity kind, not a compact-support marker)
- support_edge_summary_policy: not_materialized_full_TF_x_enhancer; compact enhancer/tf aggregate summary plus bounded detailed sample
- tf_mapping_reference: {'symbol_rows': 264987, 'accepted_symbols': 88898, 'ambiguous_symbols': 907, 'mapping_policy': 'prefer unique human ENSG for hg38 ReMap CRM; fallback unique NCBI/other; multi-ENSG remains ambiguous'}

## TF mapping status
- accepted: 3172778 mentions, 1176 distinct symbols
- ambiguous: 1872 mentions, 2 distinct symbols
- rejected: 66455 mentions, 29 distinct symbols

## Counts by chromosome
- chr1: 5000 CRM intervals, 230485 regulator mentions, 225247 accepted regulator mentions, 544910 overlap rows, 544910 accepted overlap rows, 126382563 candidate support rows, 261151 compact summary rows
- chr2: 5000 CRM intervals, 77543 regulator mentions, 75815 accepted regulator mentions, 79066 overlap rows, 79066 accepted overlap rows, 14140459 candidate support rows, 36273 compact summary rows
- chr3: 5000 CRM intervals, 48333 regulator mentions, 46883 accepted regulator mentions, 37924 overlap rows, 37924 accepted overlap rows, 7789373 candidate support rows, 19617 compact summary rows
- chr4: 5000 CRM intervals, 169670 regulator mentions, 166023 accepted regulator mentions, 329752 overlap rows, 329752 accepted overlap rows, 80099453 candidate support rows, 148131 compact summary rows
- chr5: 5000 CRM intervals, 126906 regulator mentions, 123845 accepted regulator mentions, 220040 overlap rows, 220040 accepted overlap rows, 32626677 candidate support rows, 96836 compact summary rows
- chr6: 5000 CRM intervals, 137299 regulator mentions, 134798 accepted regulator mentions, 220230 overlap rows, 220230 accepted overlap rows, 51118128 candidate support rows, 103291 compact summary rows
- chr7: 5000 CRM intervals, 208562 regulator mentions, 203889 accepted regulator mentions, 273714 overlap rows, 273714 accepted overlap rows, 63409399 candidate support rows, 132110 compact summary rows
- chr8: 5000 CRM intervals, 57747 regulator mentions, 56351 accepted regulator mentions, 87573 overlap rows, 87573 accepted overlap rows, 10586212 candidate support rows, 41589 compact summary rows
- chr9: 5000 CRM intervals, 78320 regulator mentions, 76233 accepted regulator mentions, 99108 overlap rows, 99108 accepted overlap rows, 17180932 candidate support rows, 47302 compact summary rows
- chr10: 5000 CRM intervals, 86293 regulator mentions, 84652 accepted regulator mentions, 69869 overlap rows, 69869 accepted overlap rows, 14691722 candidate support rows, 34034 compact summary rows
- chr11: 5000 CRM intervals, 194063 regulator mentions, 189992 accepted regulator mentions, 575446 overlap rows, 575446 accepted overlap rows, 105941781 candidate support rows, 267900 compact summary rows
- chr12: 5000 CRM intervals, 120916 regulator mentions, 118465 accepted regulator mentions, 185435 overlap rows, 185435 accepted overlap rows, 40016519 candidate support rows, 88177 compact summary rows
- chr13: 5000 CRM intervals, 89375 regulator mentions, 87073 accepted regulator mentions, 168195 overlap rows, 168195 accepted overlap rows, 36533800 candidate support rows, 77601 compact summary rows
- chr14: 5000 CRM intervals, 144334 regulator mentions, 141520 accepted regulator mentions, 357942 overlap rows, 357942 accepted overlap rows, 104660369 candidate support rows, 168086 compact summary rows
- chr15: 5000 CRM intervals, 59116 regulator mentions, 57700 accepted regulator mentions, 101166 overlap rows, 101166 accepted overlap rows, 15350148 candidate support rows, 51618 compact summary rows
- chr16: 5000 CRM intervals, 283361 regulator mentions, 277701 accepted regulator mentions, 753312 overlap rows, 753312 accepted overlap rows, 198568365 candidate support rows, 348295 compact summary rows
- chr17: 5000 CRM intervals, 169350 regulator mentions, 165830 accepted regulator mentions, 339602 overlap rows, 339602 accepted overlap rows, 87703374 candidate support rows, 162741 compact summary rows
- chr18: 5000 CRM intervals, 110527 regulator mentions, 108216 accepted regulator mentions, 129419 overlap rows, 129419 accepted overlap rows, 31861492 candidate support rows, 57099 compact summary rows
- chr19: 5000 CRM intervals, 351033 regulator mentions, 344576 accepted regulator mentions, 687237 overlap rows, 687237 accepted overlap rows, 187117442 candidate support rows, 310923 compact summary rows
- chr20: 5000 CRM intervals, 139748 regulator mentions, 136990 accepted regulator mentions, 335392 overlap rows, 335392 accepted overlap rows, 82000020 candidate support rows, 163042 compact summary rows
- chr21: 5000 CRM intervals, 81588 regulator mentions, 79931 accepted regulator mentions, 58704 overlap rows, 58704 accepted overlap rows, 12383560 candidate support rows, 29147 compact summary rows
- chr22: 5000 CRM intervals, 172722 regulator mentions, 169567 accepted regulator mentions, 387425 overlap rows, 387425 accepted overlap rows, 93106832 candidate support rows, 179146 compact summary rows
- chrX: 5000 CRM intervals, 82642 regulator mentions, 80825 accepted regulator mentions, 191091 overlap rows, 191091 accepted overlap rows, 29377909 candidate support rows, 91021 compact summary rows
- chrY: 2571 CRM intervals, 21172 regulator mentions, 20656 accepted regulator mentions, 0 overlap rows passing filters in this bounded tranche, 0 accepted overlap rows, 0 candidate support rows, 0 compact summary rows

## Top TFs
- HDAC2 (ENSG00000196591): 6321625 rows, 9962 CRM interval-links, NA distinct enhancers
- MAX (ENSG00000125952): 5917087 rows, 11575 CRM interval-links, NA distinct enhancers
- YY1 (ENSG00000100811): 5750195 rows, 10210 CRM interval-links, NA distinct enhancers
- KDM5B (ENSG00000117139): 5739689 rows, 7857 CRM interval-links, NA distinct enhancers
- AR (ENSG00000169083): 5595427 rows, 15958 CRM interval-links, NA distinct enhancers
- ZBTB7A (ENSG00000178951): 5434919 rows, 8626 CRM interval-links, NA distinct enhancers
- SIN3A (ENSG00000169375): 5408326 rows, 6830 CRM interval-links, NA distinct enhancers
- REST (ENSG00000084093): 5382964 rows, 8951 CRM interval-links, NA distinct enhancers
- BCL11A (ENSG00000119866): 5333289 rows, 6204 CRM interval-links, NA distinct enhancers
- EP300 (ENSG00000100393): 5300224 rows, 9353 CRM interval-links, NA distinct enhancers
- TP63 (ENSG00000073282): 5213459 rows, 10512 CRM interval-links, NA distinct enhancers
- CTCF (ENSG00000102974): 5181221 rows, 14777 CRM interval-links, NA distinct enhancers
- TAF1 (ENSG00000147133): 5179076 rows, 5596 CRM interval-links, NA distinct enhancers
- TCF12 (ENSG00000140262): 5116658 rows, 8170 CRM interval-links, NA distinct enhancers
- MYC (ENSG00000136997): 5096245 rows, 10805 CRM interval-links, NA distinct enhancers
- ETS1 (ENSG00000134954): 5025206 rows, 7619 CRM interval-links, NA distinct enhancers
- JUN (ENSG00000177606): 5014035 rows, 10923 CRM interval-links, NA distinct enhancers
- CHD1 (ENSG00000153922): 5012104 rows, 6937 CRM interval-links, NA distinct enhancers
- EZH2 (ENSG00000106462): 4959971 rows, 14520 CRM interval-links, NA distinct enhancers
- RELA (ENSG00000173039): 4921507 rows, 12206 CRM interval-links, NA distinct enhancers
- ELF1 (ENSG00000120690): 4906375 rows, 8097 CRM interval-links, NA distinct enhancers
- NR3C1 (ENSG00000113580): 4884521 rows, 9934 CRM interval-links, NA distinct enhancers
- ERG (ENSG00000157554): 4873961 rows, 10376 CRM interval-links, NA distinct enhancers
- CREBBP (ENSG00000005339): 4856547 rows, 6741 CRM interval-links, NA distinct enhancers
- RAD21 (ENSG00000164754): 4828656 rows, 10172 CRM interval-links, NA distinct enhancers
- POU5F1 (ENSG00000204531): 4824120 rows, 8622 CRM interval-links, NA distinct enhancers
- MAZ (ENSG00000103495): 4802819 rows, 6293 CRM interval-links, NA distinct enhancers
- SMAD3 (ENSG00000166949): 4752045 rows, 7504 CRM interval-links, NA distinct enhancers
- SP1 (ENSG00000185591): 4740967 rows, 6885 CRM interval-links, NA distinct enhancers
- BCOR (ENSG00000183337): 4740705 rows, 6887 CRM interval-links, NA distinct enhancers
- EGR1 (ENSG00000120738): 4712790 rows, 8357 CRM interval-links, NA distinct enhancers
- MYCN (ENSG00000134323): 4672127 rows, 8009 CRM interval-links, NA distinct enhancers
- JUND (ENSG00000130522): 4621262 rows, 6790 CRM interval-links, NA distinct enhancers
- RUNX1 (ENSG00000159216): 4553486 rows, 11349 CRM interval-links, NA distinct enhancers
- TCF3 (ENSG00000071564): 4543218 rows, 7707 CRM interval-links, NA distinct enhancers
- BRD3 (ENSG00000169925): 4520719 rows, 6624 CRM interval-links, NA distinct enhancers
- HDAC1 (ENSG00000116478): 4514795 rows, 6777 CRM interval-links, NA distinct enhancers
- FOXA1 (ENSG00000129514): 4503104 rows, 9783 CRM interval-links, NA distinct enhancers
- SMARCA4 (ENSG00000127616): 4496461 rows, 14718 CRM interval-links, NA distinct enhancers
- SMARCC1 (ENSG00000173473): 4477667 rows, 9188 CRM interval-links, NA distinct enhancers
- GABPA (ENSG00000154727): 4453069 rows, 7081 CRM interval-links, NA distinct enhancers
- CDK8 (ENSG00000132964): 4451719 rows, 4941 CRM interval-links, NA distinct enhancers
- ESR1 (ENSG00000091831): 4431671 rows, 17712 CRM interval-links, NA distinct enhancers
- PAX5 (ENSG00000196092): 4405362 rows, 5896 CRM interval-links, NA distinct enhancers
- ZNF143 (ENSG00000166478): 4389266 rows, 7304 CRM interval-links, NA distinct enhancers
- NFKB1 (ENSG00000109320): 4381800 rows, 7089 CRM interval-links, NA distinct enhancers
- MED1 (ENSG00000125686): 4318624 rows, 13256 CRM interval-links, NA distinct enhancers
- NELFE (ENSG00000204356): 4309598 rows, 8250 CRM interval-links, NA distinct enhancers
- STAT3 (ENSG00000168610): 4305351 rows, 10577 CRM interval-links, NA distinct enhancers
- SUPT5H (ENSG00000196235): 4267828 rows, 6888 CRM interval-links, NA distinct enhancers

## Top enhancers
- c734423038b5707bb0f09355edf0a7f6 chr18:3448701-3451800: 2786 rows, 6 CRM interval-links, NA distinct TFs
- 64267f5353cb9d9027c9070c51fe9341 chr18:3448703-3451659: 2786 rows, 6 CRM interval-links, NA distinct TFs
- 17e480e570e4e331f3b1de8986e3917f chr18:3448690-3451796: 2786 rows, 6 CRM interval-links, NA distinct TFs
- 6d23845b0b7242f535d6569fd1ca2068 chr19:1249805-1253863: 2703 rows, 10 CRM interval-links, NA distinct TFs
- 4ad0ca7f350eb04c8aa2d5b22ebdf3e8 chr19:1249805-1253863: 2703 rows, 10 CRM interval-links, NA distinct TFs
- e959f84455b8fd220dc0ba14e50be22b chr19:1249805-1253863: 2703 rows, 10 CRM interval-links, NA distinct TFs
- 29b850cc83d2692c3d4d4c573de99efd chr19:1249805-1253863: 2703 rows, 10 CRM interval-links, NA distinct TFs
- c277e3822b7c3250fb495d1ee5ac4f62 chr19:1249805-1253863: 2703 rows, 10 CRM interval-links, NA distinct TFs
- 42b790e62e28a2e89dcc5bc568781290 chr19:1249805-1253863: 2703 rows, 10 CRM interval-links, NA distinct TFs
- fdc908956df78e463e7bc525e3d115b7 chr17:2398868-2402332: 2599 rows, 10 CRM interval-links, NA distinct TFs
- 7b10249a1307158bc6f26a0146b02da9 chr18:3449141-3452833: 2595 rows, 7 CRM interval-links, NA distinct TFs
- b082e03bd061119cef973aefd40b4558 chr18:3447389-3450968: 2572 rows, 7 CRM interval-links, NA distinct TFs
- 4d9b574e05599e2895725ca0b5fd2323 chr14:20681470-20685104: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 37016fec5b10e3e1477ca6dc019f35ba chr14:20681189-20685425: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 18f2ab89639e74f81d37e3a861be18a4 chr14:20681078-20685082: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 051788eb130eb16b8775939b2f05b4d7 chr14:20681437-20685060: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 2dea81092f9f49362b29c770da02ee9f chr14:20681464-20685084: 2461 rows, 9 CRM interval-links, NA distinct TFs
- e422db8e4d334ab115d8591451088a83 chr14:20681071-20685059: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 11c4f62e00c6c0dd6709f992a33e8d4e chr14:20681447-20685103: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 3568f00e51ba3ef7b8e79ca45f46ddfc chr14:20681464-20685084: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 77e1d891e44540873e74f77667bf1b4f chr14:20681462-20685122: 2461 rows, 9 CRM interval-links, NA distinct TFs
- d989fcd959ab3c826a9eb573824ef0fd chr14:20681071-20685059: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 0651f01b8c6c0facbf1d4af535e8b79e chr14:20681470-20685104: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 7e189743443f2f031fb266ad1ab81da3 chr14:20681123-20685068: 2461 rows, 9 CRM interval-links, NA distinct TFs
- f15a2036e44fcf651e4fb3e430626837 chr14:20681143-20685051: 2461 rows, 9 CRM interval-links, NA distinct TFs
- c5fcd0fecac75b32d1828efe882832e6 chr14:20681367-20685046: 2461 rows, 9 CRM interval-links, NA distinct TFs
- ff142f32010320c6e443316f1cfafbfd chr14:20681462-20685122: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 47c8dfe485f81f54136deedd50e78007 chr14:20681078-20685082: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 4eda825321460a560d3a25877da19312 chr14:20681091-20685104: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 5bd62d4fb62e16c731ea89b6c77180e4 chr14:20681135-20685043: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 2c55726a3a5a8880d2ce102fe0eccd99 chr14:20681140-20685085: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 83a6a6e9ff702e6c55f9896ca41c8bfd chr14:20681107-20685078: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 9d8d3e44a94e7e2aa4bce73e44dffab4 chr14:20681123-20685068: 2461 rows, 9 CRM interval-links, NA distinct TFs
- ed670496307afc3de2d6e1c74791f8f1 chr14:20681089-20685079: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 9545a87bc4e01b6ef4ca6b224d5f5230 chr14:20681437-20685060: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 817396d6252d2dd8d81aaebb48c1d084 chr14:20681135-20685043: 2461 rows, 9 CRM interval-links, NA distinct TFs
- d6a742ee8cd7741529fb4b039aeccd6e chr14:20681189-20685425: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 3190016b4343dd366b62b3e381a82f57 chr14:20681089-20685079: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 0dd1fddba7f680a3c476205f2c1310e8 chr14:20681152-20685054: 2461 rows, 9 CRM interval-links, NA distinct TFs
- d48e01c770ef3e8d9b5ace1a9d56af35 chr14:20681367-20685046: 2461 rows, 9 CRM interval-links, NA distinct TFs
- a70db70da346bc47472172da348aa86d chr14:20681109-20685074: 2461 rows, 9 CRM interval-links, NA distinct TFs
- da68ed6d5ba44fe67381b668a7faf78e chr14:20681447-20685103: 2461 rows, 9 CRM interval-links, NA distinct TFs
- d8090fa53e4a661e7c75bda916e792ec chr14:20681107-20685078: 2461 rows, 9 CRM interval-links, NA distinct TFs
- abd968e37cc9e5eed28f7cb29f61621c chr14:20681140-20685085: 2461 rows, 9 CRM interval-links, NA distinct TFs
- f7a9cc42b1172d86aee78f5e575fe6a9 chr14:20681143-20685051: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 078c9ab5586747b9d7cb2813ed3c7bb5 chr14:20681459-20685088: 2461 rows, 9 CRM interval-links, NA distinct TFs
- 2ae1ea8c447daf0bad0037a552339f37 chr14:20681109-20685074: 2461 rows, 9 CRM interval-links, NA distinct TFs
- ac72863dd62d1d60854793d46c7ebe35 chr14:20681091-20685104: 2461 rows, 9 CRM interval-links, NA distinct TFs
- cf4da0ee6aa5b3ae370ebb2ad7be3f7e chr14:20681152-20685054: 2461 rows, 9 CRM interval-links, NA distinct TFs
- b098f0aad2db6912408b2a07e065a0db chr14:20681459-20685088: 2461 rows, 9 CRM interval-links, NA distinct TFs

## Endpoint anti-joins / semantic gates
- tf_gene_endpoint_antijoin: 0
- enhancer_endpoint_antijoin: 0
- enhancer_endpoint_antijoin_validation_mode: by_construction_from_duckdb_join_against_canonical_nodes_enhancer_parquet
- summary_type_invalid_rows: 0 (allowed values: `enhancer`, `tf`; `summary_type` is entity kind, not `crm_aggregated_support_compact`)
- summary_type_counts: enhancer=2891253, tf=23877
- observed_binding_rows: 0
- tf_regulates_gene_rows: 0
- support_evidence_type_mismatches: 0
- sample_tf_gene_endpoint_antijoin: 0
- sample_y_ids_present_in_summary: 1
- detailed_rows_materialized: 50000
- no_edges_directory: True
- no_evidence_directory: True
- ok: True

## Limitations / caveats
- CRM rows do not preserve per-experiment source accession.
- CRM column 5 is treated as an aggregated support/count-like score, not a raw per-experiment peak score.
- Sampled CRM rows lack cell/biotype context.
- CRM candidates are support/QA/triage only and must not replace primary observed_binding evidence without reviewer approval.
- This artifact does not infer or write tf_regulates_gene.

## How to use this artifact
- Use `support_candidates/tf_binds_enhancer_crm_support_summary_chr*.parquet` as compact support/QA coverage for TF-gene ↔ enhancer pairs; summary rows use `summary_type` values `enhancer` and `tf` to distinguish aggregate entity kind.
- Use `support_candidates/tf_binds_enhancer_crm_support_detailed_sample.parquet` only as an inspectable row-level sample, not a complete evidence table.
- Use `parsed/crm_tf_symbols_rejected.parquet` and `parsed/crm_tf_symbols_ambiguous.parquet` to review symbol losses before any future policy change.
- Do not promote these rows to canonical `observed_binding` or infer `tf_regulates_gene` without a new explicit reviewer/human approval.

## Non-goals enforced
- canonical_kg_writes: False
- primary_observed_binding_replacement: False
- tf_regulates_gene_written_or_inferred: False
