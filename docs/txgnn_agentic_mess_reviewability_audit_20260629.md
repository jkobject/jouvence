# TxGNN / Jouvence KG — agentic mess + reviewability rescue audit

> **Historical audit — superseded routing.** Current checkout/worktree paths are `/Users/jkobject/Documents/jouvence` and `/Users/jkobject/Documents/jouvence/.worktrees/`; older paths below record the 2026-06-29 observation only.

Date: 2026-06-29  
Workspace audited: `/Users/jkobject/.openclaw/workspace/work/txgnn`  
Mode: local read-only code/docs/artifact-shape inspection, plus writing this report. No GCS writes, no LaminDB writes, no canonical KG promotion, no deletion.

## 1. Verdict reviewability

`work/txgnn` is **not reviewable as a standalone Git repository**.

Evidence from local inspection:

- `work/txgnn/.git` is absent.
- `git rev-parse --show-toplevel` from `work/txgnn` resolves to the parent workspace: `/Users/jkobject/.openclaw/workspace`.
- `git status --short` from `work/txgnn` reports unrelated parent-workspace dirt such as `../../TOOLS.md`, `../../openclaw.json`, `../river`, `../pert-gym`, and unrelated untracked paths. That is not a TxGNN-scoped diff.
- `AGENTS.md` already states the caveat explicitly: this directory is a shared artifact workspace and PR-ready work should happen in `/Users/jkobject/.openclaw/worktrees/txgnn/<branch-or-task-id>/` or a canonical clone of `https://github.com/jkobject/TxGNN`.

Recommended procedure:

1. Establish a clean, real Git checkout/worktree of `jkobject/TxGNN` for reviewable code/docs work, e.g. under `/Users/jkobject/.openclaw/worktrees/txgnn/<task-id>-<slug>`.
2. Treat `work/txgnn` as a shared artifact/status workspace only: useful for reports, staged outputs, historical evidence, and local source-of-truth docs during migration, but **not** for PR claims.
3. Migrate only the minimal needed code/docs changes from `work/txgnn` into the clean checkout.
4. Validate and review from the clean checkout with a real `git diff` before any PR-ready claim.
5. Do **not** run `git init` in `work/txgnn`; that would make artifact/history contamination look clean without solving provenance.

## 2. Risk assessment

### Git / reviewability — Critical

The current directory mixes code, docs, 3,363 artifact files, reports, caches, and staged outputs under a non-repo workspace. Any `git diff` from here is parent-workspace noise. This is the top blocker for PR-quality engineering.

Risk symptoms:

- Cannot produce TxGNN-scoped diff from `work/txgnn`.
- Code and generated artifacts coexist in one tree.
- Some active worktrees exist separately, but the shared workspace remains the operational center.

### Code monoliths — High

The codebase has multiple large files and long functions/classes:

- `manage_db/ingest_opentargets.py`: 3,205 lines.
- `txgnn/utils.py`: 1,589 lines; includes a 385-line `disease_centric_evaluation` function with nested metrics/plotting/prediction logic and broad `except:` blocks.
- `manage_db/kg_schema.py`: 1,307 lines.
- `manage_db/backfill_edge_evidence.py`: 964 lines.
- `manage_db/build_intact_protein_interactions.py`: 956 lines.
- `manage_db/sync_parquet_nodes_to_lamindb.py`: 904 lines.
- `manage_db/build_pyg_export.py`: 899 lines.
- `txgnn/TxGNN.py`: 727 lines; class owns initialization, pretraining, finetuning, eval, explainability/graphmask workflows.

The risk is not size alone; the problem is that heavy IO, schema policy, validation, promotion semantics, CLI orchestration, and one-shot job logic are often close together.

### Artifacts / scratch mixed with code — Critical operational risk

Top-level shape:

- code-ish: `txgnn/`, `manage_db/`, `tests/`, `scripts/`, `docs/`, `notebooks/`, `todo.d/`.
- generated/huge: `artifacts/` with 3,363 files and ~68 GiB.
- historical/legacy: `artifacts/legacy_omoc_20260624_t_859cbca4/`; `.omoc` itself was not present in the current top-level listing, but `.omx` exists.
- accidental-looking local paths: `gs:/jouvencekb/...` exists as a local directory stub and should be treated suspiciously, not as canonical GCS.

