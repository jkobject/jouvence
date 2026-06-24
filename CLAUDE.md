# TxGNN / Jouvence KG — agent boot context

## Project

TxGNN is a Python ML research library for zero-shot drug repurposing on a heterogeneous biomedical KG. This repo is being expanded into the Jouvence KG with OpenTargets, HPA, TxData, source-backed evidence, LaminDB cataloging, PyG/GNN export, and learned/foundation embeddings.

## Current operating posture — 2026-06-23

Do **not** treat old `.omoc` paths as current operating instructions. Historical reports may mention `.omoc`, but new workers should use the bucket/FUSE, `artifacts/`, and `docs/` paths below.

Use `docs/current_state_20260623.md` and `todo.d/` as the current-state anchors for workers and reviewers.

Default KG access:

- Canonical KG bucket root: `gs://jouvencekb/kg/v2`.
- Verified macOS FUSE root: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`.
- Use GCS/FUSE as source of truth; do not create repo-local legacy cache directories.
- If local scratch is unavoidable, use `artifacts/staged/<task-id>/`, `artifacts/cache/<task-id>/`, or `docs/` for reports. Large staged artifacts go to `gs://jouvencekb/kg/staging/...`.
- `.omoc/` is legacy-only. If an old active process writes there, do not delete mid-run; after it finishes, preserve useful outputs elsewhere and clean `.omoc`.

Python / tools:

- Python is managed with `uv`; run commands as `uv run ...`.
- Active LaminDB instance: `jkobject/jouvencekb`.
- `lnschema_txgnn` is locally activated for `jkobject/jouvencekb`; remaining work is full/queryable exact-ID schema coverage across KG nodes, edges, evidence, and features.

## Git / reviewability caveat

This directory is currently a shared artifact workspace, not an independent git checkout: no `.git` exists under `work/txgnn`, so `git -C work/txgnn ...` falls back to the parent `/Users/jkobject/.openclaw/workspace` repo. Parent status is currently broken by invalid nested `.git` directories in sibling workspace projects.

Decision from `t_4cab4a2f`: use the existing GitHub repo `https://github.com/jkobject/TxGNN` for reviewable TxGNN code/docs. Future PR-ready work should happen in `/Users/jkobject/.openclaw/worktrees/txgnn/<branch-or-task-id>/` or a canonical clone of that repo, then be reviewed by PR. Treat this `work/txgnn` directory as a shared artifact workspace until the migration in `docs/git_reviewability_migration_t_4cab4a2f.md` is executed and reviewed. Do not `git init` here and do not claim PR-ready diffs from this directory.

## Current KG source of truth

Approved current relation coverage docs:

- `docs/kg_schema_overview.md`
- `docs/relation_coverage_current.md`
- `notebooks/kg_schema_overview.ipynb`
- `docs/relation_backlog_prioritized.md`

Accepted relation coverage snapshot:

- active declared relations: `67`
- canonical active edge relations: `37`
- canonical relations with evidence files: `15`
- canonical relations without evidence files: `22`
- declared relations not canonical yet: `30`
- staged-only/deferred: `20`
- source-audit-only/deferred: `2`
- feature-context-not-edge: `2`
- schema-only/missing: `6`
- canonical edge rows: `94,880,924`
- node files / rows: `15 / 55,523,691`

Current official feature layer has 12 feature tables including full UniProt `protein_textual_summary.parquet` and `molecule_fingerprint.parquet`; use `docs/node_feature_tables_official_promotion_report.md`, `docs/missing_node_feature_tables_official_promotion_report.md`, and `docs/protein_textual_summary_official_promotion_report.md` for details.

## What is not finished yet

Be precise in summaries. Do not call these “done” without qualifiers:

- **LaminDB**: artifact registry sync is implemented/reviewed and `lnschema_txgnn` is locally activated; schema/query coverage is still incomplete until exact-ID registries cover nodes, edges, evidence, and features and pass validation/review.
- **PyG/GNN**: bounded PyG export pilot exists; not complete until an actual PyG/HeteroData object and GNN smoke/training run execute.
- **Embeddings**: policies and surrogate pilot exist; not complete until real embeddings are created. Use official UniProt text where applicable, learned embeddings for missing node/edge info, and an edge/evidence value encoder/MLP per corrected policy.
- **ReMap**: all-peak observed-binding is stopped/deferred. CRM support/QA pilot is accepted staged-only; it must be scaled/report-reviewed before being treated as useful support artifact. It is not canonical `observed_binding`.
- **Mutation genomic direct relations**: `mutation_affects_transcript` is `canonical promoted`/review-accepted from the all-part OpenTargets 26.03 candidate; `mutation_in_gene` remains staged/deferred; `mutation_overlaps_enhancer` remains staged/context/feature-only unless a new stronger regulatory-evidence policy is accepted.

Use `todo.d/` as the lightweight human mirror of Kanban phases and definitions of done.

## Modeling doctrine

- Relation names must match source-native assertion and endpoint type.
- Gene-level rows stay in gene relations (`molecule_targets_gene`, `gene_interacts_gene`, `pathway_contains_gene`); split to protein/TF/transcript only when the source is native to those endpoints/assertions.
- Directed disease associations use cause/source → disease endpoints (`disease_associated_gene` is gene→disease).
- Protein relations are only for direct protein/isoform evidence or direct protein measurement; never project RNA/gene rows into protein edges.
- Molecule pair drug-effect rows use `molecule_synergizes_molecule`; physical molecular interactions use explicit interaction relations only when source-native.
- Entity→phenotype is canonical direction (`gene_associated_phenotype`, `molecule_associated_phenotype`, `mutation_associated_phenotype`); evidence rows carry the specific predicate/class.
- Edges are deduplicated graph assertions; evidence rows carry source-specific predicates, scores, papers, studies, assays, and provenance.
- Do not create placeholder Parquets just to satisfy schema coverage.

## Status vocabulary

Use explicit labels:

- `design done`: doc/policy exists; no production artifact implied.
- `pilot accepted`: bounded pilot reviewed; not full scale.
- `staged-only`: artifact exists outside canonical KG; no canonical promotion.
- `review-required`: producer blocked pending independent review.
- `validated`: tester checked behavior/counts/endpoints/artifacts.
- `canonical promoted`: reviewed artifact written to canonical `gs://jouvencekb/kg/v2/...`.
- `production/full done`: full intended scope exists and runs.

## Validation / promotion gates

Before promoting a KG tranche:

1. Build in `artifacts/staged/<task-id>/` or GCS staging, not `.omoc`.
2. Validate x/y endpoint anti-joins with DuckDB/PyArrow against the canonical FUSE/GCS root.
3. Write evidence rows when source provenance exists.
4. Run `manage_db.audit_edge_evidence` for edge/evidence support when applicable.
5. Update coverage docs and relevant notebook/report.
6. Run targeted tests.
7. Require reviewer acceptance before canonical write.

Useful commands:

```bash
uv run python -m py_compile manage_db/kg_schema.py manage_db/kg_evidence.py manage_db/backfill_edge_evidence.py manage_db/ingest_opentargets.py
uv run --group dev pytest tests/test_kg_schema_cleanup.py tests/test_kg_evidence.py tests/test_backfill_edge_evidence.py -q
uv run python -m manage_db.audit_kg_coverage /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 --json > artifacts/reports/<task-id>-coverage.json
```

For full endpoint validation prefer DuckDB on the mounted KG root or direct GCS paths; avoid stale local caches.
