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
- Output: see `i1_run.log` for counts; executed notebook at
  `notebooks/1_lamindb_instance_setup.executed.ipynb`.
- HP (Human Phenotype Ontology) is the active Phenotype source (PATO disabled
  per §7).

### I2 — custom records + node sync (2026-06-05)

- Run: `python -m manage_db.i2_custom_records_and_sync` (idempotent).
- 5 custom `lnschema_txgnn` record types deployed (Paper, Transcript, Enhancer,
  Dataset, Mutation).
- Sync mapped 129,375 nodes (existing=125,744, created=30, uncertain=3,601); see
  `data/txdata/node_entity_mapping.csv`.
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
- OpenTargets biosample and expression slice added as `cell_type` nodes plus
  `tissue_expresses_gene` / `cell_type_expresses_gene` edges. Expression-only
  Ensembl gene stubs are present where needed for graph-valid endpoints.
- OpenTargets disease-phenotype HPO slice merged into `disease_has_phenotype`
  with normalized `MONDO:` / `HP:` endpoints and endpoint stubs where needed.
- OpenTargets pharmacogenomics slice added as `mutation` stubs plus
  `mutation_affects_molecule_response` edges.

As of the 2026-06-09 pass,
`uv run python -m manage_db.validate_kg gs://jouvencekb/kg/v2` reports
`total_dangling_edges: 0` across the current physical export. This means the
current files are graph-valid, not complete: many schema-vision node and edge
files are still absent. The coverage audit currently reports `10 / 15` node
files, `25 / 77` edge files, `3,467,844` total nodes, and `25,559,913` total
edges.

`gene` does **not** mean that `transcript` and `protein` are fully represented.
The legacy TxData source conflates `gene/protein` in places, and some relations
use `protein` as an endpoint type, but those legacy edges still physically use
`gene` endpoints. Dedicated `nodes/protein.parquet` now exists with Ensembl
Protein (`ENSP`) IDs; `nodes/transcript.parquet` is still absent.
Current GCS edge files named `*protein*` physically validate through `gene`
endpoints (`NCBI:` / `ENSG` IDs); they should be treated as legacy
gene/protein-conflated relations until a protein-edge remapping pass exists.
The first ENSP remapping audit found this is not safely one-to-one: most legacy
protein endpoints are `NCBI:` IDs, and many Ensembl genes have multiple ENSP
translations. Only `1,528` sampled `molecule_targets_protein` endpoints were
unambiguously mappable to a single ENSP, so the next safe edge is
`gene_encodes_protein` from the new `nodes/protein.parquet`, not blind rewrites
of legacy protein-named edges.

### Node Schema & GCS Coverage

| Node type    | Primary ontology / ID namespace               | GCS? |      Rows | Comment                                                                             |
| ------------ | --------------------------------------------- | ---- | --------: | ----------------------------------------------------------------------------------- |
| `paper`      | PubMed (`PMID:12345678`)                      | yes  | 2,958,199 | Europe PMC PMIDs                                                                    |
| `gene`       | Ensembl (`ENSG00000139618`)                   | yes  |   109,325 | legacy + OpenTargets 26.03 target IDs; expression/evidence stubs added              |
| `transcript` | Ensembl (`ENST00000380152`)                   | no   |         - | not exported yet                                                                    |
| `protein`    | Ensembl Protein (`ENSP00000369497`)           | yes  |   233,995 | OpenTargets 26.03 target translations; UniProt is an xref                           |
| `pathway`    | Reactome / GO (`R-HSA-5633007`, `GO:0008150`) | yes  |    48,575 | legacy + OpenTargets Reactome evidence stubs + GO terms                             |
| `molecule`   | ChEMBL (`CHEMBL941`)                          | yes  |    31,007 | legacy + OpenTargets `drug_molecule` xrefs/properties; pharmacogenomics stubs added |
| `mutation`   | dbSNP (`rs7412`)                              | yes  |     2,429 | OpenTargets pharmacogenomics stubs                                                  |
| `disease`    | EFO (`EFO:0000305`)                           | yes  |    48,291 | legacy + OpenTargets disease IDs; disease-phenotype stubs added                     |
| `cell_type`  | CL (`CL:0000576`)                             | yes  |     3,513 | OpenTargets biosample CL IDs                                                        |
| `tissue`     | UBERON (`UBERON:0002107`)                     | yes  |    16,061 | UBERON-derived + OpenTargets biosample                                              |
| `phenotype`  | HP (`HP:0000118`)                             | yes  |    16,449 | HP-derived + OpenTargets HPO stubs                                                  |
| `cell_line`  | Cellosaurus (`CVCL_0023`)                     | no   |         - | not exported yet                                                                    |
| `organism`   | NCBI Taxonomy (`9606`)                        | no   |         - | not exported yet                                                                    |
| `dataset`    | DOI / UUID (`DOI:10.1038/s41586-023-06221-2`) | no   |         - | not exported yet                                                                    |
| `enhancer`   | ENCODE (`EH38E1516972`)                       | no   |         - | not exported yet                                                                    |

