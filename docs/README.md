# TxGNN / Jouvence documentation

This directory is the single home for durable project knowledge. Start at the repository [`README.md`](../README.md) for the public project overview, [`AGENTS.md`](../AGENTS.md) for agent boot rules, and [`TODO.md`](../TODO.md) for the current work mirror.

## Choose a route

| Need | Read |
| --- | --- |
| KG topology, evidence, metadata, features, and proof | [`guides/kg-architecture-and-evidence.md`](guides/kg-architecture-and-evidence.md) |
| Source-native relation and endpoint policy | [`guides/source-native-modeling.md`](guides/source-native-modeling.md) |
| Agent role routing and validation recipes | [`guides/agent-context.md`](guides/agent-context.md) |
| PyG export and embedding contracts | [`guides/pyg-and-embedding-contracts.md`](guides/pyg-and-embedding-contracts.md) |
| Review, promotion, rollback, and Git reviewability | [`guides/review-promotion-and-reviewability.md`](guides/review-promotion-and-reviewability.md) |
| LaminDB, VM, GCS, checkpoints, and recovery | [`guides/lamindb-porting-operations.md`](guides/lamindb-porting-operations.md) |
| Cross-cutting lessons | [`guides/lessons-learned.md`](guides/lessons-learned.md) |

## Authoritative detailed documents

### Schema, provenance, and source policy

- [`kg_schema_overview.md`](kg_schema_overview.md) — dated schema and relation inventory.
- [`relation_coverage_current.md`](relation_coverage_current.md) — dated per-relation coverage mirror.
- [`evidence_and_edge_schema_plan.md`](evidence_and_edge_schema_plan.md) — assertion/evidence separation.
- [`source_native_expansion_policy.md`](source_native_expansion_policy.md) — source and endpoint policy.
- [`source_measure_edge_matrix.md`](source_measure_edge_matrix.md) — source/measurement/relation decisions.
- [`inferred_edges_policy.md`](inferred_edges_policy.md) — inferred and contextual assertions.

### PyG, GNN, and embeddings

- [`pyg_export_runbook.md`](pyg_export_runbook.md) — bounded and production export operations.
- [`pyg_mapping_design.md`](pyg_mapping_design.md) and [`pyg_manifest_metadata_contract_t_a3b15bc8.md`](pyg_manifest_metadata_contract_t_a3b15bc8.md) — mapping and manifest contracts.
- [`foundation_embedding_policy.md`](foundation_embedding_policy.md) and [`edge_evidence_embedding_policy.md`](edge_evidence_embedding_policy.md) — feature and embedding policy.

### LaminDB, VM, and storage

- [`lamindb_kg_export_design.md`](lamindb_kg_export_design.md) — catalog/sync architecture.
- [`txgnn_access_runbook.md`](txgnn_access_runbook.md) — GCS and bounded local access.
- [`txgnn_worker_disk_migration_t_3cf62bd8.md`](txgnn_worker_disk_migration_t_3cf62bd8.md) — worker disk migration and rollback evidence.
- [`storage.md`](storage.md) — storage layout and constraints.

### Process and reviewability

- [`kanban_status_hygiene.md`](kanban_status_hygiene.md) — exact status vocabulary.
- [`git_reviewability_migration_t_4cab4a2f.md`](git_reviewability_migration_t_4cab4a2f.md) — clean clone/worktree migration.
- [`documentation_audit_20260712.md`](documentation_audit_20260712.md) — hierarchy audit and migration record.

### Documentation history

- [`history/documentation-change-log.md`](history/documentation-change-log.md) — dated documentation migration log.
- [`history/agent-boot-2026-06-29.md`](history/agent-boot-2026-06-29.md) — superseded agent-context snapshot retained as historical evidence.

## Information lifecycle

- **Root `README.md`:** public GitHub façade—purpose, installation, usage, contribution, and documentation routes.
- **Root `AGENTS.md`:** short mandatory boot file—scope, safety, source-of-truth routing.
- **Root `TODO.md`:** current human/agent mirror; Kanban remains live execution truth.
- **`docs/guides/`:** stable doctrine and runbooks.
- **Other `docs/*.md`:** dated designs, policies, audits, validation, and promotion evidence.
- **`artifacts/`:** generated reports, manifests, logs, and staged outputs; not the documentation entry point.

A dated document does not prove current live state. Re-query Kanban, GCS, LaminDB, or the worker before making a live-status claim.
