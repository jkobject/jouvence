# Canonical KG to PyG / HeteroData mapping design

Date: 2026-06-23

Task: `t_dc23f241`

## Executive recommendation

Keep `gs://jouvencekb/kg/v2` as the canonical KG source of truth and add a
versioned, reproducible PyG materialization layer under
`gs://jouvencekb/kg/v2/ml/pyg/`. The PyG layer should contain deterministic node
index maps, edge-index shards, feature manifests, split masks, evidence sidecars,
and validation reports. It must not replace `nodes/`, `edges/`, `evidence/`, or
`features/`.

The existing `txgnn/KGLoader.py` already shows the right core convention:
`HeteroData` node stores are keyed by canonical node type strings, and edge stores
are keyed by `(x_type, relation, y_type)`. This design keeps that convention and
makes it scale-safe, feature-aware, evidence-aware, and compatible with both PyG
and the legacy DGL-oriented TxGNN training API.

## Observed current state

Relevant local code/docs inspected for this design:

- `txgnn/TxData.py`: historical TxGNN loads `kg.csv`, builds train/valid/test
  CSVs, then constructs a DGL graph from `df_train` while retaining the full KG
  and split data frames.
- `txgnn/data_splits/datasplit.py`: disease-area split utilities use a homogeneous
  `edge_index` over historical integer node indices, including PyG
  `k_hop_subgraph` for disease-neighborhood masking.
- `txgnn/KGLoader.py`: current Parquet KG loader reads canonical `nodes/` and
  `edges/`, builds `node_id_maps`, exports `edge_index_frames()` keyed by
  `(source_type, relation, target_type)`, and can construct a basic
  `torch_geometric.data.HeteroData` with `num_nodes`, `node_id`, and
  `edge_index`.
- `manage_db/kg_schema.py`: canonical node types and 67 active relations are the
  source of truth for allowed endpoint types.
- `manage_db/kg_storage.py`: canonical node/edge readers use Parquet files under
  `nodes/{node_type}.parquet` and `edges/{relation}.parquet`.
- `manage_db/kg_evidence.py`: evidence rows live under
  `evidence/{relation}.parquet`, keyed by `edge_key = relation|x_id|y_id`, with
  source, predicate, score, study, paper, dataset, and statistical fields.
- `docs/kg_schema_overview.md` and `docs/source_measure_edge_matrix.md`: relation
  names preserve source-native endpoint semantics. Gene-level rows must not be
  projected into protein relations, and evidence nuance stays in evidence rows.
- `docs/node_feature_tables_canonical_promotion_report.md`: current approved
  feature layer contains sequence/textual node feature tables staged with paths
  like `features/gene_textual_summary.parquet`,
  `features/protein_sequence.parquet`, and `features/molecule_textual_summary.parquet`.

## Design principles

1. Canonical Parquet remains authoritative.
   - PyG artifacts are derived products with manifest lineage back to exact
     canonical file hashes and row counts.
   - Do not mutate canonical `nodes/`, `edges/`, `evidence/`, or `features/` when
     building PyG tensors.

2. Node and relation names stay canonical.
   - PyG node store names are exactly the canonical `NodeType.value` strings:
     `gene`, `disease`, `molecule`, `protein`, etc.
   - PyG edge store names are exactly `(x_type, relation, y_type)` triples, e.g.
     `('molecule', 'molecule_targets_gene', 'gene')`.
   - Do not collapse relations into generic `interacts`, `targets`, or historical
     TxGNN labels when doing so loses endpoint/source-native meaning.

3. Index maps are first-class artifacts.
   - Every node type gets a deterministic `id -> int64 index` map and its inverse.
   - Edge-index builders must depend on these maps, never on incidental Parquet row
     order discovered during a later run.

4. Graph tensors are separated from metadata.
   - Hot-path training tensors are compact: `edge_index`, optional numeric
     `edge_attr`, feature matrices, masks/splits.
   - Rich evidence, raw source payloads, text, sequence strings, and xrefs remain
     sidecars keyed by node/edge IDs and row indices.

