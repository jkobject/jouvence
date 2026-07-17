# Foundation embedding policy for KG node features

Task: `t_8f039536`  
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`  
Scope: policy/design only. Do not run large embedding jobs from this card.

## Executive decision

Foundation-model embeddings should be stored as versioned model feature artifacts under the KG feature layer, not as biological graph assertions. They should derive from reviewed node features in `kg/v2/features/` and must preserve enough metadata to reproduce the exact input payload and embedding model run.

Recommended defaults for the first production wave:

| Node/modal source | Default embedding family | Why this default |
|---|---|---|
| Biomedical text summaries | Biomedical sentence/text embedding model, default `pritamdeka/S-BioBERT-snli-multinli-stsb` or a locally benchmarked PubMedBERT/SapBERT encoder | Works now from existing textual-summary tables; cheap CPU/GPU batching; preserves ontology/text semantics without adding new source data. |
| Molecule SMILES/structures | Dual track: existing Morgan fingerprint stays baseline; add ChemBERTa/SMILES transformer embedding as default learned molecule embedding after small pilot | The official sparse Morgan table is already deterministic and useful; learned SMILES embeddings add chemical-neighborhood signal but need model/version pinning and validation. |
| Protein sequences | ESM2, default `esm2_t33_650M_UR50D`; smaller fallback `esm2_t12_35M_UR50D`; larger optional `esm2_t36_3B_UR50D` | Strong protein sequence baseline, local batchable, available for the official `protein_sequence` table. |
| Transcript/RNA/DNA sequences | Nucleotide Transformer family as default DNA/cDNA encoder; DNABERT-2 as cheaper fallback; RNA-FM only for explicit RNA/mature-miRNA payloads | Current transcript features are cDNA strings; use nucleotide models rather than protein or text models. RNA-specific models wait for true RNA/mature/precursor features. |
| Genes, pathways, diseases, phenotypes, tissues, cell types, cell lines | Text/ontology embeddings from reviewed summaries; optionally concatenate ontology-context text before embedding | These node types mostly have ontology/source definitions, not direct sequence payloads. |
| Nodes with no direct feature payload | Learned fallback embedding initialized/trained in the downstream model, keyed by node type/id and never stored as a fabricated canonical source-derived vector | Use a model-side learned embedding when no reviewed payload exists; keep missing-source coverage explicit. |

## Current feature inventory

The official feature layer is `gs://jouvencekb/kg/v2/features/`. The local FUSE path was not mounted during this policy write, so the inventory below comes from the canonical promotion reports already committed in `docs/`.

Officially promoted objects:

| Feature table | Node type | Rows / unique nodes | Source payload | Buildable embedding now? | Notes |
|---|---:|---:|---|---|---|
| `cell_line_textual_summary.parquet` | `cell_line` | 1,140 | Cellosaurus OBO comments mapped through DepMap xrefs | Yes, text | High coverage for cell lines in current cache. |
| `cell_type_textual_summary.parquet` | `cell_type` | 3,135 | Cell Ontology definitions | Yes, text | Ontology definitions are suitable direct text input. |
| `disease_textual_summary.parquet` | `disease` | 26,395 | OpenTargets disease descriptions with upstream ontology attribution | Yes, text | Good first wave; keep ontology/source in provenance. |
| `gene_textual_summary.parquet` | `gene` | 212,029 | OpenTargets target descriptions with Ensembl/NCBI/HGNC attribution where available | Yes, text | Use text embedding now; sequence/genomic embedding still needs coordinates/source policy. |
| `molecule_textual_summary.parquet` | `molecule` | 22,230 | ChEMBL-derived OpenTargets molecule metadata | Yes, text fallback | Prefer structure embeddings when SMILES/fingerprint exists; text is useful for biologics/missing structures. |
| `molecule_fingerprint.parquet` | `molecule` | 18,614 | RDKit Morgan sparse on-bits from `nodes/molecule.parquet.smiles` | Yes, deterministic baseline; learned molecule embeddings require SMILES payload or canonical SMILES derivation | Official table uses `morgan_binary`, radius 2, 2048 bits, chirality/bond types enabled. |
| `pathway_textual_summary.parquet` | `pathway` | 37,492 | GO definitions for GO-backed pathway nodes | Yes, text | Reactome descriptions remain deferred until an approved dump/API payload is available. |
| `phenotype_textual_summary.parquet` | `phenotype` | 13,810 | HPO definitions | Yes, text | Good text/ontology embedding input. |
| `protein_sequence.parquet` | `protein` | 112,051 | Ensembl human protein FASTA | Yes, protein sequence | Direct input for ESM/ProtT5-class models. |
| `protein_textual_summary.parquet` | `protein` | 162,163 text rows / 69.30% protein coverage | Validated/promoted full UniProt functional/comment summaries | Yes, text | Official protein text signal; build protein text embeddings as a separate modality from protein sequence. |
| `tissue_textual_summary.parquet` | `tissue` | 11,942 | UBERON definitions | Yes, text | Good text/ontology embedding input. |
| `transcript_sequence.parquet` | `transcript` | 187,268 | Ensembl human cDNA FASTA | Yes, nucleotide sequence | Use DNA/cDNA nucleotide models; do not treat as protein. |