### Edge Schema & GCS Coverage

All edges stored as Parquet with at minimum:

```
x_id, x_type, y_id, y_type, relation, display_relation,
source, credibility, [additional metadata columns...]
```

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

- yes = direct biological interaction (physical, mechanistic, sequence-derived)
- maybe = sometimes direct depending on source
- no = associative / statistical / indirect

| Relation                             | Source       | Target       | Kind              | Direct? | GCS? |      Rows | Comment                                                                   |
| ------------------------------------ | ------------ | ------------ | ----------------- | ------- | ---- | --------: | ------------------------------------------------------------------------- |
| `gene_has_transcript`                | `gene`       | `transcript` | `central_dogma`   | yes     | no   |         - | not exported yet                                                          |
| `transcript_encodes_protein`         | `transcript` | `protein`    | `central_dogma`   | yes     | no   |         - | not exported yet                                                          |
| `gene_encodes_protein`               | `gene`       | `protein`    | `central_dogma`   | no      | yes  |   233,995 | OpenTargets ENSG→ENSP translations                                        |
| `transcript_alternative_transcript`  | `transcript` | `transcript` | `central_dogma`   | yes     | no   |         - | not exported yet                                                          |
| `mutation_in_gene`                   | `mutation`   | `gene`       | `genetic`         | yes     | no   |         - | not exported yet                                                          |
| `mutation_affects_transcript`        | `mutation`   | `transcript` | `genetic`         | yes     | no   |         - | not exported yet                                                          |
| `mutation_causes_protein_change`     | `mutation`   | `protein`    | `genetic`         | yes     | no   |         - | not exported yet                                                          |
| `mutation_overlaps_enhancer`         | `mutation`   | `enhancer`   | `genetic`         | yes     | no   |         - | not exported yet                                                          |
| `mutation_associated_disease`        | `mutation`   | `disease`    | `genetic`         | no      | no   |         - | not exported yet                                                          |
| `mutation_causes_phenotype`          | `mutation`   | `phenotype`  | `genetic`         | no      | no   |         - | not exported yet                                                          |
| `mutation_affects_molecule_response` | `mutation`   | `molecule`   | `pharmacological` | no      | yes  |     4,866 | OpenTargets pharmacogenomics                                              |
| `mutation_associated_cell_type`      | `mutation`   | `cell_type`  | `genetic`         | no      | no   |         - | not exported yet                                                          |
| `gene_ortholog_gene`                 | `gene`       | `gene`       | `genetic`         | yes     | no   |         - | not exported yet                                                          |
| `enhancer_regulates_gene`            | `enhancer`   | `gene`       | `regulatory`      | no      | no   |         - | not exported yet                                                          |
| `enhancer_regulates_transcript`      | `enhancer`   | `transcript` | `regulatory`      | yes     | no   |         - | not exported yet                                                          |
| `enhancer_active_in_cell_type`       | `enhancer`   | `cell_type`  | `regulatory`      | yes     | no   |         - | not exported yet                                                          |
| `enhancer_active_in_tissue`          | `enhancer`   | `tissue`     | `regulatory`      | yes     | no   |         - | not exported yet                                                          |
| `enhancer_associated_disease`        | `enhancer`   | `disease`    | `disease_assoc`   | no      | no   |         - | not exported yet                                                          |
| `gene_coexpressed_gene`              | `gene`       | `gene`       | `expression`      | no      | no   |         - | not exported yet                                                          |
| `tissue_expresses_gene`              | `tissue`     | `gene`       | `expression`      | yes     | yes  | 3,800,648 | OpenTargets expression                                                    |
| `tissue_expresses_protein`           | `tissue`     | `protein`    | `expression`      | yes     | yes  | 1,538,088 | legacy gene/protein endpoints (`y_type=gene`)                             |
| `cell_type_expresses_gene`           | `cell_type`  | `gene`       | `expression`      | yes     | yes  | 1,561,873 | OpenTargets expression                                                    |
| `cell_type_expresses_protein`        | `cell_type`  | `protein`    | `expression`      | yes     | no   |         - | not exported yet                                                          |
| `cell_line_expresses_gene`           | `cell_line`  | `gene`       | `experimental`    | yes     | no   |         - | not exported yet                                                          |
| `cell_line_expresses_protein`        | `cell_line`  | `protein`    | `experimental`    | yes     | no   |         - | not exported yet                                                          |
| `protein_interacts_protein`          | `protein`    | `protein`    | `physical`        | yes     | yes  |   642,150 | legacy gene/protein endpoints (`gene` → `gene`)                           |
| `pathway_contains_gene`              | `pathway`    | `gene`       | `pathway`         | no      | yes  |   588,286 | Reactome / OpenTargets GO                                                 |
| `pathway_contains_protein`           | `pathway`    | `protein`    | `pathway`         | no      | yes  |    42,646 | legacy gene/protein endpoints (`y_type=gene`)                             |
| `pathway_child_of_pathway`           | `pathway`    | `pathway`    | `ontological`     | yes     | yes  |   147,680 | Reactome hierarchy                                                        |
| `molecule_in_pathway`                | `molecule`   | `pathway`    | `pathway`         | no      | yes  |     1,680 | Metabolic pathway                                                         |
| `molecule_targets_protein`           | `molecule`   | `protein`    | `pharmacological` | yes     | yes  |    41,239 | legacy gene/protein endpoints (`y_type=gene`); protein resolution pending |
| `molecule_treats_disease`            | `molecule`   | `disease`    | `pharmacological` | no      | yes  |    14,135 | Indication (clinical)                                                     |
| `molecule_contraindicates_disease`   | `molecule`   | `disease`    | `pharmacological` | no      | yes  |    30,675 | Contraindication                                                          |
| `molecule_interacts_molecule`        | `molecule`   | `molecule`   | `pharmacological` | no      | yes  | 2,676,768 | Drug-drug interaction                                                     |
| `cell_type_responds_to_molecule`     | `cell_type`  | `molecule`   | `pharmacological` | no      | no   |         - | not exported yet                                                          |
| `cell_line_responds_to_molecule`     | `cell_line`  | `molecule`   | `experimental`    | yes     | no   |         - | not exported yet                                                          |
| `phenotype_associated_molecule`      | `phenotype`  | `molecule`   | `pharmacological` | no      | yes  |    64,784 | Side effect / rescue                                                      |
| `disease_associated_gene`            | `disease`    | `gene`       | `disease_assoc`   | no      | yes  |     2,928 | OpenTargets Reactome evidence slice                                       |
| `disease_associated_protein`         | `disease`    | `protein`    | `disease_assoc`   | no      | yes  |    80,411 | legacy gene/protein endpoints (`y_type=gene`)                             |
| `disease_involves_pathway`           | `disease`    | `pathway`    | `disease_assoc`   | no      | yes  |     2,296 | OpenTargets Reactome evidence slice                                       |
| `disease_associated_mutation`        | `disease`    | `mutation`   | `genetic`         | no      | no   |         - | not exported yet                                                          |
| `disease_manifests_in_tissue`        | `disease`    | `tissue`     | `disease_assoc`   | no      | no   |         - | not exported yet                                                          |
| `disease_subtype_of_disease`         | `disease`    | `disease`    | `ontological`     | yes     | yes  |   104,809 | EFO / MONDO hierarchy                                                     |
| `disease_comorbid_disease`           | `disease`    | `disease`    | `epidemiological` | no      | no   |         - | not exported yet                                                          |
| `disease_has_phenotype`              | `disease`    | `phenotype`  | `phenotype_assoc` | yes     | yes  |   241,797 | legacy + OpenTargets HPO                                                  |
| `phenotype_observed_in_tissue`       | `phenotype`  | `tissue`     | `phenotype_assoc` | no      | no   |         - | not exported yet                                                          |
| `phenotype_caused_by_mutation`       | `phenotype`  | `mutation`   | `genetic`         | no      | no   |         - | not exported yet                                                          |
| `phenotype_associated_gene`          | `phenotype`  | `gene`       | `phenotype_assoc` | no      | no   |         - | not exported yet                                                          |
| `phenotype_associated_protein`       | `phenotype`  | `protein`    | `phenotype_assoc` | no      | yes  |     3,330 | legacy gene/protein endpoints (`y_type=gene`)                             |
| `phenotype_associated_cell_type`     | `phenotype`  | `cell_type`  | `phenotype_assoc` | no      | no   |         - | not exported yet                                                          |
| `phenotype_subtype_of_phenotype`     | `phenotype`  | `phenotype`  | `ontological`     | yes     | yes  |    37,472 | HPO hierarchy                                                             |
| `tissue_subtype_of_tissue`           | `tissue`     | `tissue`     | `ontological`     | yes     | yes  |    28,064 | UBERON parent-child hierarchy                                             |
| `cell_type_found_in_tissue`          | `cell_type`  | `tissue`     | `ontological`     | yes     | no   |         - | not exported yet                                                          |
| `cell_type_involved_in_disease`      | `cell_type`  | `disease`    | `disease_assoc`   | no      | no   |         - | not exported yet                                                          |
| `cell_type_subtype_of_cell_type`     | `cell_type`  | `cell_type`  | `ontological`     | yes     | no   |         - | not exported yet                                                          |
| `cell_line_models_disease`           | `cell_line`  | `disease`    | `experimental`    | no      | no   |         - | not exported yet                                                          |
| `cell_line_derived_from_cell_type`   | `cell_line`  | `cell_type`  | `experimental`    | yes     | no   |         - | not exported yet                                                          |
| `cell_line_derived_from_tissue`      | `cell_line`  | `tissue`     | `experimental`    | yes     | no   |         - | not exported yet                                                          |
| `cell_line_from_organism`            | `cell_line`  | `organism`   | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `cell_line_associated_disease`       | `cell_line`  | `disease`    | `experimental`    | no      | no   |         - | not exported yet                                                          |
| `organism_has_gene`                  | `organism`   | `gene`       | `genetic`         | yes     | no   |         - | not exported yet                                                          |
| `organism_models_disease`            | `organism`   | `disease`    | `experimental`    | no      | no   |         - | not exported yet                                                          |
| `organism_has_tissue`                | `organism`   | `tissue`     | `ontological`     | yes     | no   |         - | not exported yet                                                          |
| `paper_mentions_gene`                | `paper`      | `gene`       | `literature`      | no      | yes  | 7,177,163 | Europe PMC; graph-valid                                                   |
| `paper_mentions_disease`             | `paper`      | `disease`    | `literature`      | no      | yes  | 6,492,130 | Europe PMC; graph-valid                                                   |
| `paper_mentions_protein`             | `paper`      | `protein`    | `literature`      | no      | no   |         - | not exported yet                                                          |
| `paper_mentions_molecule`            | `paper`      | `molecule`   | `literature`      | no      | no   |         - | not exported yet                                                          |
| `paper_mentions_mutation`            | `paper`      | `mutation`   | `literature`      | no      | no   |         - | not exported yet                                                          |
| `paper_mentions_pathway`             | `paper`      | `pathway`    | `literature`      | no      | no   |         - | not exported yet                                                          |
| `paper_produced_dataset`             | `paper`      | `dataset`    | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `paper_cites_paper`                  | `paper`      | `paper`      | `literature`      | yes     | no   |         - | not exported yet                                                          |
| `dataset_contains_gene`              | `dataset`    | `gene`       | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `dataset_contains_disease`           | `dataset`    | `disease`    | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `dataset_contains_molecule`          | `dataset`    | `molecule`   | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `dataset_contains_cell_type`         | `dataset`    | `cell_type`  | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `dataset_contains_cell_line`         | `dataset`    | `cell_line`  | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `dataset_contains_tissue`            | `dataset`    | `tissue`     | `metadata`        | yes     | no   |         - | not exported yet                                                          |