5. Scale determines layout.
   - The current KG baseline is tens of millions of nodes and nearly 100M graph
     edges, with large enhancer and cell-line expression relations.
   - Build in chunks, write shards, and expose an optional assembly step for
     in-memory `HeteroData` only when the selected subgraph or machine can fit it.

6. Future embeddings are an extension point, not a schema rewrite.
   - Foundation embeddings for nodes and one-embedding-per-edge evidence features
     should be referenced by manifest entries and loaded lazily.

## Canonical inputs

The mapper reads the canonical KG release root:

```text
kg/v2/
  nodes/{node_type}.parquet
  edges/{relation}.parquet
  evidence/{relation}.parquet
  features/{feature_table}.parquet
  metadata/provenance.json
  metadata/SUMMARY.md
```

Required edge columns from `manage_db/kg_schema.py`:

```text
x_id, x_type, y_id, y_type, relation, display_relation, source, credibility
```

Evidence sidecar columns from `manage_db/kg_evidence.py` include:

```text
edge_key, relation, x_id, x_type, y_id, y_type,
evidence_type, source, source_dataset, source_record_id,
paper_id, dataset_id, study_id, evidence_score, effect_size, p_value,
predicate, text_span, source_payload
```

Feature tables are expected under `features/*.parquet`. Current approved examples
include `gene_textual_summary`, `molecule_textual_summary`, `protein_sequence`,
`transcript_sequence`, `disease_textual_summary`, `pathway_textual_summary`,
`tissue_textual_summary`, `cell_type_textual_summary`, `cell_line_textual_summary`,
and `phenotype_textual_summary`.

## Proposed PyG artifact layout

All files below are derived artifacts under the canonical release:

```text
kg/v2/ml/pyg/
  README.md
  manifest.json
  build_config.yaml
  validation_report.json
  validation_report.md

  schema/
    node_types.json
    edge_types.json
    feature_tables.json
    relation_to_edge_type.parquet
    txgnn_compat_relations.yaml

  node_maps/
    {node_type}.id_to_index.parquet
    {node_type}.index_to_id.parquet
    {node_type}.stats.json

  edges/
    {x_type}__{relation}__{y_type}/
      edge_index.pt
      edge_index.parquet
      edge_attr.parquet
      edge_row_map.parquet
      edge_stats.json
      reverse_edge_type.json
      shards/
        part-00000.edge_index.pt
        part-00000.edge_row_map.parquet
        part-00001.edge_index.pt
        part-00001.edge_row_map.parquet

  reverse_edges/
    {y_type}__rev_{relation}__{x_type}/
      edge_index.pt
      edge_row_map.parquet
      reverse_of.json
      shards/
        part-00000.edge_index.pt

  node_features/
    {node_type}/
      feature_manifest.json
      {feature_name}.parquet
      {feature_name}.pt
      {feature_name}.mask.pt
      {feature_name}.row_map.parquet
      embeddings/
        {embedding_model}/
          embedding.pt
          embedding.mask.pt
          embedding_manifest.json

  edge_features/
    {x_type}__{relation}__{y_type}/
      evidence_summary.parquet
      evidence_numeric_attr.pt
      evidence_numeric_attr.mask.pt
      evidence_embedding/
        {embedding_model}/
          edge_embedding.pt
          edge_embedding.mask.pt
          embedding_manifest.json

  splits/
    {split_name}/
      split_config.yaml
      train_edges.parquet
      valid_edges.parquet
      test_edges.parquet
      train_mask_by_edge_type.pt
      valid_mask_by_edge_type.pt
      test_mask_by_edge_type.pt
      disease_holdout_nodes.parquet
      negative_sampling_config.yaml
      leakage_report.json

  heterodata/
    full_graph.metadata.json
    full_graph.pt              # optional only for small/full-fit builds
    subgraphs/
      {subgraph_name}.pt
      {subgraph_name}.metadata.json

  txgnn_legacy/
    kg_directed.csv            # optional compatibility projection
    node.csv                   # optional compatibility projection
    edges.csv                  # optional compatibility projection
    relation_mapping.csv
```

