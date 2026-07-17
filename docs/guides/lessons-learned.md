# TxGNN / Jouvence KG — Lessons learned

[← Documentation index](../README.md) · [KG architecture](kg-architecture-and-evidence.md) · [Source-native modeling](source-native-modeling.md) · [PyG/embeddings](pyg-and-embedding-contracts.md) · [Review/promotion](review-promotion-and-reviewability.md)

This page compiles durable lessons from the June–July 2026 build. It is doctrine, not a live status report. Each lesson points to deeper design or evidence documents rather than duplicating every dated count and card outcome.

## Model what the source asserts, not what an ID join can invent

The most important scientific rule is source-native semantics:

- gene-level rows remain gene-level;
- transcript relations require source-native transcript/UTR/isoform endpoints;
- protein relations require direct protein/isoform identifiers or measurements;
- motif hits are predicted support, not observed TF binding;
- coordinate overlap is context unless the source supports a stronger regulatory assertion;
- associations, correlations, predictions, physical containment, and causal mechanisms must remain distinct.

An identifier projection can be useful for mapping, but it does not upgrade the biological assertion. Never turn an ENSG target into a protein edge, expand enhancer→gene to all transcripts, or call a VEP target physical containment without relation-specific proof.

Sources: [`../source_native_expansion_policy.md`](../source_native_expansion_policy.md), [`../kg_schema_overview.md`](../kg_schema_overview.md), [`../mutation_genomic_relations_promotion_policy.md`](../mutation_genomic_relations_promotion_policy.md).

## Stable relations, rich evidence

Edges are deduplicated graph assertions. Evidence rows carry the multiplicity and source nuance: predicate, assay, score, study, biosample, effect, direction, release, source record, and provenance.

This avoids relation-name explosion while preserving what makes each source scientifically different. One edge may have many evidence rows. Missing evidence must remain visible; never fabricate support rows to make a support audit pass.

Feature/context sidecars are a first-class outcome. Dense or useful data need not become graph topology:

- ReMap CRM summaries can be support/QA features without becoming `tf_binds_enhancer` edges;
- ClinicalTrials.gov trial text can be metadata/features without clinical-trial graph nodes;
- dataset/paper entities can remain provenance/catalog surfaces excluded from message passing;
- broad VEP consequences and coordinate overlaps can remain context instead of edges.

Sources: [`../evidence_and_edge_schema_plan.md`](../evidence_and_edge_schema_plan.md), [`../dataset_paper_graph_disconnection_t_c07b8b57.md`](../dataset_paper_graph_disconnection_t_c07b8b57.md), [`../clinical_trials_canonical_features_resolution_t_957a3640.md`](../clinical_trials_canonical_features_resolution_t_957a3640.md).

## Mechanical validity is not scientific validity

Endpoint anti-joins, schema checks, deduplication, and edge/evidence parity are necessary but insufficient. A 1.6M-row mutation→enhancer overlap can be mechanically perfect and still be the wrong canonical graph assertion.

Every promotion gate must separately ask:

1. Are the files technically valid and readable?
2. Are endpoints canonical and keys unique?
3. Does every edge have the expected source support?
4. Does the relation name truthfully describe the source assertion?
5. Is graph density useful rather than an artifact of expansion?
6. Could this feature leak the prediction target?

Sources: [`../mutation_genomic_relations_promotion_policy.md`](../mutation_genomic_relations_promotion_policy.md), [`../source_native_expansion_validation_report.md`](../source_native_expansion_validation_report.md).

## Promotion status must be explicit and reversible

Use exact language:

- `design done`;
- `pilot accepted`;
- `staged-only`;
- `review-required`;
- `validated`;
- `canonical promoted`;
- `production/full done`.

A bounded smoke is not a full run. Validation is not necessarily canonical promotion. Canonical promotion of one tranche is not full relation completion. Producer completion is not independent acceptance.

Prefer copy-once/versioned artifacts, manifests, hashes, and reversible retain-with-labels decisions over destructive cleanup. Destruction needs a separate evidence-based gate.

