# 06 — Process / board hygiene

## Problem

The board has many complex, multi-card tasks. We must not call something `done` when it is only:

- `design done`,
- `pilot accepted`,
- `staged-only`,
- `review-required`,
- `validated` but not promoted,
- or `canonical promoted` but not full production scope.

## Active card

- `t_caacd3d1` — process hygiene: `todo.d/` mirror, honest status labels, automatic review routing.
- `t_859cbca4` — repo/workspace cleanup: active `.omoc` moved to `artifacts/legacy_omoc_20260624_t_859cbca4/`; git/worktree issue documented pending migration/review.
- `t_4cab4a2f` — git-reviewability decision: use existing `jkobject/TxGNN` repo, migrate reviewable deltas into `/Users/jkobject/.openclaw/worktrees/txgnn/<branch-or-task-id>/`, quarantine invalid sibling `.git` dirs only after manifest + review. Plan: `docs/git_reviewability_migration_t_4cab4a2f.md`.

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
3. Status summaries must say `design done`, `pilot accepted`, `staged-only`, `review-required`, `validated`, `canonical promoted`, or `production/full done` explicitly.
4. `todo.d/` mirrors major Kanban phases for human readability; Kanban remains dispatch source of truth.
5. Do not recreate `.omoc` for new scratch reports/staged tranches. Use `artifacts/`, `docs/`, or GCS staging. During `t_859cbca4`, no active `.omoc` process was found and the legacy tree was moved to `artifacts/legacy_omoc_20260624_t_859cbca4/` with manifest `artifacts/reports/t_859cbca4_omoc_manifest.json`.

## Definition of process done

This process phase is `validated` only when:

1. `todo.d/README.md` and phase files reflect current major waves/card IDs;
2. `docs/kanban_status_hygiene.md` is present;
3. `scripts/txgnn_kanban_watchdog.py --json` reports all current `review-required` producers routed; and
4. `scripts/txgnn_kanban_watchdog.py --silent` is silent and exits `0` when all routes are healthy.
