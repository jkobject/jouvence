# Jouvence TODO — current human mirror

Kanban board `txgnn` remains the dispatch/source-of-truth. This file is a compact human overview; detailed phase mirrors live in `todo.d/`.

_Status snapshot: 2026-07-22 15:18 CEST._

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
- `canonical candidate`
- `canonical promoted`
- `stopped-by-user`
- `production/full done`

## Review snapshot

This snapshot supersedes the older June/July execution notes below. Detailed denominators and evidence are in `todo.d/01_lamindb.md`, `todo.d/02_pyg_gnn.md`, and `todo.d/03_embeddings.md`.

1. **Exact-ENSG genomic embeddings are canonical promoted and independently accepted.** Producer `t_03bf9e27` and its independent reviewer froze staged manifest `d32ef9502fe7100a4fa6512a07b1a614806f1a6d32dd395d9be3ef3faa7eb397`. After the independently accepted lifecycle fix (`t_0d57fd03` / `t_2113fbf0`), promotion `t_6cf146f0` was independently accepted at the immutable canonical Nucleotide Transformer release: 78,644 embedded + 3,071 explicit missing = 81,715 eligible human ENSG; duplicate, mismatch, nonfinite and all-zero counts are 0. This promotes the feature release only: canonical `nodes/gene.parquet` remains the mixed 267,830-row source (81,715 ENSG + 186,115 quarantined non-ENSG), so it is not a claim that the ENSG-only Gene node migration was canonically promoted.
2. **LaminDB ingestion is partial, and accepted counters differ from physical counters.** The latest durable accepted ledger (2026-07-18 evidence) is 11,671,485 / 230,874,162 rows. The latest sealed physical readback from the same date is 12,011,512 rows, with +170,027 edges and +170,000 evidence still uncredited. No newer mismatch-0 readback is claimed. The human-ENSG migration implementation is merged and independently accepted (PR #12, merge `2786d847`; corrected head `7f300b8`; `t_5c938f23` / `t_0b806c0e`), but the production rebuild and canonical node migration were not executed; live `nodes/gene.parquet` remains generation `1781617033173178`.
3. **The corrected immutable public embeddings v2 candidate is validated.** Producer `t_2d54477b` published 808,269 rows across 12 logical leaves; independent reviewer `t_2e6b355f` passed the exact 51-object candidate at generation `1784460889447648`. This is a validated immutable candidate, not a mutable latest-pointer or blanket source-backed vector for every node. Rejected v1 remains historical and unaccepted.
4. **The old 6,912-row Gene NT checkpoint is historical, not current coverage.** `t_d3b876b3` remains a non-canonical, zero-credit stopped scratch checkpoint and must not be resumed or published. It has been superseded for product status by the exact accepted 78,644-row canonical release above.
5. **DepMap revision 2 is code/test ready but not fully rebuilt.** PR #11 is pushed at `e40e2508b8f061f70fc7a4fcbf05b0f4a1accfaf`; no fresh dual full build or accepted immutable artifact is claimed. The prior candidate remains rejected.
6. **PyG/GNN has a real reviewed runtime smoke, not full-KG training.** The sidecar/mmap architecture remains the bounded path; full multi-relation model-quality training has not run. The accepted canonical zero-row formal-inference release is valid negative evidence, not inferred-edge coverage; full inferred-edge materialization and GNN ablations remain intentionally paused by `t_437925a5`.
7. **Public notebooks and the zero-backend viewer are active review lanes, not completed releases.** PR #42 continuation `t_1cf69ed9` remains review-required after an independent reviewer found a remaining keyword-shell false pass in the pedagogical checker. Viewer PRs #35 and #37 are merged; GitHub Pages deploy `29919985184` succeeded at merge `034e498`, while the public viewer remains honestly labelled `fixture-v1`. The real ≤500 MiB public bundle `t_3158fa55` is blocked after the remote stop pending explicit bounded-cloud authorization or a local/read-only rescope; retained local work is incomplete and no real candidate or publication is claimed. The merged localhost viewer remains the supported full-data path.
8. **Explicit holds remain non-dispatchable.** LaminDB/enhancer work (`t_25b1ac18`), full inferred-edge/GNN expansion (`t_437925a5`) and optional source-native expansion (`t_2a8cbcd6`) require an explicit later resumption/selection; no autonomous execution or completion credit is implied.

## Current phase mirrors

Use the live board plus the dated phase files below as the current-state anchor. `docs/current_state_20260623.md` is historical context, not live dispatch state.

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
- `reproduce/15_kg_schema_overview.ipynb`
- `docs/relation_backlog_prioritized.md`

Accepted snapshot:

- active declared relations: `67`
- canonical active edge relations: `41`; the three formerly review-required canonical writes were independently accepted by `t_2d1f767d`, and `disease_associated_protein` was independently accepted by `t_0611e6c6`
- canonical relations with evidence: `19`
- canonical relations without evidence: `22`
- declared relations not canonical yet: `26`
- staged-only/deferred: `17`
- source-audit-only/deferred: `2`
- feature-context-not-edge: `2`
- schema-only/missing: `5`
- canonical edge rows: `100,083,633`
- node rows: `55,523,691`

The count delta above is limited to the independently accepted `disease_associated_protein` promotion (`t_aa5cd96e` / reviewer `t_0611e6c6`): 3,243 canonical edges and 35,839 evidence rows, with endpoint/support/hash mismatch 0 and replay no-op. It does not change the accepted LaminDB ingestion numerator. PR #43's corrected 67-relation ledger remains changes-requested/pending and is not accepted as a replacement inventory.

## Active priorities

### 1. LaminDB / `lnschema_txgnn`

`lnschema_txgnn` activation and bounded loaders are validated, but global ingestion remains partial. Current durable counter and Gene-identity boundaries are in `todo.d/01_lamindb.md`.

- The reviewed 81,715-ENSG embedding denominator does not itself migrate the canonical Gene node table or LaminDB. PR #12's migration implementation is merged and reviewed, but the production rebuild/canonical promotion still requires its own execution, exact-ID parity, and acceptance.
- `t_ce839966` and `t_075f5353` — superseded historical +158,505 non-human Gene sync plans; remain inert and must not run.
- Accepted-versus-physical drift remains explicit; physical rows are not product credit without accepted readback evidence.

Production/full done requires reviewed ENSG-only denominators, exact-ID row parity, mismatch 0, and independent acceptance. Schema activation alone is not production/full done.

### 2. PyG / GNN

Existing PyG work is a bounded export pilot, not completion.

- `t_015bd9a4` — full KG / representative KG PyG export plus runnable GNN smoke/training.
- `t_1d1eb3a1` — validate actual HeteroData/GNN runtime.
- `t_468db80e` — review full PyG/GNN acceptance.

Done means an actual PyG/HeteroData object exists and a GNN run executes on it.

### 3. Embeddings

Four source-backed embedding families have one independently validated immutable v2 candidate, and the exact-ENSG genomic Nucleotide Transformer feature now has a separately promoted, independently accepted immutable canonical release. Model-side fallback remains required for uncovered nodes/modalities.

- `t_2d54477b` — published immutable v2 candidate: 808,269 rows, 12 logical leaves, 51 objects; producer card is historical/triage after handoff.
- `t_2e6b355f` — independent v2 reviewer: `validated` PASS on 2026-07-19. No latest-pointer mutation or universal-coverage claim.
- Rejected v1 remains historical and unaccepted.
- `t_03bf9e27` / `t_6cf146f0` — exact-ENSG genomic NT staged manifest `d32ef9502fe7100a4fa6512a07b1a614806f1a6d32dd395d9be3ef3faa7eb397` promoted after independent review to `gs://jouvencekb/kg/v2/features/embeddings/nucleotide_sequence/gene/instadeepai_nucleotide_transformer_v2_50m_multi_species/81b29e5786726d891dbf929404ef20adca5b36f1+gene_locus_1000nt_policy_v1`: 78,644 embedded, 3,071 explicit missing (3,006 source absent + 65 excluded contig/build), 81,715 eligible ENSG, and 186,115 quarantined non-ENSG. This is feature coverage, not canonical Gene-node migration.
- `t_d3b876b3` — historical stopped scratch checkpoint at 6,912 rows; non-canonical, zero current coverage credit, and no auto-resume.
- Learned fallback is still required where reviewed source vectors are absent; it is not biological evidence.

### 4. ReMap

ReMap is complete for the currently accepted route C: canonical bounded and full CRM feature-context sidecars were independently accepted, while conversion into active full `tf_binds_enhancer` topology is an explicit policy-deferred non-goal. Do not create a new execution lane without a superseding decision.

Accepted staged-only support artifacts:

- `t_3b8a2c4d` — CRM support/QA first10k chr1 pilot.
- Prefix: `gs://jouvencekb/kg/staging/source-native-expansion/remap-crm-tf-binds-enhancer-support-chr1-first10k-20260623-t_3b8a2c4d/`
- `t_b599d3bb` — CRM support/QA all-chromosome bounded 5k-per-chrom artifact; staged-only/support-only.
- Prefix: `gs://jouvencekb/kg/staging/source-native-expansion/remap-crm-tf-binds-enhancer-support-allchrom-5kperchrom-20260623-t_b599d3bb/all_chrom_5k_per_chrom/`

Canonical-readiness decision:

- `t_9c0e6a68` — decision doc: `docs/remap_crm_canonical_readiness.md`.
- `t_656a1102` / reviewer `t_69fa9b1d` accepted the bounded canonical feature-context sidecar `features/remap_crm_tf_enhancer_support.parquet`.
- `t_f2a2952e` / reviewer `t_0974375e` accepted the full sharded canonical feature-context sidecar under `features/remap_crm_tf_enhancer_support_full/`.
- CRM is `crm_aggregated_support` / support-QA only; not canonical `observed_binding`, not canonical `tf_binds_enhancer` edge/evidence, and not `tf_regulates_gene`.
- Observed binding requires peak-level/per-experiment source rows with assay/biosample/direct-binding evidence; TF→gene regulation requires a separate source-native TF→target regulation policy/source.

### 5. Mutation genomic direct relations

`mutation_affects_transcript` is canonical promoted/review-accepted from the all-part OpenTargets 26.03 candidate. `mutation_in_gene` and the support-gated `mutation_overlaps_enhancer` promotion are now independently accepted by consolidated reviewer `t_2d1f767d`; coordinate overlap alone remains context/support-only and not observed regulatory evidence.

Relations:

- `mutation_affects_transcript` — `canonical promoted` / reviewed.
- `mutation_in_gene` — `canonical promoted` / independently accepted (`t_1cfcd48f` / `t_2d1f767d`).
- `mutation_overlaps_enhancer` — `canonical promoted` / independently accepted for the support-gated `t_73c67c1b` candidate (`t_00551bc3` / `t_2d1f767d`); coordinate-only overlap remains context/support-only.

Cards:

- `t_60b3e504` — policy done.
- `t_79f8684d` — 25k staged tranche accepted for QA only.
- `t_f32f1f5b` / `t_225ae18c` — all-part `mutation_affects_transcript` candidate accepted and canonical promoted.
- `t_8de911c0` — remaining-relation next-state decision: `mutation_in_gene` bounded containment candidate only; `mutation_overlaps_enhancer` coordinate-only context/support feature; no broad or relation-specific promotion card created.
- `t_0aa76f3b` — support-gated `mutation_overlaps_enhancer` policy/pilot: evidence-backed staged edge candidate with external support context, no canonical write.
- `t_73c67c1b` — full non-context-support-gated `mutation_overlaps_enhancer` staged candidate: 1,664,278 edges/evidence rows with live endpoint anti-joins and edge/evidence validation passing. Report: `docs/mutation_overlaps_enhancer_support_gated_full_t_73c67c1b.md`.
- `t_00551bc3` — relation-specific canonical promotion of reviewed `t_73c67c1b` support-gated `mutation_overlaps_enhancer` to `gs://jouvencekb/kg/v2/{edges,evidence}/`; independently accepted by `t_2d1f767d`. Report: `docs/mutation_overlaps_enhancer_canonical_promotion_t_00551bc3.md`.
- `t_2bb8e7de` — full all-25-part `mutation_in_gene` containment-gated staged candidate built/validated under `artifacts/staged/t_2bb8e7de/`; producer handoff was `review-required`, with no canonical write.
- `t_1cfcd48f` — `mutation_in_gene` live endpoint revalidation and relation-specific canonical write to `gs://jouvencekb/kg/v2/{edges,evidence,proof}/`; independently accepted by `t_2d1f767d`. Report: `docs/mutation_in_gene_canonical_promotion_t_1cfcd48f.md`.
- `t_4b1227b3` — do not use as blanket promotion; only relation-specific promotion after explicit acceptance.

### 6. Relation waves

Use `docs/relation_backlog_prioritized.md` and `todo.d/04_relations.md`. A relation is not complete until canonical promoted+reviewed or explicitly accepted as staged/deferred.

### 7. Process hygiene

- `t_caacd3d1` — keep `todo.d/` synced, enforce honest status labels, fix review routing/watchdog behavior, and prevent `.omoc` recreation.

### 8. Public notebooks and viewer

- `t_1cf69ed9` / PR #42 — continuation remains `review-required`; fixture build/execution and focused checks passed at the latest handed-off head, but independent qualitative review still found a dressed keyword-shell false pass. Do not call the notebook course accepted or merged.
- Viewer PRs #35 and #37 are merged; GitHub Pages deploy `29919985184` succeeded at merge `034e498`. The public site remains explicitly `fixture-v1`.
- `t_3158fa55` — real zero-backend ≤500 MiB public bundle is blocked after remote stop pending explicit bounded-cloud authorization or local/read-only rescope. Local uncommitted work is partial; no reproducible measured candidate, PR, publication or product credit exists.
- The merged secure localhost/query-bundle viewer and published `viewer-install.html` guide remain the supported full-data route. Fixture mode and any static fallback must remain explicitly labeled rather than presented as the real public bundle.

### 9. Intentional holds

- `t_25b1ac18` — LaminDB/enhancer continuation paused until Jérémie explicitly resumes the Mac mini local-copy plan.
- `t_437925a5` — full inferred-edge materialization and GNN ablations paused; the accepted canonical zero-row formal-inference release remains valid but does not imply inferred-edge coverage.
- `t_2a8cbcd6` — optional source-native expansion paused until one source/outcome denominator is explicitly selected.

## Git / reviewability

The migration from `t_4cab4a2f` is now executed: `/Users/jkobject/Documents/jouvence` is the canonical local checkout for `https://github.com/jkobject/jouvence-graph`. The legacy `txgnn` path remains a compatibility-only location for preserved historical worktrees. Project-level Git commands and human review run from the canonical checkout; new task worktrees live under `/Users/jkobject/Documents/jouvence/.worktrees/<task-id>` unless a card names another verified worktree.

The root still contains ignored local artifacts/caches. Reviewability therefore requires an explicit Git diff and generated-file guard; directory contents alone are not a commit surface. Do not initialize or maintain a second canonical checkout under `~/code`.

## Historical note

Older docs/reports may mention `.omoc` and old local caches. Treat those as historical evidence only, not current instructions. If an old worker actively targets the legacy path, let it finish, then preserve useful outputs under `artifacts/`, `docs/`, or GCS staging and retire the legacy path when no active command references it.

---

_Live-status evidence refreshed 2026-07-22 15:18 CEST from immutable Kanban handoffs named above, including `t_5c938f23` / `t_0b806c0e`, `t_03bf9e27`, `t_6cf146f0`, `t_2d1f767d`, `t_1cf69ed9`, `t_3158fa55`, `t_25b1ac18`, `t_437925a5`, and `t_2a8cbcd6`. Kanban remains the live source of truth; this footer does not turn running, blocked, staged or review-required work into accepted product state._
