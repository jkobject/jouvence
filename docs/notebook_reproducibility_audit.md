# Notebook reproducibility audit

This audit maps the current notebook surface to a clean numbered sequence for explaining and reproducing the Jouvence/TxGNN KG build. It is a planning document only: no notebook creation or heavy notebook execution was performed.

## Scope and constraints

- Existing notebooks were inspected by reading metadata, markdown headings, imports, and representative code cells from the `.ipynb` JSON; heavy cells were not executed.
- Repo context read for this audit: `AGENTS.md`, `TODO.md`, `docs/kg_schema_overview.md`, `docs/source_measure_edge_matrix.md`, and `docs/txgnn_access_runbook.md`.
- Access constraint to preserve in notebooks: do not wait for macFUSE. Use the canonical GCS root `gs://jouvencekb/kg/v2` when direct GCS access works, or copy targeted tiny samples into `.omoc/gcs-cache/kg-v2/` with `gcloud storage cp` and inspect with DuckDB/PyArrow.
- LaminDB remote `jkobject/jouvencekb` may be unavailable in anonymous worker shells. Notebooks that require LaminDB should include a short auth probe and treat missing LaminHub permissions as a documented blocker, not as a reason to stall the rest of the KG reproducibility path.
- User preference / design rule: notebooks should call the existing loader, downloader, ingestion, audit, validation, sync, and export functions directly. They should not reimplement pipeline logic inline beyond small display helpers and assertions.

## Current notebook inventory

| Notebook | Current coverage | Keep / replace / obsolete | Notes |
| --- | --- | --- | --- |
| `reproduce/01_lamindb_instance_setup.ipynb` | LaminDB instance connection, initial audit, bionty source inspection/import, pertdb compound transfer, HP-vs-PATO phenotype source note. | Keep as notebook 1, but refresh execution metadata when Lamin auth works. | Good conceptual setup notebook. It is Lamin-heavy and depends on auth/instance state. |
| `reproduce/executed/01_lamindb_instance_setup.executed.ipynb` | Executed copy of notebook 1. | Keep as historical artifact or replace with a standard executed artifact naming policy. | Duplicates notebook 1 content; should not be the canonical editable notebook. |
| `reproduce/02_manage_db_setup.ipynb` | `manage_db` setup, custom `lnschema_txgnn` record types, `sync_txgnn_nodes_to_lamin_entities`, final record counts. | Keep as notebook 2, but modernize to current Parquet-first sync. | Uses older `nodes.tab` assumptions. Should point newer KG node sync to `sync_parquet_nodes_to_lamindb`. |
| `reproduce/executed/02_manage_db_setup.executed.ipynb` | Executed copy of notebook 2. | Keep as historical artifact or replace with standard executed artifact naming policy. | Duplicates notebook 2 content; not canonical editable source. |
| `reproduce/14_ingest_opentargets_legacy.ipynb` | OpenTargets discovery/download/inspection plus calls to ingestion helpers: `ingest_targets`, `ingest_diseases`, `ingest_drugs`, `ingest_interactions`, `ingest_evidence`, `ingest_go`, `ingest_reactome`, `ingest_literature`, `ingest_indication`, `ingest_mechanism_of_action`. | Replace/split into the new numbered sequence. | Valuable but too broad; it mixes release discovery, raw inspection, nodes, edges, evidence, and summary. Also misses newer ingest functions added after the notebook. |
| `reproduce/22_jouvence_explore_legacy.ipynb` | LaminDB counts and full graph exploration through KGLoader/GCS Parquet. | Replace with a final inspection/loading notebook. | Contains a likely stale import: `from manage_db.kg_loader import KGLoader`; the actual loader inspected here is `txgnn/KGLoader.py`. |
| `reproduce/15_kg_schema_overview.ipynb` | Interactive schema guide: node types, xrefs, relation taxonomy, credibility, edge schema, xref helpers, legacy mapping, pipeline sketch. | Keep as a companion explainer, but do not make it part of the build sequence. | Its markdown overlaps `docs/kg_schema_overview.md`; future build notebooks should link to docs instead of duplicating schema policy. |
| `reproduce/16_kg_schema_current_status.ipynb` | Current status inspection: schema relations, Parquet metadata, phenotype direction sanity check, bounded relation sample, backlog view. | Merge into the proposed validation/status notebook. | Useful lightweight status checks; overlaps `kg_schema_deep_inspection.ipynb`. |
| `reproduce/17_kg_schema_deep_inspection.ipynb` | Deep inspection using `audit_coverage`, `audit_edge_evidence`, schema enums, relation lifecycle views, endpoint sanity checks, optional CSV exports. | Keep concepts, rename into the proposed validation/status notebook. | Best current audit notebook; should be the basis for the final validation notebook. |
| `reproduce/23_txdata_explore_legacy.ipynb` | Original TxData CSV exploration, `download_txdata_csvs`, `add_disease_anatomy_relationships`, and early raw OpenTargets Parquet peeks. | Replace with a legacy TxData/bootstrap notebook if still needed. | Exploratory, partly obsolete. It reads `nodes.tab` / `edges.csv` and should not be the main KG build path. |
| `reproduce/24_txgnn_model_demo.ipynb` | Legacy TxGNN model training demo with `TxData`, `TxGNN`, `TxEval`, scratch paths, disease split. | Keep outside KG creation sequence as downstream ML demo. | No markdown; uses old absolute scratch path. Not a reproducible KG creation notebook. |
| `reproduce/25_gather_txgnn_paper_results.ipynb` | Result gathering/plotting for TxGNN runs; imports `TxData`, metrics, seaborn/matplotlib. | Keep under `reproduce/` as experiment analysis, outside KG creation sequence. | Not a KG construction notebook. |

