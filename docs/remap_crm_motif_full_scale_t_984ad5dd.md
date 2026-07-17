# ReMap/CRM motif co-location full-scale shard manifest

Task: `t_984ad5dd`  
Status: `review-required`; staged-only; no canonical writes.

## Verdict

Full CRM/motif/support inputs were discovered and converted into a 24-chromosome shard/resume manifest, but full motif evidence was not materialized because required full-scale sequence/motif-hit and TF×CRM×enhancer link inputs are absent locally. This is intentionally not a repeat of the bounded pilot and not a silent partial scan.

## Full input counts

- Full CRM BED intervals: 3,327,980
- CRM regulator assignments: 67,317,307
- Distinct CRM regulators: 1,210
- Canonical full support sidecar rows: 48,768,788
- TF global summary rows: 1,179
- JASPAR motif mapping rows: 1,019
- Accepted pilot motif rows retained as bounded evidence: 549

## Outputs

- Shard scope parquet: `artifacts/staged/t_984ad5dd/features/remap_crm_motif_full_scan_scope_by_chromosome.parquet`
- Resume plan: `artifacts/staged/t_984ad5dd/reports/remap_crm_motif_full_scan_resume_plan.tsv`
- Manifest: `artifacts/staged/t_984ad5dd/manifests/remap_crm_motif_full_scale_manifest.json`
- JSON report: `artifacts/staged/t_984ad5dd/reports/remap_crm_motif_full_scale_report.json`
- Human report: `artifacts/staged/t_984ad5dd/reports/remap_crm_motif_full_scale_report.md`
- Query examples: `artifacts/staged/t_984ad5dd/reports/query_examples.sql`
- Builder/discovery script: `artifacts/staged/t_984ad5dd/build_remap_crm_motif_full_scale_manifest.py`

## Input hashes / provenance

The JSON report and manifest include SHA256 hashes and row counts for the discovered inputs and outputs. Key input hashes:

- Full CRM BED `artifacts/staged/t_b599d3bb/full_local/source_cache/remap2022_crm_selected.bed`: `22f6fac5c1be237a3f46f720d348734b3ee261e8b1c8856b2d262957cfc60619`
- Canonical full support sidecar manifest `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/remap_crm_tf_enhancer_support_full/manifest.json`: `f186889ea43fa0e67c0f83be7123c700b240904d54039c744624316cd5dee765`
- Accepted bounded motif evidence `artifacts/staged/t_ea6e00ab/evidence/tf_binds_enhancer_motif_colocation.parquet`: `525f8345c87c1d6e3cfa572f258cc7d8410c060481432fae6ba800165a250b65`

## Blocker / resume plan

No local hg38 FASTA/twoBit or reviewed genome-wide motif hit track exists in the workspace; the pilot's UCSC per-interval API path is not acceptable for 3,327,980 CRM intervals. The canonical full support sidecar is aggregate support-only material and has no per TF-enhancer links, so motif rows cannot honestly be promoted to TF-enhancer evidence without either CRM BED + enhancer overlap expansion or a reviewed aggregate/link policy.

Resume by chromosome with a local indexed hg38 reference or reviewed motif-hit track, row-group checkpoints, and a reviewed TF×CRM×enhancer link policy. All resulting rows must remain support-only until tester+reviewer approval.

## Validation

Commands run:

```bash
uv run python artifacts/staged/t_984ad5dd/build_remap_crm_motif_full_scale_manifest.py
uv run python -m py_compile artifacts/staged/t_984ad5dd/build_remap_crm_motif_full_scale_manifest.py
uv run python - <<'PY'
import duckdb
p='artifacts/staged/t_984ad5dd/features/remap_crm_motif_full_scan_scope_by_chromosome.parquet'
con=duckdb.connect()
print(con.execute(f"select count(*) as rows, sum(crm_interval_rows) as crm_rows, sum(sidecar_summary_rows) as sidecar_rows, sum(crm_regulator_assignments) as regulator_assignments from read_parquet('{p}')").fetchdf().to_string(index=False))
PY
```

Observed validation summary:

```text
rows=24
crm_rows=3,327,980
sidecar_rows=48,768,788
regulator_assignments=67,317,307
all_24_chromosome_shards_represented=true
full_crm_bed_rows_match_reviewed_count=true
sidecar_summary_rows_match_reviewed_count=true
no_canonical_writes=true
full_motif_evidence_materialized=false
```

## Semantics

This task produced a full-scale input/shard/resume artifact, not active graph topology. It preserves support-only semantics:

- relation under review: `tf_binds_enhancer`
- support semantics: `support_only_motif_colocation;not_observed_binding;not_graph_edge`
- no canonical writes
- no `edges/tf_binds_enhancer.parquet` write
- no `evidence/tf_binds_enhancer.parquet` write
- no motif-only inferred edges