Validated/promoted expansion:

- `kg/v2/features/protein_textual_summary.parquet` is now an official available feature table from the full UniProt textual-summary expansion, with 162,163 protein text rows / 69.30% protein coverage reported in `docs/full_uniprot_textual_summary_expansion_20260623_t_0b0ca3cb.md`. Treat it as available text signal for protein text embeddings.

Deferred or missing sources:

| Needed feature | Target node types | Status |
|---|---|---|
| `gene_genomic_interval` / `gene_genomic_sequence` | `gene` | Missing. Prior audit recommends a coordinate/mapping precursor before raw sequence extraction; current cached gene nodes did not carry chromosome/start/end/strand. |
| Promoter/TSS/window sequence | `gene`, regulatory modeling | Missing. Requires explicit TSS/canonical-transcript/window policy. |
| Enhancer genomic sequence | `enhancer` | Missing. Requires accepted enhancer coordinates, reference build, and extraction policy. |
| Mutation local allele/context sequence | `mutation` | Missing. Requires reviewed variant coordinates/ref/alt and reference-build policy. |
| miRNA/lncRNA mature/precursor RNA sequence | future RNA node types | Missing. Requires node mapping and source terms. |
| Protein textual summaries | `protein` | Available as official `kg/v2/features/protein_textual_summary.parquet`; use for protein text embeddings, separate from protein sequence embeddings. |
| Reactome pathway descriptions | `pathway` | Deferred. GO definitions are official for GO-backed pathway rows. |
| Dataset/paper/organism text features | `dataset`, `paper`, `organism` | No official feature tables inventoried in this wave. Use only canonical metadata when a build card defines source/license. |

## Model shortlist by modality

### Biomedical text and ontology definitions

Use for: `gene_textual_summary`, official `protein_textual_summary`, `disease_textual_summary`, `pathway_textual_summary`, `phenotype_textual_summary`, `cell_type_textual_summary`, `tissue_textual_summary`, `cell_line_textual_summary`, and text fallback for molecules/datasets/papers when source text is canonical.

