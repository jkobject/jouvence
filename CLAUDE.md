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
- 7 custom `lnschema_txgnn` record types deployed live (Paper, Transcript, Disease,
  Enhancer, Dataset, Mutation, Protein). The 2026-06-10 `0004_protein` migration
  created `lnschema_txgnn_protein`; the 2026-06-11 `0005_custom_disease`
  migration created `lnschema_txgnn_disease` so non-MONDO disease-like KG terms
  are represented without direct insertion into MONDO-backed `bionty.Disease`.
  Canonical GCS parity passes for `lnschema_txgnn.Protein` (`233,995` ENSP
  proteins), `lnschema_txgnn.Disease` (`38,323` normalized disease IDs), and
  `lnschema_txgnn.Paper` (canonical GCS currently has `2,958,199` literature
  PMIDs represented); the retired local
  paper source is archived at
  `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0940Z/txgnn-literature.tar.zst`.
- Sync mapped 129,375 nodes (existing=125,744, created=30, uncertain=3,601); see
  `data/txdata/node_entity_mapping.csv`.
- Executed notebook: `notebooks/2_manage_db_setup.executed.ipynb`.

Doctrine note: `bt.Protein` exists but is UniProt-centric. TxGNN `protein`
nodes are Ensembl Protein (`ENSP`) translation products and use custom
`lnschema_txgnn.Protein` for now, keyed by `ensembl_protein_id`; `uniprot_id`
is stored only as an xref. `bt.Disease` remains MONDO-backed in this instance;
TxGNN KG disease nodes now use custom `lnschema_txgnn.Disease` keyed by the
normalized source ontology CURIE (for example `EFO:0000094`) unless/until an
explicit exact MONDO mapping policy is added.

### KG Parquet node sync

- Dry-run audit/sync: `uv run python -m manage_db.sync_parquet_nodes_to_lamindb <kg_root>`
  (default; no LaminDB writes).
- Creating missing LaminDB/bionty/pertdb records requires explicit `--write`; do
  not use `--write` unless the run is intentionally opt-in.

## Data

- Knowledge graph CSVs: `data/kg.csv`, `node.csv`, `edges.csv` (Harvard
  Dataverse)
- Download: `txdata_download.py` — EBI FTP HTTP mirror for OpenTargets, stdlib
  for Harvard
- OpenTargets: parallel download via threads, `.ot_complete` marker, alias
  resolution
- LaminDB integration exists (`reproduce/sync_nodes_to_lamindb.py`)
- Disease area files: `data/disease_files/*.csv`

### Storage Doctrine

- Do not create or depend on TxGNN/Jouvence work data under
  `/home/ubuntu/data/`. Project-owned working state should live in this repo
  when it is code/config/small reports, or in `gs://jouvencekb/` when it is KG
  data, scratch output, archives, or large artifacts.
- GCS is mounted on the VPS at `/mnt/gcs/jouvencekb` via
  `gcsfuse-jouvencekb.service`; canonical KG data lives under
  `/mnt/gcs/jouvencekb/kg/`.
- Keep active LaminDB SQLite cache local for locking/performance; do not place
  the active SQLite DB on GCS FUSE. The local LaminDB cache is
  `/home/ubuntu/lamindb-cache`.

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

Project completion rule from 2026-06-10: a KG slice is only **done** when
both conditions are true:

1. Clean Parquet node/edge files are promoted to the canonical/versioned GCS KG
   root and validate with zero dangling edges.
2. The corresponding node IDs are represented in LaminDB/bionty/custom
   registries. Local scratch Parquets or GCS-only Parquets are **not** done.

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

As of the 2026-06-15 remaining-slices promotion, the canonical export under
`/mnt/gcs/jouvencekb/kg/v2` contains all `15 / 15` node files and `40 / 77`
edge files, with `55,365,186` total nodes and `144,155,654` total edges. The
largest new slice is `enhancer` (`48,808,144` nodes) plus enhancer regulatory
edges. The default `manage_db.validate_kg` path is now an exact DuckDB anti-join
validator intended for the mounted GCS-FUSE path, for example:

```bash
uv run --no-sync python -m manage_db.validate_kg /mnt/gcs/jouvencekb/kg/v2 \
  --threads 2 --duckdb-memory-limit 4GB --duckdb-temp-dir .omoc/duckdb-tmp \
  --progress-every-relations 1
```

