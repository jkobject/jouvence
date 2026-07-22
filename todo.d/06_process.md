# 06 — Process / board hygiene

_Status snapshot: 2026-07-22 15:18 CEST._

## Problem

The board has many complex, multi-card tasks. We must not call something `done` when it is only:

- `design done`,
- `pilot accepted`,
- `staged-only`,
- `review-required`,
- `validated` but not promoted,
- `canonical candidate` but not promoted,
- `stopped-by-user`,
- or `canonical promoted` but not full production scope.

## Active card

- `t_caacd3d1` — process hygiene: `todo.d/` mirror, honest status labels, automatic review routing.
- `t_859cbca4` — repo/workspace cleanup: active `.omoc` moved to `artifacts/legacy_omoc_20260624_t_859cbca4/`; git/worktree issue documented pending migration/review.
- `t_4cab4a2f` — git-reviewability migration executed: `/Users/jkobject/Documents/jouvence` is the canonical checkout and task worktrees live under `/Users/jkobject/Documents/jouvence/.worktrees/<branch-or-task-id>/`. The older decision report remains historical context.
- `t_265da758` — current mirror synchronization and deterministic drift guard.

## Current major routes

- `t_5c938f23` / reviewer `t_0b806c0e` — corrected human-ENSG migration implementation accepted and merged in PR #12 (`2786d847`, corrected head `7f300b8`); production staged rebuild and canonical node migration remain outstanding. The old `t_8b9cdabc` candidate is rejected historical evidence.
- `t_2d54477b` → `t_2e6b355f` — immutable embeddings v2 producer/reviewer route: reviewer returned `validated` PASS; v1 remains historical/rejected.
- `t_8b9cdabc` → `t_3c7766fa` — DepMap revision-2 dependency: PR #11 code/tests are ready at `e40e2508b8f061f70fc7a4fcbf05b0f4a1accfaf`, but the full staged artifact is not built until the ENSG heavy slot releases.
- `t_d3b876b3` — gene NT is `stopped-by-user` at 6,912 / 78,164 non-canonical scratch rows; no auto-resume.
- `t_ce839966` and `t_075f5353` — superseded historical +158,505 non-human Lamin Gene cards; inert and must not run.

## Process doc

- `docs/kanban_status_hygiene.md` defines the vocabulary, producer handoff rule, watchdog rule, `.omoc` avoidance rule, and promotion definitions.

## Watchdog

- Script: `scripts/txgnn_kanban_watchdog.py`.
- Default behavior: read-only dry-run.
- Safe checks:
  - `python scripts/txgnn_kanban_watchdog.py --json`
  - `python scripts/txgnn_kanban_watchdog.py --silent`
- Mutation mode: `python scripts/txgnn_kanban_watchdog.py --apply` from a trusted operator/cron context only.

The watchdog scans blocked TxGNN producer cards with `review-required` handoffs and requires either:

1. a linked child assigned to `reviewer`, `tester`, or `cto`; or
2. an explicit routed-comment reviewer/tester card when parent-linking would deadlock a blocked producer.

## Current review-required routes observed during this card

- `t_c51d9a5b` — Lamin schema activation producer: linked tester child `t_edb59ab8` (`todo`). Status: `review-required/admin-required`, not validated and not production/full done.
- `t_cd7fec1f` — REL-WAVE-E evidence-only builder: linked tester child `t_18159206` (`todo`). Status: `review-required`, staged-only/evidence-only, not canonical promotion.
- `t_8eeb17bc` — REL-WAVE-A genomic direct builder: linked tester child `t_22d3afab` (`todo`). Status: `review-required`, bounded staged-only smoke, not full all-part rebuild; reviewer later rejected `mutation_overlaps_enhancer` as canonical edge material unless stronger regulatory evidence is selected.
- `t_34f5b642` — REL-WAVE-E QA JSON restoration fix: explicit ungated reviewer route `t_00459dfe` in producer comment. Status: `review-required`, artifact restoration pending review.

## Rules

1. Every producer that can block with `review-required` must have a reviewer/tester/CTO route before the worker stops.
2. Reviewer cards must not be accidentally deadlocked behind an already-blocked producer; use an explicit routed-comment reviewer card when needed.
3. Status summaries must say `design done`, `pilot accepted`, `staged-only`, `review-required`, `validated`, `canonical candidate`, `canonical promoted`, `stopped-by-user`, or `production/full done` explicitly.
4. `todo.d/` mirrors major Kanban phases for human readability; Kanban remains dispatch source of truth.
5. Do not recreate `.omoc` for new scratch reports/staged tranches. Use `artifacts/`, `docs/`, or GCS staging. During `t_859cbca4`, no active `.omoc` process was found and the legacy tree was moved to `artifacts/legacy_omoc_20260624_t_859cbca4/` with manifest `artifacts/reports/t_859cbca4_omoc_manifest.json`.
6. Before merging a mirror update, run `uv run --group dev python scripts/check_status_mirror_drift.py --expected-date 2026-07-22`. Change the expected date together with `TODO.md` and all six phase mirrors; superseded cards may appear only when explicitly marked historical/inert.

`AGENTS.md` was reviewed for `t_265da758` and did not need a change: its operating rules remain short, status-free, and current.

## Definition of process done

This process phase is `validated` only when:

1. `todo.d/README.md` and phase files reflect current major waves/card IDs;
2. `docs/kanban_status_hygiene.md` is present;
3. `scripts/txgnn_kanban_watchdog.py --json` reports all current `review-required` producers routed; and
4. `scripts/txgnn_kanban_watchdog.py --silent` is silent and exits `0` when all routes are healthy.
5. `scripts/check_status_mirror_drift.py --expected-date <snapshot-date>` passes for `TODO.md`, all six phase mirrors, and current/historical routing invariants.
