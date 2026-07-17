# mutation_affects_transcript canonical promotion — t_225ae18c

Date: 2026-06-23  
Producer/staged source: `t_f32f1f5b`, accepted by reviewer chain `t_50c511c6` after repair `t_2487be68`, validation `t_fad51349`, and repair review `t_9c37cb82`.  
Status: `canonical promoted` / `review-required`.

## Scope

Promoted only `mutation_affects_transcript` from `artifacts/staged/t_f32f1f5b_sql` to canonical KG root `gs://jouvencekb/kg/v2` / `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`.

No `mutation_in_gene` or `mutation_overlaps_enhancer` artifacts were promoted. Those relations remain staged/deferred according to their current policy/review status.

## Canonical objects

- `gs://jouvencekb/kg/v2/edges/mutation_affects_transcript.parquet`
  - FUSE: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/edges/mutation_affects_transcript.parquet`
  - rows: 2,599,922
  - size: 20,266,519 bytes
  - sha256: `782c1ad95f79e2c2f0a0ed754095ba1c4db8880086a64a88f13c7085b4f32251`
  - GCS generation: `1782244419732373`
  - GCS CRC32C: `GuUaHw==`
  - GCS MD5: `/37msg3JvBxsQucaRBrVng==`
- `gs://jouvencekb/kg/v2/evidence/mutation_affects_transcript.parquet`
  - FUSE: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/evidence/mutation_affects_transcript.parquet`
  - rows: 2,599,922
  - size: 199,510,540 bytes
  - sha256: `90f363d90b02b06f39d08738b6226c677e59a151e219306e5d454bc1195f2d27`
  - GCS generation: `1782244424766297`
  - GCS CRC32C: `hcDMOA==`
  - GCS note: uploaded as a 4-component composite object; use CRC32C/GCS-aware clients for integrity checks.

## Validated counts

Post-write canonical validation report: `artifacts/reports/t_225ae18c_postwrite_validation.json`.

- edge rows: 2,599,922
- evidence rows: 2,599,922
- distinct mutation x IDs: 2,312,815
- distinct transcript y IDs: 40,939
- duplicate edge keys: 0
- mutation endpoint anti-joins: 0
- transcript endpoint anti-joins: 0
- edge/evidence support gaps: 0 / 0
- malformed evidence JSON rows: 0
- noncanonical transcript evidence rows: 0
- disallowed or null SO evidence rows: 0
- L2G/GWAS leakage rows: 0
- staged/canonical size mismatches: 0
- staged/canonical sha256 mismatches: 0

## Commands run

```bash
uv run python artifacts/reports/t_f32f1f5b_qa_mutation_affects_transcript_sql.py
uv run python artifacts/reports/t_2487be68_revalidate_mutation_affects_transcript_after_fix.py
uv run python -m manage_db.audit_edge_evidence artifacts/staged/t_f32f1f5b_sql --relations mutation_affects_transcript --json --fail-on-missing > artifacts/reports/t_225ae18c_preflight_stage_edge_evidence_audit.json
uv run python -m py_compile artifacts/reports/t_f32f1f5b_build_mutation_affects_transcript_sql.py artifacts/reports/t_f32f1f5b_qa_mutation_affects_transcript_sql.py artifacts/reports/t_2487be68_revalidate_mutation_affects_transcript_after_fix.py
uv run --group dev pytest tests/test_build_staged_mutation_genomic_edges.py -q

gcloud storage cp artifacts/staged/t_f32f1f5b_sql/edges/mutation_affects_transcript.parquet gs://jouvencekb/kg/v2/edges/mutation_affects_transcript.parquet
gcloud storage cp artifacts/staged/t_f32f1f5b_sql/evidence/mutation_affects_transcript.parquet gs://jouvencekb/kg/v2/evidence/mutation_affects_transcript.parquet

uv run python artifacts/reports/t_225ae18c_postwrite_validate_mutation_affects_transcript.py
uv run python -m manage_db.audit_edge_evidence /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 --relations mutation_affects_transcript --json --fail-on-missing > artifacts/reports/t_225ae18c_postwrite_canonical_edge_evidence_audit.json
```

Relevant outputs:

- preflight QA passed with 2,599,922 edge rows and 2,599,922 evidence rows.
- target absence was confirmed before write: both canonical edge/evidence files were absent.
- `tests/test_build_staged_mutation_genomic_edges.py`: 3 passed.
- canonical `manage_db.audit_edge_evidence` passed: 2,599,922 edges, 2,599,922 evidence rows, 0 edges without evidence, 0 evidence without edge.

## Residual risks / review notes

- Independent review is still required before this promotion is treated as fully accepted in project status language.
- The canonical evidence object was uploaded by `gcloud storage cp` with parallel composite upload enabled; GCS metadata lacks an MD5 for that object and reports `Component-Count: 4`, but staged and FUSE canonical sha256 values match exactly.
- Remaining relations are resolved separately by `docs/mutation_remaining_next_state_t_8de911c0.md` and the later `docs/mutation_in_gene_canonical_promotion_t_1cfcd48f.md`: `mutation_in_gene` is now relation-specific `canonical promoted`/`review-required` after live endpoint revalidation and proof-preserving canonical write; `mutation_overlaps_enhancer` is context/support feature-only unless a stronger regulatory-evidence policy is approved.