## Existing code surface notebooks should call

The reproducible notebooks should be thin orchestration and exposition layers over this existing code surface:

| Area | Existing module/function/class | Notebook usage |
| --- | --- | --- |
| OpenTargets release discovery | `txdata_download.get_opentargets_releases`, `get_latest_opentargets_release`, `list_opentargets_datasets` | Discover and pin a release; list raw datasets before download. |
| OpenTargets download | `txdata_download.download_opentargets_dataset`, `download_opentargets_datasets` | Download selected source datasets into `data/opentargets/` or a scratch/cache root. |
| Full OpenTargets orchestration | `manage_db.ingest_opentargets.run` | Preferred high-level path for standard builds; use explicit `datasets=[...]` for reproducible tranches. |
| OpenTargets nodes | `ingest_targets`, `ingest_diseases`, `ingest_drugs`, `ingest_biosample`, `ingest_go` | Node-build notebook should call these functions and inspect resulting Parquets. |
| OpenTargets central/ontology/source edges | `ingest_orthology`, `ingest_go`, `ingest_reactome`, `ingest_biosample` | Edge notebook should call these for lower-risk structural relations. |
| OpenTargets evidence-backed biomedical edges | `ingest_interactions`, `ingest_evidence`, `ingest_indication`, `ingest_mechanism_of_action`, `ingest_target_essentiality`, `ingest_disease_phenotype`, `ingest_expression`, `ingest_pharmacogenomics`, `ingest_variant_protein_changes`, `ingest_evidence_backed_variants`, `ingest_enhancers` | Edge/evidence notebooks should call these functions directly or through `run`, never copy their row transformation logic into cells. |
| KG storage | `manage_db.kg_storage.open_kg_root`, `read_nodes`, `read_edges`, `write_nodes`, `write_edges`, `finalize_kg_export` | Use for storage abstraction and inspection; avoid ad hoc path handling except for tiny local cache probes. |
| Schema source of truth | `manage_db.kg_schema.NODE_TYPES`, `RELATIONS`, `RELATION_BY_NAME`, `xref_columns_for`, `primary_ontology_for` | Use for displayed schema tables and validations. |
| Evidence model/audit | `manage_db.kg_evidence`, `manage_db.audit_edge_evidence.audit_edge_evidence`, `manage_db.backfill_edge_evidence.backfill_edge_evidence` | Use for evidence schema examples and support audits. |
| Coverage/validation | `manage_db.audit_kg_coverage.audit_coverage`, `manage_db.validate_kg.validate_duckdb`, `validate_streaming` | Use in validation notebooks, with DuckDB preferred for full endpoint validation. |
| LaminDB sync | `manage_db.sync_parquet_nodes_to_lamindb.sync_parquet_nodes_to_lamindb`; legacy `sync_nodes_to_lamindb.sync_txgnn_nodes_to_lamin_entities` for old TxData TSVs | Use Parquet sync for current KG; keep TSV sync only as legacy migration context. |
| LaminDB parity | `manage_db.audit_lamindb_parity.audit_kg_nodes` / CLI module | Optional auth-gated parity notebook section. |
| Export | `manage_db.export_kg.export_kg` | Promotion/export notebook should call this after validation gates. |
| Graph loading | `txgnn.KGLoader.KGLoader` via `from txgnn import KGLoader` if exported | Final usage notebook should load the KG through the package loader and call `validate`, `to_pyg`, or `to_dgl` on small subsets where possible. |
| TxData legacy bootstrap | `txdata_download.download_txdata_csvs`, `add_disease_anatomy_relationships`; `txgnn.TxData.TxData` | Use only in a legacy compatibility notebook, not in the canonical KG creation path. |

