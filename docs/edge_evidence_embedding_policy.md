# Edge/evidence embedding policy: one vector per canonical edge

Task: `t_1dc65ac1`  
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`  
Scope: policy/design only. Do not run large embedding jobs from this card.

## Executive decision

Embedding work is not complete until actual vectors are created with an approved encoder and validated. The previous HashingVectorizer pilot was schema/artifact-layout validation only, not a production embedding model.

The KG should expose **one embedding vector per canonical graph edge or graph-edge group required by the PyG/GNN export**. The vector is a derived feature of the deduplicated edge assertion plus all approved source evidence/value rows that support that same endpoint pair. It is not a new biological relation, and it must not change `nodes/`, `edges/`, or `evidence/`.

Default rule:

1. Build a deterministic structured payload for each canonical edge from:
   - canonical edge identity and endpoint types: `relation|x_id|y_id`, `x_type`, `y_type`;
   - relation semantics from `manage_db/kg_schema.py`: relation name, display label, endpoint types, direct/non-direct kind when available;
   - selected edge metadata columns: `source`, `credibility`, and relation-specific edge columns such as `action_type`, `score`, `datatype`, `e2g_score`;
   - all evidence rows in `evidence/{relation}.parquet` for the same `edge_key`, after canonical ordering and leakage filtering;
   - optional textual node context only from reviewed canonical feature tables, for example `features/gene_textual_summary.parquet`, `features/disease_textual_summary.parquet`, or `features/molecule_textual_summary.parquet`.
2. Encode relation, edge metadata, numeric values, and evidence fields with a relation/value/evidence encoder: categorical/text fields may use embeddings/text encoders, numeric/scalar values are normalized and passed through an MLP, and the combined encoder outputs a fixed-width edge/evidence embedding.
3. For each `(relation, x_id, y_id)` pair, collect all canonical edge rows and all approved evidence/value rows that refer to the same node pair where the graph export groups them. Concatenate, attention-pool, DeepSets-pool, or otherwise aggregate those per-row encodings into exactly one vector per PyG/GNN graph edge or edge group.
4. For edges with no usable evidence/value payload, use a learned fallback edge embedding keyed by relation and endpoint types in the downstream model; do not emit zero/random/source-fabricated placeholders as canonical feature artifacts.
5. Store the resulting vector in a versioned derived-feature artifact under `kg/v2/features/edge_embeddings/` with hashes and manifests sufficient for exact recomputation.

This policy intentionally differs from node embeddings: node embeddings represent entity-intrinsic modalities such as text, ontology definitions, molecule structure, protein sequence, or transcript cDNA. Edge embeddings represent an **assertion with provenance**: relation semantics, endpoint pair, source predicates, confidence/statistical fields, papers/studies/datasets, and optional endpoint context.

## Canonical inputs inspected

The active schema separates deduplicated graph assertions from row-level support:

- `manage_db/kg_schema.py` defines canonical node types, relations, and edge columns.
- `manage_db/kg_evidence.py` defines evidence/support columns and keys.
- `docs/kg_schema_overview.md` states that edges are deduplicated graph assertions and evidence rows carry source predicates, scores, assays, papers, studies, context, and provenance.
- `docs/source_measure_edge_matrix.md` defines source-native relation policy: broad graph relation names stay stable, while evidence preserves predicate/source-specific nuance.
- `docs/foundation_embedding_policy.md` defines node embedding conventions, model/version metadata, immutable versioned artifacts, and validation gates that this edge policy reuses.

Canonical edge Parquets use at least:

```text
x_id, x_type, y_id, y_type, relation, display_relation, source, credibility
```

Evidence Parquets use:

```text
edge_key, relation, x_id, x_type, y_id, y_type,
evidence_type, source, source_dataset, source_record_id,
paper_id, dataset_id, study_id, evidence_score, effect_size, p_value,
direction, confidence_interval, predicate, text_span, section,
extraction_method, license, release, created_at
```

`edge_key` is `relation|x_id|y_id` and is the join key between edge and evidence rows.

## Payload construction

### Edge-level header

Every edge embedding payload starts with a structured header. Use key-value serialization, not free prose only, so recomputation is deterministic.

Recommended header fields:

```text
edge_key: <relation>|<x_id>|<y_id>
relation: <relation>
display_relation: <display_relation>
x: <x_type> <x_id> [optional preferred label]
y: <y_type> <y_id> [optional preferred label]
edge_source: <source>
edge_credibility: <1|2|3>
relation_semantics: <short relation policy text from schema/docs, version-pinned>
edge_metadata: <relation-specific allowed metadata JSON>
```

The relation semantics text should be generated from a pinned local mapping, not from a live LLM call. Examples:

- `molecule_targets_gene`: "Drug/compound target relation for sources whose native target endpoint is a gene or OpenTargets/Ensembl target ID; preserve mechanism/action metadata in evidence."
- `enhancer_regulates_gene`: "ENCODE-rE2G composite enhancer-to-gene prediction; preserve biosample, assay feature scores, distance, study, and model score."
- `tissue_expresses_protein`: "Direct Human Protein Atlas tissue protein expression/staining with protein endpoint; no RNA-to-protein projection."

### Evidence-row block

Each evidence row becomes one deterministic block:

```text
evidence_type: <evidence_type>
source: <source>
source_dataset: <source_dataset>
source_record_id: <source_record_id>
predicate: <predicate>
direction: <direction>
evidence_score: <evidence_score>
effect_size: <effect_size>
p_value: <p_value>
paper_id: <paper_id>
dataset_id: <dataset_id>
study_id: <study_id>
text_span: <text_span>
section: <section>
extraction_method: <extraction_method>
release: <release>
```

Rules:

- Drop empty fields before serialization, but record the field allowlist and serializer version in `preprocessing`.
- Normalize floats with a stable format, for example `%.8g`, so hashes do not depend on pandas/Arrow formatting quirks.
- Preserve source predicates and directions as text. Do not normalize `predicate` into a new relation name.
- Parse JSON-like payloads in `predicate` or `text_span` only for stable field filtering/order; do not rewrite scientific meaning.
- Include `paper_id`, `study_id`, and `dataset_id` as provenance identifiers, not as evidence of causal strength by themselves.

### Optional node context

Node context may improve edge vectors but must be bounded and source-reviewed.

Allowed by default:

- preferred labels and canonical IDs from node tables;
- reviewed textual summaries from `kg/v2/features/*_textual_summary.parquet`;
- molecule SMILES/name only if already canonical in molecule node/features;
- protein/gene sequence-derived summaries only if a future policy explicitly permits converting sequence features to text for edge payloads.

Default node-context inclusion:

```text
x_context: <preferred label + first N chars of reviewed summary>
y_context: <preferred label + first N chars of reviewed summary>
```

Use small caps such as 512 characters per endpoint summary for text encoders. Record `node_context_tables`, table hashes, truncation length, and missing-context behavior in the manifest.

Do not include graph-neighborhood labels, split membership, downstream labels, target disease-area assignment, train/test masks, model predictions, or negative-sampling results.

## Aggregating multiple evidence rows into one vector

### Default architecture: relation/value/evidence encoder plus group aggregation

Default for all relations unless overridden:

1. Build the edge header once for each canonical `(relation, x_id, y_id)` edge assertion.
2. Build all edge metadata, value, and evidence-row blocks for the same endpoint pair and relation; if the PyG/GNN export groups multiple source rows or relation variants between the same two nodes, aggregate the full group under the export's stable edge-group key.
3. For each evidence/value row, serialize:

```text
<header>
--- evidence/value row ---
<evidence-row block>
```

4. Encode the payload with a relation/value/evidence encoder:
   - relation/source/predicate/categorical fields use learned categorical embeddings or a compact text encoder;
   - numeric fields such as `evidence_score`, `effect_size`, `p_value`, `e2g_score`, distance, dosage, or assay values are normalized with recorded transforms and passed through an MLP;
   - optional text spans/node context use the approved biomedical text encoder;
   - concatenate/fuse these components and pass through an MLP projection to the configured edge embedding dimension.
5. Aggregate all per-row encodings for the same graph edge/group using a deterministic permutation-invariant reducer such as weighted mean, DeepSets, attention pooling, or concatenation plus projection when the row cap is small and fixed. The output cardinality is exactly one embedding per graph edge or edge group consumed by PyG/GNN.
6. Compute row weights from evidence metadata:

```text
base_weight = relation_override.base_weight or 1.0
score_weight = clipped evidence_score if present and calibrated for this source, else 1.0
credibility_weight = {1: 1.0, 2: 1.25, 3: 1.5}[edge_credibility]
source_weight = relation/source-specific calibrated multiplier, default 1.0
row_weight = base_weight * score_weight * credibility_weight * source_weight
```

7. Normalize row weights to sum to 1 within the edge/group when using weighted pooling.
8. Pool/project to one final edge embedding.
9. L2-normalize the final vector if the model family recommends normalized vectors for retrieval; otherwise record `normalization=none`.

If evidence rows exceed the model/runtime cap, deterministically select or compress rows:

- group exact duplicate evidence blocks by source fields first;
- cap to a relation-configured `max_evidence_rows_per_edge` only after sorting by `source`, `source_dataset`, descending calibrated score, `source_record_id`, `paper_id`, `study_id`;
- record `n_evidence_rows_total`, `n_evidence_rows_encoded`, and `evidence_row_selection_policy`.

### Concatenation, grouping, and aggregation

Concatenate-and-project is allowed when the edge group has a bounded fixed number of values/evidence rows, and can be useful for PyG edge attributes that expect one dense vector. For variable evidence counts, prefer permutation-invariant aggregation after per-row encoding. The builder must always record whether the output row represents a single canonical edge or an aggregated edge group.

Naive concatenate-all-text-and-encode is not the default because:

- long edges can exceed model context and silently discard evidence;
- row provenance becomes less auditable;
- one changed evidence row can perturb a long prompt in hard-to-debug ways;
- weighted pooling lets source confidence and relation-specific scoring be explicit.

### Edges with no evidence file or no evidence rows

For canonical edges without evidence rows, produce one of two outcomes:

1. If the relation has accepted edge-level source metadata sufficient for an edge payload, encode the header-only payload and set:
   - `n_evidence_rows = 0`
   - `aggregation_method = header_only`
   - `evidence_hash = sha256(empty canonical evidence list)`
2. If the edge has neither evidence nor meaningful source metadata, do not write a fabricated canonical vector. In downstream GNN training/export, allocate a learned fallback embedding keyed by relation and endpoint types (or a reviewed relation-specific unknown bucket) and report fallback counts separately.

Legacy/no-fabricated-evidence exceptions, such as accepted TxGNN broad `gene_interacts_gene` edges without row-level evidence, must be explicit in relation overrides.

## Relation-specific override mechanism

Implement overrides as a version-controlled YAML file, for example:

```text
kg/v2/features/edge_embeddings/config/edge_embedding_policy_v1.yaml
```

Recommended shape:

```yaml
policy_version: edge_embedding_policy_v1
serializer_version: edge_payload_serializer_v1
model_default:
  embedding_model: pritamdeka/S-BioBERT-snli-multinli-stsb
  embedding_version: <exact revision>+edge_policy_v1
  embedding_dim: 768
  pooling: relation_value_evidence_mlp_then_group_pool
  normalization: l2
  max_evidence_rows_per_edge: 256
relations:
  molecule_targets_gene:
    include_edge_columns: [action_type]
    score_field: evidence_score
    weight_rule: confidence_weighted_mean
    include_node_context: [molecule_textual_summary, gene_textual_summary]
  enhancer_regulates_gene:
    include_edge_columns: [e2g_score]
    score_field: e2g_score
    weight_rule: calibrated_e2g_score_weighted_mean
    include_evidence_fields: [predicate, text_span, evidence_score, direction, source_dataset, source_record_id, release]
    include_node_context: [gene_textual_summary]
  tissue_expresses_protein:
    include_edge_columns: []
    score_field: null
    weight_rule: direct_measurement_mean
    include_node_context: [tissue_textual_summary]
  gene_interacts_gene:
    include_edge_columns: []
    score_field: evidence_score
    weight_rule: source_dataset_weighted_mean
    accepted_header_only_sources: [TxGNN]
```

Override rules may change:

- evidence field allowlist/order;
- score calibration function;
- evidence row cap;
- whether endpoint textual context is included;
- model family if a relation needs a specialized encoder;
- header-only fallback acceptance.

Override rules must not change canonical relation names, endpoint types, or edge identities.

## Model choices and dimensions

### First-wave default

Use a relation/value/evidence encoder for edge/evidence payloads. Text fields can use a biomedical sentence/text embedding model, but scalar/categorical evidence values must be represented through learned embeddings and MLP projection rather than being reduced to prose only. The first-wave default should align with the node foundation embedding policy:

- default: `pritamdeka/S-BioBERT-snli-multinli-stsb` or a locally benchmarked PubMedBERT/SapBERT sentence embedding checkpoint;
- expected dimension: configured projection dimension, commonly 256-768; text sub-encoder dimensions should be projected by the MLP to the chosen edge feature dimension;
- dtype: `float32` for canonical storage unless a future storage card approves `float16` for large runs;
- normalization: `l2` if the selected sentence-transformer model expects normalized retrieval vectors; otherwise `none` with an explicit manifest value.

A general-purpose model such as `e5-large`/`bge-large` may be benchmarked, but should not be the default for source KG payloads unless it wins a local biomedical retrieval/link-prediction evaluation and privacy/license review.

### Specialized later waves

Relation families may later use specialized encoders, but only via explicit override and downstream validation:

- molecule mechanism edges may combine text evidence vectors with molecule structure/node embeddings downstream, not inside the canonical edge embedding by default;
- protein interaction edges may benchmark protein-text/evidence encoders, but should not average ESM protein sequence vectors into the edge embedding artifact unless a multimodal edge policy is approved;
- enhancer/gene regulatory edges may need a separate sequence/regulatory model in the future, but current policy uses source evidence text/score payloads.

Keep edge embeddings and node embeddings separate. If a downstream GNN wants combined features, it should load node embeddings from `features/embeddings/...` and edge embeddings from `features/edge_embeddings/...` and fuse them in model code.

## Storage schema

Recommended physical layout:

```text
kg/v2/features/edge_embeddings/
  manifests/
    edge_embedding_run_<YYYYMMDD>_<task_id>.json
  reports/
    edge_embedding_run_<YYYYMMDD>_<task_id>_validation.json
    edge_embedding_run_<YYYYMMDD>_<task_id>_skipped_edges.parquet
  config/
    edge_embedding_policy_v1.yaml
  by_relation/
    <relation>/
      <model_slug>/<embedding_version>/part-*.parquet
```

For small/medium relation tables, write one Parquet table per `(relation, model, embedding_version)`. For very large relations, shard by deterministic edge-key hash prefix while keeping a single manifest.

Required Parquet columns:

| Column | Type | Meaning |
|---|---|---|
| `edge_embedding_key` | string | Stable key: `edge_key|embedding_model|embedding_version|payload_hash|aggregation_method`. |
| `edge_key` | string | `relation|x_id|y_id`. |
| `x_id` | string | Canonical source node ID. |
| `x_type` | string | Canonical source node type. |
| `y_id` | string | Canonical target node ID. |
| `y_type` | string | Canonical target node type. |
| `relation` | string | Canonical relation name. |
| `embedding_model` | string | Exact model family/name. |
| `embedding_version` | string | Exact checkpoint/revision plus policy version. |
| `embedding_dim` | int32 | Vector dimension. |
| `embedding_dtype` | string | Physical dtype before Parquet encoding, e.g. `float32`. |
| `embedding_format` | string | `fixed_size_list_float32`, `list_float32`, or external shard format. |
| `embedding` | fixed_size_list<float32> or list<float32> | Vector payload when stored inline. |
| `pooling` | string | `relation_value_evidence_mlp_then_group_pool`, `weighted_mean_evidence_rows`, `attention_pool`, `header_only`, etc. |
| `normalization` | string | `l2` or `none`. |
| `payload_hash` | string | SHA-256 of canonical serialized header, evidence row payloads, node-context payloads, and serializer config. |
| `evidence_hash` | string | SHA-256 of canonical evidence rows after filtering and ordering. |
| `edge_hash` | string | SHA-256 of the canonical edge row fields used. |
| `node_context_hash` | string | SHA-256 of included endpoint context payloads; empty hash if no context. |
| `n_evidence_rows` | int32 | Evidence rows available after leakage filtering. |
| `n_evidence_rows_encoded` | int32 | Evidence rows actually encoded after cap/dedup. |
| `evidence_sources` | string/json | Sorted source/source_dataset summary and counts. |
| `source_edge_uri` | string | Input edge Parquet URI. |
| `source_evidence_uri` | string | Input evidence Parquet URI or empty. |
| `source_node_context_uris` | string/json | Feature/node context inputs used. |
| `preprocessing` | string/json | Serializer version, field allowlists, truncation/cap policies, score calibration. |
| `created_at` | string | UTC build timestamp. |
| `builder_code_version` | string | Git SHA/package version of builder. |
| `license` | string | Effective input/model license summary. |
| `citation` | string | Input source/model citations. |

Optional columns for external vector shards:

- `embedding_uri`
- `row_offset`
- `row_count`
- `embedding_shard_hash`

Example relation path:

```text
kg/v2/features/edge_embeddings/by_relation/molecule_targets_gene/sbiobert_snli_multinli_stsb/edge_policy_v1/part-000.parquet
```

The task body suggested `features/edge_embeddings/<relation>.parquet`; that is acceptable for a small pilot. The production convention above is preferred because it versions by model and policy without overwriting old artifacts.

## Manifest fields

Each run manifest should include:

```json
{
  "run_id": "edge_embedding_run_YYYYMMDD_task",
  "kg_root": "gs://jouvencekb/kg/v2",
  "policy_version": "edge_embedding_policy_v1",
  "serializer_version": "edge_payload_serializer_v1",
  "embedding_model": "exact/model/name",
  "embedding_version": "revision+edge_policy_v1",
  "embedding_dim": 768,
  "relations": ["molecule_targets_gene"],
  "input_edge_uris": ["gs://jouvencekb/kg/v2/edges/molecule_targets_gene.parquet"],
  "input_evidence_uris": ["gs://jouvencekb/kg/v2/evidence/molecule_targets_gene.parquet"],
  "input_node_context_uris": ["gs://jouvencekb/kg/v2/features/molecule_textual_summary.parquet"],
  "output_uris": ["gs://jouvencekb/kg/v2/features/edge_embeddings/by_relation/.../part-000.parquet"],
  "input_hashes": {"edges/molecule_targets_gene.parquet": "sha256..."},
  "edge_rows": 41239,
  "embedded_edges": 41239,
  "skipped_edges": 0,
  "builder_code_version": "git sha or package version",
  "created_at": "UTC timestamp",
  "validation": {
    "endpoint_antijoin_rows": 0,
    "evidence_join_miss_edges": 0,
    "duplicate_edge_embedding_keys": 0,
    "non_finite_vectors": 0
  }
}
```

## Concrete examples

The following examples use real canonical relation/evidence patterns observed in the current KG mount. Values are illustrative snippets, not a full embedding job.

### Example 1: `molecule_targets_gene` / mechanism-of-action evidence

Canonical edge pattern:

```text
x_id: CHEMBL1000
x_type: molecule
y_id: ENSG00000196639
y_type: gene
relation: molecule_targets_gene
display_relation: Histamine H1 receptor antagonist
source: OpenTargets
credibility: 1
edge metadata: action_type=ANTAGONIST
```

Evidence pattern:

```text
evidence_type: database_record
source: OpenTargets
source_dataset: drug_mechanism_of_action
source_record_id: <OpenTargets MoA row id>
direction: ANTAGONIST
predicate: ANTAGONIST
text_span: {"action_type":"ANTAGONIST", "endpoint_policy":"..."}
release: 26.03
```

Embedding payload should say that a ChEMBL molecule targets an Ensembl gene and preserve the action type as evidence metadata. It must not create a protein target embedding unless the source directly identifies a protein endpoint. If multiple MoA/DrugBank/CTD rows support the same edge, encode each row and weight by calibrated source confidence/evidence score if available.

### Example 2: `enhancer_regulates_gene` / ENCODE-rE2G model evidence

Canonical edge pattern:

```text
x_id: c89213ff6f21bcc0326986caac60b8d7
x_type: enhancer
y_id: ENSG00000225880
y_type: gene
relation: enhancer_regulates_gene
display_relation: regulates
source: OpenTargets/E2G
credibility: 2
edge metadata: e2g_score=0.645834
```

Evidence pattern:

```text
evidence_type: model_prediction
source: OpenTargets
source_dataset: enhancer_to_gene
evidence_score: <rE2G score when present>
direction: enhancer_to_gene
predicate: intergenic
text_span: {"biosampleId":"UBERON_0002113", "biosampleName":"...", ...}
section: ENCODE-rE2G biosample-specific composite model
extraction_method: OpenTargets 26.03 enhancer_to_gene parquet transform
```

Relation override should include `e2g_score` and biosample/model fields from `text_span`, and use a calibrated score-weighted pool when multiple biosample-specific rows support the same enhancer→gene assertion. The payload may include gene textual context if available. It should not include downstream disease labels or GNN split membership.

### Example 3: `tissue_expresses_protein` / direct HPA protein evidence

Canonical edge pattern:

```text
x_id: UBERON:0000992
x_type: tissue
y_id: ENSP00000440729
y_type: protein
relation: tissue_expresses_protein
display_relation: protein expression present
source: HPA
credibility: 3
```

Evidence pattern:

```text
evidence_type: protein_expression
source: HPA
source_dataset: proteinatlas.tsv
predicate: direct_protein_staining_or_protein_atlas_intensity
direction: tissue_to_protein
text_span: {"gene_id":"ENSG...", "uniprot_id":"...", ...}
section: HPA protein tissue specific intensity
extraction_method: HPA 25.1 proteinatlas.tsv transform
release: HPA 25.1
```

The embedding payload must preserve that this is direct protein staining/intensity evidence. It must not mention RNA expression as support and must not project gene/RNA evidence into this protein edge. Multiple antibodies/tissue subcontexts can be separate evidence rows and pooled.

### Example 4: `gene_interacts_gene` / broad interaction evidence plus legacy exception

Canonical edge pattern:

```text
x_type: gene
y_type: gene
relation: gene_interacts_gene
display_relation: interacts with
source: OpenTargets or TxGNN
credibility: 1..3
```

Evidence pattern for OpenTargets-supported rows:

```text
evidence_type: molecular_interaction
source: OpenTargets
source_dataset: interaction
predicate: string or other source database/channel
direction: undirected
text_span: {"targetA":"ENSG...", "targetB":"ENSG...", ...}
section: OpenTargets molecular interactions: IntAct/Reactome/String/etc.
extraction_method: OpenTargets 26.03 interaction parquet transform
```

Relation override should treat this relation as broad gene/gene-product interaction and preserve source channel in the evidence block. It must not split the edge embedding into `protein_interacts_protein`, `tf_regulates_gene`, or transcript/TF/enhancer embeddings from product identifiers inside `text_span`. Accepted TxGNN legacy rows without fabricated evidence may use `header_only` with an explicit `accepted_header_only_sources: [TxGNN]` override.

## Leakage and split-safety rules

Edge embeddings are often consumed by link prediction and GNN splits, so leakage control is mandatory.

Do not include:

- train/valid/test split assignment;
- labels/outcomes being predicted, unless they are the edge relation itself already present in the training graph and allowed by the task design;
- negative samples or absence labels;
- model predictions, validation metrics, or post-hoc explanations;
- disease-area holdout membership;
- downstream repurposing labels such as hidden indications/contraindications when embedding non-target edges;
- graph-neighborhood summaries computed after split construction if they reveal held-out positives;
- future evidence rows whose `created_at`, `release`, study date, or source version is after a time-split cutoff.

For transductive link prediction, it is acceptable for a training edge embedding to include that edge's own source evidence. For held-out positive edges, either:

1. build embeddings only from evidence available at the split cutoff and ensure the edge itself is allowed as an input feature for the evaluation protocol; or
2. exclude edge embeddings for target evaluation edges and use them only after prediction for interpretation.

For inductive or time-split evaluation, the embedding builder must accept a `max_source_release`/`max_created_at` filter and include the filter in `payload_hash` and manifest.

Never build edge embeddings from labels that the evaluation is supposed to predict. For example, a `molecule_treats_disease` held-out indication edge should not be embedded from positive indication evidence if the task is to predict that edge. Use only non-target context edges/features or run a separate post-hoc explanation artifact after evaluation.

## Validation and checksum strategy

Every run must validate both biological keys and vector integrity.

Required checks:

1. Edge endpoint anti-join: every `x_id`/`y_id` in output exists in `nodes/{x_type}.parquet` and `nodes/{y_type}.parquet`.
2. Relation schema check: each output `relation` exists in `RELATION_BY_NAME` and endpoint types match the relation spec.
3. Evidence join check: evidence rows, when present, join by `edge_key` to an existing canonical edge.
4. Duplicate check: `edge_embedding_key` unique; also at most one active embedding row per `(edge_key, embedding_model, embedding_version, policy_version)`.
5. Evidence count check: `n_evidence_rows` equals the count after leakage filters; `n_evidence_rows_encoded <= n_evidence_rows`.
6. Payload checksum check: recompute `payload_hash`, `edge_hash`, `evidence_hash`, and `node_context_hash` for a sample or full table.
7. Vector dimensionality: every row has exactly `embedding_dim` floats.
8. Vector finite check: no NaN/Inf values.
9. Empty/all-zero check: reject all-zero embeddings unless a future model-specific policy says they are valid.
10. Coverage report: canonical edge rows, embedded edges, skipped edges by reason, evidence-row distribution, node-context coverage.
11. License/provenance check: no blank input/model license or citation fields for promoted artifacts.
12. Reproducibility check: manifest includes exact input URIs, object generations or SHA-256 hashes, builder code version, policy config hash, model revision, tokenizer revision, pooling, normalization, and runtime preprocessing.

Checksum definitions:

- `edge_hash`: SHA-256 over canonical JSON of the selected edge row fields sorted by key.
- `evidence_hash`: SHA-256 over canonical JSON-lines of leakage-filtered evidence rows sorted by `(source, source_dataset, source_record_id, paper_id, dataset_id, study_id, predicate, created_at)`.
- `node_context_hash`: SHA-256 over canonical JSON of included endpoint context records and their source table hashes.
- `payload_hash`: SHA-256 over the full serialized payload(s), field allowlists, truncation settings, evidence-row cap policy, score calibration policy, and model input separator tokens.
- `edge_embedding_key`: SHA-256 or literal stable composite of `edge_key`, `embedding_model`, `embedding_version`, `payload_hash`, and `aggregation_method`.

Artifacts are immutable. If any input, serializer, model checkpoint, pooling rule, leakage filter, or builder code changes, write a new `embedding_version` or run prefix. Do not overwrite old edge embedding Parquets in place.

## Buildability and roadmap

Recommended sequence:

1. Implement a small serializer/manifest helper for edge embedding payloads and checksums.
2. Treat the previous HashingVectorizer pilot as schema-only validation; it did not create production embeddings.
3. Run a tiny capped real-encoder pilot on a few relations (`molecule_targets_gene`, `enhancer_regulates_gene`, `tissue_expresses_protein`, `gene_interacts_gene`) to validate schema, hashes, MLP value encoding, grouping, and one-vector-per-PyG-edge output.
4. First full relation/value/evidence-encoder wave: relations with rich evidence rows and moderate size.
5. Large relations such as `enhancer_regulates_gene` or very high-evidence-count `gene_interacts_gene` need sharding, row caps, and progress checkpointing.
6. Downstream GNN integration should load these as optional edge features/sidecars, not as replacement graph topology.

Non-goals:

- No large embedding jobs in this policy card.
- No external API embedding of KG payloads without explicit approval.
- No placeholder zero/random vectors in canonical artifacts; use learned downstream fallback embeddings for edges without source/evidence payloads.
- No relation splitting or endpoint projection through embeddings.
- No overwriting canonical edge/evidence files.
- No raw secrets or private user data in payloads/manifests.