| Candidate | Pros | Cons | Recommended role |
|---|---|---|---|
| `pritamdeka/S-BioBERT-snli-multinli-stsb` | Biomedical sentence-transformer style model; easy to batch; reasonable default for short definitions/summaries | Older/smaller; may lag newer embedding models on retrieval benchmarks | Default first wave if no project benchmark exists. |
| PubMedBERT-derived sentence embedding model, e.g. a local `pubmedbert` sentence-transformer checkpoint | Biomedical vocabulary and abstracts; good for disease/gene/protein prose | Many checkpoints are not contrastively trained for embeddings; must pick and pin one exact model | Benchmark candidate; use if local retrieval/edge prediction eval beats S-BioBERT. |
| SapBERT / BioSyn-style entity encoder | Strong biomedical synonym/entity normalization behavior | Optimized for entity names/synonyms more than long summaries | Recommended auxiliary embedding for ontology-name/synonym-only nodes. |
| General strong embedding model, e.g. `intfloat/e5-large-v2`, `BAAI/bge-large-en-v1.5`, or local approved equivalent | Strong general semantic retrieval; robust for mixed source prose | Not biomedical-specific; may blur ontology/scientific distinctions | Fallback/comparison baseline, not default unless it wins project eval. |
| API commercial embedding | Often strong and easy operationally | Privacy/cost/external data transfer concerns; source licenses may forbid sending payloads out | Avoid by default for KG source payloads unless explicitly approved. |

Default pooling/payload policy:

- Input text should be deterministic: `<node_type>: <preferred_label>. <summary_text>` plus selected synonyms/xrefs only when they are already canonical feature/node metadata.
- For multi-row summaries per node, embed each source row and also write an optional aggregated row with stable source ordering, not ad-hoc concatenation.
- Use normalized vectors for retrieval-style models when recommended by the model card; record `normalization` in metadata.

### Molecules and chemical structures

Use for: molecule nodes with official `molecule_fingerprint` rows and/or canonical SMILES in molecule node metadata.

| Candidate | Pros | Cons | Recommended role |
|---|---|---|---|
| Existing Morgan fingerprint (`molecule_fingerprint`, radius 2, 2048 bits) | Already official; deterministic; cheap; reproducible; good cheminformatics baseline | Not a foundation-model embedding; sparse binary not learned/contextual | Keep as baseline feature and compatibility input. Do not replace. |
| ChemBERTa / RoBERTa SMILES encoder | Easy SMILES input; local inference; learned chemical semantics | SMILES tokenization/canonicalization affects output; quality varies by checkpoint | Default learned molecule embedding pilot. Pin exact checkpoint and input SMILES policy. |
| MolFormer / MoLFormer family | Strong molecular representation literature; good learned baseline | Checkpoint availability/licensing and runtime need validation | Benchmark candidate after ChemBERTa pilot. |
| Graph neural molecular encoder pretrained on molecular graphs | Uses graph structure directly; less SMILES-order sensitive | Requires RDKit graph featurization and checkpoint-specific pipeline | Second wave if SMILES transformer underperforms. |
| Text embedding of molecule descriptions | Works for biologics/no SMILES and mechanism descriptions | Captures names/descriptions, not chemical structure | Fallback/companion only; never call it structure embedding. |

Default recommendation:

1. Keep `molecule_fingerprint` as `feature_family=chemical_fingerprint`.
2. Add a learned `molecule_smiles_embedding` from RDKit canonical SMILES where SMILES exists and parses.
3. For molecules without valid SMILES, write no learned structure embedding row; optionally write `molecule_text_embedding` from official text summary.

### Proteins

Use for: `protein_sequence.parquet`; also official `protein_textual_summary.parquet` as a separate text modality.

| Candidate | Pros | Cons | Recommended role |
|---|---|---|---|
| ESM2 `esm2_t33_650M_UR50D` | Strong widely used protein sequence embedding; practical batch size on a GPU; residue and sequence embeddings available | Heavier than small ESM2; long proteins may need truncation/windowing policy | Default protein sequence embedding. |
| ESM2 `esm2_t12_35M_UR50D` | Much cheaper; useful for full coverage or CPU/small GPU testing | Lower representation quality | Fallback/smoke-test model. |
| ESM2 `esm2_t36_3B_UR50D` or larger | Higher capacity | Expensive; long runtime/storage; not needed for first policy wave | Optional high-quality recompute after eval/cost approval. |
| ProtT5 / ProtTrans | Strong historical protein embeddings; sentencepiece pipeline available | Larger/older operational stack; can be slower | Benchmark alternative, not first default unless ESM unavailable. |
| Protein language model + UniProt text dual embedding | Combines sequence with official UniProt function/subcellular/PTM comments | Requires an explicit fusion policy, even though the protein text table is now available | Second wave multimodal protein representation. |