The previous PyArrow streaming validator timed out or exhausted memory once
`enhancer` was promoted because it materialized high-cardinality node ID sets in
Python. Use `--pyarrow-streaming` only for small/remote KGs that DuckDB cannot
read directly; do not use it for the canonical enhancer-scale export.

`gene` does **not** mean that `transcript` and `protein` are fully represented.
The legacy TxData source conflates `gene/protein` in places, and some relations
use `protein` as an endpoint type, but those legacy edges still physically use
`gene` endpoints. Dedicated `nodes/protein.parquet` now exists with Ensembl
Protein (`ENSP`) IDs, and `lnschema_txgnn.Protein` is live with ENSP primary
IDs plus gene/UniProt/RefSeq/PDB xrefs. `nodes/transcript.parquet` is present
from OpenTargets target transcripts.
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
| `paper`      | PubMed (`PMID:12345678`)                      | yes  | 2,958,199 | Europe PMC PMIDs; live `lnschema_txgnn.Paper` parity passes                         |
| `gene`       | Ensembl (`ENSG00000139618`)                   | yes  |   109,325 | legacy + OpenTargets 26.03 target IDs; expression/evidence stubs added              |
| `transcript` | Ensembl (`ENST00000380152`)                   | yes  |   507,365 | OpenTargets 26.03 target transcripts                                                |
| `protein`    | Ensembl Protein (`ENSP00000369497`)           | yes  |   233,995 | OpenTargets 26.03 target translations; UniProt is an xref                           |
| `pathway`    | Reactome / GO (`R-HSA-5633007`, `GO:0008150`) | yes  |    48,575 | legacy + OpenTargets Reactome evidence stubs + GO terms                             |
| `molecule`   | ChEMBL (`CHEMBL941`)                          | yes  |    31,007 | legacy + OpenTargets `drug_molecule` xrefs/properties; pharmacogenomics stubs added |
| `mutation`   | dbSNP (`rs7412`) / gnomAD-style variant IDs    | yes  | 2,589,509 | pharmacogenomics stubs + promoted protein-change/GWAS mutation union               |
| `disease`    | EFO (`EFO:0000305`)                           | yes  |    41,859 | legacy + OpenTargets disease IDs; normalized CURIE IDs with duplicate underscore/colon rows collapsed |
| `cell_type`  | CL (`CL:0000576`)                             | yes  |     3,513 | OpenTargets biosample CL IDs                                                        |
| `tissue`     | UBERON (`UBERON:0002107`)                     | yes  |    16,061 | UBERON-derived + OpenTargets biosample                                              |
| `phenotype`  | HP (`HP:0000118`)                             | yes  |    16,449 | HP-derived + OpenTargets HPO stubs                                                  |
| `cell_line`  | Cellosaurus (`CVCL_0023`)                     | yes  |     1,183 | OpenTargets DepMap/essentiality cell model IDs; source-backed remaining slice       |
| `organism`   | NCBI Taxonomy (`NCBITaxon:9606`)              | yes  |         1 | human organism node; LaminDB/bionty parity passes                                   |
| `dataset`    | DOI / UUID (`DOI:10.1038/s41586-023-06221-2`) | yes  |         1 | OpenTargets DepMap/essentiality dataset provenance node                             |
| `enhancer`   | ENCODE/OpenTargets interval ID                | yes  | 48,808,144 | OpenTargets enhancer interval IDs from enhancer-to-gene evidence                    |

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
| `gene_has_transcript`                | `gene`       | `transcript` | `central_dogma`   | yes     | yes  |   507,365 | OpenTargets target transcripts                                             |
| `transcript_encodes_protein`         | `transcript` | `protein`    | `central_dogma`   | yes     | yes  |   233,995 | OpenTargets ENST→ENSP translations                                         |
| `gene_encodes_protein`               | `gene`       | `protein`    | `central_dogma`   | no      | yes  |   233,995 | OpenTargets ENSG→ENSP translations                                        |
| `transcript_alternative_transcript`  | `transcript` | `transcript` | `central_dogma`   | yes     | no   |         - | not exported yet                                                          |
| `mutation_in_gene`                   | `mutation`   | `gene`       | `genetic`         | yes     | no   |         - | 26.03 `variant` staged; smoke shows full relation is too dense for blind promotion |
| `mutation_associated_gene`           | `mutation`   | `gene`       | `genetic`         | no      | yes  |   535,093 | OpenTargets L2G GWAS credible-set join; promoted 2026-06-10 with zero dangling endpoints |
| `mutation_affects_transcript`        | `mutation`   | `transcript` | `genetic`         | yes     | no   |         - | 26.03 `variant` staged; smoke shows full relation is too dense for blind promotion |
| `mutation_causes_protein_change`     | `mutation`   | `protein`    | `genetic`         | yes     | yes  |   177,735 | promoted 2026-06-10 from bounded variant scratch; ENSP protein endpoints             |
| `mutation_overlaps_enhancer`         | `mutation`   | `enhancer`   | `genetic`         | yes     | no   |         - | not exported yet                                                          |
| `mutation_associated_disease`        | `mutation`   | `disease`    | `genetic`         | no      | yes  | 4,656,171 | OpenTargets known-variant + GWAS disease evidence promoted 2026-06-11 with zero dangling endpoints |
| `mutation_causes_phenotype`          | `mutation`   | `phenotype`  | `genetic`         | no      | no   |         - | not exported yet                                                          |
| `mutation_affects_molecule_response` | `mutation`   | `molecule`   | `pharmacological` | no      | yes  |     4,866 | OpenTargets pharmacogenomics                                              |
| `mutation_associated_cell_type`      | `mutation`   | `cell_type`  | `genetic`         | no      | no   |         - | not exported yet                                                          |
| `gene_ortholog_gene`                 | `gene`       | `gene`       | `genetic`         | yes     | no   |         - | not exported yet                                                          |
| `enhancer_regulates_gene`            | `enhancer`   | `gene`       | `regulatory`      | no      | yes  | 48,808,144 | OpenTargets enhancer-to-gene evidence; endpoint-validated                 |
| `enhancer_regulates_transcript`      | `enhancer`   | `transcript` | `regulatory`      | yes     | no   |         - | not exported yet                                                          |
| `enhancer_active_in_cell_type`       | `enhancer`   | `cell_type`  | `regulatory`      | yes     | yes  | 19,700,144 | OpenTargets enhancer activity context; endpoint-validated                 |
| `enhancer_active_in_tissue`          | `enhancer`   | `tissue`     | `regulatory`      | yes     | yes  | 22,903,506 | OpenTargets enhancer activity context; endpoint-validated                 |
| `enhancer_associated_disease`        | `enhancer`   | `disease`    | `disease_assoc`   | no      | no   |         - | not exported yet                                                          |
| `gene_coexpressed_gene`              | `gene`       | `gene`       | `expression`      | no      | no   |         - | not exported yet                                                          |
| `tissue_expresses_gene`              | `tissue`     | `gene`       | `expression`      | yes     | yes  | 3,800,648 | OpenTargets expression                                                    |
| `tissue_expresses_protein`           | `tissue`     | `protein`    | `expression`      | yes     | yes  | 1,538,088 | legacy gene/protein endpoints (`y_type=gene`)                             |
| `cell_type_expresses_gene`           | `cell_type`  | `gene`       | `expression`      | yes     | yes  | 1,561,873 | OpenTargets expression                                                    |
| `cell_type_expresses_protein`        | `cell_type`  | `protein`    | `expression`      | yes     | no   |         - | not exported yet                                                          |
| `cell_line_expresses_gene`           | `cell_line`  | `gene`       | `experimental`    | yes     | yes  | 20,928,056 | OpenTargets DepMap target essentiality/expression slice                   |
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
| `cell_line_derived_from_tissue`      | `cell_line`  | `tissue`     | `experimental`    | yes     | yes  |     1,092 | OpenTargets DepMap cell line tissue provenance                            |
| `cell_line_from_organism`            | `cell_line`  | `organism`   | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `cell_line_associated_disease`       | `cell_line`  | `disease`    | `experimental`    | no      | no   |         - | not exported yet                                                          |
| `organism_has_gene`                  | `organism`   | `gene`       | `genetic`         | yes     | yes  |   109,325 | human-only KG provenance; zero dangling endpoints                         |
| `organism_models_disease`            | `organism`   | `disease`    | `experimental`    | no      | no   |         - | not exported yet                                                          |
| `organism_has_tissue`                | `organism`   | `tissue`     | `ontological`     | yes     | yes  |    16,061 | human-only KG anatomy provenance; zero dangling endpoints                 |
| `paper_mentions_gene`                | `paper`      | `gene`       | `literature`      | no      | yes  | 7,177,163 | Europe PMC; graph-valid                                                   |
| `paper_mentions_disease`             | `paper`      | `disease`    | `literature`      | no      | yes  | 6,492,130 | Europe PMC; graph-valid                                                   |
| `paper_mentions_protein`             | `paper`      | `protein`    | `literature`      | no      | no   |         - | not exported yet                                                          |
| `paper_mentions_molecule`            | `paper`      | `molecule`   | `literature`      | no      | no   |         - | not exported yet                                                          |
| `paper_mentions_mutation`            | `paper`      | `mutation`   | `literature`      | no      | no   |         - | not exported yet                                                          |
| `paper_mentions_pathway`             | `paper`      | `pathway`    | `literature`      | no      | no   |         - | not exported yet                                                          |
| `paper_produced_dataset`             | `paper`      | `dataset`    | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `paper_cites_paper`                  | `paper`      | `paper`      | `literature`      | yes     | no   |         - | not exported yet                                                          |
| `dataset_contains_gene`              | `dataset`    | `gene`       | `metadata`        | yes     | yes  |    17,844 | OpenTargets DepMap dataset coverage                                       |
| `dataset_contains_disease`           | `dataset`    | `disease`    | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `dataset_contains_molecule`          | `dataset`    | `molecule`   | `metadata`        | yes     | no   |         - | not exported yet                                                          |
| `dataset_contains_cell_type`         | `dataset`    | `cell_type`  | `metadata`        | yes     | no   |         - | no source-backed rows emitted; no placeholder file                         |
| `dataset_contains_cell_line`         | `dataset`    | `cell_line`  | `metadata`        | yes     | yes  |     1,183 | OpenTargets DepMap dataset coverage                                       |
| `dataset_contains_tissue`            | `dataset`    | `tissue`     | `metadata`        | yes     | yes  |        27 | OpenTargets DepMap dataset coverage                                       |

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
      Mutation, Protein (`lnschema_txgnn`; CellLine already covered by `bionty`)
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
- [ ] PARTIAL: `ingest_variants` used OpenTargets 26.03 `variant/` staging
      now archived at `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0940Z/txgnn-variants-scratch.tar.zst`
      (25 source files, 3.2G, 7,432,549 rows). Code now maps
      `mutation_causes_protein_change` to ENSP via unambiguous UniProt xrefs
      and respects the mutation node schema. One-file smoke passed but produced
      `311,562` mutation nodes, `11,652,040` `mutation_in_gene`,
      `11,652,040` `mutation_affects_transcript`, and `8,563`
      `mutation_causes_protein_change` edges with `6.5G` peak RSS. Do **not**
      blindly promote full gene/transcript variant relations; next bounded
      variant slice should promote protein-change edges first, then revisit
      stricter filters for gene/transcript.