## Proposed clean numbered notebook sequence

The current `1_...` and `2_...` notebooks already cover the LaminDB/bootstrap layer. The KG creation sequence should continue at `3_...` and should be explicit about what is cheap metadata inspection versus what downloads/builds large data.

### `3_access_and_source_inventory.ipynb`

Purpose:
- Establish reproducible access to KG/source storage and enumerate the exact source inputs.
- Pin OpenTargets release and local/GCS paths without doing a full ingest.

Required inputs:
- Repo checkout with `uv` environment.
- Optional GCS access to `gs://jouvencekb/kg/v2` and source/scratch buckets.
- Optional existing local cache under `.omoc/gcs-cache/kg-v2/`.

Functions/loaders to call:
- `txdata_download.get_opentargets_releases()`
- `txdata_download.get_latest_opentargets_release()`
- `txdata_download.list_opentargets_datasets(release)`
- `manage_db.kg_storage.open_kg_root(uri)` for canonical or cached KG roots.

Expected outputs:
- Display table of candidate OpenTargets releases and selected/pinned release.
- Display table of source dataset availability.
- Display sanitized access status for GCS, local cache, FUSE, and LaminDB.
- No canonical KG writes.

Execution cost:
- Cheap. Metadata/API listing only; no large downloads.

Validation cells:
- Assert selected release is non-empty and source datasets needed by later notebooks are listed.
- If GCS is unavailable, assert the fallback cache directories exist or show the exact `gcloud storage cp` commands for targeted samples.
- Assert no credential contents are printed.

### `4_download_opentargets_sources.ipynb`

Purpose:
- Download or verify raw OpenTargets source datasets needed for a reproducible KG build.
- Keep download orchestration separate from transformation.

Required inputs:
- Pinned release from notebook 3.
- Writable local/scratch source root, e.g. `data/opentargets/` for local reproduction or a documented scratch location.

Functions/loaders to call:
- `txdata_download.download_opentargets_datasets(datasets, dest_dir, release, workers)`
- Optionally `download_opentargets_dataset` for a single dataset retry.

Expected outputs:
- Raw OpenTargets Parquet directories for selected datasets.
- Status table with dataset name, directory existence, number of shards, and completion marker if available.

Execution cost:
- Medium to high depending on selected datasets. Network-heavy; should be parameterized so users can run only a tranche.

Validation cells:
- For each requested dataset, check directory exists and contains Parquet shards.
- Read only schema/sample rows from one shard per dataset with PyArrow/DuckDB; do not load full directories into pandas.
- Confirm release string and raw path are printed into a small build manifest.

### `5_create_core_nodes.ipynb`

Purpose:
- Build the canonical node Parquets from OpenTargets and ontology-backed sources.
- Explain endpoint namespace policy: source-native IDs first; no gene-to-protein projection unless source is protein-native.

Required inputs:
- Raw OpenTargets `target`, `disease`, `drug_molecule`, `biosample`, `go`, and `reactome` datasets as applicable.
- Output/staging KG root, e.g. `data/kg` or a scratch GCS path.