Protein pooling policy:

- Store one sequence-level vector per protein by mean pooling final hidden states over non-special residues, unless the model-specific best practice says otherwise.
- For proteins longer than the model context, do not silently truncate. Use a documented windowing strategy (`window_size`, `stride`, `pooling=mean_of_window_means`) or mark rows skipped with a build report.
- Keep protein text embeddings separate from protein sequence embeddings; fuse downstream, not in the canonical artifact, unless a future card defines a multimodal model.

### DNA, cDNA, transcripts, RNA, enhancer, mutation sequence

Use now for: `transcript_sequence.parquet` cDNA. Use later for gene/enhancer/mutation/RNA sequence features once source features are promoted.

| Candidate | Pros | Cons | Recommended role |
|---|---|---|---|
| Nucleotide Transformer family | Designed for DNA/RNA-like nucleotide sequences; good general default for cDNA/genomic intervals | Long sequences still need context/window policy; exact checkpoint must be pinned | Default for transcript cDNA and future genomic intervals. |
| DNABERT-2 | Efficient and common; works with nucleotide k-mers/tokenization | May be less strong than larger nucleotide transformers depending on task | Cheaper fallback and benchmark baseline. |
| HyenaDNA / long-context genomic sequence model | Handles much longer sequences than many transformers | Operational complexity; checkpoint/task fit needs validation | Consider for long gene/enhancer intervals after coordinate policy exists. |
| RNA-FM / RNA-specific foundation model | Better match for mature/precursor RNA payloads | Current official transcript sequences are cDNA, not RNA-specific structured sequences | Use only when RNA features are explicit. |

Default transcript policy:

- Current official `transcript_sequence` is cDNA (`alphabet=dna_iupac`), so first wave uses nucleotide DNA model embeddings.
- Keep transcript embeddings separate from gene embeddings. Do not average transcripts into gene vectors until a canonical transcript/gene aggregation policy exists.
- For very long transcripts, use the same no-silent-truncation rule as proteins: explicit windowing/stride/pooling metadata or skipped-row accounting.

### Genes, ontology entities, cell contexts, diseases, phenotypes

Default is text/ontology embedding from official textual summaries. If a node has multiple modalities in the future:

- `gene`: text embedding now; later add separate genomic interval/sequence embedding if promoted. Do not replace gene text with transcript-derived embedding.
- `pathway`: text embedding from GO/Reactome definitions; optional member-gene set encoder belongs to a separate graph/topology feature policy.
- `disease` / `phenotype`: text/ontology definitions; optional ontology-neighborhood embedding should be a separate graph-derived feature.
- `cell_type` / `tissue` / `cell_line`: text/ontology definitions now; expression-signature embeddings require reviewed measurement/source context and should not be mixed into text embeddings.
- `dataset` / `paper`: use bibliographic/metadata text only after source/license policy exists.
- `organism`: likely text/taxonomy embedding; low priority unless non-human KG expansion needs it.

## Embedding table schema

Embeddings should use a common metadata envelope across modalities. Recommended physical layout is one Parquet table per `(node_type, modality, model, major policy version)` under `kg/v2/features/embeddings/` plus JSON manifests and build reports.

Required Parquet columns:

