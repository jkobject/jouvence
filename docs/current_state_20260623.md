# Historical TxGNN / Jouvence KG state — 2026-06-23

> **Historical snapshot — superseded.** This page preserves what the project reported on 2026-06-23; its counters, statuses, workspace paths, and priorities are not maintained as live state. Use root `TODO.md` plus `todo.d/` for the current human mirror and live Kanban for dispatch/status. Do not prefer or copy this page as current operating truth.

## Storage / scratch

- Canonical KG: `gs://jouvencekb/kg/v2`.
- Verified local FUSE: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`.
- New local scratch/cache must use `artifacts/staged/<task-id>/`, `artifacts/cache/<task-id>/`, or `docs/` for reports.
- `.omoc` is retired. New commands, scripts, cards, and docs must target `artifacts/`, `docs/`, or GCS staging instead. If an old active process still targets the legacy path, let it finish, move useful outputs elsewhere, then retire the legacy path.

## Status language

Do not say a phase is “done” unless the intended full artifact exists and has been validated/reviewed. Use explicit qualifiers:

- `design done`
- `pilot accepted`
- `staged-only`
- `review-required`
- `validated`
- `canonical promoted`
- `production/full done`

## Current priorities

1. `lnschema_txgnn` is locally activated, and bounded live KGEdge/KGEdgeEvidence syncs have populated/query-validated 401,291 KGEdge rows and 359,167 KGEdgeEvidence rows in `jkobject/jouvencekb` after Wave-4 producer task `t_b788d863` (`review-required`, not accepted yet). Wave-4 used the reviewed streaming/row-batch Django bulk upsert path for a bounded `enhancer_regulates_gene` continuation window of 250,000 edges plus 250,000 evidence rows, with distinct keys matching rows and selected source/live comparison passing. This is still not production/full done; full exact-ID schema/query coverage across all KG nodes, edges, evidence, and features remains incomplete.
2. PyG/GNN is not finished until actual PyG/HeteroData is produced and a GNN smoke/training run executes.
3. Embeddings are not finished until real embeddings exist. Use official full UniProt `protein_textual_summary.parquet`; use learned embeddings for missing info; encode edge values/evidence with an MLP/value encoder that aggregates all relevant edges/evidence between the same node pair.
4. ReMap all-peak is stopped/deferred. The full/unbounded CRM support/QA sidecar is now `canonical promoted full support sidecar` under `features/remap_crm_tf_enhancer_support_full/` by `t_f2a2952e`, after readiness gate `t_7e356c5c` and reviewer `t_0d77b4f0`; it is 24 chromosome summary shards plus one TF global summary and remains support-only feature/QA material. It is not canonical `observed_binding`, not graph topology, and not `tf_binds_enhancer` edge/evidence. CTO decision `t_2e1b271a` chooses route C: keep full ReMap CRM `support-only` until a stricter reduction policy or explicit external full-materialization authorization exists.
5. Mutation genomic direct status: `mutation_affects_transcript` has been `canonical promoted`/review-accepted by `t_225ae18c`; `mutation_in_gene` has been relation-specific `canonical promoted`/`review-required` by `t_1cfcd48f` from the full all-25-part `t_2bb8e7de` containment-gated candidate using OpenTargets `target.genomicLocation` (2,599,525 edges/evidence/proof rows; live canonical endpoint anti-joins, duplicate/gap/containment/leakage checks pass); `mutation_overlaps_enhancer` has been relation-specific `canonical promoted`/`review-required` by `t_00551bc3` only for the reviewed non-context-support-gated `t_73c67c1b` candidate (1,664,278 edge/evidence rows; live endpoint anti-joins, staged/canonical SHA256 parity, and targeted edge/evidence audit pass). Coordinate overlap alone remains context/support-only and not observed regulatory evidence. See `docs/mutation_overlaps_enhancer_canonical_promotion_t_00551bc3.md`, `docs/mutation_in_gene_canonical_promotion_t_1cfcd48f.md`, `docs/mutation_remaining_next_state_t_8de911c0.md`, and `docs/mutation_in_gene_full_containment_candidate_t_2bb8e7de.md`.
6. Graph policy decision from `t_c07b8b57` plus literature scope follow-up `t_9c86ca89`: `dataset` and `paper` nodes are disconnected from the training/inference graph. Keep them as provenance/catalog metadata only (`source_dataset`, `dataset_id`, `paper_id`, PMID/DOI/source-record metadata, LaminDB/catalog sidecars). Paper/author/citation data, if retained, belongs in a separate `literature_index` namespace/export and not in default biomedical adjacency. Cleanup promotion `t_d97c4547` selected the reversible retain-with-labels path after backup gate `t_9ad833bf`: canonical `nodes/dataset.parquet`, `nodes/paper.parquet`, `edges/dataset_contains_cell_line.parquet`, and `edges/dataset_contains_tissue.parquet` remain in place as metadata-only/non-training inventory, with policy sidecars at `gs://jouvencekb/kg/v2/metadata/dataset_paper_graph_policy_t_d97c4547.{json,md}`. PyG/HeteroData export excludes `dataset`/`paper` node types and any relation touching them by default. See `docs/dataset_paper_graph_disconnection_t_c07b8b57.md` and `docs/literature_metadata_policy_t_9c86ca89.md`.
7. Keep `todo.d/` synced with Kanban phases and card IDs.
8. ClinicalTrials.gov status from `t_957a3640`: structured trial fields and trial text summaries/outcomes/eligibility/why_stopped are `canonical promoted` sidecar metadata/features (`metadata/clinical_trials_gov_trial_index.parquet`, `metadata/molecule_treats_disease_clinical_trials_gov_trial_links.parquet`, `features/clinical_trials_gov_trial_text_features.parquet`, and clinical-trial support in `evidence/molecule_treats_disease.parquet`), not clinical-trial graph nodes and not default PyG topology. The full 6,092-row HashingVectorizer trial-text table is `canonical promoted fallback sidecar` under `features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/full_staged_fallback_v1/`; foundation clinical text embeddings remain `blocked-with-resource` until a reviewed encoder/runtime/model is pinned and run.

## Current source-of-truth docs

- `todo.d/README.md` and phase files.
- `docs/kg_schema_overview.md`
- `docs/relation_coverage_current.md`
- `docs/relation_backlog_prioritized.md`
- `docs/kanban_status_hygiene.md`
- `docs/txgnn_access_runbook.md`
- `docs/dataset_paper_graph_disconnection_t_c07b8b57.md`
- `docs/literature_metadata_policy_t_9c86ca89.md`

## Git / workspace status

- `work/txgnn` is currently a shared artifact workspace, not an independent git checkout. `git -C work/txgnn status` falls back to the parent `/Users/jkobject/.openclaw/workspace` repo; current validation shows status exits 0 and reports parent workspace dirt/untracked files. The previously cited sibling `work/jkobject.github.io/.git` and `work/flow-matching-diracs/.git` paths are absent, while `work/pert-gym/.git` and `work/river/.git` are directories. Use this workspace for artifact/docs stabilization only until a dedicated TxGNN repo/worktree migration is reviewed.