Source: [`../kanban_status_hygiene.md`](../kanban_status_hygiene.md).

## Separate build, test, review, and live promotion

A robust lane has distinct evidence:

1. **Builder:** creates code or staged artifact and reports exact commands, outputs, and residual risks.
2. **Tester:** validates behavior and data from the consumer/scientific perspective.
3. **Reviewer:** challenges semantics, scope, provenance, and false-pass risks.
4. **Promotion operator:** writes canonical state only when explicitly authorized and verifies readback.

Do not collapse “the script ran” into “the dataset is correct.” Review-required producers need a real, dispatchable route; a dependency edge from a blocked producer can deadlock the reviewer, so routing must be verified rather than assumed.

Sources: [`../kanban_status_hygiene.md`](../kanban_status_hygiene.md), [`../txgnn_agentic_mess_reviewability_audit_20260629.md`](../txgnn_agentic_mess_reviewability_audit_20260629.md).

## Shared artifact workspaces are not reviewable repositories

`work/txgnn` mixes code-like files, reports, caches, staging, and historical artifacts and has no project `.git`. Git commands can resolve to the parent workspace and produce unrelated noise.

Therefore:

- use it for durable reports/status/artifacts;
- never `git init` there;
- never claim a TxGNN-scoped PR diff from it;
- isolate code/docs changes in a real clone/worktree;
- carry only the minimal relevant delta from a dirty/shared source;
- validate the exact branch/head that will be reviewed.

A clean worktree is not bureaucracy: it is what makes provenance, diff review, rollback, and reproducibility possible.

Sources: [`../txgnn_agentic_mess_reviewability_audit_20260629.md`](../txgnn_agentic_mess_reviewability_audit_20260629.md), [`../git_reviewability_migration_t_4cab4a2f.md`](../git_reviewability_migration_t_4cab4a2f.md).

## Data locality is part of correctness

For 100M-row Parquets, large bigBeds, embeddings, and LaminDB bulk syncs, execution location changes both cost and behavior.

- Heavy reads/writes run bucket-near on `txgnn-worker` or another approved in-region worker.
- macOS GCS-FUSE is limited to small bounded inspection.
- Repeated FUSE scans can create real egress and poor/random-read behavior.
- Caches are not automatically beneficial: warm exact-byte replay can be fast while adjacent forward progress remains unchanged.
- Large source localization is justified only after disk, checksum, license, and equivalence checks.
- Process guards prevent a benchmark or recovery job from competing with the real writer.

The ReMap audit showed that doubling tile size did not improve throughput and that adjacent ranges did not benefit materially from the warm UDC cache. Optimize the measured bottleneck, not the parameter that is easiest to change.

Sources: [`../remap_speed_audit_t_2fb6aaea.md`](../remap_speed_audit_t_2fb6aaea.md), [`lamindb-porting-operations.md`](lamindb-porting-operations.md).

## Liveness is not progress

A VM, shell, supervisor, or Python PID can remain alive while no useful output is committed. Long jobs need durable, semantic progress signals:

- committed offset or shard;
- attempted/upserted/verified rows;
- selected-live parity;
- throughput and last-progress timestamp;
- RSS, disk, and I/O wait;
- explicit failure classification and return code.

Checkpoints advance only after verified commit. A stale `progress.json` with `completed=[]` is evidence of no committed progress even when a child process is still present.

Source: [`lamindb-porting-operations.md`](lamindb-porting-operations.md).

## Query shape dominates LaminDB scaling

At tens of millions of rows, seemingly harmless ORM operations can dominate or freeze the workflow:

- relation-wide `count()` calls on the write-critical path are unsafe;
- reading from physical row zero to discard a large prefix makes deep offsets progressively expensive;
- materializing a million-row edge/evidence tranche before the first 5k commit defeats subchunking;
- repeating the source scan per subchunk multiplies I/O;
- SQLite WAL/temp/index behavior must be treated as part of the workload.

Use one-pass row-group streaming, bounded subchunks, selected-key verification, separate full audits, and persistent telemetry.