### Credibility Score

| Score | Meaning                                                            |
| ----- | ------------------------------------------------------------------ |
| `3`   | Established fact (curated DB, no ambiguity)                        |
| `2`   | Multiple independent evidence (papers from distinct author groups) |
| `1`   | Single evidence (one paper, possibly same authors)                 |

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

- [x] `ingest_targets` → Ensembl `nodes/gene.parquet` with xrefs. OpenTargets
      26.03 target IDs are merged into the canonical export.
- [x] `ingest_diseases` → EFO/MONDO disease nodes + hierarchy. Partially merged
      into the canonical export; current paper and evidence disease endpoints
      validate cleanly.
- [x] `ingest_drugs` → ChEMBL molecule nodes. OpenTargets `drug_molecule`
      xrefs/properties are merged into `nodes/molecule.parquet`; the row count
      remains `31,007` because the merge enriches existing ChEMBL nodes rather
      than adding new endpoint IDs.
- [x] Legacy/TxData `protein_interacts_protein`, `molecule_targets_protein`,
      indication/contraindication-like edges are present in the export.
- [ ] PARTIAL: `ingest_evidence` added the cached OpenTargets Reactome evidence
      slice (`2,928` `disease_associated_gene`, `2,296`
      `disease_involves_pathway`) and validates with zero dangling endpoints.
      Other evidence sources such as known_drug/chembl/genetic associations
      still need download/merge.
