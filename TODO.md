# TxGNN / Jouvence KG TODO — current human mirror

Kanban board `txgnn` remains the dispatch/source-of-truth. This file is a compact human overview; detailed phase mirrors live in `todo.d/`.

## Operating rule

Do **not** use `.omoc` for new work. It is a legacy scratch/cache location from older runs. New outputs should go to:

- `artifacts/staged/<task-id>/` for local staged artifacts;
- `artifacts/cache/<task-id>/` for bounded local cache if unavoidable;
- `docs/` for human-readable reports;
- `gs://jouvencekb/kg/staging/...` for remote staged artifacts;
- canonical writes only under `gs://jouvencekb/kg/v2/...` after validation + review.

Verified KG access:

- GCS canonical root: `gs://jouvencekb/kg/v2`
- macOS FUSE root: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`

## Status vocabulary

Avoid bare “done” except as a Kanban state. Use:

- `design done`
- `pilot accepted`
- `staged-only`
- `review-required`
- `validated`
- `canonical promoted`
- `production/full done`

## Current phase mirrors

Use `docs/current_state_20260623.md` plus the phase files below as the current-state anchor.

- `todo.d/01_lamindb.md`
- `todo.d/02_pyg_gnn.md`
- `todo.d/03_embeddings.md`
- `todo.d/04_relations.md`
- `todo.d/05_remap.md`
- `todo.d/06_process.md`

## Current KG coverage source of truth

Use these, not old `.omoc` reports:

- `docs/kg_schema_overview.md`
- `docs/relation_coverage_current.md`
- `notebooks/kg_schema_overview.ipynb`
- `docs/relation_backlog_prioritized.md`

Accepted snapshot:

- active declared relations: `67`
- canonical active edge relations: `37`
- canonical relations with evidence: `15`
- canonical relations without evidence: `22`
- declared relations not canonical yet: `30`
- staged-only/deferred: `20`
- source-audit-only/deferred: `2`
- feature-context-not-edge: `2`
- schema-only/missing: `6`
- canonical edge rows: `94,880,924`
- node rows: `55,523,691`

## Active priorities

### 1. LaminDB / `lnschema_txgnn`

`lnschema_txgnn` is locally activated and artifact registry sync is implemented/reviewed, but full exact-ID schema/query coverage is not finished.

- `t_c51d9a5b` — activation/config revision producer: `review-required`; local self-managed config now includes `lnschema_txgnn`.
- `t_edb59ab8` — validate activation/exact-ID registry.
- `t_59139647` — review activation/exact-ID registry.
- `t_3d4fa114` — audit/design full node/edge/evidence/feature schema/query API coverage after activation.

Done means `lnschema_txgnn` is configured and usable for `jkobject/jouvencekb`, exact-ID node/edge/evidence/feature sync probes pass, and validator/reviewer accept. Local activation alone is not production/full done.

### 2. PyG / GNN

Existing PyG work is a bounded export pilot, not completion.

- `t_015bd9a4` — full KG / representative KG PyG export plus runnable GNN smoke/training.
- `t_1d1eb3a1` — validate actual HeteroData/GNN runtime.
- `t_468db80e` — review full PyG/GNN acceptance.

Done means an actual PyG/HeteroData object exists and a GNN run executes on it.

### 3. Embeddings

Existing embedding work is policy + surrogate pilot, not production embeddings.

Corrections to encode:

- full UniProt `protein_textual_summary.parquet` is validated/promoted and should be used as text signal;
- edge values/evidence should be encoded through an MLP/value encoder;
- edge input should concatenate/aggregate all edges/evidence between the same node pair where relevant;
- nodes/edges without source info get learned embeddings;
- HashingVectorizer is schema-only pilot, not production.

Cards:

- `t_6b3c1294` — update embedding policy with corrections.
- `t_f8bae791` — create real node/edge embeddings.
- `t_34836f1c` — validate real embeddings.
- `t_384b9594` — review real embeddings.

### 4. ReMap

All-peak ReMap is stopped/deferred. Do not auto-resume.

Accepted staged-only pilot:

- `t_3b8a2c4d` — CRM support/QA first10k chr1 pilot.
- Prefix: `gs://jouvencekb/kg/staging/source-native-expansion/remap-crm-tf-binds-enhancer-support-chr1-first10k-20260623-t_3b8a2c4d/`

Next:

- `t_b599d3bb` — build accepted CRM support/QA artifact at larger/full feasible scope with detailed report.
- `t_3a7a8c9c` — validate CRM artifact.
- `t_9b96ea36` — review CRM artifact/report.

CRM is support/QA only; not canonical `observed_binding`.

### 5. Mutation genomic direct relations

`mutation_affects_transcript` is canonical promoted/review-accepted from the all-part OpenTargets 26.03 candidate. `mutation_in_gene` remains staged/deferred. `mutation_overlaps_enhancer` remains staged/context/feature-only unless stronger allele-specific regulatory/enhancer-activity evidence is selected by a new policy.

Relations:

- `mutation_affects_transcript` — `canonical promoted` / reviewed.
- `mutation_in_gene` — staged/deferred, not canonical.
- `mutation_overlaps_enhancer` — staged/context/feature-only, not canonical observed regulatory evidence.

Cards:

- `t_60b3e504` — policy done.
- `t_79f8684d` — 25k staged tranche accepted for QA only.
- `t_f32f1f5b` / `t_225ae18c` — all-part `mutation_affects_transcript` candidate accepted and canonical promoted.
- `mutation_in_gene` / `mutation_overlaps_enhancer` — deferred until explicit source/evidence policy and review acceptance.
- `t_4b1227b3` — do not use as blanket promotion; only relation-specific promotion after explicit acceptance.

### 6. Relation waves

Use `docs/relation_backlog_prioritized.md` and `todo.d/04_relations.md`. A relation is not complete until canonical promoted+reviewed or explicitly accepted as staged/deferred.

### 7. Process hygiene

- `t_caacd3d1` — keep `todo.d/` synced, enforce honest status labels, fix review routing/watchdog behavior, and prevent `.omoc` recreation.

## Git / reviewability blocker

`work/txgnn` is not currently an independent git checkout. `git -C /Users/jkobject/.openclaw/workspace/work/txgnn status` falls back to the parent workspace repo and fails because invalid nested `.git` directories exist under sibling workspace projects.

Decision from `t_4cab4a2f`: use the existing GitHub repo `https://github.com/jkobject/TxGNN` and perform future reviewable work in `/Users/jkobject/.openclaw/worktrees/txgnn/<branch-or-task-id>/` (or a canonical clone), not by `git init` in the artifact workspace. See `docs/git_reviewability_migration_t_4cab4a2f.md` for the invalid `.git` quarantine plan, migration commands, and review gates. Do not claim PR-ready diffs from `work/txgnn` until that migration is executed and reviewed.

## Historical note

Older docs/reports may mention `.omoc` and old local caches. Treat those as historical evidence only, not current instructions. If an old worker actively targets the legacy path, let it finish, then preserve useful outputs under `artifacts/`, `docs/`, or GCS staging and retire the legacy path when no active command references it.
