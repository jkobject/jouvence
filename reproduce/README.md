# Reproducing Jouvence

This directory contains the notebooks and scripts that create, ingest, audit, or reproduce the Jouvence database and the upstream TxGNN paper. User-facing exploration notebooks live separately in [`../notebooks/`](../notebooks/).

## Database construction and audit sequence

1. [`01_lamindb_instance_setup.ipynb`](01_lamindb_instance_setup.ipynb) — initialize and inspect the LaminDB instance and biological registries.
2. [`02_manage_db_setup.ipynb`](02_manage_db_setup.ipynb) — configure `manage_db` and Jouvence/Lamin record types.
3. [`03_access_and_cache_sources.ipynb`](03_access_and_cache_sources.ipynb) — resolve source access and bounded caches.
4. [`04_download_opentargets_and_source_snapshots.ipynb`](04_download_opentargets_and_source_snapshots.ipynb) — acquire and verify OpenTargets/source snapshots.
5. [`05_create_core_nodes.ipynb`](05_create_core_nodes.ipynb) — build canonical nodes and validate identifiers/xrefs.
6. [`06_build_core_edges_and_evidence.ipynb`](06_build_core_edges_and_evidence.ipynb) — build core edges and source-backed evidence.
7. [`07_opentargets_edges_and_evidence.ipynb`](07_opentargets_edges_and_evidence.ipynb) — build OpenTargets-derived relations and evidence.
8. [`08_relation_splitting_policy.ipynb`](08_relation_splitting_policy.ipynb) — execute relation split/no-split policy checks.
9. [`09_source_native_ingestion_index.ipynb`](09_source_native_ingestion_index.ipynb) — index source-native ingestion tranches and decisions.
10. [`10_source_native_interactions_summary.ipynb`](10_source_native_interactions_summary.ipynb) — inspect interaction-source ingestion.
11. [`11_biological_nodes_context_summary.ipynb`](11_biological_nodes_context_summary.ipynb) — inspect biological node and context tranches.
12. [`12_pharmacology_context_metadata_summary.ipynb`](12_pharmacology_context_metadata_summary.ipynb) — inspect pharmacology, context, and metadata tranches.
13. [`13_non_remap_canonical_promotion_summary.ipynb`](13_non_remap_canonical_promotion_summary.ipynb) — audit non-ReMap canonical promotion decisions.
14. [`14_ingest_opentargets_legacy.ipynb`](14_ingest_opentargets_legacy.ipynb) — legacy broad OpenTargets ingestion notebook retained for reproducibility.
15. [`15_kg_schema_overview.ipynb`](15_kg_schema_overview.ipynb) — inspect the KG schema and its intended use.
16. [`16_kg_schema_current_status.ipynb`](16_kg_schema_current_status.ipynb) — inspect current schema coverage.
17. [`17_kg_schema_deep_inspection.ipynb`](17_kg_schema_deep_inspection.ipynb) — run deeper schema and endpoint checks.
18. [`18_lamin_kg_schema_explorer.ipynb`](18_lamin_kg_schema_explorer.ipynb) — compare LaminDB and canonical Parquet schema surfaces.
19. [`19_node_sequence_text_features_summary.ipynb`](19_node_sequence_text_features_summary.ipynb) — audit sequence, text, fingerprint, and embedding features.
20. [`20_current_kg_state_20260624.ipynb`](20_current_kg_state_20260624.ipynb) — dated KG-state reproduction snapshot.
21. [`21_pyg_out_of_core_and_lamin_remaining.ipynb`](21_pyg_out_of_core_and_lamin_remaining.ipynb) — reproduce the out-of-core PyG proof and remaining LaminDB work.
22. [`22_jouvence_explore_legacy.ipynb`](22_jouvence_explore_legacy.ipynb) — legacy Jouvence exploration retained as build history.
23. [`23_txdata_explore_legacy.ipynb`](23_txdata_explore_legacy.ipynb) — legacy TxData exploration retained as build history.
24. [`24_txgnn_model_demo.ipynb`](24_txgnn_model_demo.ipynb) — upstream TxGNN model demonstration.
25. [`25_gather_txgnn_paper_results.ipynb`](25_gather_txgnn_paper_results.ipynb) — reproduce paper-result plots.

Executed historical copies are isolated under [`executed/`](executed/) and use the same numeric identity as their source notebook. The numeric prefix is the canonical order; new notebooks must use the next two-digit number rather than letter suffixes or unnumbered filenames.

## Paper scripts

- `run_txgnn.sh` and `train.py` run the upstream training workflow.
- `result_more_metrics.csv` contains raw result metrics.
- A historical model checkpoint is available at <https://drive.google.com/file/d/1BPHKejmUpERhLTY4negB4e6ZLmoE7dwq/view?usp=sharing> and can be loaded with `TxGNN.load_pretrained`.

## Safety

Notebooks call existing `manage_db`, `txdata_download`, and `txgnn` code; they should not duplicate production builders inline. Heavy full-KG, LaminDB, embedding, ReMap, or PyG operations are worker-only and remain gated by explicit environment variables and review. Canonical writes are never an implicit notebook default.