| Column | Type | Meaning |
|---|---|---|
| `embedding_key` | string | Stable key: `node_id|node_type|embedding_model|embedding_version|source_feature_key_or_hash|pooling`. |
| `node_id` | string | Canonical KG node id. |
| `node_type` | string | Canonical KG node type. |
| `source_feature_table` | string | Feature table used, e.g. `gene_textual_summary`, `protein_sequence`, `molecule_fingerprint`, `nodes/molecule.parquet.smiles`. |
| `source_feature_key` | string | Upstream feature row key when available; empty only for node-table-derived fallbacks. |
| `source_feature_hash` | string | SHA-256 of canonical serialized input payload and relevant preprocessing metadata. |
| `modality` | string | `text`, `molecule_smiles`, `molecule_fingerprint`, `protein_sequence`, `nucleotide_sequence`, `rna_sequence`, `ontology_text`, `multimodal_fusion`, etc. |
| `embedding_model` | string | Model family/name, e.g. `esm2_t33_650M_UR50D`. |
| `embedding_version` | string | Exact checkpoint/version/revision and local policy version. Prefer `model@revision+policy_vN`. |
| `embedding_dim` | int32 | Vector dimension. |
| `embedding_dtype` | string | Physical dtype before Parquet encoding, e.g. `float32`, `float16`. |
| `embedding_format` | string | `fixed_size_list_float32`, `list_float32`, or external shard format. |
| `embedding` | fixed_size_list<float32> or list<float32> | Vector payload when stored inline. Use fixed-size list where tooling supports it. |
| `pooling` | string | `cls`, `mean_non_special_tokens`, `mean_residue`, `mean_window_means`, `model_default`, etc. |
| `normalization` | string | `none`, `l2`, or model-specific. |
| `preprocessing` | string/json | Canonical input construction, tokenization, truncation/windowing policy, SMILES canonicalization, etc. |
| `input_length` | int64 | Characters/residues/bases/tokens as appropriate before model tokenization, or source sequence length. |
| `window_count` | int32 | Number of model windows used for long sequences; `1` for normal rows. |
| `created_at` | string | UTC build timestamp. |
| `source_feature_release` | string | Upstream feature/source release read by the embedding job. |
| `provenance` | string/json | Builder command, code version, model cache path or registry URI, device/runtime summary. |
| `license` | string | Effective license/terms inherited from input plus model license. |
| `citation` | string | Input source and model citations. |

Optional but recommended columns:

- `model_provider` (`huggingface`, `local`, `internal`, etc.).
- `model_revision_sha` or commit hash.
- `token_count` for text/sequence transformer jobs.
- `skip_reason` should not be in the main embedding table; put skipped rows in a sidecar report. Main embedding tables should contain only successfully embedded rows.

Vector storage recommendation:

- For moderate tables, store vectors inline as Parquet `fixed_size_list<float32>[dim]`, partitioned by `node_type` and `embedding_model`.
- If a backend has trouble with fixed-size lists, use `list<float32>` but assert equal `embedding_dim` in validation.
- For very large/high-dimensional runs, keep a Parquet metadata/index table plus external `.npy`, `.zarr`, or Arrow IPC shards. The metadata table must still carry `embedding_uri`, `row_offset`, `row_count`, `embedding_dim`, `embedding_dtype`, and content hash for each shard.
- Do not store JSON-encoded vectors except for tiny debugging samples.

## Artifact layout

Recommended canonical layout:

```text
kg/v2/features/embeddings/
  manifests/
    <run_id>.json
  reports/
    <run_id>_validation.json
    <run_id>_skipped_rows.parquet
  text/
    <node_type>/
      <model_slug>/<embedding_version>/part-*.parquet
  ontology_text/
    <node_type>/
      <model_slug>/<embedding_version>/part-*.parquet
  molecule_smiles/
    molecule/<model_slug>/<embedding_version>/part-*.parquet
  protein_sequence/
    protein/<model_slug>/<embedding_version>/part-*.parquet
  nucleotide_sequence/
    transcript/<model_slug>/<embedding_version>/part-*.parquet
```

Example first-wave outputs:

```text
kg/v2/features/embeddings/text/gene/sbiobert_snli_multinli_stsb/policy_v1/part-000.parquet
kg/v2/features/embeddings/text/disease/sbiobert_snli_multinli_stsb/policy_v1/part-000.parquet
kg/v2/features/embeddings/protein_sequence/protein/esm2_t33_650m_ur50d/policy_v1/part-*.parquet
kg/v2/features/embeddings/nucleotide_sequence/transcript/nucleotide_transformer/<checkpoint>+policy_v1/part-*.parquet
kg/v2/features/embeddings/molecule_smiles/molecule/chemberta/<checkpoint>+policy_v1/part-*.parquet
kg/v2/features/embeddings/manifests/embedding_run_<YYYYMMDD>_<task_id>.json
```

