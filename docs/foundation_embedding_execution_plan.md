# Foundation embedding execution plan

Task: `t_8892763b`
Status: implementation plan + first runnable scaffold; not production/full done.

## Scope and current gate

This card does not claim all Jouvence KG embeddings are finished. It establishes the production execution plan, isolated model-family environments, a machine-readable manifest schema, and a first runnable smoke scaffold that writes real staged embedding Parquets under `artifacts/staged/t_8892763b/`.

Canonical input prefix: `gs://jouvencekb/kg/v2/features/`.
Local FUSE path `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2` was probed during this task and returned `Device not configured`, so the live inventory was taken from GCS and copied to `artifacts/staged/t_8892763b/feature_inventory/` for schema inspection and smoke input. No `.omoc` paths are used.

## Live feature inventory

GCS listing at task time showed 12 feature Parquets / 808,269 rows / 201.08 MiB. Schemas and SHA256 hashes are in `artifacts/staged/t_8892763b/feature_inventory/feature_inventory.json`.

| Feature table | Rows | Modality class | Selected model(s) | Model family | Run/env dir | Execution notes |
|---|---:|---|---|---|---|---|
| `cell_line_textual_summary.parquet` | 1,140 | text / ontology summary | `pritamdeka/S-BioBERT-snli-multinli-stsb` first wave; benchmark PubMedBERT/SapBERT later | `text_sbiobert` | `envs/embeddings/text_sbiobert` | Buildable now from official text feature table; one vector per source text row, separate from other modalities. |
| `cell_type_textual_summary.parquet` | 3,135 | text / ontology summary | `pritamdeka/S-BioBERT-snli-multinli-stsb` first wave; benchmark PubMedBERT/SapBERT later | `text_sbiobert` | `envs/embeddings/text_sbiobert` | Buildable now from official text feature table; one vector per source text row, separate from other modalities. |
| `disease_textual_summary.parquet` | 26,395 | text / ontology summary | `pritamdeka/S-BioBERT-snli-multinli-stsb` first wave; benchmark PubMedBERT/SapBERT later | `text_sbiobert` | `envs/embeddings/text_sbiobert` | Buildable now from official text feature table; one vector per source text row, separate from other modalities. |
| `gene_textual_summary.parquet` | 212,029 | text / ontology summary | `pritamdeka/S-BioBERT-snli-multinli-stsb` first wave; benchmark PubMedBERT/SapBERT later | `text_sbiobert` | `envs/embeddings/text_sbiobert` | Buildable now from official text feature table; one vector per source text row, separate from other modalities. |
| `molecule_textual_summary.parquet` | 22,230 | text / ontology summary | `pritamdeka/S-BioBERT-snli-multinli-stsb` first wave; benchmark PubMedBERT/SapBERT later | `text_sbiobert` | `envs/embeddings/text_sbiobert` | Buildable now from official text feature table; one vector per source text row, separate from other modalities. |
| `pathway_textual_summary.parquet` | 37,492 | text / ontology summary | `pritamdeka/S-BioBERT-snli-multinli-stsb` first wave; benchmark PubMedBERT/SapBERT later | `text_sbiobert` | `envs/embeddings/text_sbiobert` | Buildable now from official text feature table; one vector per source text row, separate from other modalities. |
| `phenotype_textual_summary.parquet` | 13,810 | text / ontology summary | `pritamdeka/S-BioBERT-snli-multinli-stsb` first wave; benchmark PubMedBERT/SapBERT later | `text_sbiobert` | `envs/embeddings/text_sbiobert` | Buildable now from official text feature table; one vector per source text row, separate from other modalities. |
| `protein_textual_summary.parquet` | 162,163 | text / ontology summary | `pritamdeka/S-BioBERT-snli-multinli-stsb` first wave; benchmark PubMedBERT/SapBERT later | `text_sbiobert` | `envs/embeddings/text_sbiobert` | Buildable now from official text feature table; one vector per source text row, separate from other modalities. |
| `tissue_textual_summary.parquet` | 11,942 | text / ontology summary | `pritamdeka/S-BioBERT-snli-multinli-stsb` first wave; benchmark PubMedBERT/SapBERT later | `text_sbiobert` | `envs/embeddings/text_sbiobert` | Buildable now from official text feature table; one vector per source text row, separate from other modalities. |
| `molecule_fingerprint.parquet` | 18,614 | molecule fingerprint / SMILES-derived structure baseline | Keep official Morgan sparse baseline; learned ChemBERTa/MolFormer follow-up uses same canonical SMILES policy | `molecule_smiles` | `envs/embeddings/molecule_smiles` | Buildable now for learned SMILES if model/checkpoint is pinned; Morgan table is already official but not a foundation vector. |
| `protein_sequence.parquet` | 112,051 | protein amino-acid sequence | ESM2 `esm2_t33_650M_UR50D`; fallback `esm2_t12_35M_UR50D`; optional 3B after cost approval | `protein_esm2` | `envs/embeddings/protein_esm2` | Buildable now but GPU/windowing required; no silent truncation. |
| `transcript_sequence.parquet` | 187,268 | transcript cDNA / nucleotide sequence | Nucleotide Transformer default; DNABERT-2 fallback | `nucleotide_transformer` | `envs/embeddings/nucleotide_transformer` | Buildable now but long-sequence length audit/windowing required; do not collapse into gene embeddings. |

Feature tables absent/deferred for this wave: gene genomic sequence/interval, promoter windows, enhancer sequence, mutation local allele/context sequence, mature/precursor RNA sequence, Reactome-specific pathway descriptions, cell expression signatures. These require separate source-feature promotion/policy cards before embedding jobs.