Notes:

- `edge_index.pt` stores a 2 x E `torch.long` tensor.
- `edge_index.parquet` stores the same data as columns `src_index`, `dst_index`
  for DuckDB/Polars inspection and chunked validation.
- `edge_row_map.parquet` maps each edge-index column to canonical identity:
  `edge_pos`, `relation`, `x_id`, `y_id`, `edge_key`, `canonical_row_group`,
  `canonical_row_number` when available.
- `edge_attr.parquet` should start with compact numeric/categorical edge-level
  fields copied from canonical edge rows: `credibility`, encoded source ID, and
  optional relation-specific numeric columns if they already exist on edges.
- `evidence_summary.parquet` is one row per graph edge, derived from
  `evidence/{relation}.parquet`, and should contain aggregated fields such as
  `evidence_count`, `max_evidence_score`, `mean_evidence_score`, `min_p_value`,
  `has_paper`, `has_dataset`, and encoded dominant evidence/source types.
- Raw evidence rows are not duplicated into PyG. Store pointers and row maps.

## Node type mapping

Use all canonical node types as PyG node stores unless a build config explicitly
selects a subset:

| Canonical node type | PyG node store | ID source | Index map files |
| --- | --- | --- | --- |
| `gene` | `data['gene']` | `nodes/gene.parquet:id` | `node_maps/gene.*.parquet` |
| `transcript` | `data['transcript']` | `nodes/transcript.parquet:id` | `node_maps/transcript.*.parquet` |
| `protein` | `data['protein']` | `nodes/protein.parquet:id` | `node_maps/protein.*.parquet` |
| `disease` | `data['disease']` | `nodes/disease.parquet:id` | `node_maps/disease.*.parquet` |
| `molecule` | `data['molecule']` | `nodes/molecule.parquet:id` | `node_maps/molecule.*.parquet` |
| `pathway` | `data['pathway']` | `nodes/pathway.parquet:id` | `node_maps/pathway.*.parquet` |
| `mutation` | `data['mutation']` | `nodes/mutation.parquet:id` | `node_maps/mutation.*.parquet` |
| `enhancer` | `data['enhancer']` | `nodes/enhancer.parquet:id` | `node_maps/enhancer.*.parquet` |
| `tissue` | `data['tissue']` | `nodes/tissue.parquet:id` | `node_maps/tissue.*.parquet` |
| `cell_type` | `data['cell_type']` | `nodes/cell_type.parquet:id` | `node_maps/cell_type.*.parquet` |
| `cell_line` | `data['cell_line']` | `nodes/cell_line.parquet:id` | `node_maps/cell_line.*.parquet` |
| `phenotype` | `data['phenotype']` | `nodes/phenotype.parquet:id` | `node_maps/phenotype.*.parquet` |
| `organism` | `data['organism']` | `nodes/organism.parquet:id` | `node_maps/organism.*.parquet` |
| `paper` | `data['paper']` | `nodes/paper.parquet:id` | `node_maps/paper.*.parquet` |
| `dataset` | `data['dataset']` | `nodes/dataset.parquet:id` | `node_maps/dataset.*.parquet` |

Deterministic indexing rule:

1. Read `nodes/{node_type}.parquet` with at least `id`.
2. Normalize IDs as strings without changing canonical content.
3. Validate uniqueness and non-null IDs.
4. Preserve canonical file row order by default for reproducibility with existing
   artifacts; optionally allow `sort_by_id: true` only in a new major PyG build
   version.
5. Emit:
   - `{node_type}.id_to_index.parquet`: `id`, `node_type`, `node_index`.
   - `{node_type}.index_to_id.parquet`: `node_index`, `node_type`, `id`.
   - `{node_type}.stats.json`: row count, unique ID count, null count, hash of ID
     sequence, source node file path/hash.

`HeteroData` construction:

```python
data[node_type].num_nodes = node_count
data[node_type].node_id = index_to_id_list  # optional debug/list export for small graphs
```

For large builds, keep `node_id` as an on-disk sidecar and avoid attaching Python
lists of tens of millions of IDs to in-memory `HeteroData` unless explicitly
requested.