Functions/loaders to call:
- `manage_db.kg_storage.open_kg_root`
- `manage_db.ingest_opentargets.ingest_targets`
- `ingest_diseases`
- `ingest_drugs`
- `ingest_biosample`
- `ingest_go`
- Node schema helpers from `manage_db.kg_schema`.

Expected outputs:
- Node Parquets under `nodes/` for gene, transcript, protein, disease, molecule, pathway, tissue, cell_type, phenotype, cell_line, organism, dataset, enhancer where source steps apply.
- Node count and xref coverage tables.

Execution cost:
- Medium. Mostly raw Parquet reads and node table writes.

Validation cells:
- Assert required node files exist after each ingest.
- Use `manage_db.kg_schema.NODE_TYPES` and `xref_columns_for` to check required xref columns.
- Display row counts with `pyarrow.parquet.ParquetFile(...).metadata.num_rows` or DuckDB counts.
- Spot-check namespace prefixes: Ensembl gene/transcript/protein IDs, EFO/HP/UBERON/CL/ChEMBL/NCBITaxon as appropriate.

### `6_build_structural_edges.ipynb`

Purpose:
- Build lower-risk structural/ontology/central-dogma edges before evidence-heavy biomedical assertions.
- Make direction and endpoint policy visible.

Required inputs:
- Node Parquets from notebook 5.
- Raw OpenTargets datasets: `target`, `target_homologues`, `go`, `reactome`, `biosample` as needed.

Functions/loaders to call:
- `manage_db.ingest_opentargets.ingest_targets` for `gene_has_transcript` / `transcript_encodes_protein` side outputs if produced there.
- `ingest_orthology`
- `ingest_go`
- `ingest_reactome`
- `ingest_biosample`
- `manage_db.validate_kg.validate_duckdb` or targeted DuckDB anti-joins.

Expected outputs:
- Structural/ontology edge Parquets such as `gene_has_transcript`, `transcript_encodes_protein`, `gene_ortholog_gene`, `pathway_contains_gene`, `pathway_child_of_pathway`, organism/tissue/cell-line metadata edges where supported.

Execution cost:
- Medium. Reads selected raw datasets; validates endpoints.

Validation cells:
- Endpoint anti-joins for every relation built in the notebook.
- Schema check against `manage_db.kg_schema.RELATION_BY_NAME` for `x_type`, `y_type`, and `relation` columns.
- Row-count summary compared to the current schema overview where relevant.

### `7_build_source_backed_edges_and_evidence.ipynb`

Purpose:
- Build disease, pharmacology, variant, expression, enhancer, and interaction relations with evidence support.
- Demonstrate the broad-relation-plus-rich-evidence doctrine.

Required inputs:
- Node and structural edge Parquets from notebooks 5-6.
- Raw OpenTargets datasets including `interaction`, `evidence*`, `drug_indication`, `drug_mechanism_of_action`, `target_essentiality`, `disease_phenotype`, `expression`, `pharmacogenomics`, `variant`, `known_variant`, `enhancer_to_gene`, plus any local HPA/source files for direct protein expression when used.

Functions/loaders to call:
- `manage_db.ingest_opentargets.ingest_interactions`
- `ingest_evidence`
- `ingest_indication`
- `ingest_mechanism_of_action`
- `ingest_target_essentiality`
- `ingest_disease_phenotype`
- `ingest_expression`
- `ingest_pharmacogenomics`
- `ingest_variant_protein_changes`
- `ingest_evidence_backed_variants`
- `ingest_enhancers`
- Relation-specific builders/backfills when selected, e.g. `manage_db.backfill_edge_evidence.backfill_edge_evidence`, `build_mutation_associated_disease_evidence`, `build_molecule_treats_disease_clinical_evidence`, and direct-source builders such as `manage_db.build_mutation_associated_phenotype.build_local_mutation_associated_phenotype`.

Expected outputs:
- Deduplicated edge Parquets under `edges/{relation}.parquet`.
- Source-backed evidence Parquets under `evidence/{relation}.parquet` with predicates, source datasets, scores, study IDs, PMIDs/source record IDs, context fields, and release/provenance.

Execution cost:
- High. This is the heaviest transformation notebook and should support tranche parameters.