- [x] `ingest_evidence_backed_variants` / dataset alias
      `known_variant` added a sparse, evidence-first variant path. It scans
      `evidence_*` directories for high-value genetics datatypes
      (`gwas_credible_sets`, `genetic_association`, `ot_genetics_portal`,
      `gene_burden`, `eva`, `clingen`, `uniprot_variants`,
      `somatic_mutation`, `intogen`) and emits only backed `mutation` stubs plus
      `mutation_associated_disease` edges. The direct path deliberately has no
      inverse disease→mutation edge. Keep this explicit, not part of
      `ALL_DATASETS`, until audited under systemd limits. The local scratch
      `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0907Z/txgnn-known-variants-scratch/kg` validated with
      `2,174,478` nodes, `3,807,475` edges, and zero dangling edges; its
      disease relation is now promoted into canonical GCS as part of the
      `4,656,171`-row `mutation_associated_disease` union.
- [x] Directionality rule for variants: do not materialize inverse 1:1 edges.
      Variant evidence should use the causality-oriented mutation→disease
      direction (`mutation_associated_disease`) unless a relation encodes a
      genuinely different biological statement.
- [x] Download/audit small OpenTargets genetics evidence datasets for the
      evidence-backed variant path. Caches include
      `evidence_gwas_credible_sets`, `evidence_eva`, `evidence_eva_somatic`,
      `evidence_gene_burden`, `evidence_clingen`,
      `evidence_uniprot_variants`, and `evidence_intogen` under
      `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0907Z/txgnn-known-variants-scratch/opentargets`.
