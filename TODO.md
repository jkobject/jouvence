# Jouvence TODO — current human mirror

Kanban board `txgnn` remains the dispatch/source-of-truth. This file is a compact human overview; detailed phase mirrors live in `todo.d/`.

## Operating rule

Do **not** use `.omoc` for new work. It is a legacy scratch/cache location from older runs. New outputs should go to:

- `artifacts/staged/<task-id>/` for local staged artifacts;
- `artifacts/cache/<task-id>/` for bounded local cache if unavoidable;
- `docs/` for human-readable reports;
- `gs://jouvencekb/kg/staging/...` for remote staged artifacts;
- canonical writes only under `gs://jouvencekb/kg/v2/...` after validation + review.

Heavy Jouvence jobs are VM-only. Any card that may run LaminDB full/bulk syncs, production/full PyG/GNN exports or training, ReMap scaling, embeddings/full-KG scans, all-relation reads, or bulk canonical KG reads/writes must state `must_run_on=txgnn-worker` (the retained VM name) or another explicitly approved in-region worker, use `gs://jouvencekb/kg/v2` as source, and forbid `/Users/jkobject/mnt/gcs/...` / macOS GCS-FUSE for heavy work. Required preflight: verify `hostname`, launch/inspect with `gcloud compute ssh txgnn-worker`, check for an existing related writer/process, and fail if any heavy input/output path starts with `/Users/jkobject/mnt/gcs`. Copyable card template: `artifacts/reports/t_d682b7ad/heavy_job_vm_only_card_template.md`.

ReMap fresh-UDC continuations: foreground Kanban cards should use `--max-tiles 5`. Larger bounded continuations require a local/background supervisor with explicit heartbeat/progress JSON, stdout/stderr/rc capture, task-local fresh UDC, and canonical-negative validation/enforcement. Never reuse the old suspected-corrupt `artifacts/cache/t_1bc29376/udc` cache (relative, absolute, or descendant spellings are supervisor-rejected after path normalization). Full/unbounded caps (`--max-tiles >= 3220`, including `3220`) are rejected unless `--reviewed-full-run-override` is supplied after a separate reviewed operations gate; do not use the override for normal bounded continuations. Current supervisor template: `artifacts/reports/t_a2674d49/remap_fresh_udc_supervisor.py`; plan: `artifacts/reports/t_a2674d49/remap_supervisor_plan.md`.

Verified KG access:

