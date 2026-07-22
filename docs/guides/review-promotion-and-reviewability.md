# Review, promotion, rollback, and reviewability

[← Documentation index](../README.md) · [KG architecture](kg-architecture-and-evidence.md) · [Agent context](agent-context.md)

The normal delivery lane is:

```text
design → staged artifact → independent validation → promotion authorization
       → canonical write → post-write validation → independent acceptance
```

A staged validation never implicitly authorizes a canonical write. A successful canonical write remains `review-required` until the actual written objects are independently accepted.

## Status vocabulary

Use exact states:

- `design done` — policy or implementation design only;
- `pilot accepted` — bounded evidence accepted for its declared scope;
- `staged-only` — produced outside canonical paths;
- `review-required` — producer evidence exists but independent acceptance is pending;
- `validated` — declared checks passed for the stated object/scope;
- `canonical promoted` — canonical write and readback occurred;
- `production/full done` — intended full production scope is complete and accepted.

Never collapse smoke, staged validation, canonical promotion, and full completion into “done.”

## Promotion manifest

A promotion must record:

- exact object and relation scope;
- input identities, releases, hashes, and transformation policy;
- staged object paths and row/key counts;
- pre-write endpoint, duplicate, evidence, semantic, and leakage checks;
- explicit canonical-write authorization;
- copy/write method and rollback mechanism;
- staged/canonical parity and live readback after writing;
- proof that unrelated objects remained unchanged;
- residual risks and independent-review status.

Prefer immutable/versioned or copy-once objects and retain-with-labels cleanup over destructive rewrites. Deletion requires separate destructive approval and independently reviewed recovery evidence.

## Role separation

- **Builder:** creates the implementation or staged artifact and reports exact evidence.
- **Tester:** validates behavior/data from a consumer and scientific perspective.
- **Reviewer:** challenges semantics, scope, provenance, leakage, and false-pass risks.
- **Promotion operator:** performs only the authorized canonical write and verifies readback.

A reviewer must be dispatchable. Do not make a review card depend on a producer that is already blocked awaiting that same review; this creates a workflow deadlock rather than a gate.

## Reviewable code and documentation

`/Users/jkobject/Documents/jouvence` is the canonical local Jouvence checkout and project-level review surface. Task worktrees live under `/Users/jkobject/Documents/jouvence/.worktrees/`; ignored artifacts are never part of a review unless explicitly force-added and justified.

For reviewable changes:

1. use the canonical `work/txgnn` worktree or a task worktree of `jkobject/TxGNN`;
2. record the base repository and commit;
3. copy only the intended files/delta from any dirty source;
4. inventory provenance for copied files;
5. run tests in the clean worktree;
6. report the exact diff and head that the reviewer will inspect;
7. keep caches, large artifacts, credentials, and unrelated workspace changes out of the branch.

Never `git init` another TxGNN directory, maintain a second canonical checkout under `~/code`, or describe ignored artifact contents as part of a TxGNN-scoped diff.

## Validation must challenge false passes

A useful reviewer checks more than commands and exit codes:

- the tested object is the object intended for promotion;
- bounded evidence is not presented as full coverage;
- edge/evidence parity did not rely on synthesized placeholders;
- relation semantics match the source;
- checks ran on the correct host, instance, branch, and artifact generation;
- post-write readback validates canonical objects rather than staged copies;
- rollback assets exist and are actually usable;
- no out-of-scope resource or object changed.

## Authoritative detailed sources

- [`../kanban_status_hygiene.md`](../kanban_status_hygiene.md)
- [`../git_reviewability_migration_t_4cab4a2f.md`](../git_reviewability_migration_t_4cab4a2f.md)
- [`../txgnn_agentic_mess_reviewability_audit_20260629.md`](../txgnn_agentic_mess_reviewability_audit_20260629.md)
- Local generated report (not versioned): `artifacts/reports/t_ade56294/source_isolation.md`
- [`../mutation_in_gene_canonical_promotion_t_1cfcd48f.md`](../mutation_in_gene_canonical_promotion_t_1cfcd48f.md)
- [`../remap_crm_full_support_sidecar_canonical_promotion_t_f2a2952e.md`](../remap_crm_full_support_sidecar_canonical_promotion_t_f2a2952e.md)