Sources: [`lamindb-porting-operations.md`](lamindb-porting-operations.md), [`../../artifacts/reports/t_d7f9c01a/root_cause.md`](../../artifacts/reports/t_d7f9c01a/root_cause.md).

## PyG at this scale is a sidecar/memmap system, not one giant pickle

The architecture can be training-ready without full production training having run. At Jouvence scale:

- keep relation-wise `edge_index.npy` and row maps;
- memory-map selected relations;
- bound runtime loading and training samples;
- avoid a no-cap `heterodata/full_graph.pt`;
- preserve node maps, edge maps, reverse-edge mappings, and provenance as sidecars;
- stage remote sidecars to worker-local storage before local-path mmap loaders;
- treat a tiny smoke as execution evidence, not model-quality evidence.

Sources: [`../pyg_gnn_readiness_gate_t_825cfdcf.md`](../pyg_gnn_readiness_gate_t_825cfdcf.md), [`../pyg_manifest_metadata_contract_t_a3b15bc8.md`](../pyg_manifest_metadata_contract_t_a3b15bc8.md).

## Missing, deferred, fallback, and source-backed features are different states

Do not hide missing biology behind zeros or a generic “embedding available” flag.

- **source-backed available:** a real sidecar exists for some or all rows;
- **absent:** no source-backed sidecar exists for the selected type/relation;
- **deferred:** the modality is intentionally postponed pending source/policy/compute;
- **fallback:** a deterministic scaffold or model-side learned embedding supports execution but is not claimed as source-derived biological signal.

Coverage must be reported per node type/relation and per row, not inferred from the existence of one bounded sample. Keep modalities separate—protein sequence, protein text, transcript cDNA, molecule structure, ontology text—and fuse downstream. Derived embeddings are immutable versioned features tied to exact source hashes, model revisions, preprocessing, pooling, and licenses.

Sources: [`../foundation_embedding_policy.md`](../foundation_embedding_policy.md), [`../pyg_manifest_metadata_contract_t_a3b15bc8.md`](../pyg_manifest_metadata_contract_t_a3b15bc8.md), [`../clinical_trials_canonical_features_resolution_t_957a3640.md`](../clinical_trials_canonical_features_resolution_t_957a3640.md).

## Leakage policy belongs beside the feature

Text, status, trial outcomes, downstream associations, and support gates may reveal the label a model is supposed to predict. Canonical availability does not imply unrestricted training use.

Every feature/evidence surface with target information should document:

- which prediction tasks it can leak;
- whether it must be masked, partitioned, or excluded;
- whether it is input, supervision, evaluation-only, or provenance;
- how train/validation/test splits enforce the rule.

Clinical-trial outcomes and intervention text are the clearest example: useful canonical metadata, but dangerous for held-out molecule→disease prediction.

Source: [`../clinical_trials_canonical_features_resolution_t_957a3640.md`](../clinical_trials_canonical_features_resolution_t_957a3640.md).

## Project boundaries are operational safety boundaries

Shared cloud projects and concurrent sessions make “unexpected activity” ambiguous. A TxGNN operator must act only on explicitly scoped TxGNN resources. It must not stop, resize, pause, or reinterpret pert-gym resources merely because they are visible in the same account.

Cost guards, monitors, and cleanup scripts should use exact resource allowlists/targets and per-project ownership. Observability failure is also not remote failure: inability to reach an API proves only that current state is unknown.

Sources: [`lamindb-porting-operations.md`](lamindb-porting-operations.md), [`../../AGENTS.md`](../../AGENTS.md).

## Documentation should compile evidence, not copy status

The useful hierarchy is:

- `AGENTS.md`: short boot rules;
- `docs/guides/`: stable architecture, doctrine, runbooks, and cross-links;
- `docs/`: dated designs, audits, validation and promotion evidence;
- `artifacts/`: machine outputs, logs, manifests, staged data;
- `TODO.md` / `todo.d/`: concise phase mirrors;
- Kanban: live execution and ownership.

Do not paste live PIDs, cron states, or transient task lists into durable guides. Do preserve incidents when they changed the operating model, clearly labeled with the date and linked evidence.
