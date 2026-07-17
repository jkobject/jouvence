# ReMap/CRM motif co-location evidence layer

Kanban task: `t_ea6e00ab`  
Status: `review-required`; staged-only; no canonical KG writes.

## Summary

A bounded real motif co-location evidence layer was built for the accepted ReMap CRM/peak `tf_binds_enhancer` pilot lineage. No local motif hit tables were present in the workspace, so this task used public JASPAR 2026 CORE vertebrate non-redundant PFMs and scanned bounded hg38 enhancer/CRM intersection intervals fetched from the UCSC sequence API.

The output is evidence/feature sidecar material only. Motif support can strengthen ReMap observed ChIP evidence for the same canonical TF gene and enhancer, but motif-only rows are explicitly predicted/support rows and must not create active `tf_binds_enhancer` graph edges.

## Inputs

- Parent observed evidence: `artifacts/staged/t_a405fe3b/evidence/tf_binds_enhancer.parquet`
- Parent CRM/peak prototype: `artifacts/staged/t_f558cee3/support_candidates/`
- Canonical KG endpoints: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/nodes/{gene,enhancer}.parquet`
- Motif source: `https://jaspar.elixir.no/download/data/2026/CORE/JASPAR2026_CORE_vertebrates_non-redundant_pfms_jaspar.txt`
- Sequence source for this bounded scan: `https://api.genome.ucsc.edu/getData/sequence`, hg38

## Outputs

- Builder: `artifacts/staged/t_ea6e00ab/build_remap_crm_motif_colocation.py`
- Motif evidence: `artifacts/staged/t_ea6e00ab/evidence/tf_binds_enhancer_motif_colocation.parquet`
- Motif→gene mapping: `artifacts/staged/t_ea6e00ab/features/jaspar2026_motif_tf_gene_mapping.parquet`
- Bounded parent candidates: `artifacts/staged/t_ea6e00ab/features/bounded_parent_observed_candidates.parquet`
- Report: `artifacts/staged/t_ea6e00ab/reports/remap_crm_motif_colocation_report.json`
- Human report: `artifacts/staged/t_ea6e00ab/reports/remap_crm_motif_colocation_report.md`
- Independent validation: `artifacts/staged/t_ea6e00ab/reports/remap_crm_motif_colocation_independent_validation.json`

## Counts

- JASPAR motifs parsed: 1,019
- Motif mapping rows: 1,019
- Motif mapping status counts: 996 `accepted_unique_ensg`, 18 `rejected_no_gene_symbol_match`, 3 `ambiguous_multi_ensg`, 2 `ambiguous_multi_id`
- Parent candidate rows scanned: 69 across 6 CRM intervals and 31 observed TF symbols
- Motif evidence rows: 549
- `motif_support` rows linked to parent observed ReMap evidence: 440
- Motif-only predicted/support rows: 109
- Distinct matched TFs in hits: 28
- Distinct motif models hit: 30

## Validation

Independent validation in `artifacts/staged/t_ea6e00ab/reports/remap_crm_motif_colocation_independent_validation.json` reports:

- Required fields present: `motif_source`, `motif_id`, `motif_name`, `matched_tf`, `mapped_gene_id`, `coordinates`, `overlap_policy`, `score`, `pvalue`, `source_release`, `leakage_caveat`, `motif_only_candidate`, `evidence_type`, `predicate`, `supported_observed_evidence_id`
- `motif_support_rows`: 440
- `motif_only_rows`: 109
- `motif_only_edge_key_non_null`: 0
- `support_missing_observed_link`: 0
- `observed_binding_rows`: 0
- `tf_regulates_gene_rows`: 0
- `null_mapped_gene_id_rows`: 0
- Overall `ok`: true

## Policy integration

Use this as a staged support/evidence layer for ReMap-derived `tf_binds_enhancer`, not as canonical graph topology.

- Motif support row semantics: `evidence_type=motif_support`, `predicate=motif_supports_observed_binding`, and `supported_observed_evidence_id` points to the parent ReMap observed evidence row.
- Motif-only row semantics: `evidence_type=motif_predicted_support`, `predicate=motif_matches_enhancer`, `motif_only_candidate=True`, and `edge_key=NULL`; these rows cannot create active edges.
- Overlap policy: same canonical TF gene, same enhancer, hg38 motif scan on enhancer/CRM intersection, and support requires motif hit overlapping the ReMap peak by at least 1 bp or motif center inside the peak.
- Leakage caveat: exclude ReMap/CRM/motif regulatory evidence from supervised labels for `tf_binds_enhancer`, `enhancer_regulates_gene`, disease/drug prediction, or any target constructed from overlapping regulatory evidence unless a split policy explicitly prevents leakage.

## Scalable policy proposal

1. Promote motif support as a sharded feature/evidence sidecar first, partitioned by chromosome and motif source release.
2. Use JASPAR/HOCOMOCO/ENCODE motif tracks only when genome build, threshold semantics, motif version, and TF mapping are explicit.
3. Require same canonical TF gene + same enhancer + motif/peak overlap for support of observed ReMap evidence.
4. Keep motif-only hits as predicted/support rows with no active edge until a reviewer accepts an inferred-binding policy.
5. Before scaling, replace API sequence fetches with local/reference FASTA streaming and record scanner/version/threshold calibration.

## Residual risks

- This is a bounded scanner pilot, not a calibrated production motif caller.
- P-values are null because the local scanner uses a relative PSSM threshold. A production scanner should emit reviewed p-value/FPR semantics or consume official hit tracks with documented thresholds.
- JASPAR motif-name to TF mapping is exact/single-token in this pass. Family, heterodimer, and alias mappings are counted/rejected or left unexpanded until policy review.
- HOCOMOCO and ENCODE motif hits were identified as possible sources but not consumed because no local hit table was present and the bounded task selected one real source for materialization.