Numeric/categorical edge/evidence value features are not in `features/`; they live in `edges/` and `evidence/` and are covered by `docs/edge_evidence_embedding_policy.md`. Production edge embeddings must use a relation/value/evidence encoder with numeric/categorical value MLP/projection and one output vector per canonical edge or PyG edge group.

## Execution waves

1. Text/ontology summary embeddings (`text_sbiobert`):
   - Inputs: all 9 `*_textual_summary.parquet` tables, including official UniProt `protein_textual_summary.parquet`.
   - Default model: `pritamdeka/S-BioBERT-snli-multinli-stsb` via `sentence-transformers`.
   - Expected rows: 490,336 text rows.
   - Output prefix: `artifacts/staged/t_8892763b/text_sbiobert_full/` for review; canonical only after validation/review under `features/embeddings/text/...`.
   - CPU is acceptable for smoke/tiny batches; GPU recommended for full batch.

2. Molecule learned structure embeddings (`molecule_smiles`):
   - Inputs: official `molecule_fingerprint.parquet` plus canonical SMILES fields recorded there (`input_smiles`, `canonical_smiles_rdkit`) and/or source `nodes/molecule.parquet.smiles` after readback verification.
   - Keep Morgan fingerprint as deterministic baseline; do not call it a foundation vector.
   - Default learned model: ChemBERTa/SMILES transformer, benchmark MolFormer later.
   - Output separate from molecule text embeddings.

3. Protein sequence embeddings (`protein_esm2`):
   - Input: `protein_sequence.parquet` (112,051 rows).
   - Default model: ESM2 `esm2_t33_650M_UR50D`; smoke fallback `esm2_t12_35M_UR50D`.
   - GPU required for production. Long proteins must use explicit window/stride/mean-of-window-means policy or be reported skipped; no silent truncation.

4. Transcript cDNA nucleotide embeddings (`nucleotide_transformer`):
   - Input: `transcript_sequence.parquet` (187,268 rows), `alphabet=dna_iupac`.
   - Default model: Nucleotide Transformer; fallback DNABERT-2.
   - Requires length distribution audit and window policy before full run.

5. Edge/evidence value embeddings (`edge_value_mlp`):
   - Inputs: `edges/*.parquet` and `evidence/*.parquet`, not node feature tables.
   - Default: structured relation/value/evidence payload + numeric/categorical learned components + MLP projection + weighted/DeepSets/attention pooling to one vector per canonical edge/group.
   - Output prefix: `features/edge_embeddings/by_relation/<relation>/<model>/<policy>/` after review.

6. Learned fallback embeddings:
   - For nodes/edges without reviewed source payloads, use model-side learned embeddings in downstream training checkpoints, not fabricated canonical KG feature rows.

## First runnable scaffold

Builder module: `manage_db.build_real_embeddings`.

Text-only smoke command used for this card:

```bash
uv run --group embeddings-text python -m manage_db.build_real_embeddings   --kg-root artifacts/staged/t_8892763b/feature_inventory   --output-dir artifacts/staged/t_8892763b/text_sbiobert_smoke   --text-limit-per-table 1   --skip-edge-embeddings   --batch-size 2   --clean
```

Expected smoke output:

- real S-BioBERT vectors for one row per available textual-summary table;
- Parquet files under `artifacts/staged/t_8892763b/text_sbiobert_smoke/features/embeddings/text/...`;
- `manifest.json` and `real_embedding_summary.md`;
- validation checks for duplicate embedding keys, vector dimensionality, finite vectors, and all-zero vectors.

Use `--test-deterministic-encoder` only in unit tests. Production/smoke evidence for this card must use the real sentence-transformer path.

## Environment/run directories

The `pyproject.toml` now defines model-family dependency groups:

- `embeddings-text`: sentence-transformers + torch for S-BioBERT/PubMedBERT/SapBERT text runs.
- `embeddings-edge`: sentence-transformers + torch for relation/value/evidence MLP smoke/full edge runs.
- `embeddings-molecule`: transformers + torch + RDKit for ChemBERTa/MolFormer-style SMILES runs.
- `embeddings-protein`: fair-esm + torch for ESM2 runs.
- `embeddings-nucleotide`: transformers + torch for Nucleotide Transformer/DNABERT-2 runs.

Human-readable runbooks live under `envs/embeddings/<model_family>/README.md`. Each family must write outputs only under `artifacts/staged/<task-id>/...` until validation/review; canonical promotion to `features/` is a separate gate.

## Validation before any full/canonical promotion

For each run:

1. Verify input object list, row counts, schemas, and SHA256/source generation against the manifest.
2. Assert one output key per intended feature row/edge group; no duplicate embedding keys.
3. Assert every vector length equals declared `embedding_dim`; no NaN/Inf/all-zero vectors.
4. Verify no `.omoc` paths in commands, manifest, or outputs.
5. Verify endpoint anti-joins for node embeddings against canonical `nodes/<node_type>.parquet` when node tables are available.
6. Produce skipped-row sidecars with deterministic reasons for invalid SMILES, overlong sequence windows, missing source payloads, or model runtime failures.
7. Require independent review before copying staged outputs to canonical `gs://jouvencekb/kg/v2/features/embeddings/...` or `features/edge_embeddings/...`.

## Follow-up card decomposition

Create separate child cards for:

- full text S-BioBERT production run over all textual-summary feature tables;
- learned molecule SMILES embedding scaffold/run;
- protein ESM2 length audit + smoke + production run;
- transcript nucleotide length audit + smoke + production run;
- edge/evidence value MLP full relation plan/run;
- validation/review gate over all staged embedding manifests before canonical promotion.
