# Repo/workspace cleanup report — `t_859cbca4`

Date: 2026-06-24
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`

## Summary

This cleanup stabilized the active TxGNN/Jouvence worker context before the next production wave. The active boot docs and TODO mirrors now reflect the current state: `lnschema_txgnn` is locally activated but not full/queryable schema coverage, `mutation_affects_transcript` is canonical-promoted/review-accepted, `mutation_in_gene` remains staged/deferred, `mutation_overlaps_enhancer` remains staged/context/feature-only, ReMap CRM remains support/QA only, PyG/GNN and embeddings are not production/full done.

## Changed files / artifacts

- `CLAUDE.md`
  - Added explicit git/reviewability caveat.
  - Updated LaminDB status from “activation required” to “locally activated; schema/query coverage incomplete”.
  - Updated mutation genomic direct status to distinguish canonical `mutation_affects_transcript` from deferred/staged relations.
  - Removed ambiguous active `.omoc` cache wording.
- `TODO.md`
  - Updated active LaminDB, mutation genomic direct, and git blocker sections.
  - Added `t_3d4fa114` as post-activation full schema/query API coverage work.
- `docs/current_state_20260623.md`
  - Added git/workspace status section.
  - Reworded retired `.omoc` policy to avoid any active write instruction.
- `todo.d/01_lamindb.md`
  - Clarified local activation status and remaining exact-ID/query coverage gaps.
- `todo.d/04_relations.md`
  - Updated mutation-specific path with `t_f32f1f5b`/`t_225ae18c` canonical transcript promotion and deferred gene/enhancer relations.
- `todo.d/06_process.md`
  - Recorded this cleanup and legacy `.omoc` move.
- `artifacts/reports/t_859cbca4_omoc_manifest.json`
  - Manifest for preserved legacy `.omoc` tree.
- `artifacts/legacy_omoc_20260624_t_859cbca4/`
  - Full moved legacy `.omoc` contents; 41 files, 317,077,384 bytes.
- `docs/repo_cleanup_t_859cbca4.md`
  - This report.

## Git / worktree diagnosis

`work/txgnn` is not currently an independent git checkout: there is no `.git` under `/Users/jkobject/.openclaw/workspace/work/txgnn`. Running git inside it falls back to parent repo `/Users/jkobject/.openclaw/workspace`.

Observed command:

```bash
git -C /Users/jkobject/.openclaw/workspace/work/txgnn status --short --branch
```

Observed result:

```text
fatal: 'work/jkobject.github.io/.git' not recognized as a git repository
```

Root cause found during cleanup: sibling path `/Users/jkobject/.openclaw/workspace/work/jkobject.github.io/.git` exists as an incomplete directory and is missing at least `HEAD`, `config`, and `index`. Because TxGNN falls through to the parent workspace repo, the broken sibling nested `.git` breaks parent `git status` and makes TxGNN non-PR-reviewable from this shared directory.

Safest action taken here: document the blocker in active boot docs rather than initializing a new repo in-place or deleting/rewriting a sibling `.git` outside this task workspace. A follow-up fix/migration card should decide whether to:

1. repair or remove the broken `work/jkobject.github.io/.git` from the parent workspace; and
2. migrate `work/txgnn` into a dedicated GitHub repo or proper git worktree so future TxGNN diffs are reviewable.

## `.omoc` scratch/cache cleanup

Before cleanup:

```text
.omoc existed, size 302M, no active process matched txgnn/.omoc/jouvencekb.
```

Action:

```text
Moved .omoc -> artifacts/legacy_omoc_20260624_t_859cbca4/
Wrote manifest -> artifacts/reports/t_859cbca4_omoc_manifest.json
```

After cleanup:

```text
PASS_no_active_omoc
```

Known remaining references are historical/read-only or code comments/tests that import legacy scripts; active guidance now says new work must use `artifacts/`, `docs/`, or GCS staging.

## Kanban-facing cleanup

- Ran `scripts/txgnn_kanban_watchdog.py --json`.
- Result: healthy, `missing_routes: 0`.
- Current reported routed producer: `t_4b1227b3` has follow-up fix card `t_590a4bb7` and is not silently unblocked.
- No intentional guard was unblocked by this cleanup.

## Verification commands

```bash
python scripts/txgnn_kanban_watchdog.py --json
```

Result: exit `0`; JSON included `"healthy": true`, `"missing_routes": 0`.

```bash
uv run python -m py_compile manage_db/kg_schema.py manage_db/kg_evidence.py manage_db/backfill_edge_evidence.py manage_db/ingest_opentargets.py manage_db/kg_queries.py manage_db/build_pyg_export.py scripts/txgnn_kanban_watchdog.py
```

Result: exit `0`; only warning was that the ambient Hermes `VIRTUAL_ENV` differs from project `.venv` and is ignored by `uv`.

```bash
git -C /Users/jkobject/.openclaw/workspace/work/txgnn status --short --branch
```

Result: expected failure remains and is documented above.

```bash
test ! -e /Users/jkobject/.openclaw/workspace/work/txgnn/.omoc && echo PASS_no_active_omoc
```

Result: `PASS_no_active_omoc`.

Targeted stale-phrase checks after patch:

- `activation is still required`: no active boot/TODO hit.
- `exact-ID registry activation is still required`: no active boot/TODO hit.
- `Policy-aware 25k tranche exists staged-only/QA; not canonical and not full all-part`: no active boot/TODO hit.

## Remaining risks / blockers

1. Git/reviewability is not fixed in-place. This shared directory still cannot produce a clean PR diff until the parent/sibling `.git` issue and TxGNN repo/worktree ownership are fixed.
2. Legacy tests under `tests/` still refer to old `.omoc/scripts/...` loaders. The legacy scripts are preserved under `artifacts/legacy_omoc_20260624_t_859cbca4/`; a separate code cleanup should either migrate those scripts into `scripts/` or mark the tests as historical/skipped.
3. `docs/current_state_20260623.md` remains date-stamped from the previous day; content is current as of this cleanup, but a future state snapshot should use a fresh dated filename.
4. No canonical KG writes or Lamin remote/admin changes were performed by this cleanup.

## Next-wave cards unblocked by context cleanup

This cleanup does not validate or promote the next-wave production work itself. It removes stale-context risk for these lanes to resume with honest labels:

- LaminDB / `lnschema_txgnn`: continue validation/review/schema-query coverage (`t_edb59ab8`, `t_59139647`, `t_3d4fa114`, `t_ad32fe14`, `t_7120233a`, `t_3a388f93`).
- PyG/GNN runtime: continue full/representative export and real HeteroData/GNN smoke (`t_015bd9a4`, `t_1d1eb3a1`, `t_468db80e`).
- Real embeddings: continue corrected policy and real node/edge embeddings (`t_6b3c1294`, `t_f8bae791`, `t_34836f1c`, `t_384b9594`).
- ReMap CRM support/QA: continue larger/full feasible CRM support artifact only, not canonical observed binding (`t_b599d3bb`, `t_3a7a8c9c`, `t_9b96ea36`).
- Mutation genomic direct: treat only `mutation_affects_transcript` as canonical-promoted; keep `mutation_in_gene` and `mutation_overlaps_enhancer` deferred/staged until separate acceptance.
