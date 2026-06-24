# Current TxGNN / Jouvence KG state — 2026-06-23

This is the short current-state anchor for workers. Prefer this plus `todo.d/` over older historical reports.

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

1. `lnschema_txgnn` is locally activated, but must now be made complete/queryable across all KG nodes, edges, evidence, and features. Artifact sync plus node registries alone are not enough.
2. PyG/GNN is not finished until actual PyG/HeteroData is produced and a GNN smoke/training run executes.
3. Embeddings are not finished until real embeddings exist. Use official full UniProt `protein_textual_summary.parquet`; use learned embeddings for missing info; encode edge values/evidence with an MLP/value encoder that aggregates all relevant edges/evidence between the same node pair.
4. ReMap all-peak is stopped/deferred. CRM support/QA pilot is accepted staged-only and now needs a larger/full feasible support-QA artifact with a detailed report. It is not canonical `observed_binding`.
5. Mutation genomic direct status: `mutation_affects_transcript` has been `canonical promoted`/review-accepted by `t_225ae18c` from the accepted all-part OpenTargets 26.03 staged candidate and subsequent independent review; `mutation_in_gene` remains staged/deferred; `mutation_overlaps_enhancer` specifically remains staged/context/feature unless stronger allele-specific regulatory/enhancer-activity evidence is selected by a new policy.
6. Keep `todo.d/` synced with Kanban phases and card IDs.

## Current source-of-truth docs

- `todo.d/README.md` and phase files.
- `docs/kg_schema_overview.md`
- `docs/relation_coverage_current.md`
- `docs/relation_backlog_prioritized.md`
- `docs/kanban_status_hygiene.md`
- `docs/txgnn_access_runbook.md`

## Git / workspace status

- `work/txgnn` is currently a shared artifact workspace, not an independent git checkout. `git -C work/txgnn status` falls back to the parent workspace repo and fails on the incomplete sibling `work/jkobject.github.io/.git`. Use this workspace for artifact/docs stabilization only until a dedicated TxGNN repo/worktree migration is reviewed.