Size hotspots:

- `artifacts/reports`: ~35 GiB, dominated by LaminDB `.bak` files.
- `artifacts/cache`: ~17 GiB.
- `artifacts/staged`: ~15 GiB.
- TxGNN worktrees outside this workspace: ~26 GiB total, including active foundation embeddings.

### Docs / status divergence — High

There is a good current-state system (`AGENTS.md`, `docs/current_state_20260623.md`, `todo.d/`), but it is intrinsically fragile because Kanban, artifacts, docs, and local runs evolve independently.

Observed examples:

- `AGENTS.md` and `docs/current_state_20260623.md` both warn that `work/txgnn` is not a repo, which is good.
- `todo.d/` is a human-readable mirror, but explicitly says Kanban remains dispatch source of truth.
- Major phase files contain many card IDs and status labels; without periodic reconciliation, they can lag behind accepted reviewer gates or failed/stopped workers.

### KG promotion safety — High but reasonably documented

The project has strong safety vocabulary and docs:

- `docs/kg_schema_overview.md`
- `docs/relation_coverage_current.md`
- `docs/kanban_status_hygiene.md`
- `docs/txgnn_access_runbook.md`
- multiple promotion/validation reports, e.g. mutation and clinical-trials canonical promotion docs.

The safety risk is that agents can still run from the artifact workspace, then claim status from local artifacts without a clean reviewable code diff. Promotion gates must stay separate from code cleanup work.

## 3. Code hotspots

| File | Function / unit | Approx size | Why risky | Minimal refactor | Tests needed |
|---|---:|---:|---|---|---|
| `txgnn/utils.py` | `disease_centric_evaluation` | ~385 lines | Nested metric calculators, plotting, model inference, label construction, random baseline, and broad `except:` all in one function. Hard to test and easy to change behavior accidentally. | Extract: label construction, prediction graph construction, ranking metrics, classification metrics, plotting. Keep public wrapper stable. | Golden fixture for a tiny disease/drug graph; metric regression tests; no-plot path; random baseline deterministic seed test. |
| `txgnn/TxGNN.py` | `TxGNN` class | ~693 class lines | Training, eval, model lifecycle, W&B, graphmask/explainability coupled into one mutable object. | Split training loop helpers and evaluation/explainability orchestration without changing external API. | Existing training smoke if feasible; initialization/pretrain/finetune API compatibility tests. |
| `manage_db/ingest_opentargets.py` | multiple `ingest_*` functions | file ~3,205 lines; functions up to ~213 lines | Many source-specific ETL paths and schema/policy assumptions in one file. High regression risk for OpenTargets relation semantics. | Extract per-domain modules only when touched: variants, evidence, expression, pharmacogenomics, enhancers. Keep CLI compatibility. | Existing OpenTargets tests plus per-domain fixture tests and anti-join/evidence checks. |
| `manage_db/build_pyg_export.py` | `build_pyg_export` | ~282 lines | Reads nodes/edges/features, validates, writes maps/tensors/manifests in one function. Central PyG safety path. | Extract node-map build, edge-map build, feature-map write, manifest write. Preserve `BuildConfig`/`BuildResult`. | `tests/test_build_pyg_export.py`; add fixture asserting dataset/paper exclusion and missing endpoint behavior. |
| `manage_db/sync_parquet_edges_to_lamindb.py` | `_sync_relation_pass` / `sync_relation_to_lamindb` | ~95 + ~? lines | Live LaminDB writes, chunking, idempotence, source reads, and verification tightly coupled. Dangerous because failures can leave live DB locks/stale backups. | Separate read-window planning, chunk execution, live upsert transaction, and post-write verification. No behavior change without dedicated reviewer. | `tests/test_sync_parquet_edges_to_lamindb.py`; dry-run tests; idempotence fixture; no-writer/lock behavior mocked. |
| `manage_db/sync_parquet_nodes_to_lamindb.py` | `sync_parquet_nodes_to_lamindb`, `_row_to_record_spec` | file ~904 lines; functions ~174/114 lines | Similar live-write risk for node registries; broad exception fallbacks around Lamin/Django availability. | Extract Lamin runtime adapter and pure row-normalization layer. | `tests/test_sync_parquet_nodes_to_lamindb.py`; registry-unavailable test; row normalization fixtures. |
| `manage_db/build_hpa_cellular_components.py` | `build_artifacts` | ~296 lines | Source parsing, entity mapping, evidence construction, and output writing likely coupled. | Extract source readers and row builders; keep CLI. | Existing HPA tests plus endpoint/evidence schema tests. |
| `manage_db/backfill_edge_evidence.py` | evidence builders | file ~964 lines; functions up to ~134 lines | Evidence semantics are KG-critical; mistakes can imply unsupported biological assertions. | Extract per-relation evidence builders and shared audit helpers. | `tests/test_backfill_edge_evidence.py`, evidence support audit fixture. |
| `manage_db/build_intact_protein_interactions.py` | `build_from_mitab`, `evidence_row` | ~210 / ~100 lines | Protein endpoint/source-native semantics are sensitive; direct-protein vs gene projection errors are costly. | Separate MITAB reader, endpoint resolver, edge builder, evidence builder. | `tests/test_build_intact_protein_interactions.py`; direct-protein endpoint fixture. |
| `scripts/txgnn_kanban_watchdog.py` | watchdog script | ~624 lines | Board routing automation can create/release review gates. A bug causes process debt rather than code failure. | Keep as script but split pure board-state classifier from mutation/apply actions. | `tests/test_txgnn_kanban_watchdog.py`; dry-run/apply route fixtures. |