- [x] Protein-change variant slice promoted and synced (2026-06-10):
      canonical GCS now has the unioned `nodes/mutation.parquet` plus
      `177,735` `mutation_causes_protein_change` edges. `lnschema_txgnn.Protein`
      has `233,995 / 233,995` ENSP protein IDs, and mutation IDs needed by
      the promoted safe variant slices are in `lnschema_txgnn.Mutation`.
- [x] Combined variant scratch disease edges promoted after the custom disease
      registry policy unblocked non-MONDO disease-like IDs.
      The retired combined variant scratch is archived at
      `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0940Z/txgnn-variant-combined-scratch.tar.zst` and had `2,419,072`
      nodes and `3,985,210` edges. Its `mutation_associated_disease` edges were merged with the GWAS disease
      slice and promoted on 2026-06-11. Canonical GCS now has `52,889` disease
      nodes and `4,656,171` `mutation_associated_disease` edges with targeted
      endpoint validation reporting zero dangling mutation and disease endpoints.
- [x] GWAS credible-set join. Datasets `credible_set`,
      `l2g_prediction`, and `study` are cached under
      `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0907Z/txgnn-gwas-join-scratch/opentargets`. Code now joins
      `evidence_gwas_credible_sets.studyLocusId → credible_set.studyLocusId →
      credible_set.variantId` and emits directed `mutation_associated_disease`
      edges. `l2g_prediction` with score ≥ `0.75` emits directed
      `mutation_associated_gene` edges. No inverse 1:1 edges are materialized.
      Bounded systemd run `txgnn-gwas-known-variant-ingest-r5` completed in
      `15min06s` with `1.2G` peak memory. Scratch
      `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0907Z/txgnn-gwas-join-scratch/kg` validates with `452,875`
      nodes, `1,383,789` edges, and zero dangling edges:
      `429,997` mutation nodes, `10,414` disease stubs, `12,464` gene stubs,
      `848,696` `mutation_associated_disease`, and `535,093`
      `mutation_associated_gene`. The `mutation_associated_gene` relation is
      now promoted to canonical GCS and its mutation/gene endpoints are
      represented in LaminDB/bionty. The GWAS disease relation is now included in the canonical
      `mutation_associated_disease` union; targeted endpoint validation reports
      zero dangling mutation and disease endpoints.
