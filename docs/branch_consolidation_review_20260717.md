# TxGNN branch consolidation review — 2026-07-17

## Scope and safety

- Review base: `origin/main` at `ad0c2e3de8522025fc0f2d6a3f76caa0658d0e39`.
- Prepared branch: `consolidate/branch-cleanup-20260717`.
- Worktree: `/Users/jkobject/.openclaw/worktrees/txgnn/branch-consolidation-20260717`.
- No push, remote branch deletion, PR closure, or mutation of `origin/main` was performed by this consolidation pass.
- Historical branches were never merged wholesale. Focused commits were replayed onto current `main`; current schema/code won every conflict.

## Executive decision

The remote branches should **not** all be merged as branches. Most old branches consist of code already absorbed by patch plus worker handoff files, or obsolete code that conflicts with the current KG schema.

The useful unique work has been consolidated locally:

1. leak-free and multi-relation/multi-primary PyG smoke work from PR #3;
2. embedding production scaffold from PR #4;
3. local GCS cache/FUSE-free smoke from PR #5, plus a missing fix that deletes stale optional cache entries;
4. exact accepted Parquet catalog head from PR #7;
5. public notebooks from PR #8, including requester-pays project separation;
6. OpenTargets ingestion code accidentally truncated by `a70bb42`, restored from its parent and reconciled with the current canonical relation directions.

PR #2 and PR #6 must not be merged wholesale: both are superseded by newer code in `main`, and their old heads retain review defects.

## Remote branch decisions