Broad stub/TODO scan found many defensive `except` blocks and fallbacks. Some are legitimate optional-runtime handling (`Django`, `LaminDB`, `FileNotFoundError`), but the riskiest style is broad `except:` or `except Exception` in core metric/promotion/write paths. Prioritize narrowing those only when the surrounding path is under test.

## 4. Artefact hygiene

### Code source

- `txgnn/` — core TxGNN library, legacy/original model/data/evaluation code.
- `manage_db/` — Jouvence KG builders, validators, migration/sync tools, LaminDB schema, PyG export, evidence tooling.
- `scripts/` — orchestration/watchdog and one-off support scripts.
- `tests/` — 59 `test_*.py` files covering schema, evidence, OpenTargets, PyG/GNN, LaminDB, embeddings, ReMap, CTGov, relation builders.

These should live in a real Git checkout/worktree. PR-ready changes should be migrated there.

### Durable reports / docs

- `docs/` — human-readable state, runbooks, validation/promotion reports. Keep curated docs in Git after migration if they are durable; large generated reports should be summarized, not all committed.
- `todo.d/` — lightweight human mirror of Kanban phases; useful and should remain versioned if kept concise.

### Staged artifacts

- `artifacts/staged/<task-id>/` — produced feature/edge/evidence candidates and embedding/PyG outputs. Some are real scientific artifacts; most should not be in Git. They need manifest/hash/status pointers in docs, not code review diffs.

### Reports

- `artifacts/reports/<task-id>/` — logs, validation JSON, backup manifests, and LaminDB `.bak` files. Small reports can support review; huge `.bak` files should be externalized/retention-managed.

### Scratch/cache

- `artifacts/cache/<task-id>/` — local source/cache data. Must not be committed. Requires explicit retention policy because anti-GCS-egress caching can consume local disk.
- UCSC/JASPAR `udc/.../sparseData` files are large/sparse and can be corrupted; they need a Mac-vs-GCP policy before re-download/rebuild.

### Legacy-only

- `.omoc` — retired; current top-level `.omoc` was not present, but legacy outputs exist under `artifacts/legacy_omoc_20260624_t_859cbca4/`.
- `.omx` — local operational/cache/log state, not source.
- `gs:/...` — local directory artifact that looks like a mistaken path interpretation; classify and ignore/remove only after a separate cleanup review.

## 5. Freeze plan

### Freeze now

1. Freeze canonical writes: no GCS canonical promotion, no LaminDB writes, no live syncs during cleanup.
2. Freeze PR-ready claims from `work/txgnn`.
3. Freeze new large local caches unless the task explicitly says why Vieta 7/Mac local is acceptable vs GCP server.
4. Freeze ReMap/JASPAR local re-download/rebuild until the corrupted `bigBedToBed`/UDC cache issue is classified and routed.
5. Freeze broad refactors in `manage_db/` until a clean Git checkout exists.