- [ ] Full OpenTargets `interaction`, `reactome`, `indication`, and
      `mechanismOfAction` runs need a fresh audited merge into the canonical
      export if we want the expanded OT-scale graph. OpenTargets 26.03
      `target` + `go` are merged and validated.
- [ ] PARTIAL: `ingest_literature` produced and uploaded `paper` nodes plus
      `paper_mentions_gene` / `paper_mentions_disease`; these now validate
      cleanly after the target/disease node ID-space merge.

### Phase 5 — Additional sources ⚠️ (partially implemented, mostly pending export)

Additional OpenTargets-derived functions exist, but the corresponding node/edge
files are missing from the current canonical export unless listed in the Current
Export Reality section above.

- [x] `ingest_disease_phenotype`: OpenTargets HPO slice merged and audited with
      normalized `MONDO:` / `HP:` endpoints.
- [ ] PARTIAL: `ingest_expression` added OpenTargets `tissue_expresses_gene` and
      `cell_type_expresses_gene`; `cell_type_expresses_protein` remains pending.
- [x] `ingest_biosample`: OpenTargets `cell_type` nodes are present in the
      canonical export.
- [x] `ingest_pharmacogenomics`: OpenTargets pharmacogenomics slice merged as
      `mutation` stubs and `mutation_affects_molecule_response`.