## Relation and edge type mapping

For every active canonical edge file `edges/{relation}.parquet`, derive the PyG
edge type from the relation schema and observed endpoint columns:

```python
edge_type = (x_type, relation, y_type)
data[edge_type].edge_index = torch.LongTensor([[src...], [dst...]])
```

The edge type must match `manage_db.kg_schema.RELATION_BY_NAME[relation]` unless a
known documented exception exists. If the file is empty but the relation exists,
emit an empty edge-index artifact with the schema endpoint types.

### Example heterogeneous edge mappings

| Canonical edge file | Source columns | PyG edge type | Semantics preserved |
| --- | --- | --- | --- |
| `edges/molecule_targets_gene.parquet` | `x_type=molecule`, `y_type=gene` | `('molecule', 'molecule_targets_gene', 'gene')` | Gene-endpoint drug target relation; do not project to protein unless source is protein-native. |
| `edges/disease_associated_gene.parquet` | `x_type=gene`, `y_type=disease` | `('gene', 'disease_associated_gene', 'disease')` | Directed gene→disease association despite relation name containing disease first. |
| `edges/gene_interacts_gene.parquet` | `x_type=gene`, `y_type=gene` | `('gene', 'gene_interacts_gene', 'gene')` | Broad gene/gene-product interaction; product-specific nuance remains evidence metadata. |
| `edges/enhancer_regulates_gene.parquet` | `x_type=enhancer`, `y_type=gene` | `('enhancer', 'enhancer_regulates_gene', 'gene')` | rE2G/ABC-like predictive enhancer→gene context; no causality inflation. |
| `edges/tissue_expresses_protein.parquet` | `x_type=tissue`, `y_type=protein` | `('tissue', 'tissue_expresses_protein', 'protein')` | Direct HPA protein evidence only; never RNA→protein projection. |
| `edges/molecule_treats_disease.parquet` | `x_type=molecule`, `y_type=disease` | `('molecule', 'molecule_treats_disease', 'disease')` | Clinical indication relation for therapeutic link prediction. |
| `edges/pathway_contains_gene.parquet` | `x_type=pathway`, `y_type=gene` | `('pathway', 'pathway_contains_gene', 'gene')` | Gene-level Reactome/GO membership. |
| `edges/mutation_associated_disease.parquet` | `x_type=mutation`, `y_type=disease` | `('mutation', 'mutation_associated_disease', 'disease')` | Variant-disease association with GWAS/ClinVar evidence detail in sidecar. |

Relation mapping artifact:

`schema/relation_to_edge_type.parquet`

```text
relation, x_type, y_type, pyg_src_type, pyg_relation, pyg_dst_type,
kind, direct, canonical_edge_path, canonical_evidence_path,
edge_count, has_reverse, reverse_relation_name, include_in_txgnn_legacy
```

## Reverse edges

PyG message passing often needs reverse edges for directed heterogeneous graphs.
Canonical KG direction should remain untouched, so reverse edges are derived-only:

- Forward edge type: `(x_type, relation, y_type)`.
- Reverse edge type: `(y_type, 'rev_' + relation, x_type)`.
- Reverse edge index: source/destination rows swapped from the forward edge.
- Reverse row map: preserve `edge_key` and `forward_edge_pos`; do not mint new
  canonical edge keys.

Default policy:

```yaml
reverse_edges:
  enabled: true
  materialize_for_message_passing: true
  include_self_reverses: false  # self-type relations can use either same store or explicit reverse by model config
  relation_name_prefix: rev_
  excluded_relations: []
```

Self-type relations (`gene_interacts_gene`, `disease_subtype_of_disease`,
`molecule_synergizes_molecule`) need per-relation treatment:

- If a relation is semantically symmetric and canonical edges are stored in a
  canonical pair order, either duplicate reverse columns for message passing or
  configure the model as undirected for that edge type.
- If a self-type relation is directed (`molecule_parent_of_molecule`, hierarchy
  relations), keep explicit reverse edge types for message passing but do not
  reinterpret reverse semantics as canonical biology.