### Allow

1. Local read-only inspection.
2. Small docs/status reports under `docs/` or `artifacts/reports/`.
3. Creating a clean TxGNN worktree/clone.
4. Migrating minimal code/docs deltas into that clean checkout.
5. Small targeted tests on local fixtures.

### Resume urgent work without worsening debt

1. For urgent scientific/KG tasks, create a dedicated worktree from `jkobject/TxGNN`.
2. Use `work/txgnn/artifacts` only as input artifact store, not as code-diff source.
3. If a job needs >5–10 GiB scratch or repeated GCS reads, force an execution decision: local Vieta 7/Mac vs GCP server.
4. Keep every producer ending `review-required` routed to reviewer/tester/CTO before stopping.

## 6. Guardrails TxGNN

Agent checklist:

- Any PR-ready task must start from a real clone/worktree of `jkobject/TxGNN`, not `work/txgnn`.
- Never claim a diff is PR-ready from `work/txgnn`.
- Do not run `git init` in `work/txgnn`.
- No canonical KG write without explicit reviewer gate and current status docs.
- No LaminDB write during cleanup/audit work.
- No GCS write during cleanup/audit work.
- No delete of `.omoc` or historical artifacts without a separate manifest + retention decision.
- No “done” claim without the right validation for the lane:
  - endpoint anti-joins for KG edges,
  - evidence support audit where evidence exists,
  - targeted tests/py_compile for code paths,
  - manifest/hash/source-count checks for staged artifacts,
  - reviewer/tester acceptance for promotion or full-production claims.
- No placeholder Parquet to satisfy schema coverage.
- Relation names must be source-native; do not project gene/RNA rows into protein relations without explicit source/native policy.
- Status vocabulary must stay strict: `design done`, `pilot accepted`, `staged-only`, `review-required`, `validated`, `canonical promoted`, `production/full done`.
- For large data access: explicitly decide local cache vs GCP server vs GCS/FUSE; avoid blind repeated FUSE reads and avoid uncontrolled local caches.

## 7. Top 10 actions

1. **Create/choose a clean reviewable TxGNN clone/worktree** from `jkobject/TxGNN`; make it the only place for PR-ready code/docs.
2. Write a short `docs/reviewability_migration_status.md` in the clean checkout pointing back to this audit and `docs/git_reviewability_migration_t_4cab4a2f.md`.
3. Freeze `work/txgnn` as artifact/status workspace; update `TODO.md`/`todo.d/06_process.md` if needed to make that visible to every worker.
4. Inventory unmerged code/docs deltas in `work/txgnn` vs clean repo; migrate only minimal needed deltas, not generated artifacts.
5. Add/verify `.gitignore` rules in the clean repo for `artifacts/`, `.omoc/`, `.omx/`, `gs:/`, `.pytest_cache/`, `__pycache__/`, local venvs, and large generated outputs.
6. Establish artifact retention policy: keep small manifests/reports in docs; move/delete old `.bak` and caches only after manifest/remote-copy decision.
7. Refactor only one hotspot at a time, starting with paths that block current work: likely `build_pyg_export.py` or LaminDB sync adapters, not a wholesale framework rewrite.
8. Split `txgnn/utils.py::disease_centric_evaluation` behind tests before changing model/evaluation behavior.
9. Keep `manage_db/ingest_opentargets.py` stable until per-domain fixture tests are pinned; then extract variants/evidence/enhancers incrementally.
10. Route large ReMap/JASPAR and full embedding/GNN jobs to a Mac-vs-GCP decision gate before execution; record expected disk/RAM/cache and egress behavior in the Kanban card body.

## 8. No-op safety

During this audit I performed local reads and wrote this Markdown report only.

I did **not**:

- initialize Git in `work/txgnn`;
- delete files or directories;
- promote canonical KG files;
- write to GCS;
- write to LaminDB;
- run live KG sync;
- run mass GCS/FUSE reads.

The only filesystem mutation was creating this report file:

`docs/txgnn_agentic_mess_reviewability_audit_20260629.md`
