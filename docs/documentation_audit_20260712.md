# Documentation hierarchy audit — 2026-07-12

## Decision

Unify all durable TxGNN/Jouvence knowledge under `docs/`. Stable doctrine lives in `docs/guides/`; useful historical documentation lives in `docs/history/`. Legacy compatibility stubs were removed after repository-internal references were migrated.

## Classification

| Surface | Classification | Action |
| --- | --- | --- |
| `README.md` | KEEP + EDIT | Keep as the public GitHub façade; route readers to installation, API usage, contribution, Jouvence architecture, and `docs/README.md`. |
| `AGENTS.md` | KEEP + EDIT | Keep as the only agent boot file and point to scoped `docs/guides/` pages. |
| `TODO.md` | KEEP | Keep as the compact current-state mirror; Kanban remains live truth. Its large historical detail should be reduced in a later status-hygiene pass, not rewritten without a fresh board audit. |
| `todo.d/` | MERGE LATER | Retain current phase mirrors. They overlap `TODO.md` and should eventually be folded into a smaller current-state structure after live status reconciliation. |
| Stable doctrine pages | MERGE | Canonical content lives in `docs/guides/`; redundant compatibility pages were removed after complete comparison. |
| Legacy documentation index | MERGE | Navigation is provided by `docs/README.md`; the redundant compatibility index was removed. |
| Documentation maintenance log | MERGE | Useful provenance moved to `docs/history/documentation-change-log.md`. |
| Superseded agent boot snapshot | MERGE | Useful historical context summarized in `docs/history/agent-boot-2026-06-29.md`; current instructions remain in root `AGENTS.md`. |
| Core policy/runbook documents in `docs/` | KEEP | Preserve KG provenance, source/edge/evidence policy, PyG, LaminDB, VM/GCS, storage, and review evidence. |
| Task-ID reports in `docs/` | KEEP | They are provenance and promotion evidence. Do not delete based only on apparent duplication. |
| `.omoc` references in historical docs | HISTORICAL CONTEXT | Preserve as historical evidence; active instructions continue to prohibit new `.omoc` work. |

## Duplicate and dependency findings

- The former secondary index duplicated navigation already implicit across `README.md`, `AGENTS.md`, and many `docs/` links; `docs/README.md` is now the single durable index.
- `agent-context.md` duplicated boot and operating rules from `AGENTS.md`; it remains a detailed role/validation guide, while `AGENTS.md` stays short and mandatory.
- `lessons-learned.md` intentionally synthesizes several policy documents; it is retained as synthesis rather than treated as a duplicate.
- `TODO.md`, `todo.d/`, and `docs/current_state_20260623.md` overlap and contain dated state. They were not merged automatically because doing so safely requires a fresh Kanban/live-system reconciliation.
- Source code and manifests refer extensively to exact `docs/*.md` policy/report paths. Those paths were preserved.
- Active root docs and reports now reference the canonical `docs/guides/...` and `docs/history/...` paths directly.
- No TxGNN script was found to require the removed compatibility files as executable input. References were documentary/status paths.

## Boundaries and residual work

- This directory is a shared artifact workspace, not an independent TxGNN Git checkout. Parent-repository `git status` is not a TxGNN-scoped diff.
- No canonical KG, GCS object, LaminDB row, VM, cron, bucket, or process was changed.
- No `pert-gym` resource or file was inspected or modified.
- A later clean-worktree migration should carry this exact documentation delta into `jkobject/TxGNN` and run the repository's normal review flow.
- This migration changed documentation only; no code, infrastructure, catalog, or data artifact was modified.
