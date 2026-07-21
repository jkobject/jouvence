# Jouvence rename occurrence inventory — t_2e26fc60

This is the bounded occurrence inventory for the 2026-07-17 product/repository rename. It distinguishes product branding from upstream/history and technical compatibility identifiers; it is not a claim that every historical `TxGNN` byte has been rewritten.

## Rename now

- Public repository/product surfaces: root `README.md`, `AGENTS.md`, `TODO.md`, `docs/README.md`, `docs/guides/agent-context.md`, and the current access runbook now lead with **Jouvence** and point to `https://github.com/jkobject/jouvence-graph`.
- Python project metadata: distribution metadata is `Jouvence`; homepage/repository point to `jkobject/jouvence-graph`; the description explicitly acknowledges upstream TxGNN.
- Current notebook presentation: reproducibility README, active setup/build notebooks 3–8, Lamin explorer 11, PyG/Lamin notebook 14, and current schema overview/status titles use Jouvence product branding.
- Notebook configuration: `JOUVENCE_*` is primary in the active setup/build notebooks, with matching `TXGNN_*` fallback aliases. `manage_db.jouvence_env.get_jouvence_env` provides a warning-producing compatibility helper for Python callers.
- CLI/user-facing output: current OpenTargets ingest, KG validation/audit commands, public-notebook error text, Lamin artifact descriptions, ClinicalTrials.gov user agents, and the Kanban watchdog label use Jouvence.

## Preserve upstream/history

- `https://github.com/mims-harvard/TxGNN`, the TxGNN paper/method name, `txgnn.org`, the TxGNN figure, citation prose, and reproduction/API examples are explicit upstream scientific references.
- Source/evidence values such as `source="TxGNN"`, `txgnn_legacy_*`, and comments explaining legacy TxData/TxGNN semantics are provenance, not Jouvence branding.
- Dated audits, promotion reports, validation reports, executed notebooks, and `docs/history/` retain the names that were true when the evidence was produced. They were not bulk-edited.
- Existing artifact URIs, `gs://jouvencekb`, `jkobject/jouvencekb`, `txgnn-worker`, and canonical/FUSE paths remain unchanged.

## Compatibility migration later

- Python import package `txgnn`, public classes (`TxGNN`, `TxData`, `TxEval`), `lnschema_txgnn`, persisted Lamin/schema identifiers, and the package version attribute remain unchanged. A future alias package requires an independently designed release/deprecation plan.
- Local directories/worktrees, Kanban board slug `txgnn`, watchdog/script filenames, test filenames, VM name `txgnn-worker`, and the `docs/txgnn_access_runbook.md` filename remain stable so automation and historical links do not break.
- Dated summary notebooks 9A/9C/9D retain `TXGNN_*` flags as historical executable evidence. Migrating them requires regenerating/revalidating their paired tests and evidence claims rather than a blind JSON replacement.
- The JSON Schema `$id` under the former repository URL is preserved pending an explicit schema-version and redirect/alias decision; changing an identifier is not equivalent to changing a documentation link.
- The nested `manage_db/lnschema_txgnn` distribution metadata remains tied to the persisted schema package. Rename only with a tested dual-package/import migration.

## Search boundary

Targeted searches covered root public/current guidance, project metadata, current scripts and tests, `manage_db` user-facing strings, notebook titles/prose/configuration, repository URLs, and filenames containing `txgnn`. Historical reports and stored result data were classified but not opened or rewritten unless they were current contributor guidance named above.