Validation cells:
- For each relation built: endpoint anti-joins, edge/evidence support audit via `audit_edge_evidence`, and source/predicate distribution summary from evidence.
- Check that protein relations are only populated from protein-native/direct protein sources; never project RNA/gene rows into protein edges.
- Check ENCODE-rE2G/enhancer outputs preserve biosample/context feature metadata.
- Check broad relations preserve source subdatabase nuance in evidence instead of exploding relation names unnecessarily.

### `8_validate_kg_and_evidence.ipynb`

Purpose:
- Provide the canonical validation/status notebook for a built or cached KG.
- Consolidate the useful parts of `kg_schema_current_status.ipynb` and `kg_schema_deep_inspection.ipynb`.

Required inputs:
- Built KG root, canonical GCS root, or local targeted cache.

Functions/loaders to call:
- `manage_db.audit_kg_coverage.audit_coverage`
- `manage_db.audit_edge_evidence.audit_edge_evidence`
- `manage_db.validate_kg.validate_duckdb` for full validation when local/FUSE path is available.
- `manage_db.validate_kg.validate_streaming` as a fallback.
- `manage_db.kg_schema.RELATIONS`, `NODE_TYPES`, relation lifecycle/status fields.

Expected outputs:
- Coverage report table: nodes present, edges present, rows, missing active relations.
- Evidence support table: edges without evidence, evidence without edge, per relation.
- Endpoint validation summary with total dangling edges.
- Optional exported CSV summaries under `.omoc/reports/` or `reports/`.

Execution cost:
- Cheap to medium for metadata counts; high for full DuckDB endpoint validation on the complete KG.

Validation cells:
- Assert `total_dangling_edges == 0` for full validation runs.
- Assert all required node files exist.
- Assert evidence-backed relations selected for the tranche pass `audit_edge_evidence(...).ok`.
- Verify schema docs and source matrix are current enough for the built relation set.

### `9_sync_lamindb_and_parity.ipynb`

Purpose:
- Sync current Parquet node registries into LaminDB and audit parity, as an auth-gated optional notebook.
- Modernize notebook 2 by moving from legacy `nodes.tab` sync to Parquet node sync.

Required inputs:
- Built KG root or canonical KG root.
- Authenticated LaminDB session with access to `jkobject/jouvencekb`.

Functions/loaders to call:
- `manage_db.sync_parquet_nodes_to_lamindb.sync_parquet_nodes_to_lamindb`
- `manage_db.audit_lamindb_parity.audit_kg_nodes` / module CLI if exposed for notebook use.
- Legacy only: `manage_db.sync_nodes_to_lamindb.sync_txgnn_nodes_to_lamin_entities` for old TxData TSV migration notes.

Expected outputs:
- Sync summary by node type: existing, created/missing, skipped, errors.
- LaminDB parity report for KG nodes.

Execution cost:
- Medium and auth-dependent.

Validation cells:
- First cell checks `lamin info` / `ln.connect("jkobject/jouvencekb")` in a sanitized way.
- If anonymous or instance unavailable, skip sync cells and display blocker text from `docs/txgnn_access_runbook.md`.
- After sync, assert no unexpected missing required node registries.

### `10_export_and_load_graph.ipynb`

Purpose:
- Demonstrate promotion/export and downstream graph loading without retraining the model.
- Provide the reproducibility bridge from Parquet KG to `KGLoader`, PyG, and DGL.

Required inputs:
- Validated staging KG root.
- Destination local/GCS root if export is being demonstrated.
- Optional small subset for PyG/DGL smoke tests if full KG loading is too expensive.

Functions/loaders to call:
- `manage_db.export_kg.export_kg`
- `manage_db.kg_storage.finalize_kg_export`
- `txgnn.KGLoader.KGLoader` via package import when available.
- `KGLoader.validate`, `edge_index_frames`, `to_pyg`, `to_dgl` where dependencies and memory allow.

Expected outputs:
- Exported KG root with `nodes/`, `edges/`, `evidence/`, and `metadata/provenance.json`.
- Loader validation summary and graph backend smoke result.

Execution cost:
- Medium for metadata/export, potentially high memory for full graph materialization. Include a small-subset smoke path.