- [ ] `ingest_variants`: smoke-tested only; full mutation/transcript/protein
      variant graph remains pending.
- [ ] `ingest_enhancers`: smoke-tested only; enhancer nodes and enhancer
      regulatory edges remain pending.
- [ ] Add source features: for each source, download and add their real feature
      (e.g. genes get their sequence, same for transcripts, molecules, proteins,
      enhancers) for paper, get their abstract and discussion.

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

- `manage_db/kg_storage.py` centralises pyarrow/fsspec writes, append
  deduplication, and provenance/metadata helpers.
- `manage_db/ingest_opentargets.py` and `manage_db/kg_migrate.py` now flow
  through the storage layer for local paths and `gs://` URIs.
- `manage_db/export_kg.py` exports legacy `data/kg` layouts into `kg/v2/`,
  writing provenance and `SUMMARY.md` for reproducibility.
- `tests/test_kg_storage.py` covers atomic writes, schema validation,
  provenance, and an optional GCS smoke round-trip.
- Legacy TxGNN KG exported to `gs://jouvencekb/kg/v2`; paper, Reactome,
  molecule/MoA, biosample, and expression slices were later added. Current GCS
  layout has 8 node files and 23 edge files and validates with zero dangling
  edges.

### Phase 8 — KGLoader + graph export ✅ (complete)

- `txgnn.KGLoader(data_dir)` scans node/edge parquets and builds stable node ID
  maps.
- `KGLoader.validate()` reports node counts, edge counts, and dangling-edge
  counts.
- `KGLoader.edge_index_frames()` exports integer edge tables keyed by canonical
  edge type.
- `to_pyg()` → `torch_geometric.data.HeteroData` when optional PyG deps are
  installed.
- `to_dgl()` → `dgl.heterograph` when optional DGL deps are installed.
- `txgnn.__init__` uses lazy heavy imports so `from txgnn import KGLoader` works
  without importing DGL.

### Phase 9 — Validation

- [x] Dangling edge checks (`KGLoader.validate()`)
- [x] Schema coverage audit CLI:
      `uv run python -m manage_db.audit_kg_coverage gs://jouvencekb/kg/v2`
      reports physical node/edge file coverage against `kg_schema.py`. Current
      GCS export: 8/15 node files, 23/77 edge files. See
      `docs/kg_coverage_audit.md`.
- [x] Remote GCS validation after paper, OpenTargets ID-space merge,
      biosample/expression, and disease-phenotype promotion:
      `uv run python -m manage_db.validate_kg gs://jouvencekb/kg/v2` reports
      `3,467,844` nodes, `25,559,913` edges, and `total_dangling_edges: 0`.
- [ ] Node ontology coverage stats
- [ ] Final TxGNN model smoke test on the VPS. This must be a tiny model and
      must run under explicit systemd limits: at most `CPUQuota=200%` and
      `MemoryMax=4G`. Use local/scratch data, no production GCS mutation, and
      treat any memory/CPU pressure as a blocker rather than raising limits.