## Edge index construction

For each relation:

1. Load `edges/{relation}.parquet` in row groups or bounded batches with columns
   `x_id`, `x_type`, `y_id`, `y_type`, `relation`, plus selected edge attributes.
2. Validate every row has `relation == {relation}`.
3. Validate endpoint types match the relation schema.
4. Map `x_id` through `node_maps/{x_type}.id_to_index.parquet`.
5. Map `y_id` through `node_maps/{y_type}.id_to_index.parquet`.
6. Record anti-join failures in `validation_report.json`; fail strict builds when
   any dangling endpoint exists.
7. Write shard-level `part-*.edge_index.pt` and `part-*.edge_row_map.parquet`.
8. Optionally concatenate shards to `edge_index.pt` if memory budget allows.
9. Emit `edge_stats.json` with row counts, missing endpoint counts, dtype, min/max
   indices, duplicate canonical edge checks, source file hashes, and shard sizes.

Implementation should prefer DuckDB/Polars/PyArrow joins for large relations:

- Small/medium relation: load ID maps in memory and stream edge row groups.
- Large relation (`enhancer_regulates_gene`, `cell_line_expresses_gene`, other
  multi-million-row files): use DuckDB joins against Parquet maps and write shards
  without materializing all rows in pandas.
- Extremely large node types (`enhancer`, `paper`) must not become Python dicts in
  full builds unless the build config explicitly permits it.

## Node feature mapping

Feature tables should be represented in three layers:

1. Raw feature sidecar in Parquet, index-aligned through `row_map.parquet`.
2. Optional tensorized representation in `.pt` for numeric arrays/embeddings.
3. Mask tensor indicating which nodes have the feature.

General feature contract:

```text
features/{feature_table}.parquet
  node_id: canonical node ID
  node_type: canonical node type
  feature_key: stable feature table/key
  value columns: text, sequence, vector path, numeric values, checksum, metadata
```

If current table columns differ, the PyG builder should normalize through a
feature adapter and record the original schema in `feature_manifest.json`.

### Example node feature tables

| Feature table | Node store | PyG artifact | Initial tensor handling | Future embedding handling |
| --- | --- | --- | --- | --- |
| `features/gene_textual_summary.parquet` | `data['gene']` | `node_features/gene/gene_textual_summary.parquet` plus mask | Keep text off-tensor; attach optional encoded categorical/source fields only. | `node_features/gene/embeddings/{model}/embedding.pt` from text foundation model. |
| `features/molecule_textual_summary.parquet` | `data['molecule']` | `node_features/molecule/molecule_textual_summary.parquet` plus mask | Keep text/offline metadata sidecar; optionally combine with fingerprints. | Molecule text or multimodal compound embedding. |
| `features/molecule_fingerprint.parquet` | `data['molecule']` | `node_features/molecule/molecule_fingerprint.pt` plus mask | Tensorize bit vectors as `torch.float32` or packed bool depending model config. | Can be concatenated with chemical foundation embeddings. |
| `features/protein_sequence.parquet` | `data['protein']` | `node_features/protein/protein_sequence.parquet` plus mask | Keep raw sequence off-tensor; expose length/checksum numeric features if desired. | Protein language model embedding under `embeddings/{model}/embedding.pt`. |
| `features/transcript_sequence.parquet` | `data['transcript']` | `node_features/transcript/transcript_sequence.parquet` plus mask | Keep raw sequence off-tensor; optional length/GC features. | Transcript/nucleotide foundation embedding. |
| `features/disease_textual_summary.parquet` | `data['disease']` | `node_features/disease/disease_textual_summary.parquet` plus mask | Keep disease text sidecar. | Clinical/biomedical text embedding. |

Minimum `HeteroData` attachment policy:

```python
# Numeric/vector features only, if configured and all dimensions are valid.
data[node_type].x = feature_tensor
# Missing rows are represented by mask and configured imputation.
data[node_type].x_mask = feature_mask
```