- GCS canonical root: `gs://jouvencekb/kg/v2`
- macOS FUSE root: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2` for small bounded/local inspection only; forbidden for heavy LaminDB/PyG/ReMap/embedding/full-KG work.

## Status vocabulary

Avoid bare “done” except as a Kanban state. Use:

- `design done`
- `pilot accepted`
- `staged-only`
- `review-required`
- `validated`
- `canonical promoted`
- `production/full done`

## Review snapshot — 2026-07-15

This snapshot supersedes the older June execution notes below. Detailed denominators and evidence are in `todo.d/01_lamindb.md`, `todo.d/02_pyg_gnn.md`, and `todo.d/03_embeddings.md`.

1. **LaminDB ingestion is partial and under recovery.** Strict accepted ledger: **11,641,485 / 230,874,162 rows (5.04%)**, checkpoint **13,880,000**. A copy-only rollback/parity recovery is determining whether one additional 5k edge + 5k evidence prefix survived. No product writer is active during recovery.
2. **Node source features are not universally complete.** Canonical protein/transcript sequences exist; gene genomic sequence is staged and partial; enhancer/mutation sequence modalities remain absent; text descriptions cover nine node types with partial row coverage. See the explicit per-type matrix in `todo.d/03_embeddings.md`.
3. **Real embeddings exist, but not one source-backed vector per physical node.** Full staged protein ESM2 is accepted at **112,051/112,051** and full staged transcript NT at **187,268/187,268**. Other real text/molecule/edge modalities and learned fallback wiring have bounded reviewed evidence. Most are staged-only, and enhancer/mutation-heavy rows require model-side fallback.
4. **PyG/GNN has a real reviewed runtime smoke, not full-KG training.** A real `HeteroData` plus heterogeneous GraphSAGE link-prediction smoke passed and was independently rerun. The sidecar/mmap architecture is training-ready; full multi-relation model-quality training has not run.
5. **16 GB is enough only for the sampled sidecar/mmap design.** Bounded measured RSS was about 0.5 GB. A monolithic dense vector for all 55.5M nodes would require ~53 GiB even at 256 float32 dimensions, so full training must remain sharded/mmap-backed and sampled.

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
- canonical active edge relations: `40`, including three `canonical promoted`/`review-required` relations pending acceptance
- canonical relations with evidence: `18`
- canonical relations without evidence: `22`
- declared relations not canonical yet: `27`
- staged-only/deferred: `18`
- source-audit-only/deferred: `2`
- feature-context-not-edge: `2`
- schema-only/missing: `5`
- canonical edge rows: `100,080,390`
- node rows: `55,523,691`

## Active priorities

### 1. LaminDB / `lnschema_txgnn`

`lnschema_txgnn` is locally activated and artifact registry sync is implemented/reviewed. Bounded live KGEdge/KGEdgeEvidence syncs now populate/query-validate 130,050 KGEdge rows and 95,025 KGEdgeEvidence rows after Wave-2 (`t_cf755270`, `bounded live sync wave2 accepted`), but full exact-ID schema/query coverage is not finished and this is not production/full done.

- `t_c51d9a5b` — activation/config revision producer: `review-required`; local self-managed config now includes `lnschema_txgnn`.
- `t_f6b334c7` — controlled live KGEdge/KGEdgeEvidence Wave-1: `bounded live sync wave1 accepted`; not production/full done.
- `t_cf755270` — bounded live KGEdge/KGEdgeEvidence Wave-2: `bounded live sync wave2 accepted` producer handoff pending review; batch loader proof with 100,000 additional KGEdge rows and 70,000 additional KGEdgeEvidence rows; not production/full done.
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

Accepted staged-only support artifacts:

- `t_3b8a2c4d` — CRM support/QA first10k chr1 pilot.
- Prefix: `gs://jouvencekb/kg/staging/source-native-expansion/remap-crm-tf-binds-enhancer-support-chr1-first10k-20260623-t_3b8a2c4d/`
- `t_b599d3bb` — CRM support/QA all-chromosome bounded 5k-per-chrom artifact; staged-only/support-only.
- Prefix: `gs://jouvencekb/kg/staging/source-native-expansion/remap-crm-tf-binds-enhancer-support-allchrom-5kperchrom-20260623-t_b599d3bb/all_chrom_5k_per_chrom/`

Canonical-readiness decision:

- `t_9c0e6a68` — decision doc: `docs/remap_crm_canonical_readiness.md`.
- Only appropriate canonical target from current CRM artifact: support/evidence sidecar `features/remap_crm_tf_enhancer_support.parquet`, via separately reviewed promotion card `t_656a1102`.
- CRM is `crm_aggregated_support` / support-QA only; not canonical `observed_binding`, not canonical `tf_binds_enhancer` edge/evidence, and not `tf_regulates_gene`.
- Observed binding requires peak-level/per-experiment source rows with assay/biosample/direct-binding evidence; TF→gene regulation requires a separate source-native TF→target regulation policy/source.

### 5. Mutation genomic direct relations

`mutation_affects_transcript` is canonical promoted/review-accepted from the all-part OpenTargets 26.03 candidate. `mutation_in_gene` is now relation-specific canonical promoted/review-required by `t_1cfcd48f` from the full all-25-part containment-gated candidate (`t_2bb8e7de`) using OpenTargets `target.genomicLocation`, with 2,599,525 edge/evidence/proof rows and passing live canonical endpoint, duplicate/gap, containment, leakage, staged/canonical sha256, and edge/evidence audit gates. `mutation_overlaps_enhancer` is canonical promoted/review-required by `t_00551bc3` only for the reviewed non-context-support-gated `t_73c67c1b` candidate (1,664,278 edge/evidence rows); coordinate overlap alone remains context/support-only and not observed regulatory evidence.