Validation cells:
- Assert exported root contains required directories and provenance metadata.
- `KGLoader(...).validate().ok` on the exported/smoke KG.
- Optional `to_pyg` / `to_dgl` smoke only on a tiny slice unless the environment is provisioned for the full KG.

### Optional `11_legacy_txdata_and_txgnn_demo.ipynb`

Purpose:
- Keep legacy TxGNN/TxData reproduction separate from Jouvence KG creation.
- Explain how `reproduce/24_txgnn_model_demo.ipynb`, `txdata_explore.ipynb`, and `reproduce/25_gather_txgnn_paper_results.ipynb` relate to downstream experiments.

Required inputs:
- Legacy TxData files (`nodes.tab`, `edges.csv`) or downloaded TxData CSVs.
- Training/evaluation result files if plotting.

Functions/loaders to call:
- `txdata_download.download_txdata_csvs`
- `txdata_download.add_disease_anatomy_relationships`
- `txgnn.TxData.TxData`
- `txgnn.TxGNN.TxGNN`
- `txgnn.TxEval.TxEval`

Expected outputs:
- Legacy data split smoke output, not a canonical KG build.
- Clear warning that this is downstream/legacy compatibility, not source-of-truth KG construction.

Execution cost:
- Medium to high if training is run. Keep training off by default.

Validation cells:
- Assert legacy files exist and split preparation runs on a tiny/smoke configuration.
- Plotting notebook should validate input result files before computing metrics.

## Suggested renames / consolidation

- Canonical editable notebooks:
  - Keep `1_lamindb_instance_setup.ipynb`.
  - Keep/modernize `2_manage_db_setup.ipynb`.
  - Add notebooks `3_...` through `10_...` above.
- Historical executed artifacts:
  - Keep `.executed.ipynb` files only as generated artifacts, not hand-edited sources.
  - Preserve historical executed copies under `reproduce/executed/<numbered-name>.ipynb`; `notebooks/` remains output-free and user-facing.
- Replace `ingest_opentargets.ipynb` with notebooks 3-7.
- Merge `kg_schema_current_status.ipynb` and `kg_schema_deep_inspection.ipynb` into notebook 8.
- Keep `kg_schema_overview.ipynb` as an explainer, but make `docs/kg_schema_overview.md` and `docs/source_measure_edge_matrix.md` the authoritative docs.
- Move/label `txdata_explore.ipynb`, `reproduce/24_txgnn_model_demo.ipynb`, and `reproduce/25_gather_txgnn_paper_results.ipynb` as legacy/downstream experiment notebooks, outside KG creation.

## Blockers and caveats for implementers

- LaminDB remote access is not guaranteed in worker shells. Notebook 9 must be skip-safe when `lamin info` reports anonymous or `ln.connect("jkobject/jouvencekb")` fails.
- Full KG validation should use DuckDB on a mounted/local path when possible. If only `gs://` is available, use targeted cache samples for notebook demonstration and run full validation as a documented CLI/job step.
- Current docs say FUSE is not present on the macOS worker. Do not make any notebook wait for macFUSE approval.
- Beware stale imports in existing notebooks. In particular, `Jouvence_Explore.ipynb` imports `from manage_db.kg_loader import KGLoader`, but the inspected loader implementation is `txgnn/KGLoader.py`; future notebooks should use the package import path that actually resolves in the repo environment.
- Keep biomedical KG semantics aligned with `docs/source_measure_edge_matrix.md`: source-native endpoint policy, broad relations with rich evidence, no RNA/gene-to-protein projection, and context preserved for enhancer predictions.

## Acceptance checklist for the future notebook implementation cards

- Every notebook starts with cheap environment/path/source checks before expensive operations.
- Every notebook has explicit parameters for source root, output root, OpenTargets release, and selected datasets/tranches.
- Notebook cells call repository functions/classes directly and keep inline logic limited to display, small assertions, and examples.
- Heavy notebooks support a small/sample mode and a full mode.
- Every build notebook has validation cells that inspect generated Parquets and endpoint consistency.
- Every evidence-producing notebook runs or demonstrates `audit_edge_evidence` for the relations it builds.
- The final graph loading notebook proves the generated Parquet KG can be consumed by `KGLoader` on at least a tiny/smoke slice.
