# KG reproducibility notebooks

This directory contains notebooks for explaining and reproducing the Jouvence/TxGNN KG build. The rule is that notebooks call existing package code (`manage_db`, `txdata_download`, `txgnn`) and keep inline code limited to configuration, display, and validation queries.

Default behavior is safe and lightweight: notebooks use sample/read-only mode, may use the verified FUSE mount at `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2` only for small bounded inspection, and keep heavy production writes behind explicit environment flags. Heavy TxGNN jobs are VM-only: run LaminDB/PyG/ReMap/embedding/full-KG jobs on `txgnn-worker` or another explicitly approved in-region worker with `gs://jouvencekb/kg/v2`, never through Mac GCS-FUSE. `.omoc` is retired and should not be used for new notebook caches.

## Sequence

1. `1_lamindb_instance_setup.ipynb` — LaminDB instance setup and biological registry context. Auth-dependent.
2. `2_manage_db_setup.ipynb` — `manage_db` setup and custom TxGNN/Lamin record types. To be modernized toward Parquet-first sync.
3. `3_access_and_cache_sources.ipynb` — storage/source access, OpenTargets release discovery, GCS/cache fallbacks.
4. `4_download_opentargets_and_source_snapshots.ipynb` — raw OpenTargets source download/cache verification.
5. `5_create_core_nodes.ipynb` — canonical node builders and node/xref validation.
6. `6_build_core_edges_and_evidence.ipynb` — core structural and source-backed edge/evidence builders, provenance summaries, endpoint/evidence support checks.
7. `7_opentargets_edges_and_evidence.ipynb` — OpenTargets-derived disease/gene/molecule/pathway/interaction relations with source dataset and evidence preservation.
8. `8_block1_relation_splitting_policy.ipynb` — executable Block 1 split/no-split policy for `gene_interacts_gene`, `pathway_contains_gene`, and `molecule_targets_gene`.
9. `9_sync_lamindb_and_parity.ipynb` — planned: auth-gated Parquet→LaminDB sync and parity audit.
10. `10_export_and_load_graph.ipynb` — planned: export/promotion and downstream `KGLoader` smoke tests.
9A. `9a_source_native_interactions_summary.ipynb` — read-only/source-native interaction ingestion notebook for IntAct bounded PPI, BioGRID PPI/PTM split, miRNA real-source alias/target staging, and ReMap all-peak deferred plus bounded CRM support/QA status; includes source access, schema decisions, counts, validation/reviewer status, and explicit no-canonical-promotion recommendations.
9B. `9b_l2_biological_nodes_context_summary.ipynb` — read-only L2 biological nodes/context summary for lncRNA, RBP/RNA CLIP, expression/coexpression, HPA localization, Complex Portal, UniProt PTM, and gene paralog tranches; records staged-only/feature-context status and no canonical promotion.
9C. `9c_pharmacology_context_metadata_summary.ipynb` — read-only pharmacology/context/metadata summary for clinical/safety evidence, protein-native/context batches, Sci-Plex candidate-context downgrade, and metadata/source-coverage staged artifacts; records no canonical promotion.
9. `9_source_native_l2_ingestion_index.ipynb` — short read-only N4D index tying together N4A/N4B/N4C plus non-ReMap promotion, ReMap deferred/support-only status, and ReMap-independent feature-layer promotions; separates biological edge/evidence canonical promotion from node feature-layer inclusion and records explicit deferred/not-promoted tranches.
9D. `9d_non_remap_part2_canonical_promotion_summary.ipynb` — read-only decision notebook for the non-ReMap Part 2/source-native canonical promotion lane; records the approved BioGRID physical PPI-only canonical candidate, all deferred/feature-context tranches, validation evidence, available post-promotion report/manifest evidence, and explicit ReMap `tf_binds_enhancer` exclusion.
11. `11_lamin_kg_schema_explorer.ipynb` — safe/read-only explorer for Lamin availability, KG node schema, relation/edge/evidence schema, and Parquet metadata under a configurable KG root.
12. `12_node_sequence_text_features_summary.ipynb` — safe/read-only summary of staged/promoted node sequence, textual-summary, and molecule fingerprint feature tables; records source/license matrices, schema contracts, validation PASS, the current reviewer-approved 12-table official `features/` inclusion set including `molecule_fingerprint` and full `protein_textual_summary`, the deferred `gene_sequence`/`gene_genomic_interval` policy state, and explicit no-ReMap/no-edge/no-evidence constraints.

Companion notebooks such as `kg_schema_overview.ipynb`, `kg_schema_current_status.ipynb`, and `kg_schema_deep_inspection.ipynb` remain useful explainers/audits but are not the canonical build sequence.

## Running safely

From the repo root, validate notebook structure with:

```bash
uv run python -c "import nbformat; nbformat.validate(nbformat.read('notebooks/6_build_core_edges_and_evidence.ipynb', as_version=4))"
```

For interactive execution, start with defaults. Heavy cells are guarded by environment variables:

- `TXGNN_NOTEBOOK_SAMPLE_MODE=1` (default): prefer cached/local samples.
- `TXGNN_NOTEBOOK_RUN_BUILD=1`: allow builder cells to write under `data/kg` or configured output roots.
- `TXGNN_NOTEBOOK_FULL_VALIDATION=1`: run full DuckDB endpoint validation on a local/mounted KG root.
- `TXGNN_NOTEBOOK_RUN_BLOCK1_SPLIT=1`: reserved for tested Block 1 splitter functions; do not implement split transforms inline in notebooks.

Use direct `gs://jouvencekb/kg/v2` reads or, for small bounded inspection only, the verified FUSE mount at `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2` for reproducibility. If a notebook needs a bounded local cache, use `artifacts/cache/<notebook-or-task>/`, not `.omoc`. Do not require macFUSE when direct GCS access is sufficient, and do not use Mac FUSE for heavy production notebook runs.

## KG semantics encoded here

- Relation names follow source-native endpoint and assertion semantics.
- Gene-level OpenTargets rows stay in gene relations; they are not projected to protein relations through mapping tables.
- Broad relations are acceptable when row-level predicates/subdatabases live in `evidence/{relation}.parquet`.
- Context-specific enhancer predictions must preserve biosample/context and feature provenance.
- Every source-backed relation needs edge/evidence support audits and endpoint anti-joins before promotion.