Do not attach raw strings (`summary`, `sequence`, source payload JSON) directly to
full-scale `HeteroData` objects. Keep those in sidecars and use embeddings or
small numeric summaries in tensors.

## Evidence and edge attributes

Canonical evidence rows preserve source-native semantics. PyG should use them in
three optional ways:

1. Edge-level numeric summary attributes.
   - One row per canonical graph edge.
   - Recommended columns: `evidence_count`, `max_evidence_score`,
     `mean_evidence_score`, `min_p_value`, `max_abs_effect_size`, `has_paper`,
     `has_dataset`, encoded `dominant_evidence_type`, encoded `dominant_source`.
   - Tensor artifact: `edge_features/{edge_type}/evidence_numeric_attr.pt`.

2. Evidence row retrieval sidecar.
   - Keep raw evidence in canonical `evidence/{relation}.parquet`.
   - Use `edge_row_map.parquet` and `edge_key` to retrieve all supporting evidence
     rows for explanations/audits.

3. One-embedding-per-edge evidence features.
   - Future relation-specific evidence encoders can produce exactly one vector per
     graph edge by pooling all evidence rows for that edge.
   - Store under
     `edge_features/{edge_type}/evidence_embedding/{embedding_model}/edge_embedding.pt`.
   - Record pooling method in `embedding_manifest.json`: `mean`, `attention`,
     `best_score`, `source_weighted`, etc.

Do not split relation names by evidence predicate. For example,
`molecule_targets_gene` remains one PyG edge type even if evidence predicates vary
by mechanism/action type; predicate-specific detail belongs in edge attributes or
sidecars.

## Split hooks

The PyG layer should support both historical TxGNN split modes and new relation-
aware heterogeneous splits.

Recommended split artifact root:

```text
kg/v2/ml/pyg/splits/{split_name}/
```

Split records should identify edges by canonical keys, not just integer positions:

```text
relation, x_type, y_type, x_id, y_id, edge_key, split, reason, seed
```

Supported split families:

1. `random_link_prediction`
   - Random train/valid/test over selected positive edge types.
   - Use only configured target relations for evaluation if desired.

2. `txgnn_complex_disease`
   - Preserve historical TxGNN behavior: hold out treatments for selected diseases
     so test diseases have no treatment edges in train.
   - Target relations should include `molecule_treats_disease`, optionally
     historical equivalents if compatibility projections are built.

3. `disease_eval_{disease_id}`
   - Mask treatment/contraindication edges for a single disease while retaining
     non-leaking context edges according to config.

4. `disease_area_{area}`
   - Use disease ontology area membership and optional k-hop neighborhood masking,
     replacing the old homogeneous `edge_index` with typed edge masks.

5. `full_graph`
   - No test set. Reserve validation fraction on selected target relations for
     early stopping, matching historical TxGNN full-graph mode.

For PyG `HeteroData`, split masks can be stored in two equivalent forms:

```python
data[edge_type].train_mask
data[edge_type].val_mask
data[edge_type].test_mask
```

or externally as dictionaries in `train_mask_by_edge_type.pt`, etc. For full-scale
builds, prefer external masks and attach only for selected subgraphs.

Leakage checks:

- No held-out disease treatment edge in train for disease holdout splits.
- Reverse edges inherit the same split as their forward edge.
- Evidence-derived features for a held-out edge must not include labels from test
  evidence if the task treats that edge as unknown.
- Negative samples must be generated after positive split assignment and must not
  collide with positives in any split.

## TxGNN compatibility layer

The canonical PyG representation should be the primary target, but the build can
also emit optional legacy projections for existing TxGNN code paths:

```text
kg/v2/ml/pyg/txgnn_legacy/
  kg_directed.csv
  node.csv
  edges.csv
  relation_mapping.csv
```

Compatibility projection rules:

- `kg_directed.csv` columns should preserve historical expectations:
  `x_idx`, `x_id`, `x_type`, `y_idx`, `y_id`, `y_type`, `relation`, plus names
  where available.
- `x_idx`/`y_idx` must come from the deterministic PyG node maps, either as
  global legacy indices or typed indices with an explicit `node_type` namespace.