| Branch | Last activity | Audit | Decision |
|---|---:|---|---|
| `phase3-kg-migration` | 2026-03-03 | 0 commits ahead; fully ancestor/absorbed | Delete after review; nothing to merge |
| `claude/wizardly-wu` | 2026-03-03 | only commit is patch-equivalent on `main`; remaining delta is stale `CLAUDE.md` | Delete after review |
| `feat/schema-xref-redesign` | 2026-03-02 | schema commit patch-equivalent on `main` | Delete after review |
| `claude/youthful-sanderson` | 2026-03-05 | substantive code, coding standards, and notebook are byte-identical to main commit `0b9af2d`; only stale `CLAUDE.md` differs | Delete after review; nothing to salvage |
| `chore/i1-bionty-pertdb-ingest` | 2026-06-10 | implementation patch-equivalent; only unique commit is worker handoff material | Delete after review |
| `chore/i2-custom-records-node-sync` | 2026-06-10 | implementation patch-equivalent; only unique commit is worker handoff material | Delete after review |
| `chore/paper-ingest` | 2026-06-10 | implementation patch-equivalent; only unique commit is worker handoff material | Delete after review |
| `feat/phase6-credibility` | 2026-06-10 | implementation patch-equivalent; only unique commit is worker handoff material | Delete after review |
| `feat/phase7-parquet` | 2026-06-10 | three commits patch-equivalent; only unique commit is worker handoff material | Delete after review |
| `migrate/artifact-workspace-20260624-t_4cab4a2f` (PR #2) | 2026-06-24 | old migration base; merging tip would remove/rewind large parts of current repo; old inline review blockers | Close as superseded; delete branch after consolidation lands |
| `feat/t_fdb7423e-pyg-gnn-run` (PR #3) | 2026-06-24 | five useful focused commits above migration base | Useful work ported; close as superseded after consolidation lands |
| `feat/t_8892763b-foundation-embeddings` (PR #4) | 2026-06-24 | useful scaffold; stacked on migration base | Focused commit ported; close after consolidation lands |
| `fix/t_28e02c47-fuse-smoke` (PR #5) | 2026-06-24 | useful cache path; P2 stale-cache review defect remained | Focused commit ported and P2 fixed; close after consolidation lands |
| `feat/t_678057ab-lamin-bulk-loader` (PR #6) | 2026-06-24 | old loader already superseded by more advanced current implementation; old P1/P2 review blockers | Close without merge; delete branch |
| `docs/t_c45c2004-parquet-catalog` (PR #7) | 2026-07-17 | exact reviewer-accepted head `51274e6`; directly mergeable and clean against current base | Exact three-commit head ported into the single consolidation path; direct merge would also be safe if landed separately |
| `feat/t_3de2db50-public-notebooks` (PR #8) | 2026-07-16 | useful notebooks; stacked on obsolete PR #2; requester-pays fix present | Three unique commits rebased/ported onto current main with README/dependency conflicts resolved |
| `main` | 2026-07-17 | current remote base `ad0c2e3` | Advance only after human review of consolidation |

## Local-only refs/worktrees

- `review/recover-shared-work-20260717` currently equals `origin/main`; delete locally after consolidation lands.
- `main` in `/Users/jkobject/.openclaw/real-clones/TxGNN` is one commit behind `origin/main`; fast-forward it after review.
- `fix/t_95eca063-pyg-manifest-policy` and `fix/t_d7f9c01a-lamin-observability` point to `a70bb42` and have no unique commit. Their worktrees can be removed after confirming no external process still uses them.

## Integration commits prepared

```text
dd1f136 docs: record bounded PyG GNN subset run
7940bb4 fix: add leak-free heldout PyG smoke eval
2523974 test: cover PyG GNN smoke CLI scale report
cb39a4a test: record multi-relation PyG GNN smoke
3448143 test: support multi-primary PyG GNN smoke
cae26bb feat: scaffold foundation embedding production plan
c7612dd fix: make embedding smoke reproducible without FUSE
4d614fa fix: drop stale optional embedding cache inputs
ae08f30 docs: add generated Parquet dataset catalog
50e0fc1 fix: make Parquet catalog checks truthful
90776fb fix: address Parquet catalog review comments
6ca2961 feat: add public Jouvence notebook suite
3779b4b fix: make notebook generation deterministic
1a2eade fix: separate requester-pays billing project
77ac7c0 test: preserve modern PyG fixtures during branch consolidation
c650588 fix: restore OpenTargets ingestion paths lost during packaging
```

## OpenTargets corruption found during branch review

Commit `a70bb42` changed `manage_db/ingest_opentargets.py` by `+99/-620` lines. A broad deletion accidentally truncated:

- evidence edge/evidence finalization;
- GO ingestion;
- target-essentiality dataset/gene context;
- gene-to-protein expression projection.

The stale test that imported `ingest_literature` was also contradictory: its `paper_mentions_gene` and `paper_mentions_disease` relations are explicitly forbidden by `tests/test_kg_schema_cleanup.py`. That obsolete test was removed, while the remaining 15 OpenTargets tests were made runnable.

Restoration used `a70bb42^` for the three truncated functions, then reconciled them with current doctrine:

- `disease_associated_gene`: gene → disease;
- `disease_involves_pathway`: pathway → disease;
- GO pathway nodes carry required `go_id`, `reactome_id`, and `kegg_id` columns;
- protein projections document `projected_via_protein_node_xref`.

## Verification

Focused integration suite:

```text
32 passed
```

OpenTargets suite after restoration:

```text
15 passed
```

Full suite:

```text
310 passed, 6 skipped, 2 deprecation warnings
```

Additional gates:

- `git diff --check origin/main..HEAD`: pass;
- Python compilation of touched modules/tests: pass;
- working tree clean after commits: required before final handoff;
- no generated data/artifact directories were added.

## Proposed review/landing sequence

1. Human reviews `origin/main..consolidate/branch-cleanup-20260717` locally.
2. If accepted, push only the consolidation branch and merge it into `main` through one reviewed PR or an explicitly approved fast-forward strategy.
3. Re-run the exact full suite at the immutable pushed SHA.
4. Close PRs #2–#8 with links to the consolidation outcome and an explicit “superseded/ported” reason.
5. Delete the listed remote branches only after `main` contains the reviewed consolidation SHA.
6. Prune local refs/worktrees and fast-forward the canonical local `main`.
