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
26. [`26_source_reproduction_index.ipynb`](26_source_reproduction_index.ipynb) — reconcile the canonical source denominator and explain the base Open Targets/TxData-derived lanes.
27. [`27_source_native_protein_context_reproduction.ipynb`](27_source_native_protein_context_reproduction.ipynb) — explain BioGRID, IntAct, HPA, UniProt, Reactome, ChEMBL, and deferred miRNA paths, with a bounded IntAct mapping illustration.
28. [`28_cell_line_pharmacology_clinical_reproduction.ipynb`](28_cell_line_pharmacology_clinical_reproduction.ipynb) — explain DepMap/Project Score, GDSC, PRISM 20Q2, Cellosaurus, and ClinicalTrials.gov, with bounded parser illustrations.
29. [`29_official_features_exports_reproduction.ipynb`](29_official_features_exports_reproduction.ipynb) — explain Ensembl/HPO/RDKit features, Cell Ontology and UBERON textual-feature sources, embeddings, PyG export, and the partial Lamin status surface, with a bounded schema/hash illustration.

Executed historical copies are isolated under [`executed/`](executed/) and use the same numeric identity as their source notebook. The numeric prefix is the canonical order; new notebooks must use the next two-digit number rather than letter suffixes or unnumbered filenames.

## Authoritative source-family inventory

[`source_family_inventory.json`](source_family_inventory.json) contains 26 source/pipeline families: 12 that contributed canonical nodes, edges, or evidence; five official feature-source families (including canonical Cellosaurus where it also backs official text features); six staged families (including the bounded PyG export/runtime smoke); and four deferred families. Artifact status is kept separate from replay completeness: a canonical family can be explanatorily complete while lacking a bounded source-native fixture. Every row records its release or historical snapshot, access and licence, cache template, preprocessing entrypoint, mapping/rejection policy, outputs, accepted validation evidence, notebook anchor, and exact residual gap. Regenerate the four deterministic notebooks with `uv run python reproduce/generate_source_reproduction_notebooks.py`.

## Paper scripts

- `run_txgnn.sh` and `train.py` run the upstream training workflow.
- `result_more_metrics.csv` contains raw result metrics.
- A historical model checkpoint is available at <https://drive.google.com/file/d/1BPHKejmUpERhLTY4negB4e6ZLmoE7dwq/view?usp=sharing> and can be loaded with `TxGNN.load_pretrained`.

## Safety

The four source-reproduction notebooks are not command runners. Production commands appear only as Markdown text. Executable cells use synthetic inputs, temporary directories, and pure tracked parser/schema functions; they do not invoke a shell, subprocess, network, cloud/GCS, LaminDB, canonical paths, or production builders. Heavy and canonical work remains outside notebooks and requires its own reviewed worker card.