- `relation_mapping.csv` must document any mapping from canonical relation names
  to historical TxGNN labels. Prefer no remapping unless the legacy trainer
  requires it.
- Keep canonical relation names in all new PyG artifacts.

## Build configuration

`build_config.yaml` should make all non-obvious choices explicit:

```yaml
kg_root: gs://jouvencekb/kg/v2
pyg_root: gs://jouvencekb/kg/v2/ml/pyg
build_id: pyg-v1-YYYYMMDD-<short_sha>
index_order: canonical_row_order
strict_endpoint_validation: true
node_types: all
relations: active_existing_files
reverse_edges:
  enabled: true
  relation_name_prefix: rev_
features:
  attach_raw_text_to_heterodata: false
  tensorize:
    molecule_fingerprint: true
  embeddings:
    enabled: false
splits:
  - name: full_graph
    target_relations: [molecule_treats_disease]
    valid_fraction: 0.05
    seed: 42
scale:
  edge_shard_rows: 5000000
  max_in_memory_nodes_for_dict_map: 5000000
  write_parquet_edge_index: true
  write_torch_edge_index: true
```

## Manifest

`manifest.json` should be the idempotency and reproducibility driver:

```json
{
  "kg_version": "v2",
  "pyg_schema_version": "1.0.0",
  "canonical_root": "gs://jouvencekb/kg/v2",
  "pyg_root": "gs://jouvencekb/kg/v2/ml/pyg",
  "build_id": "pyg-v1-YYYYMMDD-<short_sha>",
  "generated_at": "...",
  "code_sha": "...",
  "inputs": {
    "nodes/gene.parquet": {"rows": 267830, "content_hash": "..."},
    "edges/molecule_targets_gene.parquet": {"rows": 41239, "content_hash": "..."},
    "evidence/molecule_targets_gene.parquet": {"rows": 41239, "content_hash": "..."}
  },
  "node_types": {
    "gene": {
      "num_nodes": 267830,
      "id_to_index": "node_maps/gene.id_to_index.parquet",
      "index_to_id": "node_maps/gene.index_to_id.parquet"
    }
  },
  "edge_types": {
    "molecule__molecule_targets_gene__gene": {
      "pyg_edge_type": ["molecule", "molecule_targets_gene", "gene"],
      "num_edges": 41239,
      "edge_index": "edges/molecule__molecule_targets_gene__gene/edge_index.pt",
      "edge_row_map": "edges/molecule__molecule_targets_gene__gene/edge_row_map.parquet",
      "reverse_edge_type": ["gene", "rev_molecule_targets_gene", "molecule"]
    }
  },
  "features": {},
  "splits": {},
  "validation": "validation_report.json"
}
```

## Implementation plan

1. Formalize schemas and config.
   - Add a builder module, e.g. `txgnn/pyg_export.py` or
     `manage_db/export_pyg.py`.
   - Define dataclasses for node maps, edge type specs, feature specs, and split
     specs.
   - Read relation metadata from `manage_db.kg_schema.RELATION_BY_NAME`.

2. Build node maps.
   - Stream every selected `nodes/{node_type}.parquet`.
   - Validate ID uniqueness/non-nullness.
   - Write `id_to_index`, `index_to_id`, and stats.

3. Build edge-index shards.
   - For each selected relation, join `x_id`/`y_id` to node maps.
   - Emit forward `edge_index` shards, row maps, and edge stats.
   - Emit derived reverse edges if configured.

4. Add feature adapters.
   - Start with approved node feature tables: textual summary, sequence,
     molecule fingerprint when available.
   - Produce masks and row maps.
   - Tensorize only vector/numeric tables; keep text/sequence as sidecars until
     embeddings are generated.

5. Add evidence summaries.
   - Aggregate `evidence/{relation}.parquet` by `edge_key`.
   - Join one row per graph edge through `edge_row_map.parquet`.
   - Write numeric attribute tensors only for configured relations.

6. Add split builders.
   - Implement `full_graph` and random link-prediction first.
   - Port historical `complex_disease`, `disease_eval`, and disease-area logic to
     typed edge masks after the basic PyG export is validated.