Relations:

- `mutation_affects_transcript` — `canonical promoted` / reviewed.
- `mutation_in_gene` — `canonical promoted` / `review-required`; relation-specific canonical write done by `t_1cfcd48f`, pending independent acceptance.
- `mutation_overlaps_enhancer` — `canonical promoted` / `review-required` for the support-gated `t_73c67c1b` candidate promoted by `t_00551bc3`; coordinate-only overlap remains context/support-only and not observed regulatory evidence.

Cards:

- `t_60b3e504` — policy done.
- `t_79f8684d` — 25k staged tranche accepted for QA only.
- `t_f32f1f5b` / `t_225ae18c` — all-part `mutation_affects_transcript` candidate accepted and canonical promoted.
- `t_8de911c0` — remaining-relation next-state decision: `mutation_in_gene` bounded containment candidate only; `mutation_overlaps_enhancer` coordinate-only context/support feature; no broad or relation-specific promotion card created.
- `t_0aa76f3b` — support-gated `mutation_overlaps_enhancer` policy/pilot: evidence-backed staged edge candidate with external support context, no canonical write.
- `t_73c67c1b` — full non-context-support-gated `mutation_overlaps_enhancer` staged candidate: 1,664,278 edges/evidence rows with live endpoint anti-joins and edge/evidence validation passing. Report: `docs/mutation_overlaps_enhancer_support_gated_full_t_73c67c1b.md`.
- `t_00551bc3` — relation-specific canonical promotion of reviewed `t_73c67c1b` support-gated `mutation_overlaps_enhancer` to `gs://jouvencekb/kg/v2/{edges,evidence}/`; status `canonical promoted`/`review-required` pending independent acceptance. Report: `docs/mutation_overlaps_enhancer_canonical_promotion_t_00551bc3.md`.
- `t_2bb8e7de` — full all-25-part `mutation_in_gene` containment-gated staged candidate built/validated under `artifacts/staged/t_2bb8e7de/`; producer handoff was `review-required`, with no canonical write.
- `t_1cfcd48f` — `mutation_in_gene` live endpoint revalidation and relation-specific canonical write to `gs://jouvencekb/kg/v2/{edges,evidence,proof}/`; status `review-required` pending independent review. Report: `docs/mutation_in_gene_canonical_promotion_t_1cfcd48f.md`.
- `t_4b1227b3` — do not use as blanket promotion; only relation-specific promotion after explicit acceptance.

### 6. Relation waves

Use `docs/relation_backlog_prioritized.md` and `todo.d/04_relations.md`. A relation is not complete until canonical promoted+reviewed or explicitly accepted as staged/deferred.

### 7. Process hygiene

- `t_caacd3d1` — keep `todo.d/` synced, enforce honest status labels, fix review routing/watchdog behavior, and prevent `.omoc` recreation.

## Git / reviewability

The migration from `t_4cab4a2f` is now executed: `/Users/jkobject/.openclaw/workspace/work/txgnn` is the canonical local worktree for `https://github.com/jkobject/jouvence`. The local `txgnn` path remains for compatibility. Project-level Git commands and human review run here; parallel task worktrees remain under `/Users/jkobject/.openclaw/worktrees/txgnn/<branch-or-task-id>/`.

The root still contains ignored local artifacts/caches. Reviewability therefore requires an explicit Git diff and generated-file guard; directory contents alone are not a commit surface. Do not initialize or maintain a second canonical checkout under `~/code`.

## Historical note

Older docs/reports may mention `.omoc` and old local caches. Treat those as historical evidence only, not current instructions. If an old worker actively targets the legacy path, let it finish, then preserve useful outputs under `artifacts/`, `docs/`, or GCS staging and retire the legacy path when no active command references it.