Manifest fields:

```json
{
  "run_id": "embedding_run_YYYYMMDD_task",
  "kg_root": "gs://jouvencekb/kg/v2",
  "input_feature_uris": ["gs://jouvencekb/kg/v2/features/gene_textual_summary.parquet"],
  "output_uris": ["gs://jouvencekb/kg/v2/features/embeddings/text/gene/.../part-000.parquet"],
  "embedding_model": "exact/model/name",
  "embedding_version": "revision+policy_v1",
  "embedding_dim": 768,
  "input_rows": 212029,
  "embedded_rows": 212029,
  "skipped_rows": 0,
  "source_feature_hashes": {"gene_textual_summary.parquet": "sha256..."},
  "builder_code_version": "git sha or package version",
  "created_at": "UTC timestamp",
  "validation": {"endpoint_antijoin_rows": 0, "duplicate_embedding_keys": 0}
}
```

## Update and recompute strategy

Embeddings are derived features. They should be immutable once promoted and recomputed into a new `embedding_version` or run prefix when any of the following changes:

1. Input feature content changes, detected by object generation/SHA256 or table-level manifest hash.
2. Input payload construction changes, e.g. adding preferred labels/synonyms to text.
3. Model checkpoint, revision, tokenizer, or pooling/normalization policy changes.
4. Runtime-affecting preprocessing changes, e.g. sequence window size/stride or SMILES canonicalization.
5. Bug fix in builder code that changes any vector or source hash.

Do not overwrite existing embedding artifacts in place. Promotion should be copy-once into a new versioned prefix, with a manifest that points to exact input objects and source hashes.

Validation gates for each run:

- Endpoint anti-join: every `node_id` must exist in the target node table.
- Duplicate key check: `embedding_key` unique in an output table.
- Dimensionality check: every row has exactly `embedding_dim` floats.
- Non-finite check: no NaN/Inf vector values.
- Empty/all-zero check: reject all-zero embeddings unless a specific model can legitimately emit them and policy says so.
- Source hash check: recompute `source_feature_hash` for a sample or the full table.
- Coverage report: input rows, unique input nodes, embedded rows, skipped rows by reason.
- License/provenance check: no blank model/input license or citation fields.

Compute assumptions:

| Wave | Expected cost profile | Operational note |
|---|---|---|
| Text embeddings for ~300k-600k summary rows | Cheap/moderate. Single GPU or CPU batching is plausible depending on model. | First wave; run by node type and checkpoint each table separately. |
| Molecule SMILES embeddings for ~18k-22k structures | Cheap. | Pilot-friendly; compare against existing Morgan fingerprints in downstream eval. |
| Protein ESM2 for ~112k sequences | Moderate/heavy. Requires GPU batching and long-sequence policy. | Run as its own card/job, checkpoint progress, and heartbeat/log counts. |
| Transcript nucleotide embeddings for ~187k cDNA sequences | Heavy. Long sequences can dominate runtime. | Requires explicit windowing/skipping policy before job launch. |
| Future gene/enhancer/mutation sequence embeddings | Potentially very heavy. | Do not start until source sequence feature tables are promoted and size distribution is known. |

## Buildability matrix

Can build now from official features:

| Embedding artifact | Inputs | Recommended model | Status |
|---|---|---|---|
| Text embeddings for cell lines, cell types, diseases, genes, molecules, pathways, phenotypes, proteins, tissues | Official `*_textual_summary.parquet`, including `protein_textual_summary.parquet` | S-BioBERT/PubMedBERT/SapBERT benchmark set | Buildable now; not done until actual vectors are created and validated. |
| Molecule deterministic baseline | Official `molecule_fingerprint.parquet` | Already built fingerprint; optionally convert to dense model input downstream | Available now. |
| Molecule learned SMILES embedding | `nodes/molecule.parquet.smiles` and/or fields already captured by `molecule_fingerprint` provenance | ChemBERTa/MolFormer pilot | Buildable if the builder reads the same reviewed SMILES source and records source hash. |
| Protein sequence embeddings | Official `protein_sequence.parquet` | ESM2 default | Buildable now, but compute-heavy. |
| Transcript cDNA embeddings | Official `transcript_sequence.parquet` | Nucleotide Transformer/DNABERT-2 | Buildable now, but compute-heavy and long-sequence policy must be explicit. |

