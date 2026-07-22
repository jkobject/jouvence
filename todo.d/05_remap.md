# 05 — ReMap

_Status snapshot: 2026-07-22 15:18 CEST._

Heavy-job guardrail: ReMap scaling, full/unbounded CRM/peak work, and large support/evidence materialization must run on `txgnn-worker` or another explicitly approved in-region worker with source `gs://jouvencekb/kg/v2`. Do not run heavy ReMap reads/writes from the Mac through `/Users/jkobject/mnt/gcs/...` / macOS GCS-FUSE. Future cards must include `must_run_on=txgnn-worker`, `hostname` and `gcloud compute ssh` preflight, an existing-process check, and a fail-fast guard for paths starting `/Users/jkobject/mnt/gcs`.

## Current state

ReMap is complete for the currently accepted route C: bounded and full canonical CRM feature-context sidecars are independently accepted. Converting them into active full `tf_binds_enhancer` graph topology is a policy-deferred non-goal, not unfinished ReMap execution.

- `t_8bc6dacf` — stopped by user strategy decision; not canonical; do not auto-resume.
- No canonical `tf_binds_enhancer` edge/evidence exists yet, but the approved ontology direction is to use `tf_binds_enhancer` for ReMap CRM/peak/motif-supported TF-enhancer binding evidence rather than inventing a permanent support-only relation label.

Accepted support-only artifacts:

- `t_3b8a2c4d` — CRM support/QA first10k chr1 `pilot accepted`/`staged-only`.
- Prefix: `gs://jouvencekb/kg/staging/source-native-expansion/remap-crm-tf-binds-enhancer-support-chr1-first10k-20260623-t_3b8a2c4d/`
- `t_b599d3bb` — CRM support/QA all-chromosome bounded 5k-per-chrom artifact accepted as staged-only/support-only.
- Prefix: `gs://jouvencekb/kg/staging/source-native-expansion/remap-crm-tf-binds-enhancer-support-allchrom-5kperchrom-20260623-t_b599d3bb/all_chrom_5k_per_chrom/`
- `t_656a1102` / reviewer `t_69fa9b1d` — bounded canonical CRM feature-context sidecar accepted `validated`.
- `t_f2a2952e` / reviewer `t_0974375e` — full/unbounded sharded canonical CRM feature-context sidecar accepted `validated` after readiness gate `t_7e356c5c`.
- Prefix: `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/` with 24 chromosome summary shards, `tf_global_summary.parquet`, `manifest.json`, and `metadata.json`; see `docs/remap_crm_full_support_sidecar_canonical_promotion_t_f2a2952e.md`.
- Semantics: `crm_aggregated_support` / support-QA only.
- Not `observed_binding`; not `tf_regulates_gene`; not canonical `tf_binds_enhancer` edge/evidence.

## Canonical-readiness decision

- `t_9c0e6a68` — decision doc: `docs/remap_crm_canonical_readiness.md`.
- `t_f558cee3` — reassessment/prototype update: CRM support can be linked back to ReMap ChIP-seq peak rows by reconstructed same-TF coordinate overlap, but CRM itself still lacks source peak IDs, experiment accessions, antibody/protein metadata, and cell/biotype context.
- Bounded prototype: `artifacts/staged/t_f558cee3/reports/remap_crm_peak_decomposition_prototype_report.md` over first 80 chr1 CRM intervals found 6,876 same-TF ReMap `all` peak overlaps, 1,846 distinct source accessions, 1,421 distinct biotypes, and ReMap biotype XLSX metadata matches for 230 sample biotypes.
- The existing canonical feature sidecar remains useful as a bounded QA/support artifact and must not be overwritten by this reassessment.
- User policy correction: CRM is derived from ReMap ChIP-seq, so the strongest honest graph target is canonical `tf_binds_enhancer` with caveats encoded in `evidence/tf_binds_enhancer`, not a support-only replacement relation.
- A new bounded staged candidate is justified: active `tf_binds_enhancer` rows should use ReMap `all` peak evidence where available and may use CRM-derived reconstructed binding support when the evidence row records the reconstruction policy, missing CRM-native peak foreign key, metadata coverage, motif support, context fields, and leakage guard.
- `tf_regulates_gene` is blocked from the CRM support artifact. It requires a separate source-native TF→target regulation source or an explicitly reviewed inferred-relation policy.

## Policy-deferred topology non-goal

