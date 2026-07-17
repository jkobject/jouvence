# ReMap CRM/peak `tf_binds_enhancer` staged pilot

Kanban task: `t_a405fe3b`  
Status: `review-required`; staged-only; no canonical KG writes.

## Scope

This pilot materializes the corrected ReMap CRM/peak evidence policy for `tf_binds_enhancer` using the bounded parent prototype from `artifacts/staged/t_f558cee3`:

- parent input: `artifacts/staged/t_f558cee3/support_candidates/crm_to_all_peak_overlap_sample.parquet`
- bounded scope: first 80 chr1 CRM intervals from the parent prototype
- active edge criterion: same TF gene and same accepted enhancer interval must have both ReMap all-peak observed binding support and CRM reconstructed binding support
- motif support: not materialized; no local motif hit table was available
- motif-only active edges: 0
- canonical writes: false

## Outputs

- edges: `artifacts/staged/t_a405fe3b/edges/tf_binds_enhancer.parquet`
- evidence: `artifacts/staged/t_a405fe3b/evidence/tf_binds_enhancer.parquet`
- validation JSON: `artifacts/staged/t_a405fe3b/reports/validation_report.json`
- markdown report: `artifacts/staged/t_a405fe3b/reports/remap_crm_tf_binds_enhancer_pilot_report.md`
- build script: `artifacts/staged/t_a405fe3b/build_remap_crm_tf_binds_enhancer_pilot.py`

## Counts

- parent all-peak overlap rows: 6,876
- edge rows: 1,224,536
- evidence rows: 6,356,561
- distinct TF genes: 564
- distinct enhancers: 6,814
- evidence rows with `observed_binding_peak`: 5,053,011
- evidence rows with `crm_reconstructed_binding_support`: 1,303,550
- evidence rows with `motif_support`: 0

## Validation summary

All targeted validation gates passed in `artifacts/staged/t_a405fe3b/reports/validation_report.json`:

- duplicate active edges: 0
- duplicate evidence IDs: 0
- duplicate source-record/edge/evidence-type rows: 0
- TF gene endpoint anti-join: 0
- enhancer endpoint anti-join: 0 by construction from the builder join against canonical `nodes/enhancer.parquet`
- evidence without edge: 0
- edge without evidence: 0
- active edges without `observed_binding_peak`: 0
- active edges without `crm_reconstructed_binding_support`: 0
- motif-only active edges: 0
- unexpected evidence types: 0
- `tf_regulates_gene` rows: 0
- mixed/null genome build rows: 0

## Metadata/context coverage

- observed ReMap source accession present on observed-binding evidence rows: 5,053,011
- observed ReMap biotype present on observed-binding evidence rows: 5,053,011
- ReMap biotype description present: 1,921,075 rows
- antibody target/ID/lot coverage: 0 rows; fields are nullable because inspected ReMap BED rows do not expose antibody metadata
- protein accession coverage: 0 rows; fields are nullable because inspected ReMap BED rows do not expose protein accession metadata
- CRM-to-peak link policy: `reconstructed_coordinate_overlap_same_tf` for all evidence rows
- genome build: `GRCh38/hg38`

## Residual risks

- This is a bounded pilot, not a full production ReMap/CRM table.
- CRM-to-peak linkage is reconstructed from same TF symbol plus coordinate overlap; CRM rows do not carry source-recorded peak foreign keys.
- Antibody/protein metadata remains unavailable from the inspected ReMap BED rows.
- Motif support remains future work because no local motif hit table was available.
- Canonical enhancer node density produces many TF-enhancer rows for overlapping enhancer records; full-scale promotion should evaluate biological duplicate intervals and leakage policy before canonical writes.

## Recommendation

Accept or reject this staged schema/counts in independent review. If accepted, create a separate full-scale builder/tester/reviewer pipeline that streams all selected CRM/peak evidence with the same support gates and still performs no canonical write until reviewer approval.
