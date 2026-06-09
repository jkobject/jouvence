# TxGNN — Claude Project Context

## What This Is

TxGNN is a Python ML research library for **zero-shot drug repurposing** via
graph neural networks. It trains on a biomedical knowledge graph (17,080
diseases × 7,957 drug candidates) to predict drug indications and
contraindications.

Paper:
[MedRxiv 2023.03.19.23287458](https://www.medrxiv.org/content/10.1101/2023.03.19.23287458v2)

## Package Structure

```
txgnn/
  TxData.py      # Data loading, splits, knowledge graph prep
  TxGNN.py       # Main model class (pretrain, finetune, eval, XAI)
  TxEval.py      # Disease-centric evaluation
  model.py       # GNN architecture
  utils.py       # Shared utilities
  graphmask/     # GraphMask XAI module
  data_splits/   # Pre-defined train/val/test splits
txdata_download.py  # Data download helpers (EBI FTP + Harvard Dataverse)
notebooks/
  txdata_explore.ipynb
reproduce/
  sync_nodes_to_lamindb.py
```

## Core API

```python
from txgnn import TxData, TxGNN, TxEval

TxData = TxData(data_folder_path='./data')
TxData.prepare_split(split='complex_disease', seed=42)

TxGNN = TxGNN(data=TxData, device='cuda:0')
TxGNN.model_initialize(n_hid=100, n_inp=100, n_out=100, proto=True, proto_num=3)
TxGNN.pretrain(...)
TxGNN.finetune(...)

TxEval = TxEval(model=TxGNN)
TxEval.eval_disease_centric(disease_idxs='test_set', ...)
```

## Environment

- Python >= 3.12, managed with **uv** (`uv.lock` present)
- Run: `uv run python ...`
- Key deps: PyTorch, DGL, pandas, numpy, scikit-learn, goatools
- No JupyterLab installed (only nbconvert/nbformat in venv)
- No web server — this is a pure research library

## lamindb

the lamin instance for this is jkobject/jouvencekb and requires authentication
from jkobject and a gsutil command access setup with the jkobject project id
jkobject-1549353370965

### I1 — bionty/pertdb populated (2026-06-04)
- Run: `python -m manage_db.i1_bionty_pertdb_import` (idempotent)
- Output: see `i1_run.log` for counts; executed notebook at `notebooks/1_lamindb_instance_setup.executed.ipynb`.
- HP (Human Phenotype Ontology) is the active Phenotype source (PATO disabled per §7).

### I2 — custom records + node sync (2026-06-05)
- Run: `python -m manage_db.i2_custom_records_and_sync` (idempotent).
- 5 custom `lnschema_txgnn` record types deployed (Paper, Transcript, Enhancer, Dataset, Mutation).
- Sync mapped 129,375 nodes (existing=125,744, created=30, uncertain=3,601); see `data/txdata/node_entity_mapping.csv`.
- Executed notebook: `notebooks/2_manage_db_setup.executed.ipynb`.

## Data

- Knowledge graph CSVs: `data/kg.csv`, `node.csv`, `edges.csv` (Harvard
  Dataverse)
- Download: `txdata_download.py` — EBI FTP HTTP mirror for OpenTargets, stdlib
  for Harvard
- OpenTargets: parallel download via threads, `.ot_complete` marker, alias
  resolution
- LaminDB integration exists (`reproduce/sync_nodes_to_lamindb.py`)
- Disease area files: `data/disease_files/*.csv`

## Splits

| Split                                                      | Description                                                 |
| ---------------------------------------------------------- | ----------------------------------------------------------- |
| `complex_disease`                                          | Systematic: all treatments for sampled diseases → test only |
| `cell_proliferation`, `mental_health`, `cardiovascular`, … | 9 disease-area splits                                       |
| `random`                                                   | Random shuffle across drug-disease pairs                    |
| `full_graph`                                               | No masking; 95% train / 5% val                              |
| `disease_eval`                                             | Single disease masking for deployment                       |

## No Dev Servers

No web framework, no API server, no frontend. Use notebooks directly via
`jupyter notebook` (must be installed separately).

---

## Expanded KG Vision

### Goal

Build a **large-scale heterogeneous biomedical knowledge graph** combining
TxGNN's existing KG with OpenTargets and other sources. Nodes are registered in
**LaminDB** and identified exclusively via **ontology IDs**. Edges and node
feature tables are stored as **Parquet files**. A loader function converts
everything into a GNN-ready graph object.

### Current Export Reality (2026-06-09)

Canonical export under `gs://jouvencekb/kg/v2/` is **not yet the full expanded
KG vision**. It is currently:

- TxData legacy KG migrated to the Phase 7 Parquet layout.
- I1/I2 LaminDB/bionty registry setup and TxData node mapping.
- OpenTargets target and disease ID spaces merged enough for graph-valid
  literature endpoints.
- OpenTargets Europe PMC literature files physically added (`paper` nodes and
  `paper_mentions_gene` / `paper_mentions_disease` edges).
- OpenTargets Reactome evidence slice added as `disease_associated_gene` and
  `disease_involves_pathway`.
- OpenTargets ChEMBL molecule nodes and mechanism-of-action target edges added
  from the local Phase 4/5 slice.

As of the 2026-06-09 pass, `uv run python -m manage_db.validate_kg
gs://jouvencekb/kg/v2` reports `total_dangling_edges: 0` across the current
physical export. This means the current files are graph-valid, not complete:
many schema-vision node and edge files are still absent.

`gene` does **not** mean that `transcript` and `protein` are fully represented.
The legacy TxData source conflates `gene/protein` in places, and some relations
use `protein` as an endpoint type, but there is no dedicated
`nodes/protein.parquet` or `nodes/transcript.parquet` in the current export.

#### Current Node Files on GCS

| Node type | Rows | Status |
| --- | ---: | --- |
| `disease` | 45,407 | present; legacy + OpenTargets disease IDs |
| `gene` | 57,860 | present; legacy + OpenTargets Ensembl IDs |
| `molecule` | 31,005 | present; legacy + OpenTargets ChEMBL molecule IDs |
| `paper` | 2,958,199 | present; Europe PMC PMIDs |
| `pathway` | 48,021 | present; legacy + OpenTargets Reactome evidence stubs |
| `phenotype` | 15,311 | present; HP-derived |
| `tissue` | 14,033 | present; UBERON-derived |

Missing node files from the schema vision:
`transcript`, `protein`, `cell_type`, `mutation`, `organism`, `cell_line`,
`dataset`, `enhancer`.

#### Current Edge Files on GCS

| Relation | Rows | Status |
| --- | ---: | --- |
| `disease_associated_gene` | 2,928 | present; OpenTargets Reactome evidence slice |
| `disease_associated_protein` | 80,411 | present |
| `disease_has_phenotype` | 151,338 | present |
| `disease_involves_pathway` | 2,296 | present; OpenTargets Reactome evidence slice |
| `disease_subtype_of_disease` | 104,809 | present |
| `molecule_contraindicates_disease` | 30,675 | present |
| `molecule_in_pathway` | 1,680 | present |
| `molecule_interacts_molecule` | 2,676,768 | present |
| `molecule_targets_protein` | 41,239 | present; includes OpenTargets MoA rows with Ensembl gene endpoints pending protein resolution |
| `molecule_treats_disease` | 14,135 | present |
| `paper_mentions_disease` | 6,492,130 | present; graph-valid |
| `paper_mentions_gene` | 7,177,163 | present; graph-valid |
| `pathway_child_of_pathway` | 147,680 | present |
| `pathway_contains_gene` | 297,737 | present |
| `pathway_contains_protein` | 42,646 | present |
| `phenotype_associated_molecule` | 64,784 | present |
| `phenotype_associated_protein` | 3,330 | present |
| `phenotype_subtype_of_phenotype` | 37,472 | present |
| `protein_interacts_protein` | 642,150 | present |
| `tissue_expresses_protein` | 1,538,088 | present |
| `tissue_subtype_of_tissue` | 28,064 | present |

Missing edge files from the schema vision include all transcript/mutation/
enhancer/cell-type/cell-line/organism/dataset relations, plus several
OpenTargets relations that are implemented in code but not present in the
current canonical export: `tissue_expresses_gene`,
`cell_type_expresses_gene`, `cell_type_expresses_protein`,
`phenotype_associated_gene`, and the extra literature relations
`paper_mentions_protein`, `paper_mentions_molecule`,
`paper_mentions_mutation`, `paper_mentions_pathway`, `paper_cites_paper`,
`paper_produced_dataset`.

### Node Types & Ontology Namespaces

| Node type    | Primary ontology / ID namespace      |
| ------------ | ------------------------------------ |
| `paper`      | PubMed ID / DOI                      |
| `gene`       | Ensembl Gene ID (ENSG…)              |
| `transcript` | Ensembl Transcript ID (ENST…)        |
| `protein`    | UniProt accession                    |
| `pathway`    | Reactome / GO term                   |
| `molecule`   | ChEMBL ID / InChIKey                 |
| `mutation`   | dbSNP rsID / HGVS                    |
| `disease`    | MONDO / EFO / HP                     |
| `cell_type`  | Cell Ontology (CL:…)                 |
| `tissue`     | UBERON                               |
| `phenotype`  | Human Phenotype Ontology (HP:…)      |
| `cell_line`  | Cellosaurus (CVCL\_…)                |
| `organism`   | NCBI Taxonomy ID                     |
| `dataset`    | Internal UUID / DOI                  |
| `enhancer`   | ENCODE / Ensembl Regulatory Build ID |

### Edge Schema

All edges stored as Parquet with at minimum:

```
x_id, x_type, y_id, y_type, relation, display_relation,
source, credibility, [additional metadata columns…]
```

### Credibility Score

| Score | Meaning                                                            |
| ----- | ------------------------------------------------------------------ |
| `3`   | Established fact (curated DB, no ambiguity)                        |
| `2`   | Multiple independent evidence (papers from distinct author groups) |
| `1`   | Single evidence (one paper, possibly same authors)                 |

### Relation Types

**Kind legend:**

- `central_dogma` — molecular biology sequence/expression flow
- `regulatory` — transcriptional / epigenetic control
- `physical` — direct molecular binding or complex membership
- `genetic` — genomic position or variant association
- `pathway` — functional pathway membership
- `pharmacological` — drug action on target or disease
- `expression` — quantitative abundance in context
- `disease_assoc` — statistical or causal disease link
- `phenotype_assoc` — phenotypic consequence
- `ontological` — IS-A / part-of hierarchy
- `experimental` — derived from cell line / in-vitro assay
- `epidemiological` — population-level co-occurrence
- `literature` — NLP / co-mention in text
- `metadata` — dataset provenance

**Direct flag:**

- ✓ = direct biological interaction (physical, mechanistic, sequence-derived)
- ~ = sometimes direct depending on source
- ✗ = associative / statistical / indirect

| Relation                             | Source     | Target     | Kind            | Direct? | Notes                      |
| ------------------------------------ | ---------- | ---------- | --------------- | ------- | -------------------------- |
| `gene_has_transcript`                | gene       | transcript | central_dogma   | ✓       | Transcription              |
| `transcript_encodes_protein`         | transcript | protein    | central_dogma   | ✓       | Translation                |
| `gene_encodes_protein`               | gene       | protein    | central_dogma   | ✗       | Shortcut edge              |
| `mutation_in_gene`                   | mutation   | gene       | genetic         | ✓       | Genomic position           |
| `mutation_affects_transcript`        | mutation   | transcript | genetic         | ✓       | Splicing / UTR variant     |
| `mutation_causes_protein_change`     | mutation   | protein    | genetic         | ✓       | Amino acid change          |
| `mutation_overlaps_enhancer`         | mutation   | enhancer   | genetic         | ✓       | Regulatory variant         |
| `mutation_associated_disease`        | mutation   | disease    | genetic         | ~       | GWAS / ClinVar             |
| `mutation_causes_phenotype`          | mutation   | phenotype  | genetic         | ~       | Mendelian / GWAS           |
| `mutation_affects_molecule_response` | mutation   | molecule   | pharmacological | ~       | Pharmacogenomics           |
| `mutation_associated_cell_type`      | mutation   | cell_type  | genetic         | ✗       | eQTL cell-type enrichment  |
| `enhancer_regulates_gene`            | enhancer   | gene       | regulatory      | ✓       | ChIP-seq / Hi-C            |
| `enhancer_regulates_transcript`      | enhancer   | transcript | regulatory      | ✓       | TSS-specific regulation    |
| `enhancer_active_in_cell_type`       | enhancer   | cell_type  | regulatory      | ✓       | ATAC-seq / ChIP-seq        |
| `enhancer_active_in_tissue`          | enhancer   | tissue     | regulatory      | ✓       | Bulk ATAC / DNase-seq      |
| `enhancer_associated_disease`        | enhancer   | disease    | disease_assoc   | ~       | GWAS overlap               |
| `gene_coexpressed_gene`              | gene       | gene       | expression      | ✗       | Co-expression network      |
| `gene_ortholog_gene`                 | gene       | gene       | genetic         | ✓       | Cross-species orthology    |
| `transcript_alternative_transcript`  | transcript | transcript | central_dogma   | ✓       | Alternative splicing       |
| `protein_interacts_protein`          | protein    | protein    | physical        | ✓       | PPI (STRING, IntAct…)      |
| `pathway_contains_gene`              | pathway    | gene       | pathway         | ~       | Reactome / GO              |
| `pathway_contains_protein`           | pathway    | protein    | pathway         | ~       | Reactome / KEGG            |
| `pathway_child_of_pathway`           | pathway    | pathway    | ontological     | ✓       | Reactome hierarchy         |
| `molecule_in_pathway`                | molecule   | pathway    | pathway         | ~       | Metabolic pathway          |
| `molecule_targets_protein`           | molecule   | protein    | pharmacological | ✓       | Drug-target binding        |
| `molecule_treats_disease`            | molecule   | disease    | pharmacological | ✗       | Indication (clinical)      |
| `molecule_contraindicates_disease`   | molecule   | disease    | pharmacological | ✗       | Contraindication           |
| `molecule_interacts_molecule`        | molecule   | molecule   | pharmacological | ~       | Drug-drug interaction      |
| `disease_associated_gene`            | disease    | gene       | disease_assoc   | ~       | GWAS / rare variant        |
| `disease_associated_protein`         | disease    | protein    | disease_assoc   | ~       | Proteomics / genetics      |
| `disease_involves_pathway`           | disease    | pathway    | disease_assoc   | ✗       | Pathway enrichment         |
| `disease_associated_mutation`        | disease    | mutation   | genetic         | ~       | ClinVar / GWAS             |
| `disease_subtype_of_disease`         | disease    | disease    | ontological     | ✓       | MONDO / EFO hierarchy      |
| `disease_comorbid_disease`           | disease    | disease    | epidemiological | ✗       | Co-occurrence in EHR       |
| `disease_manifests_in_tissue`        | disease    | tissue     | disease_assoc   | ~       | Pathology annotation       |
| `disease_has_phenotype`              | disease    | phenotype  | phenotype_assoc | ✓       | HPO annotation             |
| `phenotype_observed_in_tissue`       | phenotype  | tissue     | phenotype_assoc | ~       | Anatomical manifestation   |
| `phenotype_caused_by_mutation`       | phenotype  | mutation   | genetic         | ~       | Mendelian causal           |
| `phenotype_associated_gene`          | phenotype  | gene       | phenotype_assoc | ~       | HPO-gene annotation        |
| `phenotype_associated_protein`       | phenotype  | protein    | phenotype_assoc | ✗       | Inferred via gene          |
| `phenotype_associated_molecule`      | phenotype  | molecule   | pharmacological | ✗       | Side effect / rescue       |
| `phenotype_associated_cell_type`     | phenotype  | cell_type  | phenotype_assoc | ✗       | Cell type enrichment       |
| `phenotype_subtype_of_phenotype`     | phenotype  | phenotype  | ontological     | ✓       | HPO hierarchy              |
| `tissue_expresses_gene`              | tissue     | gene       | expression      | ✓       | GTEx / HPA bulk RNA        |
| `tissue_expresses_protein`           | tissue     | protein    | expression      | ✓       | HPA / proteomics           |
| `cell_type_expresses_gene`           | cell_type  | gene       | expression      | ✓       | scRNA-seq (CellxGene)      |
| `cell_type_expresses_protein`        | cell_type  | protein    | expression      | ✓       | CyTOF / sc-proteomics      |
| `cell_type_found_in_tissue`          | cell_type  | tissue     | ontological     | ✓       | Cell Ontology / UBERON     |
| `cell_type_involved_in_disease`      | cell_type  | disease    | disease_assoc   | ✗       | scRNA disease enrichment   |
| `cell_type_responds_to_molecule`     | cell_type  | molecule   | pharmacological | ~       | Drug screen / perturbation |
| `cell_type_subtype_of_cell_type`     | cell_type  | cell_type  | ontological     | ✓       | Cell Ontology IS-A         |
| `cell_line_expresses_gene`           | cell_line  | gene       | experimental    | ✓       | RNA-seq (CCLE…)            |
| `cell_line_expresses_protein`        | cell_line  | protein    | experimental    | ✓       | Proteomics (CCLE…)         |
| `cell_line_responds_to_molecule`     | cell_line  | molecule   | experimental    | ✓       | GDSC / PRISM viability     |
| `cell_line_models_disease`           | cell_line  | disease    | experimental    | ~       | Curated annotation         |
| `cell_line_derived_from_cell_type`   | cell_line  | cell_type  | experimental    | ✓       | Cellosaurus                |
| `cell_line_derived_from_tissue`      | cell_line  | tissue     | experimental    | ✓       | Cellosaurus origin         |
| `cell_line_from_organism`            | cell_line  | organism   | metadata        | ✓       | Donor species              |
| `cell_line_associated_disease`       | cell_line  | disease    | experimental    | ~       | Added by user              |
| `organism_has_gene`                  | organism   | gene       | genetic         | ✓       | Ensembl species            |
| `organism_models_disease`            | organism   | disease    | experimental    | ~       | MGI / Alliance             |
| `organism_has_tissue`                | organism   | tissue     | ontological     | ✓       | Anatomy ontology           |
| `paper_mentions_gene`                | paper      | gene       | literature      | ✗       | NLP / Europe PMC           |
| `paper_mentions_disease`             | paper      | disease    | literature      | ✗       | NLP / Europe PMC           |
| `paper_mentions_protein`             | paper      | protein    | literature      | ✗       | NLP / Europe PMC           |
| `paper_mentions_molecule`            | paper      | molecule   | literature      | ✗       | NLP / Europe PMC           |
| `paper_mentions_mutation`            | paper      | mutation   | literature      | ✗       | NLP / Europe PMC           |
| `paper_mentions_pathway`             | paper      | pathway    | literature      | ✗       | NLP / Europe PMC           |
| `paper_produced_dataset`             | paper      | dataset    | metadata        | ✓       | Provenance                 |
| `paper_cites_paper`                  | paper      | paper      | literature      | ✓       | Citation graph             |
| `dataset_contains_gene`              | dataset    | gene       | metadata        | ✓       | Measured entity            |
| `dataset_contains_disease`           | dataset    | disease    | metadata        | ✓       | Measured entity            |
| `dataset_contains_molecule`          | dataset    | molecule   | metadata        | ✓       | Measured entity            |
| `dataset_contains_cell_type`         | dataset    | cell_type  | metadata        | ✓       | Measured entity            |
| `dataset_contains_cell_line`         | dataset    | cell_line  | metadata        | ✓       | Measured entity            |
| `dataset_contains_tissue`            | dataset    | tissue     | metadata        | ✓       | Measured entity            |

### Storage Layer

- **LaminDB**: node registry, ontology resolution, artifact versioning
- **Parquet**: one file (or directory) per edge type; node feature tables
- **bionty**: ontology resolution for Gene, Disease, Pathway, CellType, etc.
- **pertdb**: management of perturbations, and molecules

### Graph Export

Target: **PyTorch Geometric `HeteroData`** (preferred over DGL for new work —
more actively maintained, better heterogeneous graph API, richer ecosystem). DGL
`DGLHeteroGraph` kept as fallback for backward compatibility with existing TxGNN
training code.

```python
# Desired API
from txgnn import KGLoader
kg = KGLoader(data_dir='./data')
hetero_data = kg.to_pyg()   # PyG HeteroData
hetero_dgl  = kg.to_dgl()   # DGL HeteroGraph (legacy)
```

---

## Build Plan

### Phase 1 — Schema & ontology design ✅ (complete)

- [x] Node types + ontology namespaces defined
- [x] Full relation taxonomy with kind + direct flags
- [x] Cross-reference / alias tables (EFO↔MONDO↔HP, Ensembl↔UniProt…)
- [x] `txgnn/kg_schema.py` — Python schema as single source of truth

### Phase 2 — LaminDB schema

- [x] Set up `bionty` registries (Gene, Disease, Pathway, CellType, Tissue,
      Phenotype, Organism)
- [x] Define custom `Record` types for Paper, Transcript, Enhancer, Dataset,
      Mutation (`lnschema_txgnn`; CellLine already covered by `bionty`)
- [x] Register ontology source versions for reproducibility
      (`reproduce/register_ontology_sources.py`)

### Phase 3 — TxGNN KG migration ✅ (complete)

- [x] Map existing `node.csv` types → new ontology-based IDs
      (`manage_db/kg_migrate.py` — 129,375 nodes × 6 types,
      NCBI/HP/MONDO/GO/UBERON/CTD/Reactome/DrugBank)
- [x] Convert `kg.csv` edges → new edge Parquet schema (existing curated KG =
      credibility 3) (`manage_db/kg_migrate.py` — 8,100,498 edges × 17 relation
      files; zero unmapped relations)
- [x] Validate every node ID resolves to a bionty/LaminDB record (schema
      validation helper in `notebooks/kg_schema_overview.ipynb` §7; all IDs
      normalised to valid ontology formats)

### Phase 4 — OpenTargets ingestion ⚠️ (implemented, not fully exported)

`manage_db/ingest_opentargets.py` contains ingestion functions for the core
OpenTargets datasets, but the current canonical `gs://jouvencekb/kg/v2` export
does **not** yet reflect a complete OpenTargets run/merge.

- [x] `ingest_targets` → Ensembl `nodes/gene.parquet` with xrefs. Partially
      merged into the canonical export; enough Ensembl IDs exist for current
      paper and evidence endpoints.
- [x] `ingest_diseases` → EFO/MONDO disease nodes + hierarchy. Partially merged
      into the canonical export; current paper and evidence disease endpoints
      validate cleanly.
- [ ] `ingest_drugs` → ChEMBL molecule nodes. Implemented, but canonical export
      still appears legacy-sized (`8,775` molecule nodes).
- [x] Legacy/TxData `protein_interacts_protein`, `molecule_targets_protein`,
      indication/contraindication-like edges are present in the export.
- [ ] PARTIAL: `ingest_evidence` added the cached OpenTargets Reactome evidence
      slice (`2,928` `disease_associated_gene`, `2,296`
      `disease_involves_pathway`) and validates with zero dangling endpoints.
      Other evidence sources such as known_drug/chembl/genetic associations
      still need download/merge.
- [ ] Full OpenTargets `interaction`, `go`, `reactome`,
      `indication`, and `mechanismOfAction` runs need a fresh audited merge
      into the canonical export if we want the expanded OT-scale graph.
- [ ] PARTIAL: `ingest_literature` produced and uploaded `paper` nodes plus
      `paper_mentions_gene` / `paper_mentions_disease`; these now validate
      cleanly after the target/disease node ID-space merge.

### Phase 5 — Additional sources ⚠️ (partially implemented, mostly pending export)

Additional OpenTargets-derived functions exist, but the corresponding node/edge
files are missing from the current canonical export unless listed in the
Current Export Reality section above.

- [ ] `ingest_disease_phenotype`: implemented; current export has legacy
      `disease_has_phenotype`, but not an audited OT-scale merge.
- [ ] `ingest_expression`: implemented; current export lacks
      `tissue_expresses_gene`, `cell_type_expresses_gene`, and
      `cell_type_expresses_protein`.
- [ ] `ingest_biosample`: implemented; current export lacks `cell_type` nodes.
- [ ] `ingest_pharmacogenomics`: implemented; current export lacks `mutation`
      nodes and `mutation_affects_molecule_response`.
- [ ] `ingest_variants`: smoke-tested only; full mutation/transcript/protein
      variant graph remains pending.
- [ ] `ingest_enhancers`: smoke-tested only; enhancer nodes and enhancer
      regulatory edges remain pending.

### Phase 6 — Edge credibility pipeline ✅ complete

- `manage_db/credibility.py` now houses `score_credibility`, enforcing curated
  database overrides, evidence deduplication, and author-group independence.
- Composed A→C→B paths roll up through `merge_composed_path`, propagating the
  weakest credibility and annotated intermediary context.
- `dedup_edges` regenerates credibility from merged evidence while preserving
  deterministic ordering across grouped edges.
- End-to-end coverage lives in `tests/test_credibility.py`, executed via
  `uv run --group dev pytest tests/test_credibility.py -v` on CI and locally.

### Phase 7 — Parquet storage layout ✅ (complete)

```
data/kg/
  nodes/{gene,disease,protein,…}.parquet
  edges/{relation_name}.parquet
```

- `manage_db/kg_storage.py` centralises pyarrow/fsspec writes, append deduplication, and provenance/metadata helpers.
- `manage_db/ingest_opentargets.py` and `manage_db/kg_migrate.py` now flow through the storage layer for local paths and `gs://` URIs.
- `manage_db/export_kg.py` exports legacy `data/kg` layouts into `kg/v2/`, writing provenance and `SUMMARY.md` for reproducibility.
- `tests/test_kg_storage.py` covers atomic writes, schema validation, provenance, and an optional GCS smoke round-trip.
- Legacy TxGNN KG exported to `gs://jouvencekb/kg/v2`; paper files were later
  added. Current GCS layout has 7 node files and 19 edge files, but the paper
  mention edges are not yet endpoint-valid against the exported node ID spaces.

### Phase 8 — KGLoader + graph export ✅ (complete)

- `txgnn.KGLoader(data_dir)` scans node/edge parquets and builds stable node ID maps.
- `KGLoader.validate()` reports node counts, edge counts, and dangling-edge counts.
- `KGLoader.edge_index_frames()` exports integer edge tables keyed by canonical edge type.
- `to_pyg()` → `torch_geometric.data.HeteroData` when optional PyG deps are installed.
- `to_dgl()` → `dgl.heterograph` when optional DGL deps are installed.
- `txgnn.__init__` uses lazy heavy imports so `from txgnn import KGLoader` works without importing DGL.

### Phase 9 — Validation

- [x] Dangling edge checks (`KGLoader.validate()`)
- [x] Schema coverage audit CLI:
      `uv run python -m manage_db.audit_kg_coverage gs://jouvencekb/kg/v2`
      reports physical node/edge file coverage against `kg_schema.py`. Current
      GCS export: 7/15 node files, 19/77 edge files. See
      `docs/kg_coverage_audit.md`.
- [x] Remote smoke validation before paper upload: legacy-only
      `KGLoader("gs://jouvencekb/kg/v2").validate()` returned 129,312 nodes,
      5,848,026 edges, 0 dangling edges.
- [ ] Re-run validation after paper upload and OpenTargets node ID merge.
      Current paper files are expected to fail dangling checks because
      `paper_mentions_gene` uses `ENSG...` IDs while exported genes are
      `NCBI:*`, and `paper_mentions_disease` uses `EFO_...`/`MONDO_...` IDs
      while exported disease nodes are legacy-normalized.
- [ ] Node ontology coverage stats
- [ ] Smoke-test: load full graph into PyG once `torch`/`torch_geometric` are installed in the target runtime.