- Keep the existing promoted bounded `features/remap_crm_tf_enhancer_support.parquet` as a `crm_aggregated_support` feature/QA sidecar; it was not overwritten by the full sidecar promotion.
- Fresh-UDC continuation operations policy (`t_a2674d49`): foreground cards should use `--max-tiles 5`; larger bounded continuations require a supervisor/background pattern with heartbeat/progress JSON, stdout/stderr/rc capture, task-local fresh UDC, and canonical-negative validation/enforcement. Use `artifacts/reports/t_a2674d49/remap_fresh_udc_supervisor.py` / `artifacts/reports/t_a2674d49/remap_supervisor_plan.md` as the reusable local template. Never use the old suspected-corrupt `artifacts/cache/t_1bc29376/udc` cache; relative, absolute, and descendant spellings are supervisor-rejected after path normalization. Full/unbounded caps (`--max-tiles >= 3220`, including `3220`) are rejected unless `--reviewed-full-run-override` is supplied after a separate reviewed operations gate; do not use the override for normal bounded continuations.
- Treat `features/remap_crm_tf_enhancer_support_full/` as shard-aware support-only feature/QA material, not graph topology and not a replacement for `tf_binds_enhancer` edge/evidence promotion.
- `t_6c07d9c8` — shard-aware read-only helper added at `manage_db/remap_crm_support_reader.py` with fixture tests in `tests/test_remap_crm_support_reader.py`. Use it to list the 24 canonical shards, read bounded TF/enhancer samples from one chromosome, read `tf_global_summary.parquet`, and run bounded endpoint checks over loaded samples. Live FUSE readback report: `artifacts/reports/t_6c07d9c8_remap_crm_support_reader_live_readback.json`. Semantics remain support-only feature/QA material, not edge/evidence/observed binding/inferred topology.
- `t_a405fe3b` / reviewer `t_95856c15` — bounded first80 chr1 CRM/peak `tf_binds_enhancer` edge/evidence pilot is `pilot accepted` / `staged-only` with 1,224,536 edges and 6,356,561 evidence rows. It is not canonical/full production.
- `t_f8cc9e4b` — full/unbounded CRM/peak edge/evidence scaling is a validated feasibility/policy gate. Existing accepted full CRM lineage `t_5968ce32` reports 24,453,482,386 TF × CRM × enhancer candidate support rows intentionally not materialized; converting it into active `tf_binds_enhancer` edges/evidence would require either reviewed aggregate-reduction semantics or explicit external large-product materialization approval. See `docs/remap_crm_tf_binds_enhancer_full_feasibility_t_f8cc9e4b.md` and `artifacts/reports/t_f8cc9e4b_feasibility_gate.json`.
- `t_2e1b271a` — accepted route C: full ReMap CRM stays feature-context material; do not create full edge/evidence build work, silently aggregate the sidecar into graph topology, or claim canonical `tf_binds_enhancer` edge/evidence promotion without a superseding policy decision. Decision doc: `docs/remap_crm_tf_binds_enhancer_next_decision_t_2e1b271a.md`.
- `t_ea6e00ab` — bounded motif co-location layer for ReMap/CRM `tf_binds_enhancer` support is `review-required` / `staged-only`. It scans real JASPAR 2026 CORE vertebrate PFMs on bounded hg38 enhancer/CRM intersections from the accepted `t_a405fe3b`/`t_f558cee3` lineage and writes 549 motif rows: 440 `motif_support` rows linked to parent ReMap observed evidence plus 109 motif-only predicted/support rows with `edge_key=NULL`. Artifact/report: `artifacts/staged/t_ea6e00ab/` and `docs/remap_crm_motif_colocation_t_ea6e00ab.md`. No canonical writes.
- `t_ba65eb81` — compact-coded ReMap/CRM `tf_binds_enhancer` support prototype is `review-required` / `staged-only`. It supersedes treating the 24.45B TF×CRM×enhancer count as a final blocker: that count is the naive exploded row product, while the intended representation stores per-enhancer `support_codes: list<int64>` arrays plus a support-code dictionary mapping each code to TF/source/accession/biotype/antibody/protein/context/motif/evidence metadata. Prototype artifacts: `artifacts/staged/t_ba65eb81/features/tf_binds_enhancer_enhancer_support_codes.parquet`, `artifacts/staged/t_ba65eb81/features/tf_binds_enhancer_support_code_dictionary.parquet`, `artifacts/staged/t_ba65eb81/reports/query_examples.sql`, and `docs/remap_compact_coded_tf_binds_enhancer_t_ba65eb81.md`. Query examples now explicitly cover enhancer→TFs, TF→enhancers, support_class, motif, direct cell_line/tissue/cell_type/antibody/protein predicate shapes, and report zero direct-slot coverage with ReMap biotype/context_note fallback coverage. No canonical writes; active training edges require a later reviewed reducer/leakage policy.
- Do not create a separate support-only relation label unless a future reviewer explicitly needs a non-label namespace; the default relation name for this evidence family is `tf_binds_enhancer` when edge/evidence semantics are reviewed and accepted.
- No canonical writes should happen in ReMap readiness/scaling cards without a separate positive reviewer gate.

## Accepted route-C boundary

The accepted ReMap route is done at canonical feature-context scope: bounded and full sidecars are independently accepted and queryable. Active full `tf_binds_enhancer` edge/evidence topology is outside this accepted scope and remains policy-deferred; any future topology lane requires an explicit superseding decision, reducer/leakage policy, and separate review.