- [ ] Phase 4 audit datasets are archived under
      `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0940Z/txgnn-phase4-audit.tar.zst`:
      `interaction`, `interaction_evidence`, `clinical_indication`, and
      `drug_mechanism_of_action`.
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
  layout has 11 node files and 30 edge files. The 2026-06-10 full streaming
  validation was clean before disease-edge promotion, and the 2026-06-11
  `mutation_associated_disease` edge addition has targeted zero-dangling
  endpoint validation.

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
      GCS export: 11/15 node files, 30/77 edge files. See
      `docs/kg_coverage_audit.md`.
- [x] Remote GCS validation after paper, OpenTargets ID-space merge,
      biosample/expression, and disease-phenotype promotion:
      the 2026-06-10 full streaming run of `PYARROW_NUM_THREADS=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run python -m manage_db.validate_kg gs://jouvencekb/kg/v2 --batch-size 250000` reported
      `6,562,289` nodes, `27,014,101` edges, and `total_dangling_edges: 0`.
      The 2026-06-11 `mutation_associated_disease` promotion changed only
      `nodes/disease.parquet` and added `edges/mutation_associated_disease.parquet`;
      targeted validation of that new edge file reports zero dangling mutation
      or disease endpoints. A fresh full streaming validation attempt after the
      promotion timed out after 20 minutes with no output on GCS FUSE.
- [x] Node ontology coverage stats. 2026-06-11 report:
      `.omoc/reports/node-ontology-coverage-20260611T113441Z.json` over
      `/mnt/gcs/jouvencekb/kg/v2` counted `6,555,857` node rows across
      `12 / 15` node files and missing `cell_line`, `dataset`,
      and `enhancer`. The human organism slice added `NCBITaxon:9606` plus
      `109,325` `organism_has_gene` and `16,061` `organism_has_tissue` edges. The 2026-06-11 normalization pass rewrote disease and
      cell-type node IDs plus all selected endpoint columns from underscore
      ontology syntax to CURIE syntax (for example `EFO_...` -> `EFO:...`,
      `CL_...` -> `CL:...`) and collapsed `11,030` duplicate disease rows.
      Remaining non-primary namespaces include expected legacy DrugBank, CTD,
      NCBI, gnomAD-like, and `OTVAR` IDs; missing node files remain the next
      schema-completion work.