7. Add assembly APIs.
   - Extend `KGLoader` or add `PyGKGLoader` to load from `ml/pyg/manifest.json`.
   - Support full in-memory `HeteroData` only when configured.
   - Support selected relation/node-type subgraph loading for development.

8. Add optional TxGNN legacy projection.
   - Generate CSVs only for compatibility and keep mapping documentation explicit.

## Validation checks

Required build-time checks:

- Node checks:
  - every selected node table exists;
  - `id` is non-null and unique per node type;
  - `node_index` is contiguous from `0` to `num_nodes - 1`;
  - `index_to_id` is exact inverse of `id_to_index`;
  - ID sequence hash is recorded.

- Edge checks:
  - every selected edge file has required columns;
  - `relation` column contains exactly the expected relation name;
  - observed `x_type`/`y_type` match `kg_schema.py` relation endpoints;
  - zero dangling endpoints in strict mode;
  - `edge_index` max/min values are within node counts;
  - `edge_index` column count equals canonical edge row count after any documented
    filtering;
  - duplicate `(relation, x_id, y_id)` counts are reported;
  - reverse edge count equals forward edge count and row maps point back to forward
    edge positions.

- Feature checks:
  - feature node IDs anti-join cleanly against the target node map, or missing
    coverage is reported as expected;
  - tensor row count equals node count when aligned tensors are emitted;
  - mask length equals node count;
  - vector dimensions are constant within each tensorized feature;
  - text/sequence payloads are not accidentally embedded into full-scale
    `HeteroData` objects.

- Evidence checks:
  - evidence `edge_key` values join to canonical edge row maps;
  - evidence aggregation row count is <= graph edge count;
  - numeric attributes have masks for missing values;
  - held-out split labels are not leaked through evidence-derived attributes when
    the edge is a prediction target.

- Split checks:
  - train/valid/test edge sets are disjoint by `edge_key`;
  - reverse edges inherit forward split assignment;
  - disease holdout splits contain no held-out disease treatment positives in
    train;
  - negative samples do not collide with positives in any split;
  - split configs include seed, target relations, and filtering rules.

- Reproducibility checks:
  - repeated build with same canonical hashes and config produces identical node
    ID sequence hashes and edge row-map hashes;
  - manifest lists every input path/hash and output path/hash;
  - validation report is written even on failure, with partial stats.

## Minimal API sketch

```python
from txgnn.pyg_export import export_pyg, PyGKGLoader

export_pyg(
    kg_root="gs://jouvencekb/kg/v2",
    pyg_root="gs://jouvencekb/kg/v2/ml/pyg",
    config="build_config.yaml",
)

loader = PyGKGLoader("gs://jouvencekb/kg/v2/ml/pyg/manifest.json")
data = loader.load_heterodata(
    node_types=["molecule", "gene", "disease"],
    edge_types=[
        ("molecule", "molecule_targets_gene", "gene"),
        ("gene", "disease_associated_gene", "disease"),
        ("molecule", "molecule_treats_disease", "disease"),
    ],
    attach_features=["molecule_fingerprint"],
    attach_splits="full_graph",
)
```

## Non-goals for this design card

- Do not build the full tensors here.
- Do not decide final model architecture or loss function.
- Do not collapse canonical source-native relations into historical TxGNN labels.
- Do not promote staged feature tables or change the official `features/` pointer.
- Do not create protein relations from gene/RNA endpoint rows.

## Open decisions for implementation cards

1. Whether the first production PyG build should store a full `full_graph.pt` or
   only per-type shards plus subgraph assembly.
2. Which embedding model names and vector dimensions to standardize for first
   text, sequence, compound, and evidence embeddings.
3. Whether large self-type relations should materialize explicit reverse edge
   stores or rely on model-level undirected handling.
4. Whether TxGNN legacy compatibility should use typed node indices or a single
   global homogeneous index in generated CSVs.
5. Which split should be the first acceptance target: `full_graph`,
   `random_link_prediction`, or `txgnn_complex_disease`.