Needs missing or unpromoted source features:

| Embedding artifact | Missing prerequisite |
|---|---|
| Gene genomic sequence embeddings | Build/promote gene coordinate or sequence feature table from accepted Ensembl/GENCODE mapping and GRCh38 reference policy. |
| Enhancer sequence embeddings | Accepted enhancer coordinate feature table and reference extraction policy. |
| Mutation sequence/context embeddings | Accepted variant coordinate/ref/alt source and reference context policy. |
| RNA-specific embeddings | Mature/precursor RNA feature tables and node mapping/source terms. |
| Reactome-specific pathway text embeddings | Approved local Reactome description JSON/TSV/API payload and promoted pathway textual summaries. |
| Cell expression/signature embeddings | Reviewed measurement matrix/source policy; should be separate from text embeddings. |
| Graph/topology embeddings | Separate graph-derived feature policy; not covered by this foundation-model payload policy. |

## Multimodal fallback and fusion policy

Do not force one vector per node by mixing modalities prematurely. Store separate embeddings per modality and let downstream model code decide how to fuse.

Recommended fallback precedence for a downstream consumer that needs a single vector:

1. Use the modality most directly tied to the node biology/chemistry: protein sequence for proteins, molecule structure for molecules, transcript nucleotide sequence for transcripts.
2. If direct modality is absent, use reviewed text/ontology embedding when available.
3. If only node name/xrefs are available, build a low-confidence `node_metadata_text` embedding only after a source/license policy card defines the payload.
4. If no reviewed payload exists, do not write a fabricated canonical embedding row. For GNN/model training, allocate a learned fallback embedding (for example a trainable per-node-type unknown bucket or per-node ID table, regularized and versioned in model artifacts) and report missing source-feature coverage separately.

Fusion options for future cards:

- Late fusion: keep vectors separate and concatenate/attention-fuse in the GNN/ML pipeline.
- Projection layer: train modality-specific projections to a common dimension using graph/self-supervised objectives; store learned projected vectors only under a separate `learned_projection` policy version.
- Neighbor-derived imputation: only as a model-training artifact, not canonical KG feature, unless explicitly approved and marked as imputed.

## First implementation roadmap

1. Add a lightweight manifest/schema helper for `features/embeddings/` but do not run embedding jobs in this policy card.
2. Treat the previous HashingVectorizer pilot as schema/artifact-layout validation only; it is not a production embedding model and does not make embeddings done.
3. Run a capped real-model pilot per modality to validate schema, vector dtype, source hashing, and artifact layout with actual vectors.
4. First full wave: text embeddings for official textual summaries, including `protein_textual_summary.parquet`, and learned molecule SMILES embeddings, because they are cheap and mostly complete.
5. Second wave: protein ESM2 embeddings with explicit long-sequence/window policy and progress checkpointing.
6. Third wave: transcript nucleotide embeddings after a length distribution audit.
7. Later waves: gene/enhancer/mutation/RNA embeddings only after missing source feature tables are promoted.

## Non-goals and guardrails

- No large embedding jobs in this card.
- No scraping or external API embedding of KG payloads without explicit approval.
- No placeholder vectors for missing modalities in canonical feature artifacts; use learned model-side fallback embeddings for nodes without reviewed payloads.
- No overwriting existing official feature artifacts.
- No conflation of RNA/gene/transcript/protein biology: transcript cDNA embeddings are transcript features; protein embeddings are protein sequence features; gene genomic embeddings require gene genomic source features.
- No raw PII or secrets in manifests/provenance.