- [ ] LaminDB parity audit and sync. 2026-06-10 bounded sync created
      `233,995` custom ENSP protein records and `2,588,052` mutation records
      needed by the combined/GWAS safe variant slices (`2,165,367` from the
      combined scratch plus `422,685` additional GWAS mutations; `7,312` GWAS
      mutations already existed after the first sync). Current parity: combined
      scratch has `0 / 233,995` proteins missing and `0 / 2,165,367` mutations
      missing. GWAS scratch has `0 / 429,997`
      mutations missing and `0 / 12,464` genes missing. `EFO_...` disease IDs canonicalize to `EFO:...`,
      and bionty has no `EFO:` disease ontology IDs in this instance. The
      2026-06-11 policy is to represent TxGNN disease nodes in custom
      `lnschema_txgnn.Disease` keyed by normalized source ontology ID, avoiding
      direct non-MONDO inserts into `bionty.Disease`. A 2026-06-11 canonical
      parity pass against `/mnt/gcs/jouvencekb/kg/v2` created `30,851` missing
      canonical paper records, `1,456` remaining gnomAD-like mutation records,
      and `38,323` custom disease records, reconciled gnomAD-like IDs onto
      existing rsID mutation rows where needed, and then verified
      `missing_ids=0` for canonical `paper`, `mutation`, `protein`,
      `disease`, and `organism` nodes. The 2026-06-11 `mutation_associated_disease` promotion added
      `4,598` disease node rows and synced `3,536` additional custom disease
      records; parity still reports `missing_ids=0` for canonical disease and mutation nodes. The sync code now avoids refreshing stale LaminDB hub metadata when
      `jkobject/jouvencekb` is already connected, preventing the wrong
      `gs://jouvencekb/.lamindb/lamin.db` lookup; the actual storage root is
      `gs://jouvencekb/lamin/.lamindb/lamin.db` with a local SQLite cache under
      `/home/ubuntu/lamindb-cache`. The 2026-06-11 task 26 pass synced
      canonical transcripts into `lnschema_txgnn.Transcript`; targeted parity now
      reports `transcript missing_ids=0`. The remaining exact-ID parity gaps for
      public bionty/pertdb-backed spaces were resolved by custom TxGNN registries
      rather than unsafe public writes: `lnschema_txgnn.Gene`, `Molecule`,
      `Pathway`, `Tissue`, and `CellType` represent canonical KG primary IDs
      exactly. Hermes verified canonical parity on 2026-06-11 with
      `missing_ids=0` for `gene`, `molecule`, `pathway`, `tissue`, `cell_type`,
      `transcript`, `disease`, `protein`, `paper`, `mutation`, and `organism`;
      see `.omoc/reports/hermes-parity-custom-registries-*.json`. Use
      `uv run python -m manage_db.audit_lamindb_parity <kg_root>` before claiming
      any remaining KG slice is complete.
- [x] Final TxGNN model smoke test on the VPS. Hermes ran
      `scripts/final_txgnn_tiny_smoke.py` under explicit systemd limits
      (`CPUQuota=200%`, `MemoryMax=4G`) on 2026-06-12. The smoke uses only
      temporary local scratch data, validates a mini Parquet KG through
      `KGLoader`, initializes a tiny CPU `TxGNN`/`HeteroRGCN` model with
      `proto=False`, and performs a forward pass over the six hard-coded
      drug-disease etypes. Result: systemd `success`, runtime `7.235s`, peak
      memory `449.1M`, `kgloader_ok=true`, `pred_pos_relations=6`,
      `pred_neg_relations=6`. Evidence:
      `.omoc/reports/hermes-final-txgnn-tiny-smoke-20260612T182202Z.txt`.
      Runtime note: DGL 2.1.0 requires the legacy-compatible stack used for the
      smoke (`torch==2.2.1`, `torchdata==0.7.1`, `numpy==1.26.4`) and was run
      with `uv run --no-sync` to avoid the KG tooling lock re-syncing NumPy 2.x.
      Reproducible wrapper: `scripts/run_final_txgnn_tiny_smoke_systemd.sh`,
      verified on 2026-06-14 with systemd `success`, runtime `7.290s`, peak
      memory `389.6M`; evidence
      `.omoc/reports/hermes-final-txgnn-tiny-smoke-wrapper-*.txt`.
